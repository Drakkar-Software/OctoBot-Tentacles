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
import octobot_tentacles_manager.api as tentacles_manager_api
import octobot_commons.logging as bot_logging
import tentacles.Services.Interfaces.web_interface.models.backtesting as backtesting_model
import tentacles.Services.Interfaces.web_interface as web_interface_root
import tentacles.Services.Interfaces.web_interface.constants as constants


def _get_logger():
    return bot_logging.get_logger("StrategyDesign")


def get_plotted_data(trading_mode, run_id=None, optimizer_id=None):
    elements = scripting_library.DisplayedElements()
    db_name = trading_mode.get_db_name(bot_id=interfaces_util.get_bot_api().get_bot_id()) if run_id is None \
        else trading_mode.get_db_name(backtesting=True, prefix=run_id, optimizer_id=optimizer_id)
    interfaces_util.run_in_bot_async_executor(
        elements.fill_from_database(db_name)
    )
    return elements.to_json()


def get_backtesting_run_plotted_data(trading_mode, run_id):
    elements = interfaces_util.run_in_bot_async_executor(
        trading_mode.get_backtesting_plot(run_id)
    )
    return elements.to_json()


def update_plot_script(trading_mode, is_live):
    interfaces_util.run_in_bot_main_loop(
        services_api.send_user_command(
            interfaces_util.get_bot_api().get_bot_id(),
            trading_mode.get_name(),
            trading_mode.USER_COMMAND_RELOAD_SCRIPT,
            {
                trading_mode.USER_COMMAND_RELOAD_SCRIPT_IS_LIVE: is_live
            },
            wait_for_processing=True
        )
    )
    return {"success": True}


def get_run_data(trading_mode, is_live, optimizer_id=None):
    return {
        "data": interfaces_util.run_in_bot_async_executor(
            scripting_library.read_metadata(trading_mode=trading_mode,
                                            backtesting=not is_live,
                                            optimizer_id=optimizer_id)
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


def start_strategy_design_optimizer(trading_mode, config, exchange_id, randomly_chose_runs):
    tools = web_interface_root.WebInterface.tools
    optimizer = tools[constants.BOT_TOOLS_STRATEGY_OPTIMIZER]
    if optimizer is not None and octobot_api.is_optimizer_computing(optimizer):
        return False, "Optimizer already running"
    data_file = backtesting_model.create_data_files_from_current_bot(exchange_id)
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
        octobot_api.initialize_design_strategy_optimizer(optimizer)
    )
    thread = threading.Thread(target=interfaces_util.run_in_bot_async_executor,
                              args=(octobot_api.start_design_strategy_optimizer(optimizer, randomly_chose_runs), ),
                              name=f"{optimizer.get_name()}-WebInterface-runner")
    thread.start()
    return True, "Success"
