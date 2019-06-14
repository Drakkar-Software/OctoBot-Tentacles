"""
OctoBot Tentacle

$tentacle_description: {
    "name": "in_development_real_time_evaluators",
    "type": "Evaluator",
    "subtype": "RealTime",
    "version": "1.1.0",
    "requirements": [],
    "developing": true
}
"""


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

import tulipy
from typing import Dict

from config import CONFIG_TIME_FRAME, TimeFrames, CONFIG_REFRESH_RATE, START_PENDING_EVAL_NOTE, PriceIndexes, \
    ExchangeConstantsOrderBookInfoColumns
from evaluator.RealTime import RealTimeExchangeEvaluator


class WhalesOrderBookEvaluator(RealTimeExchangeEvaluator):

    def _refresh_data(self):
        pass

    async def eval_impl(self):
        pass

    def set_default_config(self):
        self.specific_config = {
            CONFIG_REFRESH_RATE: 5,
            CONFIG_TIME_FRAME: TimeFrames.FIVE_MINUTES
        }

    def _should_eval(self):
        pass


# Returns :
# 0 when situation is changing
# -1 when the market is stable
# 1 when the market is unstable

class InstantVolatilityEvaluator(RealTimeExchangeEvaluator):
    DESCRIPTION = "Triggers when the stochastic indicator crosses stability and instability thresholds. " \
                  "Evaluation is respectively -1 or 1."

    STOCH_INSTABILITY_THRESHOLD = 50
    STOCH_STABILITY_THRESHOLD = 30

    def __init__(self, exchange, symbol):
        super().__init__(exchange, symbol)
        self.last_candle_data = None
        self.last_eval_note = START_PENDING_EVAL_NOTE

    async def _refresh_data(self):
        self.last_candle_data = await self._get_data_from_exchange(self.specific_config[CONFIG_TIME_FRAME],
                                                                   limit=20, return_list=False)

    async def eval_impl(self):
        self.eval_note = 0
        # slowk --> fastest
        # slowd --> slowest
        pct_k_period = 14
        pct_k_slowing_period = 3
        pct_d_period = 3
        if len(self.last_candle_data[PriceIndexes.IND_PRICE_HIGH.value] > pct_k_period):
            slowk, slowd = tulipy.stoch(self.last_candle_data[PriceIndexes.IND_PRICE_HIGH.value],
                                        self.last_candle_data[PriceIndexes.IND_PRICE_LOW.value],
                                        self.last_candle_data[PriceIndexes.IND_PRICE_CLOSE.value],
                                        pct_k_period,
                                        pct_k_slowing_period,
                                        pct_d_period)

            last_value = slowd[-1]

            if last_value > self.STOCH_INSTABILITY_THRESHOLD:
                self.eval_note = 1

            if last_value < self.STOCH_STABILITY_THRESHOLD:
                self.eval_note = -1

            if self.last_eval_note != self.eval_note:
                await self.notify_evaluator_task_managers(self.get_name())
                self.last_eval_note = self.eval_note

    def set_default_config(self):
        super().set_default_config()
        self.specific_config[CONFIG_REFRESH_RATE] = 0.5

    def _should_eval(self):
        return True


class InstantMarketMakingEvaluator(RealTimeExchangeEvaluator):
    DESCRIPTION = "Triggers on order book change. Uses the simple moving average (on a length of 6) to set its " \
                  "evaluation. Warning: sets an order book evaluation which can only be used by specific strategies."

    def __init__(self, exchange, symbol):
        super().__init__(exchange, symbol)
        self.last_best_bid = None
        self.last_best_ask = None
        self.last_order_book_data = None
        self.should_eval = True

    @staticmethod
    def get_eval_type():
        return Dict[str, float]

    async def _refresh_data(self):
        self.last_order_book_data = await self._get_order_book_from_exchange(limit=5)

    async def eval_impl(self):
        self.eval_note = ""
        best_bid = self.last_best_bid
        best_ask = self.last_best_ask

        if self.last_order_book_data is not None:
            best_bid = self.last_order_book_data[ExchangeConstantsOrderBookInfoColumns.BIDS.value][-1]
            best_ask = self.last_order_book_data[ExchangeConstantsOrderBookInfoColumns.ASKS.value][-1]

        if self.last_best_ask != best_ask or self.last_best_bid != best_bid:
            self.eval_note = {
                ExchangeConstantsOrderBookInfoColumns.BIDS.value: best_bid,
                ExchangeConstantsOrderBookInfoColumns.ASKS.value: best_ask
            }
            await self.notify_evaluator_task_managers(self.get_name())
            self.last_best_ask = best_ask
            self.last_best_bid = best_bid

    def set_default_config(self):
        super().set_default_config()
        self.specific_config[CONFIG_REFRESH_RATE] = 60

    def _should_eval(self):
        return self.should_eval


class InstantRegulatedMarketEvaluator(RealTimeExchangeEvaluator):

    MARKET_PRICE = "regulated_market_price"
    MARKET_RANGE = "regulated_market_range"

    def __init__(self, exchange, symbol):
        super().__init__(exchange, symbol)
        self.last_candle_data = None
        self.last_eval_note = START_PENDING_EVAL_NOTE
        self.should_eval = True

    async def _refresh_data(self):
        new_data = await self._get_data_from_exchange(self.specific_config[CONFIG_TIME_FRAME],
                                                      limit=20, return_list=False)
        self.should_eval = not self._compare_data(new_data, self.last_candle_data)
        self.last_candle_data = new_data

    async def eval_impl(self):
        self.eval_note = 0
        close_values = self.last_candle_data[PriceIndexes.IND_PRICE_CLOSE.value]

        last_price = close_values[-1]

        # TODO
        # should sell
        if last_price > self.specific_config[self.MARKET_PRICE] + \
                self.specific_config[self.MARKET_PRICE] * self.specific_config[self.MARKET_RANGE]:
            self.eval_note = 1

        # should buy
        elif last_price < self.specific_config[self.MARKET_PRICE] - \
                self.specific_config[self.MARKET_PRICE] * self.specific_config[self.MARKET_RANGE]:
            self.eval_note = -1

        else:
            self.eval_note = 0

        if self.last_eval_note != self.eval_note:
            await self.notify_evaluator_task_managers(self.get_name())
            self.last_eval_note = self.eval_note

    def set_default_config(self):
        super().set_default_config()
        self.specific_config[CONFIG_REFRESH_RATE] = 0.3

    def _should_eval(self):
        return self.should_eval
