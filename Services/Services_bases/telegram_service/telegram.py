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
import telegram
import telegram.ext

import octobot_commons.logging as bot_logging
import octobot_services.constants as services_constants
import octobot_services.services as services
import octobot.constants as constants


class TelegramService(services.AbstractService):
    CHAT_ID = "chat-id"

    LOGGERS = ["telegram.bot", "telegram.ext.updater", "telegram.vendor.ptb_urllib3.urllib3.connectionpool"]

    def __init__(self):
        super().__init__()
        self.telegram_api = None
        self.chat_id = None
        self.telegram_updater = None
        self.users = []
        self.text_chat_dispatcher = {}
        self._bot_url = None
        self.connected = False

    def get_fields_description(self):
        return {
            self.CHAT_ID: "ID of your chat.",
            services_constants.CONFIG_TOKEN: "Token given by 'botfather'.",
            services_constants.CONFIG_USERNAMES_WHITELIST: "List of telegram usernames (user's @ identifier without "
                                                           "@) allowed to talk to your OctoBot. This allows you to "
                                                           "limit your OctoBot's telegram interactions to specific "
                                                           "users only. No access restriction if left empty."
        }

    def get_default_value(self):
        return {
            self.CHAT_ID: "",
            services_constants.CONFIG_TOKEN: "",
            services_constants.CONFIG_USERNAMES_WHITELIST: [],
        }

    def get_required_config(self):
        return [self.CHAT_ID, services_constants.CONFIG_TOKEN]

    def get_read_only_info(self):
        return {
            "Connected to": self._bot_url
        } if self._bot_url else {}

    @classmethod
    def get_help_page(cls) -> str:
        return f"{constants.OCTOBOT_WEBSITE_URL}/guides/#telegram"

    @staticmethod
    def is_setup_correctly(config):
        return services_constants.CONFIG_TELEGRAM in config[services_constants.CONFIG_CATEGORY_SERVICES] \
               and services_constants.CONFIG_SERVICE_INSTANCE in config[services_constants.CONFIG_CATEGORY_SERVICES][
                   services_constants.CONFIG_TELEGRAM]

    async def prepare(self):
        if not self.telegram_api:
            self.chat_id = self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_TELEGRAM][
                self.CHAT_ID]
            self.telegram_api = telegram.Bot(
                token=self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_TELEGRAM][
                    services_constants.CONFIG_TOKEN])

        if not self.telegram_updater:
            self.telegram_updater = telegram.ext.Updater(
                self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_TELEGRAM][
                    services_constants.CONFIG_TOKEN],
                use_context=True,
                workers=1
            )

        bot_logging.set_logging_level(self.LOGGERS, logging.WARNING)

    def register_text_polling_handler(self, chat_types, handler):
        for chat_type in chat_types:
            self.text_chat_dispatcher[chat_type] = handler

    def text_handler(self, update, _):
        chat_type = update.effective_chat["type"]
        if chat_type in self.text_chat_dispatcher:
            self.text_chat_dispatcher[chat_type](_, update)
        else:
            self.logger.info(f"No handler for telegram update of type {chat_type}, update: {update}")

    def add_text_handler(self):
        self.telegram_updater.dispatcher.add_handler(
            telegram.ext.MessageHandler(telegram.ext.Filters.text, self.text_handler))

    def add_handlers(self, handlers):
        for handler in handlers:
            self.telegram_updater.dispatcher.add_handler(handler)

    def add_error_handler(self, handler):
        self.telegram_updater.dispatcher.add_error_handler(handler)

    def is_registered(self, user_key):
        return user_key in self.users

    def register_user(self, user_key):
        self.users.append(user_key)

    def start_dispatcher(self):
        try:
            if self.users:
                self.add_text_handler()
                self.connected = True
                self.telegram_updater.start_polling(timeout=2)
        except Exception as e:
            self.connected = False
            raise e

    def is_running(self):
        return self.telegram_updater and self.telegram_updater.running

    def get_type(self):
        return services_constants.CONFIG_TELEGRAM

    def get_website_url(self):
        return "https://telegram.org/"

    def get_endpoint(self):
        return self.telegram_api

    def get_updater(self):
        return self.telegram_updater

    def stop(self):
        if self.connected and self.telegram_updater:
            self.telegram_updater.stop()
            self.connected = False

    @staticmethod
    def get_is_enabled(config):
        return services_constants.CONFIG_CATEGORY_SERVICES in config \
               and services_constants.CONFIG_TELEGRAM in config[services_constants.CONFIG_CATEGORY_SERVICES]

    def has_required_configuration(self):
        return services_constants.CONFIG_CATEGORY_SERVICES in self.config \
               and services_constants.CONFIG_TELEGRAM in self.config[services_constants.CONFIG_CATEGORY_SERVICES] \
               and self.check_required_config(
            self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_TELEGRAM]) \
               and self.get_is_enabled(self.config)

    async def send_message(self, content, markdown=False, reply_to_message_id=None) -> telegram.Message:
        kwargs = {}
        if markdown:
            kwargs[services_constants.MESSAGE_PARSE_MODE] = telegram.parsemode.ParseMode.MARKDOWN
        try:
            if content:
                # no async call possible yet
                return self.telegram_api.send_message(chat_id=self.chat_id, text=content,
                                                      reply_to_message_id=reply_to_message_id, **kwargs)
        except telegram.error.TimedOut:
            # retry on failing
            try:
                # no async call possible yet
                return self.telegram_api.send_message(chat_id=self.chat_id, text=content,
                                                      reply_to_message_id=reply_to_message_id, **kwargs)
            except telegram.error.TimedOut as e:
                self.logger.error(f"Failed to send message : {e}")
        except telegram.error.Unauthorized as e:
            self.logger.error(f"Failed to send message ({e}): invalid telegram configuration.")
        return None

    def _fetch_bot_url(self):
        self._bot_url = f"https://web.telegram.org/#/im?p={self.telegram_api.get_me().name}"
        return self._bot_url

    def get_successful_startup_message(self):
        try:
            return f"Successfully initialized and accessible at: {self._fetch_bot_url()}.", True
        except telegram.error.NetworkError as e:
            self.log_connection_error_message(e)
            return "", False
        except telegram.error.Unauthorized as e:
            self.logger.error(f"Error when connecting to Telegram ({e}): invalid telegram configuration.")
            return "", False
