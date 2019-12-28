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
from werkzeug.serving import make_server

from octobot_commons.logging.logging_util import get_logger
import threading
from time import sleep

from octobot_services.constants import CONFIG_WEB, CONFIG_CATEGORY_SERVICES, CONFIG_WEB_IP, CONFIG_WEB_PORT
from tentacles.Interfaces.interfaces.web import server_instance
from tentacles.Interfaces.interfaces.web.constants import BOT_TOOLS_BACKTESTING, BOT_TOOLS_BACKTESTING_SOURCE, \
    BOT_TOOLS_STRATEGY_OPTIMIZER
from tentacles.Interfaces.interfaces.web.controllers import load_routes

from octobot_interfaces.web.abstract_web_interface import AbstractWebInterface


class WebInterface(AbstractWebInterface, threading.Thread):

    tools = {
        BOT_TOOLS_BACKTESTING: None,
        BOT_TOOLS_BACKTESTING_SOURCE: None,
        BOT_TOOLS_STRATEGY_OPTIMIZER: None
    }

    def __init__(self, config):
        AbstractWebInterface.__init__(self, config)
        threading.Thread.__init__(self)
        self.app = None
        self.srv = None
        self.ctx = None

    def _prepare_server(self):
        try:
            self.srv = make_server(host=self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB][CONFIG_WEB_IP],
                                   port=self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB][CONFIG_WEB_PORT],
                                   threaded=True,
                                   app=server_instance)
            self.ctx = server_instance.app_context()
            self.ctx.push()
        except OSError as e:
            self.srv = None
            self.get_logger().exception(f"Fail to start web interface : {e}")

    def run(self):
        # wait bot is ready
        while not self.is_bot_ready():
            sleep(0.1)

        # Define the WSGI server object
        self._prepare_server()

        load_routes()

        if self.srv:
            self.srv.serve_forever()

    def start(self):
        # start thread
        threading.Thread.start(self)

    def _prepare_stop(self):
        self.srv.server_close()

    def stop(self):
        self._prepare_stop()
        self.srv.shutdown()
