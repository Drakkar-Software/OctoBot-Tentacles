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
import typing

import ccxt

import octobot_commons.enums
import octobot_trading.errors
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges


class Bitmax(exchanges.SpotCCXTExchange, exchanges.MarginExchange, exchanges.FutureExchange):
    DESCRIPTION = ""

    BUY_STR = "Buy"
    SELL_STR = "Sell"

    ACCOUNTS = {
        trading_enums.AccountTypes.CASH: 'cash',
        trading_enums.AccountTypes.MARGIN: 'margin',
        trading_enums.AccountTypes.FUTURE: 'futures',  # currently in beta
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
        return trading_enums.AccountTypes[account.lower()]

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        try:
            # on BitMax, precision is a decimal instead of a number of digits
            market_status = self._fix_market_status(copy.deepcopy(self.connector.client.market(symbol)))
            if with_fixer:
                market_status = exchanges.ExchangeMarketStatusFixer(market_status, price_example).market_status
            return market_status
        except ccxt.NotSupported:
            raise octobot_trading.errors.NotSupported
        except Exception as e:
            self.logger.error(f"Fail to get market status of {symbol}: {e}")
            return {}

    async def get_my_recent_trades(self, symbol=None, since=None, limit=None, **kwargs):
        # On BitMax, account recent trades is available under fetch_closed_orders
        return await self.connector.client.fetch_closed_orders(symbol=symbol, since=since, limit=limit, params=kwargs)

    async def get_symbol_prices(self,
                                symbol: str,
                                time_frame: octobot_commons.enums.TimeFrames,
                                limit: int = None,
                                **kwargs: dict) -> typing.Optional[list]:
        if limit is None:
            # force default limit on Bitmax since it's not use by default in fetch_ohlcv
            options = self.connector.client.safe_value(self.connector.client.options, 'fetchOHLCV', {})
            limit = self.connector.client.safe_integer(options, 'limit', 500)
        return await super().get_symbol_prices(symbol, time_frame, limit, **kwargs)


    def _fix_market_status(self, market_status):
        market_status[trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION.value][
            trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION_AMOUNT.value] = self._get_digits_count(
            market_status[trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION.value][
                trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION_AMOUNT.value])
        market_status[trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION.value][
            trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION_PRICE.value] = self._get_digits_count(
            market_status[trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION.value][
                trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION_PRICE.value])
        return market_status

    def _get_digits_count(self, value):
        return round(abs(math.log(value, 10)))

    async def _create_specific_order(self, order_type, symbol, quantity, price=None):
        created_order = await super()._create_specific_order(order_type, symbol, quantity, price)
        return self._add_missing_order_details(created_order, order_type, quantity, price)

    def _add_missing_order_details(self, order, order_type, quantity, price):
        order[trading_enums.ExchangeConstantsOrderColumns.SIDE.value] = trading_enums.TradeOrderSide.BUY.value \
            if order_type in {trading_enums.TraderOrderType.BUY_MARKET, trading_enums.TraderOrderType.BUY_LIMIT} \
            else trading_enums.TradeOrderSide.SELL.value
        order[trading_enums.ExchangeConstantsOrderColumns.PRICE.value] = price
        order[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] = quantity
        order[trading_enums.ExchangeConstantsOrderColumns.STATUS.value] = trading_enums.OrderStatus.OPEN.value
        return order
