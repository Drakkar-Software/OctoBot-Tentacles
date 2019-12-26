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

from copy import copy

from octobot_backtesting.api.backtesting import create_backtesting, initialize_created_backtesting, \
    get_backtesting_progress, is_backtesting_in_progress, get_backtesting_run_report
from octobot_backtesting.api.exchange_data_collector import collect_exchange_historical_data
from octobot_backtesting.constants import BACKTESTING_FILE_PATH
from octobot_commons.constants import CONFIG_TRADING_FILE_PATH, CONFIG_EVALUATOR_FILE_PATH
from octobot_commons.logging.logging_util import get_logger
from octobot_backtesting.api.data_file import get_all_available_data_files, get_file_description, delete_data_file

from octobot_commons.tentacles_management.config_manager import reload_tentacle_config
from octobot_evaluators.constants import CONFIG_EVALUATOR
from octobot_interfaces.util.bot import get_bot
from octobot_interfaces.util.util import run_in_bot_main_loop
from octobot_trading.constants import CONFIG_TRADING_TENTACLES
from tentacles.Interfaces.interfaces.web.constants import BOT_TOOLS_BACKTESTING, BOT_TOOLS_BACKTESTING_SOURCE, \
    BOT_TOOLS_STRATEGY_OPTIMIZER
from tentacles.Interfaces.interfaces.web.web_interface import WebInterface

LOGGER = get_logger("DataCollectorWebInterfaceModel")


def get_data_files_with_description():
    files = get_all_available_data_files()
    files_with_description = {
        data_file: get_file_description(data_file) for data_file in files
    }
    return files_with_description


def start_backtesting_using_specific_files(files, source, reset_tentacle_config=False):
    try:
        tools = WebInterface.tools
        if tools[BOT_TOOLS_STRATEGY_OPTIMIZER] and tools[BOT_TOOLS_STRATEGY_OPTIMIZER].get_is_computing():
            return False, "Optimizer already running"
        elif tools[BOT_TOOLS_BACKTESTING] and tools[BOT_TOOLS_BACKTESTING].get_is_computing():
            return False, "A backtesting is already running"
        else:
            if reset_tentacle_config:
                config = reload_tentacle_config(copy(get_bot().config), CONFIG_EVALUATOR, CONFIG_EVALUATOR_FILE_PATH)
                config = reload_tentacle_config(config, CONFIG_TRADING_TENTACLES, CONFIG_TRADING_FILE_PATH)
            else:
                config = get_bot().config
            backtesting = create_backtesting(config, files)
            run_in_bot_main_loop(initialize_created_backtesting(backtesting), blocking=False)
            tools[BOT_TOOLS_BACKTESTING] = backtesting
            tools[BOT_TOOLS_BACKTESTING_SOURCE] = source
            return True, "Backtesting started"
    except Exception as e:
        LOGGER.exception(e)
        return False, f"Error when starting backtesting: {e}"


def get_backtesting_status():
    if WebInterface.tools[BOT_TOOLS_BACKTESTING]:
        backtesting = WebInterface.tools[BOT_TOOLS_BACKTESTING]
        if is_backtesting_in_progress(backtesting):
            return "computing", get_backtesting_progress(backtesting) * 100
        return "finished", 100
    else:
        return "not started", 0


def get_backtesting_report(source):
    tools = WebInterface.tools
    if tools[BOT_TOOLS_BACKTESTING]:
        backtesting = tools[BOT_TOOLS_BACKTESTING]
        if tools[BOT_TOOLS_BACKTESTING_SOURCE] == source:
            return get_backtesting_run_report(backtesting)
    return {}


def get_delete_data_file(file_name):
    deleted, error = delete_data_file(file_name)
    if deleted:
        return deleted, f"{file_name} deleted"
    else:
        return deleted, f"Can't delete {file_name} ({error})"


def collect_data_file(exchange, symbol):
    success = False
    try:
        result = run_in_bot_main_loop(collect_exchange_historical_data(get_bot().config, exchange, [symbol]))
        success = True
    except Exception as e:
        result = f"data collector error: {e}"

    if success:
        return success, f"{result} saved"
    else:
        return success, f"Can't collect data for {symbol} on {exchange} ({result})"


def save_data_file(name, file):
    try:
        file.save(f"{BACKTESTING_FILE_PATH}/{name}")
        message = f"{name} saved"
        LOGGER.info(message)
        return True, message
    except Exception as e:
        message = f"Error when saving file: {e}. File can't be saved."
        LOGGER.error(message)
        return False, message
