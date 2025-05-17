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
import octobot_commons.constants as commons_constants
import octobot_commons.symbols as symbol_utils
import octobot_commons.dict_util as dict_util
import octobot_commons.logging as commons_logging
import octobot_services.interfaces.util as interfaces_util
import tentacles.Services.Interfaces.web_interface.models.json_schemas as json_schemas
import octobot_tentacles_manager.api


_LOGGER_NAME = "MMConfigurationModel"


def save_market_making_configuration(
    enabled_exchange: str,
    trading_pair: str,
    exchange_configurations: list[dict],
    trading_simulator_configuration: dict,
    simulated_portfolio_configuration: list[dict],
    trading_mode_name: str,
    trading_mode_configuration: dict,
) -> None:
    _save_tentacle_config(trading_mode_name, trading_mode_configuration)
    _save_user_config(
        enabled_exchange, trading_pair, exchange_configurations,
        trading_simulator_configuration, simulated_portfolio_configuration
    )


def _save_user_config(
    enabled_exchange: str,
    trading_pair: str,
    exchange_configurations: list[dict],
    trading_simulator_configuration: dict,
    simulated_portfolio_configuration: list[dict],
) -> None:
    current_edited_config = interfaces_util.get_edited_config(dict_only=False)

    # exchanges: regenerate the whole configuration
    exchange_config_update = json_schemas.json_exchange_config_to_config(
        exchange_configurations, False
    )
    # only enable selected exchange and force spot trading
    exchange_config_update[enabled_exchange].update({
        commons_constants.CONFIG_ENABLED_OPTION: True,
        commons_constants.CONFIG_EXCHANGE_TYPE: commons_constants.CONFIG_EXCHANGE_SPOT,
    })
    current_exchanges_config = copy.deepcopy(current_edited_config.config[commons_constants.CONFIG_EXCHANGES])
    # nested_update_dict to keep nested key/val that might have been in previous config but are not in update
    # don't pass current_exchanges_config directly to really delete exchanges
    updated_exchange_config = {
        exchange: exchange_config
        for exchange, exchange_config in current_exchanges_config.items()
        if exchange in exchange_config_update
    }
    dict_util.nested_update_dict(updated_exchange_config, exchange_config_update)

    # currencies: regenerate the whole configuration
    updated_currencies_config = {
        trading_pair: {
            commons_constants.CONFIG_ENABLED_OPTION: True,
            commons_constants.CONFIG_CRYPTO_PAIRS: [trading_pair]
        }
    }

    # trader simulator
    simulated_enabled = trading_simulator_configuration[commons_constants.CONFIG_ENABLED_OPTION]
    updated_simulator_config = copy.deepcopy(current_edited_config.config[commons_constants.CONFIG_SIMULATOR])
    simulator_config_update = {
        **trading_simulator_configuration, **{
            commons_constants.CONFIG_STARTING_PORTFOLIO: json_schemas.json_simulated_portfolio_to_config(
                simulated_portfolio_configuration
            )
        }
    }
    dict_util.nested_update_dict(updated_simulator_config, simulator_config_update)

    # real trader
    updated_trader_config = copy.deepcopy(current_edited_config.config[commons_constants.CONFIG_TRADER])
    # only update the "enabled" state
    updated_trader_config[commons_constants.CONFIG_ENABLED_OPTION] = not simulated_enabled

    # trading
    updated_trading_config = copy.deepcopy(current_edited_config.config[commons_constants.CONFIG_TRADING])
    # only update the reference market
    updated_trading_config[commons_constants.CONFIG_TRADER_REFERENCE_MARKET] = (
        symbol_utils.parse_symbol(trading_pair).quote
    )

    update = {
        commons_constants.CONFIG_CRYPTO_CURRENCIES: updated_currencies_config,
        commons_constants.CONFIG_EXCHANGES: updated_exchange_config,
        commons_constants.CONFIG_TRADING: updated_trading_config,
        commons_constants.CONFIG_TRADER: updated_trader_config,
        commons_constants.CONFIG_SIMULATOR: updated_simulator_config,
    }
    # apply & save changes
    current_edited_config.config.update(update)
    current_edited_config.save()
    _get_logger().info(
        f"Configuration updated. Current profile: {current_edited_config.profile.name}"
    )


def _save_tentacle_config(
    trading_mode_name: str,
    trading_mode_configuration: dict,
) -> None:
    tentacle_class = octobot_tentacles_manager.api.get_tentacle_class_from_string(trading_mode_name)
    octobot_tentacles_manager.api.update_tentacle_config(
        interfaces_util.get_edited_tentacles_config(),
        tentacle_class,
        trading_mode_configuration,
        keep_existing=False,
    )
    _get_logger().info(
        f"{trading_mode_name} configuration updated."
    )


def _get_logger():
    return commons_logging.get_logger(_LOGGER_NAME)
