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
import threading

import octobot.api as octobot_api
import octobot_services.interfaces.util as interfaces_util
import octobot_services.api as services_api
import octobot_trading.modes.scripting_library as scripting_library
import octobot_trading.api as trading_api
import octobot_tentacles_manager.api as tentacles_manager_api
import octobot_commons.logging as bot_logging
import octobot_commons.databases as databases
import octobot_commons.enums as commons_enums
import octobot_commons.errors as commons_errors
import tentacles.Services.Interfaces.web_interface.models.backtesting as backtesting_model
import tentacles.Services.Interfaces.web_interface as web_interface_root
import tentacles.Services.Interfaces.web_interface.constants as constants
import tentacles.Services.Interfaces.web_interface.models.configuration as configuration


def _get_logger():
    return bot_logging.get_logger("StrategyDesign")


def get_plotted_data(trading_mode, symbol, time_frame, run_id=None, optimizer_id=None, exchange_id=None):
    elements = scripting_library.DisplayedElements()
    database_manager = databases.DatabaseManager(trading_mode,
                                                 backtesting_id=run_id,
                                                 optimizer_id=optimizer_id)
    exchange_name = trading_api.get_exchange_name(trading_api.get_exchange_manager_from_exchange_id(exchange_id)) \
        if exchange_id else None
    try:
        interfaces_util.run_in_bot_async_executor(
            elements.fill_from_database(database_manager, exchange_name, symbol, time_frame,
                                        exchange_id, with_inputs=run_id is None)
        )
    except commons_errors.DatabaseNotFoundError as e:
        _get_logger().exception(e, True, f"Error when opening database: {e}")
    return elements.to_json()


def get_backtesting_run_plotted_data(trading_mode, exchange, symbol, run_id, optimizer_id):
    elements = interfaces_util.run_in_bot_async_executor(
        trading_mode.get_backtesting_plot(exchange, symbol, run_id, optimizer_id)
    )
    return elements.to_json()


def _send_command_to_activated_tentacles(command, wait_for_processing=True):
    trading_mode = configuration.get_config_activated_trading_mode()
    evaluators = configuration.get_config_activated_evaluators()
    for tentacle in [trading_mode] + evaluators:
        interfaces_util.run_in_bot_main_loop(
            services_api.send_user_command(
                interfaces_util.get_bot_api().get_bot_id(),
                tentacle.get_name(),
                command,
                None,
                wait_for_processing=wait_for_processing
            )
        )


def reload_scripts():
    try:
        _send_command_to_activated_tentacles(commons_enums.UserCommands.RELOAD_SCRIPT.value)
        return {"success": True}
    except Exception as e:
        _get_logger().exception(e, True, f"Failed to reload scripts: {e}")
        raise


def get_run_data(trading_mode, include_optimizer_runs=True):
    return {
        "data": interfaces_util.run_in_bot_async_executor(
            scripting_library.read_metadata(trading_mode=trading_mode, include_optimizer_runs=include_optimizer_runs)
        )
    }


def save_strategy_design_optimizer_config(trading_mode, config_update):
    try:
        optimizer = octobot_api.create_design_strategy_optimizer(trading_mode)
        tentacles_manager_api.update_tentacle_config(interfaces_util.get_edited_tentacles_config(),
                                                     optimizer,
                                                     config_update)
        return f"Optimizer configuration updated"
    except Exception as e:
        _get_logger().exception(e, False)
        return f"Error when updating tentacle config: {e}"


def get_strategy_design_optimizer_config(trading_mode):
    return tentacles_manager_api.get_tentacle_config(interfaces_util.get_edited_tentacles_config(),
                                                     octobot_api.create_design_strategy_optimizer(trading_mode))


def start_strategy_design_optimizer(trading_mode, config, exchange_id, randomly_chose_runs,
                                    start_timestamp=None, end_timestamp=None, resume=False):
    tools = web_interface_root.WebInterface.tools
    optimizer = tools[constants.BOT_TOOLS_STRATEGY_OPTIMIZER]
    if optimizer is not None and octobot_api.is_optimizer_computing(optimizer):
        return False, "Optimizer already running"
    data_files = None if resume else \
        [backtesting_model.get_data_files_from_current_bot(exchange_id, start_timestamp, end_timestamp)]
    temp_independent_backtesting = octobot_api.create_independent_backtesting(
        interfaces_util.get_global_config(), None, [])
    optimizer_config = interfaces_util.run_in_bot_async_executor(
        octobot_api.initialize_independent_backtesting_config(temp_independent_backtesting)
    )
    optimizer = octobot_api.create_design_strategy_optimizer(
        trading_mode,
        optimizer_config,
        interfaces_util.get_bot_api().get_edited_tentacles_config(),
        config,
        data_files)
    interfaces_util.run_in_bot_async_executor(
        octobot_api.initialize_design_strategy_optimizer(optimizer, is_computing=True, is_resuming=resume)
    )
    start_func = octobot_api.resume_design_strategy_optimizer if resume else octobot_api.start_design_strategy_optimizer
    tools[constants.BOT_TOOLS_STRATEGY_OPTIMIZER] = optimizer
    thread = threading.Thread(target=interfaces_util.run_in_bot_async_executor,
                              args=(start_func(optimizer, randomly_chose_runs), ),
                              name=f"{optimizer.get_name()}-WebInterface-runner")
    thread.start()
    return True, "Success"


def resume_strategy_design_optimizer(trading_mode, randomly_chose_runs, start_timestamp=None, end_timestamp=None):
    return start_strategy_design_optimizer(trading_mode, None, None, randomly_chose_runs,
                                           start_timestamp=start_timestamp, end_timestamp=end_timestamp, resume=True)


def get_strategy_optimizer_queue(trading_mode):
    return {
        "queue": interfaces_util.run_in_bot_async_executor(
            octobot_api.get_design_strategy_optimizer_queue(trading_mode)
        )
     }


def update_strategy_optimizer_queue(trading_mode, updated_queue):
    return {
        "queue": interfaces_util.run_in_bot_async_executor(
            octobot_api.update_design_strategy_optimizer_queue(trading_mode, updated_queue)
        )
     }


def _send_clear_command(command, message):
    try:
        _send_command_to_activated_tentacles(command)
        return {"title": message}
    except Exception as e:
        _get_logger().exception(e, True, f"Failed to reload scripts: {e}")
        raise


def clear_simulated_orders_cache():
    return _send_clear_command(commons_enums.UserCommands.CLEAR_SIMULATED_ORDERS_CACHE.value,
                               "Cleared simulated orders cache")


def clear_simulated_trades_cache():
    return _send_clear_command(commons_enums.UserCommands.CLEAR_SIMULATED_TRADES_CACHE.value,
                               "Cleared simulated trades cache")


def clear_plotted_cache():
    return _send_clear_command(commons_enums.UserCommands.CLEAR_PLOTTING_CACHE.value, "Cleared plotting cache")


def clear_all_cache():
    return _send_clear_command(commons_enums.UserCommands.CLEAR_ALL_CACHE.value, "Cleared all cache")
