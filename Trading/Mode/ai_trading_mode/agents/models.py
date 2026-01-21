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
Pydantic models for AI agent outputs.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class SignalRecommendation(BaseModel):
    """A trading signal recommendation for an asset."""
    action: str = Field(
        description="Trading action: 'buy', 'sell', 'hold', 'increase', 'decrease'."
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence level of the signal (0 to 1)."
    )
    reasoning: str = Field(
        description="Explanation of why this signal was generated."
    )
    
    @field_validator("action")
    def validate_action(cls, v: str) -> str:
        allowed_actions = ["buy", "sell", "hold", "increase", "decrease"]
        v_lower = v.lower()
        if v_lower not in allowed_actions:
            raise ValueError(f"Action must be one of {allowed_actions}")
        return v_lower


class CryptoSignalOutput(BaseModel):
    """Output from a cryptocurrency signal agent."""
    cryptocurrency: str = Field(description="The cryptocurrency being analyzed.")
    signal: SignalRecommendation = Field(description="The trading signal for this cryptocurrency.")
    market_context: str = Field(description="Brief description of current market context.")
    key_factors: List[str] = Field(
        default_factory=list,
        description="Key factors influencing this signal."
    )


class RiskMetrics(BaseModel):
    """Portfolio risk metrics."""
    overall_risk_level: str = Field(
        description="Overall risk level: 'low', 'medium', 'high', 'critical'."
    )
    concentration_risk: float = Field(
        ge=0.0,
        le=1.0,
        description="Risk from over-concentration in few assets (0-1)."
    )
    volatility_exposure: float = Field(
        ge=0.0,
        le=1.0,
        description="Exposure to volatile assets (0-1)."
    )
    liquidity_risk: float = Field(
        ge=0.0,
        le=1.0,
        description="Risk from illiquid positions (0-1)."
    )
    
    @field_validator("overall_risk_level")
    def validate_risk_level(cls, v: str) -> str:
        allowed_levels = ["low", "medium", "high", "critical"]
        v_lower = v.lower()
        if v_lower not in allowed_levels:
            raise ValueError(f"Risk level must be one of {allowed_levels}")
        return v_lower


class RiskAssessmentOutput(BaseModel):
    """Output from the risk assessment agent."""
    metrics: RiskMetrics = Field(description="Calculated risk metrics.")
    recommendations: List[str] = Field(
        description="Risk mitigation recommendations."
    )
    max_allocation_per_asset: Dict[str, float] = Field(
        default_factory=dict,
        description="Maximum recommended allocation percentage per asset."
    )
    min_cash_reserve: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Minimum recommended cash/stablecoin reserve (0-1)."
    )
    reasoning: str = Field(description="Explanation of the risk assessment.")


class SynthesizedSignal(BaseModel):
    """A synthesized signal for an asset combining multiple signal sources."""
    asset: str = Field(description="The asset symbol.")
    direction: str = Field(
        description="Synthesized direction: 'bullish', 'bearish', 'neutral'."
    )
    strength: float = Field(
        ge=0.0,
        le=1.0,
        description="Signal strength (0-1)."
    )
    consensus_level: str = Field(
        description="Level of agreement between signals: 'strong', 'moderate', 'weak', 'conflicting'."
    )
    trading_instruction: str = Field(
        description="Clear trading instruction derived from signals."
    )
    
    @field_validator("direction")
    def validate_direction(cls, v: str) -> str:
        allowed_directions = ["bullish", "bearish", "neutral"]
        v_lower = v.lower()
        if v_lower not in allowed_directions:
            raise ValueError(f"Direction must be one of {allowed_directions}")
        return v_lower
    
    @field_validator("consensus_level")
    def validate_consensus(cls, v: str) -> str:
        allowed_levels = ["strong", "moderate", "weak", "conflicting"]
        v_lower = v.lower()
        if v_lower not in allowed_levels:
            raise ValueError(f"Consensus level must be one of {allowed_levels}")
        return v_lower


class SignalSynthesisOutput(BaseModel):
    """Output from the signal manager agent - synthesizes all signals."""
    synthesized_signals: List[SynthesizedSignal] = Field(
        description="List of synthesized signals per asset."
    )
    market_outlook: str = Field(
        description="Overall market outlook: 'bullish', 'bearish', 'neutral', 'mixed'."
    )
    summary: str = Field(
        description="Summary of the synthesized signals without making decisions."
    )


class AssetDistribution(BaseModel):
    """Distribution allocation for a single asset."""
    asset: str = Field(description="Asset symbol.")
    percentage: float = Field(
        ge=0.0,
        le=100.0,
        description="Allocation percentage (0-100)."
    )
    action: str = Field(
        description="Action to take: 'increase', 'decrease', 'maintain', 'add', 'remove'."
    )
    explanation: str = Field(
        description="Explanation for this allocation."
    )
    
    @field_validator("action")
    def validate_action(cls, v: str) -> str:
        allowed_actions = ["increase", "decrease", "maintain", "add", "remove"]
        v_lower = v.lower()
        if v_lower not in allowed_actions:
            raise ValueError(f"Action must be one of {allowed_actions}")
        return v_lower


class DistributionOutput(BaseModel):
    """Output from the distribution agent - final portfolio distribution."""
    distributions: List[AssetDistribution] = Field(
        description="Target distribution for each asset."
    )
    rebalance_urgency: str = Field(
        description="Urgency of rebalancing: 'immediate', 'soon', 'low', 'none'."
    )
    reasoning: str = Field(
        description="Overall reasoning for the distribution decisions."
    )
    
    @field_validator("rebalance_urgency")
    def validate_urgency(cls, v: str) -> str:
        allowed_urgency = ["immediate", "soon", "low", "none"]
        v_lower = v.lower()
        if v_lower not in allowed_urgency:
            raise ValueError(f"Urgency must be one of {allowed_urgency}")
        return v_lower
    
    def get_distribution_dict(self) -> Dict[str, float]:
        """Convert distributions to a simple dict format."""
        return {d.asset: d.percentage for d in self.distributions}
    
    def get_ai_instructions(self) -> List[dict]:
        """Convert distributions to AI instruction format for ai_index_distribution."""
        from tentacles.Trading.Mode.ai_trading_mode import ai_index_distribution
        
        instructions = []
        for dist in self.distributions:
            if dist.action == "increase":
                instructions.append({
                    ai_index_distribution.INSTRUCTION_ACTION: ai_index_distribution.ACTION_INCREASE_EXPOSURE,
                    ai_index_distribution.INSTRUCTION_SYMBOL: dist.asset,
                    ai_index_distribution.INSTRUCTION_WEIGHT: dist.percentage,
                })
            elif dist.action == "decrease":
                instructions.append({
                    ai_index_distribution.INSTRUCTION_ACTION: ai_index_distribution.ACTION_REDUCE_EXPOSURE,
                    ai_index_distribution.INSTRUCTION_SYMBOL: dist.asset,
                    ai_index_distribution.INSTRUCTION_WEIGHT: dist.percentage,
                })
            elif dist.action == "add":
                instructions.append({
                    ai_index_distribution.INSTRUCTION_ACTION: ai_index_distribution.ACTION_ADD_TO_DISTRIBUTION,
                    ai_index_distribution.INSTRUCTION_SYMBOL: dist.asset,
                    ai_index_distribution.INSTRUCTION_WEIGHT: dist.percentage,
                })
            elif dist.action == "remove":
                instructions.append({
                    ai_index_distribution.INSTRUCTION_ACTION: ai_index_distribution.ACTION_REMOVE_FROM_DISTRIBUTION,
                    ai_index_distribution.INSTRUCTION_SYMBOL: dist.asset,
                })
            elif dist.action == "maintain":
                instructions.append({
                    ai_index_distribution.INSTRUCTION_ACTION: ai_index_distribution.ACTION_UPDATE_RATIO,
                    ai_index_distribution.INSTRUCTION_SYMBOL: dist.asset,
                    ai_index_distribution.INSTRUCTION_WEIGHT: dist.percentage,
                })
        
        return instructions
