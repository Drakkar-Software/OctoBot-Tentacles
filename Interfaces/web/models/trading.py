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

from octobot_interfaces.util.bot import get_bot
from octobot_interfaces.util.util import get_exchange_managers
from octobot_trading.api.exchange import get_exchange_manager_from_exchange_name, get_watched_timeframes, \
    get_exchange_name


def get_exchange_time_frames(exchange_name):
    try:
        exchange_manager = get_exchange_manager_from_exchange_name(exchange_name)
        return get_watched_timeframes(exchange_manager), get_exchange_name(exchange_manager)
    except KeyError:
        return [], ""


def get_evaluation(symbol, exchange_name):
    try:
        if exchange_name:
            return "N/A"
            # TODO: return trading mode state
            # exchange_manager = get_exchange_manager_from_exchange_name(exchange_name)
            # symbol_evaluator = get_bot().get_symbol_evaluator_list()[symbol]
            # return (
            #     ",".join([
            #         f"{dec.get_state().name}: {round(dec.get_final_eval(), 4)}"
            #         if dec.get_state() is not None else "N/A"
            #         for dec in symbol_evaluator.get_deciders(exchange)
            #     ])
            # )
    except KeyError:
        return "N/A"
