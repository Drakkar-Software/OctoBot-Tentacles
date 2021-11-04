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
import octobot_trading.modes.scripting_library as scripting_library
import octobot_trading.api as trading_api
import tentacles.Trading.Mode.scripted_trading_mode.trading.example_trading_script as live_script
import tentacles.Trading.Mode.scripted_trading_mode.backtesting as backtesting_script


class ScriptedTradingMode(scripting_library.AbstractScriptedTradingMode):

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.producer = ScriptedTradingModeProducer
        self.register_script_module(live_script)
        self.register_script_module(backtesting_script, live=False)


class ScriptedTradingModeProducer(scripting_library.AbstractScriptedTradingModeProducer):
    async def get_backtesting_metadata(self):
        profitability, profitability_percent, _, _, _ = trading_api.get_profitability_stats(self.exchange_manager)
        return {
            "id": self.trading_mode.get_prefix(self.trading_mode.bot_id),
            "p&l": float(profitability),
            "p&l%": float(profitability_percent),
            "trades": len(trading_api.get_trade_history(self.exchange_manager)),
            "timestamp": self.trading_mode.timestamp,
            "name": self.trading_mode.script_name,
            "user_inputs": self.trading_mode.trading_config
        }
