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

from evaluator.TA.TA_evaluator import VolatilityEvaluator

import talib


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
