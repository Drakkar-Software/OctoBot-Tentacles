#  Drakkar-Software OctoBot-Tentacles
#  Copyright (c) Drakkar-Software, All rights reserved.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.
import typing

from octobot_agents.agent.channels.agent import (
    AbstractAgentChannel,
    AbstractAgentChannelConsumer,
    AbstractAgentChannelProducer,
)
from octobot_agents.agent.memory.channels.memory_agent import AbstractMemoryAgent
import octobot_agents.models as models
from octobot_agents.constants import (
    MEMORY_TITLE_MAX_LENGTH,
    MEMORY_CONTEXT_MAX_LENGTH,
    MEMORY_CONTENT_MAX_LENGTH,
)

class DefaultMemoryAgentChannel(AbstractAgentChannel):
    """Channel for default memory agent."""
    __slots__ = ()


class DefaultMemoryAgentConsumer(AbstractAgentChannelConsumer):
    """Consumer for default memory agent."""
    __slots__ = ()


class DefaultMemoryAgentProducer(AbstractAgentChannelProducer, AbstractMemoryAgent):
    """
    Default memory agent - simple rule-based memory operations.
    
    Inherits from AbstractAgentChannelProducer AND AbstractMemoryAgent.
    Uses simple heuristics instead of LLM.
    """
    
    AGENT_CHANNEL: typing.Type[AbstractAgentChannel] = DefaultMemoryAgentChannel
    AGENT_CONSUMER: typing.Type[AbstractAgentChannelConsumer] = DefaultMemoryAgentConsumer
    
    def __init__(
        self,
        channel: typing.Optional[DefaultMemoryAgentChannel] = None,
        self_improving: bool = True,
    ):
        AbstractMemoryAgent.__init__(self, self_improving=self_improving)
        AbstractAgentChannelProducer.__init__(self, channel)
        self.name = self.__class__.__name__
    
    def _transform_to_instructions(
        self,
        improvement: models.AgentImprovement,
        agent_name: str
    ) -> typing.Tuple[str, str, str]:
        """
        Transform critic feedback into actionable instructions using heuristics.
        
        Args:
            improvement: The AgentImprovement model with critic feedback
            agent_name: Name of the agent
            
        Returns:
            Tuple of (title, content, context) for the memory
        """
        improvements_list = improvement.improvements
        issues_list = improvement.issues
        reasoning = improvement.reasoning
        
        # Build structured actions from improvements and issues
        structured_actions = []
        
        # Transform common issues into short, direct commands
        for issue in issues_list:
            issue_lower = issue.lower()
            if "empty dict" in issue_lower or "empty result" in issue_lower:
                structured_actions.append("Return structured output")
            elif "schema validation failed" in issue_lower or "validation failed" in issue_lower:
                structured_actions.append("Validate schema")
            elif "missing data" in issue_lower or "missing field" in issue_lower:
                structured_actions.append("Include all required fields")
            elif "incorrect" in issue_lower or "wrong" in issue_lower:
                structured_actions.append("Verify output format")
            elif "tuple" in issue_lower and "expected" in issue_lower:
                structured_actions.append("Return dict format")
        
        # Add improvements as short commands if not already covered
        for improvement_text in improvements_list:
            improvement_lower = improvement_text.lower()
            if "quality" in improvement_lower:
                if not any("validate" in action.lower() or "structure" in action.lower() for action in structured_actions):
                    structured_actions.append("Validate output")
            elif "completeness" in improvement_lower:
                if not any("complete" in action.lower() or "missing" in action.lower() or "include" in action.lower() for action in structured_actions):
                    structured_actions.append("Include all fields")
            elif "correctness" in improvement_lower:
                if not any("correct" in action.lower() or "verify" in action.lower() for action in structured_actions):
                    structured_actions.append("Verify output")
        
        # If no structured actions were generated, create short commands from improvements
        if not structured_actions:
            for improvement_text in improvements_list:
                # Make it short and imperative
                improvement_short = improvement_text.lower()
                if "improve" in improvement_short:
                    improvement_short = improvement_short.replace("improve", "").strip()
                if "quality" in improvement_short:
                    structured_actions.append("Validate output")
                elif "completeness" in improvement_short:
                    structured_actions.append("Include all fields")
                elif "correctness" in improvement_short:
                    structured_actions.append("Verify output")
                else:
                    # Extract key verb/noun, make imperative
                    words = improvement_short.split()[:3]  # Take first 3 words max
                    structured_actions.append(" ".join(words).capitalize())
        
        # Build content as simple command list - no headers
        content_parts = []
        for action in structured_actions:
            # Remove numbering if present
            action_clean = action.lstrip("0123456789. ").strip()
            if action_clean:
                content_parts.append(action_clean)
        
        content = "\n".join(content_parts) if content_parts else "Follow instructions"
        
        # Generate short, direct title from first issue or improvement
        if issues_list:
            # Extract short problem description from first issue
            first_issue = issues_list[0].lower()
            if "schema validation" in first_issue or "validation failed" in first_issue:
                title = "Validate schema"
            elif "empty dict" in first_issue or "empty result" in first_issue:
                title = "Return structured output"
            elif "missing" in first_issue:
                title = "Include all fields"
            elif "tuple" in first_issue:
                title = "Return dict format"
            else:
                # Extract key words (max 3-4 words)
                words = first_issue.split()[:4]
                title = " ".join(words).capitalize()
        elif improvements_list:
            # Extract short command from first improvement
            first_improvement = improvements_list[0].lower()
            if "quality" in first_improvement:
                title = "Validate output"
            elif "completeness" in first_improvement:
                title = "Include all fields"
            elif "correctness" in first_improvement:
                title = "Verify output"
            else:
                words = first_improvement.split()[:3]
                title = " ".join(words).capitalize()
        elif reasoning:
            # Extract short command from reasoning
            reasoning_lower = reasoning.lower()
            if "schema" in reasoning_lower:
                title = "Validate schema"
            elif "empty" in reasoning_lower:
                title = "Return structured output"
            else:
                words = reasoning.split()[:3]
                title = " ".join(words).capitalize()
        else:
            title = "Follow instructions"
        
        # Truncate title if needed
        if len(title) > MEMORY_TITLE_MAX_LENGTH:
            truncated = title[:MEMORY_TITLE_MAX_LENGTH]
            last_space = truncated.rfind(' ')
            if last_space > MEMORY_TITLE_MAX_LENGTH * 0.7:
                title = truncated[:last_space].strip()
            else:
                title = truncated.strip()
        
        # Build short, focused context - just the problem, no verbose descriptions
        if issues_list:
            # Extract short problem description from first issue
            first_issue = issues_list[0]
            if "schema validation failed" in first_issue.lower():
                context = "Schema validation failed"
            elif "empty dict" in first_issue.lower() or "empty result" in first_issue.lower():
                context = "Empty output"
            elif "missing" in first_issue.lower():
                context = "Missing fields"
            elif "tuple" in first_issue.lower():
                context = "Wrong format"
            else:
                # Extract first few words (max 5-6 words)
                words = first_issue.split()[:6]
                context = " ".join(words)
                # Remove common verbose prefixes
                context = context.replace("Agent ", "").replace("produced result with ", "").replace("quality issues. ", "")
        else:
            context = "Quality issue"
        
        # Truncate context if needed
        if len(context) > MEMORY_CONTEXT_MAX_LENGTH:
            truncated = context[:MEMORY_CONTEXT_MAX_LENGTH]
            last_space = truncated.rfind(' ')
            if last_space > MEMORY_CONTEXT_MAX_LENGTH * 0.7:
                context = truncated[:last_space].strip()
            else:
                context = truncated.strip()
        
        # Truncate content if needed at sentence boundary
        if len(content) > MEMORY_CONTENT_MAX_LENGTH:
            truncated = content[:MEMORY_CONTENT_MAX_LENGTH]
            last_period = truncated.rfind('.')
            last_newline = truncated.rfind('\n')
            last_break = max(last_period, last_newline)
            if last_break > MEMORY_CONTENT_MAX_LENGTH * 0.7:
                content = truncated[:last_break + 1].strip()
            else:
                content = truncated.strip()
        
        return title, content, context
    
    async def execute(
        self,
        input_data: typing.Union[models.MemoryInput, typing.Dict[str, typing.Any]],
        ai_service: typing.Any  # AbstractAIService - type not available at runtime
    ) -> models.MemoryOperation:
        """
        Execute memory operations using simple heuristics.
        
        Args:
            input_data: Contains {"critic_analysis": CriticAnalysis, "agent_outputs": Dict, "execution_metadata": dict}
            ai_service: Not used by default memory agent
            
        Returns:
            MemoryOperation with list of operations performed
        """
        critic_analysis = input_data.get("critic_analysis")
        agent_outputs = input_data.get("agent_outputs", {})
        
        if not critic_analysis:
            return models.MemoryOperation(
                success=False,
                operations=[],
                memory_ids=[],
                agent_updates={},
                agents_processed=[],
                agents_skipped=list(agent_outputs.keys()),
                message="No critic analysis provided",
            )
        
        # Validate critic_analysis to ensure it's a model
        critic_analysis = models.CriticAnalysis.model_validate_or_self(critic_analysis)
        
        # Get agent_improvements dict
        agent_improvements = critic_analysis.get_agent_improvements()
        agents_to_process = list(agent_improvements.keys())
        
        if not agents_to_process:
            return models.MemoryOperation(
                success=True,
                operations=[],
                memory_ids=[],
                agent_updates={},
                agents_processed=[],
                agents_skipped=list(agent_outputs.keys()),
                message="No agents need memory updates",
            )
        
        operations = []
        memory_ids = []
        agent_updates = {}
        agents_processed = []
        agents_skipped = []
        
        # Get team producer for agent version lookup
        execution_metadata = input_data.get("execution_metadata", {})
        team_producer = execution_metadata.get("team_producer")
        
        # Process each agent
        for agent_name in agents_to_process:
            improvement = agent_improvements[agent_name]
            
            # Validate improvement to ensure it's a model
            improvement = models.AgentImprovement.model_validate_or_self(improvement)
            
            # Get agent instance to check if memory is enabled
            agent = self._get_agent_from_team(team_producer, agent_name)
            
            # Check if agent has memory enabled
            if agent is None:
                agents_skipped.append(agent_name)
                continue
            
            try:
                memory_enabled = agent.has_memory_enabled()
            except AttributeError:
                # Agent doesn't have memory_manager, skip it
                agents_skipped.append(agent_name)
                continue
            
            # Skip agents without memory enabled
            if not memory_enabled:
                agents_skipped.append(agent_name)
                continue
            
            # Use agent's existing memory_manager instead of creating a new one
            agent_memory_storage = agent.memory_manager
            
            # Transform critic feedback into actionable instructions
            title, content, context = self._transform_to_instructions(improvement, agent_name)
            
            # Store the actionable instruction as memory
            await agent_memory_storage.store_memory(
                messages=[{"role": "user", "content": content}],
                input_data={"agent_id": ""},
                metadata={
                    "category": "improvement",
                    "importance_score": 0.7,
                    "title": title,
                    "context": context,
                }
            )
            
            # Get newly created memory ID
            all_memories = agent_memory_storage.get_all_memories()
            if all_memories:
                new_memory_id = all_memories[-1].get("id")
                memory_ids.append(new_memory_id)
                agent_updates.setdefault(agent_name, []).append(new_memory_id)
                operations.append("generated")
            
            agents_processed.append(agent_name)
        
        # Add agents not in agent_improvements to skipped list
        all_agent_names = self._collect_all_agent_names(agent_outputs, team_producer)
        for name in all_agent_names:
            if name not in agents_to_process and name not in agents_skipped:
                agents_skipped.append(name)
        
        return models.MemoryOperation(
            success=True,
            operations=operations,
            memory_ids=memory_ids,
            agent_updates=agent_updates,
            agents_processed=agents_processed,
            agents_skipped=agents_skipped,
            message=f"Generated memories for {len(agents_processed)} agents",
        )
