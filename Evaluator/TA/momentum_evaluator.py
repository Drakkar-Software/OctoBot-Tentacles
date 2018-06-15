"""
OctoBot Tentacle

$tentacle_description: {
    "name": "momentum_evaluator",
    "type": "Evaluator",
    "subtype": "TA",
    "version": "1.0.0",
    "requirements": []
}
"""

import math

import tulipy

from config.cst import *
from evaluator.TA.TA_evaluator import MomentumEvaluator
from evaluator.Util import PatternAnalyser
from evaluator.Util import TrendAnalysis
from tools.data_util import DataUtil


class RSIMomentumEvaluator(MomentumEvaluator):
    def __init__(self):
        super().__init__()
        self.pertinence = 1

    # TODO : temp analysis
    def eval_impl(self):
        if len(self.data):
            rsi_v = tulipy.rsi(self.data[PriceIndexes.IND_PRICE_CLOSE.value], period=14)

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


# bollinger_bands
class BBMomentumEvaluator(MomentumEvaluator):
    def __init__(self):
        super().__init__()

    def eval_impl(self):
        self.eval_note = START_PENDING_EVAL_NOTE
        if len(self.data):
            # compute bollinger bands
            lower_band, middle_band, upper_band = tulipy.bbands(self.data[PriceIndexes.IND_PRICE_CLOSE.value], 20, 2)

            # if close to lower band => low value => bad,
            # therefore if close to middle, value is keeping up => good
            # finally if up the middle one or even close to the upper band => very good

            current_value = self.data[PriceIndexes.IND_PRICE_CLOSE.value][-1]
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


# ADX --> trend_strength
class ADXMomentumEvaluator(MomentumEvaluator):
    def __init__(self):
        super().__init__()

    # implementation according to: https://www.investopedia.com/articles/technical/02/041002.asp => length = 14 and
    # exponential moving average = 20 in a uptrend market
    # idea: adx > 30 => strong trend, < 20 => trend change to come
    def eval_impl(self):
        self.eval_note = START_PENDING_EVAL_NOTE
        if len(self.data):
            min_adx = 7.5
            max_adx = 45
            neutral_adx = 25
            adx = tulipy.adx(self.data[PriceIndexes.IND_PRICE_HIGH.value],
                             self.data[PriceIndexes.IND_PRICE_LOW.value],
                             self.data[PriceIndexes.IND_PRICE_CLOSE.value],
                             14)
            instant_ema = tulipy.ema(self.data[PriceIndexes.IND_PRICE_CLOSE.value], 2)
            slow_ema = tulipy.ema(self.data[PriceIndexes.IND_PRICE_CLOSE.value], 20)
            adx = DataUtil.drop_nan(adx)

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
                                crossing_indexes, adx) if len(crossing_indexes) > 2 \
                                else 0.75
                        proximity_to_max = min(1, current_adx / max_adx)
                        self.eval_note = multiplier * proximity_to_max * chances_to_be_max

                # weak adx => change to come
                else:
                    self.eval_note = multiplier * min(1, ((neutral_adx - current_adx) / (neutral_adx - min_adx)))


class OBVMomentumEvaluator(MomentumEvaluator):
    def __init__(self):
        super().__init__()

    def eval_impl(self):
        # obv_v = talib.OBV(self.data[PriceStrings.STR_PRICE_CLOSE.value],
        #                   self.data[PriceStrings.STR_PRICE_VOL.value])
        pass


# William's % R --> overbought / oversold
class WilliamsRMomentumEvaluator(MomentumEvaluator):
    def __init__(self):
        super().__init__()

    def eval_impl(self):
        # willr_v = talib.WILLR(self.data[PriceStrings.STR_PRICE_HIGH.value],
        #                       self.data[PriceStrings.STR_PRICE_LOW.value],
        #                       self.data[PriceStrings.STR_PRICE_CLOSE.value])
        pass


# TRIX --> percent rate-of-change trend
class TRIXMomentumEvaluator(MomentumEvaluator):
    def __init__(self):
        super().__init__()

    def eval_impl(self):
        # trix_v = talib.TRIX(self.data[PriceStrings.STR_PRICE_CLOSE.value])
        pass


class MACDMomentumEvaluator(MomentumEvaluator):
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

    def eval_impl(self):
        self.eval_note = START_PENDING_EVAL_NOTE
        if len(self.data):
            macd, macd_signal, macd_hist = tulipy.macd(self.data[PriceIndexes.IND_PRICE_CLOSE.value], 12, 26, 9)

            # on macd hist => M pattern: bearish movement, W pattern: bullish movement
            #                 max on hist: optimal sell or buy
            macd_hist = DataUtil.drop_nan(macd_hist)
            zero_crossing_indexes = TrendAnalysis.get_threshold_change_indexes(macd_hist, 0)
            last_index = len(macd_hist) - 1
            pattern, start_index, end_index = PatternAnalyser.find_pattern(macd_hist, zero_crossing_indexes, last_index)

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


class ChaikinOscillatorMomentumEvaluator(MomentumEvaluator):
    def __init__(self):
        super().__init__()

    def eval_impl(self):
        pass
