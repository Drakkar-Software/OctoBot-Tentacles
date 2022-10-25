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
import octobot_trading.errors


class Kraken(exchanges.SpotCCXTExchange):
    DESCRIPTION = ""

    RECENT_TRADE_FIXED_LIMIT = 1000

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.logger.error("Kraken is not providing free and used data for account balance. "
                          "OctoBot wont be able to manage a real portfolio correctly.")

    @classmethod
    def get_name(cls):
        return 'kraken'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer)

    async def get_recent_trades(self, symbol, limit=RECENT_TRADE_FIXED_LIMIT, **kwargs):
        if limit is not None and limit != self.RECENT_TRADE_FIXED_LIMIT:
            self.logger.debug(f"Trying to get_recent_trades with limit != {self.RECENT_TRADE_FIXED_LIMIT} : ({limit})")
            limit = self.RECENT_TRADE_FIXED_LIMIT
        return await super().get_recent_trades(symbol=symbol, limit=limit, **kwargs)

    async def get_order_book(self, symbol, limit=5, **kwargs):
        # suggestion from https://github.com/ccxt/ccxt/issues/8135#issuecomment-748520283
        try:
            return await self.connector.client.fetch_l2_order_book(symbol, limit=limit, params=kwargs)
        except Exception as e:
            raise octobot_trading.errors.FailedRequest(f"Failed to get_order_book {e}")

    async def get_symbol_prices(self, symbol, time_frame, limit: int = None, **kwargs: dict):
        # ohlcv limit is not working as expected, limit is doing [:-limit] but we want [-limit:]
        candles = await super().get_symbol_prices(symbol=symbol, time_frame=time_frame, limit=limit, **kwargs)
        if limit:
            return candles[-limit:]
        return candles
