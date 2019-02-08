"""
OctoBot Tentacle

$tentacle_description: {
    "name": "safe_profit_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.1.0",
    "requirements": [],
    "config_files": ["SafeProfitMode.json"],
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

from trading.trader.modes.abstract_mode_creator import AbstractTradingModeCreator
from trading.trader.modes.abstract_mode_decider import AbstractTradingModeDecider
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode


class SafeProfitMode(AbstractTradingMode):
    def __init__(self, config, symbol_evaluator, exchange, symbol):
        super().__init__(config)

        self.add_creator(SafeProfitModeCreator(self))
        self.set_decider(SafeProfitModeDecider(self, symbol_evaluator, exchange, symbol))


class SafeProfitModeCreator(AbstractTradingModeCreator):
    def __init__(self, trading_mode):
        super().__init__(trading_mode)


class SafeProfitModeDecider(AbstractTradingModeDecider):
    def __init__(self, trading_mode, symbol_evaluator, exchange, symbol):
        super().__init__(trading_mode, symbol_evaluator, exchange, symbol)