"""
OctoBot Tentacle

$tentacle_description: {
    "name": "dip_analyser_strategy_evaluator",
    "type": "Evaluator",
    "subtype": "Strategies",
    "version": "1.1.1",
    "requirements": ["momentum_evaluator", "instant_fluctuations_evaluator"],
    "config_files": ["DipAnalyserStrategyEvaluator.json"],
    "config_schema_files": ["DipAnalyserStrategyEvaluator_schema.json"],
    "tests":["test_dip_analyser_strategy_evaluator"]
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

from typing import Dict

from config import START_PENDING_EVAL_NOTE, EvaluatorMatrixTypes, TimeFrames, STRATEGIES_REQUIRED_TIME_FRAME
from evaluator.Strategies import MixedStrategiesEvaluator
from evaluator.TA import RSIWeightMomentumEvaluator, KlingerOscillatorReversalConfirmationMomentumEvaluator


class DipAnalyserStrategyEvaluator(MixedStrategiesEvaluator):
    REVERSAL_CONFIRMATION_CLASS_NAME = KlingerOscillatorReversalConfirmationMomentumEvaluator.get_name()
    REVERSAL_WEIGHT_CLASS_NAME = RSIWeightMomentumEvaluator.get_name()

    DESCRIPTION = "DipAnalyserStrategyEvaluator is a strategy analysing market dips using RSI averages and Klinger " \
                  "oscillator for confirmations. It focuses on the one time frame only."

    @staticmethod
    def get_eval_type():
        return Dict[str, int]

    def __init__(self):
        super().__init__()
        self.time_frame = TimeFrames(self.get_specific_config()[STRATEGIES_REQUIRED_TIME_FRAME][0])

    async def eval_impl(self) -> None:
        self.eval_note = START_PENDING_EVAL_NOTE
        try:
            TA_evaluations = self.matrix[EvaluatorMatrixTypes.TA]
            if TA_evaluations[self.REVERSAL_CONFIRMATION_CLASS_NAME][self.time_frame]:
                self.eval_note = TA_evaluations[self.REVERSAL_WEIGHT_CLASS_NAME][self.time_frame]
        except KeyError:
            self.eval_note = START_PENDING_EVAL_NOTE
