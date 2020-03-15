"""
OctoBot Tentacle

$tentacle_description: {
    "package_name": "OctoBot-Tentacles",
    "name": "bitmex",
    "type": "Trading",
    "subtype": "Exchange",
    "version": "1.0.0",
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
from octobot_trading.exchanges.types.future_exchange import FutureExchange
from octobot_trading.exchanges.types.margin_exchange import MarginExchange
from octobot_trading.exchanges.types.spot_exchange import SpotExchange
from ccxt.async_support.bitmax import bitmax


class Bitmax(SpotExchange, MarginExchange, FutureExchange):
    DESCRIPTION = ""

    @classmethod
    def get_name(cls):
        bitmax
        return 'bitmax'

    # override to add url
    def set_sandbox_mode(self, is_sandboxed):
        if is_sandboxed:
            self.client.urls['api'] = 'https://bitmax-test.io'
        else:
            self.client.setSandboxMode(is_sandboxed)
