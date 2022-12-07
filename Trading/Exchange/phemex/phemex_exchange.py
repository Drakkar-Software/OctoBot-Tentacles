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
import asyncio

import octobot_trading.exchanges as exchanges


class Phemex(exchanges.SpotCCXTExchange):
    DESCRIPTION = ""

    @classmethod
    def get_name(cls):
        return 'phemex'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def get_order(self, order_id: str, symbol: str = None, **kwargs: dict) -> dict:
        if order := await self.connector.get_order(symbol=symbol, order_id=order_id, **kwargs):
            return order
        # try from closed orders (get_order is not returning filled or cancelled orders)
        if order := await self.get_order_from_open_and_closed_orders(order_id, symbol):
            return order
        # try from trades (get_order is not returning filled or cancelled orders)
        return await self._get_order_from_trades(symbol, order_id, {})

    async def _get_order_from_trades(self, symbol, order_id, order_to_update):
        # usually the last trade is the right one
        for _ in range(3):
            if (order := await self.get_order_from_trades(symbol, order_id, order_to_update)) is None:
                await asyncio.sleep(3)
            else:
                return order
        raise KeyError("Order id not found in trades. Impossible to build order from trades history")

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer)
