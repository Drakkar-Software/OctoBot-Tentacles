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

from octobot_commons.enums import TimeFrames
from octobot_evaluators.api.matrix import get_value
from octobot_evaluators.channels.evaluator_channel import trigger_technical_evaluators_re_evaluation_with_updated_data
from octobot_evaluators.data_manager.matrix_manager import get_evaluations_by_evaluator
from octobot_evaluators.enums import EvaluatorMatrixTypes
from octobot_evaluators.errors import UnsetTentacleEvaluation
from octobot_evaluators.evaluator import StrategyEvaluator, START_PENDING_EVAL_NOTE
from octobot_trading.api.exchange import get_exchange_id_from_matrix_id
from tentacles.Evaluator.TA import KlingerOscillatorMomentumEvaluator, BBMomentumEvaluator


class MoveSignalsStrategyEvaluator(StrategyEvaluator):

    SIGNAL_CLASS_NAME = KlingerOscillatorMomentumEvaluator.get_name()
    WEIGHT_CLASS_NAME = BBMomentumEvaluator.get_name()

    SHORT_PERIOD_WEIGHT = 0.40
    MEDIUM_PERIOD_WEIGHT = 0.30
    LONG_PERIOD_WEIGHT = 0.30

    SIGNAL_MINIMUM_THRESHOLD = 0.15

    def __init__(self):
        super().__init__()
        self.evaluation_time_frames = [TimeFrames.THIRTY_MINUTES.value,
                                       TimeFrames.ONE_HOUR.value,
                                       TimeFrames.FOUR_HOURS.value]
        self.short_period_eval = SignalWithWeight(TimeFrames.THIRTY_MINUTES)    # 30min
        self.medium_period_eval = SignalWithWeight(TimeFrames.ONE_HOUR)   # 1h
        self.long_period_eval = SignalWithWeight(TimeFrames.FOUR_HOURS)     # 4h

    async def matrix_callback(self,
                              matrix_id,
                              evaluator_name,
                              evaluator_type,
                              eval_note,
                              eval_note_type,
                              exchange_name,
                              cryptocurrency,
                              symbol,
                              time_frame):
        if evaluator_type == EvaluatorMatrixTypes.REAL_TIME.value:
            # trigger re-evaluation
            exchange_id = get_exchange_id_from_matrix_id(exchange_name, matrix_id)
            await trigger_technical_evaluators_re_evaluation_with_updated_data(matrix_id,
                                                                               evaluator_name,
                                                                               evaluator_type,
                                                                               exchange_name,
                                                                               cryptocurrency,
                                                                               symbol,
                                                                               exchange_id,
                                                                               self.strategy_time_frames)
            # do not continue this evaluation
            return
        elif evaluator_type == EvaluatorMatrixTypes.TA.value:
            try:
                TA_by_timeframe = {
                    available_time_frame: get_evaluations_by_evaluator(
                        matrix_id,
                        exchange_name,
                        EvaluatorMatrixTypes.TA.value,
                        cryptocurrency,
                        symbol,
                        available_time_frame.value,
                        allow_missing=False,
                        allowed_values=[START_PENDING_EVAL_NOTE])
                    for available_time_frame in self.strategy_time_frames
                }

                self._refresh_evaluations(TA_by_timeframe)
                self._compute_final_evaluation()
                await self.strategy_completed(cryptocurrency, symbol)

            except UnsetTentacleEvaluation as e:
                self.logger.debug(f"Tentacles evaluation initialization: not ready yet for a strategy update ({e})")
            except KeyError as e:
                self.logger.error(f"Missing {e} evaluation in matrix, did you activate the required evaluator ?")

    def _compute_final_evaluation(self):
        composite_evaluation = self._compute_fractal_evaluation(self.short_period_eval, self.SHORT_PERIOD_WEIGHT)
        composite_evaluation += self._compute_fractal_evaluation(self.medium_period_eval, self.MEDIUM_PERIOD_WEIGHT)
        composite_evaluation += self._compute_fractal_evaluation(self.long_period_eval, self.LONG_PERIOD_WEIGHT)
        self.eval_note = composite_evaluation

    @staticmethod
    def _compute_fractal_evaluation(signal_with_weight, multiplier):
        if signal_with_weight.signal != START_PENDING_EVAL_NOTE \
           and signal_with_weight.weight != START_PENDING_EVAL_NOTE:
            evaluation_sign = signal_with_weight.signal * signal_with_weight.weight
            if abs(signal_with_weight.signal) >= MoveSignalsStrategyEvaluator.SIGNAL_MINIMUM_THRESHOLD \
               and evaluation_sign > 0:
                eval_side = 1 if signal_with_weight.signal > 0 else -1
                signal_strength = 2 * signal_with_weight.signal * signal_with_weight.weight
                weighted_eval = min(signal_strength, 1)
                return weighted_eval * multiplier * eval_side
        return 0

    def _refresh_evaluations(self, TA_by_timeframe):
        self.short_period_eval.refresh_evaluation(TA_by_timeframe)
        self.medium_period_eval.refresh_evaluation(TA_by_timeframe)
        self.long_period_eval.refresh_evaluation(TA_by_timeframe)


class SignalWithWeight:

    def __init__(self, time_frame):
        self.time_frame = time_frame
        self.signal = START_PENDING_EVAL_NOTE
        self.weight = START_PENDING_EVAL_NOTE

    def reset_evaluation(self):
        self.signal = START_PENDING_EVAL_NOTE
        self.weight = START_PENDING_EVAL_NOTE

    def refresh_evaluation(self, TA_by_timeframe):
        self.reset_evaluation()
        self.signal = get_value(TA_by_timeframe[self.time_frame][MoveSignalsStrategyEvaluator.SIGNAL_CLASS_NAME])
        self.weight = get_value(TA_by_timeframe[self.time_frame][MoveSignalsStrategyEvaluator.WEIGHT_CLASS_NAME])
