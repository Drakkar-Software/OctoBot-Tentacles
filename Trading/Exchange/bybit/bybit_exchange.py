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


class BybitSpotExchange(exchanges.SpotCCXTExchange):
    DESCRIPTION = ""

    @classmethod
    def get_name(cls) -> str:
        return 'bybit'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def get_symbol_prices(self, symbol, time_frame, limit: int = 200, **kwargs: dict):
        #Bybit return an error if there is no limit or since parameter
        try:
            return await self.connector.client.fetch_ohlcv(symbol, time_frame.value, limit=limit, params=kwargs)
        except Exception as e:
            raise octobot_trading.errors.FailedRequest(f"Failed to get_symbol_prices {e}")
