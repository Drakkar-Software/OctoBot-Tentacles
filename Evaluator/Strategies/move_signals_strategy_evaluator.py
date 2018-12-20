"""
OctoBot Tentacle

$tentacle_description: {
    "name": "move_signals_strategy_evaluator",
    "type": "Evaluator",
    "subtype": "Strategies",
    "version": "1.0.0",
    "requirements": ["momentum_evaluator", "trend_evaluator", "instant_fluctuations_evaluator"],
    "config_files": ["MoveSignalsStrategyEvaluator.json"],
    "tests":["test_move_signals_strategy_evaluator"]
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

from config import *
from evaluator.Strategies import MixedStrategiesEvaluator
from evaluator.TA import KlingerOscillatorMomentumEvaluator, BBMomentumEvaluator


class MoveSignalsStrategyEvaluator(MixedStrategiesEvaluator):

    SIGNAL_CLASS_NAME = KlingerOscillatorMomentumEvaluator.get_name()
    WEIGHT_CLASS_NAME = BBMomentumEvaluator.get_name()

    SHORT_PERIOD_WEIGHT = 0.40
    MEDIUM_PERIOD_WEIGHT = 0.30
    LONG_PERIOD_WEIGHT = 0.30

    SIGNAL_MINIMUM_THRESHOLD = 0.15

    DESCRIPTION = "MoveSignalsStrategyEvaluator is a fractal strategy (strategy using different time frames to " \
                  "balance decisions). It is using KlingerOscillatorMomentumEvaluator (momentum evaluator) " \
                  "to know when to start a trade and BBMomentumEvaluator (bollinger momentum evaluator) " \
                  "to know how much weight giving to this trade. Uses InstantFluctuationsEvaluator to spot " \
                  "sudden market changes within timeframes. Warning: Works only on liquid markets."

    def __init__(self):
        super().__init__()
        self.short_period_eval = SignalWithWeight(TimeFrames.THIRTY_MINUTES)    # 30min
        self.medium_period_eval = SignalWithWeight(TimeFrames.ONE_HOUR)   # 1h
        self.long_period_eval = SignalWithWeight(TimeFrames.FOUR_HOURS)     # 4h

    def eval_impl(self) -> None:
        TA_evaluations = self.matrix[EvaluatorMatrixTypes.TA]
        if self.SIGNAL_CLASS_NAME in TA_evaluations and self.WEIGHT_CLASS_NAME in TA_evaluations:
            self._refresh_evaluations(TA_evaluations)
            self._compute_final_evaluation()

    def _compute_final_evaluation(self):
        composite_evaluation = self._compute_fractal_evaluation(self.short_period_eval, self.SHORT_PERIOD_WEIGHT)
        composite_evaluation += self._compute_fractal_evaluation(self.medium_period_eval, self.MEDIUM_PERIOD_WEIGHT)
        composite_evaluation += self._compute_fractal_evaluation(self.long_period_eval, self.LONG_PERIOD_WEIGHT)
        self.eval_note = composite_evaluation

    @staticmethod
    def _compute_fractal_evaluation(signal_with_weight, multiplier):
        if signal_with_weight.signal != START_PENDING_EVAL_NOTE \
           and signal_with_weight.weight != START_PENDING_EVAL_NOTE:
            evaluation_sign = signal_with_weight.signal*signal_with_weight.weight
            if abs(signal_with_weight.signal) >= MoveSignalsStrategyEvaluator.SIGNAL_MINIMUM_THRESHOLD \
               and evaluation_sign > 0:
                eval_side = 1 if signal_with_weight.signal > 0 else -1
                signal_strenght = 2*signal_with_weight.signal*signal_with_weight.weight
                weigthed_eval = min(signal_strenght, 1)
                return weigthed_eval*multiplier*eval_side
        return 0

    def _refresh_evaluations(self, TA_evaluations):
        self.short_period_eval.refresh_evaluation(TA_evaluations)
        self.medium_period_eval.refresh_evaluation(TA_evaluations)
        self.long_period_eval.refresh_evaluation(TA_evaluations)


class SignalWithWeight:

    def __init__(self, time_frame):
        self.time_frame = time_frame
        self.signal = START_PENDING_EVAL_NOTE
        self.weight = START_PENDING_EVAL_NOTE

    def reset_evaluation(self):
        self.signal = START_PENDING_EVAL_NOTE
        self.weight = START_PENDING_EVAL_NOTE

    def refresh_evaluation(self, TA_evaluations):
        self.reset_evaluation()
        if self.time_frame in TA_evaluations[MoveSignalsStrategyEvaluator.SIGNAL_CLASS_NAME] \
           and self.time_frame in TA_evaluations[MoveSignalsStrategyEvaluator.WEIGHT_CLASS_NAME]:
            self.signal = TA_evaluations[MoveSignalsStrategyEvaluator.SIGNAL_CLASS_NAME][self.time_frame]
            self.weight = TA_evaluations[MoveSignalsStrategyEvaluator.WEIGHT_CLASS_NAME][self.time_frame]
