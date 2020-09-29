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

from time import sleep
from flask_socketio import SocketIO

from octobot_commons.logging import register_error_notifier
from octobot_services.constants import CONFIG_WEB, CONFIG_CATEGORY_SERVICES, CONFIG_WEB_IP, CONFIG_WEB_PORT, \
    DEFAULT_SERVER_PORT, DEFAULT_SERVER_IP, ENV_WEB_PORT, ENV_WEB_ADDRESS, CONFIG_AUTO_OPEN_IN_WEB_BROWSER, \
    ENV_AUTO_OPEN_IN_WEB_BROWSER, CONFIG_WEB_REQUIRES_PASSWORD, CONFIG_WEB_PASSWORD
from octobot_trading.api.exchange import get_exchange_manager_from_exchange_name_and_id, is_exchange_trading, \
    get_exchange_manager_from_exchange_id
from octobot_trading.api.trader import is_trader_simulated
from tentacles.Services.Interfaces.web_interface.constants import BOT_TOOLS_BACKTESTING, BOT_TOOLS_BACKTESTING_SOURCE, \
    BOT_TOOLS_STRATEGY_OPTIMIZER
from tentacles.Services.Interfaces.web_interface.controllers import load_routes
from tentacles.Services.Interfaces.web_interface.login.web_login_manager import WebLoginManager
from tentacles.Services.Interfaces.web_interface.security import register_responses_extra_header
from tentacles.Services.Interfaces.web_interface.websockets import load_namespaces, namespaces
from tentacles.Services.Services_bases import WebService
from octobot_services.interfaces.web.abstract_web_interface import AbstractWebInterface


class WebInterface(AbstractWebInterface, threading.Thread):
    REQUIRED_SERVICES = [WebService]

    tools = {
        BOT_TOOLS_BACKTESTING: None,
        BOT_TOOLS_BACKTESTING_SOURCE: None,
        BOT_TOOLS_STRATEGY_OPTIMIZER: None
    }

    def __init__(self, config):
        AbstractWebInterface.__init__(self, config)
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
        self._init_web_settings()

    async def register_new_exchange_impl(self, exchange_id):
        if exchange_id not in self.registered_exchanges_ids:
            await self._register_on_channels(exchange_id)

    def _init_web_settings(self):
        try:
            self.host = os.getenv(ENV_WEB_ADDRESS, self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB][CONFIG_WEB_IP])
        except KeyError:
            self.host = os.getenv(ENV_WEB_ADDRESS, DEFAULT_SERVER_IP)
        try:
            self.port = int(os.getenv(ENV_WEB_PORT, self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB][CONFIG_WEB_PORT]))
        except KeyError:
            self.port = int(os.getenv(ENV_WEB_PORT, DEFAULT_SERVER_PORT))
        self.session_secret_key = WebService.generate_session_secret_key()
        try:
            self.requires_password = self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB][CONFIG_WEB_REQUIRES_PASSWORD]
        except KeyError:
            pass
        try:
            self.password_hash = self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB][CONFIG_WEB_PASSWORD]
        except KeyError:
            pass
        try:
            env_value = os.getenv(ENV_AUTO_OPEN_IN_WEB_BROWSER, None)
            if env_value is None:
                self.should_open_web_interface = \
                    self.config[CONFIG_CATEGORY_SERVICES][CONFIG_WEB][CONFIG_AUTO_OPEN_IN_WEB_BROWSER]
            else:
                self.should_open_web_interface = env_value.lower() == "true"
        except KeyError:
            self.should_open_web_interface = True

    @staticmethod
    async def _web_trades_callback(exchange: str, exchange_id: str, cryptocurrency: str, symbol: str, trade, old_trade):
        from tentacles.Services.Interfaces.web_interface import send_new_trade
        send_new_trade(trade,
                       is_trader_simulated(get_exchange_manager_from_exchange_name_and_id(exchange, exchange_id)))

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
            if is_exchange_trading(get_exchange_manager_from_exchange_id(exchange_id)):
                from octobot_trading.api.channels import subscribe_to_trades_channel, subscribe_to_ohlcv_channel
                await subscribe_to_trades_channel(self._web_trades_callback, exchange_id)
                await subscribe_to_ohlcv_channel(self._web_ohlcv_empty_callback, exchange_id)
        except ImportError:
            self.logger.error("Watching trade channels requires OctoBot-Trading package installed")

    def _handle_login(self, server_instance):
        self.web_login_manger = WebLoginManager(server_instance, self.requires_password, self.password_hash)

    def _prepare_websocket(self):
        from tentacles.Services.Interfaces.web_interface import server_instance, send_general_notifications
        # handles all namespaces without an explicit error handler
        websocket_instance = SocketIO(server_instance, async_mode="gevent")

        @websocket_instance.on_error_default
        def default_error_handler(e):
            self.logger.exception(e, True, f"Error with websocket: {e}")

        load_namespaces()
        for namespace in namespaces:
            websocket_instance.on_namespace(namespace)

        register_error_notifier(send_general_notifications)
        return websocket_instance

    async def _async_run(self) -> bool:
        # wait bot is ready
        while not self.is_bot_ready():
            sleep(0.05)

        try:
            from tentacles.Services.Interfaces.web_interface import server_instance
            # register session secret key
            server_instance.secret_key = self.session_secret_key
            self._handle_login(server_instance)
            load_routes()
            self.websocket_instance = self._prepare_websocket()

            register_responses_extra_header(server_instance, True)

            if self.should_open_web_interface:
                self._open_web_interface_on_browser()

            self.websocket_instance.run(server_instance,
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
