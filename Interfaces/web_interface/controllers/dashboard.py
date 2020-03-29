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

from flask import jsonify

from tentacles.Interfaces.web_interface import server_instance
from tentacles.Interfaces.web_interface.models.dashboard import get_currency_price_graph_update, \
    get_value_from_dict_or_string, get_first_symbol_data, get_watched_symbol_data
from octobot_interfaces.util.profitability import get_global_profitability
from octobot_commons.pretty_printer import PrettyPrinter


@server_instance.route('/dashboard/currency_price_graph_update/<exchange_id>/<symbol>/<time_frame>/<mode>')
def currency_price_graph_update(exchange_id, symbol, time_frame, mode="live"):
    in_backtesting = mode != "live"
    return jsonify(get_currency_price_graph_update(exchange_id,
                                                   get_value_from_dict_or_string(symbol),
                                                   time_frame,
                                                   backtesting=in_backtesting))


@server_instance.route('/dashboard/first_symbol')
def first_symbol():
    return jsonify(get_first_symbol_data())


@server_instance.route('/dashboard/watched_symbol/<symbol>')
def watched_symbol(symbol):
    return jsonify(get_watched_symbol_data(symbol))
