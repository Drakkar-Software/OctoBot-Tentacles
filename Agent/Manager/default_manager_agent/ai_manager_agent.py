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
"""
AI team manager agent - uses LLM to decide execution flow.
"""
import typing
from typing import TYPE_CHECKING

from octobot_agents.agent import (
    AbstractAgentChannel,
    AbstractAgentChannelConsumer,
    AbstractAIAgentChannelProducer,
)
from octobot_agents.team.manager.manager_agent import AbstractTeamManagerAgent
from octobot_agents.models import ExecutionPlan

if TYPE_CHECKING:
    from octobot_agents.models import ManagerInput


class AITeamManagerAgentChannel(AbstractAgentChannel):
    """Channel for AI team manager."""
    __slots__ = ()


class AITeamManagerAgentConsumer(AbstractAgentChannelConsumer):
    """Consumer for AI team manager."""
    __slots__ = ()


class AITeamManagerAgentProducer(AbstractAIAgentChannelProducer, AbstractTeamManagerAgent):
    """
    AI team manager agent - uses LLM to decide execution flow.
    
    Inherits from AbstractAIAgentChannelProducer AND AbstractTeamManagerAgent.
    Has Channel, Producer, Consumer components (as all AI agents do).
    """
    
    AGENT_CHANNEL: typing.Type[AbstractAgentChannel] = AITeamManagerAgentChannel
    AGENT_CONSUMER: typing.Type[AbstractAgentChannelConsumer] = AITeamManagerAgentConsumer
    
    def __init__(
        self,
        channel: typing.Optional[AITeamManagerAgentChannel] = None,
        model: typing.Optional[str] = None,
        max_tokens: typing.Optional[int] = None,
        temperature: typing.Optional[float] = None,
    ):
        AbstractTeamManagerAgent.__init__(self)
        AbstractAIAgentChannelProducer.__init__(self, channel, model=model, max_tokens=max_tokens, temperature=temperature)
    
    def _get_default_prompt(self) -> str:
        """
        Return the default prompt for the AI team manager.
        
        Returns:
            The default system prompt string.
        """
        return """You are a team execution manager for an agent team system.
Your role is to analyze the team structure, current state, and any instructions,
then create an execution plan that determines:
1. Which agents to execute
2. In what order
3. What instructions to send to each agent
4. Whether to loop execution

The execution plan should optimize for the team's goals while respecting dependencies."""
    
    async def execute(
        self,
        input_data: typing.Union["ManagerInput", typing.Dict[str, typing.Any]],
        ai_service: typing.Any  # AbstractAIService - type not available at runtime
    ) -> ExecutionPlan:
        """
        Build execution plan using LLM.
        
        Args:
            input_data: Contains {"team_producer": team_producer, "initial_data": initial_data, "instructions": instructions}
            ai_service: The AI service instance for LLM calls
            
        Returns:
            ExecutionPlan from LLM
        """
        team_producer = input_data.get("team_producer")
        initial_data = input_data.get("initial_data", {})
        instructions = input_data.get("instructions")
        
        if team_producer is None:
            raise ValueError("team_producer is required in input_data")
        
        # Build context
        agents_info = []
        for agent in team_producer.agents:
            agents_info.append({
                "name": agent.name,
                "channel": agent.AGENT_CHANNEL.__name__ if agent.AGENT_CHANNEL else None,
            })
        
        relations_info = []
        for source_channel, target_channel in team_producer.relations:
            relations_info.append({
                "source": source_channel.__name__,
                "target": target_channel.__name__,
            })
        
        context = {
            "team_name": team_producer.team_name,
            "agents": agents_info,
            "relations": relations_info,
            "initial_data": initial_data,
            "instructions": instructions,
        }
        
        # Build messages for LLM
        messages = [
            {"role": "system", "content": self.prompt},
            {
                "role": "user",
                "content": f"""Analyze the following team structure and create an execution plan:

Team: {team_producer.team_name}
Agents: {self.format_data(agents_info)}
Relations: {self.format_data(relations_info)}
Initial Data: {self.format_data(initial_data)}
Instructions: {self.format_data(instructions) if instructions else "None"}

Create an execution plan that determines the order and instructions for each agent."""
            },
        ]
        
        # Call LLM with ExecutionPlan as response schema
        response_data = await self._call_llm(
            messages,
            ai_service,
            json_output=True,
            response_schema=ExecutionPlan,
        )
        
        # Parse into ExecutionPlan model
        execution_plan = ExecutionPlan.model_validate(response_data)
        
        self.logger.debug(f"Generated execution plan with {len(execution_plan.steps)} steps")
        
        return execution_plan
