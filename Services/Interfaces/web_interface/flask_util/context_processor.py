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
import octobot_commons.constants as commons_constants
import octobot.constants as constants
import tentacles.Services.Interfaces.web_interface.models as models
import tentacles.Services.Interfaces.web_interface as web_interface
import tentacles.Services.Interfaces.web_interface.login as web_interface_login
import octobot_trading.util as trading_util


@web_interface.server_instance.context_processor
def context_processor_register():
    def get_tentacle_config_file_content(tentacle_class):
        return models.get_tentacle_config(tentacle_class)

    def get_tentacle_config_schema_content(tentacle_class):
        return models.get_tentacle_config_schema(tentacle_class)

    def get_exchange_holdings(holdings, holding_type):
        return ', '.join(f'{exchange.capitalize()}: {holding[holding_type]}'
                         for exchange, holding in holdings['exchanges'].items())

    def filter_currency_pairs(currency, symbol_list, full_symbol_list, config_symbols):
        currency_key = currency
        symbol = full_symbol_list.get(currency_key, None)
        if symbol is None:
            # try on uppercase
            currency_key = currency.upper()
            symbol = full_symbol_list.get(currency_key, None)
        if symbol is None:
            return symbol_list
        filtered_symbol = [s for s in symbol_list
                    if full_symbol_list[currency_key][models.SYMBOL_KEY] in symbol_util.split_symbol(s)]
        return (filtered_symbol + [s for s in config_symbols[currency]["pairs"]
                                                    if s in symbol_list and s not in filtered_symbol])

    def get_profile_traded_pairs_by_currency(profile):
        return {
            currency: val[commons_constants.CONFIG_CRYPTO_PAIRS]
            for currency, val in profile.config[commons_constants.CONFIG_CRYPTO_CURRENCIES].items()
            if commons_constants.CONFIG_CRYPTO_PAIRS in val
                and val[commons_constants.CONFIG_CRYPTO_PAIRS]
                and trading_util.is_currency_enabled(profile.config, currency, True)
        }

    def get_profile_exchanges(profile):
        return [
            exchange_name
            for exchange_name in profile.config[commons_constants.CONFIG_EXCHANGES]
            if profile.config[commons_constants.CONFIG_EXCHANGES][exchange_name].get(
                commons_constants.CONFIG_ENABLED_OPTION, True)
        ]

    def is_real_trading(profile):
        if trading_util.is_trader_enabled(profile.config):
            return True
        return False

    def get_enabled_trader(profile):
        if is_real_trading(profile):
            return "Real trading"
        if trading_util.is_trader_simulator_enabled(profile.config):
            return "Simulated trading"
        return ""

    def get_filtered_list(origin_list, filtering_list):
        return [
            element
            for element in origin_list
            if element in filtering_list
        ]

    return dict(
        LAST_UPDATED_STATIC_FILES=web_interface.LAST_UPDATED_STATIC_FILES,
        OCTOBOT_WEBSITE_URL=constants.OCTOBOT_WEBSITE_URL,
        OCTOBOT_DOCS_URL=constants.OCTOBOT_DOCS_URL,
        DEVELOPER_DOCS_URL=constants.DEVELOPER_DOCS_URL,
        EXCHANGES_DOCS_URL=constants.EXCHANGES_DOCS_URL,
        OCTOBOT_FEEDBACK_URL=constants.OCTOBOT_FEEDBACK,
        OCTOBOT_COMMUNITY_URL=constants.OCTOBOT_COMMUNITY_URL,
        IS_DEMO=constants.IS_DEMO,
        get_tentacle_config_file_content=get_tentacle_config_file_content,
        get_tentacle_config_schema_content=get_tentacle_config_schema_content,
        filter_currency_pairs=filter_currency_pairs,
        get_exchange_holdings=get_exchange_holdings,
        get_profile_traded_pairs_by_currency=get_profile_traded_pairs_by_currency,
        get_profile_exchanges=get_profile_exchanges,
        get_enabled_trader=get_enabled_trader,
        get_filtered_list=get_filtered_list,
        get_current_profile=models.get_current_profile,
        is_real_trading=is_real_trading,
        is_login_required=web_interface_login.is_login_required,
        is_authenticated=web_interface_login.is_authenticated,
    )
