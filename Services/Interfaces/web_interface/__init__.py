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
import flask

import tentacles.Services.Interfaces.web_interface.api as api
import octobot_commons.logging as bot_logging

server_instance = flask.Flask(__name__)

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
DASHBOARD_NOTIFICATION_KEY = "dashboard_notifications"

# Make WebInterface visible to imports
from tentacles.Services.Interfaces.web_interface.web import WebInterface

import tentacles.Services.Interfaces.web_interface.advanced_controllers as advanced_controllers

server_instance.register_blueprint(advanced_controllers.advanced)
server_instance.register_blueprint(api.api)

# disable server logging
loggers = ['engineio.server', 'socketio.server', 'geventwebsocket.handler']
for logger in loggers:
    logging.getLogger(logger).setLevel(logging.WARNING)

notifications = []

matrix_history = []
symbol_data_history = {}
portfolio_value_history = {
    "real_value": [],
    "simulated_value": [],
    "timestamp": []
}

TIME_AXIS_TITLE = "Time"


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

    # TODO: handle candles history (display candles on old trades,
    #  a way to solve this would be to keep more candle before flushing them)
    # import numpy
    # from config import PriceIndexes
    # if force_data_reset or time_frame not in symbol_data_history[symbol]:
    #     symbol_data_history[symbol][time_frame] = data
    # else:
    #     # merge new data into current data
    #     # find index from where data is new
    #     new_data_index = 0
    #     candle_times = data[PriceIndexes.IND_PRICE_TIME.value]
    #     current_candle_list = symbol_data_history[symbol][time_frame]
    #     for i in range(1, len(candle_times)):
    #         if candle_times[-i] > current_candle_list[PriceIndexes.IND_PRICE_TIME.value][-1]:
    #             new_data_index = i
    #         else:
    #             # update last candle if necessary, then break loop
    #             if current_candle_list[PriceIndexes.IND_PRICE_TIME.value][-1] == candle_times[-i]:
    #                 current_candle_list[PriceIndexes.IND_PRICE_CLOSE.value][-1] = \
    #                     data[PriceIndexes.IND_PRICE_CLOSE.value][-i]
    #                 current_candle_list[PriceIndexes.IND_PRICE_HIGH.value][-1] = \
    #                     data[PriceIndexes.IND_PRICE_HIGH.value][-i]
    #                 current_candle_list[PriceIndexes.IND_PRICE_LOW.value][-1] = \
    #                     data[PriceIndexes.IND_PRICE_LOW.value][-i]
    #                 current_candle_list[PriceIndexes.IND_PRICE_VOL.value][-1] = \
    #                     data[PriceIndexes.IND_PRICE_VOL.value][-i]
    #             break
    #     if new_data_index > 0:
    #         data_list = [None] * len(PriceIndexes)
    #         for i, _ in enumerate(data):
    #             data_list[i] = data[i][-new_data_index:]
    #         new_data = numpy.array(data_list)
    #         symbol_data_history[symbol][time_frame] = numpy.concatenate((symbol_data_history[symbol][time_frame],
    #                                                                      new_data), axis=1)


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


def send_new_trade(dict_new_trade, is_simulated):
    if is_simulated:
        _send_notification(DASHBOARD_NOTIFICATION_KEY, simulated_trades=[dict_new_trade])
    else:
        _send_notification(DASHBOARD_NOTIFICATION_KEY, real_trades=[dict_new_trade])


async def add_notification(level, title, message):
    notifications.append({
        "Level": level.value,
        "Title": title,
        "Message": message
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

