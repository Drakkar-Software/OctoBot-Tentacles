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

import copy

import octobot.constants as octobot_contants
import octobot_commons.constants as commons_constants
import octobot_services.interfaces.util as interfaces_util
import octobot_commons.config_manager as config_manager
import tentacles.Services.Interfaces.web_interface.constants as constants


def _symbol_in_currencies_config(config, symbol):
    return any(symbol in crypto_currency_data[commons_constants.CONFIG_CRYPTO_PAIRS]
               for crypto_currency_data in config[commons_constants.CONFIG_CRYPTO_CURRENCIES].values())


def get_watched_symbols():
    config = interfaces_util.get_edited_config()
    if constants.CONFIG_WATCHED_SYMBOLS not in config:
        config[constants.CONFIG_WATCHED_SYMBOLS] = []
    else:
        for symbol in copy.copy(config[constants.CONFIG_WATCHED_SYMBOLS]):
            if not _symbol_in_currencies_config(config, symbol):
                config[constants.CONFIG_WATCHED_SYMBOLS].remove(symbol)
    return config[constants.CONFIG_WATCHED_SYMBOLS]


def add_watched_symbol(symbol):
    watched_symbols = get_watched_symbols()
    watched_symbols.append(symbol)
    return _save_edition()


def remove_watched_symbol(symbol):
    watched_symbols = get_watched_symbols()
    if symbol in watched_symbols:
        watched_symbols.remove(symbol)
    return _save_edition()


def _save_edition():
    config_manager.simple_save_config_update(interfaces_util.get_edited_config(),
                                             schema_file=octobot_contants.CONFIG_FILE_SCHEMA)
    return True
