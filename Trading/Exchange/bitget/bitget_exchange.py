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


class _BitgetCCXTExchange(exchanges.CCXTExchange):
    def get_client_time_frames(self):
        # on Bitget, it is necessary to specify the instrument type to get timeframes
        # use client.timeframes["spot"]
        return set(self.client.timeframes["spot"])


class Bitget(exchanges.SpotCCXTExchange):

    CONNECTOR_CLASS = _BitgetCCXTExchange
    DESCRIPTION = ""

    @classmethod
    def get_name(cls):
        return 'bitget'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def create_order(self, order_type: trading_enums.TraderOrderType, symbol: str, quantity: decimal.Decimal,
                           price: decimal.Decimal = None, stop_price: decimal.Decimal = None,
                           side: trading_enums.TradeOrderSide = None, current_price: decimal.Decimal = None,
                           params: dict = None) -> typing.Optional[dict]:
        convert_quantity = order_type is trading_enums.TraderOrderType.BUY_MARKET
        if convert_quantity:
            # on Bitget, market orders are in quote currency (YYY in XYZ/YYY)
            if price is None:
                raise octobot_trading.errors.NotSupported(f"{self.get_name()} requires a price parameter to create "
                                                          f"market orders as quantity is in quote currency")
            quantity = quantity * price
        created_order = await super().create_order(order_type, symbol, quantity,
                                                   price=price, stop_price=stop_price,
                                                   side=side, current_price=current_price,
                                                   params=params)
        # ensure order side (issue with current ccxt version)
        created_order[trading_enums.ExchangeConstantsOrderColumns.SIDE.value] = side.value
        if convert_quantity:
            # convert it back: use FILLED for accuracy
            created_order[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] = \
                created_order[trading_enums.ExchangeConstantsOrderColumns.FILLED.value]
        return created_order

    async def get_my_recent_trades(self, symbol=None, since=None, limit=None, **kwargs):
        return self._uniformize_trades(await super().get_my_recent_trades(symbol=symbol,
                                                                          since=since,
                                                                          limit=limit,
                                                                          **kwargs))

    def _uniformize_trades(self, trades):
        for trade in trades:
            # fees example for paid fees in USDT:
            # {'code': 'USDT', 'cost': -0.015922}
            fee = trade[trading_enums.ExchangeConstantsOrderColumns.FEE.value]
            if trading_enums.ExchangeConstantsFeesColumns.CURRENCY.value not in fee:
                fee[trading_enums.ExchangeConstantsFeesColumns.CURRENCY.value] = fee.get("code")
            fee[trading_enums.ExchangeConstantsFeesColumns.COST.value] *= -1
        return trades

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer)
