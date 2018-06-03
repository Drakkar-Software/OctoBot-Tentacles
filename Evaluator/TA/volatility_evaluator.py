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
