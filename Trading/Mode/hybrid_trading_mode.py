"""
OctoBot Tentacle

$tentacle_description: {
    "name": "hybrid_trading_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.1.0",
    "requirements": ["daily_trading_mode", "high_frequency_mode", "market_stability_strategy_evaluator"],
    "config_files": ["HybridTradingMode.json"],
    "developing": true
}
"""
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

from tentacles.Evaluator.Strategies import MarketStabilityStrategiesEvaluator
from trading.trader.modes.abstract_mode_decider import AbstractTradingModeDecider
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode


class HybridTradingMode(AbstractTradingMode):
    def __init__(self, config, symbol_evaluator, exchange):
        super().__init__(config, symbol_evaluator, exchange)

        self.set_decider(HybridTradingModeDecider(self, symbol_evaluator, exchange))

    @staticmethod
    def get_required_strategies():
        return [MarketStabilityStrategiesEvaluator]


class HybridTradingModeDecider(AbstractTradingModeDecider):
    def __init__(self, trading_mode, symbol_evaluator, exchange):
        super().__init__(trading_mode, symbol_evaluator, exchange)

    def set_final_eval(self):
        pass

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True

    def create_state(self):
        pass
