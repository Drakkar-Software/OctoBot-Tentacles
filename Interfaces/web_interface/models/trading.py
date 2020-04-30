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
from octobot_interfaces.util.util import get_exchange_managers
from octobot_trading.api.exchange import get_watched_timeframes, get_exchange_name, \
    get_exchange_manager_from_exchange_id, get_exchange_manager_from_exchange_name_and_id
from octobot_trading.api.modes import get_trading_modes, get_trading_mode_symbol, get_trading_mode_current_state
from octobot_trading.api.profitability import get_initializing_currencies_prices


def get_exchange_time_frames(exchange_id):
    try:
        exchange_manager = get_exchange_manager_from_exchange_id(exchange_id)
        return get_watched_timeframes(exchange_manager), get_exchange_name(exchange_manager)
    except KeyError:
        return [], ""


def get_initializing_currencies_prices_set():
    initializing_currencies = set()
    for exchange_manager in get_exchange_managers():
        initializing_currencies = initializing_currencies.union(get_initializing_currencies_prices(exchange_manager))
    return initializing_currencies


def get_evaluation(symbol, exchange_name, exchange_id):
    try:
        if exchange_name:
            exchange_manager = get_exchange_manager_from_exchange_name_and_id(exchange_name, exchange_id)
            for trading_mode in get_trading_modes(exchange_manager):
                if get_trading_mode_symbol(trading_mode) == symbol:
                    state_desc, val_state = get_trading_mode_current_state(trading_mode)
                    try:
                        val_state = round(val_state)
                    except TypeError:
                        pass
                    return f"{state_desc.replace('_', ' ')}, {val_state}"
    except KeyError:
        pass
    return "N/A"
