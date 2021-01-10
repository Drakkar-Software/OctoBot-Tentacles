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
import ccxt

import octobot_trading.errors
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges


class CoinbasePro(exchanges.SpotCCXTExchange):
    @classmethod
    def get_name(cls):
        return 'coinbasepro'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        try:
            # on coinbasepro, precision is a decimal instead of a number of digits
            market_status = self._fix_market_status(copy.deepcopy(self.connector.client.market(symbol)))
            if with_fixer:
                market_status = exchanges.ExchangeMarketStatusFixer(market_status, price_example).market_status
            return market_status
        except ccxt.NotSupported:
            raise octobot_trading.errors.NotSupported
        except Exception as e:
            self.logger.error(f"Fail to get market status of {symbol}: {e}")
            return {}

    async def cancel_order(self, order_id, symbol=None, **kwargs):
        self.logger.debug(f"Post cancel for order with id={order_id}")
        try:
            if await super().cancel_order(order_id, symbol=symbol, **kwargs):
                # on coinbasepro, impossible to get a cancelled order
                self.logger.debug(f"Ensure cancel for order with id={order_id}")
                return await self.get_order(order_id, symbol=symbol, **kwargs) is None
        except KeyError as e:
            self.logger.error(f"Order {order_id} failed to cancel | KeyError: {e}")
        return False

    async def get_my_recent_trades(self, symbol=None, since=None, limit=None, **kwargs):
        return self._uniformize_trades(await super().get_my_recent_trades(symbol=symbol,
                                                                          since=since,
                                                                          limit=limit,
                                                                          **kwargs))

    def _uniformize_trades(self, trades):
        if not trades:
            return []
        for trade in trades:
            trade[trading_enums.ExchangeConstantsOrderColumns.STATUS.value] = trading_enums.OrderStatus.CLOSED.value
            trade[trading_enums.ExchangeConstantsOrderColumns.ID.value] = trade[
                trading_enums.ExchangeConstantsOrderColumns.ORDER.value]
            trade[trading_enums.ExchangeConstantsOrderColumns.TYPE.value] = trading_enums.TradeOrderType.MARKET.value \
                if trade["takerOrMaker"] == trading_enums.ExchangeConstantsMarketPropertyColumns.TAKER.value \
                else trading_enums.TradeOrderType.LIMIT.value
        return trades

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
