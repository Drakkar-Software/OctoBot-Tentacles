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
from octobot_commons.constants import START_PENDING_EVAL_NOTE, HOURS_TO_SECONDS
from octobot_commons.enums import TimeFrames
from octobot_commons.evaluators_util import check_valid_eval_note
from octobot_evaluators.api.matrix import get_value, get_type, get_time
from octobot_evaluators.channels.evaluator_channel import trigger_technical_evaluators_re_evaluation_with_updated_data
from octobot_evaluators.enums import EvaluatorMatrixTypes
from octobot_evaluators.errors import UnsetTentacleEvaluation
from octobot_evaluators.evaluator import StrategyEvaluator, EVALUATOR_EVAL_DEFAULT_TYPE, \
    TA_LOOP_CALLBACK
from octobot_tentacles_manager.api.configurator import get_tentacle_config
from octobot_trading.api.exchange import get_exchange_id_from_matrix_id, get_exchange_current_time, \
    get_exchange_manager_from_exchange_name_and_id


class SimpleMixedStrategyEvaluator(StrategyEvaluator):

    SOCIAL_EVALUATORS_NOTIFICATION_TIMEOUT_KEY = "social_evaluators_notification_timeout"
    RE_EVAL_TA_ON_RT_OR_SOCIAL = "re_evaluate_TA_when_social_or_realtime_notification"
    BACKGROUND_SOCIAL_EVALUATORS = "background_social_evaluators"

    def __init__(self):
        super().__init__()
        self.counter = 0
        self.evaluation = 0
        self.re_evaluation_triggering_eval_types = [EvaluatorMatrixTypes.SOCIAL.value,
                                                    EvaluatorMatrixTypes.REAL_TIME.value]
        config = get_tentacle_config(self.__class__)
        self.social_evaluators_default_timeout = config.get(
            SimpleMixedStrategyEvaluator.SOCIAL_EVALUATORS_NOTIFICATION_TIMEOUT_KEY, 1 * HOURS_TO_SECONDS)
        self.re_evaluate_TA_when_social_or_realtime_notification = config.get(
            SimpleMixedStrategyEvaluator.RE_EVAL_TA_ON_RT_OR_SOCIAL, True)
        self.background_social_evaluators = config.get(SimpleMixedStrategyEvaluator.BACKGROUND_SOCIAL_EVALUATORS, [])

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
        # TODO: find better way than this if
        if evaluator_name == self.get_name() or evaluator_type == EvaluatorMatrixTypes.TA.value:
            # avoid infinite auto callback and notifications from TA evaluators since they are handled in their
            # own callback
            return
        if symbol is None and cryptocurrency is not None and evaluator_type == EvaluatorMatrixTypes.SOCIAL.value:
            # social evaluators can by cryptocurrency related but not symbol related, wakeup every symbol
            for available_symbol in self.get_available_symbols(matrix_id, exchange_name, cryptocurrency):
                await self._trigger_evaluation(matrix_id,
                                               evaluator_name,
                                               evaluator_type,
                                               eval_note,
                                               eval_note_type,
                                               exchange_name,
                                               cryptocurrency,
                                               available_symbol,
                                               time_frame)
            return
        else:
            await self._trigger_evaluation(matrix_id,
                                           evaluator_name,
                                           evaluator_type,
                                           eval_note,
                                           eval_note_type,
                                           exchange_name,
                                           cryptocurrency,
                                           symbol,
                                           time_frame)

    async def technical_evaluators_update_loop_callback(self,
                                                        matrix_id,
                                                        update_source,
                                                        evaluator_type,
                                                        exchange_name,
                                                        cryptocurrency,
                                                        symbol,
                                                        time_frame):
        # Automatically called every time all technical evaluators have a relevant evaluation
        # Mostly called after a time-frame updates
        # To be used to trigger an evaluation
        # Do not forget to check if evaluator_name is self.name
        await self._trigger_evaluation(matrix_id,
                                       update_source,
                                       evaluator_type,
                                       None,
                                       None,
                                       exchange_name,
                                       cryptocurrency,
                                       symbol,
                                       time_frame)

    async def _trigger_evaluation(self,
                                  matrix_id,
                                  evaluator_name,
                                  evaluator_type,
                                  eval_note,
                                  eval_note_type,
                                  exchange_name,
                                  cryptocurrency,
                                  symbol,
                                  time_frame):

        # only start evaluations when technical evaluators have been initialized
        try:
            TA_by_timeframe = {
                available_time_frame: self.get_evaluations_by_evaluator(
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
            # social evaluators by symbol
            social_evaluations_by_evaluator = self.get_evaluations_by_evaluator(matrix_id,
                                                                                exchange_name,
                                                                                EvaluatorMatrixTypes.SOCIAL.value,
                                                                                cryptocurrency,
                                                                                symbol)
            # social evaluators by crypto currency
            social_evaluations_by_evaluator.update(self.get_evaluations_by_evaluator(matrix_id,
                                                                                     exchange_name,
                                                                                     EvaluatorMatrixTypes.SOCIAL.value,
                                                                                     cryptocurrency))
            available_rt_time_frames = self.get_available_time_frames(matrix_id,
                                                                      exchange_name,
                                                                      EvaluatorMatrixTypes.REAL_TIME.value,
                                                                      cryptocurrency,
                                                                      symbol)
            RT_evaluations_by_time_frame = {
                available_time_frame: self.get_evaluations_by_evaluator(
                    matrix_id,
                    exchange_name,
                    EvaluatorMatrixTypes.REAL_TIME.value,
                    cryptocurrency,
                    symbol,
                    available_time_frame)
                for available_time_frame in available_rt_time_frames
            }
            if self.re_evaluate_TA_when_social_or_realtime_notification and evaluator_name != TA_LOOP_CALLBACK \
                    and evaluator_type in self.re_evaluation_triggering_eval_types \
                    and evaluator_name not in self.background_social_evaluators:
                if check_valid_eval_note(eval_note, eval_type=eval_note_type,
                                         expected_eval_type=EVALUATOR_EVAL_DEFAULT_TYPE):
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
            self.counter = 0
            self.evaluation = 0

            for eval_by_rt in RT_evaluations_by_time_frame.values():
                for evaluation in eval_by_rt.values():
                    eval_value = get_value(evaluation)
                    if check_valid_eval_note(eval_value, eval_type=get_type(evaluation),
                                             expected_eval_type=EVALUATOR_EVAL_DEFAULT_TYPE):
                        self.evaluation += eval_value
                        self.counter += 1

            for eval_by_ta in TA_by_timeframe.values():
                for evaluation in eval_by_ta.values():
                    eval_value = get_value(evaluation)
                    if check_valid_eval_note(eval_value, eval_type=get_type(evaluation),
                                             expected_eval_type=EVALUATOR_EVAL_DEFAULT_TYPE):
                        self.evaluation += eval_value
                        self.counter += 1

            if social_evaluations_by_evaluator:
                exchange_manager = get_exchange_manager_from_exchange_name_and_id(
                    exchange_name,
                    get_exchange_id_from_matrix_id(exchange_name, self.matrix_id)
                )
                current_time = get_exchange_current_time(exchange_manager)
                for evaluation in social_evaluations_by_evaluator.values():
                    eval_value = get_value(evaluation)
                    if check_valid_eval_note(eval_value, eval_type=get_type(evaluation),
                                             expected_eval_type=EVALUATOR_EVAL_DEFAULT_TYPE,
                                             eval_time=get_time(evaluation),
                                             expiry_delay=self.social_evaluators_default_timeout,
                                             current_time=current_time):
                        self.evaluation += eval_value
                        self.counter += 1

            if self.counter > 0:
                self.eval_note = self.evaluation / self.counter
                await self.evaluation_completed(cryptocurrency, symbol)

        except UnsetTentacleEvaluation as e:
            if evaluator_name == TA_LOOP_CALLBACK:
                self.logger.error(f"Missing technical evaluator data for ({e})")
            # otherwise it's a social or real-time evaluator, it will shortly be taken into account by TA update cycle
        except Exception as e:
            self.logger.exception(e, True, f"Error when computing strategy evaluation: {e}")


class FullMixedStrategiesEvaluator(StrategyEvaluator):

    def __init__(self):
        super().__init__()
        self.social_counter = 0
        self.ta_relevance_counter = 0
        self.rt_counter = 0

        self.ta_evaluation = 0
        self.social_evaluation = 0
        self.rt_evaluation = 0
        self.divergence_evaluation = 0

    async def matrix_callback(self,
                              matrix_id,
                              evaluator_name,
                              evaluator_type,
                              eval_note,
                              eval_note_type,
                              eval_time,
                              exchange_name,
                              cryptocurrency,
                              symbol,
                              time_frame):
        # TODO: find better way than this if
        if evaluator_name == self.get_name():
            # avoid infinite auto callback
            return
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
                                     self.evaluator_types_matrix.get_evaluator_eval_type(rt),
                                     EVALUATOR_EVAL_DEFAULT_TYPE):
                self.rt_evaluation += self.matrix[EvaluatorMatrixTypes.REAL_TIME][rt]
                self.rt_counter += 1

        for ta in self.matrix[EvaluatorMatrixTypes.TA]:
            if self.matrix[EvaluatorMatrixTypes.TA][ta]:
                for ta_time_frame in self.matrix[EvaluatorMatrixTypes.TA][ta]:
                    if check_valid_eval_note(self.matrix[EvaluatorMatrixTypes.TA][ta][ta_time_frame],
                                             self.evaluator_types_matrix.get_evaluator_eval_type(ta),
                                             EVALUATOR_EVAL_DEFAULT_TYPE):
                        time_frame_relevance = FullMixedStrategiesEvaluator.TimeFramesRelevance[ta_time_frame]
                        self.ta_evaluation += self.matrix[EvaluatorMatrixTypes.TA][ta][ta_time_frame] \
                            * time_frame_relevance
                        self.ta_relevance_counter += time_frame_relevance

        for social in self.matrix[EvaluatorMatrixTypes.SOCIAL]:
            eval_note = self.matrix[EvaluatorMatrixTypes.SOCIAL][social]
            if check_valid_eval_note(eval_note,
                                     self.evaluator_types_matrix.get_evaluator_eval_type(social),
                                     EVALUATOR_EVAL_DEFAULT_TYPE):
                self.social_evaluation += eval_note
                self.social_counter += 1

        await self.finalize(cryptocurrency, symbol)

    async def finalize(self, cryptocurrency, symbol):
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
            self.eval_note = -1
            await self.evaluation_completed(cryptocurrency, symbol)

    TimeFramesRelevance = {
        TimeFrames.ONE_MINUTE: 5,
        TimeFrames.THREE_MINUTES: 5,
        TimeFrames.FIVE_MINUTES: 5,
        TimeFrames.FIFTEEN_MINUTES: 15,
        TimeFrames.THIRTY_MINUTES: 30,
        TimeFrames.ONE_HOUR: 50,
        TimeFrames.TWO_HOURS: 50,
        TimeFrames.FOUR_HOURS: 50,
        TimeFrames.HEIGHT_HOURS: 30,
        TimeFrames.TWELVE_HOURS: 30,
        TimeFrames.ONE_DAY: 30,
        TimeFrames.THREE_DAYS: 15,
        TimeFrames.ONE_WEEK: 15,
        TimeFrames.ONE_MONTH: 5,
    }
