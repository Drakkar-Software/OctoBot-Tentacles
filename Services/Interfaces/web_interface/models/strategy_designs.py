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
    interfaces_util.run_in_bot_async_executor(
        elements.fill_from_database(database_manager, exchange_name, symbol, time_frame,
                                    exchange_id, with_inputs=run_id is None)
    )
    return elements.to_json()


def get_backtesting_run_plotted_data(trading_mode, exchange, symbol, run_id, optimizer_id=None):
    elements = interfaces_util.run_in_bot_async_executor(
        trading_mode.get_backtesting_plot(exchange, symbol, run_id, optimizer_id)
    )
    return elements.to_json()


def reload_scripts():
    try:
        trading_mode = configuration.get_config_activated_trading_mode()
        evaluators = configuration.get_config_activated_evaluators()
        for tentacle in [trading_mode] + evaluators:
            interfaces_util.run_in_bot_main_loop(
                services_api.send_user_command(
                    interfaces_util.get_bot_api().get_bot_id(),
                    tentacle.get_name(),
                    commons_enums.UserCommands.RELOAD_SCRIPT.value,
                    None,
                    wait_for_processing=True
                )
            )
        return {"success": True}
    except Exception as e:
        _get_logger().exception(e, True, f"Failed to reload scripts: {e}")
        raise


def get_run_data(trading_mode, optimizer_id=None):
    return {
        "data": interfaces_util.run_in_bot_async_executor(
            scripting_library.read_metadata(trading_mode=trading_mode, optimizer_id=optimizer_id)
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
                                    start_timestamp=None, end_timestamp=None):
    tools = web_interface_root.WebInterface.tools
    optimizer = tools[constants.BOT_TOOLS_STRATEGY_OPTIMIZER]
    if optimizer is not None and octobot_api.is_optimizer_computing(optimizer):
        return False, "Optimizer already running"
    data_file = backtesting_model.get_data_files_from_current_bot(exchange_id, start_timestamp, end_timestamp)
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
        [data_file])
    tools[constants.BOT_TOOLS_STRATEGY_OPTIMIZER] = optimizer
    interfaces_util.run_in_bot_async_executor(
        octobot_api.initialize_design_strategy_optimizer(optimizer, is_computing=True)
    )
    thread = threading.Thread(target=interfaces_util.run_in_bot_async_executor,
                              args=(octobot_api.start_design_strategy_optimizer(optimizer, randomly_chose_runs), ),
                              name=f"{optimizer.get_name()}-WebInterface-runner")
    thread.start()
    return True, "Success"
