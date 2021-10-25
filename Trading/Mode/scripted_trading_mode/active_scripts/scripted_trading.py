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

from .script import script
from octobot_trading.modes.scripting_library import AbstractScriptedTradingMode, AbstractScriptedTradingModeProducer


class ScriptedTradingMode(AbstractScriptedTradingMode):
    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.producer = ScriptedTradingModeProducer


class ScriptedTradingModeProducer(AbstractScriptedTradingModeProducer):
    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)
        self.script = script
