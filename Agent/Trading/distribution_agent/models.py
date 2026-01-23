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
Pydantic models for distribution agent outputs.
"""
from typing import Dict, List
from pydantic import BaseModel, Field, field_validator


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
