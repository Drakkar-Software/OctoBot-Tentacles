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

from octobot_commons.constants import START_PENDING_EVAL_NOTE
from octobot_commons.data_util import drop_nan
from octobot_evaluators.evaluator import TAEvaluator
from tentacles.Evaluator.Util import TrendAnalysis


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
