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
from octobot_trading.enums import ExchangeConstantsOrderColumns, AccountTypes, OrderStatus, \
    ExchangeConstantsMarketPropertyColumns, TradeOrderType
from octobot_trading.exchanges.implementations.spot_ccxt_exchange import SpotCCXTExchange


class Binance(SpotCCXTExchange):
    DESCRIPTION = ""

    BUY_STR = "BUY"
    SELL_STR = "SELL"

    ACCOUNTS = {
        AccountTypes.CASH: 'cash'
    }

    BINANCE_MARK_PRICE = "markPrice"

    CCXT_CLIENT_LOGIN_OPTIONS = {'defaultMarket': 'future'}

    @classmethod
    def get_name(cls):
        return 'binance'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def get_balance(self, params=None):
        return await SpotExchange.get_balance(self, params=self._get_params(params))

    async def get_my_recent_trades(self, symbol=None, since=None, limit=None, params=None):
        return self._uniformize_trades(await super().get_my_recent_trades(symbol=symbol,
                                                                          since=since,
                                                                          limit=limit,
                                                                          params=params))

    def _uniformize_trades(self, trades):
        for trade in trades:
            trade[ExchangeConstantsOrderColumns.STATUS.value] = OrderStatus.CLOSED.value
            trade[ExchangeConstantsOrderColumns.ID.value] = trade[ExchangeConstantsOrderColumns.ORDER.value]
            trade[ExchangeConstantsOrderColumns.TYPE.value] = TradeOrderType.MARKET.value \
                if trade["takerOrMaker"] == ExchangeConstantsMarketPropertyColumns.TAKER.value \
                else TradeOrderType.LIMIT.value
        return trades

    def _get_params(self, params):
        if params is None:
            params = {}
        params.update({'recvWindow': 60000})
        return params

    async def get_order(self, order_id, symbol=None, params=None):
        return await self._ensure_order_completeness(
            await super().get_order(order_id=order_id, symbol=symbol, params=params), symbol, params)

    async def create_order(self, order_type, symbol, quantity, price=None, stop_price=None, params=None):
        return await self._ensure_order_completeness(
            await super().create_order(order_type, symbol, quantity, price=price, stop_price=stop_price, params=params),
            symbol, params)

    async def get_closed_orders(self, symbol=None, since=None, limit=None, params=None):
        orders = await super().get_closed_orders(symbol=symbol, since=since, limit=limit, params=params)
        # closed orders are missing fees on binance: add them from trades
        trades = {
            trade[ExchangeConstantsOrderColumns.ORDER.value]: trade
            for trade in await super().get_my_recent_trades(symbol=symbol, since=since, limit=limit, params=params)
        }
        for order in orders:
            self._fill_order_missing_data(order, trades)
        return orders

    async def _ensure_order_completeness(self, order, symbol, params):
        if order and order[ExchangeConstantsOrderColumns.STATUS.value] == OrderStatus.CLOSED.value and \
           not order[ExchangeConstantsOrderColumns.FEE.value]:
            trades = {
                trade[ExchangeConstantsOrderColumns.ORDER.value]: trade
                for trade in await super().get_my_recent_trades(symbol=symbol, params=params)
            }
            self._fill_order_missing_data(order, trades)
        return order

    def _fill_order_missing_data(self, order, trades):
        order_id = order[ExchangeConstantsOrderColumns.ID.value]
        if not order[ExchangeConstantsOrderColumns.FEE.value] and order_id in trades:
            order[ExchangeConstantsOrderColumns.FEE.value] = \
                trades[order_id][ExchangeConstantsOrderColumns.FEE.value]
