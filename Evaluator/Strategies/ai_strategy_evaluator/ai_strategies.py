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
import typing

import octobot_commons.constants as commons_constants
import octobot_commons.enums as commons_enums
import octobot_evaluators.matrix as matrix
import octobot_evaluators.enums as evaluators_enums
import octobot_evaluators.constants as evaluators_constants
import octobot_evaluators.errors as evaluators_errors
import octobot_evaluators.evaluators as evaluators
import octobot_commons.os_util as os_util
import octobot_services.api as services_api
import octobot_services.errors as services_errors
import tentacles.Services.Services_bases.gpt_service as gpt_service


class LLMStrategyEvaluator(evaluators.StrategyEvaluator):
    SYSTEM_PROMPT_KEY = "system_prompt"
    
    def __init__(self, tentacles_setup_config):
        super().__init__(tentacles_setup_config)
        self.gpt_model = gpt_service.GPTService.DEFAULT_MODEL
        self.services_config = None
        self.system_prompt = None

    async def load_and_save_user_inputs(self, bot_id: str) -> dict:
        """
        instance method API for user inputs
        Initialize and save the tentacle user inputs in run data
        :return: the filled user input configuration
        """
        self.is_backtesting = self._is_in_backtesting()
        if self.is_backtesting and not gpt_service.GPTService.BACKTESTING_ENABLED:
            self.logger.error(f"{self.get_name()} is disabled in backtesting. It will only emit neutral evaluations")
        await self._init_GPT_models()
        return await super().load_and_save_user_inputs(bot_id)

    def init_user_inputs(self, inputs: dict) -> None:
        """
        Called right before starting the tentacle, should define all the tentacle's user inputs unless
        those are defined somewhere else.
        """
        super().init_user_inputs(inputs)

        # GPT model
        current_value = self.specific_config.get("GPT_model")
        models = list(self.GPT_MODELS) or (
            [current_value] if current_value else [gpt_service.GPTService.DEFAULT_MODEL]
        )
        self.gpt_model = self.UI.user_input(
            "GPT model", commons_enums.UserInputTypes.OPTIONS, gpt_service.GPTService.DEFAULT_MODEL,
            inputs, options=sorted(models),
            title="GPT Model: the GPT model to use. Enable the evaluator to load other models."
        )

        self.system_prompt = self.UI.user_input(self.SYSTEM_PROMPT_KEY,
                               commons_enums.UserInputTypes.TEXT,
                               self.system_prompt, inputs,
                               title="The system prompt to use for the GPT model.")

    async def _init_GPT_models(self):
        if not self.GPT_MODELS:
            self.GPT_MODELS = [gpt_service.GPTService.DEFAULT_MODEL]
            if self.enable_model_selector and not self.is_backtesting:
                try:
                    service = await services_api.get_service(
                        gpt_service.GPTService, self.is_backtesting, self.services_config
                    )
                    self.GPT_MODELS = service.models
                except Exception as err:
                    self.logger.exception(err, True, f"Impossible to fetch GPT models: {err}")

    @classmethod
    def get_default_config(cls, time_frames: typing.Optional[list[str]] = None) -> dict:
        return {
            evaluators_constants.STRATEGIES_REQUIRED_TIME_FRAME: (
                time_frames or [commons_enums.TimeFrames.ONE_HOUR.value]
            ),
            commons_constants.CONFIG_TENTACLES_REQUIRED_CANDLES_COUNT: 500,
        }

    async def matrix_callback(self,
                              matrix_id,
                              evaluator_name,
                              evaluator_type,
                              eval_note,
                              eval_note_type,
                              eval_note_description,
                              eval_note_metadata,
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
                                               eval_note_description,
                                               eval_note_metadata,
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
                                           eval_note_description,
                                           eval_note_metadata,
                                           exchange_name,
                                           cryptocurrency,
                                           symbol)

    async def _trigger_evaluation(self,
                                  matrix_id,
                                  evaluator_name,
                                  evaluator_type,
                                  eval_note,
                                  eval_note_type,
                                  eval_note_description,
                                  eval_note_metadata,
                                  exchange_name,
                                  cryptocurrency,
                                  symbol):
        # ensure only start evaluations when technical evaluators have been initialized
        try:
            TA_by_timeframe = {
                available_time_frame: matrix.get_evaluation_descriptions_by_evaluator(
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
            social_evaluations_by_evaluator = matrix.get_evaluation_descriptions_by_evaluator(matrix_id,
                                                                                  exchange_name,
                                                                                  evaluators_enums.EvaluatorMatrixTypes.SOCIAL.value,
                                                                                  cryptocurrency,
                                                                                  symbol)
            # social evaluators by crypto currency
            social_evaluations_by_evaluator.update(matrix.get_evaluation_descriptions_by_evaluator(matrix_id,
                                                                                       exchange_name,
                                                                                       evaluators_enums.EvaluatorMatrixTypes.SOCIAL.value,
                                                                                       cryptocurrency))
                                                                                       
            formatted_data = ""
            result = await self.ask_gpt(self.system_prompt, formatted_data)
            self.eval_note = 0
            await self.strategy_completed(cryptocurrency, symbol)

        except evaluators_errors.UnsetTentacleEvaluation as e:
            if evaluator_type == evaluators_enums.EvaluatorMatrixTypes.TA.value:
                self.logger.error(f"Missing technical evaluator data for ({e})")
            # otherwise it's a social or real-time evaluator, it will shortly be taken into account by TA update cycle
        except Exception as e:
            self.logger.exception(e, True, f"Error when computing strategy evaluation: {e}")

    async def ask_gpt(self, preprompt, inputs) -> str:
        try:
            service = await services_api.get_service(
                gpt_service.GPTService,
                self.is_backtesting,
                {} if self.is_backtesting else self.services_config
            )
            service.apply_daily_token_limit_if_possible(self.gpt_tokens_limit)
            model = self.gpt_model if self.enable_model_selector else None
            resp = await service.get_chat_completion(
                [
                    service.create_message("system", preprompt, model=model),
                    service.create_message("user", inputs, model=model),
                ],
                model=model
            )
            self.logger.info(f"GPT's answer is '{resp}'")
            return resp
        except services_errors.CreationError as err:
            raise evaluators_errors.UnavailableEvaluatorError(f"Impossible to get ChatGPT prediction: {err}") from err
