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
import functools

import octobot_commons.tentacles_management as tentacles_management

import octobot_trading.exchanges as exchanges
import octobot_trading.modes

import octobot_tentacles_manager.api


def get_config_history_propagated_tentacles_config_keys(tentacle: str) -> list[str]:
    tentacle_class = octobot_tentacles_manager.api.get_tentacle_class_from_string(tentacle)
    return tentacle_class.get_config_history_propagated_tentacles_config_keys()


# cached to avoid calling default_parents_inspection when unnecessary
@functools.lru_cache(maxsize=128)
def is_trading_mode_tentacle(tentacle_name: str) -> bool:
    tentacle_class = octobot_tentacles_manager.api.get_tentacle_class_from_string(tentacle_name)
    return tentacles_management.default_parents_inspection(tentacle_class, octobot_trading.modes.AbstractTradingMode)


# cached to avoid calling default_parents_inspection when unnecessary
@functools.lru_cache(maxsize=128)
def is_exchange_tentacle(tentacle_name: str) -> bool:
    tentacle_class = octobot_tentacles_manager.api.get_tentacle_class_from_string(tentacle_name)
    return tentacles_management.default_parents_inspection(tentacle_class, exchanges.RestExchange)
