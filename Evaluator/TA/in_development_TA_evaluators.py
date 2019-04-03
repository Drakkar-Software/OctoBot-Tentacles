"""
OctoBot Tentacle

$tentacle_description: {
    "name": "in_development_TA_evaluators",
    "type": "Evaluator",
    "subtype": "TA",
    "version": "1.1.0",
    "requirements": [],
    "tests":[],
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


from evaluator.TA.TA_evaluator import MomentumEvaluator, TrendEvaluator, VolatilityEvaluator


class OBVMomentumEvaluator(MomentumEvaluator):

    async def eval_impl(self):
        # obv_v = talib.OBV(self.data[PriceStrings.STR_PRICE_CLOSE.value],
        #                   self.data[PriceStrings.STR_PRICE_VOL.value])
        pass


# William's % R --> overbought / oversold
class WilliamsRMomentumEvaluator(MomentumEvaluator):

    async def eval_impl(self):
        # willr_v = talib.WILLR(self.data[PriceStrings.STR_PRICE_HIGH.value],
        #                       self.data[PriceStrings.STR_PRICE_LOW.value],
        #                       self.data[PriceStrings.STR_PRICE_CLOSE.value])
        pass


# TRIX --> percent rate-of-change trend
class TRIXMomentumEvaluator(MomentumEvaluator):

    async def eval_impl(self):
        # trix_v = talib.TRIX(self.data[PriceStrings.STR_PRICE_CLOSE.value])
        pass


class ChaikinOscillatorMomentumEvaluator(MomentumEvaluator):

    async def eval_impl(self):
        pass


# https://mrjbq7.github.io/ta-lib/func_groups/overlap_studies.html
class CandleAnalysisTrendEvaluator(TrendEvaluator):

    async def eval_impl(self):
        pass


# directional_movement_index --> trend strength
class DMITrendEvaluator(TrendEvaluator):

    async def eval_impl(self):
        pass


# bollinger_bands
class BBTrendEvaluator(TrendEvaluator):

    async def eval_impl(self):
        pass


# ease_of_movement --> ease to change trend --> trend strength
class EOMTrendEvaluator(TrendEvaluator):

    async def eval_impl(self):
        pass


# average_true_range
class ATRVolatilityEvaluator(VolatilityEvaluator):

    async def eval_impl(self):
        pass


# mass index
class MassIndexVolatilityEvaluator(VolatilityEvaluator):

    async def eval_impl(self):
        pass


class ChaikinVolatilityEvaluator(VolatilityEvaluator):

    async def eval_impl(self):
        pass


class StochasticVolatilityEvaluator(VolatilityEvaluator):

    async def eval_impl(self):
        # slowk, slowd = talib.STOCH(self.data[PriceStrings.STR_PRICE_HIGH.value],
        #                            self.data[PriceStrings.STR_PRICE_LOW.value],
        #                            self.data[PriceStrings.STR_PRICE_CLOSE.value])
        pass
