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


class Bitmex(FutureExchange):
    DESCRIPTION = ""

    BUY_STR = "Buy"
    SELL_STR = "Sell"

    MARK_PRICE_IN_TICKER = True
    FUNDING_IN_TICKER = True

    @classmethod
    def get_name(cls):
        return 'bitmex'

    async def get_recent_trades(self, symbol, limit=50, params=None):
        if params is None:
            params = {}
        params.update({"reverse": True})
        await FutureExchange.get_recent_trades(self, symbol=symbol, limit=limit, params=params)
