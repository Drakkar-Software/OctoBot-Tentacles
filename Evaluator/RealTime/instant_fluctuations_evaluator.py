"""
OctoBot Tentacle

$tentacle_description: {
    "name": "instant_fluctuations_evaluator",
    "type": "Evaluator",
    "subtype": "RealTime",
    "version": "1.1.2",
    "requirements": [],
    "config_files": ["InstantRegulatedMarketEvaluator.json", "InstantFluctuationsEvaluator.json"],
    "config_schema_files": ["InstantFluctuationsEvaluator_schema.json"]
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

import math
import tulipy

import numpy as np

from config import ExchangeConstantsOrderBookInfoColumns, CONFIG_REFRESH_RATE, PriceIndexes, CONFIG_TIME_FRAME, \
    START_PENDING_EVAL_NOTE
from evaluator.RealTime.realtime_evaluator import RealTimeExchangeEvaluator

"""
Idea moves are lasting approx 12min:
Check the last 12 candles and compute mean closing prices as well as mean volume with a gradually narrower interval to 
compute the strength or weakness of the move
"""


class InstantFluctuationsEvaluator(RealTimeExchangeEvaluator):
    DESCRIPTION = "Triggers when a change of price ( > 1%) or of volume ( > x4) from recent average happens." \
                  "The price distance from recent average is defining the evaluation."

    PRICE_THRESHOLD_KEY = "price_difference_threshold_percent"
    VOLUME_THRESHOLD_KEY = "volume_difference_threshold_percent"

    def __init__(self, exchange, symbol):
        super().__init__(exchange, symbol)
        self.something_is_happening = False
        self.last_notification_eval = 0

        self.average_prices = {}
        self.last_price = 0

        # Volume
        self.average_volumes = {}
        self.last_volume = 0

        # Constants
        self.evaluator_config = self.get_specific_config()
        self.VOLUME_HAPPENING_THRESHOLD = 1 + (self.evaluator_config[self.VOLUME_THRESHOLD_KEY] / 100)
        self.PRICE_HAPPENING_THRESHOLD = self.evaluator_config[self.PRICE_THRESHOLD_KEY] / 100
        self.MIN_TRIGGERING_DELTA = 0.15
        self.candle_segments = [10, 8, 6, 5, 4, 3, 2, 1]

    async def _refresh_data(self):
        await self.update()

    def reset(self):
        super(InstantFluctuationsEvaluator, self).reset()
        self.average_prices = {}
        self.last_price = 0
        self.average_volumes = {}
        self.last_volume = 0
        self.last_notification_eval = 0

    async def eval_impl(self):
        self.evaluate_volume_fluctuations()
        if self.something_is_happening and self.eval_note != START_PENDING_EVAL_NOTE:
            if abs(self.last_notification_eval - self.eval_note) >= self.MIN_TRIGGERING_DELTA:
                self.last_notification_eval = self.eval_note
                await self.notify_evaluator_task_managers(self.get_name(), force_TA_refresh=True)
            self.something_is_happening = False
        else:
            self.eval_note = START_PENDING_EVAL_NOTE

    def evaluate_volume_fluctuations(self):
        volume_trigger = 0
        price_trigger = 0

        for segment in self.candle_segments:
            if segment in self.average_volumes and segment in self.average_prices:
                # check volume fluctuation
                if self.last_volume > self.VOLUME_HAPPENING_THRESHOLD * self.average_volumes[segment]:
                    volume_trigger += 1
                    self.something_is_happening = True

                # check price fluctuation
                segment_average_price = self.average_prices[segment]
                if self.last_price > (1 + self.PRICE_HAPPENING_THRESHOLD) * segment_average_price:
                    price_trigger += 1
                    self.something_is_happening = True

                elif self.last_price < (1 - self.PRICE_HAPPENING_THRESHOLD) * segment_average_price:
                    price_trigger -= 1
                    self.something_is_happening = True

        if self.candle_segments:
            average_volume_trigger = min(1, volume_trigger / len(self.candle_segments) + 0.2)
            average_price_trigger = price_trigger / len(self.candle_segments)

            if average_price_trigger < 0:
                # math.cos(1-x) between 0 and 1 starts around 0.5 and smoothly goes up to 1
                self.eval_note = -1 * math.cos(1 - (-1 * average_price_trigger * average_volume_trigger))
            elif average_price_trigger > 0:
                self.eval_note = math.cos(1 - average_price_trigger * average_volume_trigger)
            else:
                # no price info => high volume but no price move, can't say anything
                self.something_is_happening = False
        else:
            self.something_is_happening = False

    async def update(self):
        candles_data = await self._get_data_from_exchange(self.specific_config[CONFIG_TIME_FRAME],
                                                          limit=self.candle_segments[0])

        for segment in self.candle_segments:
            volume_data = [d for d in candles_data[PriceIndexes.IND_PRICE_VOL.value][-segment:] if d is not None]
            price_data = [d for d in candles_data[PriceIndexes.IND_PRICE_CLOSE.value][-segment:] if d is not None]
            self.average_volumes[segment] = np.mean(volume_data)
            self.average_prices[segment] = np.mean(price_data)

        self.last_volume = candles_data[PriceIndexes.IND_PRICE_VOL.value][-1]
        self.last_price = candles_data[PriceIndexes.IND_PRICE_CLOSE.value][-1]

    def _should_eval(self):
        return True


class InstantMAEvaluator(RealTimeExchangeEvaluator):
    DESCRIPTION = "Triggers systematically. Uses the simple moving average (on a length of 6) to set its evaluation."

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
        period = 6
        close_values = self.last_candle_data[PriceIndexes.IND_PRICE_CLOSE.value]
        if len(close_values) > period:
            sma_values = tulipy.sma(close_values, period)

            last_ma_value = sma_values[-1]

            if last_ma_value == 0:
                self.eval_note = 0
            else:
                last_price = close_values[-1]
                current_ratio = last_price / last_ma_value
                if current_ratio > 1:
                    # last_price > last_ma_value => sell ? => eval_note > 0
                    if current_ratio >= 2:
                        self.eval_note = 1
                    else:
                        self.eval_note = current_ratio - 1
                elif current_ratio < 1:
                    # last_price < last_ma_value => buy ? => eval_note < 0
                    self.eval_note = -1 * (1 - current_ratio)
                else:
                    self.eval_note = 0

            await self.notify_evaluator_task_managers(self.get_name())

    def set_default_config(self):
        super().set_default_config()
        self.specific_config[CONFIG_REFRESH_RATE] = 0.3

    def _should_eval(self):
        return self.should_eval
