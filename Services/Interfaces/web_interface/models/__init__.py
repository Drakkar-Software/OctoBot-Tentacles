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
from tentacles.Services.Interfaces.web_interface.models import logs
from tentacles.Services.Interfaces.web_interface.models import medias
from tentacles.Services.Interfaces.web_interface.models import profiles
from tentacles.Services.Interfaces.web_interface.models import strategy_optimizer
from tentacles.Services.Interfaces.web_interface.models import tentacles
from tentacles.Services.Interfaces.web_interface.models import trading
from tentacles.Services.Interfaces.web_interface.models import web_interface_tab


from tentacles.Services.Interfaces.web_interface.models.backtesting import (
    CURRENT_BOT_DATA,
    get_full_candle_history_exchange_list,
    get_other_history_exchange_list,
    get_data_files_with_description,
    start_backtesting_using_specific_files,
    stop_previous_backtesting,
    create_snapshot_data_collector,
    get_data_files_from_current_bot,
    start_backtesting_using_current_bot_data,
    get_backtesting_status,
    get_backtesting_report,
    get_latest_backtesting_run_id,
    get_delete_data_file,
    get_data_collector_status,
    stop_data_collector,
    collect_data_file,
    save_data_file,
)
from tentacles.Services.Interfaces.web_interface.models.commands import (
    schedule_delayed_command,
    restart_bot,
    stop_bot,
    update_bot,
)
from tentacles.Services.Interfaces.web_interface.models.community import (
    get_community_metrics_to_display,
    can_get_community_metrics,
    get_account_tentacles_packages,
    get_preview_tentacles_packages,
    get_current_octobots_stats,
    get_all_user_bots,
    get_selected_user_bot,
    select_bot,
    create_new_bot,
)
from tentacles.Services.Interfaces.web_interface.models.configuration import (
    get_evaluators_tentacles_startup_activation,
    get_trading_tentacles_startup_activation,
    get_tentacle_documentation,
    get_tentacle_from_string,
    get_tentacle_user_commands,
    get_tentacle_config,
    get_tentacle_config_and_edit_display,
    get_tentacle_config_schema,
    get_tentacles_activation_desc_by_group,
    update_tentacle_config,
    update_copied_trading_id,
    reset_config_to_default,
    get_strategy_config,
    get_in_backtesting_mode,
    accepted_terms,
    accept_terms,
    get_evaluator_detailed_config,
    get_config_activated_trading_mode,
    get_config_activated_strategies,
    get_config_activated_evaluators,
    update_tentacles_activation_config,
    update_global_config,
    activate_metrics,
    activate_beta_env,
    get_metrics_enabled,
    get_beta_env_enabled_in_config,
    get_services_list,
    get_notifiers_list,
    get_enabled_trading_pairs,
    get_symbol_list,
    get_config_time_frames,
    get_timeframes_list,
    get_strategy_required_time_frames,
    format_config_symbols,
    get_all_symbols_dict,
    get_exchange_logo,
    get_traded_time_frames,
    get_full_exchange_list,
    get_tested_exchange_list,
    get_simulated_exchange_list,
    get_other_exchange_list,
    get_exchanges_details,
    are_compatible_accounts,
    get_current_exchange,
    REQUIREMENTS_KEY,
    SYMBOL_KEY,
    ID_KEY,
    change_reference_market_on_config_currencies,
    send_command_to_activated_tentacles,
    send_command_to_tentacles,
    reload_scripts,
    reload_activated_tentacles_config,
    reload_tentacle_config,
    update_config_currencies,
    get_config_required_candles_count,
)
from tentacles.Services.Interfaces.web_interface.models.dashboard import (
    parse_get_symbol,
    get_value_from_dict_or_string,
    format_trades,
    get_first_exchange_data,
    get_watched_symbol_data,
    get_watched_symbols,
    get_startup_messages,
    get_first_symbol_data,
    get_currency_price_graph_update,
)
from tentacles.Services.Interfaces.web_interface.models.interface_settings import (
    add_watched_symbol,
    remove_watched_symbol,
)
from tentacles.Services.Interfaces.web_interface.models.logs import (
    LOG_EXPORT_FORMAT,
    export_logs,
)
from tentacles.Services.Interfaces.web_interface.models.medias import (
    is_valid_tentacle_image_path,
    is_valid_audio_path,
)
from tentacles.Services.Interfaces.web_interface.models.profiles import (
    get_current_profile,
    duplicate_and_select_profile,
    select_profile,
    get_profiles,
    get_profiles_tentacles_details,
    update_profile,
    remove_profile,
    export_profile,
    import_profile,
    download_and_import_profile,
    get_profile_name,
)
from tentacles.Services.Interfaces.web_interface.models.strategy_optimizer import (
    get_strategies_list,
    get_time_frames_list,
    get_evaluators_list,
    get_risks_list,
    cancel_optimizer,
    start_optimizer,
    get_optimizer_results,
    get_optimizer_report,
    get_current_run_params,
    get_optimizer_status,
)
from tentacles.Services.Interfaces.web_interface.models.tentacles import (
    get_tentacles_packages,
    get_official_tentacles_url,
    call_tentacle_manager,
    install_packages,
    update_packages,
    reset_packages,
    update_modules,
    uninstall_modules,
    get_tentacles,
)
from tentacles.Services.Interfaces.web_interface.models.trading import (
    ensure_valid_exchange_id,
    get_exchange_time_frames,
    get_initializing_currencies_prices_set,
    get_evaluation,
    get_exchanges_load,
    get_exchange_holdings_per_symbol,
    get_symbols_values,
    get_portfolio_historical_values,
)
from tentacles.Services.Interfaces.web_interface.models.web_interface_tab import (
    WebInterfaceTab,
)


__all__ = [
    "get_data_files_with_description",
    "start_backtesting_using_specific_files",
    "stop_previous_backtesting",
    "create_snapshot_data_collector",
    "get_data_files_from_current_bot",
    "start_backtesting_using_current_bot_data",
    "get_backtesting_status",
    "get_backtesting_report",
    "get_latest_backtesting_run_id",
    "get_delete_data_file",
    "get_data_collector_status",
    "stop_data_collector",
    "collect_data_file",
    "save_data_file",
    "schedule_delayed_command",
    "restart_bot",
    "stop_bot",
    "update_bot",
    "get_community_metrics_to_display",
    "can_get_community_metrics",
    "get_account_tentacles_packages",
    "get_preview_tentacles_packages",
    "get_current_octobots_stats",
    "get_all_user_bots",
    "get_selected_user_bot",
    "select_bot",
    "create_new_bot",
    "get_evaluators_tentacles_startup_activation",
    "get_trading_tentacles_startup_activation",
    "get_tentacle_documentation",
    "get_tentacle_from_string",
    "get_tentacle_user_commands",
    "get_tentacle_config",
    "get_tentacle_config_and_edit_display",
    "get_tentacle_config_schema",
    "get_tentacles_activation_desc_by_group",
    "update_tentacle_config",
    "update_copied_trading_id",
    "reset_config_to_default",
    "get_strategy_config",
    "get_in_backtesting_mode",
    "accepted_terms",
    "accept_terms",
    "get_evaluator_detailed_config",
    "get_config_activated_trading_mode",
    "get_config_activated_strategies",
    "get_config_activated_evaluators",
    "update_tentacles_activation_config",
    "update_global_config",
    "activate_metrics",
    "activate_beta_env",
    "get_metrics_enabled",
    "get_beta_env_enabled_in_config",
    "get_services_list",
    "get_notifiers_list",
    "get_enabled_trading_pairs",
    "get_symbol_list",
    "get_config_time_frames",
    "get_timeframes_list",
    "get_strategy_required_time_frames",
    "format_config_symbols",
    "get_all_symbols_dict",
    "get_exchange_logo",
    "get_traded_time_frames",
    "get_full_exchange_list",
    "get_tested_exchange_list",
    "get_simulated_exchange_list",
    "get_other_exchange_list",
    "get_exchanges_details",
    "are_compatible_accounts",
    "get_current_exchange",
    "parse_get_symbol",
    "get_value_from_dict_or_string",
    "format_trades",
    "get_first_exchange_data",
    "get_watched_symbol_data",
    "get_first_symbol_data",
    "get_currency_price_graph_update",
    "get_watched_symbols",
    "get_startup_messages",
    "add_watched_symbol",
    "remove_watched_symbol",
    "LOG_EXPORT_FORMAT",
    "export_logs",
    "is_valid_tentacle_image_path",
    "is_valid_audio_path",
    "get_current_profile",
    "duplicate_and_select_profile",
    "select_profile",
    "get_profiles",
    "get_profiles_tentacles_details",
    "update_profile",
    "remove_profile",
    "export_profile",
    "import_profile",
    "download_and_import_profile",
    "get_profile_name",
    "get_strategies_list",
    "get_time_frames_list",
    "get_evaluators_list",
    "get_risks_list",
    "cancel_optimizer",
    "start_optimizer",
    "get_optimizer_results",
    "get_optimizer_report",
    "get_current_run_params",
    "get_optimizer_status",
    "get_tentacles_packages",
    "get_official_tentacles_url",
    "call_tentacle_manager",
    "install_packages",
    "update_packages",
    "reset_packages",
    "update_modules",
    "uninstall_modules",
    "get_tentacles",
    "ensure_valid_exchange_id",
    "get_exchange_time_frames",
    "get_initializing_currencies_prices_set",
    "get_evaluation",
    "get_exchanges_load",
    "REQUIREMENTS_KEY",
    "SYMBOL_KEY",
    "ID_KEY",
    "get_exchange_holdings_per_symbol",
    "get_symbols_values",
    "get_portfolio_historical_values",
    "CURRENT_BOT_DATA",
    "get_full_candle_history_exchange_list",
    "get_other_history_exchange_list",
    "change_reference_market_on_config_currencies",
    "send_command_to_activated_tentacles",
    "send_command_to_tentacles",
    "reload_scripts",
    "reload_activated_tentacles_config",
    "reload_tentacle_config",
    "update_config_currencies",
    "get_config_required_candles_count",
    "WebInterfaceTab",
]
