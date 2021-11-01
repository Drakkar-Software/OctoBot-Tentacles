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

import octobot_trading.modes.scripting_library as scripting_library
import tentacles.Trading.Mode.scripted_trading_mode.trading.example_trading_script as live_script
import tentacles.Trading.Mode.scripted_trading_mode.backtesting as backtesting_script


class ScriptedTradingMode(scripting_library.AbstractScriptedTradingMode):

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.producer = ScriptedTradingModeProducer
        self.register_script(live_script.script)
        self.register_script(backtesting_script.backtest_test_script, live=False)

    async def reload_script(self, live=True):
        if live:
            #TODO really reload, this is not working
            importlib.reload(live_script)
            self.register_script(live_script.script, live=live)
            # todo cancel and restart live tasks
            await self.start_over_database()
        else:
            importlib.reload(backtesting_script)
            self.register_script(backtesting_script.backtest_test_script, live=live)


class ScriptedTradingModeProducer(scripting_library.AbstractScriptedTradingModeProducer):
    pass
