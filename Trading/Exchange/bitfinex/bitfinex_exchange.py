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


class Bitfinex(exchanges.SpotCCXTExchange):

    # bitfinex2 only supports 1, 25 and 100 size
    # https://docs.bitfinex.com/reference#rest-public-book
    SUPPORTED_ORDER_BOOK_LIMITS = [1, 25, 100]
    DEFAULT_ORDER_BOOK_LIMIT = 25

    @classmethod
    def get_name(cls):
        return 'bitfinex2'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def get_order_book(self, symbol, limit=DEFAULT_ORDER_BOOK_LIMIT, **kwargs):
        if limit is None or limit not in self.SUPPORTED_ORDER_BOOK_LIMITS:
            self.logger.debug(f"Trying to get_order_book with limit not {self.SUPPORTED_ORDER_BOOK_LIMITS} : ({limit})")
            limit = self.DEFAULT_ORDER_BOOK_LIMIT
        return await super().get_recent_trades(symbol=symbol, limit=limit, **kwargs)
