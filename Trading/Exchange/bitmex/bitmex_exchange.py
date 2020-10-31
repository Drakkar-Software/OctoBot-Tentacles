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
import octobot_trading.exchanges as exchanges


class Bitmex(exchanges.SpotCCXTExchange, exchanges.FutureExchange):
    DESCRIPTION = ""

    BUY_STR = "Buy"
    SELL_STR = "Sell"

    MARK_PRICE_IN_TICKER = True
    FUNDING_IN_TICKER = True

    @classmethod
    def get_name(cls):
        return 'bitmex'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def get_recent_trades(self, symbol, limit=50, **kwargs):
        kwargs.update({"reverse": True})
        return await exchanges.FutureExchange.get_recent_trades(self, symbol=symbol, limit=limit, **kwargs)
