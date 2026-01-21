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
import octobot_evaluators.enums as evaluators_enums
from .base_agent import BaseAgent
from .summarization_agent import SummarizationAgent
from .technical_analysis_agent import TechnicalAnalysisAgent
from .sentiment_analysis_agent import SentimentAnalysisAgent
from .real_time_analysis_agent import RealTimeAnalysisAgent


class AgentFactory:
    """Factory for creating LLM agents."""

    @staticmethod
    def create_summarization_agent(
        synthesis_method="weighted", **config
    ) -> SummarizationAgent:
        return SummarizationAgent(synthesis_method=synthesis_method, **config)

    @staticmethod
    def create_technical_agent(**config) -> TechnicalAnalysisAgent:
        return TechnicalAnalysisAgent(**config)

    @staticmethod
    def create_sentiment_agent(**config) -> SentimentAnalysisAgent:
        return SentimentAnalysisAgent(**config)

    @staticmethod
    def create_realtime_agent(**config) -> RealTimeAnalysisAgent:
        return RealTimeAnalysisAgent(**config)

    @staticmethod
    def create_agent_for_evaluator_type(evaluator_type: str, **config) -> BaseAgent:
        """Create appropriate agent for evaluator type."""
        type_to_agent = {
            evaluators_enums.EvaluatorMatrixTypes.TA.value: TechnicalAnalysisAgent,
            evaluators_enums.EvaluatorMatrixTypes.SOCIAL.value: SentimentAnalysisAgent,
            evaluators_enums.EvaluatorMatrixTypes.REAL_TIME.value: RealTimeAnalysisAgent,
        }
        agent_class = type_to_agent.get(evaluator_type)
        if agent_class:
            return agent_class(**config)
        raise ValueError(f"No agent available for evaluator type: {evaluator_type}")
