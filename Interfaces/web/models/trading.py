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

from octobot_trading.api.exchange import get_watched_timeframes, get_exchange_name, \
    get_exchange_manager_from_exchange_id, get_exchange_manager_from_exchange_name_and_id
from octobot_trading.api.modes import get_trading_modes, get_trading_mode_symbol, get_trading_mode_current_state


def get_exchange_time_frames(exchange_id):
    try:
        exchange_manager = get_exchange_manager_from_exchange_id(exchange_id)
        return get_watched_timeframes(exchange_manager), get_exchange_name(exchange_manager)
    except KeyError:
        return [], ""


def get_evaluation(symbol, exchange_name):
    try:
        if exchange_name:
            exchange_manager = get_exchange_manager_from_exchange_name_and_id(exchange_name, exchange_id)
            for trading_mode in get_trading_modes(exchange_manager):
                if get_trading_mode_symbol(trading_mode) == symbol:
                    state_desc, state = get_trading_mode_current_state(trading_mode)
                    return f"{state_desc.replace('_', ' ')}, {round(state)}"
    except KeyError:
        pass
    return "N/A"
