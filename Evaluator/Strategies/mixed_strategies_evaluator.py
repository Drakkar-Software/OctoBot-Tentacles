"""
OctoBot Tentacle

$tentacle_description: {
    "package_name": "OctoBot-Tentacles",
    "name": "mixed_strategies_evaluator",
    "type": "Evaluator",
    "subtype": "Strategies",
    "version": "1.1.1",
    "requirements": ["instant_fluctuations_evaluator", "news_evaluator"],
    "config_files": ["FullMixedStrategiesEvaluator.json", "InstantSocialReactionMixedStrategiesEvaluator.json", "SimpleMixedStrategyEvaluator.json"],
    "config_schema_files": ["FullMixedStrategiesEvaluator_schema.json", "SimpleMixedStrategyEvaluator_schema.json"],
    "tests":["test_simple_mixed_strategies_evaluator", "test_full_mixed_strategies_evaluator"]
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
from octobot_commons.evaluators_util import check_valid_eval_note
from octobot_evaluators.enums import EvaluatorMatrixTypes
from octobot_evaluators.evaluator import StrategyEvaluator


class SimpleMixedStrategyEvaluator(StrategyEvaluator):
    DESCRIPTION = "SimpleMixedStrategyEvaluator is the most flexible strategy. Meant to be customized, it is using " \
                  "every activated technical, social and real time evaluator, and averages the evaluation notes of " \
                  "each to compute its final evaluation.\nThis strategy can be used to make simple trading strategies " \
                  "using for example only one evaluator or more complex ones using a multi-evaluator setup.\n" \
                  "Used time frames are 1h, 4h and 1d.\n" \
                  "Warning: this strategy only considers evaluators computing evaluations between -1 and 1."

    def __init__(self):
        super().__init__()
        self.counter = 0
        self.evaluation = 0

    async def matrix_callback(self,
                              evaluator_name,
                              evaluator_type,
                              eval_note,
                              exchange_name,
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
            await self.evaluation_completed(symbol, time_frame)

    def finalize(self):
        if self.counter > 0:
            self.eval_note = self.evaluation / self.counter
