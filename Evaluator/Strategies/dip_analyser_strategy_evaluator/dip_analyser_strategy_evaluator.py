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
from typing import Dict

from octobot_commons.enums import TimeFrames
from octobot_evaluators.api.matrix import get_value
from octobot_evaluators.channels.evaluator_channel import trigger_technical_evaluators_re_evaluation_with_updated_data
from octobot_evaluators.constants import STRATEGIES_REQUIRED_TIME_FRAME
from octobot_evaluators.data_manager.matrix_manager import get_evaluations_by_evaluator
from octobot_evaluators.enums import EvaluatorMatrixTypes
from octobot_evaluators.evaluator import StrategyEvaluator, START_PENDING_EVAL_NOTE
from octobot_tentacles_manager.api.configurator import get_tentacle_config
from octobot_trading.api.exchange import get_exchange_id_from_matrix_id
from tentacles.Evaluator.TA import RSIWeightMomentumEvaluator, KlingerOscillatorReversalConfirmationMomentumEvaluator


class DipAnalyserStrategyEvaluator(StrategyEvaluator):
    REVERSAL_CONFIRMATION_CLASS_NAME = KlingerOscillatorReversalConfirmationMomentumEvaluator.get_name()
    REVERSAL_WEIGHT_CLASS_NAME = RSIWeightMomentumEvaluator.get_name()

    @staticmethod
    def get_eval_type():
        return Dict[str, int]

    def __init__(self):
        super().__init__()
        self.evaluation_time_frame = \
            TimeFrames(get_tentacle_config(self.__class__)[STRATEGIES_REQUIRED_TIME_FRAME][0]).value

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
            self.eval_note = START_PENDING_EVAL_NOTE
            TA_evaluations = get_evaluations_by_evaluator(matrix_id,
                                                          exchange_name,
                                                          EvaluatorMatrixTypes.TA.value,
                                                          cryptocurrency,
                                                          symbol,
                                                          self.evaluation_time_frame,
                                                          allowed_values=[START_PENDING_EVAL_NOTE])

            try:
                if get_value(TA_evaluations[self.REVERSAL_CONFIRMATION_CLASS_NAME]):
                    self.eval_note = get_value(TA_evaluations[self.REVERSAL_WEIGHT_CLASS_NAME])
                await self.evaluation_completed(cryptocurrency, symbol)
            except KeyError as e:
                self.logger.error(f"Missing required evaluator: {e}")

