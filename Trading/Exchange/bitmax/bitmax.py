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
import copy

import math

from octobot_trading.enums import AccountTypes, TraderOrderType, ExchangeConstantsMarketStatusColumns as Ecmsc, \
    ExchangeConstantsOrderColumns, OrderStatus, TradeOrderSide
from octobot_trading.exchanges.implementations.spot_ccxt_exchange import SpotCCXTExchange
from octobot_trading.exchanges.types.future_exchange import FutureExchange
from octobot_trading.exchanges.types.margin_exchange import MarginExchange
from octobot_trading.exchanges.util.exchange_market_status_fixer import ExchangeMarketStatusFixer


class Bitmax(SpotCCXTExchange, MarginExchange, FutureExchange):
    DESCRIPTION = ""

    BUY_STR = "Buy"
    SELL_STR = "Sell"

    ACCOUNTS = {
        AccountTypes.CASH: 'cash',
        AccountTypes.MARGIN: 'margin',
        AccountTypes.FUTURE: 'futures',  # currently in beta
    }

    @classmethod
    def get_name(cls):
        return 'bitmax'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def switch_to_account(self, account_type):
        # TODO
        pass

    def parse_account(self, account):
        return AccountTypes[account.lower()]

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        try:
            # on BitMax, precision is a decimal instead of a number of digits
            market_status = self._fix_market_status(copy.deepcopy(self.client.market(symbol)))
            if with_fixer:
                market_status = ExchangeMarketStatusFixer(market_status, price_example).market_status
            return market_status
        except Exception as e:
            self.logger.error(f"Fail to get market status of {symbol}: {e}")
            return {}

    async def get_my_recent_trades(self, symbol=None, since=None, limit=None, params=None):
        # On BitMax, account recent trades is available under fetch_closed_orders
        if params is None:
            params = {}
        return await self.client.fetch_closed_orders(symbol=symbol, since=since, limit=limit, params=params)

    def _fix_market_status(self, market_status):
        market_status[Ecmsc.PRECISION.value][Ecmsc.PRECISION_AMOUNT.value] = self._get_digits_count(
            market_status[Ecmsc.PRECISION.value][Ecmsc.PRECISION_AMOUNT.value])
        market_status[Ecmsc.PRECISION.value][Ecmsc.PRECISION_PRICE.value] = self._get_digits_count(
            market_status[Ecmsc.PRECISION.value][Ecmsc.PRECISION_PRICE.value])
        return market_status

    def _get_digits_count(self, value):
        return round(abs(math.log(value, 10)))

    async def _create_specific_order(self, order_type, symbol, quantity, price=None):
        created_order = await super()._create_specific_order(order_type, symbol, quantity, price)
        return self._add_missing_order_details(created_order, order_type, quantity, price)

    def _add_missing_order_details(self, order, order_type, quantity, price):
        order[ExchangeConstantsOrderColumns.SIDE.value] = TradeOrderSide.BUY.value \
            if order_type in {TraderOrderType.BUY_MARKET, TraderOrderType.BUY_LIMIT} \
            else TradeOrderSide.SELL.value
        order[ExchangeConstantsOrderColumns.PRICE.value] = price
        order[ExchangeConstantsOrderColumns.AMOUNT.value] = quantity
        order[ExchangeConstantsOrderColumns.STATUS.value] = OrderStatus.OPEN.value
        return order
