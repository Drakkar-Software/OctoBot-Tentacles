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
Distribution Agent.
Makes final portfolio distribution decisions based on synthesized signals and risk assessment.
Uses ai_index_distribution functions to apply changes.
"""
import json
import typing

from pydantic import BaseModel

from tentacles.Trading.Mode.ai_trading_mode.agents.base_agent import BaseAgent
from tentacles.Trading.Mode.ai_trading_mode.agents.state import AIAgentState
from tentacles.Trading.Mode.ai_trading_mode.agents.models import (
    DistributionOutput,
    RiskAssessmentOutput,
    SignalSynthesisOutput,
)


class DistributionAgent(BaseAgent):
    """
    Distribution agent that makes final portfolio allocation decisions.
    Combines signal synthesis and risk assessment to determine target distribution.
    """
    
    AGENT_NAME = "DistributionAgent"
    AGENT_VERSION = "1.0.0"
    
    def __init__(self, model=None, max_tokens=None, temperature=None):
        """
        Initialize the distribution agent.
        
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
You are a Portfolio Distribution Agent for cryptocurrency trading.
Your task is to make FINAL portfolio allocation decisions based on synthesized signals and risk assessment.

## Your Role
- Determine target percentage allocation for each asset.
- Balance signal-driven opportunities with risk constraints.
- Decide on rebalancing urgency.

## Important Constraints
- Total allocation MUST sum to exactly 100%.
- Respect maximum allocation limits from risk assessment.
- Maintain minimum cash reserve as recommended by risk agent.
- Consider current distribution to minimize unnecessary trades.

## Allocation Actions
- "increase": Increase allocation from current level
- "decrease": Decrease allocation from current level
- "maintain": Keep current allocation
- "add": Add new asset to portfolio
- "remove": Remove asset from portfolio entirely

## Rebalancing Urgency
- "immediate": Critical signals or risk levels require immediate action
- "soon": Moderate signals suggest rebalancing within the trading session
- "low": Minor adjustments that can wait
- "none": Current distribution is acceptable

## Decision Framework
1. Start with current distribution as baseline
2. Apply signal synthesis recommendations (increase/decrease based on direction and strength)
3. Apply risk constraints (max allocation limits, min cash reserve)
4. Ensure total sums to 100%
5. Determine urgency based on signal strength and risk level

## Output Requirements
Output a JSON object with:
- "allocations": Array of objects with "asset", "target_percentage", "action", "reasoning"
- "rebalance_urgency": One of "immediate", "soon", "low", "none"
- "reasoning": Summary explanation
"""
    
    def _build_user_prompt(self, state: AIAgentState) -> str:
        """Build the user prompt with all decision inputs."""
        signal_synthesis = state.get("signal_synthesis")
        risk_output = state.get("risk_output")
        current_distribution = state.get("current_distribution", {})
        cryptocurrencies = state.get("cryptocurrencies", [])
        reference_market = state.get("reference_market", "USD")
        
        # Format signal synthesis
        synthesis_data = {}
        if signal_synthesis:
            if isinstance(signal_synthesis, SignalSynthesisOutput):
                synthesis_data = {
                    "market_outlook": signal_synthesis.market_outlook,
                    "summary": signal_synthesis.summary,
                    "signals": [
                        {
                            "asset": s.asset,
                            "direction": s.direction,
                            "strength": s.strength,
                            "consensus_level": s.consensus_level,
                            "trading_instruction": s.trading_instruction
                        }
                        for s in signal_synthesis.synthesized_signals
                    ]
                }
            elif isinstance(signal_synthesis, dict):
                synthesis_data = signal_synthesis
        
        # Format risk output
        risk_data = {}
        if risk_output:
            if isinstance(risk_output, RiskAssessmentOutput):
                risk_data = {
                    "overall_risk_level": risk_output.metrics.overall_risk_level,
                    "concentration_risk": risk_output.metrics.concentration_risk,
                    "volatility_exposure": risk_output.metrics.volatility_exposure,
                    "liquidity_risk": risk_output.metrics.liquidity_risk,
                    "max_allocations": risk_output.max_allocation_per_asset,
                    "min_cash_reserve": risk_output.min_cash_reserve,
                    "recommendations": risk_output.recommendations,
                    "reasoning": risk_output.reasoning
                }
            elif isinstance(risk_output, dict):
                risk_data = risk_output
        
        allowed_assets = cryptocurrencies + [reference_market]
        
        return f"""
# Determine Portfolio Distribution

## Allowed Assets
{json.dumps(allowed_assets, indent=2)}

## Current Distribution (percentages)
{json.dumps(current_distribution, indent=2)}

## Signal Synthesis (from Signal Agent)
{json.dumps(synthesis_data, indent=2, default=str)}

## Risk Assessment (from Risk Agent)
{json.dumps(risk_data, indent=2, default=str)}

## Reference Market (Stablecoin/Cash)
{reference_market}

## Task
Based on the synthesized signals and risk assessment:
1. Determine target allocation percentage for each asset
2. Specify the action (increase/decrease/maintain/add/remove)
3. Ensure total allocations sum to exactly 100%
4. Respect risk constraints (max allocations, min cash reserve)
5. Set rebalancing urgency
6. Provide reasoning for decisions

Remember: 
- Percentages must sum to 100%
- Only use allowed assets
- Balance opportunity with risk
"""
    
    async def execute(self, state: AIAgentState, llm_service) -> typing.Any:
        """
        Execute distribution decision.
        
        Args:
            state: The current agent state.
            llm_service: The LLM service instance.
            
        Returns:
            Dictionary with distribution_output.
        """
        self.logger.info(f"Starting {self.name}...")
        
        try:
            messages = [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": self._build_user_prompt(state)},
            ]
            
            response_data = await self._call_llm(
                messages,
                llm_service,
                json_output=True,
                response_schema=DistributionOutput,
            )
            
            # Parse into model
            distribution_output = DistributionOutput(**response_data)
            
            self.logger.info(f"{self.name} completed successfully.")
            
            return {"distribution_output": distribution_output}
            
        except Exception as e:
            self.logger.exception(f"Error in {self.name}: {e}")
            return {}


async def run_distribution_agent(state: AIAgentState, llm_service) -> dict:
    """
    Convenience function to run the distribution agent.
    
    Args:
        state: The current agent state.
        llm_service: The LLM service instance.
        
    Returns:
        State updates from the agent.
    """
    agent = DistributionAgent()
    return await agent.execute(state, llm_service)
