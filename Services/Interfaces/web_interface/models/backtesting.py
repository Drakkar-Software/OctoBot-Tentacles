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
import os
import asyncio

import octobot_commons.logging as bot_logging
import octobot.api as octobot_api
import octobot_backtesting.api as backtesting_api
import octobot_tentacles_manager.api as tentacles_manager_api
import octobot_backtesting.constants as backtesting_constants
import octobot_services.interfaces.util as interfaces_util
import tentacles.Services.Interfaces.web_interface.constants as constants
import tentacles.Services.Interfaces.web_interface as web_interface_root

LOGGER = bot_logging.get_logger("DataCollectorWebInterfaceModel")


async def _get_description(data_file, files_with_description):
    description = await backtesting_api.get_file_description(data_file)
    if description is not None:
        files_with_description[data_file] = description


async def _retrieve_data_files_with_description(files):
    files_with_description = {}
    await asyncio.gather(*[_get_description(data_file, files_with_description) for data_file in files])
    return files_with_description


def get_data_files_with_description():
    files = backtesting_api.get_all_available_data_files()
    return interfaces_util.run_in_bot_async_executor(_retrieve_data_files_with_description(files))


def start_backtesting_using_specific_files(files, source, reset_tentacle_config=False, run_on_common_part_only=True):
    try:
        tools = web_interface_root.WebInterface.tools
        previous_independent_backtesting = tools[constants.BOT_TOOLS_BACKTESTING]
        if tools[constants.BOT_TOOLS_STRATEGY_OPTIMIZER] and octobot_api.is_optimizer_in_progress(
                tools[constants.BOT_TOOLS_STRATEGY_OPTIMIZER]):
            return False, "Optimizer already running"
        elif previous_independent_backtesting and \
                octobot_api.is_independent_backtesting_in_progress(previous_independent_backtesting):
            return False, "A backtesting is already running"
        else:
            if previous_independent_backtesting:
                interfaces_util.run_in_bot_main_loop(
                    octobot_api.stop_independent_backtesting(previous_independent_backtesting))
            if reset_tentacle_config:
                tentacles_setup_config = tentacles_manager_api.get_tentacles_setup_config()
            else:
                tentacles_setup_config = interfaces_util.get_bot_api().get_edited_tentacles_config()
            config = interfaces_util.get_global_config()
            independent_backtesting = octobot_api.create_independent_backtesting(config,
                                                                                 tentacles_setup_config,
                                                                                 files,
                                                                                 run_on_common_part_only=run_on_common_part_only)
            interfaces_util.run_in_bot_main_loop(
                octobot_api.initialize_and_run_independent_backtesting(independent_backtesting), blocking=False)
            tools[constants.BOT_TOOLS_BACKTESTING] = independent_backtesting
            tools[constants.BOT_TOOLS_BACKTESTING_SOURCE] = source
            return True, "Backtesting started"
    except Exception as e:
        LOGGER.exception(e, False)
        return False, f"Error when starting backtesting: {e}"


def get_backtesting_status():
    if web_interface_root.WebInterface.tools[constants.BOT_TOOLS_BACKTESTING] is not None:
        independent_backtesting = web_interface_root.WebInterface.tools[constants.BOT_TOOLS_BACKTESTING]
        if octobot_api.is_independent_backtesting_in_progress(independent_backtesting):
            return "computing", octobot_api.get_independent_backtesting_progress(independent_backtesting) * 100
        if octobot_api.is_independent_backtesting_finished(independent_backtesting) or \
                octobot_api.is_independent_backtesting_stopped(independent_backtesting):
            return "finished", 100
        return "starting", 0
    return "not started", 0


def get_backtesting_report(source):
    tools = web_interface_root.WebInterface.tools
    if tools[constants.BOT_TOOLS_BACKTESTING]:
        backtesting = tools[constants.BOT_TOOLS_BACKTESTING]
        if tools[constants.BOT_TOOLS_BACKTESTING_SOURCE] == source:
            return interfaces_util.run_in_bot_async_executor(
                octobot_api.get_independent_backtesting_report(backtesting))
    return {}


def get_delete_data_file(file_name):
    deleted, error = backtesting_api.delete_data_file(file_name)
    if deleted:
        return deleted, f"{file_name} deleted"
    else:
        return deleted, f"Can't delete {file_name} ({error})"


def collect_data_file(exchange, symbol):
    success = False
    try:
        result = interfaces_util.run_in_bot_async_executor(
            backtesting_api.collect_exchange_historical_data(exchange,
                                                             interfaces_util.get_bot_api().get_edited_tentacles_config(),
                                                             [symbol]))
        success = True
    except Exception as e:
        result = f"data collector error: {e}"

    if success:
        return success, f"{result} saved"
    else:
        return success, f"Can't collect data for {symbol} on {exchange} ({result})"


async def _convert_into_octobot_data_file_if_necessary(output_file):
    try:
        description = await backtesting_api.get_file_description(output_file, data_path="")
        if description is not None:
            # no error: current bot format data
            return f"{output_file} saved"
        else:
            # try to convert into current bot format
            converted_output_file = await backtesting_api.convert_data_file(output_file)
            if converted_output_file is not None:
                message = f"Saved into {converted_output_file}"
            else:
                message = "Failed to convert file."
            # remove invalid format file
            os.remove(output_file)
            return message
    except Exception as e:
        message = f"Error when handling backtesting data file: {e}"
        LOGGER.exception(e, True, message)
        return message


def save_data_file(name, file):
    try:
        output_file = f"{backtesting_constants.BACKTESTING_FILE_PATH}/{name}"
        file.save(output_file)
        message = interfaces_util.run_in_bot_async_executor(_convert_into_octobot_data_file_if_necessary(output_file))
        LOGGER.info(message)
        return True, message
    except Exception as e:
        message = f"Error when saving file: {e}. File can't be saved."
        LOGGER.error(message)
        return False, message
