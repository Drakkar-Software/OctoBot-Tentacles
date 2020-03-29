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
from octobot_commons.evaluators_util import check_valid_eval_note
from octobot_evaluators.enums import EvaluatorMatrixTypes
from octobot_evaluators.evaluator import StrategyEvaluator


class SimpleMixedStrategyEvaluator(StrategyEvaluator):

    def __init__(self):
        super().__init__()
        self.counter = 0
        self.evaluation = 0

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
        self.counter = 0
        self.evaluation = 0

        # for rt in self.matrix[EvaluatorMatrixTypes.REAL_TIME]:
        #     if check_valid_eval_note(self.matrix[EvaluatorMatrixTypes.REAL_TIME][rt],
        #                              self.evaluator_types_matrix.get_evaluator_eval_type(rt)):
        #         self.evaluation += self.matrix[EvaluatorMatrixTypes.REAL_TIME][rt]
        #         self.counter += 1
        #
        # for ta in self.matrix[EvaluatorMatrixTypes.TA]:
        #     if self.matrix[EvaluatorMatrixTypes.TA][ta]:
        #         for ta_time_frame in self.matrix[EvaluatorMatrixTypes.TA][ta]:
        #             if check_valid_eval_note(self.matrix[EvaluatorMatrixTypes.TA][ta][ta_time_frame],
        #                                      self.evaluator_types_matrix.get_evaluator_eval_type(ta)):
        #                 self.evaluation += self.matrix[EvaluatorMatrixTypes.TA][ta][ta_time_frame]
        #                 self.counter += 1
        #
        # for social in self.matrix[EvaluatorMatrixTypes.SOCIAL]:
        #     if check_valid_eval_note(self.matrix[EvaluatorMatrixTypes.SOCIAL][social],
        #                              self.evaluator_types_matrix.get_evaluator_eval_type(social)):
        #         self.evaluation += self.matrix[EvaluatorMatrixTypes.SOCIAL][social]
        #         self.counter += 1

        self.finalize()

        # TODO temp
        if evaluator_name != self.get_name():
            await self.evaluation_completed(cryptocurrency, symbol, time_frame)

    def finalize(self):
        if self.counter > 0:
            self.eval_note = self.evaluation / self.counter
