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
from abc import abstractmethod

import flask
from tentacles.Interfaces.web.api import api
from octobot_commons.logging import logs_database, reset_errors_count, LOG_DATABASE, LOG_NEW_ERRORS_COUNT
from flask_socketio import SocketIO

server_instance = flask.Flask(__name__)
websocket_instance = SocketIO(server_instance)

from tentacles.Interfaces.web.advanced_controllers import advanced

server_instance.register_blueprint(advanced)
server_instance.register_blueprint(api)

# disable server logging
loggers = ['engineio.server', 'socketio.server']
for logger in loggers:
    logging.getLogger(logger).setLevel(logging.WARNING)

notifications = []


class Notifier:
    @abstractmethod
    def send_notifications(self) -> bool:
        raise NotImplementedError("send_notifications is not implemented")


GENERAL_NOTIFICATION_KEY = "general_notifications"
BACKTESTING_NOTIFICATION_KEY = "backtesting_notifications"
notifiers = {}

matrix_history = []
symbol_data_history = {}
portfolio_value_history = {
    "real_value": [],
    "simulated_value": [],
    "timestamp": []
}

TIME_AXIS_TITLE = "Time"


def register_notifier(notification_key, notifier):
    if notification_key not in notifiers:
        notifiers[notification_key] = []
    notifiers[notification_key].append(notifier)


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


def _send_notification(notification_key) -> bool:
    if notification_key in notifiers:
        return any(notifier.all_clients_send_notifications()
                   for notifier in notifiers[notification_key])
    return False


def send_general_notifications():
    if _send_notification(GENERAL_NOTIFICATION_KEY):
        flush_notifications()


def send_backtesting_status():
    _send_notification(BACKTESTING_NOTIFICATION_KEY)


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
    return logs_database[LOG_DATABASE]


def get_errors_count():
    return logs_database[LOG_NEW_ERRORS_COUNT]


def flush_errors_count():
    reset_errors_count()
