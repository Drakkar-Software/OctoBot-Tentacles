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
import numpy
import math

import octobot_commons.constants as commons_constants
import octobot_commons.data_util as data_util
import octobot_evaluators.evaluators as evaluators
import octobot_evaluators.util as evaluators_util
import octobot_tentacles_manager.api as tentacles_manager_api
import octobot_trading.api as trading_api
import tentacles.Evaluator.Util as EvaluatorUtil


# evaluates position of the current (2 unit) average trend relatively to the 5 units average and 10 units average trend
class DoubleMovingAverageTrendEvaluator(evaluators.TAEvaluator):

    def __init__(self):
        super().__init__()
        self.long_period_length = 10

    async def ohlcv_callback(self, exchange: str, exchange_id: str,
                             cryptocurrency: str, symbol: str, time_frame, candle, inc_in_construction_data):
        # self.logger.info(f"ohlcv_callback {time_frame}")
        candle_data = trading_api.get_symbol_close_candles(self.get_exchange_symbol_data(exchange, exchange_id, symbol),
                                                           time_frame,
                                                           include_in_construction=inc_in_construction_data)
        await self.evaluate(cryptocurrency, symbol, time_frame, candle_data, candle)

    async def evaluate(self, cryptocurrency, symbol, time_frame, candle_data, candle):
        self.eval_note = commons_constants.START_PENDING_EVAL_NOTE
        if len(candle_data) >= self.long_period_length:
            time_units = [5, self.long_period_length]
            current_moving_average = tulipy.sma(candle_data, 2)
            results = [self.get_moving_average_analysis(candle_data, current_moving_average, time_unit)
                       for time_unit in time_units]
            if len(results):
                self.eval_note = numpy.mean(results)
            else:
                self.eval_note = commons_constants.START_PENDING_EVAL_NOTE

            if self.eval_note == 0:
                self.eval_note = commons_constants.START_PENDING_EVAL_NOTE
        await self.evaluation_completed(cryptocurrency, symbol, time_frame,
                                        eval_time=evaluators_util.get_eval_time(full_candle=candle,
                                                                                time_frame=time_frame))

    # < 0 --> Current average bellow other one (computed using time_period)
    # > 0 --> Current average above other one (computed using time_period)
    @staticmethod
    def get_moving_average_analysis(data, current_moving_average, time_period):

        time_period_unit_moving_average = tulipy.sma(data, time_period)

        # equalize array size
        min_len_arrays = min(len(time_period_unit_moving_average), len(current_moving_average))

        # compute difference between 1 unit values and others ( >0 means currently up the other one)
        values_difference = \
            (current_moving_average[-min_len_arrays:] - time_period_unit_moving_average[-min_len_arrays:])
        values_difference = data_util.drop_nan(values_difference)

        if len(values_difference):
            # indexes where current_unit_moving_average crosses time_period_unit_moving_average
            crossing_indexes = EvaluatorUtil.TrendAnalysis.get_threshold_change_indexes(values_difference, 0)

            multiplier = 1 if values_difference[-1] > 0 else -1

            # check at least some data crossed 0
            if crossing_indexes:
                normalized_data = data_util.normalize_data(values_difference)
                current_value = min(abs(normalized_data[-1]) * 2, 1)
                if math.isnan(current_value):
                    return 0
                # check <= values_difference.count()-1if current value is max/min
                if current_value == 0 or current_value == 1:
                    chances_to_be_max = EvaluatorUtil.TrendAnalysis.get_estimation_of_move_state_relatively_to_previous_moves_length(
                        crossing_indexes,
                        values_difference)
                    return multiplier * current_value * chances_to_be_max
                # other case: maxima already reached => return distance to max
                else:
                    return multiplier * current_value

        # just crossed the average => neutral
        return 0


# evaluates position of the current ema to detect divergences
class EMADivergenceTrendEvaluator(evaluators.TAEvaluator):
    EMA_SIZE = "size"
    SHORT_VALUE = "short"
    LONG_VALUE = "long"

    def __init__(self):
        super().__init__()
        self.evaluator_config = tentacles_manager_api.get_tentacle_config(self.__class__)
        self.period = self.evaluator_config[self.EMA_SIZE]

    async def ohlcv_callback(self, exchange: str, exchange_id: str,
                             cryptocurrency: str, symbol: str, time_frame, candle, inc_in_construction_data):
        candle_data = trading_api.get_symbol_close_candles(self.get_exchange_symbol_data(exchange, exchange_id, symbol),
                                                           time_frame,
                                                           include_in_construction=inc_in_construction_data)
        await self.evaluate(cryptocurrency, symbol, time_frame, candle_data, candle)

    async def evaluate(self, cryptocurrency, symbol, time_frame, candle_data, candle):
        self.eval_note = commons_constants.START_PENDING_EVAL_NOTE
        if len(candle_data) >= self.period:
            current_ema = tulipy.ema(candle_data, self.period)[-1]
            current_price_close = candle_data[-1]
            diff = (current_price_close / current_ema * 100) - 100

            if diff <= self.evaluator_config[self.LONG_VALUE]:
                self.eval_note = -1
            elif diff >= self.evaluator_config[self.SHORT_VALUE]:
                self.eval_note = 1
        await self.evaluation_completed(cryptocurrency, symbol, time_frame,
                                        eval_time=evaluators_util.get_eval_time(full_candle=candle,
                                                                                time_frame=time_frame))
