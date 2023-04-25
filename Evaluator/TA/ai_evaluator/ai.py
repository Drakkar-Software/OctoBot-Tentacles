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
import tulipy
import os

import octobot_commons.constants as commons_constants
import octobot_commons.enums as commons_enums
import octobot_commons.enums as enums
import octobot_commons.os_util as os_util
import octobot_commons.data_util as data_util
import octobot_evaluators.evaluators as evaluators
import octobot_evaluators.util as evaluators_util
import octobot_evaluators.errors as evaluators_errors
import octobot_trading.api as trading_api
import octobot_services.api as services_api
import octobot_services.errors as services_errors
import tentacles.Services.Services_bases.gpt_service as gpt_service


class GPTEvaluator(evaluators.TAEvaluator):
    PREPROMPT = "Predict: {up or down} {confidence%} (no other information)"
    PASSED_DATA_LEN = 10
    HIGH_CONFIDENCE_PERCENT = 80
    MEDIUM_CONFIDENCE_PERCENT = 50
    LOW_CONFIDENCE_PERCENT = 30
    INDICATORS = {
        "No indicator: the raw value of the selected source": lambda data, period: data,
        "EMA: Exponential Moving Average": tulipy.ema,
        "SMA: Simple Moving Average": tulipy.sma,
        "Kaufman Adaptive Moving Average": tulipy.kama,
        "Hull Moving Average": tulipy.kama,
        "RSI: Relative Strength Index": tulipy.rsi,
        "Detrended Price Oscillator": tulipy.dpo,
    }
    SOURCES = ["Open", "High", "Low", "Close", "Volume"]
    GPT_MODELS = []

    def __init__(self, tentacles_setup_config):
        super().__init__(tentacles_setup_config)
        self.indicator = None
        self.source = None
        self.period = None
        self.gpt_model = gpt_service.GPTService.DEFAULT_MODEL
        self.is_backtesting = False
        self.min_allowed_timeframe = os.getenv("MIN_GPT_TIMEFRAME", None)
        self.enable_model_selector = os_util.parse_boolean_environment_var("ENABLE_GPT_MODELS_SELECTOR", "True")
        self._min_allowed_timeframe_minutes = 0
        try:
            if self.min_allowed_timeframe:
                self._min_allowed_timeframe_minutes = \
                    commons_enums.TimeFramesMinutes[commons_enums.TimeFrames(self.min_allowed_timeframe)]
        except ValueError:
            self.logger.error(f"Invalid timeframe configuration: unknown timeframe: '{self.min_allowed_timeframe}'")
        self.allow_reevaluations = os_util.parse_boolean_environment_var("ALLOW_GPT_REEVALUATIONS", "True")

    def enable_reevaluation(self) -> bool:
        """
        Override when artificial re-evaluations from the evaluator channel can be disabled
        """
        return self.allow_reevaluations

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
        self.indicator = self.UI.user_input(
            "indicator", enums.UserInputTypes.OPTIONS, next(iter(self.INDICATORS)),
            inputs, options=list(self.INDICATORS),
            title="Indicator: the technical indicator to apply and give the result of to chat GPT."
        )
        self.source = self.UI.user_input(
            "source", enums.UserInputTypes.OPTIONS, self.SOURCES[3],
            inputs, options=self.SOURCES,
            title="Source: values of candles data to pass to the indicator."
        )
        self.period = self.UI.user_input(
            "period", enums.UserInputTypes.INT,
            self.period, inputs, min_val=1,
            title="Period: length of the indicator period."
        )
        if len(self.GPT_MODELS) > 1 and self.enable_model_selector:
            self.gpt_model = self.UI.user_input(
                "GPT model", enums.UserInputTypes.OPTIONS, gpt_service.GPTService.DEFAULT_MODEL,
                inputs, options=list(self.GPT_MODELS),
                title="GPT Model: the GPT model to use."
            )

    async def _init_GPT_models(self):
        if not self.GPT_MODELS:
            self.GPT_MODELS = [gpt_service.GPTService.DEFAULT_MODEL]
            if self.enable_model_selector and not self.is_backtesting:
                try:
                    service = await services_api.get_service(gpt_service.GPTService, self.is_backtesting)
                    self.GPT_MODELS = service.models
                except Exception as err:
                    self.logger.exception(err, True, f"Impossible to fetch GPT models: {err}")

    async def _init_registered_topics(self, all_symbols_by_crypto_currencies, currencies, symbols, time_frames):
        await super()._init_registered_topics(all_symbols_by_crypto_currencies, currencies, symbols, time_frames)
        for time_frame in time_frames:
            if not self._check_timeframe(time_frame.value):
                self.logger.error(f"{time_frame.value} time frame will be ignored for {self.get_name()} "
                                  f"as {time_frame.value} is not allowed in this configuration. "
                                  f"The shortest allowed time frame is {self.min_allowed_timeframe}. {self.get_name()} "
                                  f"will emit neutral evaluations on this time frame.")

    async def ohlcv_callback(self, exchange: str, exchange_id: str,
                             cryptocurrency: str, symbol: str, time_frame, candle, inc_in_construction_data):
        candle_data = self.get_candles_data_api()(
            self.get_exchange_symbol_data(exchange, exchange_id, symbol), time_frame,
            include_in_construction=inc_in_construction_data
        )
        await self.evaluate(cryptocurrency, symbol, time_frame, candle_data, candle)

    async def evaluate(self, cryptocurrency, symbol, time_frame, candle_data, candle):
        self.eval_note = commons_constants.START_PENDING_EVAL_NOTE
        if self._check_timeframe(time_frame):
            try:
                computed_data = self.call_indicator(candle_data)
                reduced_data = computed_data[-self.PASSED_DATA_LEN:]
                formatted_data = ", ".join(str(datum).replace('[', '').replace(']', '') for datum in reduced_data)
                prediction = await self.ask_gpt(self.PREPROMPT, formatted_data, symbol, time_frame)
                cleaned_prediction = prediction.strip().replace("\n", "").replace(".", "").lower()
                prediction_side = self._parse_prediction_side(cleaned_prediction)
                if prediction_side == 0:
                    self.logger.error(f"Error when reading GPT answer: {cleaned_prediction}")
                    return
                confidence = self._parse_confidence(cleaned_prediction) / 100
                self.eval_note = prediction_side * confidence
            except services_errors.InvalidRequestError as e:
                self.logger.error(f"Invalid GPT request: {e}")
            except services_errors.RateLimitError as e:
                self.logger.error(f"Too many requests: {e}")
            except services_errors.UnavailableInBacktestingError:
                # error already logged error for backtesting in use_backtesting_init_timeout
                pass
            except evaluators_errors.UnavailableEvaluatorError as e:
                self.logger.exception(e, True, f"Evaluation error: {e}")
            except tulipy.lib.InvalidOptionError as e:
                self.logger.warning(
                    f"Error when computing {self.indicator} on {self.period} period with {len(candle_data)} "
                    f"candles: {e}"
                )
                self.logger.exception(e, False)
        else:
            self.logger.debug(f"Ignored {time_frame} time frame as the shorted allowed time frame is "
                              f"{self.min_allowed_timeframe}")
        await self.evaluation_completed(cryptocurrency, symbol, time_frame,
                                        eval_time=evaluators_util.get_eval_time(full_candle=candle,
                                                                                time_frame=time_frame))

    async def ask_gpt(self, preprompt, inputs, symbol, time_frame) -> str:
        try:
            service = await services_api.get_service(gpt_service.GPTService, self.is_backtesting)
            resp = await service.get_chat_completion(
                [
                    service.create_message("system", preprompt),
                    service.create_message("user", inputs),
                ],
                model=self.gpt_model if self.enable_model_selector else None
            )
            self.logger.info(f"GPT's answer is '{resp}' for {symbol} on {time_frame} with input: {inputs}")
            return resp
        except services_errors.CreationError as err:
            raise evaluators_errors.UnavailableEvaluatorError(f"Impossible to get ChatGPT prediction: {err}") from err

    def call_indicator(self, candle_data):
        return data_util.drop_nan(self.INDICATORS[self.indicator](candle_data, self.period))

    def get_candles_data_api(self):
        return {
            self.SOURCES[0]: trading_api.get_symbol_open_candles,
            self.SOURCES[1]: trading_api.get_symbol_high_candles,
            self.SOURCES[2]: trading_api.get_symbol_low_candles,
            self.SOURCES[3]: trading_api.get_symbol_close_candles,
            self.SOURCES[4]: trading_api.get_symbol_volume_candles,
        }[self.source]

    def _check_timeframe(self, time_frame):
        return commons_enums.TimeFramesMinutes[commons_enums.TimeFrames(time_frame)] >= \
            self._min_allowed_timeframe_minutes

    def _parse_prediction_side(self, cleaned_prediction):
        if "down " in cleaned_prediction:
            return 1
        elif "up " in cleaned_prediction:
            return -1
        return 0

    def _parse_confidence(self, cleaned_prediction):
        """
        possible formats:
        up 70%                   (most common case)
        up with 70% confidence
        up with high confidence
        """
        if "%" in cleaned_prediction:
            percent_index = cleaned_prediction.index("%")
            return float(cleaned_prediction[:percent_index].split(" ")[-1])
        if "high" in cleaned_prediction:
            return self.HIGH_CONFIDENCE_PERCENT
        if "medium" in cleaned_prediction or "intermediate" in cleaned_prediction:
            return self.MEDIUM_CONFIDENCE_PERCENT
        if "low" in cleaned_prediction:
            return self.LOW_CONFIDENCE_PERCENT
        self.logger.warning(f"Impossible to parse confidence in {cleaned_prediction}. Using low confidence")
        return self.LOW_CONFIDENCE_PERCENT
