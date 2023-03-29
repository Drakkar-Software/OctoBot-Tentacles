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
import os
import openai
import logging
import datetime

import octobot_services.constants as services_constants
import octobot_services.services as services
import octobot_services.errors as errors
import octobot.constants as constants


class GPTService(services.AbstractService):
    def get_fields_description(self):
        if self._env_secret_key is None:
            return {
                services_constants.CONIG_OPENAI_SECRET_KEY: "Your openai API secret key",
            }
        return {}

    def get_default_value(self):
        if self._env_secret_key is None:
            return {
                services_constants.CONIG_OPENAI_SECRET_KEY: "",
            }
        return {}

    def __init__(self):
        super().__init__()
        logging.getLogger("openai").setLevel(logging.WARNING)
        self._env_secret_key = os.getenv(services_constants.ENV_OPENAI_SECRET_KEY, None)
        self.model = os.getenv(services_constants.ENV_GPT_MODEL, "gpt-3.5-turbo")
        self.models = []
        self.daily_tokens_limit = int(os.getenv(services_constants.ENV_GPT_DAILY_TOKENS_LIMIT, 0))
        self.consumed_daily_tokens = 1
        self.last_consumed_token_date = None

    @staticmethod
    def create_message(role, content):
        return {"role": role, "content": content}

    async def get_chat_completion(
        self,
        messages,
        model=None,
        max_tokens=3000,
        n=1,
        stop=None,
        temperature=0.5,
    ):
        self._ensure_rate_limit()
        try:
            completions = await openai.ChatCompletion.acreate(
                api_key=self._get_api_key(),
                model=model or self.model,
                max_tokens=max_tokens,
                n=n,
                stop=stop,
                temperature=temperature,
                messages=messages
            )
            self._update_token_usage(completions['usage']['total_tokens'])
            return completions["choices"][0]["message"]["content"]
        except openai.error.InvalidRequestError as err:
            raise errors.InvalidRequestError(f"Error when running request (invalid request): {err}") from err
        except Exception as err:
            raise errors.InvalidRequestError(f"Unexpected error when running request: {err}") from err

    def _ensure_rate_limit(self):
        if self.last_consumed_token_date != datetime.date.today():
            self.consumed_daily_tokens = 0
            self.last_consumed_token_date = datetime.date.today()
        if not self.daily_tokens_limit:
            return
        if self.consumed_daily_tokens >= self.daily_tokens_limit:
            raise errors.RateLimitError("Daily rate limit reached")

    def _update_token_usage(self, consumed_tokens):
        self.consumed_daily_tokens += consumed_tokens
        self.logger.debug(f"Consumed {consumed_tokens} tokens. {self.consumed_daily_tokens} consumed tokens today.")

    def check_required_config(self, config):
        if self._env_secret_key is not None:
            return True
        try:
            return bool(config[services_constants.CONIG_OPENAI_SECRET_KEY])
        except KeyError:
            return False

    def has_required_configuration(self):
        try:
            return self.check_required_config(
                self.config[services_constants.CONFIG_CATEGORY_SERVICES].get(services_constants.CONFIG_GPT, {})
            )
        except KeyError:
            return False

    def get_required_config(self):
        return [] if self._env_secret_key else [services_constants.CONIG_OPENAI_SECRET_KEY]

    @classmethod
    def get_help_page(cls) -> str:
        return f"{constants.OCTOBOT_DOCS_URL}/gpt/using-gpt-with-octobot"

    def get_type(self) -> None:
        return services_constants.CONFIG_GPT

    def get_logo(self):
        return None
    
    def _get_api_key(self):
        return self._env_secret_key or \
            self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_GPT][
                services_constants.CONIG_OPENAI_SECRET_KEY
            ]

    async def prepare(self) -> None:
        try:
            fetched_models = await openai.Model.alist(api_key=self._get_api_key())
            self.models = [d["id"] for d in fetched_models["data"]]
            if self.model not in self.models:
                self.logger.warning(f"Warning: selected '{self.model}' model is not in GPT available models. "
                                    f"Available models are: {self.models}")
        except openai.error.AuthenticationError as err:
            self.logger.error(f"Error when checking api key: {err}")
        except Exception as err:
            self.logger.error(f"Unexpected error when checking api key: {err}")

    def _is_healthy(self):
        return self._get_api_key() and self.models

    def get_successful_startup_message(self):
        return f"GPT configured and ready. {len(self.models)} AI models are available. Using {self.model}.", \
            self._is_healthy()

    async def stop(self):
        pass
