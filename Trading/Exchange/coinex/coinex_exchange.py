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
import decimal
import typing

import octobot_trading.exchanges as exchanges
import octobot_trading.enums as trading_enums
import octobot_trading.errors

class Coinex(exchanges.SpotCCXTExchange):
    DESCRIPTION = ""
    MAX_PAGINATION_LIMIT: int = 100

    @classmethod
    def get_name(cls):
        return 'coinex'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer)

    async def get_open_orders(self, symbol=None, since=None, limit=None, **kwargs) -> list:
        return [
            self._ensure_order_quantity(order)
            for order in await super().get_open_orders(symbol=symbol,
                                                       since=since,
                                                       limit=self._fix_limit(limit),
                                                       **kwargs)
        ]

    async def get_closed_orders(self, symbol=None, since=None, limit=None, **kwargs) -> list:
        return [
            self._ensure_order_quantity(order)
            for order in await super().get_closed_orders(symbol=symbol,
                                                         since=since,
                                                         limit=self._fix_limit(limit),
                                                         **kwargs)
        ]

    async def create_order(self, order_type: trading_enums.TraderOrderType, symbol: str, quantity: decimal.Decimal,
                           price: decimal.Decimal = None, stop_price: decimal.Decimal = None,
                           side: trading_enums.TradeOrderSide = None, current_price: decimal.Decimal = None,
                           params: dict = None) -> typing.Optional[dict]:
        # tell ccxt to use amount as provided and not to compute it by multiplying it by price which is done here
        # (price should not be sent to market orders). Only used for buy market orders
        self.connector.add_options({"createMarketBuyOrderRequiresPrice": False})
        if order_type is trading_enums.TraderOrderType.BUY_MARKET:
            # on coinex, market orders are in quote currency (YYY in XYZ/YYY)
            if price is None:
                raise octobot_trading.errors.NotSupported(f"{self.get_name()} requires a price parameter to create "
                                                          f"market orders as quantity is in quote currency")
            quantity = quantity * price
        if created_order := await super().create_order(order_type, symbol, quantity,
                                                       price=price, stop_price=stop_price,
                                                       side=side, current_price=current_price,
                                                       params=params):
            self._ensure_order_quantity(created_order)
        return created_order

    async def get_order(self, order_id: str, symbol: str = None, **kwargs: dict) -> dict:
        if order := await super().get_order(order_id, symbol=symbol, **kwargs):
            self._ensure_order_quantity(order)
        return order

    def _ensure_order_quantity(self, order):
        try:
            if order[trading_enums.ExchangeConstantsOrderColumns.TYPE.value] \
                    == trading_enums.TradeOrderType.MARKET.value and \
                    order[trading_enums.ExchangeConstantsOrderColumns.SIDE.value] == \
                    trading_enums.TradeOrderSide.BUY.value:
                # convert amount to have the same units as evert other exchange: use FILLED for accuracy
                order[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] = \
                    order[trading_enums.ExchangeConstantsOrderColumns.FILLED.value]
        except KeyError:
            pass
        return order

    def _fix_limit(self, limit: int) -> int:
        return min(self.MAX_PAGINATION_LIMIT, limit)
