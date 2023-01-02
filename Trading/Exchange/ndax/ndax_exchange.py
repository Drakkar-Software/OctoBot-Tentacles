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
import octobot_trading.enums as trading_enums


class Ndax(exchanges.SpotCCXTExchange):
    DESCRIPTION = ""

    DEFAULT_MAX_LIMIT = 500

    @classmethod
    def get_name(cls):
        return 'ndax'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def get_symbol_prices(self, symbol, time_frame, limit: int = None, **kwargs: dict):
        # ohlcv without limit is not supported, replaced by a default max limit
        if limit is None:
            limit = self.DEFAULT_MAX_LIMIT
        return await super().get_symbol_prices(symbol=symbol, time_frame=time_frame, limit=limit, **kwargs)

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer)

    async def get_price_ticker(self, symbol: str, **kwargs: dict):
        ticker = await super().get_price_ticker(symbol=symbol, **kwargs)
        for key in [
            trading_enums.ExchangeConstantsTickersColumns.HIGH.value,
            trading_enums.ExchangeConstantsTickersColumns.LOW.value,
            trading_enums.ExchangeConstantsTickersColumns.OPEN.value,
            trading_enums.ExchangeConstantsTickersColumns.BASE_VOLUME.value,
        ]:
            if ticker[key] == 0.0:
                ticker[key] = None
        return ticker
