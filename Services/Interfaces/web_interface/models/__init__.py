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


from tentacles.Services.Interfaces.web_interface.models import backtesting
from tentacles.Services.Interfaces.web_interface.models import commands
from tentacles.Services.Interfaces.web_interface.models import community
from tentacles.Services.Interfaces.web_interface.models import configuration
from tentacles.Services.Interfaces.web_interface.models import dashboard
from tentacles.Services.Interfaces.web_interface.models import interface_settings
from tentacles.Services.Interfaces.web_interface.models import medias
from tentacles.Services.Interfaces.web_interface.models import strategy_optimizer
from tentacles.Services.Interfaces.web_interface.models import tentacles
from tentacles.Services.Interfaces.web_interface.models import trading


from tentacles.Services.Interfaces.web_interface.models.backtesting import (
    get_data_files_with_description,
    start_backtesting_using_specific_files,
    get_backtesting_status,
    get_backtesting_report,
    get_delete_data_file,
    collect_data_file,
    save_data_file,
)
from tentacles.Services.Interfaces.web_interface.models.commands import (
    schedule_delayed_command,
    restart_bot,
    stop_bot,
)
from tentacles.Services.Interfaces.web_interface.models.community import (
    get_community_metrics_to_display,
    can_get_community_metrics,
)
from tentacles.Services.Interfaces.web_interface.models.configuration import (
    get_evaluators_tentacles_startup_activation,
    get_trading_tentacles_startup_activation,
    get_tentacle_documentation,
    get_tentacle_from_string,
    get_tentacle_config,
    get_tentacle_config_schema,
    get_tentacles_activation_desc_by_group,
    update_tentacle_config,
    reset_config_to_default,
    get_strategy_config,
    get_in_backtesting_mode,
    accepted_terms,
    accept_terms,
    get_evaluator_detailed_config,
    get_config_activated_trading_mode,
    update_tentacles_activation_config,
    update_global_config,
    manage_metrics,
    get_metrics_enabled,
    get_services_list,
    get_notifiers_list,
    get_symbol_list,
    format_config_symbols,
    get_all_symbols_dict,
    get_exchange_logo,
    get_full_exchange_list,
    get_tested_exchange_list,
    get_simulated_exchange_list,
    get_other_exchange_list,
    get_current_exchange,
    REQUIREMENTS_KEY,
    SYMBOL_KEY,
    ID_KEY,
)
from tentacles.Services.Interfaces.web_interface.models.dashboard import (
    parse_get_symbol,
    get_value_from_dict_or_string,
    format_trades,
    get_watched_symbol_data,
    get_watched_symbols,
    get_first_symbol_data,
    get_currency_price_graph_update,
)
from tentacles.Services.Interfaces.web_interface.models.interface_settings import (
    add_watched_symbol,
    remove_watched_symbol,
)
from tentacles.Services.Interfaces.web_interface.models.medias import (
    is_valid_tentacle_image_path,
)
from tentacles.Services.Interfaces.web_interface.models.strategy_optimizer import (
    get_strategies_list,
    get_time_frames_list,
    get_evaluators_list,
    get_risks_list,
    start_optimizer,
    get_optimizer_results,
    get_optimizer_report,
    get_current_run_params,
    get_optimizer_status,
)
from tentacles.Services.Interfaces.web_interface.models.tentacles import (
    get_tentacles_packages,
    call_tentacle_manager,
    install_packages,
    update_packages,
    reset_packages,
    update_modules,
    uninstall_modules,
    get_tentacles,
)
from tentacles.Services.Interfaces.web_interface.models.trading import (
    get_exchange_time_frames,
    get_initializing_currencies_prices_set,
    get_evaluation,
    get_exchanges_load,
)


__all__ = [
    "get_data_files_with_description",
    "start_backtesting_using_specific_files",
    "get_backtesting_status",
    "get_backtesting_report",
    "get_delete_data_file",
    "collect_data_file",
    "save_data_file",
    "schedule_delayed_command",
    "restart_bot",
    "stop_bot",
    "get_community_metrics_to_display",
    "can_get_community_metrics",
    "get_evaluators_tentacles_startup_activation",
    "get_trading_tentacles_startup_activation",
    "get_tentacle_documentation",
    "get_tentacle_from_string",
    "get_tentacle_config",
    "get_tentacle_config_schema",
    "get_tentacles_activation_desc_by_group",
    "update_tentacle_config",
    "reset_config_to_default",
    "get_strategy_config",
    "get_in_backtesting_mode",
    "accepted_terms",
    "accept_terms",
    "get_evaluator_detailed_config",
    "get_config_activated_trading_mode",
    "update_tentacles_activation_config",
    "update_global_config",
    "manage_metrics",
    "get_metrics_enabled",
    "get_services_list",
    "get_notifiers_list",
    "get_symbol_list",
    "format_config_symbols",
    "get_all_symbols_dict",
    "get_exchange_logo",
    "get_full_exchange_list",
    "get_tested_exchange_list",
    "get_simulated_exchange_list",
    "get_other_exchange_list",
    "get_current_exchange",
    "parse_get_symbol",
    "get_value_from_dict_or_string",
    "format_trades",
    "get_watched_symbol_data",
    "get_first_symbol_data",
    "get_currency_price_graph_update",
    "get_watched_symbols",
    "add_watched_symbol",
    "remove_watched_symbol",
    "is_valid_tentacle_image_path",
    "get_strategies_list",
    "get_time_frames_list",
    "get_evaluators_list",
    "get_risks_list",
    "start_optimizer",
    "get_optimizer_results",
    "get_optimizer_report",
    "get_current_run_params",
    "get_optimizer_status",
    "get_tentacles_packages",
    "call_tentacle_manager",
    "install_packages",
    "update_packages",
    "reset_packages",
    "update_modules",
    "uninstall_modules",
    "get_tentacles",
    "get_exchange_time_frames",
    "get_initializing_currencies_prices_set",
    "get_evaluation",
    "get_exchanges_load",
    "REQUIREMENTS_KEY",
    "SYMBOL_KEY",
    "ID_KEY"
]


