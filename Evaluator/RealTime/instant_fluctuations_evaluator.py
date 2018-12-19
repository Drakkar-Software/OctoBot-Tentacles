"""
OctoBot Tentacle

$tentacle_description: {
    "package_name": "OctoBot-Tentacles",
    "name": "instant_fluctuations_evaluator",
    "type": "Evaluator",
    "subtype": "RealTime",
    "version": "1.0.0",
    "requirements": [],
    "config_files": ["InstantRegulatedMarketEvaluator.json"]
}
"""
import math
import tulipy

import numpy as np

from config import *
from evaluator.RealTime.realtime_evaluator import RealTimeTAEvaluator

"""
Idea moves are lasting approx 12min:
Check the last 12 candles and compute mean closing prices as well as mean volume with a gradually narrower interval to 
compute the strength or weakness of the move
"""


class InstantFluctuationsEvaluator(RealTimeTAEvaluator):
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
        self.VOLUME_HAPPENING_THRESHOLD = 4
        self.PRICE_HAPPENING_THRESHOLD = 0.01
        self.MIN_TRIGGERING_DELTA = 0.15
        self.candle_segments = [10, 8, 6, 5, 4, 3, 2, 1]

    def _refresh_data(self):
        self.update()

    def reset(self):
        super(InstantFluctuationsEvaluator, self).reset()
        self.average_prices = {}
        self.last_price = 0
        self.average_volumes = {}
        self.last_volume = 0
        self.last_notification_eval = 0

    def eval_impl(self):
        self.evaluate_volume_fluctuations()
        if self.something_is_happening and self.eval_note != START_PENDING_EVAL_NOTE:
            if abs(self.last_notification_eval - self.eval_note) >= self.MIN_TRIGGERING_DELTA:
                self.last_notification_eval = self.eval_note
                self.notify_evaluator_thread_managers(self.__class__.__name__, force_TA_refresh=True)
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

    def update(self):
        candles_data = self._get_data_from_exchange(self.specific_config[CONFIG_TIME_FRAME],
                                                    limit=self.candle_segments[0])

        for segment in self.candle_segments:
            self.average_volumes[segment] = np.mean(candles_data[PriceIndexes.IND_PRICE_VOL.value][-segment:])
            self.average_prices[segment] = np.mean(candles_data[PriceIndexes.IND_PRICE_CLOSE.value][-segment:])

        self.last_volume = candles_data[PriceIndexes.IND_PRICE_VOL.value][-1]
        self.last_price = candles_data[PriceIndexes.IND_PRICE_CLOSE.value][-1]

    def _should_eval(self):
        return True


# Returns :
# 0 when situation is changing
# -1 when the market is stable
# 1 when the market is unstable

class InstantVolatilityEvaluator(RealTimeTAEvaluator):
    STOCH_INSTABILITY_THRESHOLD = 50
    STOCH_STABILITY_THRESHOLD = 30

    def __init__(self, exchange, symbol):
        super().__init__(exchange, symbol)
        self.last_candle_data = None
        self.last_eval_note = START_PENDING_EVAL_NOTE

    def _refresh_data(self):
        self.last_candle_data = self._get_data_from_exchange(self.specific_config[CONFIG_TIME_FRAME],
                                                             limit=20, return_list=False)

    def eval_impl(self):
        self.eval_note = 0
        # slowk --> fastest
        # slowd --> slowest
        slowk, slowd = tulipy.stoch(self.last_candle_data[PriceIndexes.IND_PRICE_HIGH.value],
                                    self.last_candle_data[PriceIndexes.IND_PRICE_LOW.value],
                                    self.last_candle_data[PriceIndexes.IND_PRICE_CLOSE.value],
                                    14,
                                    3,
                                    3)

        last_value = slowd[-1]

        if last_value > self.STOCH_INSTABILITY_THRESHOLD:
            self.eval_note = 1

        if last_value < self.STOCH_STABILITY_THRESHOLD:
            self.eval_note = -1

        if self.last_eval_note != self.eval_note:
            self.notify_evaluator_thread_managers(self.__class__.__name__)
            self.last_eval_note = self.eval_note

    def set_default_config(self):
        super().set_default_config()
        self.specific_config[CONFIG_REFRESH_RATE] = 0.5

    def _should_eval(self):
        return True


class InstantMAEvaluator(RealTimeTAEvaluator):
    def __init__(self, exchange, symbol):
        super().__init__(exchange, symbol)
        self.last_candle_data = None
        self.last_eval_note = START_PENDING_EVAL_NOTE
        self.should_eval = True

    def _refresh_data(self):
        new_data = self._get_data_from_exchange(self.specific_config[CONFIG_TIME_FRAME],
                                                limit=20, return_list=False)
        self.should_eval = not self._compare_data(new_data, self.last_candle_data)
        self.last_candle_data = new_data

    def eval_impl(self):
        self.eval_note = 0
        close_values = self.last_candle_data[PriceIndexes.IND_PRICE_CLOSE.value]
        sma_values = tulipy.sma(close_values, 6)

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

        self.notify_evaluator_thread_managers(self.__class__.__name__)

    def set_default_config(self):
        super().set_default_config()
        self.specific_config[CONFIG_REFRESH_RATE] = 0.3

    def _should_eval(self):
        return self.should_eval


class InstantRegulatedMarketEvaluator(RealTimeTAEvaluator):
    MARKET_PRICE = "regulated_market_price"
    MARKET_RANGE = "regulated_market_range"

    def __init__(self, exchange, symbol):
        super().__init__(exchange, symbol)
        self.last_candle_data = None
        self.last_eval_note = START_PENDING_EVAL_NOTE
        self.should_eval = True

    def _refresh_data(self):
        new_data = self._get_data_from_exchange(self.specific_config[CONFIG_TIME_FRAME],
                                                limit=20, return_list=False)
        self.should_eval = not self._compare_data(new_data, self.last_candle_data)
        self.last_candle_data = new_data

    def eval_impl(self):
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
            self.notify_evaluator_thread_managers(self.__class__.__name__)
            self.last_eval_note = self.eval_note

    def set_default_config(self):
        super().set_default_config()
        self.specific_config[CONFIG_REFRESH_RATE] = 0.3

    def _should_eval(self):
        return self.should_eval
