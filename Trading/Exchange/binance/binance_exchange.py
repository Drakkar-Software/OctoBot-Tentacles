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

import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges


class Binance(exchanges.SpotCCXTExchange):
    DESCRIPTION = ""

    BUY_STR = "BUY"
    SELL_STR = "SELL"

    ACCOUNTS = {
        trading_enums.AccountTypes.CASH: 'cash'
    }

    BINANCE_MARK_PRICE = "markPrice"

    def __init__(self, config, exchange_manager):
        exchanges.SpotCCXTExchange.__init__(self, config, exchange_manager)

    @classmethod
    def get_name(cls):
        return 'binance'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def get_balance(self, **kwargs):
        return await exchanges.SpotCCXTExchange.get_balance(self, **self._get_params(kwargs))

    async def get_my_recent_trades(self, symbol=None, since=None, limit=None, **kwargs):
        return self._uniformize_trades(await super().get_my_recent_trades(symbol=symbol,
                                                                          since=since,
                                                                          limit=limit,
                                                                          **kwargs))

    def _uniformize_trades(self, trades):
        for trade in trades:
            trade[trading_enums.ExchangeConstantsOrderColumns.STATUS.value] = trading_enums.OrderStatus.CLOSED.value
            trade[trading_enums.ExchangeConstantsOrderColumns.ID.value] = trade[
                trading_enums.ExchangeConstantsOrderColumns.ORDER.value]
            trade[trading_enums.ExchangeConstantsOrderColumns.TYPE.value] = trading_enums.TradeOrderType.MARKET.value \
                if trade["takerOrMaker"] == trading_enums.ExchangeConstantsMarketPropertyColumns.TAKER.value \
                else trading_enums.TradeOrderType.LIMIT.value
        return trades

    def _get_params(self, params):
        if params is None:
            params = {}
        params.update({'recvWindow': 60000})
        return params

    async def get_order(self, order_id, symbol=None, **kwargs):
        return await self._ensure_order_completeness(
            await super().get_order(order_id=order_id, symbol=symbol, **kwargs), symbol, **kwargs)

    async def create_order(self, order_type: trading_enums.TraderOrderType, symbol: str, quantity: decimal.Decimal,
                           price: decimal.Decimal = None, stop_price: decimal.Decimal = None,
                           side: trading_enums.TradeOrderSide = None, current_price: decimal.Decimal = None,
                           params: dict = None):
        return await self._ensure_order_completeness(
            await super().create_order(order_type, symbol, quantity,
                                       price=price, stop_price=stop_price,
                                       side=side, current_price=current_price,
                                       params=params),
            symbol)

    async def get_closed_orders(self, symbol=None, since=None, limit=None, **kwargs):
        orders = await super().get_closed_orders(symbol=symbol, since=since, limit=limit, **kwargs)
        # closed orders are missing fees on binance: add them from trades
        trades = {
            trade[trading_enums.ExchangeConstantsOrderColumns.ORDER.value]: trade
            for trade in await super().get_my_recent_trades(symbol=symbol, since=since, limit=limit, **kwargs)
        }
        for order in orders:
            self._fill_order_missing_data(order, trades)
        return orders

    async def _ensure_order_completeness(self, order, symbol, **kwargs):
        if order and order[
            trading_enums.ExchangeConstantsOrderColumns.STATUS.value] == trading_enums.OrderStatus.CLOSED.value and \
                not order[trading_enums.ExchangeConstantsOrderColumns.FEE.value]:
            trades = {
                trade[trading_enums.ExchangeConstantsOrderColumns.ORDER.value]: trade
                for trade in await super().get_my_recent_trades(symbol=symbol, **kwargs)
            }
            self._fill_order_missing_data(order, trades)
        return order

    def _fill_order_missing_data(self, order, trades):
        order_id = order[trading_enums.ExchangeConstantsOrderColumns.ID.value]
        if not order[trading_enums.ExchangeConstantsOrderColumns.FEE.value] and order_id in trades:
            order[trading_enums.ExchangeConstantsOrderColumns.FEE.value] = \
                trades[order_id][trading_enums.ExchangeConstantsOrderColumns.FEE.value]
