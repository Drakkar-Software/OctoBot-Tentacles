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
Pydantic models for AI strategy evaluator agent outputs.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class TechnicalAnalysisOutput(BaseModel):
    """Output from the technical analysis agent."""
    eval_note: float = Field(
        ge=-1.0,
        le=1.0,
        description="Evaluation score from -1 (strong sell) to 1 (strong buy)."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence level of the analysis (0-1)."
    )
    description: str = Field(
        description="Summary description of the technical analysis."
    )
    trend: Optional[str] = Field(
        default=None,
        description="Current market trend: 'uptrend', 'downtrend', 'sideways'. Leave empty if unclear."
    )
    support_level: Optional[float] = Field(
        default=None,
        description="Identified support level price. Leave empty if no clear support identified."
    )
    resistance_level: Optional[float] = Field(
        default=None,
        description="Identified resistance level price. Leave empty if no clear resistance identified."
    )
    key_indicators: Optional[List[str]] = Field(
        default=None,
        description="Key technical indicators analyzed. Leave empty if no relevant indicators."
    )
    recommendations: Optional[List[str]] = Field(
        default=None,
        description="Trading recommendations based on technical analysis. Leave empty if no specific recommendations."
    )
    
    @field_validator("trend")
    def validate_trend(cls, v: str) -> str:
        if v is None:
            return None
        allowed_trends = ["uptrend", "downtrend", "sideways"]
        v_lower = v.lower()
        if v_lower not in allowed_trends:
            raise ValueError(f"Trend must be one of {allowed_trends}")
        return v_lower


class SentimentMetrics(BaseModel):
    """Sentiment analysis metrics."""
    sentiment_score: float = Field(
        ge=-1.0,
        le=1.0,
        description="Sentiment score from -1 (very negative) to 1 (very positive)."
    )
    
    @field_validator("sentiment_score")
    def validate_score(cls, v: float) -> float:
        return max(-1.0, min(1.0, v))


class SentimentAnalysisOutput(BaseModel):
    """Output from the sentiment analysis agent."""
    eval_note: float = Field(
        ge=-1.0,
        le=1.0,
        description="Evaluation score from -1 (very negative) to 1 (very positive)."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence level of the sentiment analysis (0-1)."
    )
    description: str = Field(
        description="Summary description of the sentiment analysis."
    )
    sentiment_score: float = Field(
        ge=-1.0,
        le=1.0,
        description="Detailed sentiment score from -1 to 1. Same as eval_note."
    )
    sources_analyzed: Optional[List[str]] = Field(
        default=None,
        description="Data sources used for sentiment analysis. Leave empty if none identified."
    )
    key_mentions: Optional[List[str]] = Field(
        default=None,
        description="Key mentions or topics driving sentiment. Leave empty if none."
    )
    market_implications: Optional[str] = Field(
        default=None,
        description="Implications of sentiment for market direction. Leave empty if unclear."
    )
    recommendations: Optional[List[str]] = Field(
        default=None,
        description="Trading recommendations based on sentiment. Leave empty if none."
    )


class RealTimeAnalysisOutput(BaseModel):
    """Output from the real-time analysis agent."""
    eval_note: float = Field(
        ge=-1.0,
        le=1.0,
        description="Evaluation score from -1 (strong selling pressure) to 1 (strong buying pressure)."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence level of the real-time analysis (0-1)."
    )
    description: str = Field(
        description="Summary description of the real-time market analysis."
    )
    price_momentum: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Price momentum indicator from -1 (strong downward) to 1 (strong upward). Leave empty if no momentum."
    )
    current_status: Optional[str] = Field(
        default=None,
        description="Current market status: 'bullish', 'bearish', 'neutral', 'volatile'. Leave empty if unclear."
    )
    volume_signal: Optional[str] = Field(
        default=None,
        description="Volume analysis: 'high', 'normal', 'low'. Leave empty if no volume data."
    )
    urgency_level: Optional[str] = Field(
        default=None,
        description="Action urgency: 'immediate', 'high', 'medium', 'low', 'none'. Leave empty if no urgency."
    )
    critical_events: Optional[List[str]] = Field(
        default=None,
        description="Any critical events or catalysts detected. Leave empty if none."
    )
    recommendations: Optional[List[str]] = Field(
        default=None,
        description="Real-time trading recommendations. Leave empty if none."
    )
    
    @field_validator("current_status")
    def validate_status(cls, v: str) -> str:
        if v is None:
            return None
        allowed_statuses = ["bullish", "bearish", "neutral", "volatile"]
        v_lower = v.lower()
        if v_lower not in allowed_statuses:
            raise ValueError(f"Status must be one of {allowed_statuses}")
        return v_lower
    
    @field_validator("volume_signal")
    def validate_volume(cls, v: str) -> str:
        if v is None:
            return None
        allowed_volumes = ["high", "normal", "low"]
        v_lower = v.lower()
        if v_lower not in allowed_volumes:
            raise ValueError(f"Volume signal must be one of {allowed_volumes}")
        return v_lower
    
    @field_validator("urgency_level")
    def validate_urgency(cls, v: str) -> str:
        if v is None:
            return None
        allowed_urgencies = ["immediate", "high", "medium", "low", "none"]
        v_lower = v.lower()
        if v_lower not in allowed_urgencies:
            raise ValueError(f"Urgency level must be one of {allowed_urgencies}")
        return v_lower


class SummarizationOutput(BaseModel):
    """Output from the summarization agent."""
    eval_note: float = Field(
        ge=-1.0,
        le=1.0,
        description="Final evaluation score from -1 (strong sell) to 1 (strong buy)."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence level of the final analysis (0-1)."
    )
    description: str = Field(
        description="Comprehensive summary of market analysis including key consensus points, overall outlook (bullish/bearish/mixed), key recommendations, and identified risks."
    )
