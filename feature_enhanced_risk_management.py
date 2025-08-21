#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Risk Management Module for OctoBot Tentacles

This module provides advanced risk management features including:
- Dynamic position sizing based on volatility
- Portfolio heat management
- Correlation-based risk assessment
- Maximum drawdown protection

Author: OctoBot Community
Version: 1.0.0
License: LGPL-3.0
"""

import math
import numpy as np
from typing import Dict, List, Optional, Tuple

class EnhancedRiskManager:
    """
    Advanced risk management system for OctoBot trading strategies.
    
    Implements dynamic position sizing, correlation analysis, and drawdown protection
    to optimize risk-adjusted returns while preserving capital.
    """
    
    def __init__(self, 
                 max_portfolio_heat: float = 0.02,  # 2% max portfolio risk per trade
                 max_correlation_threshold: float = 0.7,  # Max correlation between positions
                 volatility_lookback: int = 20,  # Periods for volatility calculation
                 max_drawdown_limit: float = 0.15):  # 15% max portfolio drawdown
        
        self.max_portfolio_heat = max_portfolio_heat
        self.max_correlation_threshold = max_correlation_threshold
        self.volatility_lookback = volatility_lookback
        self.max_drawdown_limit = max_drawdown_limit
        
        # Internal state tracking
        self.position_history: Dict[str, List] = {}
        self.portfolio_equity_curve: List[float] = []
        self.active_positions: Dict[str, Dict] = {}
        
    def calculate_position_size(self, 
                              symbol: str,
                              entry_price: float,
                              stop_loss: float,
                              portfolio_value: float,
                              price_history: List[float]) -> float:
        """
        Calculate optimal position size using volatility-adjusted Kelly Criterion.
        
        Args:
            symbol: Trading symbol
            entry_price: Planned entry price
            stop_loss: Stop loss price
            portfolio_value: Current portfolio value
            price_history: Recent price history for volatility calculation
            
        Returns:
            Optimal position size in base currency
        """
        
        # Calculate volatility-based risk adjustment
        volatility = self._calculate_volatility(price_history)
        volatility_multiplier = max(0.5, min(1.5, 1.0 / (1.0 + volatility)))
        
        # Calculate risk per unit
        risk_per_unit = abs(entry_price - stop_loss) / entry_price
        
        # Apply portfolio heat limit with volatility adjustment
        max_position_value = portfolio_value * self.max_portfolio_heat * volatility_multiplier
        
        # Calculate position size
        position_size = max_position_value / risk_per_unit
        
        # Apply correlation limits
        correlation_adjusted_size = self._apply_correlation_limits(symbol, position_size)
        
        # Apply drawdown protection
        drawdown_adjusted_size = self._apply_drawdown_protection(correlation_adjusted_size, portfolio_value)
        
        return min(drawdown_adjusted_size, portfolio_value * 0.25)  # Never risk more than 25% of portfolio
    
    def _calculate_volatility(self, price_history: List[float]) -> float:
        """
        Calculate annualized volatility using recent price data.
        """
        if len(price_history) < 2:
            return 0.2  # Default 20% volatility assumption
            
        returns = [math.log(price_history[i] / price_history[i-1]) 
                  for i in range(1, min(len(price_history), self.volatility_lookback + 1))]
        
        if not returns:
            return 0.2
            
        return np.std(returns) * math.sqrt(252)  # Annualized volatility
    
    def _apply_correlation_limits(self, symbol: str, base_position_size: float) -> float:
        """
        Reduce position size if high correlation with existing positions detected.
        """
        # Placeholder for correlation analysis
        # In a full implementation, this would analyze price correlations
        # between the new symbol and existing positions
        
        correlation_factor = 1.0  # Default no adjustment
        
        # Example logic: reduce size if we have many correlated positions
        similar_positions = len([pos for pos in self.active_positions.keys() 
                               if pos.split('/')[0] == symbol.split('/')[0]])
        
        if similar_positions > 2:
            correlation_factor = 0.7  # Reduce by 30% for concentrated exposure
        
        return base_position_size * correlation_factor
    
    def _apply_drawdown_protection(self, position_size: float, portfolio_value: float) -> float:
        """
        Apply drawdown protection to reduce position sizes during losing streaks.
        """
        if len(self.portfolio_equity_curve) < 10:
            return position_size  # Not enough data for drawdown calculation
            
        # Calculate current drawdown
        peak_value = max(self.portfolio_equity_curve)
        current_drawdown = (peak_value - portfolio_value) / peak_value
        
        # Reduce position size as drawdown increases
        if current_drawdown > self.max_drawdown_limit / 2:
            drawdown_factor = max(0.3, 1.0 - (current_drawdown / self.max_drawdown_limit))
            return position_size * drawdown_factor
            
        return position_size
    
    def update_portfolio_state(self, current_value: float, positions: Dict[str, Dict]):
        """
        Update internal state tracking for risk calculations.
        
        Args:
            current_value: Current portfolio value
            positions: Dict of active positions {symbol: {size, entry_price, current_price}}
        """
        self.portfolio_equity_curve.append(current_value)
        self.active_positions = positions.copy()
        
        # Limit history to prevent memory issues
        if len(self.portfolio_equity_curve) > 1000:
            self.portfolio_equity_curve = self.portfolio_equity_curve[-500:]
    
    def check_risk_limits(self, portfolio_value: float) -> Tuple[bool, str]:
        """
        Check if current portfolio state exceeds risk limits.
        
        Returns:
            Tuple of (risk_ok: bool, message: str)
        """
        if len(self.portfolio_equity_curve) < 2:
            return True, "Insufficient data for risk assessment"
            
        # Check drawdown limit
        peak_value = max(self.portfolio_equity_curve)
        current_drawdown = (peak_value - portfolio_value) / peak_value
        
        if current_drawdown > self.max_drawdown_limit:
            return False, f"Portfolio drawdown ({current_drawdown:.1%}) exceeds limit ({self.max_drawdown_limit:.1%})"
            
        # Check portfolio heat
        total_risk = sum([pos.get('risk_amount', 0) for pos in self.active_positions.values()])
        portfolio_heat = total_risk / portfolio_value
        
        if portfolio_heat > self.max_portfolio_heat * 2:  # 2x buffer for existing positions
            return False, f"Portfolio heat ({portfolio_heat:.1%}) too high"
            
        return True, "Risk levels acceptable"

# Example usage and integration hooks
def integrate_with_octobot_strategy():
    """
    Example integration pattern for OctoBot strategies.
    
    This function demonstrates how to integrate the EnhancedRiskManager
    with existing OctoBot trading strategies.
    """
    
    # Initialize risk manager with conservative settings
    risk_manager = EnhancedRiskManager(
        max_portfolio_heat=0.015,  # 1.5% per trade
        max_correlation_threshold=0.6,
        volatility_lookback=14,
        max_drawdown_limit=0.12  # 12% max drawdown
    )
    
    # Example strategy integration points:
    # 1. Before opening new positions
    # 2. During portfolio rebalancing
    # 3. For dynamic stop-loss adjustments
    
    return risk_manager

if __name__ == "__main__":
    # Basic functionality test
    rm = EnhancedRiskManager()
    
    # Simulate position sizing calculation
    test_price_history = [100, 102, 98, 103, 101, 99, 104, 102]
    position_size = rm.calculate_position_size(
        symbol="BTC/USDT",
        entry_price=100.0,
        stop_loss=95.0,
        portfolio_value=10000.0,
        price_history=test_price_history
    )
    
    print(f"Calculated position size: ${position_size:.2f}")
    print("Enhanced Risk Management module loaded successfully.")
