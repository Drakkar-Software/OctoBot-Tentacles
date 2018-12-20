"""
OctoBot Tentacle

$tentacle_description: {
    "name": "volatility_evaluator",
    "type": "Evaluator",
    "subtype": "TA",
    "version": "1.0.0",
    "requirements": []
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

from evaluator.TA.TA_evaluator import VolatilityEvaluator


# average_true_range
class ATRVolatilityEvaluator(VolatilityEvaluator):

    def eval_impl(self):
        pass


# mass index
class MassIndexVolatilityEvaluator(VolatilityEvaluator):

    def eval_impl(self):
        pass


class ChaikinVolatilityEvaluator(VolatilityEvaluator):

    def eval_impl(self):
        pass


class StochasticVolatilityEvaluator(VolatilityEvaluator):
    def __init__(self):
        super().__init__()

    def eval_impl(self):
        # slowk, slowd = talib.STOCH(self.data[PriceStrings.STR_PRICE_HIGH.value],
        #                            self.data[PriceStrings.STR_PRICE_LOW.value],
        #                            self.data[PriceStrings.STR_PRICE_CLOSE.value])
        pass


class StochasticRSIVolatilityEvaluator(VolatilityEvaluator):
    def __init__(self):
        super().__init__()

    def eval_impl(self):
        # fastk, fastd = talib.STOCHRSI(self.data[PriceStrings.STR_PRICE_CLOSE.value])
        pass
