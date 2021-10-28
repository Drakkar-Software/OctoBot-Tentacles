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

import importlib

from .test_script import *
import octobot_trading.modes.scripting_library as scripting_library
import tentacles.Trading.Mode.scripted_trading_mode.active_scripts.test_script.backtesting.test_script as test_script


class ScriptedTradingMode(scripting_library.AbstractScriptedTradingMode):
    PLOT_SCRIPT = None

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.producer = ScriptedTradingModeProducer
        self.register_plot_script(test_script.backtest_test_script)

    @classmethod
    async def plot_script(cls) -> scripting_library.PlottedElements:
        return await cls.PLOT_SCRIPT()

    @classmethod
    def register_plot_script(cls, plot_script):
        cls.PLOT_SCRIPT = plot_script

    @classmethod
    def reload_plot_script(cls):
        importlib.reload(test_script)
        cls.register_plot_script(test_script.backtest_test_script)


class ScriptedTradingModeProducer(scripting_library.AbstractScriptedTradingModeProducer):
    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)
        self.script = script
