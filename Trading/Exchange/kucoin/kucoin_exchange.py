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

import octobot_commons.logging as logging
import octobot_trading.errors
import octobot_trading.exchanges as exchanges


def _kucoin_retrier(f):
    async def wrapper(*args, **kwargs):
        for i in range(0, Kucoin.MAX_CANDLES_FETCH_INSTANT_RETRY):
            try:
                return await f(*args, **kwargs)
            except octobot_trading.errors.FailedRequest as e:
                if Kucoin.INSTANT_RETRY_ERROR_CODE in str(e):
                    # should retry instantly, error on kucoin side
                    # see https://github.com/Drakkar-Software/OctoBot/issues/2000
                    logging.get_logger(Kucoin.get_name()).debug(
                        f"{Kucoin.INSTANT_RETRY_ERROR_CODE} error on request, retrying now "
                        f"(attempt {i+1} / {Kucoin.MAX_CANDLES_FETCH_INSTANT_RETRY}).")
                else:
                    raise
        raise octobot_trading.errors.FailedRequest(
            f"Failed request after {Kucoin.MAX_CANDLES_FETCH_INSTANT_RETRY} retries due "
            f"to {Kucoin.INSTANT_RETRY_ERROR_CODE} error code"
        )
    return wrapper


class Kucoin(exchanges.SpotCCXTExchange):
    MAX_CANDLES_FETCH_INSTANT_RETRY = 5
    INSTANT_RETRY_ERROR_CODE = "429000"

    @classmethod
    def get_name(cls):
        return 'kucoin'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer,
                                            remove_price_limits=True)

    @_kucoin_retrier
    async def get_symbol_prices(self, symbol, time_frame, limit: int = 200, **kwargs: dict):
        return await super().get_symbol_prices(symbol=symbol, time_frame=time_frame, limit=limit, **kwargs)

    async def get_recent_trades(self, symbol, limit=50, **kwargs):
        # on ccxt kucoin recent trades are received in reverse order from exchange and therefore should never be
        # filtered by limit before reversing (or most recent trades are lost)
        recent_trades = await super().get_recent_trades(symbol, limit=None, **kwargs)
        return recent_trades[::-1][:limit] if recent_trades else []

    async def get_order_book(self, symbol, limit=20, **kwargs):
        # override default limit to be kucoin complient
        return super().get_order_book(symbol, limit=limit, **kwargs)

    def should_log_on_ddos_exception(self, exception) -> bool:
        """
        Override when necessary
        """
        return Kucoin.INSTANT_RETRY_ERROR_CODE not in str(exception)
