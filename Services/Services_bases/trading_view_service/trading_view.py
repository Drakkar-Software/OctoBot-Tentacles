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
import uuid

import octobot_services.constants as services_constants
import octobot_services.services as services
import octobot.constants as constants


class TradingViewService(services.AbstractService):
    def __init__(self):
        super().__init__()
        self.requires_token = None
        self.token = None
        self._webhook_url = None

    @staticmethod
    def is_setup_correctly(config):
        return True

    @staticmethod
    def get_is_enabled(config):
        return True

    def has_required_configuration(self):
        return True

    def get_required_config(self):
        return [services_constants.CONFIG_REQUIRE_TRADING_VIEW_TOKEN,
                services_constants.CONFIG_TRADING_VIEW_TOKEN]

    def get_fields_description(self):
        return {
            services_constants.CONFIG_REQUIRE_TRADING_VIEW_TOKEN: "When enabled the Trading View webhook will require your "
                                                                  "tradingview.com token to process any signal.",
            services_constants.CONFIG_TRADING_VIEW_TOKEN: "Your personal unique tradingview.com token. Can be used to ensure only your "
                                                          "Trading View signals are triggering your OctoBot in case someone else get "
                                                          "your webhook link. You can change it at any moment but remember to change it "
                                                          "on your tradingview.com signal account as well."
        }

    def get_default_value(self):
        return {
            services_constants.CONFIG_REQUIRE_TRADING_VIEW_TOKEN: False,
            services_constants.CONFIG_TRADING_VIEW_TOKEN: self.get_security_token(uuid.uuid4().hex)
        }

    def get_read_only_info(self):
        return {
            "Webhook url:": self._webhook_url
        } if self._webhook_url else {}

    @classmethod
    def get_help_page(cls) -> str:
        return f"{constants.OCTOBOT_DOCS_URL}/webhooks/tradingview-webhook"

    def get_endpoint(self) -> None:
        return None

    def get_type(self) -> None:
        return services_constants.CONFIG_TRADING_VIEW

    def get_website_url(self):
        return "https://www.tradingview.com/"

    def get_logo(self):
        return "https://in.tradingview.com/static/images/favicon.ico"

    async def prepare(self) -> None:
        try:
            self.requires_token = \
                self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_TRADING_VIEW][
                    services_constants.CONFIG_REQUIRE_TRADING_VIEW_TOKEN]
            self.token = \
                self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_TRADING_VIEW][
                    services_constants.CONFIG_TRADING_VIEW_TOKEN]
        except KeyError:
            if self.requires_token is None:
                self.requires_token = self.get_default_value()[services_constants.CONFIG_REQUIRE_TRADING_VIEW_TOKEN]
            if self.token is None:
                self.token = self.get_default_value()[services_constants.CONFIG_TRADING_VIEW_TOKEN]
            # save new values into config file
            updated_config = {
                services_constants.CONFIG_REQUIRE_TRADING_VIEW_TOKEN: self.requires_token,
                services_constants.CONFIG_TRADING_VIEW_TOKEN: self.token
            }
            self.save_service_config(services_constants.CONFIG_TRADING_VIEW, updated_config)

    @staticmethod
    def get_security_token(pin_code):
        """
        Generate unique token from pin.  This adds a marginal amount of security.
        :param pin_code: the pin code to use
        :return: the generated token
        """
        token = hashlib.sha224(pin_code.encode('utf-8'))
        return token.hexdigest()

    def register_webhook_url(self, webhook_url):
        self._webhook_url = webhook_url

    def get_successful_startup_message(self):
        return "", True
