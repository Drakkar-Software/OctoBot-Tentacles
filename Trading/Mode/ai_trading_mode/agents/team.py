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
AI Agent Team Orchestrator.
Coordinates the execution of all agents in the proper order:
1. Signal agent - analyzes all cryptocurrencies and synthesizes signals
2. Risk agent + Distribution agent (parallel)
3. Complete
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

from tentacles.Trading.Mode.ai_trading_mode.agents.state import AIAgentState
from tentacles.Trading.Mode.ai_trading_mode.agents.signal_agent import SignalAgent
from tentacles.Trading.Mode.ai_trading_mode.agents.risk_agent import RiskAgent
from tentacles.Trading.Mode.ai_trading_mode.agents.distribution_agent import DistributionAgent
from tentacles.Trading.Mode.ai_trading_mode.agents.models import DistributionOutput


class AIAgentTeam:
    """
    Orchestrates the AI agent team for portfolio management.
    
    Execution flow:
    1. Signal agent analyzes all cryptocurrencies and synthesizes signals
    2. Risk agent and Distribution agent run in parallel (after signals complete)
    3. Complete
    """
    
    def __init__(self, llm_service):
        """
        Initialize the agent team.
        
        Args:
            llm_service: The LLM service instance for agent communication.
        """
        self.llm_service = llm_service
        self.logger = logging.getLogger("AITradingTeam")
    
    async def run(
        self,
        global_strategy_data: Dict[str, List[dict]],
        crypto_strategy_data: Dict[str, Dict[str, List[dict]]],
        cryptocurrencies: List[str],
        portfolio: Dict[str, Any],
        orders: Dict[str, Any],
        current_distribution: Dict[str, float],
        reference_market: str = "USD",
        exchange_name: str = "unknown",
    ) -> Optional[DistributionOutput]:
        """
        Execute the full agent pipeline and return distribution decisions.
        
        Args:
            global_strategy_data: Global strategy evaluation data.
            crypto_strategy_data: Per-cryptocurrency strategy data.
            cryptocurrencies: List of cryptocurrencies to analyze.
            portfolio: Current portfolio state from trading API.
            orders: Current orders state from trading API.
            current_distribution: Current portfolio distribution percentages.
            reference_market: The reference market/stablecoin.
            exchange_name: Name of the exchange.
            
        Returns:
            DistributionOutput with final portfolio distribution decisions, or None.
        """
        self.logger.info("Starting AI agent team execution...")
        
        # Initialize state - use dict to avoid type issues with TypedDict
        state: AIAgentState = {}  # type: ignore
        state["global_strategy_data"] = global_strategy_data  # type: ignore
        state["crypto_strategy_data"] = crypto_strategy_data  # type: ignore
        state["cryptocurrencies"] = cryptocurrencies
        state["reference_market"] = reference_market
        state["portfolio"] = portfolio  # type: ignore
        state["orders"] = orders  # type: ignore
        state["current_distribution"] = current_distribution
        state["signal_outputs"] = {"signals": {}}
        state["risk_output"] = None
        state["signal_synthesis"] = None
        state["distribution_output"] = None
        state["exchange_name"] = exchange_name
        state["timestamp"] = datetime.utcnow().isoformat()
        
        state = await self._run_signal_agent(state)
        state = await self._run_risk_agent(state)
        state = await self._run_distribution_agent(state)
        
        self.logger.info("AI agent team execution completed.")
        
        return state.get("distribution_output")
    
    async def _run_signal_agent(self, state: AIAgentState) -> AIAgentState:
        """
        Run the unified signal agent that analyzes all cryptocurrencies at once.
        
        Args:
            state: Current agent state.
            
        Returns:
            Updated state with signal outputs and synthesis.
            
        Raises:
            Exception: Re-raises any exception from signal agent execution.
        """
        signal_agent = SignalAgent()
        
        try:
            result = await signal_agent.execute(state, self.llm_service)
            
            # Extract signal outputs
            if "signal_outputs" in result:
                state["signal_outputs"] = result["signal_outputs"]  # type: ignore
            
            # Extract signal synthesis
            if "signal_synthesis" in result:
                state["signal_synthesis"] = result["signal_synthesis"]
            
            self.logger.info("Signal agent completed successfully.")
        except Exception as e:
            self.logger.error(f"Signal agent failed: {e}")
            # Critical failure - signal analysis is required for downstream agents
            raise Exception(f"Signal agent execution failed, cannot proceed: {e}") from e
        
        return state
    
    async def _run_risk_agent(self, state: AIAgentState) -> AIAgentState:
        """
        Run the risk assessment agent with signal outputs.
        
        Args:
            state: Current agent state with signal outputs.
            
        Returns:
            Updated state with risk output.
            
        Raises:
            Exception: If risk agent fails.
        """
        risk_agent = RiskAgent()
        
        try:
            result = await risk_agent.execute(state, self.llm_service)
            
            # Extract risk output
            if "risk_output" in result:
                state["risk_output"] = result["risk_output"]
            
            self.logger.info("Risk agent completed successfully.")
        except Exception as e:
            self.logger.error(f"Risk agent failed: {e}")
            raise Exception(f"Risk agent execution failed: {e}") from e
        
        return state
    
    async def _run_distribution_agent(self, state: AIAgentState) -> AIAgentState:
        """
        Run the distribution decision agent with signal and risk outputs.
        
        Args:
            state: Current agent state with signal and risk outputs.
            
        Returns:
            Updated state with distribution output.
            
        Raises:
            Exception: If distribution agent fails.
        """
        distribution_agent = DistributionAgent()
        
        try:
            result = await distribution_agent.execute(state, self.llm_service)
            
            # Extract distribution output
            if "distribution_output" in result:
                state["distribution_output"] = result["distribution_output"]
            
            self.logger.info("Distribution agent completed successfully.")
        except Exception as e:
            self.logger.error(f"Distribution agent failed: {e}")
            raise Exception(f"Distribution agent execution failed: {e}") from e
        
        return state
    
    @staticmethod
    def build_portfolio_state(
        exchange_manager,
    ) -> Dict[str, Any]:
        """
        Build portfolio state from exchange manager.
        
        Args:
            exchange_manager: The OctoBot exchange manager.
            
        Returns:
            Portfolio state dictionary.
        """
        import octobot_trading.api as trading_api
        
        portfolio = trading_api.get_portfolio(exchange_manager)
        reference_market = trading_api.get_portfolio_reference_market(exchange_manager)
        
        holdings = {}
        holdings_value = {}
        total_value = 0
        
        for asset, amount in portfolio.items():
            if hasattr(amount, 'total'):
                holdings[asset] = float(amount.total)
            elif isinstance(amount, dict):
                holdings[asset] = float(amount.get('total', 0))
            else:
                holdings[asset] = float(amount)
        
        # Get portfolio value
        try:
            portfolio_value_holder = exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder
            total_value = float(portfolio_value_holder.get_traded_assets_holdings_value(reference_market))
        except Exception:
            total_value = 0
        
        # Get available balance
        try:
            available_balance = float(
                exchange_manager.exchange_personal_data.portfolio_manager.portfolio
                .get_currency_portfolio(reference_market).available
            )
        except Exception:
            available_balance = 0
        
        return {
            "holdings": holdings,
            "holdings_value": holdings_value,
            "total_value": total_value,
            "reference_market": reference_market,
            "available_balance": available_balance,
        }
    
    @staticmethod
    def build_orders_state(exchange_manager) -> Dict[str, Any]:
        """
        Build orders state from exchange manager.
        
        Args:
            exchange_manager: The OctoBot exchange manager.
            
        Returns:
            Orders state dictionary.
        """
        import octobot_trading.api as trading_api
        
        try:
            open_orders = trading_api.get_open_orders(exchange_manager)
            orders_list = [
                {
                    "symbol": order.symbol,
                    "side": order.side.value if hasattr(order.side, 'value') else str(order.side),
                    "type": order.order_type.value if hasattr(order.order_type, 'value') else str(order.order_type),
                    "amount": float(order.origin_quantity),
                    "price": float(order.origin_price) if order.origin_price else None,
                    "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
                }
                for order in open_orders
            ]
        except Exception:
            orders_list = []
        
        return {
            "open_orders": orders_list,
            "pending_orders": [],
            "recent_trades": [],
        }
    
    @staticmethod
    def build_current_distribution(trading_mode) -> Dict[str, float]:
        """
        Build current distribution from trading mode.
        
        Args:
            trading_mode: The AI trading mode instance.
            
        Returns:
            Dictionary of asset to percentage distribution.
        """
        if not hasattr(trading_mode, 'ratio_per_asset') or not trading_mode.ratio_per_asset:
            return {}
        
        from tentacles.Trading.Mode.index_trading_mode import index_distribution
        
        return {
            asset: float(data.get(index_distribution.DISTRIBUTION_VALUE, 0))
            for asset, data in trading_mode.ratio_per_asset.items()
        }
