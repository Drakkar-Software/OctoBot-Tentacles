"""
OctoBot Tentacle

$tentacle_description: {
    "name": "price_refresher_evaluator",
    "type": "Evaluator",
    "subtype": "RealTime",
    "version": "1.1.1",
    "config_files": ["PeriodicPriceTickerEvaluator.json"],
    "config_schema_files": ["PeriodicPriceTickerEvaluator_schema.json"]
}
"""
#  Drakkar-Software OctoBot
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

from typing import Dict


from config import ExchangeConstantsTickersInfoColumns, PriceIndexes, CONFIG_TIME_FRAME, \
    START_PENDING_EVAL_NOTE
from evaluator.RealTime.realtime_evaluator import RealTimeExchangeEvaluator


class PeriodicPriceTickerEvaluator(RealTimeExchangeEvaluator):
    DESCRIPTION = "Triggers on a specific interval an notifies the listening strategy with the current price."

    def __init__(self, exchange, symbol):
        super().__init__(exchange, symbol)
        self.last_price = 0

    @staticmethod
    def get_eval_type():
        return Dict[str, float]

    async def _refresh_data(self):
        try:
            candles_data = await self._get_data_from_exchange(self.specific_config[CONFIG_TIME_FRAME])
            self.last_price = candles_data[PriceIndexes.IND_PRICE_CLOSE.value][-1]
        except Exception as e:
            self.logger.exception(e)

    def reset(self):
        super(PeriodicPriceTickerEvaluator, self).reset()
        self.last_price = None

    async def eval_impl(self):
        if self.last_price is not None:
            self.eval_note = self.get_evaluation(self.last_price)
            await self.notify_evaluator_task_managers(self.get_name())
        else:
            self.eval_note = self.get_evaluation(START_PENDING_EVAL_NOTE)

    @staticmethod
    def get_evaluation(last_price):
        return {
            ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: last_price
        }

    def _should_eval(self):
        return True

    def set_default_config(self):
        time_frames = self.exchange.get_exchange_manager().get_config_time_frame()

        self.specific_config = {
            CONFIG_TIME_FRAME: time_frames[0],
        }
