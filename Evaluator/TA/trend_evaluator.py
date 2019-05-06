"""
OctoBot Tentacle

$tentacle_description: {
    "name": "trend_evaluator",
    "type": "Evaluator",
    "subtype": "TA",
    "version": "1.1.1",
    "requirements": [],
    "config_files": ["EMADivergenceTrendEvaluator.json"],
    "config_schema_files": ["EMADivergenceTrendEvaluator_schema.json"],
    "tests":["test_double_moving_averages_TA_evaluator"]
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

from config import *
import numpy
import math

from evaluator.TA.TA_evaluator import TrendEvaluator
from evaluator.Util import TrendAnalysis
from tools.data_util import DataUtil


# evaluates position of the current (2 unit) average trend relatively to the 5 units average and 10 units average trend
class DoubleMovingAverageTrendEvaluator(TrendEvaluator):
    DESCRIPTION = "Uses two moving averages (length of 5 and length of 10) to find reversals. " \
                  "Evaluates -1 to 1 relatively to the computed reversal probability and the current price " \
                  "distance from moving averages."

    async def eval_impl(self):
        self.eval_note = START_PENDING_EVAL_NOTE
        long_period_length = 10
        if len(self.data[PriceIndexes.IND_PRICE_CLOSE.value]) > long_period_length:
            time_units = [5, long_period_length]
            current_moving_average = tulipy.sma(self.data[PriceIndexes.IND_PRICE_CLOSE.value], 2)
            results = [self.get_moving_average_analysis(self.data[PriceIndexes.IND_PRICE_CLOSE.value],
                                                        current_moving_average,
                                                        i)
                       for i in time_units]
            if len(results):
                self.eval_note = numpy.mean(results)
            else:
                self.eval_note = START_PENDING_EVAL_NOTE

            if self.eval_note == 0:
                self.eval_note = START_PENDING_EVAL_NOTE

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
        values_difference = DataUtil.drop_nan(values_difference)

        if len(values_difference):
            # indexes where current_unit_moving_average crosses time_period_unit_moving_average
            crossing_indexes = TrendAnalysis.get_threshold_change_indexes(values_difference, 0)

            multiplier = 1 if values_difference[-1] > 0 else -1

            # check at least some data crossed 0
            if crossing_indexes:
                normalized_data = DataUtil.normalize_data(values_difference)
                current_value = min(abs(normalized_data[-1]) * 2, 1)
                if math.isnan(current_value):
                    return 0
                # check <= values_difference.count()-1if current value is max/min
                if current_value == 0 or current_value == 1:
                    chances_to_be_max = TrendAnalysis.get_estimation_of_move_state_relatively_to_previous_moves_length(
                        crossing_indexes,
                        values_difference)
                    return multiplier * current_value * chances_to_be_max
                # other case: maxima already reached => return distance to max
                else:
                    return multiplier * current_value

        # just crossed the average => neutral
        return 0


# evaluates position of the current ema to detect divergences
class EMADivergenceTrendEvaluator(TrendEvaluator):
    DESCRIPTION = "Uses ema to find divergences. " \
                  "Evaluates -1 to 1 relatively to the computed divergence probability."

    EMA_SIZE = "size"
    SHORT_VALUE = "short"
    LONG_VALUE = "long"

    def __init__(self):
        super().__init__()
        self.evaluator_config = self.get_specific_config()

    async def eval_impl(self):
        self.eval_note = START_PENDING_EVAL_NOTE
        current_ema = tulipy.ema(self.data[PriceIndexes.IND_PRICE_CLOSE.value],
                                 self.get_specific_config()[self.EMA_SIZE])[-1]
        current_price_close = self.data[PriceIndexes.IND_PRICE_CLOSE.value][-1]
        diff = (current_price_close / current_ema * 100) - 100

        if diff <= self.evaluator_config[self.LONG_VALUE]:
            self.eval_note = -1
        elif diff >= self.evaluator_config[self.SHORT_VALUE]:
            self.eval_note = 1
