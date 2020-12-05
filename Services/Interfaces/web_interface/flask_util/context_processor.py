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

import octobot_commons.symbol_util as symbol_util
import octobot.constants as constants
import tentacles.Services.Interfaces.web_interface.models as models
import tentacles.Services.Interfaces.web_interface as web_interface


@web_interface.server_instance.context_processor
def context_processor_register():
    def get_tentacle_config_file_content(tentacle_class):
        return models.get_tentacle_config(tentacle_class)

    def get_tentacle_config_schema_content(tentacle_class):
        return models.get_tentacle_config_schema(tentacle_class)

    def filter_currency_pairs(currency, symbol_list, full_symbol_list):
        currency_key = currency
        symbol = full_symbol_list.get(currency_key, None)
        if symbol is None:
            # try on uppercase
            currency_key = currency.upper()
            symbol = full_symbol_list.get(currency_key, None)
        if symbol is None:
            return symbol_list
        return [s for s in symbol_list
                if full_symbol_list[currency_key][models.SYMBOL_KEY] in symbol_util.split_symbol(s)]

    return dict(
        LAST_UPDATED_STATIC_FILES=web_interface.LAST_UPDATED_STATIC_FILES,
        OCTOBOT_WIKI_URL=constants.OCTOBOT_WIKI_URL,
        get_tentacle_config_file_content=get_tentacle_config_file_content,
        get_tentacle_config_schema_content=get_tentacle_config_schema_content,
        filter_currency_pairs=filter_currency_pairs
    )
