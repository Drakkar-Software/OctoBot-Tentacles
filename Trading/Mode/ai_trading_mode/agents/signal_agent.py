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
Signal Agent.
Analyzes all cryptocurrencies and generates both individual and synthesized signals.
Combines per-crypto analysis with overall market signal synthesis in a single agent.
"""
import json
import typing

from pydantic import BaseModel

from tentacles.Trading.Mode.ai_trading_mode.agents.base_agent import BaseAgent
from tentacles.Trading.Mode.ai_trading_mode.agents.state import AIAgentState
from tentacles.Trading.Mode.ai_trading_mode.agents.models import CryptoSignalOutput, SignalSynthesisOutput


class SignalAgent(BaseAgent):
    """
    Signal agent that analyzes all cryptocurrencies and synthesizes signals.
    
    This agent:
    1. Analyzes each cryptocurrency against all available data
    2. Generates individual signals with confidence levels
    3. Synthesizes signals across all cryptos to identify market consensus
    """
    
    AGENT_NAME = "SignalAgent"
    AGENT_VERSION = "1.0.0"
    
    def __init__(self, model=None, max_tokens=None, temperature=None):
        """
        Initialize the signal agent.
        
        Args:
            model: LLM model to use.
            max_tokens: Maximum tokens for response.
            temperature: Temperature for LLM randomness.
        """
        super().__init__(
            name=self.AGENT_NAME,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    
    def _get_default_prompt(self) -> str:
        """Return the default system prompt."""
        return """
You are a Comprehensive Signal Analysis Agent for cryptocurrency portfolio management.
Your task is to analyze all tracked cryptocurrencies and generate both individual trading signals and synthesized market signals.

## Your Dual Role

### Part 1: Per-Cryptocurrency Analysis
- Analyze each cryptocurrency provided
- Consider global market strategy data and crypto-specific data
- Consider current portfolio holdings and open orders
- Generate a clear trading signal with confidence level
- Identify key factors driving each signal

### Part 2: Signal Synthesis (CRITICAL)
- Identify consensus across cryptocurrency signals
- Synthesize signals into clear trading instructions
- Provide overall market outlook
- Do NOT make allocation decisions - only synthesize

## Per-Crypto Signal Actions (for "action" field only)
- "buy": Strong bullish signal, recommend increasing position
- "sell": Strong bearish signal, recommend decreasing position
- "hold": Neutral signal, recommend maintaining current position
- "increase": Moderate bullish, suggest gradual increase
- "decrease": Moderate bearish, suggest gradual decrease

## CRITICAL: Synthesis Direction Values (for "direction" field ONLY)
When synthesizing signals, ALWAYS use ONLY these exact values for direction:
- "bullish": Positive market direction
- "bearish": Negative market direction
- "neutral": No clear direction

DO NOT use "buy", "sell", "hold", "increase", or "decrease" in the direction field. ONLY use: bullish, bearish, or neutral.

## Consensus Levels (for "consensus_level" field)
Must be EXACTLY one of:
- "strong": High agreement (>0.7 confidence)
- "moderate": Moderate agreement (0.5-0.7)
- "weak": Low agreement or mixed signals
- "conflicting": Opposing signals

## Market Outlook (for "market_outlook" field)
Must be EXACTLY one of:
- "bullish": Majority positive signals
- "bearish": Majority negative signals
- "neutral": Balanced or low conviction
- "mixed": Strong conflicting signals

Be precise, data-driven, and base all recommendations ONLY on provided data.
"""
    
    def _build_user_prompt(self, state: AIAgentState) -> str:
        """Build the user prompt with all available data."""
        global_strategy = state.get("global_strategy_data", {})
        crypto_strategy = state.get("crypto_strategy_data", {})
        cryptocurrencies = state.get("cryptocurrencies", [])
        portfolio = state.get("portfolio", {})
        orders = state.get("orders", {})
        current_distribution = state.get("current_distribution", {})
        
        portfolio_str = json.dumps(portfolio, indent=2, default=str) if portfolio else "No portfolio data"
        orders_str = json.dumps(orders, indent=2, default=str) if orders else "No orders"
        
        return f"""
# Analyze All Cryptocurrencies and Synthesize Signals

## Global Strategy Data
{self.format_strategy_data(global_strategy)}

## Per-Cryptocurrency Strategy Data
{self.format_strategy_data(crypto_strategy)}

## Tracked Cryptocurrencies
{json.dumps(cryptocurrencies, indent=2)}

## Current Portfolio Context
{portfolio_str}

## Current Distribution
{json.dumps(current_distribution, indent=2)}

## Open Orders
{orders_str}

## Reference Market
{portfolio.get('reference_market', 'USD')}

## Task

1. **Generate Individual Signals**: For each cryptocurrency, analyze all available data and generate:
   - Trading signal (buy/sell/hold/increase/decrease)
   - Confidence level (0-1)
   - Reasoning based on strategy data
   - Market context
   - Key factors (max 5)

2. **Synthesize Signals**: After analyzing all cryptos, synthesize them into:
   - Synthesized signal for each cryptocurrency with direction and strength
   - Consensus level for each asset
   - Clear trading instructions (without specific percentages)
   - Overall market outlook
   - Summary of the synthesis

Output a JSON object with TWO sections:
- "per_crypto_signals": Array of individual signals
- "synthesis": Overall signal synthesis

Remember: Base ONLY on the provided data. Do not make allocation decisions - only synthesize.
"""
    
    async def execute(self, state: AIAgentState, llm_service) -> typing.Any:
        """
        Execute signal analysis and synthesis.
        
        Args:
            state: The current agent state.
            llm_service: The LLM service instance.
            
        Returns:
            Dictionary with signal_outputs and signal_synthesis.
        """
        self.logger.info(f"Starting {self.name}...")
        
        # Create wrapper model for strict schema validation
        class SignalAgentOutput(BaseModel):
            per_crypto_signals: list[CryptoSignalOutput]
            synthesis: SignalSynthesisOutput
        
        try:
            messages = [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": self._build_user_prompt(state)},
            ]
            
            response_data = await self._call_llm(
                messages,
                llm_service,
                json_output=True,
                response_schema=SignalAgentOutput,
            )
            
            # Process per-crypto signals
            signal_outputs = {"signals": {}}
            per_crypto = response_data.get("per_crypto_signals", [])
            
            for signal_data in per_crypto:
                crypto = signal_data.get("cryptocurrency", "")
                if crypto:
                    signal_output = CryptoSignalOutput(**signal_data)
                    signal_outputs["signals"][crypto] = signal_output
            
            # Process synthesis
            synthesis_data = response_data.get("synthesis", {})
            synthesis_output = SignalSynthesisOutput(**synthesis_data) if synthesis_data else None
            
            self.logger.info(f"{self.name} completed successfully.")
            
            return {
                "signal_outputs": signal_outputs,
                "signal_synthesis": synthesis_output,
            }
            
        except Exception as e:
            self.logger.exception(f"Error in {self.name}: {e}")
            return {}


async def run_signal_agent(state: AIAgentState, llm_service) -> dict:
    """
    Convenience function to run the signal agent.
    
    Args:
        state: The current agent state.
        llm_service: The LLM service instance.
        
    Returns:
        State updates from the agent.
    """
    agent = SignalAgent()
    return await agent.execute(state, llm_service)
