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

import copy
import logging
import time
import abc
import os.path
import flask
import flask_cors
from flask_caching import Cache

import tentacles.Services.Interfaces.web_interface.api as api
import octobot_commons.logging as bot_logging

server_instance = flask.Flask(__name__)
server_instance.config['SEND_FILE_MAX_AGE_DEFAULT'] = 604800
cache = Cache(config={"CACHE_TYPE": "SimpleCache"})


class Notifier:
    @abc.abstractmethod
    def send_notifications(self) -> bool:
        raise NotImplementedError("send_notifications is not implemented")


notifiers = {}


def register_notifier(notification_key, notifier):
    if notification_key not in notifiers:
        notifiers[notification_key] = []
    notifiers[notification_key].append(notifier)


GENERAL_NOTIFICATION_KEY = "general_notifications"
BACKTESTING_NOTIFICATION_KEY = "backtesting_notifications"
DATA_COLLECTOR_NOTIFICATION_KEY = "data_collector_notifications"
STRATEGY_OPTIMIZER_NOTIFICATION_KEY = "strategy_optimizer_notifications"
DASHBOARD_NOTIFICATION_KEY = "dashboard_notifications"

import tentacles.Services.Interfaces.web_interface.flask_util as flask_util

# Override system configuration content types
flask_util.init_content_types()
server_instance.json = flask_util.FloatDecimalJSONProvider(server_instance)

# Set CORS policy
if flask_util.get_user_defined_cors_allowed_origins() != "*":
    # never allow "*" as allowed origin, prefer not setting it if user did not specifically set origins
    flask_cors.CORS(server_instance, origins=flask_util.get_user_defined_cors_allowed_origins())

# Make WebInterface visible to imports
from tentacles.Services.Interfaces.web_interface.web import WebInterface

import tentacles.Services.Interfaces.web_interface.advanced_controllers as advanced_controllers

server_instance.register_blueprint(advanced_controllers.advanced)
server_instance.register_blueprint(api.api)

# disable server logging
loggers = ['engineio.server', 'socketio.server', 'geventwebsocket.handler']
for logger in loggers:
    logging.getLogger(logger).setLevel(logging.WARNING)

registered_plugins = []
notifications = []

matrix_history = []
symbol_data_history = {}
portfolio_value_history = {
    "real_value": [],
    "simulated_value": [],
    "timestamp": []
}

TIME_AXIS_TITLE = "Time"


def dir_last_updated(folder):
    return str(max(os.path.getmtime(os.path.join(root_path, f))
                   for root_path, dirs, files in os.walk(folder)
                   for f in files))


LAST_UPDATED_STATIC_FILES = dir_last_updated(os.path.join(os.path.dirname(__file__), "static"))


def update_registered_plugins(plugins):
    global LAST_UPDATED_STATIC_FILES
    last_update_time = float(LAST_UPDATED_STATIC_FILES)
    for plugin in plugins:
        if plugin not in registered_plugins:
            registered_plugins.append(plugin)
            if plugin.static_folder:
                last_update_time = max(last_update_time, float(dir_last_updated(plugin.static_folder)))
    LAST_UPDATED_STATIC_FILES = last_update_time


# register flask utilities
import tentacles.Services.Interfaces.web_interface.flask_util


def add_to_matrix_history(matrix):
    matrix_history.append({
        "matrix": copy.deepcopy(matrix.get_matrix()),
        "timestamp": time.time()
    })


def add_to_portfolio_value_history(real_value, simulated_value):
    portfolio_value_history["real_value"].append(real_value)
    portfolio_value_history["simulated_value"].append(simulated_value)
    portfolio_value_history["timestamp"].append(time.time())


def add_to_symbol_data_history(symbol, data, time_frame, force_data_reset=False):
    if symbol not in symbol_data_history:
        symbol_data_history[symbol] = {}
    symbol_data_history[symbol][time_frame] = data


def flush_notifications():
    notifications.clear()


def _send_notification(notification_key, **kwargs) -> bool:
    if notification_key in notifiers:
        return any(notifier.all_clients_send_notifications(**kwargs)
                   for notifier in notifiers[notification_key])
    return False


def send_general_notifications(**kwargs):
    if _send_notification(GENERAL_NOTIFICATION_KEY, **kwargs):
        flush_notifications()


def send_backtesting_status(**kwargs):
    _send_notification(BACKTESTING_NOTIFICATION_KEY, **kwargs)


def send_data_collector_status(**kwargs):
    _send_notification(DATA_COLLECTOR_NOTIFICATION_KEY, **kwargs)


def send_strategy_optimizer_status(**kwargs):
    _send_notification(STRATEGY_OPTIMIZER_NOTIFICATION_KEY, **kwargs)


def send_new_trade(dict_new_trade, is_simulated):
    if is_simulated:
        _send_notification(DASHBOARD_NOTIFICATION_KEY, simulated_trades=[dict_new_trade])
    else:
        _send_notification(DASHBOARD_NOTIFICATION_KEY, real_trades=[dict_new_trade])


async def add_notification(level, title, message, sound=None):
    notifications.append({
        "Level": level.value,
        "Title": title,
        "Message": message,
        "Sound": sound
    })
    send_general_notifications()


def get_matrix_history():
    return matrix_history


def get_portfolio_value_history():
    return portfolio_value_history


def get_symbol_data_history(symbol, time_frame):
    return symbol_data_history[symbol][time_frame]


def get_notifications():
    return notifications


def get_logs():
    return bot_logging.logs_database[bot_logging.LOG_DATABASE]


def get_errors_count():
    return bot_logging.logs_database[bot_logging.LOG_NEW_ERRORS_COUNT]


def flush_errors_count():
    bot_logging.reset_errors_count()
