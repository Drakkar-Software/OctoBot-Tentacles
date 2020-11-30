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

import octobot_services.interfaces.util as interfaces_util
import octobot_trading.api as trading_api


def get_exchange_time_frames(exchange_id):
    try:
        exchange_manager = trading_api.get_exchange_manager_from_exchange_id(exchange_id)
        return trading_api.get_watched_timeframes(exchange_manager), trading_api.get_exchange_name(exchange_manager)
    except KeyError:
        return [], ""


def get_initializing_currencies_prices_set():
    initializing_currencies = set()
    for exchange_manager in interfaces_util.get_exchange_managers():
        initializing_currencies = initializing_currencies.union(
            trading_api.get_initializing_currencies_prices(exchange_manager))
    return initializing_currencies


def get_evaluation(symbol, exchange_name, exchange_id):
    try:
        if exchange_name:
            exchange_manager = trading_api.get_exchange_manager_from_exchange_name_and_id(exchange_name, exchange_id)
            for trading_mode in trading_api.get_trading_modes(exchange_manager):
                if trading_api.get_trading_mode_symbol(trading_mode) == symbol:
                    state_desc, val_state = trading_api.get_trading_mode_current_state(trading_mode)
                    try:
                        val_state = round(val_state)
                    except TypeError:
                        pass
                    return f"{state_desc.replace('_', ' ')}, {val_state}"
    except KeyError:
        pass
    return "N/A"


def get_exchanges_load():
    return {
        trading_api.get_exchange_name(exchange_manager): {
            "load": trading_api.get_currently_handled_pair_with_time_frame(exchange_manager),
            "max_load": trading_api.get_max_handled_pair_with_time_frame(exchange_manager),
            "overloaded": trading_api.is_overloaded(exchange_manager)
        }
        for exchange_manager in interfaces_util.get_exchange_managers()
    }
