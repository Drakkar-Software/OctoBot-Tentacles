#  Drakkar-Software OctoBot
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
AI Index Trading Mode module for OctoBot.
Handles AI-driven portfolio rebalancing based on strategy evaluations and external agent instructions.
"""
import os
import typing

import octobot_commons.enums as commons_enums
import octobot_commons.constants as commons_constants
import octobot_evaluators.enums as evaluators_enums
from octobot_evaluators import matrix
import octobot_evaluators.api as evaluators_api
import octobot_commons.evaluators_util as evaluators_util
import octobot_evaluators.constants as evaluators_constants
import octobot_trading.enums as trading_enums
import octobot_trading.modes as trading_modes
import octobot_trading.constants as trading_constants
import octobot_services.api.services as services_api
import tentacles.Services.Services_bases

from tentacles.Trading.Mode.ai_trading_mode import ai_index_distribution
from tentacles.Trading.Mode.index_trading_mode import index_trading
from tentacles.Trading.Mode.ai_trading_mode.agents.team import AIAgentTeam

# Data keys
STRATEGY_DATA_KEY = "strategy_data"
CRYPTO_STRATEGY_DATA_KEY = "crypto_strategy_data"
GLOBAL_STRATEGY_DATA_KEY = "global_strategy_data"
AI_INSTRUCTIONS_KEY = "ai_instructions"


class AIIndexTradingModeProducer(index_trading.IndexTradingModeProducer):
    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)
        # Track global strategy data separately from crypto-specific data
        self._global_strategy_data = {}
        self._crypto_strategy_data = {}  # {cryptocurrency: strategy_data}
        self.services_config = None

    async def set_final_eval(
        self,
        matrix_id: str,
        cryptocurrency: typing.Optional[str],
        symbol: typing.Optional[str],
        time_frame,
        trigger_source: str,
    ) -> None:
        """
        Collect all strategy evaluations and trigger crypto-specific agent analysis.
        Only triggers analysis when both global and crypto-specific data are available.
        """
        if cryptocurrency is None:
            # This is a global evaluation
            global_strategy_data = self._collect_global_strategy_data(matrix_id)
            if global_strategy_data:
                self._global_strategy_data = global_strategy_data
        else:
            # This is a cryptocurrency-specific evaluation
            crypto_strategy_data = self._collect_crypto_strategy_data(
                matrix_id, cryptocurrency, symbol, time_frame
            )
            if crypto_strategy_data:
                self._crypto_strategy_data[cryptocurrency] = crypto_strategy_data
                await self._trigger_crypto_analysis(
                    crypto_strategy_data, cryptocurrency, symbol, time_frame
                )

    def _collect_global_strategy_data(self, matrix_id: str) -> dict:
        """
        Collect strategy data from global evaluations (cryptocurrency=None).
        These come from GlobalLLMAIStrategyEvaluator.
        """
        strategy_data = {}
        strategy_type = evaluators_enums.EvaluatorMatrixTypes.STRATEGIES.value
        tentacle_nodes = matrix.get_tentacle_nodes(
            matrix_id=matrix_id,
            exchange_name=self.exchange_name,
            tentacle_type=strategy_type,
        )
        # Get global strategy nodes (cryptocurrency=None)
        for evaluated_strategy_node in matrix.get_tentacles_value_nodes(
            matrix_id,
            tentacle_nodes,
            cryptocurrency=None,
            symbol=None,
            time_frame=None,
        ):
            if evaluators_util.check_valid_eval_note(
                evaluators_api.get_value(evaluated_strategy_node),
                evaluators_api.get_type(evaluated_strategy_node),
                evaluators_constants.EVALUATOR_EVAL_DEFAULT_TYPE,
            ):
                eval_note = evaluators_api.get_value(evaluated_strategy_node)
                note_description = evaluators_api.get_description(evaluated_strategy_node)
                note_metadata = evaluators_api.get_metadata(evaluated_strategy_node)

                if strategy_type not in strategy_data:
                    strategy_data[strategy_type] = []

                strategy_data[strategy_type].append(
                    {
                        "eval_note": eval_note,
                        "description": note_description,
                        "metadata": note_metadata,
                        "cryptocurrency": None,
                        "symbol": None,
                        "evaluation_type": "global",
                    }
                )

        return strategy_data

    def _collect_crypto_strategy_data(
        self,
        matrix_id: str,
        cryptocurrency: str,
        symbol: typing.Optional[str],
        time_frame=None,
    ) -> dict:
        """
        Collect strategy data from cryptocurrency-specific evaluations.
        These come from CryptoLLMAIStrategyEvaluator.
        """
        strategy_data = {}
        strategy_type = evaluators_enums.EvaluatorMatrixTypes.STRATEGIES.value
        tentacle_nodes = matrix.get_tentacle_nodes(
            matrix_id=matrix_id,
            exchange_name=self.exchange_name,
            tentacle_type=strategy_type,
        )
        for evaluated_strategy_node in matrix.get_tentacles_value_nodes(
            matrix_id,
            tentacle_nodes,
            cryptocurrency=cryptocurrency,
            symbol=symbol,
            time_frame=time_frame,
        ):
            if evaluators_util.check_valid_eval_note(
                evaluators_api.get_value(evaluated_strategy_node),
                evaluators_api.get_type(evaluated_strategy_node),
                evaluators_constants.EVALUATOR_EVAL_DEFAULT_TYPE,
            ):
                eval_note = evaluators_api.get_value(evaluated_strategy_node)
                note_description = evaluators_api.get_description(evaluated_strategy_node)
                note_metadata = evaluators_api.get_metadata(evaluated_strategy_node)

                if strategy_type not in strategy_data:
                    strategy_data[strategy_type] = []

                strategy_data[strategy_type].append(
                    {
                        "eval_note": eval_note,
                        "description": note_description,
                        "metadata": note_metadata,
                        "cryptocurrency": cryptocurrency,
                        "symbol": symbol,
                        "evaluation_type": "crypto_specific",
                    }
                )

        return strategy_data

    def _collect_all_strategy_data(
        self, matrix_id: str, cryptocurrency: str, symbol: str, time_frame=None
    ) -> dict:
        """
        Legacy method: Collect all strategy data (both global and crypto-specific).
        Kept for backwards compatibility.
        """
        strategy_data = {}
        strategy_type = evaluators_enums.EvaluatorMatrixTypes.STRATEGIES.value
        tentacle_nodes = matrix.get_tentacle_nodes(
            matrix_id=matrix_id,
            exchange_name=self.exchange_name,
            tentacle_type=strategy_type,
        )
        for evaluated_strategy_node in matrix.get_tentacles_value_nodes(
            matrix_id,
            tentacle_nodes,
            cryptocurrency=cryptocurrency,
            symbol=symbol,
            time_frame=time_frame,
        ):
            if evaluators_util.check_valid_eval_note(
                evaluators_api.get_value(evaluated_strategy_node),
                evaluators_api.get_type(evaluated_strategy_node),
                evaluators_constants.EVALUATOR_EVAL_DEFAULT_TYPE,
            ):
                eval_note = evaluators_api.get_value(evaluated_strategy_node)
                note_description = evaluators_api.get_description(evaluated_strategy_node)
                note_metadata = evaluators_api.get_metadata(evaluated_strategy_node)

                if strategy_type not in strategy_data:
                    strategy_data[strategy_type] = []

                strategy_data[strategy_type].append(
                    {
                        "eval_note": eval_note,
                        "description": note_description,
                        "metadata": note_metadata,
                        "cryptocurrency": cryptocurrency,
                        "symbol": symbol,
                    }
                )

        return strategy_data

    async def _trigger_crypto_analysis(
        self,
        crypto_strategy_data: dict,
        cryptocurrency: str,
        symbol: typing.Optional[str],
        time_frame,
    ):
        """
        Handle cryptocurrency-specific strategy analysis from CryptoLLMAIStrategyEvaluator.
        This is only triggered when both global and crypto-specific data are available.
        Runs the AI agent team to generate portfolio distribution decisions.
        """
        if not self._global_strategy_data or cryptocurrency not in self._crypto_strategy_data:
            self.logger.debug(
                f"Skipping crypto analysis for {cryptocurrency} as global strategy data is not available."
            )
            return
        
        # Check if all cryptocurrencies have been analyzed
        # Only run the full agent team when we have data for all tracked coins
        indexed_coins = getattr(self.trading_mode, 'indexed_coins', [])
        if not indexed_coins:
            self.logger.debug("No indexed coins configured, skipping agent analysis.")
            return
        
        # Check if we have crypto strategy data for all indexed coins
        all_coins_ready = all(
            coin in self._crypto_strategy_data 
            for coin in indexed_coins
        )
        
        if not all_coins_ready:
            self.logger.debug(
                f"Waiting for all crypto strategy data. "
                f"Have: {list(self._crypto_strategy_data.keys())}, "
                f"Need: {indexed_coins}"
            )
            return
        
        self.logger.info("All strategy data collected. Running AI agent team...")
        
        try:
            await self._run_agent_team()
        except Exception as e:
            self.logger.exception(f"Error running AI agent team: {e}")
    
    async def _run_agent_team(self):
        """
        Run the AI agent team to analyze portfolio and generate distribution decisions.
        """        
        # Get LLM service
        llm_service = await self._get_llm_service()
        if llm_service is None:
            self.logger.error("Failed to create LLM service. Check AI configuration.")
            return
        
        # Build agent team
        agent_team = AIAgentTeam(llm_service=llm_service)
        
        # Get portfolio and orders state
        portfolio_state = AIAgentTeam.build_portfolio_state(self.exchange_manager)
        orders_state = AIAgentTeam.build_orders_state(self.exchange_manager)
        current_distribution = AIAgentTeam.build_current_distribution(self.trading_mode)
        
        # Get cryptocurrencies
        cryptocurrencies = list(self._crypto_strategy_data.keys())
        reference_market = self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
        
        # Run agent team
        self.logger.info("Running AI agent team for portfolio distribution analysis...")
        distribution_output = await agent_team.run(
            global_strategy_data=self._global_strategy_data,
            crypto_strategy_data=self._crypto_strategy_data,
            cryptocurrencies=cryptocurrencies,
            portfolio=portfolio_state,
            orders=orders_state,
            current_distribution=current_distribution,
            reference_market=reference_market,
            exchange_name=self.exchange_name,
        )
        
        if distribution_output is None:
            self.logger.warning("Agent team returned no distribution output.")
            return
        
        self.logger.info(
            f"Agent team completed. Urgency: {distribution_output.rebalance_urgency}"
        )
        
        # Convert to AI instructions and trigger rebalance
        ai_instructions = distribution_output.get_ai_instructions()
        
        if ai_instructions and distribution_output.rebalance_urgency != "none":
            await self._submit_trading_evaluation(ai_instructions)
    
    async def _get_llm_service(self):
        """Get the LLM service instance."""
        try:
            gpt_service_class = tentacles.Services.Services_bases.LLMService
        except (AttributeError, ImportError):
            self.logger.error("LLMService not available, cannot perform LLM analysis")
            return None

        gpt_service = await services_api.get_service(
            gpt_service_class, self.exchange_manager.is_backtesting, self.services_config
        )
        if not gpt_service:
            self.logger.error("LLMService not available, cannot perform LLM analysis")
            return None
        return gpt_service
    
    async def _submit_trading_evaluation(self, ai_instructions: list):
        """
        Submit AI instructions to trigger portfolio rebalancing.
        """
        ai_index_distribution.apply_ai_instructions(
            self.trading_mode, ai_instructions
        )
        await self.ensure_index()


class AIIndexTradingModeConsumer(index_trading.IndexTradingModeConsumer):
    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True


class AIIndexTradingMode(index_trading.IndexTradingMode):
    """
    AI-driven Index Trading Mode that uses GPT to generate dynamic portfolio distributions
    based on strategy evaluation descriptions, inheriting rebalancing logic from IndexTradingMode.
    """

    MODE_PRODUCER_CLASSES = [AIIndexTradingModeProducer]
    MODE_CONSUMER_CLASSES = [AIIndexTradingModeConsumer]

    # AI-specific config keys
    MODEL_KEY = "model"
    TEMPERATURE_KEY = "temperature"
    MAX_TOKENS_KEY = "max_tokens"

    async def single_exchange_process_health_check(self, chained_orders, tickers):
        return []

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)

    def init_user_inputs(self, inputs: dict) -> None:
        """
        Initialize user inputs for AI configuration.
        """
        super().init_user_inputs(inputs)

        # AI Model Configuration
        self.UI.user_input(
            self.MODEL_KEY,
            commons_enums.UserInputTypes.TEXT,
            inputs.get(self.MODEL_KEY),
            inputs,
            title="LLM model to use for AI strategy.",
        )

        self.UI.user_input(
            self.TEMPERATURE_KEY,
            commons_enums.UserInputTypes.FLOAT,
            inputs.get(self.TEMPERATURE_KEY),
            inputs,
            min_val=0.0,
            max_val=1.0,
            title="Temperature for AI randomness (0.0 = deterministic, 1.0 = creative).",
        )

        self.UI.user_input(
            self.MAX_TOKENS_KEY,
            commons_enums.UserInputTypes.INT,
            inputs.get(self.MAX_TOKENS_KEY),
            inputs,
            min_val=500,
            max_val=4000,
            title="Maximum tokens for AI response.",
        )
