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
import octobot_trading.modes as modes


class ScriptedTradingMode(modes.AbstractScriptedTradingMode):

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.producer = ScriptedTradingModeProducer
        import backtesting_script
        import profile_trading_script
        self.register_script_module(profile_trading_script)
        self.register_script_module(backtesting_script, live=False)


class ScriptedTradingModeProducer(modes.AbstractScriptedTradingModeProducer):
    pass
