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

import octobot.constants as octobot_contants
import octobot_commons.config_manager as config_manager
import octobot_services.interfaces.util as interfaces_util
import tentacles.Services.Interfaces.web_interface.models as models


def add_watched_symbol(symbol):
    watched_symbols = models.get_watched_symbols()
    watched_symbols.append(symbol)
    return _save_edition()


def remove_watched_symbol(symbol):
    watched_symbols = models.get_watched_symbols()
    if symbol in watched_symbols:
        watched_symbols.remove(symbol)
    return _save_edition()


def _save_edition():
    config_manager.simple_save_config_update(interfaces_util.get_edited_config(),
                                             schema_file=octobot_contants.CONFIG_FILE_SCHEMA)
    return True
