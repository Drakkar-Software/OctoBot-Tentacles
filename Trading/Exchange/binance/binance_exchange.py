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


class Binance(exchanges.RestExchange):
    DESCRIPTION = ""

    BUY_STR = "BUY"
    SELL_STR = "SELL"

    ACCOUNTS = {    # useless ?
        trading_enums.AccountTypes.CASH: 'cash'
    }

    @classmethod
    def get_name(cls):
        return 'binance'

    def get_adapter_class(self):
        return BinanceCCXTAdapter

    async def get_balance(self, **kwargs):
        return await exchanges.RestExchange.get_balance(self, **self._get_params(kwargs))

    def _get_params(self, params):
        if params is None:
            params = {}
        params.update({'recvWindow': 60000})
        return params

    async def get_order(self, order_id, symbol=None, **kwargs):
        return await self._ensure_order_completeness(
            await super().get_order(order_id=order_id, symbol=symbol, **kwargs),
            symbol, **kwargs
        )

    async def create_order(self, order_type: trading_enums.TraderOrderType, symbol: str, quantity: decimal.Decimal,
                           price: decimal.Decimal = None, stop_price: decimal.Decimal = None,
                           side: trading_enums.TradeOrderSide = None, current_price: decimal.Decimal = None,
                           params: dict = None):
        return await self._ensure_order_completeness(
            await super().create_order(order_type, symbol, quantity,
                                       price=price, stop_price=stop_price,
                                       side=side, current_price=current_price,
                                       params=params),
            symbol
        )

    async def get_closed_orders(self, symbol=None, since=None, limit=None, **kwargs):
        orders = await super().get_closed_orders(symbol=symbol, since=since, limit=limit, **kwargs)
        # closed orders are missing fees on binance: add them from trades
        trades = await self.get_trades_by_order_id(symbol=symbol, since=since, limit=limit, **kwargs)
        for order in orders:
            await self._ensure_order_completeness(order, symbol, trades=trades, **kwargs)
        return orders

    async def _ensure_order_completeness(self, order, symbol, trades=None, **kwargs):
        if order and order[
            trading_enums.ExchangeConstantsOrderColumns.STATUS.value
        ] == trading_enums.OrderStatus.CLOSED.value and self._should_fetch_fees_from_trades(order):
            if trades is None:
                trades = await self.get_trades_by_order_id(symbol=symbol, **kwargs)
            self._fill_order_missing_data(order, trades)
        return order

    async def get_trades_by_order_id(self, symbol=None, since=None, limit=None, **kwargs):
        trades = {}
        for trade in await super().get_my_recent_trades(symbol=symbol, since=since, limit=limit, **kwargs):
            order_id = trade[trading_enums.ExchangeConstantsOrderColumns.ORDER.value]
            if order_id in trades:
                trades[order_id].append(trade)
            else:
                trades[order_id] = [trade]
        return trades

    def _fill_order_missing_data(self, order, trades):
        order_id = order[trading_enums.ExchangeConstantsOrderColumns.ID.value]
        if self._should_fetch_fees_from_trades(order) and order_id in trades:
            order_fee = trades[order_id][0][trading_enums.ExchangeConstantsOrderColumns.FEE.value]
            # add each order's trades fee
            for trade in trades[order_id][1:]:
                order_fee[trading_enums.FeePropertyColumns.COST.value] += \
                    trade[trading_enums.ExchangeConstantsOrderColumns.FEE.value][trading_enums.FeePropertyColumns.COST.value]
                order_fee[trading_enums.FeePropertyColumns.EXCHANGE_ORIGINAL_COST.value] += \
                    trade[trading_enums.ExchangeConstantsOrderColumns.FEE.value][
                        trading_enums.FeePropertyColumns.EXCHANGE_ORIGINAL_COST.value]
            order[trading_enums.ExchangeConstantsOrderColumns.FEE.value] = order_fee

    def _should_fetch_fees_from_trades(self, order):
        try:
            return order[trading_enums.ExchangeConstantsOrderColumns.FEE.value][
                trading_enums.FeePropertyColumns.EXCHANGE_ORIGINAL_COST.value] is None
        except KeyError:
            return True


class BinanceCCXTAdapter(exchanges.CCXTAdapter):

    def fix_trades(self, raw, **kwargs):
        raw = super().fix_trades(raw, **kwargs)
        for trade in raw:
            trade[trading_enums.ExchangeConstantsOrderColumns.STATUS.value] = trading_enums.OrderStatus.CLOSED.value
            trade[trading_enums.ExchangeConstantsOrderColumns.ID.value] = trade[
                trading_enums.ExchangeConstantsOrderColumns.ORDER.value]
        return raw
