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
from octobot_trading.enums import ExchangeConstantsOrderColumns, OrderStatus, TradeOrderType, \
    ExchangeConstantsMarketPropertyColumns
from octobot_trading.exchanges.types.spot_exchange import SpotExchange


class CoinbasePro(SpotExchange):
    @classmethod
    def get_name(cls):
        return 'coinbasepro'

    async def cancel_order(self, order_id, symbol=None, params=None):
        self.logger.debug(f"Post cancel for order with id={order_id}")
        try:
            if await super().cancel_order(order_id, symbol=symbol, params=params):
                # on coinbasepro, impossible to get a cancelled order
                self.logger.debug(f"Ensure cancel for order with id={order_id}")
                return await self.get_order(order_id, symbol=symbol, params=params) is None
        except KeyError as e:
            self.logger.error(f"Order {order_id} failed to cancel | KeyError: {e}")
        return False

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
