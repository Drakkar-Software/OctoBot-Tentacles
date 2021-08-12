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
import octobot_services.interfaces.util as interfaces_util
import tentacles.Services.Interfaces.web_interface.models as models


def add_watched_symbol(symbol):
    watched_symbols = models.get_watched_symbols()
    if symbol not in watched_symbols:
        watched_symbols.append(symbol)
        return _save_edition()
    return True


def remove_watched_symbol(symbol):
    watched_symbols = models.get_watched_symbols()
    try:
        watched_symbols.remove(symbol)
        return _save_edition()
    except ValueError:
        return True


def _save_edition():
    interfaces_util.get_edited_config(dict_only=False).save(schema_file=octobot_contants.CONFIG_FILE_SCHEMA)
    return True
