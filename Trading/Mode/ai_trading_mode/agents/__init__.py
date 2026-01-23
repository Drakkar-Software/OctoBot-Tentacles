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
DEPRECATED: This module is kept for backward compatibility.
All agents have been moved to tentacles.Agent.Trading/
Please use the new locations:
- tentacles.Agent.Trading.signal_agent.SignalAgent
- tentacles.Agent.Trading.risk_agent.RiskAgent
- tentacles.Agent.Trading.distribution_agent.DistributionAgent
- tentacles.Agent.Trading.team.AIAgentTeam
"""

# Re-export from new locations for backward compatibility
from tentacles.Agent.Trading.signal_agent import SignalAgent
from tentacles.Agent.Trading.signal_agent.state import AIAgentState
from tentacles.Agent.Trading.risk_agent import RiskAgent
from tentacles.Agent.Trading.distribution_agent import DistributionAgent
from tentacles.Agent.Trading.team import AIAgentTeam

# BaseAgent is now AbstractAIAgentChannelProducer from octobot_agents
from octobot_agents import AbstractAIAgentChannelProducer as BaseAgent

__all__ = [
    "AIAgentTeam",
    "AIAgentState",
    "BaseAgent",
    "SignalAgent",
    "RiskAgent",
    "DistributionAgent",
]
