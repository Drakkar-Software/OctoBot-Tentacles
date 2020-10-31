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
import octobot_trading.exchanges as exchanges


class Kucoin(exchanges.SpotCCXTExchange):
    @classmethod
    def get_name(cls):
        return 'kucoin'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def get_recent_trades(self, symbol, limit=50, **kwargs):
        # on ccxt kucoin recent trades are received in reverse order from exchange and therefore should never be
        # filtered by limit before reversing (or most recent trades are lost)
        recent_trades = await super().get_recent_trades(symbol, limit=None, **kwargs)
        return recent_trades[::-1][:limit] if recent_trades else []

    async def get_order_book(self, symbol, limit=20, **kwargs):
        # override default limit to be kucoin complient
        return super().get_order_book(symbol, limit=limit, **kwargs)
