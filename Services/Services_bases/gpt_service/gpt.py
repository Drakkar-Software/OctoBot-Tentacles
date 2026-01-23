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
import asyncio
import os
import typing
import uuid
import openai
import logging
import datetime

try:
    from openai.lib._pydantic import to_strict_json_schema
except ImportError:
    # Fallback for older OpenAI SDK versions
    to_strict_json_schema = None

import octobot_services.constants as services_constants
import octobot_services.services as services
import octobot_services.errors as errors

import octobot_commons.constants as commons_constants
import octobot_commons.enums as commons_enums
import octobot_commons.logging as commons_logging
import octobot_commons.time_frame_manager as time_frame_manager
import octobot_commons.authentication as authentication
import octobot_commons.tree as tree
import octobot_commons.configuration.fields_utils as fields_utils

import octobot.constants as constants
import octobot.community as community


NO_SYSTEM_PROMPT_MODELS = [
    "o1-mini",
]
MINIMAL_PARAMS_SERIES_MODELS = [
    "o",  # the whole o-series does not support temperature parameter
]
MINIMAL_PARAMS_MODELS = [
    "gpt-5",  # does not support temperature parameter
]
SYSTEM = "system"
USER = "user"

REASONING_EFFORT_LOW = "low"
REASONING_EFFORT_MEDIUM = "medium"
REASONING_EFFORT_HIGH = "high"
REASONING_EFFORT_VALUES = (REASONING_EFFORT_LOW, REASONING_EFFORT_MEDIUM, REASONING_EFFORT_HIGH)


class LLMService(services.AbstractService, services.AbstractAIService):
    BACKTESTING_ENABLED = True
    DEFAULT_MODEL = None
    NO_TOKEN_LIMIT_VALUE = -1

    def get_fields_description(self):
        if self._env_secret_key is None:
            return {
                services_constants.CONFIG_OPENAI_SECRET_KEY: "Your openai API secret key",
                services_constants.CONFIG_LLM_CUSTOM_BASE_URL: (
                    "Custom LLM base url to use. Leave empty to use openai.com. For Ollama models, "
                    "add /v1 to the url (such as: http://localhost:11434/v1)"
                ),
                services_constants.CONFIG_LLM_MODEL: (
                    f"LLM model to use (default: {self.DEFAULT_MODEL}). "
                    "Can be overridden by GPT_MODEL environment variable."
                ),
                services_constants.CONFIG_LLM_DAILY_TOKENS_LIMIT: (
                    f"Daily token limit (default: {self.NO_TOKEN_LIMIT_VALUE} for no limit). "
                    "Can be overridden by GPT_DAILY_TOKEN_LIMIT environment variable."
                ),
                services_constants.CONFIG_LLM_SHOW_REASONING: (
                    "Show model thinking/reasoning. When enabled, uses Responses API for better reasoning access. "
                    "Default: False."
                ),
                services_constants.CONFIG_LLM_REASONING_EFFORT: (
                    "Reasoning effort level for models that support reasoning. "
                    "Values: 'low', 'medium', 'high', or empty for default. "
                    "If configured, the model will be treated as reasoning-capable."
                ),
            }
        return {}

    def get_default_value(self):
        if self._env_secret_key is None:
            return {
                services_constants.CONFIG_OPENAI_SECRET_KEY: "",
                services_constants.CONFIG_LLM_CUSTOM_BASE_URL: "",
                services_constants.CONFIG_LLM_MODEL: self.DEFAULT_MODEL,
                services_constants.CONFIG_LLM_DAILY_TOKENS_LIMIT: self.NO_TOKEN_LIMIT_VALUE,
                services_constants.CONFIG_LLM_SHOW_REASONING: False,
                services_constants.CONFIG_LLM_REASONING_EFFORT: "",
            }
        return {}

    def __init__(self):
        super().__init__()
        logging.getLogger("openai").setLevel(logging.WARNING)
        self._env_secret_key: typing.Optional[str] = (
            os.getenv(services_constants.ENV_OPENAI_SECRET_KEY, None) or None
        )
        # Model priority: env var > config > default
        env_model = os.getenv(services_constants.ENV_GPT_MODEL, None)
        self.model: str = env_model or self.DEFAULT_MODEL

        self.models: list[str] = []

        # Daily token limit priority: env var > config > default
        env_daily_token_limit_str = os.getenv(
            services_constants.ENV_GPT_DAILY_TOKENS_LIMIT, None
        )
        if env_daily_token_limit_str:
            self._env_daily_token_limit: int = int(env_daily_token_limit_str)
        else:
            self._env_daily_token_limit: int = self.NO_TOKEN_LIMIT_VALUE

        self._daily_tokens_limit: int = self._env_daily_token_limit
        self.consumed_daily_tokens: int = 1
        self.last_consumed_token_date: typing.Optional[datetime.date] = None

    def _load_model_from_config(self):
        """Load model from config if not overridden by environment variable."""
        if os.getenv(services_constants.ENV_GPT_MODEL, None):
            # Environment variable takes precedence
            return
        try:
            config_model = self.config[services_constants.CONFIG_CATEGORY_SERVICES][
                self.get_type()
            ].get(services_constants.CONFIG_LLM_MODEL)
            if config_model and not fields_utils.has_invalid_default_config_value(
                config_model
            ):
                self.model = config_model
        except (KeyError, TypeError):
            pass

    def _load_token_limit_from_config(self):
        """Load daily token limit from config if not overridden by environment variable."""
        if os.getenv(services_constants.ENV_GPT_DAILY_TOKENS_LIMIT, None):
            # Environment variable takes precedence
            return
        try:
            config_limit = self.config[services_constants.CONFIG_CATEGORY_SERVICES][
                self.get_type()
            ].get(services_constants.CONFIG_LLM_DAILY_TOKENS_LIMIT)
            if (
                config_limit is not None
                and not fields_utils.has_invalid_default_config_value(config_limit)
            ):
                if isinstance(config_limit, str):
                    self._daily_tokens_limit = int(config_limit)
                else:
                    self._daily_tokens_limit = config_limit
        except (KeyError, TypeError, ValueError):
            pass

    def _load_show_reasoning_from_config(self) -> bool:
        """Load show_reasoning setting from config."""
        try:
            config_show_reasoning = self.config[services_constants.CONFIG_CATEGORY_SERVICES][
                self.get_type()
            ].get(services_constants.CONFIG_LLM_SHOW_REASONING)
            if config_show_reasoning is not None:
                if isinstance(config_show_reasoning, str):
                    return config_show_reasoning.lower() in ("true", "1", "yes")
                return bool(config_show_reasoning)
        except (KeyError, TypeError):
            pass
        return False

    def _load_reasoning_effort_from_config(self) -> typing.Optional[str]:
        """Load reasoning_effort setting from config.
        
        Returns:
            str: "low", "medium", "high", or None if not configured
        """
        try:
            config_reasoning_effort = self.config[services_constants.CONFIG_CATEGORY_SERVICES][
                self.get_type()
            ].get(services_constants.CONFIG_LLM_REASONING_EFFORT)
            if config_reasoning_effort is not None:
                if isinstance(config_reasoning_effort, str):
                    effort = config_reasoning_effort.strip().lower()
                    if effort in REASONING_EFFORT_VALUES:
                        return effort
                    elif effort == "":
                        return None
                # Try to convert other types
                effort_str = str(config_reasoning_effort).lower()
                return effort_str if effort_str in REASONING_EFFORT_VALUES else None
        except (KeyError, TypeError):
            pass
        return None

    @staticmethod
    def create_message(role, content, model: typing.Optional[str] = None):
        if role == SYSTEM and model in NO_SYSTEM_PROMPT_MODELS:
            commons_logging.get_logger(LLMService.__name__).debug(
                f"Overriding prompt to use {USER} instead of {SYSTEM} for {model}"
            )
            return {"role": USER, "content": content}
        return {"role": role, "content": content}


    async def get_completion(
        self,
        messages,
        model=None,
        max_tokens=10000,
        n=1,
        stop=None,
        temperature=0.5,
        json_output=False,
        response_schema=None,
        reasoning_effort: typing.Optional[str] = None,
        show_reasoning: typing.Optional[bool] = None,
    ) -> typing.Union[str, dict, None]:
        """Get a completion from the LLM.
        
        Args:
            messages: List of message dicts
            model: Model to use
            max_tokens: Max tokens in response
            n: Number of completions
            stop: Stop sequences
            temperature: Sampling temperature
            json_output: Return JSON format
            response_schema: Optional Pydantic model or JSON schema dict for structured output.
                           If provided with json_output=True, enforces the response to match schema.
            reasoning_effort: Set reasoning effort if model supports reasoning.
                            Values: "low", "medium", "high", or None to use config/default.
                            If configured (via parameter or config), model is treated as reasoning-capable.
            show_reasoning: If True and reasoning_effort is configured, returns reasoning summary.
                          If None, uses config value. Default: False.
        
        Returns:
            str: Content when show_reasoning=False
            dict: {"content": str, "reasoning": str} when show_reasoning=True and reasoning available
            None: On error
        """
        self._ensure_rate_limit()
        try:
            model = model or self.model
            
            # Load reasoning_effort from config if not provided as parameter
            if reasoning_effort is None:
                reasoning_effort = self._load_reasoning_effort_from_config()
            
            # Determine if we should show reasoning
            if show_reasoning is None:
                show_reasoning = self._load_show_reasoning_from_config()
            
            # If reasoning_effort is configured, treat model as reasoning-capable
            has_reasoning_config = reasoning_effort is not None and reasoning_effort in REASONING_EFFORT_VALUES
            
            # Use Responses API when reasoning is configured and show_reasoning is enabled
            if has_reasoning_config and show_reasoning:
                try:
                    return await self._get_completion_with_responses_api(
                        messages, model, max_tokens, n, stop, temperature,
                        json_output, response_schema, reasoning_effort
                    )
                except (AttributeError, errors.InvalidRequestError) as err:
                    # Fall back to Chat Completions if Responses API fails
                    self.logger.warning(
                        f"Responses API failed for {model}: {err}. "
                        "Falling back to Chat Completions API."
                    )
                    # Continue with Chat Completions below
            
            supports_params = not self._is_minimal_params_model(model)
            if not supports_params:
                self.logger.debug(
                    f"The {model} model does not support every required parameter, results might not be as accurate "
                    f"as with other models."
                )
            # Prepare API call parameters
            api_kwargs = {
                "model": model,
                "max_completion_tokens": max_tokens,
                "n": n,
                "stop": stop,
                "temperature": temperature if supports_params else openai.NOT_GIVEN,
                "messages": messages,
            }
            
            # Add reasoning_effort if configured
            if has_reasoning_config:
                api_kwargs["reasoning_effort"] = reasoning_effort
            
            if json_output:
                if response_schema is not None:
                    if hasattr(response_schema, "model_json_schema"):
                        # It's a Pydantic model - use OpenAI's built-in function
                        if to_strict_json_schema is not None:
                            schema = to_strict_json_schema(response_schema)
                        else:
                            # Fallback for older OpenAI SDK versions
                            schema = response_schema.model_json_schema()
                            self.logger.warning(
                                "to_strict_json_schema not available. "
                                "Schema may not be fully compatible with strict mode."
                            )
                    else:
                        # response_schema is already a dict
                        schema = response_schema
                    api_kwargs["response_format"] = {
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema.get("title", "response"),
                            "schema": schema,
                            "strict": True,
                        }
                    }
                else:
                    # Fallback to basic JSON object format
                    api_kwargs["response_format"] = {"type": "json_object"}

            completions = await self._get_client().chat.completions.create(**api_kwargs)
            if completions.usage is not None:
                self._update_token_usage(completions.usage.total_tokens)
            
            if not completions.choices:
                raise errors.InvalidRequestError(
                    f"Empty response from model {model}: no choices returned"
                )
            
            message_content = completions.choices[0].message.content
            if message_content is None:
                raise errors.InvalidRequestError(
                    f"Empty content in response from model {model}. "
                    "This may occur when tool calls are present or the model returned no content."
                )
            return message_content
        except (
            openai.BadRequestError,
            openai.UnprocessableEntityError,  # error in request
        ) as err:
            if "does not support 'system' with this model" in str(err):
                # v2 compatibility: use getattr to safely access message attribute
                desc = getattr(err, 'message', str(err))
                err_message = (
                    f'The "{model}" model can\'t be used with {SYSTEM} prompts. '
                    f"It should be added to NO_SYSTEM_PROMPT_MODELS: {desc}"
                )
            else:
                err_message = f"Error when running request with model {model} (invalid request): {err}"
            raise errors.InvalidRequestError(err_message) from err
        except openai.NotFoundError as err:
            self.logger.error(
                f"Model {model} not found: {err}. Available models: {', '.join(self.models)}"
            )
            self.creation_error_message = str(err)
        except openai.AuthenticationError as err:
            self.logger.error(f"Invalid OpenAI api key: {err}")
            self.creation_error_message = str(err)
        except Exception as err:
            raise errors.InvalidRequestError(
                f"Unexpected error when running request with model {model}: {err}"
            ) from err

    def _get_client(self) -> openai.AsyncOpenAI:
        return openai.AsyncOpenAI(
            api_key=self._get_api_key(),
            base_url=self._get_base_url(),
        )

    async def _get_completion_with_responses_api(
        self,
        messages,
        model: str,
        max_tokens: int,
        n: int,
        stop,
        temperature: float,
        json_output: bool,
        response_schema,
        reasoning_effort: typing.Optional[str],
    ) -> typing.Union[str, dict]:
        """Get completion using Responses API for better reasoning access.
        
        This method is used for reasoning models when show_reasoning is enabled.
        The Responses API provides better access to reasoning summaries.
        """
        try:
            # Convert messages to Responses API format
            # Responses API expects input as a list of input items
            input_items = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    # For system messages, prepend to first user message or add as separate text
                    if input_items and input_items[-1].get("type") == "input_text":
                        # Prepend system message to last text input
                        input_items[-1]["text"] = f"System: {content}\n\n{input_items[-1]['text']}"
                    else:
                        input_items.append({
                            "type": "input_text",
                            "text": f"System: {content}"
                        })
                elif role in ("user", "assistant"):
                    input_items.append({
                        "type": "input_text",
                        "text": content
                    })
            
            # Prepare Responses API parameters
            responses_kwargs = {
                "model": model,
                "input": input_items,
                "max_output_tokens": max_tokens,
            }
            
            # Add reasoning_effort if specified
            if reasoning_effort and reasoning_effort in REASONING_EFFORT_VALUES:
                responses_kwargs["reasoning"] = {"effort": reasoning_effort}
            
            # Call Responses API
            response = await self._get_client().responses.create(**responses_kwargs)
            
            # Extract content and reasoning from response
            content = None
            reasoning_summary = None
            
            if hasattr(response, 'output') and response.output:
                for output_item in response.output:
                    # Handle different output item types
                    item_type = getattr(output_item, 'type', None)
                    
                    if item_type == 'text':
                        # Extract text content
                        content = getattr(output_item, 'text', None)
                        if content is None:
                            # Try alternative attribute names
                            content = getattr(output_item, 'content', None)
                    
                    elif item_type == 'reasoning':
                        # Extract reasoning summary
                        summary = getattr(output_item, 'summary', None)
                        if summary:
                            if isinstance(summary, list) and len(summary) > 0:
                                # Summary is a list of summary items
                                first_summary = summary[0]
                                reasoning_summary = getattr(first_summary, 'text', None) or str(first_summary)
                            elif hasattr(summary, 'text'):
                                reasoning_summary = summary.text
                            else:
                                reasoning_summary = str(summary)
            
            # Update token usage if available
            if hasattr(response, 'usage') and response.usage:
                total_tokens = getattr(response.usage, 'total_tokens', None)
                if total_tokens:
                    self._update_token_usage(total_tokens)
            
            # Log reasoning if available
            if reasoning_summary:
                self.logger.info(
                    f"Model reasoning summary for {model} ({len(reasoning_summary)} chars): "
                    f"{reasoning_summary[:200]}{'...' if len(reasoning_summary) > 200 else ''}"
                )
            
            if content is None:
                raise errors.InvalidRequestError(
                    f"Empty content in response from model {model} via Responses API."
                )
            
            # Return dict with content and reasoning if reasoning is available
            if reasoning_summary:
                return {
                    "content": content,
                    "reasoning": reasoning_summary
                }
            return content
            
        except AttributeError as err:
            # Responses API might not be available in all SDK versions
            self.logger.warning(
                f"Responses API not available or error occurred: {err}. "
                "Falling back to Chat Completions API."
            )
            # Fall through to regular Chat Completions
            raise
        except Exception as err:
            self.logger.error(f"Error using Responses API: {err}")
            raise errors.InvalidRequestError(
                f"Error when using Responses API with model {model}: {err}"
            ) from err

    def _is_of_series(self, model: str, series: str) -> bool:
        if model.startswith(series) and len(model) > 1:
            # avoid false positive: check if the next character is a number (ex: o3 model)
            try:
                int(model[len(series)])
                return True
            except ValueError:
                return False
        return False

    def _is_minimal_params_model(self, model: str) -> bool:
        for minimal_params_series in MINIMAL_PARAMS_SERIES_MODELS:
            if self._is_of_series(model, minimal_params_series):
                return True
        for minimal_params_model in MINIMAL_PARAMS_MODELS:
            if model.startswith(minimal_params_model):
                return True
        return False

    @staticmethod
    def is_setup_correctly(config):
        return True

    def allow_token_limit_update(self):
        return self._env_daily_token_limit == self.NO_TOKEN_LIMIT_VALUE

    def apply_daily_token_limit_if_possible(self, updated_limit: int):
        # do not allow updating daily_tokens_limit when set from environment variables
        if self.allow_token_limit_update():
            self._daily_tokens_limit = updated_limit

    def _ensure_rate_limit(self):
        if self.last_consumed_token_date != datetime.date.today():
            self.consumed_daily_tokens = 0
            self.last_consumed_token_date = datetime.date.today()
        if self._daily_tokens_limit == self.NO_TOKEN_LIMIT_VALUE:
            return
        if self.consumed_daily_tokens >= self._daily_tokens_limit:
            raise errors.RateLimitError(
                f"Daily rate limit reached (used {self.consumed_daily_tokens} out of {self._daily_tokens_limit})"
            )

    def _update_token_usage(self, consumed_tokens):
        self.consumed_daily_tokens += consumed_tokens
        self.logger.debug(
            f"Consumed {consumed_tokens} tokens. {self.consumed_daily_tokens} consumed tokens today."
        )

    def check_required_config(self, config):
        if self._env_secret_key is not None or self._get_base_url():
            return True
        try:
            config_key = config[services_constants.CONFIG_OPENAI_SECRET_KEY]
            return (
                bool(config_key)
                and config_key not in commons_constants.DEFAULT_CONFIG_VALUES
            )
        except KeyError:
            return False

    def has_required_configuration(self):
        try:
            return self.check_required_config(
                self.config[services_constants.CONFIG_CATEGORY_SERVICES].get(
                    self.get_type(), {}
                )
            )
        except KeyError:
            return False

    def get_required_config(self):
        return (
            [] if self._env_secret_key else [services_constants.CONFIG_OPENAI_SECRET_KEY]
        )

    @classmethod
    def get_help_page(cls) -> str:
        return f"{constants.OCTOBOT_DOCS_URL}/octobot-interfaces/chatgpt"

    def get_type(self) -> str:
        return services_constants.CONFIG_GPT

    def get_website_url(self):
        return "https://platform.openai.com/overview"

    def get_logo(self):
        return "https://upload.wikimedia.org/wikipedia/commons/0/04/ChatGPT_logo.svg"

    def _get_api_key(self):
        key = self._env_secret_key or self.config[
            services_constants.CONFIG_CATEGORY_SERVICES
        ][self.get_type()].get(services_constants.CONFIG_OPENAI_SECRET_KEY, None)
        if key and not fields_utils.has_invalid_default_config_value(key):
            return key
        if self._get_base_url():
            # no key and custom base url: use random key
            return uuid.uuid4().hex
        return key

    def _get_base_url(self):
        value = self.config[services_constants.CONFIG_CATEGORY_SERVICES][
            self.get_type()
        ].get(services_constants.CONFIG_LLM_CUSTOM_BASE_URL)
        if fields_utils.has_invalid_default_config_value(value):
            return None
        return value or None

    async def prepare(self) -> None:
        try:
            # Load model and token limit from config (with env var precedence)
            self._load_model_from_config()
            self._load_token_limit_from_config()

            if self._get_base_url():
                self.logger.debug(f"Using custom LLM url: {self._get_base_url()}")
            fetched_models = await self._get_client().models.list()
            if fetched_models.data:
                self.logger.debug(f"Fetched {len(fetched_models.data)} models")
                self.models = [d.id for d in fetched_models.data]
            else:
                self.logger.warning("No fetched models")
                self.models = []
            if self.model not in self.models:
                if self._get_base_url():
                    self.logger.info(
                        f"Custom LLM available models are: {self.models}. "
                        f"Please select one of those in your evaluator configuration."
                    )
                else:
                    self.logger.warning(
                        f"Warning: the default '{self.model}' model is not in available LLM models from the "
                        f"selected LLM provider. "
                        f"Available models are: {self.models}. Please select an available model when configuring your "
                        f"evaluators."
                    )
        except openai.AuthenticationError as err:
            self.logger.error(f"Invalid OpenAI api key: {err}")
            self.creation_error_message = str(err)
        except Exception as err:
            self.logger.exception(
                err, True, f"Unexpected error when initializing LLM service: {err}"
            )

    def _is_healthy(self):
        return self._get_api_key() and self.models

    def get_successful_startup_message(self):
        return (
            f"LLM configured and ready. {len(self.models)} AI models are available. Using {self.models}.",
            self._is_healthy(),
        )

    def use_stored_signals_only(self):
        return not self.config

    async def stop(self):
        pass


class LLMSignalService(LLMService):
    """LLM service for managing signals generation and storage."""

    def get_fields_description(self):
        fields = super().get_fields_description()
        # LLMSignalService uses the same config as LLMService for backward compatibility
        return fields

    def get_default_value(self):
        return super().get_default_value()

    def __init__(self):
        super().__init__()
        self.stored_signals: tree.BaseTree = tree.BaseTree()

    async def get_chat_completion(
        self,
        messages,
        model=None,
        max_tokens=3000,
        n=1,
        stop=None,
        temperature=0.5,
        exchange: typing.Optional[str] = None,
        symbol: typing.Optional[str] = None,
        time_frame: typing.Optional[str] = None,
        version: typing.Optional[str] = None,
        candle_open_time: typing.Optional[float] = None,
        use_stored_signals: bool = False,
    ) -> str:
        """Get a signal from stored signals or GPT."""
        if use_stored_signals:
            return self._get_signal_from_stored_signals(
                exchange, symbol, time_frame, version, candle_open_time
            )
        if self.use_stored_signals_only():
            signal = await self._fetch_signal_from_stored_signals(
                exchange, symbol, time_frame, version, candle_open_time
            )
            if not signal:
                # should not happen
                self.logger.error(
                    f"Missing ChatGPT signal from stored signals on {symbol} {time_frame} "
                    f"for timestamp: {candle_open_time} with version: {version}"
                )
            return signal
        return await self._get_signal_from_gpt(
            messages, model, max_tokens, n, stop, temperature
        )

    async def _get_signal_from_gpt(
        self, messages, model=None, max_tokens=3000, n=1, stop=None, temperature=0.5
    ):
        """Get a signal from GPT."""
        return await self.get_completion(
            messages, model, max_tokens, n, stop, temperature
        )

    def _get_signal_from_stored_signals(
        self,
        exchange: str,
        symbol: str,
        time_frame: str,
        version: str,
        candle_open_time: float,
    ) -> str:
        try:
            return self.stored_signals.get_node(
                [exchange, symbol, time_frame, version, candle_open_time]
            ).node_value
        except tree.NodeExistsError:
            return ""

    async def _fetch_signal_from_stored_signals(
        self,
        exchange: str,
        symbol: str,
        time_frame: str,
        version: str,
        candle_open_time: float,
    ) -> typing.Optional[str]:
        authenticator = authentication.Authenticator.instance()
        try:
            return await authenticator.get_gpt_signal(
                exchange,
                symbol,
                commons_enums.TimeFrames(time_frame),
                candle_open_time,
                version,
            )
        except Exception as err:
            self.logger.exception(err, True, f"Error when fetching gpt signal: {err}")

    def store_signal_history(
        self,
        exchange: str,
        symbol: str,
        time_frame: commons_enums.TimeFrames,
        version: str,
        signals_by_candle_open_time,
    ):
        tf = time_frame.value
        for candle_open_time, signal in signals_by_candle_open_time.items():
            self.stored_signals.set_node_at_path(
                signal, str, [exchange, symbol, tf, version, candle_open_time]
            )

    def has_signal_history(
        self,
        exchange: str,
        symbol: str,
        time_frame: commons_enums.TimeFrames,
        min_timestamp: float,
        max_timestamp: float,
        version: str,
    ):
        for ts in (min_timestamp, max_timestamp):
            if (
                self._get_signal_from_stored_signals(
                    exchange,
                    symbol,
                    time_frame.value,
                    version,
                    time_frame_manager.get_last_timeframe_time(time_frame, ts),
                )
                == ""
            ):
                return False
        return True

    async def _fetch_and_store_history(
        self,
        authenticator,
        exchange_name,
        symbol,
        time_frame,
        version,
        min_timestamp: float,
        max_timestamp: float,
    ):
        # no need to fetch a particular exchange
        signals_by_candle_open_time = await authenticator.get_gpt_signals_history(
            None,
            symbol,
            time_frame,
            time_frame_manager.get_last_timeframe_time(time_frame, min_timestamp),
            time_frame_manager.get_last_timeframe_time(time_frame, max_timestamp),
            version,
        )
        if signals_by_candle_open_time:
            self.logger.info(
                f"Fetched {len(signals_by_candle_open_time)} ChatGPT signals "
                f"history for {symbol} {time_frame} on any exchange."
            )
        else:
            self.logger.error(
                f"No ChatGPT signal history for {symbol} on {time_frame.value} for any exchange with {version}. "
                f"Please check {self._supported_history_url()} to get the list of supported signals history."
            )
        self.store_signal_history(
            exchange_name, symbol, time_frame, version, signals_by_candle_open_time
        )

    async def fetch_gpt_history(
        self,
        exchange_name: str,
        symbols: list,
        time_frames: list,
        version: str,
        start_timestamp: float,
        end_timestamp: float,
    ):
        authenticator = authentication.Authenticator.instance()
        coros = [
            self._fetch_and_store_history(
                authenticator,
                exchange_name,
                symbol,
                time_frame,
                version,
                start_timestamp,
                end_timestamp,
            )
            for symbol in symbols
            for time_frame in time_frames
            if not self.has_signal_history(
                exchange_name,
                symbol,
                time_frame,
                start_timestamp,
                end_timestamp,
                version,
            )
        ]
        if coros:
            await asyncio.gather(*coros)

    def clear_signal_history(self):
        self.stored_signals.clear()

    def _supported_history_url(self):
        return f"{community.IdentifiersProvider.COMMUNITY_URL}/features/chatgpt-trading"

    def check_required_config(self, config):
        if (
            self._env_secret_key is not None
            or self.use_stored_signals_only()
            or self._get_base_url()
        ):
            return True
        try:
            config_key = config[services_constants.CONFIG_OPENAI_SECRET_KEY]
            return (
                bool(config_key)
                and config_key not in commons_constants.DEFAULT_CONFIG_VALUES
            )
        except KeyError:
            return False

    def has_required_configuration(self):
        try:
            if self.use_stored_signals_only():
                return True
            return self.check_required_config(
                self.config[services_constants.CONFIG_CATEGORY_SERVICES].get(
                    services_constants.CONFIG_GPT, {}
                )
            )
        except KeyError:
            return False

    def _is_healthy(self):
        return self.use_stored_signals_only() or (self._get_api_key() and self.models)

    def get_successful_startup_message(self):
        return (
            f"GPT configured and ready. {len(self.models)} AI models are available. "
            f"Using {'stored signals' if self.use_stored_signals_only() else self.models}.",
            self._is_healthy(),
        )

    async def prepare(self) -> None:
        try:
            if self.use_stored_signals_only():
                self.logger.info(
                    f"Skipping GPT - OpenAI models fetch as self.use_stored_signals_only() is True"
                )
                return

            self._load_model_from_config()
            self._load_token_limit_from_config()

            if self._get_base_url():
                self.logger.info(f"Using custom LLM url: {self._get_base_url()}")
            fetched_models = await self._get_client().models.list()
            if fetched_models.data:
                self.logger.info(f"Fetched {len(fetched_models.data)} models")
                self.models = [d.id for d in fetched_models.data]
            else:
                self.logger.info("No fetched models")
                self.models = []
            if self.model not in self.models:
                if self._get_base_url():
                    self.logger.info(
                        f"Custom LLM available models are: {self.models}. "
                        f"Please select one of those in your evaluator configuration."
                    )
                else:
                    self.logger.warning(
                        f"Warning: the default '{self.model}' model is not in available LLM models from the "
                        f"selected LLM provider. "
                        f"Available models are: {self.models}. Please select an available model when configuring your "
                        f"evaluators."
                    )
        except openai.AuthenticationError as err:
            self.logger.error(f"Invalid OpenAI api key: {err}")
            self.creation_error_message = str(err)
        except Exception as err:
            self.logger.exception(
                err, True, f"Unexpected error when initializing GPT service: {err}"
            )


# Backward compatibility: keep GPTService as an alias for LLMSignalService
GPTService = LLMSignalService
