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
import socket
import uuid

from octobot_commons.constants import CONFIG_ENABLED_OPTION
from octobot_services.constants import CONFIG_WEB, CONFIG_CATEGORY_SERVICES, CONFIG_SERVICE_INSTANCE, \
    CONFIG_WEB_PORT, DEFAULT_SERVER_PORT, ENV_WEB_PORT, ENV_WEB_ADDRESS, CONFIG_AUTO_OPEN_IN_WEB_BROWSER, \
    CONFIG_WEB_REQUIRES_PASSWORD, CONFIG_WEB_SESSION_SECRET_KEY, CONFIG_WEB_PASSWORD
from octobot_services.services.abstract_service import AbstractService


class WebService(AbstractService):
    BACKTESTING_ENABLED = True

    def __init__(self):
        super().__init__()
        self.web_app = None
        self.requires_password = None
        self.session_secret_key = None
        self.password_hash = None

    def get_fields_description(self):
        return {
            CONFIG_WEB_PORT: "Port to access your OctoBot web interface from.",
            CONFIG_AUTO_OPEN_IN_WEB_BROWSER: "When enabled, OctoBot will open the web interface on your web "
                                             "browser upon startup.",
            CONFIG_WEB_REQUIRES_PASSWORD: "When enabled, OctoBot web interface will be protected by a password. "
                                          "Failing 10 times to enter this password will block the user and require "
                                          "OctoBot restart before being able to retry to authenticate.",
            CONFIG_WEB_PASSWORD: "Password to enter to access this OctoBot when password protection is enabled. "
                                 "Only a hash of this password will be stored."
        }

    def get_default_value(self):
        return {
            CONFIG_WEB_PORT: DEFAULT_SERVER_PORT,
            CONFIG_AUTO_OPEN_IN_WEB_BROWSER: True,
            CONFIG_WEB_REQUIRES_PASSWORD: False,
            CONFIG_WEB_PASSWORD: ""
        }

    def get_required_config(self):
        return [CONFIG_WEB_PORT]

    @classmethod
    def get_help_page(cls) -> str:
        return "https://github.com/Drakkar-Software/OctoBot/wiki/Web-interface#web-interface"

    @staticmethod
    def is_setup_correctly(config):
        return CONFIG_WEB in config[CONFIG_CATEGORY_SERVICES] \
            and CONFIG_SERVICE_INSTANCE in config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB]

    @staticmethod
    def get_is_enabled(config):
        # allow to disable web interface from config, enabled by default otherwise
        try:
            return config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB][CONFIG_ENABLED_OPTION]
        except KeyError:
            return True

    def has_required_configuration(self):
        return self.get_is_enabled(self.config)

    def get_endpoint(self) -> None:
        return self.web_app

    def get_type(self) -> None:
        return CONFIG_WEB

    @staticmethod
    def generate_session_secret_key():
        return uuid.uuid4().hex

    async def prepare(self) -> None:
        try:
            self.requires_password = \
                self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB][CONFIG_WEB_REQUIRES_PASSWORD]
            self.session_secret_key = self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB][CONFIG_WEB_SESSION_SECRET_KEY]
            self.password_hash = self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB][CONFIG_WEB_PASSWORD]
        except KeyError:
            if self.requires_password is None:
                self.requires_password = self.get_default_value()[CONFIG_WEB_REQUIRES_PASSWORD]
            if self.session_secret_key is None:
                # generate a new unique session secret key if not existing already to ensure security
                # https://flask.palletsprojects.com/en/1.1.x/quickstart/#sessions
                self.session_secret_key = self.generate_session_secret_key()
            if self.password_hash is None:
                self.password_hash = self.get_default_value()[CONFIG_WEB_PASSWORD]
            # save new values into config file
            updated_config = {
                CONFIG_WEB_REQUIRES_PASSWORD: self.requires_password,
                CONFIG_WEB_SESSION_SECRET_KEY: self.session_secret_key,
                CONFIG_WEB_PASSWORD: self.password_hash
            }
            self.save_service_config(CONFIG_WEB, updated_config, update=True)

    @staticmethod
    def get_should_warn():
        return False

    def stop(self):
        if self.web_app:
            self.web_app.stop()

    def _get_web_server_url(self):
        try:
            port = os.getenv(ENV_WEB_PORT, self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB][CONFIG_WEB_PORT])
        except KeyError:
            port = os.getenv(ENV_WEB_PORT, DEFAULT_SERVER_PORT)
        return f"{os.getenv(ENV_WEB_ADDRESS, socket.gethostbyname(socket.gethostname()))}:{port}"

    def get_successful_startup_message(self):
        return f"Interface successfully initialized and accessible at: http://{self._get_web_server_url()}.", True
