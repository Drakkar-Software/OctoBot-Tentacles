"""
OctoBot Tentacle

$tentacle_description: {
    "name": "mixed_strategies_evaluator",
    "type": "Evaluator",
    "subtype": "Strategies",
    "version": "1.1.1",
    "requirements": ["instant_fluctuations_evaluator", "news_evaluator"],
    "config_files": ["FullMixedStrategiesEvaluator.json", "InstantSocialReactionMixedStrategiesEvaluator.json", "SimpleMixedStrategiesEvaluator.json"],
    "config_schema_files": ["FullMixedStrategiesEvaluator_schema.json", "SimpleMixedStrategiesEvaluator_schema.json"],
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

from config import EvaluatorMatrixTypes, TimeFramesRelevance
from evaluator.Strategies import MixedStrategiesEvaluator
from tentacles.Evaluator.RealTime import InstantFluctuationsEvaluator
from tentacles.Evaluator.Social import RedditForumEvaluator
from tools.evaluators_util import check_valid_eval_note


class FullMixedStrategiesEvaluator(MixedStrategiesEvaluator):
    DESCRIPTION = "FullMixedStrategiesEvaluator a flexible strategy. Meant to be customized, it is using " \
                  "every activated technical evaluator and averages the evaluation notes of " \
                  "each to compute its final evaluation. This strategy can be used to make simple trading strategies " \
                  "using for example only one evaluator or more complex ones using a multi-evaluator setup. " \
                  "FullMixedStrategiesEvaluator can also handle InstantFluctuationsEvaluator and " \
                  "RedditForumEvaluator if activated." \
                  "This strategy is similar to SimpleMixedStrategiesEvaluator except for the detail that it assigns " \
                  "weights to time frames in order to try to make the final evaluation more accurate. " \
                  "Used time frames are 30m, 1h, 2h, 4h and 1d. " \
                  "Warning: this strategy only considers evaluators computing evaluations between -1 and 1."

    def __init__(self):
        super().__init__()
        self.create_divergence_analyser()
        self.social_counter = 0
        self.ta_relevance_counter = 0
        self.rt_counter = 0

        self.ta_evaluation = 0
        self.social_evaluation = 0
        self.rt_evaluation = 0
        self.divergence_evaluation = 0

    def inc_social_counter(self, inc=1):
        self.social_counter += inc

    def inc_ta_counter(self, inc=1):
        self.ta_relevance_counter += inc

    def inc_rt_counter(self, inc=1):
        self.rt_counter += inc

    def set_matrix(self, matrix):
        super().set_matrix(matrix)

        # TODO temp with notification
        # self.get_divergence()

    async def eval_impl(self) -> None:
        # TODO : temp counter without relevance
        self.social_counter = 0
        self.rt_counter = 0

        # relevance counters
        self.ta_relevance_counter = 0

        # eval note total with relevance factor
        self.ta_evaluation = 0
        self.social_evaluation = 0
        self.rt_evaluation = 0

        # example
        # if RSIMomentumEvaluator.get_name() in self.matrix[EvaluatorMatrixTypes.TA]:
        #     self.divergence_evaluation = self.divergence_evaluator_analyser.calc_evaluator_divergence(
        #         EvaluatorMatrixTypes.TA,
        #         RSIMomentumEvaluator.get_name())

        for rt in self.matrix[EvaluatorMatrixTypes.REAL_TIME]:
            if check_valid_eval_note(self.matrix[EvaluatorMatrixTypes.REAL_TIME][rt],
                                     self.evaluator_types_matrix.get_evaluator_eval_type(rt)):
                self.rt_evaluation += self.matrix[EvaluatorMatrixTypes.REAL_TIME][rt]
                self.inc_rt_counter()

        for ta in self.matrix[EvaluatorMatrixTypes.TA]:
            if self.matrix[EvaluatorMatrixTypes.TA][ta]:
                for ta_time_frame in self.matrix[EvaluatorMatrixTypes.TA][ta]:
                    if check_valid_eval_note(self.matrix[EvaluatorMatrixTypes.TA][ta][ta_time_frame],
                                             self.evaluator_types_matrix.get_evaluator_eval_type(ta)):
                        time_frame_relevance = TimeFramesRelevance[ta_time_frame]
                        self.ta_evaluation += self.matrix[EvaluatorMatrixTypes.TA][ta][
                                                  ta_time_frame] * time_frame_relevance
                        self.inc_ta_counter(time_frame_relevance)

        for social in self.matrix[EvaluatorMatrixTypes.SOCIAL]:
            eval_note = self.matrix[EvaluatorMatrixTypes.SOCIAL][social]
            if check_valid_eval_note(eval_note, self.evaluator_types_matrix.get_evaluator_eval_type(social)):
                self.social_evaluation += eval_note
                self.inc_social_counter()

        self.finalize()

    def finalize(self):
        # TODO : This is an example
        eval_temp = 0
        category = 0

        if self.ta_relevance_counter > 0:
            eval_temp += self.ta_evaluation / self.ta_relevance_counter
            category += 1

        if self.social_counter > 0:
            eval_temp += self.social_evaluation / self.social_counter
            category += 1

        if self.rt_counter > 0:
            eval_temp += self.rt_evaluation / self.rt_counter
            category += 1

        if category > 0:
            self.eval_note = eval_temp / category


class InstantSocialReactionMixedStrategiesEvaluator(MixedStrategiesEvaluator):
    def __init__(self):
        super().__init__()
        self.social_counter = 0
        self.instant_counter = 0

        self.instant_evaluation = 0
        self.social_evaluation = 0

    async def eval_impl(self) -> None:
        self.social_counter = 0
        self.instant_counter = 0

        self.instant_evaluation = 0
        self.social_evaluation = 0

        # TODO : This is an example
        if InstantFluctuationsEvaluator.get_name() in self.matrix[EvaluatorMatrixTypes.REAL_TIME]:
            if check_valid_eval_note(self.matrix[EvaluatorMatrixTypes.REAL_TIME][
                                         InstantFluctuationsEvaluator.get_name()],
                                     self.evaluator_types_matrix.get_evaluator_eval_type(
                                         InstantFluctuationsEvaluator.get_name())):
                self.instant_evaluation += self.matrix[EvaluatorMatrixTypes.REAL_TIME][
                    InstantFluctuationsEvaluator.get_name()]
                self.inc_instant_counter()

        if RedditForumEvaluator.get_name() in self.matrix[EvaluatorMatrixTypes.SOCIAL]:
            if check_valid_eval_note(self.matrix[EvaluatorMatrixTypes.SOCIAL][
                                         RedditForumEvaluator.get_name()],
                                     self.evaluator_types_matrix.get_evaluator_eval_type(
                                         RedditForumEvaluator.get_name())):
                self.social_evaluation += \
                    self.matrix[EvaluatorMatrixTypes.SOCIAL][RedditForumEvaluator.get_name()]
                self.inc_social_counter()

        self.finalize()

    def inc_social_counter(self, inc=1):
        self.social_counter += inc

    def inc_instant_counter(self, inc=1):
        self.instant_counter += inc

    def finalize(self):
        # TODO : This is an example
        eval_temp = 0
        category = 0

        if self.instant_counter > 0:
            eval_temp += self.instant_evaluation / self.instant_counter
            category += 1

        if self.social_counter > 0:
            eval_temp += self.social_evaluation / self.social_counter
            category += 1

        if category > 0:
            self.eval_note = eval_temp / category


class SimpleMixedStrategiesEvaluator(MixedStrategiesEvaluator):
    DESCRIPTION = "SimpleMixedStrategiesEvaluator is the most flexible strategy. Meant to be customized, it is using " \
                  "every activated technical, social and real time evaluator, and averages the evaluation notes of " \
                  "each to compute its final evaluation. This strategy can be used to make simple trading strategies " \
                  "using for example only one evaluator or more complex ones using a multi-evaluator setup. " \
                  "Used time frames are 1h, 4h and 1d. " \
                  "Warning: this strategy only considers evaluators computing evaluations between -1 and 1."

    def __init__(self):
        super().__init__()
        self.create_divergence_analyser()
        self.counter = 0
        self.evaluation = 0

    def set_matrix(self, matrix):
        super().set_matrix(matrix)

        # TODO temp with notification
        # self.get_divergence()

    async def eval_impl(self) -> None:
        self.counter = 0
        self.evaluation = 0

        for rt in self.matrix[EvaluatorMatrixTypes.REAL_TIME]:
            if check_valid_eval_note(self.matrix[EvaluatorMatrixTypes.REAL_TIME][rt],
                                     self.evaluator_types_matrix.get_evaluator_eval_type(rt)):
                self.evaluation += self.matrix[EvaluatorMatrixTypes.REAL_TIME][rt]
                self.counter += 1

        for ta in self.matrix[EvaluatorMatrixTypes.TA]:
            if self.matrix[EvaluatorMatrixTypes.TA][ta]:
                for ta_time_frame in self.matrix[EvaluatorMatrixTypes.TA][ta]:
                    if check_valid_eval_note(self.matrix[EvaluatorMatrixTypes.TA][ta][ta_time_frame],
                                             self.evaluator_types_matrix.get_evaluator_eval_type(ta)):
                        self.evaluation += self.matrix[EvaluatorMatrixTypes.TA][ta][ta_time_frame]
                        self.counter += 1

        for social in self.matrix[EvaluatorMatrixTypes.SOCIAL]:
            if check_valid_eval_note(self.matrix[EvaluatorMatrixTypes.SOCIAL][social],
                                     self.evaluator_types_matrix.get_evaluator_eval_type(social)):
                self.evaluation += self.matrix[EvaluatorMatrixTypes.SOCIAL][social]
                self.counter += 1

        self.finalize()

    def finalize(self):
        if self.counter > 0:
            self.eval_note = self.evaluation / self.counter
