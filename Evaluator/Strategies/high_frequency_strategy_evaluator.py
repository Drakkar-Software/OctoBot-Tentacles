"""
OctoBot Tentacle

$tentacle_description: {
    "name": "high_frequency_strategy_evaluator",
    "type": "Evaluator",
    "subtype": "Strategies",
    "version": "1.0.0",
    "requirements": ["instant_fluctuations_evaluator"]
}
"""
from config.cst import TimeFrames, EvaluatorMatrixTypes

from evaluator.Strategies import MixedStrategiesEvaluator
from tentacles.Evaluator.RealTime import InstantMAEvaluator


# WARNING : THIS STRATEGY MUST BE USED WITH A WEBSOCKET
class HighFrequencyStrategiesEvaluator(MixedStrategiesEvaluator):
    def __init__(self):
        super().__init__()

    def eval_impl(self) -> None:
        matrix_note = self.matrix[EvaluatorMatrixTypes.REAL_TIME][InstantMAEvaluator.get_name()]
        self.eval_note = matrix_note

    @classmethod
    def get_required_time_frames(cls):
        return [TimeFrames.FIVE_MINUTES]

    @classmethod
    def get_required_evaluators(cls):
        return [InstantMAEvaluator.get_name()]
