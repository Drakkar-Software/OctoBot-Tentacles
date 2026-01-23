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
Pydantic models for signal agent outputs.
"""
from typing import List, Literal
from pydantic import BaseModel, Field


class SignalRecommendation(BaseModel):
    """A trading signal recommendation for an asset."""
    action: Literal["buy", "sell", "hold", "increase", "decrease"] = Field(
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


class CryptoSignalOutput(BaseModel):
    """Output from a cryptocurrency signal agent."""
    cryptocurrency: str = Field(description="The cryptocurrency being analyzed.")
    signal: SignalRecommendation = Field(description="The trading signal for this cryptocurrency.")
    market_context: str = Field(description="Brief description of current market context.")
    key_factors: List[str] = Field(
        default_factory=list,
        description="Key factors influencing this signal."
    )


class SynthesizedSignal(BaseModel):
    """A synthesized signal for an asset combining multiple signal sources."""
    asset: str = Field(description="The asset symbol.")
    direction: Literal["bullish", "bearish", "neutral"] = Field(
        description="Synthesized direction: 'bullish', 'bearish', 'neutral'."
    )
    strength: float = Field(
        ge=0.0,
        le=1.0,
        description="Signal strength (0-1)."
    )
    consensus_level: Literal["strong", "moderate", "weak", "conflicting"] = Field(
        description="Level of agreement between signals: 'strong', 'moderate', 'weak', 'conflicting'. "
                   "DO NOT use 'neutral' - use 'weak' for low agreement instead."
    )
    trading_instruction: str = Field(
        description="Clear trading instruction derived from signals."
    )


class SignalSynthesisOutput(BaseModel):
    """Output from the signal manager agent - synthesizes all signals."""
    synthesized_signals: List[SynthesizedSignal] = Field(
        description="List of synthesized signals per asset."
    )
    market_outlook: Literal["bullish", "bearish", "neutral", "mixed"] = Field(
        description="Overall market outlook: 'bullish', 'bearish', 'neutral', 'mixed'."
    )
    summary: str = Field(
        description="Summary of the synthesized signals without making decisions."
    )
