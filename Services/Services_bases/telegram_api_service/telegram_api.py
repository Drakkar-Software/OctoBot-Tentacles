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
import logging

import octobot_commons.constants as common_constants
import octobot_commons.logging as bot_logging
import telegram
import telethon

import octobot.constants as constants
import octobot_services.constants as services_constants
import octobot_services.services as services


class TelegramApiService(services.AbstractService):
    LOGGERS = ["TelegramApiService.client.updates", "TelegramApiService.extensions.messagepacker",
               "TelegramApiService.network.mtprotosender", "telethon.crypto.aes", "telethon.crypto.aesctr"]

    def __init__(self):
        super().__init__()
        self.telegram_client: telethon.TelegramClient = None
        self.me = None
        self.connected = False

        bot_logging.set_logging_level(self.LOGGERS, logging.WARNING)

    def get_fields_description(self):
        return {
            services_constants.CONFIG_API: "App api key.",
            services_constants.CONFIG_API_HASH: "App api hash.",
            services_constants.CONFIG_TELEGRAM_PHONE: "Your telegram phone number (beginning with '+' country code).",
        }

    def get_default_value(self):
        return {
            services_constants.CONFIG_API: "",
            services_constants.CONFIG_API_HASH: "",
            services_constants.CONFIG_TELEGRAM_PHONE: ""
        }

    def add_event_handler(self, callback, event):
        if self.telegram_client:
            self.telegram_client.add_event_handler(callback, event)

    def get_required_config(self):
        return [services_constants.CONFIG_API, services_constants.CONFIG_API_HASH]

    def get_read_only_info(self):
        return {f"Connected as {self.me.username}": f"https://telegram.me/{self.me.username}"} \
            if self.connected and self.me else {}

    @classmethod
    def get_help_page(cls) -> str:
        return f"{constants.OCTOBOT_WEBSITE_URL}/guides/#telegram-api"

    @staticmethod
    def is_setup_correctly(config):
        return services_constants.CONFIG_TELEGRAM_API in config[services_constants.CONFIG_CATEGORY_SERVICES] \
               and services_constants.CONFIG_SERVICE_INSTANCE in config[services_constants.CONFIG_CATEGORY_SERVICES][
                   services_constants.CONFIG_TELEGRAM_API]

    async def prepare(self):
        if not self.telegram_client:
            try:
                self.telegram_client = telethon.TelegramClient(f"{common_constants.USER_FOLDER}/telegram-api",
                                                               self.config[services_constants.CONFIG_CATEGORY_SERVICES]
                                                               [services_constants.CONFIG_TELEGRAM_API]
                                                               [services_constants.CONFIG_API],
                                                               self.config[services_constants.CONFIG_CATEGORY_SERVICES]
                                                               [services_constants.CONFIG_TELEGRAM_API]
                                                               [services_constants.CONFIG_API_HASH],
                                                               base_logger=self.get_name())

                await self.telegram_client.start(
                    phone=
                    self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_TELEGRAM_API]
                    [services_constants.CONFIG_TELEGRAM_PHONE]
                )
                self.me = await self.telegram_client.get_me()
                self.connected = True
            except Exception as e:
                self.logger.error(f"Failed to connect to Telegram Api : {e}")

    def is_running(self):
        return self.telegram_client.is_connected()

    def get_type(self):
        return services_constants.CONFIG_TELEGRAM_API

    def get_website_url(self):
        return "https://telegram.org/"

    def get_endpoint(self):
        return self.telegram_client

    def get_brand_name(self):
        return "telegram"

    def stop(self):
        if self.connected:
            self.telegram_client.disconnect()
            self.connected = False

    @staticmethod
    def get_is_enabled(config):
        return services_constants.CONFIG_CATEGORY_SERVICES in config \
               and services_constants.CONFIG_TELEGRAM_API in config[services_constants.CONFIG_CATEGORY_SERVICES]

    def has_required_configuration(self):
        return services_constants.CONFIG_CATEGORY_SERVICES in self.config \
               and services_constants.CONFIG_TELEGRAM_API in self.config[services_constants.CONFIG_CATEGORY_SERVICES] \
               and self.check_required_config(
            self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_TELEGRAM_API]) \
               and self.get_is_enabled(self.config)

    async def send_message(self, content, markdown=False, reply_to_message_id=None) -> telegram.Message:
        kwargs = {}
        if markdown:
            kwargs[services_constants.MESSAGE_PARSE_MODE] = telegram.parsemode.ParseMode.MARKDOWN
        try:
            if content:
                return await self.telegram_client.send_message(entity=self.me.username,
                                                               message=content,
                                                               reply_to=reply_to_message_id, **kwargs)
        except Exception as e:
            self.logger.error(f"Failed to send message : {e}")
        return None

    def get_successful_startup_message(self):
        try:
            return f"Successfully connected to {self.me.username} account.", True
        except Exception as e:
            self.logger.error(f"Error when connecting to Telegram API ({e}): invalid telegram configuration.")
            return "", False
