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
import octobot_services.interfaces.util as interfaces_util
import octobot_services.api as services_api
import octobot_trading.modes.scripting_library as scripting_library


def get_plotted_data(trading_mode):
    elements = scripting_library.PlottedElements()
    interfaces_util.run_in_bot_async_executor(
        elements.fill_from_database(
            trading_mode.get_db_name(
                bot_id=interfaces_util.get_bot_api().get_bot_id()
            )
        )
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


async def _read_metadata(trading_mode, is_live):
    data_file = trading_mode.get_db_name(metadata_db=True, backtesting=not is_live)
    async with scripting_library.MetadataReader.database(data_file) as reader:
        return await reader.read()


def get_run_data(trading_mode, is_live):
    return {
        "data": interfaces_util.run_in_bot_async_executor(
            _read_metadata(trading_mode, is_live)
        )
    }
