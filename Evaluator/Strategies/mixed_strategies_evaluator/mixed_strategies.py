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
import octobot_commons.constants as commons_constants
import octobot_commons.evaluators_util as evaluators_util
import octobot_commons.time_frame_manager as time_frame_manager
import octobot_evaluators.api as evaluators_api
import octobot_evaluators.evaluators.channel as evaluators_channel
import octobot_evaluators.matrix as matrix
import octobot_evaluators.enums as evaluators_enums
import octobot_evaluators.constants as evaluators_constants
import octobot_evaluators.errors as errors
import octobot_evaluators.evaluators as evaluators
import octobot_tentacles_manager.api.configurator as tentacles_manager_api
import octobot_trading.api as trading_api


class SimpleStrategyEvaluator(evaluators.StrategyEvaluator):
    SOCIAL_EVALUATORS_NOTIFICATION_TIMEOUT_KEY = "social_evaluators_notification_timeout"
    RE_EVAL_TA_ON_RT_OR_SOCIAL = "re_evaluate_TA_when_social_or_realtime_notification"
    BACKGROUND_SOCIAL_EVALUATORS = "background_social_evaluators"

    def __init__(self):
        super().__init__()
        self.re_evaluation_triggering_eval_types = [evaluators_enums.EvaluatorMatrixTypes.SOCIAL.value,
                                                    evaluators_enums.EvaluatorMatrixTypes.REAL_TIME.value]
        config = tentacles_manager_api.get_tentacle_config(self.__class__)
        self.social_evaluators_default_timeout = config.get(
            SimpleStrategyEvaluator.SOCIAL_EVALUATORS_NOTIFICATION_TIMEOUT_KEY, 1 * commons_constants.HOURS_TO_SECONDS)
        self.re_evaluate_TA_when_social_or_realtime_notification = config.get(
            SimpleStrategyEvaluator.RE_EVAL_TA_ON_RT_OR_SOCIAL, True)
        self.background_social_evaluators = config.get(SimpleStrategyEvaluator.BACKGROUND_SOCIAL_EVALUATORS, [])

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
        if symbol is None and cryptocurrency is not None and evaluator_type == evaluators_enums.EvaluatorMatrixTypes.SOCIAL.value:
            # social evaluators can be cryptocurrency related but not symbol related, wakeup every symbol
            for available_symbol in matrix.get_available_symbols(matrix_id, exchange_name, cryptocurrency):
                await self._trigger_evaluation(matrix_id,
                                               evaluator_name,
                                               evaluator_type,
                                               eval_note,
                                               eval_note_type,
                                               exchange_name,
                                               cryptocurrency,
                                               available_symbol)
            return
        else:
            await self._trigger_evaluation(matrix_id,
                                           evaluator_name,
                                           evaluator_type,
                                           eval_note,
                                           eval_note_type,
                                           exchange_name,
                                           cryptocurrency,
                                           symbol)

    async def _trigger_evaluation(self,
                                  matrix_id,
                                  evaluator_name,
                                  evaluator_type,
                                  eval_note,
                                  eval_note_type,
                                  exchange_name,
                                  cryptocurrency,
                                  symbol):
        # ensure only start evaluations when technical evaluators have been initialized
        try:
            TA_by_timeframe = {
                available_time_frame: matrix.get_evaluations_by_evaluator(
                    matrix_id,
                    exchange_name,
                    evaluators_enums.EvaluatorMatrixTypes.TA.value,
                    cryptocurrency,
                    symbol,
                    available_time_frame.value,
                    allow_missing=False,
                    allowed_values=[commons_constants.START_PENDING_EVAL_NOTE])
                for available_time_frame in self.strategy_time_frames
            }
            # social evaluators by symbol
            social_evaluations_by_evaluator = matrix.get_evaluations_by_evaluator(matrix_id,
                                                                                  exchange_name,
                                                                                  evaluators_enums.EvaluatorMatrixTypes.SOCIAL.value,
                                                                                  cryptocurrency,
                                                                                  symbol)
            # social evaluators by crypto currency
            social_evaluations_by_evaluator.update(matrix.get_evaluations_by_evaluator(matrix_id,
                                                                                       exchange_name,
                                                                                       evaluators_enums.EvaluatorMatrixTypes.SOCIAL.value,
                                                                                       cryptocurrency))
            available_rt_time_frames = self.get_available_time_frames(matrix_id,
                                                                      exchange_name,
                                                                      evaluators_enums.EvaluatorMatrixTypes.REAL_TIME.value,
                                                                      cryptocurrency,
                                                                      symbol)
            RT_evaluations_by_time_frame = {
                available_time_frame: matrix.get_evaluations_by_evaluator(
                    matrix_id,
                    exchange_name,
                    evaluators_enums.EvaluatorMatrixTypes.REAL_TIME.value,
                    cryptocurrency,
                    symbol,
                    available_time_frame)
                for available_time_frame in available_rt_time_frames
            }
            if self.re_evaluate_TA_when_social_or_realtime_notification \
                    and any(value for value in TA_by_timeframe.values()) \
                    and evaluator_type != evaluators_enums.EvaluatorMatrixTypes.TA.value \
                    and evaluator_type in self.re_evaluation_triggering_eval_types \
                    and evaluator_name not in self.background_social_evaluators:
                if evaluators_util.check_valid_eval_note(eval_note, eval_type=eval_note_type,
                                                         expected_eval_type=evaluators_constants.EVALUATOR_EVAL_DEFAULT_TYPE):
                    # trigger re-evaluation
                    exchange_id = trading_api.get_exchange_id_from_matrix_id(exchange_name, matrix_id)
                    await evaluators_channel.trigger_technical_evaluators_re_evaluation_with_updated_data(matrix_id,
                                                                                                          evaluator_name,
                                                                                                          evaluator_type,
                                                                                                          exchange_name,
                                                                                                          cryptocurrency,
                                                                                                          symbol,
                                                                                                          exchange_id,
                                                                                                          self.strategy_time_frames)
                    # do not continue this evaluation
                    return
            counter = 0
            total_evaluation = 0

            for eval_by_rt in RT_evaluations_by_time_frame.values():
                for evaluation in eval_by_rt.values():
                    eval_value = evaluators_api.get_value(evaluation)
                    if evaluators_util.check_valid_eval_note(eval_value, eval_type=evaluators_api.get_type(evaluation),
                                                             expected_eval_type=evaluators_constants.EVALUATOR_EVAL_DEFAULT_TYPE):
                        total_evaluation += eval_value
                        counter += 1

            for eval_by_ta in TA_by_timeframe.values():
                for evaluation in eval_by_ta.values():
                    eval_value = evaluators_api.get_value(evaluation)
                    if evaluators_util.check_valid_eval_note(eval_value, eval_type=evaluators_api.get_type(evaluation),
                                                             expected_eval_type=evaluators_constants.EVALUATOR_EVAL_DEFAULT_TYPE):
                        total_evaluation += eval_value
                        counter += 1

            if social_evaluations_by_evaluator:
                exchange_manager = trading_api.get_exchange_manager_from_exchange_name_and_id(
                    exchange_name,
                    trading_api.get_exchange_id_from_matrix_id(exchange_name, self.matrix_id)
                )
                current_time = trading_api.get_exchange_current_time(exchange_manager)
                for evaluation in social_evaluations_by_evaluator.values():
                    eval_value = evaluators_api.get_value(evaluation)
                    if evaluators_util.check_valid_eval_note(eval_value, eval_type=evaluators_api.get_type(evaluation),
                                                             expected_eval_type=evaluators_constants.EVALUATOR_EVAL_DEFAULT_TYPE,
                                                             eval_time=evaluators_api.get_time(evaluation),
                                                             expiry_delay=self.social_evaluators_default_timeout,
                                                             current_time=current_time):
                        total_evaluation += eval_value
                        counter += 1

            if counter > 0:
                self.eval_note = total_evaluation / counter
                await self.strategy_completed(cryptocurrency, symbol)

        except errors.UnsetTentacleEvaluation as e:
            if evaluator_type == evaluators_enums.EvaluatorMatrixTypes.TA.value:
                self.logger.error(f"Missing technical evaluator data for ({e})")
            # otherwise it's a social or real-time evaluator, it will shortly be taken into account by TA update cycle
        except Exception as e:
            self.logger.exception(e, True, f"Error when computing strategy evaluation: {e}")


class TechnicalAnalysisStrategyEvaluator(evaluators.StrategyEvaluator):
    TIME_FRAMES_TO_WEIGHT = "time_frames_to_weight"
    TIME_FRAME = "time_frame"
    WEIGHT = "weight"
    DEFAULT_WEIGHT = 1

    def __init__(self):
        super().__init__()
        self.allowed_evaluator_types = [evaluators_enums.EvaluatorMatrixTypes.TA.value,
                                        evaluators_enums.EvaluatorMatrixTypes.REAL_TIME.value]
        config = tentacles_manager_api.get_tentacle_config(self.__class__)
        self.weight_by_time_frames = TechnicalAnalysisStrategyEvaluator._get_weight_by_time_frames(
            config[TechnicalAnalysisStrategyEvaluator.TIME_FRAMES_TO_WEIGHT])

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
        if evaluator_type not in self.allowed_evaluator_types:
            # only wake up on relevant callbacks
            return

        try:
            TA_by_timeframe = {
                available_time_frame: matrix.get_evaluations_by_evaluator(
                    matrix_id,
                    exchange_name,
                    evaluators_enums.EvaluatorMatrixTypes.TA.value,
                    cryptocurrency,
                    symbol,
                    available_time_frame.value,
                    allow_missing=False,
                    allowed_values=[commons_constants.START_PENDING_EVAL_NOTE])
                for available_time_frame in self.strategy_time_frames
            }

            if evaluator_type == evaluators_enums.EvaluatorMatrixTypes.REAL_TIME.value:
                # trigger re-evaluation
                exchange_id = trading_api.get_exchange_id_from_matrix_id(exchange_name, matrix_id)
                await evaluators_channel.trigger_technical_evaluators_re_evaluation_with_updated_data(matrix_id,
                                                                                                      evaluator_name,
                                                                                                      evaluator_type,
                                                                                                      exchange_name,
                                                                                                      cryptocurrency,
                                                                                                      symbol,
                                                                                                      exchange_id,
                                                                                                      self.strategy_time_frames)
                # do not continue this evaluation
                return

            total_evaluation = 0
            total_weights = 0

            for time_frame, eval_by_ta in TA_by_timeframe.items():
                for evaluation in eval_by_ta.values():
                    eval_value = evaluators_api.get_value(evaluation)
                    if evaluators_util.check_valid_eval_note(eval_value, eval_type=evaluators_api.get_type(evaluation),
                                                             expected_eval_type=evaluators_constants.EVALUATOR_EVAL_DEFAULT_TYPE):
                        weight = self.weight_by_time_frames.get(time_frame.value, self.DEFAULT_WEIGHT)
                        total_evaluation += eval_value * weight
                        total_weights += weight

            if total_weights > 0:
                self.eval_note = total_evaluation / total_weights
                await self.strategy_completed(cryptocurrency, symbol)

        except errors.UnsetTentacleEvaluation as e:
            self.logger.error(f"Missing technical evaluator data for ({e})")

    @classmethod
    def get_required_time_frames(cls, config: dict):
        if evaluators_constants.CONFIG_FORCED_TIME_FRAME in config:
            return time_frame_manager.parse_time_frames(config[evaluators_constants.CONFIG_FORCED_TIME_FRAME])
        strategy_config = tentacles_manager_api.get_tentacle_config(cls)
        if TechnicalAnalysisStrategyEvaluator.TIME_FRAMES_TO_WEIGHT in strategy_config:
            tf_to_weight = strategy_config[TechnicalAnalysisStrategyEvaluator.TIME_FRAMES_TO_WEIGHT]
            return time_frame_manager.parse_time_frames(
                list(TechnicalAnalysisStrategyEvaluator._get_weight_by_time_frames(tf_to_weight)))
        else:
            raise Exception(f"'{TechnicalAnalysisStrategyEvaluator.TIME_FRAMES_TO_WEIGHT}' "
                            f"is missing in configuration file")

    @staticmethod
    def _get_weight_by_time_frames(tf_to_weight):
        return {
            tf_and_weight[TechnicalAnalysisStrategyEvaluator.TIME_FRAME]:
                tf_and_weight[TechnicalAnalysisStrategyEvaluator.WEIGHT]
            for tf_and_weight in tf_to_weight
        }
