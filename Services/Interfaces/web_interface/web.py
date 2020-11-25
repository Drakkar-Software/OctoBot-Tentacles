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
import os
import threading
import socket
import webbrowser
import time
import flask_socketio

import octobot_commons.logging as bot_logging
import octobot_services.constants as services_constants
import octobot_services.interfaces as services_interfaces
import octobot_trading.api as trading_api
import tentacles.Services.Interfaces.web_interface.constants as constants
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.security as security
import tentacles.Services.Interfaces.web_interface.websockets as websockets
import tentacles.Services.Interfaces.web_interface as web_interface_root
import tentacles.Services.Services_bases as Service_bases

# import web_interface.controllers to register endpoints
import tentacles.Services.Interfaces.web_interface.controllers


class WebInterface(services_interfaces.AbstractWebInterface, threading.Thread):
    REQUIRED_SERVICES = [Service_bases.WebService]

    tools = {
        constants.BOT_TOOLS_BACKTESTING: None,
        constants.BOT_TOOLS_BACKTESTING_SOURCE: None,
        constants.BOT_TOOLS_STRATEGY_OPTIMIZER: None
    }

    def __init__(self, config):
        services_interfaces.AbstractWebInterface.__init__(self, config)
        threading.Thread.__init__(self, name=self.get_name())
        self.logger = self.get_logger()
        self.app = None
        self.srv = None
        self.ctx = None
        self.host = None
        self.port = None
        self.session_secret_key = None
        self.websocket_instance = None
        self.web_login_manger = None
        self.requires_password = False
        self.password_hash = ""
        # Set services_constants.ENV_CORS_ALLOWED_ORIGINS env variable add stricter cors rules allowed origins
        # example: http://localhost:5000
        # Note: you can specify multiple origins using comma as a separator, ex: http://localhost:5000,https://a.com
        self.cors_allowed_origins = os.getenv(services_constants.ENV_CORS_ALLOWED_ORIGINS, "*")
        if "," in self.cors_allowed_origins:
            self.cors_allowed_origins = self.cors_allowed_origins.split(",")
        self._init_web_settings()

    async def register_new_exchange_impl(self, exchange_id):
        if exchange_id not in self.registered_exchanges_ids:
            await self._register_on_channels(exchange_id)

    def _init_web_settings(self):
        try:
            self.host = os.getenv(services_constants.ENV_WEB_ADDRESS,
                                  self.config[services_constants.CONFIG_CATEGORY_SERVICES]
                                  [services_constants.CONFIG_WEB][services_constants.CONFIG_WEB_IP])
        except KeyError:
            self.host = os.getenv(services_constants.ENV_WEB_ADDRESS, services_constants.DEFAULT_SERVER_IP)
        try:
            self.port = int(os.getenv(services_constants.ENV_WEB_PORT,
                                      self.config[services_constants.CONFIG_CATEGORY_SERVICES]
                                      [services_constants.CONFIG_WEB][services_constants.CONFIG_WEB_PORT]))
        except KeyError:
            self.port = int(os.getenv(services_constants.ENV_WEB_PORT, services_constants.DEFAULT_SERVER_PORT))
        self.session_secret_key = Service_bases.WebService.generate_session_secret_key()
        try:
            self.requires_password = \
                self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_WEB] \
                    [services_constants.CONFIG_WEB_REQUIRES_PASSWORD]
        except KeyError:
            pass
        try:
            self.password_hash = self.config[services_constants.CONFIG_CATEGORY_SERVICES] \
                [services_constants.CONFIG_WEB][services_constants.CONFIG_WEB_PASSWORD]
        except KeyError:
            pass
        try:
            env_value = os.getenv(services_constants.ENV_AUTO_OPEN_IN_WEB_BROWSER, None)
            if env_value is None:
                self.should_open_web_interface = self.config[services_constants.CONFIG_CATEGORY_SERVICES] \
                    [services_constants.CONFIG_WEB][services_constants.CONFIG_AUTO_OPEN_IN_WEB_BROWSER]
            else:
                self.should_open_web_interface = env_value.lower() == "true"
        except KeyError:
            self.should_open_web_interface = True

    @staticmethod
    async def _web_trades_callback(exchange: str, exchange_id: str, cryptocurrency: str, symbol: str, trade, old_trade):
        web_interface_root.send_new_trade(trade,
                                          trading_api.is_trader_simulated(
                                              trading_api.get_exchange_manager_from_exchange_name_and_id(exchange,
                                                                                                         exchange_id)))

    @staticmethod
    async def _web_ohlcv_empty_callback(
            exchange: str,
            exchange_id: str,
            cryptocurrency: str,
            symbol: str,
            time_frame,
            candle
    ):
        pass

    async def _register_on_channels(self, exchange_id):
        try:
            if trading_api.is_exchange_trading(trading_api.get_exchange_manager_from_exchange_id(exchange_id)):
                await trading_api.subscribe_to_trades_channel(self._web_trades_callback, exchange_id)
                await trading_api.subscribe_to_ohlcv_channel(self._web_ohlcv_empty_callback, exchange_id)
        except ImportError:
            self.logger.error("Watching trade channels requires OctoBot-Trading package installed")

    def _handle_login(self, server_instance):
        self.web_login_manger = login.WebLoginManager(server_instance, self.requires_password, self.password_hash)

    def _prepare_websocket(self):
        # handles all namespaces without an explicit error handler
        websocket_instance = flask_socketio.SocketIO(
            web_interface_root.server_instance,
            async_mode="gevent",
            cors_allowed_origins=self.cors_allowed_origins
        )

        @websocket_instance.on_error_default
        def default_error_handler(e):
            self.logger.exception(e, True, f"Error with websocket: {e}")
        for namespace in websockets.namespaces:
            websocket_instance.on_namespace(namespace)

        bot_logging.register_error_notifier(web_interface_root.send_general_notifications)
        return websocket_instance

    async def _async_run(self) -> bool:
        # wait bot is ready
        while not self.is_bot_ready():
            time.sleep(0.05)

        try:
            # register session secret key
            web_interface_root.server_instance.secret_key = self.session_secret_key
            self._handle_login(web_interface_root.server_instance)
            self.websocket_instance = self._prepare_websocket()

            security.register_responses_extra_header(web_interface_root.server_instance, True)

            if self.should_open_web_interface:
                self._open_web_interface_on_browser()

            self.websocket_instance.run(web_interface_root.server_instance,
                                        host=self.host,
                                        port=self.port,
                                        log_output=False,
                                        debug=False)
            return True
        except Exception as e:
            self.logger.exception(e, False, f"Fail to start web interface : {e}")
        return False

    def _open_web_interface_on_browser(self):
        try:
            webbrowser.open(f"http://{socket.gethostbyname(socket.gethostname())}:{self.port}")
        except Exception as e:
            self.logger.warning(f"Impossible to open automatically web interface: {e}")

    async def _inner_start(self) -> bool:
        threading.Thread.start(self)
        return True

    async def stop(self):
        if self.websocket_instance is not None:
            try:
                self.logger.debug("Stopping web interface")
                self.websocket_instance.stop()
            except Exception as e:
                self.logger.exception(f"Fail to stop web interface : {e}", False)
