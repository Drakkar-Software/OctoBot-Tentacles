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
import hashlib

from octobot_services.constants import CONFIG_TRADING_VIEW, CONFIG_REQUIRE_TRADING_VIEW_TOKEN, CONFIG_CATEGORY_SERVICES
from octobot_services.services.abstract_service import AbstractService


class TradingViewService(AbstractService):
    def __init__(self):
        super().__init__()
        self.requires_token = False
        self.chat_id = None
        self.telegram_updater = None
        self.users = []
        self.text_chat_dispatcher = {}

    @staticmethod
    def is_setup_correctly(config):
        return True

    @staticmethod
    def get_is_enabled(config):
        return True

    def has_required_configuration(self):
        return True

    def get_required_config(self):
        return [CONFIG_REQUIRE_TRADING_VIEW_TOKEN]

    def get_fields_description(self):
        return {
            CONFIG_REQUIRE_TRADING_VIEW_TOKEN: "When enabled the Trading View webhook will require a valid token to "
                                               "process a signal. This token is printed in the terminal at startup."
        }

    def get_default_value(self):
        return {
            CONFIG_REQUIRE_TRADING_VIEW_TOKEN: False
        }

    @classmethod
    def get_help_page(cls) -> str:
        return "https://github.com/Drakkar-Software/OctoBot/wiki/TradingView-webhook"

    def get_endpoint(self) -> None:
        return None

    def get_type(self) -> None:
        return CONFIG_TRADING_VIEW

    async def prepare(self) -> None:
        try:
            self.requires_token = \
                self.config[CONFIG_CATEGORY_SERVICES][CONFIG_TRADING_VIEW][CONFIG_REQUIRE_TRADING_VIEW_TOKEN]
        except KeyError:
            self.requires_token = self.get_default_value()[CONFIG_REQUIRE_TRADING_VIEW_TOKEN]

    @staticmethod
    def get_security_token(pin_code):
        """
        Generate unique token from pin.  This adds a marginal amount of security.
        :param pin_code: the pin code to use
        :return: the generated token
        """
        token = hashlib.sha224(pin_code.encode('utf-8'))
        return token.hexdigest()

    def get_successful_startup_message(self):
        return "", True
