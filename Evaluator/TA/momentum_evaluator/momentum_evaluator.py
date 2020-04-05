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
import numpy
import tulipy
from typing import Dict

from octobot_commons.constants import START_PENDING_EVAL_NOTE
from octobot_commons.data_util import drop_nan
from octobot_commons.errors import ConfigError
from octobot_evaluators.evaluator import TAEvaluator
from octobot_tentacles_manager.api.configurator import get_tentacle_config
from tentacles.Evaluator.Util import TrendAnalysis, PatternAnalyser


class RSIMomentumEvaluator(TAEvaluator):

    def __init__(self):
        super().__init__()
        self.pertinence = 1

    async def ohlcv_callback(self, exchange: str, exchange_id: str, symbol: str, time_frame, candle):
        period_length = 14
        candle_data = self.get_symbol_candles(exchange, exchange_id, symbol, time_frame).\
            get_symbol_close_candles(period_length)
        if candle_data is not None and len(candle_data) >= period_length:
            rsi_v = tulipy.rsi(drop_nan(candle_data.base), period=period_length)

            if len(rsi_v) and not math.isnan(rsi_v[-1]):
                long_trend = TrendAnalysis.get_trend(rsi_v, self.long_term_averages)
                short_trend = TrendAnalysis.get_trend(rsi_v, self.short_term_averages)

                # check if trend change
                if short_trend > 0 > long_trend:
                    # trend changed to up
                    self.set_eval_note(-short_trend)

                elif long_trend > 0 > short_trend:
                    # trend changed to down
                    self.set_eval_note(short_trend)

                # use RSI current value
                last_rsi_value = rsi_v[-1]
                if last_rsi_value > 50:
                    self.set_eval_note(rsi_v[-1] / 200)
                else:
                    self.set_eval_note((rsi_v[-1] - 100) / 200)
                await self.evaluation_completed(self.cryptocurrency, symbol, time_frame)


# double RSI analysis
class RSIWeightMomentumEvaluator(TAEvaluator):
    PERIOD = "period"
    SLOW_EVAL_COUNT = "slow_eval_count"
    FAST_EVAL_COUNT = "fast_eval_count"
    RSI_TO_WEIGHTS = "RSI_to_weight"
    SLOW_THRESHOLD = "slow_threshold"
    FAST_THRESHOLD = "fast_threshold"
    FAST_THRESHOLDS = "fast_thresholds"
    WEIGHTS = "weights"
    PRICE = "price"
    VOLUME = "volume"

    @staticmethod
    def get_eval_type():
        return Dict[str, int]

    def __init__(self):
        super().__init__()
        self.evaluator_config = get_tentacle_config(self.__class__)
        self.period_length = self.evaluator_config[self.PERIOD]
        self.slow_eval_count = self.evaluator_config[self.SLOW_EVAL_COUNT]
        self.fast_eval_count = self.evaluator_config[self.FAST_EVAL_COUNT]

        try:
            # ensure rsi weights are sorted
            self.weights = sorted(self.evaluator_config[self.RSI_TO_WEIGHTS], key=lambda a: a[self.SLOW_THRESHOLD])
            for i, fast_threshold in enumerate(self.weights):
                fast_threshold[self.FAST_THRESHOLDS] = sorted(fast_threshold[self.FAST_THRESHOLDS],
                                                              key=lambda a: a[self.FAST_THRESHOLD])
        except KeyError as e:
            raise ConfigError(f"Error when reading config: {e}")

    def _get_rsi_averages(self, symbol_candles):
        # compute the slow and fast RSI average
        candle_data = symbol_candles.get_symbol_close_candles(self.period_length)
        if len(candle_data) > self.period_length:
            rsi_v = tulipy.rsi(drop_nan(candle_data.base), period=self.period_length)
            rsi_v = drop_nan(rsi_v)
            if len(rsi_v):
                slow_average = numpy.mean(rsi_v[-self.slow_eval_count:])
                fast_average = numpy.mean(rsi_v[-self.fast_eval_count:])
                return slow_average, fast_average, rsi_v
        return None, None, None

    @staticmethod
    def _check_inferior(bound, val1, val2):
        return val1 < bound and val2 < bound

    def _analyse_dip_weight(self, slow_rsi, fast_rsi, current_rsi):
        # returns price weight, volume weight
        try:
            for slow_rsi_weight in self.weights:
                if slow_rsi < slow_rsi_weight[self.SLOW_THRESHOLD]:
                    for fast_rsi_weight in slow_rsi_weight[self.FAST_THRESHOLDS]:
                        if self._check_inferior(fast_rsi_weight[self.FAST_THRESHOLD], fast_rsi, current_rsi):
                            return fast_rsi_weight[self.WEIGHTS][self.PRICE], \
                                fast_rsi_weight[self.WEIGHTS][self.VOLUME]
                    # exit loop since the target RSI has been found
                    break
        except KeyError as e:
            self.logger.error(self.get_config_file_error_message(e))
        return None, None

    async def ohlcv_callback(self, exchange: str, exchange_id: str, symbol: str, time_frame, candle):
        self.eval_note = START_PENDING_EVAL_NOTE
        symbol_candles = self.get_symbol_candles(exchange, exchange_id, symbol, time_frame)
        # compute the slow and fast RSI average
        slow_rsi, fast_rsi, rsi_v = self._get_rsi_averages(symbol_candles)
        if slow_rsi is not None and fast_rsi is not None and rsi_v is not None:
            last_rsi_values_to_consider = 5
            analysed_rsi = rsi_v[-last_rsi_values_to_consider:]
            peak_reached = TrendAnalysis.min_has_just_been_reached(analysed_rsi, acceptance_window=0.95, delay=2)
            if peak_reached:
                price_weight, volume_weight = self._analyse_dip_weight(slow_rsi, fast_rsi, rsi_v[-1])
                if price_weight is not None and volume_weight is not None:
                    self.eval_note = {
                        "price_weight": price_weight,
                        "volume_weight": volume_weight,
                        "current_candle_time": symbol_candles.get_symbol_time_candles(1)[-1]
                    }
            await self.evaluation_completed(self.cryptocurrency, symbol, time_frame)


# bollinger_bands
class BBMomentumEvaluator(TAEvaluator):
    async def ohlcv_callback(self, exchange: str, exchange_id: str, symbol: str, time_frame, candle):
        self.eval_note = START_PENDING_EVAL_NOTE
        period_length = 20
        candle_data = self.get_symbol_candles(exchange, exchange_id, symbol, time_frame).\
            get_symbol_close_candles(period_length)
        if len(candle_data) >= period_length:
            # compute bollinger bands
            lower_band, middle_band, upper_band = tulipy.bbands(drop_nan(candle_data.base), period_length, 2)

            # if close to lower band => low value => bad,
            # therefore if close to middle, value is keeping up => good
            # finally if up the middle one or even close to the upper band => very good

            current_value = candle_data[-1]
            current_up = upper_band[-1]
            current_middle = middle_band[-1]
            current_low = lower_band[-1]
            delta_up = current_up - current_middle
            delta_low = current_middle - current_low

            # its exactly on all bands
            if current_up == current_low:
                self.eval_note = START_PENDING_EVAL_NOTE

            # exactly on the middle
            elif current_value == current_middle:
                self.eval_note = 0

            # up the upper band
            elif current_value > current_up:
                self.eval_note = 1

            # down the lower band
            elif current_value < current_low:
                self.eval_note = -1

            # regular values case: use parabolic factor all the time
            else:

                # up the middle band
                if current_middle < current_value:
                    self.eval_note = math.pow((current_value - current_middle) / delta_up, 2)

                # down the middle band
                elif current_middle > current_value:
                    self.eval_note = -1 * math.pow((current_middle - current_value) / delta_low, 2)
            await self.evaluation_completed(self.cryptocurrency, symbol, time_frame)


# ADX --> trend_strength
class ADXMomentumEvaluator(TAEvaluator):
    # implementation according to: https://www.investopedia.com/articles/technical/02/041002.asp => length = 14 and
    # exponential moving average = 20 in a uptrend market
    # idea: adx > 30 => strong trend, < 20 => trend change to come
    async def ohlcv_callback(self, exchange: str, exchange_id: str, symbol: str, time_frame, candle):
        self.eval_note = START_PENDING_EVAL_NOTE
        period_length = 14
        minimal_data = period_length + 11
        symbol_candles = self.get_symbol_candles(exchange, exchange_id, symbol, time_frame)
        close_candles = symbol_candles.get_symbol_close_candles(minimal_data)
        if len(close_candles) >= period_length + 10:
            min_adx = 7.5
            max_adx = 45
            neutral_adx = 25
            high_candles = symbol_candles.get_symbol_high_candles(period_length).base
            low_candles = symbol_candles.get_symbol_low_candles(period_length).base
            adx = tulipy.adx(high_candles, low_candles, close_candles.base, period_length)
            instant_ema = drop_nan(tulipy.ema(close_candles.base, 2))
            slow_ema = drop_nan(tulipy.ema(close_candles.base, 20))
            adx = drop_nan(adx)

            if len(adx):
                current_adx = adx[-1]
                current_slows_ema = slow_ema[-1]
                current_instant_ema = instant_ema[-1]

                multiplier = -1 if current_instant_ema < current_slows_ema else 1

                # strong adx => strong trend
                if current_adx > neutral_adx:
                    # if max adx already reached => when ADX forms a top and begins to turn down, you should look for a
                    # retracement that causes the price to move toward its 20-day exponential moving average (EMA).
                    adx_last_values = adx[-15:]
                    adx_last_value = adx_last_values[-1]

                    local_max_adx = adx_last_values.max()
                    # max already reached => trend will slow down
                    if adx_last_value < local_max_adx:

                        self.eval_note = multiplier * (current_adx - neutral_adx) / (local_max_adx - neutral_adx)

                    # max not reached => trend will continue, return chances to be max now
                    else:
                        crossing_indexes = TrendAnalysis.get_threshold_change_indexes(adx, neutral_adx)
                        chances_to_be_max = \
                            TrendAnalysis.get_estimation_of_move_state_relatively_to_previous_moves_length(
                                crossing_indexes, adx) if len(crossing_indexes) > 2 else 0.75
                        proximity_to_max = min(1, current_adx / max_adx)
                        self.eval_note = multiplier * proximity_to_max * chances_to_be_max

                # weak adx => change to come
                else:
                    self.eval_note = multiplier * min(1, ((neutral_adx - current_adx) / (neutral_adx - min_adx)))
                await self.evaluation_completed(self.cryptocurrency, symbol, time_frame)


class MACDMomentumEvaluator(TAEvaluator):
    def __init__(self):
        super().__init__()
        self.previous_note = None

    def _analyse_pattern(self, pattern, macd_hist, zero_crossing_indexes, price_weight,
                         pattern_move_time, sign_multiplier):
        # add pattern's strength
        weight = price_weight * PatternAnalyser.get_pattern_strength(pattern)

        average_pattern_period = 0.7
        if len(zero_crossing_indexes) > 1:
            # compute chances to be after average pattern period
            patterns = [PatternAnalyser.get_pattern(
                macd_hist[zero_crossing_indexes[i]:zero_crossing_indexes[i + 1]])
                for i in range(len(zero_crossing_indexes) - 1)
            ]
            if 0 != zero_crossing_indexes[0]:
                patterns.append(PatternAnalyser.get_pattern(macd_hist[0:zero_crossing_indexes[0]]))
            if len(macd_hist) - 1 != zero_crossing_indexes[-1]:
                patterns.append(PatternAnalyser.get_pattern(macd_hist[zero_crossing_indexes[-1]:]))
            double_patterns_count = patterns.count("W") + patterns.count("M")

            average_pattern_period = TrendAnalysis. \
                get_estimation_of_move_state_relatively_to_previous_moves_length(
                    zero_crossing_indexes,
                    macd_hist,
                    pattern_move_time,
                    double_patterns_count)

        # if we have few data but wave is growing => set higher value
        if len(zero_crossing_indexes) <= 1 and price_weight == 1:
            if self.previous_note is not None:
                average_pattern_period = 0.95
            self.previous_note = sign_multiplier * weight * average_pattern_period
        else:
            self.previous_note = None

        self.eval_note = sign_multiplier * weight * average_pattern_period

    async def ohlcv_callback(self, exchange: str, exchange_id: str, symbol: str, time_frame, candle):
        self.eval_note = START_PENDING_EVAL_NOTE
        long_period_length = 26
        candle_data = self.get_symbol_candles(exchange, exchange_id, symbol, time_frame).\
            get_symbol_close_candles(long_period_length)
        if len(candle_data) >= long_period_length:
            macd, macd_signal, macd_hist = tulipy.macd(drop_nan(candle_data.base), 12, long_period_length, 9)

            # on macd hist => M pattern: bearish movement, W pattern: bullish movement
            #                 max on hist: optimal sell or buy
            macd_hist = drop_nan(macd_hist)
            zero_crossing_indexes = TrendAnalysis.get_threshold_change_indexes(macd_hist, 0)
            last_index = len(macd_hist) - 1
            pattern, start_index, end_index = PatternAnalyser.find_pattern(macd_hist, zero_crossing_indexes,
                                                                           last_index)

            if pattern != PatternAnalyser.UNKNOWN_PATTERN:

                # set sign (-1 buy or 1 sell)
                sign_multiplier = -1 if pattern == "W" or pattern == "V" else 1

                # set pattern time frame => W and M are on 2 time frames, others 1
                pattern_move_time = 2 if (pattern == "W" or pattern == "M") and end_index == last_index else 1

                # set weight according to the max value of the pattern and the current value
                current_pattern_start = start_index
                price_weight = macd_hist[-1] / macd_hist[current_pattern_start:].max() if sign_multiplier == 1 \
                    else macd_hist[-1] / macd_hist[current_pattern_start:].min()

                if not math.isnan(price_weight):
                    self._analyse_pattern(pattern, macd_hist, zero_crossing_indexes, price_weight,
                                          pattern_move_time, sign_multiplier)
            await self.evaluation_completed(self.cryptocurrency, symbol, time_frame)


class KlingerOscillatorMomentumEvaluator(TAEvaluator):

    async def ohlcv_callback(self, exchange: str, exchange_id: str, symbol: str, time_frame, candle):
        eval_proposition = START_PENDING_EVAL_NOTE
        short_period = 35    # standard with klinger
        long_period = 55     # standard with klinger
        ema_signal_period = 13  # standard ema signal for klinger
        symbol_candles = self.get_symbol_candles(exchange, exchange_id, symbol, time_frame)
        kvo = tulipy.kvo(drop_nan(symbol_candles.get_symbol_high_candles().base),
                         drop_nan(symbol_candles.get_symbol_low_candles().base),
                         drop_nan(symbol_candles.get_symbol_close_candles().base),
                         drop_nan(symbol_candles.get_symbol_volume_candles().base),
                         short_period,
                         long_period)
        kvo = drop_nan(kvo)
        if len(kvo) >= ema_signal_period:
            kvo_ema = tulipy.ema(kvo, ema_signal_period)

            ema_difference = kvo-kvo_ema

            if len(ema_difference) > 1:
                zero_crossing_indexes = TrendAnalysis.get_threshold_change_indexes(ema_difference, 0)

                current_difference = ema_difference[-1]
                significant_move_threshold = numpy.std(ema_difference)

                factor = 0.2

                if TrendAnalysis.peak_has_been_reached_already(ema_difference[zero_crossing_indexes[-1]:]):
                    if abs(current_difference) > significant_move_threshold:
                        factor = 1
                    else:
                        factor = 0.5

                eval_proposition = current_difference*factor/significant_move_threshold

                if abs(eval_proposition) > 1:
                    eval_proposition = 1 if eval_proposition > 0 else -1

        self.eval_note = eval_proposition
        await self.evaluation_completed(self.cryptocurrency, symbol, time_frame)
