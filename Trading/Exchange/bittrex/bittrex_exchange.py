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
import ccxt

import octobot_trading.exchanges as exchanges
import octobot_trading.errors


class Bittrex(exchanges.SpotCCXTExchange):
    DESCRIPTION = ""

    SUPPORTED_ORDER_BOOK_LIMITS = [1, 25, 500]
    DEFAULT_ORDER_BOOK_LIMIT = 25

    @classmethod
    def get_name(cls):
        return 'bittrex'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def get_order_book(self, symbol, limit=DEFAULT_ORDER_BOOK_LIMIT, **kwargs):
        if limit is None or limit not in self.SUPPORTED_ORDER_BOOK_LIMITS:
            self.logger.debug(f"Trying to get_order_book with limit not {self.SUPPORTED_ORDER_BOOK_LIMITS} : ({limit})")
            limit = self.DEFAULT_ORDER_BOOK_LIMIT
        return await super().get_recent_trades(symbol=symbol, limit=limit, **kwargs)

    async def get_symbol_prices(self, symbol, time_frame, limit: int = None, **kwargs: dict):
        # ohlcv limit is not working as expected, limit is doing [:-limit] but we want [-limit:]
        try:
            candles = await self.connector.client.fetch_ohlcv(symbol, time_frame.value, params=kwargs)
            if limit:
                return candles[-limit:]
            return candles
        except Exception as e:
            raise octobot_trading.errors.FailedRequest(f"Failed to get_symbol_prices {e}")

    async def get_price_ticker(self, symbol: str, **kwargs: dict):
        """
        Multiple calls are required to get all ticker data
        https://github.com/ccxt/ccxt/issues/7893
        Default ccxt call is using publicGetMarketsMarketSymbolTicker
        But the mandatory data is available by calling publicGetMarketsMarketSymbolSummary
        """
        try:
            return await self.connector.client.fetch_ticker(symbol, params={
                'method': 'publicGetMarketsMarketSymbolSummary'
            })
        except ccxt.BaseError as e:
            raise octobot_trading.errors.FailedRequest(f"Failed to get_price_ticker {e}")
