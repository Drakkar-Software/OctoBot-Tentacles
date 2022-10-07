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
import copy
import math
import decimal
import ccxt

import octobot_trading.errors
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges
from octobot_trading.enums import ExchangeConstantsOrderColumns as ecoc


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
        # try from trades (get_order is not returning filled or cancelled orders)
        # todo: figure out a way to fet cancelled orders
        return await self._get_order_from_trades(symbol, order_id, {})

    async def _get_order_from_trades(self, symbol, order_id, order_to_update):
        trades = await self.get_my_recent_trades(symbol)
        # usually the last trade is the right one
        for _ in range(3):
            for trade in trades[::-1]:
                if trade[ecoc.ORDER.value] == order_id:
                    order_to_update[ecoc.INFO.value] = trade[ecoc.INFO.value]
                    order_to_update[ecoc.ID.value] = order_id
                    order_to_update[ecoc.SYMBOL.value] = symbol
                    order_to_update[ecoc.TYPE.value] = trade[ecoc.TYPE.value]
                    order_to_update[ecoc.AMOUNT.value] = trade[ecoc.AMOUNT.value]
                    order_to_update[ecoc.DATETIME.value] = trade[ecoc.DATETIME.value]
                    order_to_update[ecoc.SIDE.value] = trade[ecoc.SIDE.value]
                    order_to_update[ecoc.TAKERORMAKER.value] = trade[ecoc.TAKERORMAKER.value]
                    order_to_update[ecoc.PRICE.value] = trade[ecoc.PRICE.value]
                    order_to_update[ecoc.TIMESTAMP.value] = order_to_update.get(ecoc.TIMESTAMP.value,
                                                                            trade[ecoc.TIMESTAMP.value])
                    order_to_update[ecoc.STATUS.value] = trading_enums.OrderStatus.FILLED.value
                    order_to_update[ecoc.FILLED.value] = trade[ecoc.AMOUNT.value]
                    order_to_update[ecoc.COST.value] = trade[ecoc.COST.value]
                    order_to_update[ecoc.REMAINING.value] = 0
                    order_to_update[ecoc.FEE.value] = trade[ecoc.FEE.value]
                    return order_to_update
            # retry soon
            await asyncio.sleep(3)
        raise KeyError("Order id not found in trades. Impossible to build order from trades history")

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        try:
            market_status = self._fix_market_status(copy.deepcopy(self.connector.client.market(symbol)))
            if with_fixer:
                market_status = exchanges.ExchangeMarketStatusFixer(market_status, price_example).market_status
            return market_status
        except ccxt.NotSupported:
            raise octobot_trading.errors.NotSupported
        except Exception as e:
            self.logger.error(f"Fail to get market status of {symbol}: {e}")
        return {}

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
