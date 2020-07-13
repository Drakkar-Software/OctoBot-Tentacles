#  Drakkar-Software OctoBot-Private-Tentacles
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
from octobot_trading.exchanges.types.spot_exchange import SpotExchange


class Kucoin(SpotExchange):
    @classmethod
    def get_name(cls):
        return 'kucoin'

    async def get_recent_trades(self, symbol, limit=50, params=None):
        # on ccxt kucoin recent trades are received in reverse order from exchange and therefore should never be
        # filtered by limit before reversing (or most recent trades are lost)
        recent_trades = await super().get_recent_trades(symbol, limit=None, params=params)
        return recent_trades[::-1][:limit]

    async def get_order_book(self, symbol, limit=20, params=None):
        # override default limit to be kucoin complient
        return super().get_order_book(symbol, limit=limit, params=limit)
