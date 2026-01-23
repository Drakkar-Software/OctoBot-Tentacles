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
AI Trading Agent Team.
Orchestrates Signal, Risk, and Distribution agents for portfolio management.

DAG Structure:
    Signal ──┬──> Risk ──┐
             │           ├──> Distribution
             └───────────┘
             
The Distribution agent receives inputs from both Signal and Risk agents.
"""
import typing

import octobot_agents as agent

from tentacles.Agent.Trading.signal_agent import (
    SignalAIAgentChannel,
    SignalAIAgentProducer,
)
from tentacles.Agent.Trading.risk_agent import (
    RiskAIAgentChannel,
    RiskAIAgentProducer,
)
from tentacles.Agent.Trading.distribution_agent import (
    DistributionAIAgentChannel,
    DistributionAIAgentProducer,
    DistributionOutput,
)


class TradingAgentTeamChannel(agent.AbstractAgentTeamChannel):
    """Channel for TradingAgentTeam outputs."""
    OUTPUT_SCHEMA = DistributionOutput


class TradingAgentTeamConsumer(agent.AbstractAgentTeamChannelConsumer):
    """Consumer for TradingAgentTeam outputs."""
    pass


class TradingAgentTeam(agent.AbstractSyncAgentTeamChannelProducer):
    """
    Sync team that orchestrates trading agents for portfolio distribution.
    
    Execution flow:
    1. Signal agent analyzes cryptocurrencies and generates signals
    2. Risk agent evaluates portfolio risk based on signal outputs
    3. Distribution agent makes final allocation decisions
    
    Usage:
        team = TradingAgentTeam(ai_service=llm_service)
        results = await team.run(agent_state)
        distribution_output = results["DistributionAgent"]["distribution_output"]
    """
    
    TEAM_NAME = "TradingAgentTeam"
    TEAM_CHANNEL = TradingAgentTeamChannel
    TEAM_CONSUMER = TradingAgentTeamConsumer
    
    def __init__(
        self,
        ai_service: typing.Any,
        model: typing.Optional[str] = None,
        max_tokens: typing.Optional[int] = None,
        temperature: typing.Optional[float] = None,
        channel: typing.Optional[TradingAgentTeamChannel] = None,
        team_id: typing.Optional[str] = None,
    ):
        """
        Initialize the trading agent team.
        
        Args:
            ai_service: The LLM service instance.
            model: LLM model to use for all agents.
            max_tokens: Maximum tokens for LLM responses.
            temperature: Temperature for LLM randomness.
            channel: Optional output channel for team results.
            team_id: Unique identifier for this team instance.
        """
        # Create agent producers
        signal_producer = SignalAIAgentProducer(
            channel=None,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        risk_producer = RiskAIAgentProducer(
            channel=None,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        distribution_producer = DistributionAIAgentProducer(
            channel=None,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        agents = [signal_producer, risk_producer, distribution_producer]
        
        # Define relations:
        # Signal -> Risk (Risk needs signal synthesis)
        # Signal -> Distribution (Distribution needs signal outputs)
        # Risk -> Distribution (Distribution needs risk assessment)
        relations = [
            (SignalAIAgentChannel, RiskAIAgentChannel),
            (SignalAIAgentChannel, DistributionAIAgentChannel),
            (RiskAIAgentChannel, DistributionAIAgentChannel),
        ]
        
        super().__init__(
            channel=channel,
            agents=agents,
            relations=relations,
            ai_service=ai_service,
            team_name=self.TEAM_NAME,
            team_id=team_id,
        )
    
    async def run_with_state(
        self,
        state: dict,
    ) -> typing.Optional["DistributionOutput"]:
        """
        Convenience method to run the team with an agent state dict.
        
        Args:
            state: Dict containing portfolio, strategy data, etc.
            
        Returns:
            DistributionOutput from the distribution agent, or None on error.
        """
        # Run the team
        results = await self.run(state)
        
        # Extract distribution result
        distribution_result = results.get("DistributionAgent")
        if distribution_result is None:
            return None
        
        # Handle dict result format
        if isinstance(distribution_result, dict):
            return distribution_result.get("distribution_output")
        
        return distribution_result
