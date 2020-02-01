#  Drakkar-Software OctoBot-Interfaces
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
import threading
from time import sleep

from octobot_commons.logging import register_error_notifier
from octobot_services.constants import CONFIG_WEB, CONFIG_CATEGORY_SERVICES, CONFIG_WEB_IP, CONFIG_WEB_PORT, \
    DEFAULT_SERVER_PORT, DEFAULT_SERVER_IP
from tentacles.Interfaces.web import server_instance, websocket_instance, send_general_notifications
from tentacles.Interfaces.web.constants import BOT_TOOLS_BACKTESTING, BOT_TOOLS_BACKTESTING_SOURCE, \
    BOT_TOOLS_STRATEGY_OPTIMIZER
from tentacles.Interfaces.web.controllers import load_routes
from tentacles.Interfaces.web.websockets import load_namespaces, namespaces
from tentacles.Services import WebService
from octobot_interfaces.web.abstract_web_interface import AbstractWebInterface


class WebInterface(AbstractWebInterface, threading.Thread):
    REQUIRED_SERVICE = WebService

    tools = {
        BOT_TOOLS_BACKTESTING: None,
        BOT_TOOLS_BACKTESTING_SOURCE: None,
        BOT_TOOLS_STRATEGY_OPTIMIZER: None
    }

    def __init__(self, config):
        AbstractWebInterface.__init__(self, config)
        threading.Thread.__init__(self, name=self.get_name())
        self.app = None
        self.srv = None
        self.ctx = None
        self.host = None
        self.port = None
        self._init_web_settings()

    def _init_web_settings(self):
        try:
            self.host = self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB][CONFIG_WEB_IP]
        except KeyError:
            self.host = DEFAULT_SERVER_IP
        try:
            self.port = self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB][CONFIG_WEB_PORT]
        except KeyError:
            self.port = DEFAULT_SERVER_PORT

    def _prepare_websocket(self):
        # handles all namespaces without an explicit error handler
        @websocket_instance.on_error_default
        def default_error_handler(e):
            self.get_logger().error(f"Error with websocket: {e}")
            self.get_logger().exception(e)

        load_namespaces()
        for namespace in namespaces:
            websocket_instance.on_namespace(namespace)

        register_error_notifier(send_general_notifications)

    async def _async_run(self) -> bool:
        # wait bot is ready
        while not self.is_bot_ready():
            sleep(0.1)

        load_routes()
        self._prepare_websocket()

        try:
            websocket_instance.run(server_instance,
                                   host=self.host,
                                   port=self.port,
                                   log_output=False,
                                   debug=False)
            return True
        except Exception as e:
            self.get_logger().exception(f"Fail to start web interface : {e}")
        return False

    async def _inner_start(self) -> bool:
        threading.Thread.start(self)
        return True

    def _prepare_stop(self):
        self.srv.server_close()

    def stop(self):
        self._prepare_stop()
        self.srv.shutdown()
