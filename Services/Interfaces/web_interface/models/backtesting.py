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
import ccxt
import threading

import octobot.strategy_optimizer
import octobot_commons.enums as commons_enums
import octobot_commons.logging as bot_logging
import octobot_commons.time_frame_manager as time_frame_manager
import octobot_commons.symbols as commons_symbols
import octobot_commons.databases as databases
import octobot_commons.constants as commons_constants
import octobot.api as octobot_api
import octobot_backtesting.api as backtesting_api
import octobot_tentacles_manager.api as tentacles_manager_api
import octobot_backtesting.constants as backtesting_constants
import octobot_backtesting.enums as backtesting_enums
import octobot_backtesting.collectors as collectors
import octobot_services.interfaces.util as interfaces_util
import octobot_services.enums as services_enums
import octobot_trading.constants as trading_constants
import octobot_trading.enums as trading_enums
import octobot_trading.api as trading_api
import tentacles.Services.Interfaces.web_interface.constants as constants
import tentacles.Services.Interfaces.web_interface as web_interface_root
import tentacles.Services.Interfaces.web_interface.models.trading as trading_model


STOPPING_TIMEOUT = 30
CURRENT_BOT_DATA = "current_bot_data"
# data collector can be really slow, let it up to 2 hours to run
DATA_COLLECTOR_TIMEOUT = 2 * commons_constants.HOURS_TO_SECONDS


def get_full_candle_history_exchange_list():
    full_exchange_list = list(set(ccxt.exchanges))
    return [exchange for exchange in trading_constants.FULL_CANDLE_HISTORY_EXCHANGES if exchange in full_exchange_list]


def get_other_history_exchange_list():
    full_exchange_list = list(set(ccxt.exchanges))
    return [exchange for exchange in full_exchange_list if
            exchange not in trading_constants.FULL_CANDLE_HISTORY_EXCHANGES]


async def _get_description(data_file, files_with_description):
    description = await backtesting_api.get_file_description(data_file)
    if _is_usable_description(description):
        files_with_description.append((data_file, description))


def _is_usable_description(description):
    return description is not None \
           and description[backtesting_enums.DataFormatKeys.SYMBOLS.value] is not None \
           and description[backtesting_enums.DataFormatKeys.TIME_FRAMES.value] is not None


async def _retrieve_data_files_with_description(files):
    files_with_description = []
    await asyncio.gather(*[_get_description(data_file, files_with_description) for data_file in files])
    return sorted(
        files_with_description,
        key=lambda f: f[1][backtesting_enums.DataFormatKeys.TIMESTAMP.value],
        reverse=True
    )


def get_data_files_with_description():
    files = backtesting_api.get_all_available_data_files()
    return interfaces_util.run_in_bot_async_executor(_retrieve_data_files_with_description(files))


def start_backtesting_using_specific_files(files, source, reset_tentacle_config=False, run_on_common_part_only=True,
                                           start_timestamp=None, end_timestamp=None, trading_type=None,
                                           enable_logs=False,
                                           auto_stop=False, collector_start_callback=None, start_callback=None):
    return _start_backtesting(files, source, reset_tentacle_config=reset_tentacle_config,
                              run_on_common_part_only=run_on_common_part_only,
                              start_timestamp=start_timestamp, end_timestamp=end_timestamp, trading_type=trading_type,
                              use_current_bot_data=False, enable_logs=enable_logs,
                              auto_stop=auto_stop, collector_start_callback=collector_start_callback,
                              start_callback=start_callback)


def start_backtesting_using_current_bot_data(data_source, exchange_id, source, reset_tentacle_config=False,
                                             start_timestamp=None, end_timestamp=None, trading_type=None,
                                             enable_logs=False, auto_stop=False,
                                             collector_start_callback=None, start_callback=None):
    use_current_bot_data = data_source == CURRENT_BOT_DATA
    files = None if use_current_bot_data else [data_source]
    return _start_backtesting(files, source, reset_tentacle_config=reset_tentacle_config,
                              run_on_common_part_only=False,
                              start_timestamp=start_timestamp, end_timestamp=end_timestamp, trading_type=trading_type,
                              use_current_bot_data=use_current_bot_data,
                              exchange_id=exchange_id, enable_logs=enable_logs,
                              auto_stop=auto_stop, collector_start_callback=collector_start_callback,
                              start_callback=start_callback)


def stop_previous_backtesting():
    previous_independent_backtesting = web_interface_root.WebInterface.tools[constants.BOT_TOOLS_BACKTESTING]
    if previous_independent_backtesting and \
            not octobot_api.is_independent_backtesting_stopped(previous_independent_backtesting):
        interfaces_util.run_in_bot_main_loop(
            octobot_api.stop_independent_backtesting(previous_independent_backtesting))
        return True, "Backtesting is stopping"
    return True, "No backtesting to stop"


def _parse_trading_type(trading_type):
    if trading_type is None or trading_type == commons_constants.USE_CURRENT_PROFILE:
        return commons_constants.USE_CURRENT_PROFILE, commons_constants.USE_CURRENT_PROFILE
    if trading_type == trading_enums.ExchangeTypes.SPOT.value:
        return commons_constants.CONFIG_EXCHANGE_SPOT, commons_constants.USE_CURRENT_PROFILE
    if trading_type == trading_enums.FutureContractType.INVERSE_PERPETUAL.value:
        return commons_constants.CONFIG_EXCHANGE_FUTURE, trading_enums.FutureContractType.INVERSE_PERPETUAL
    if trading_type == trading_enums.FutureContractType.LINEAR_PERPETUAL.value:
        return commons_constants.CONFIG_EXCHANGE_FUTURE, trading_enums.FutureContractType.LINEAR_PERPETUAL
    if trading_type == trading_enums.ExchangeTypes.MARGIN.value:
        return commons_constants.CONFIG_EXCHANGE_MARGIN, commons_constants.USE_CURRENT_PROFILE
    raise RuntimeError(f"Unsupported trading type: {trading_type}")


def _start_backtesting(files, source, reset_tentacle_config=False, run_on_common_part_only=True,
                       start_timestamp=None, end_timestamp=None, trading_type=None, use_current_bot_data=False,
                       exchange_id=None, enable_logs=False, auto_stop=False,
                       collector_start_callback=None, start_callback=None):
    tools = web_interface_root.WebInterface.tools
    if exchange_id is not None:
        trading_model.ensure_valid_exchange_id(exchange_id)
    try:
        previous_independent_backtesting = tools[constants.BOT_TOOLS_BACKTESTING]
        optimizer = tools[constants.BOT_TOOLS_STRATEGY_OPTIMIZER]
        is_optimizer_running = tools[constants.BOT_TOOLS_STRATEGY_OPTIMIZER] and \
                               interfaces_util.run_in_bot_async_executor(
                                octobot_api.is_optimizer_in_progress(tools[constants.BOT_TOOLS_STRATEGY_OPTIMIZER])
                               )
        if is_optimizer_running and not isinstance(optimizer, octobot.strategy_optimizer.StrategyDesignOptimizer):
            return False, "An optimizer is already running"
        if use_current_bot_data and \
                isinstance(tools[constants.BOT_TOOLS_DATA_COLLECTOR], collectors.AbstractExchangeBotSnapshotCollector):
            # can't start a new backtest with use_current_bot_data when a snapshot collector is on
            return False, "An data collector is already running"
        if tools[constants.BOT_PREPARING_BACKTESTING]:
            return False, "An backtesting is already running"
        if previous_independent_backtesting and \
                octobot_api.is_independent_backtesting_in_progress(previous_independent_backtesting):
            return False, "A backtesting is already running"
        else:
            tools[constants.BOT_PREPARING_BACKTESTING] = True
            if previous_independent_backtesting:
                interfaces_util.run_in_bot_main_loop(
                    octobot_api.stop_independent_backtesting(previous_independent_backtesting))
            if reset_tentacle_config:
                tentacles_config = interfaces_util.get_edited_config(dict_only=False).get_tentacles_config_path()
                tentacles_setup_config = tentacles_manager_api.get_tentacles_setup_config(tentacles_config)
            else:
                tentacles_setup_config = interfaces_util.get_bot_api().get_edited_tentacles_config()
            config = interfaces_util.get_edited_config()
            exchange_type, contract_type = _parse_trading_type(trading_type)
            config[commons_constants.CONFIG_EXCHANGE_TYPE] = exchange_type
            config[commons_constants.CONFIG_CONTRACT_TYPE] = contract_type
            tools[constants.BOT_TOOLS_BACKTESTING_SOURCE] = source
            if is_optimizer_running and files is None:
                files = [get_data_files_from_current_bot(exchange_id, start_timestamp, end_timestamp, collect=False)]
            if not is_optimizer_running and use_current_bot_data:
                tools[constants.BOT_TOOLS_DATA_COLLECTOR] = \
                    create_snapshot_data_collector(exchange_id, start_timestamp, end_timestamp)
                tools[constants.BOT_TOOLS_BACKTESTING] = None
            else:
                tools[constants.BOT_TOOLS_BACKTESTING] = octobot_api.create_independent_backtesting(
                    config,
                    tentacles_setup_config,
                    files,
                    run_on_common_part_only=run_on_common_part_only,
                    start_timestamp=start_timestamp / 1000 if start_timestamp else None,
                    end_timestamp=end_timestamp / 1000 if end_timestamp else None,
                    enable_logs=enable_logs,
                    stop_when_finished=auto_stop)
                tools[constants.BOT_TOOLS_DATA_COLLECTOR] = None
            interfaces_util.run_in_bot_main_loop(
                _collect_initialize_and_run_independent_backtesting(
                    tools[constants.BOT_TOOLS_DATA_COLLECTOR], tools[constants.BOT_TOOLS_BACKTESTING],
                    config, tentacles_setup_config, files, run_on_common_part_only,
                    start_timestamp, end_timestamp, enable_logs, auto_stop, collector_start_callback, start_callback),
                blocking=False,
                timeout=DATA_COLLECTOR_TIMEOUT)
            return True, "Backtesting started"
    except Exception as e:
        tools[constants.BOT_PREPARING_BACKTESTING] = False
        bot_logging.get_logger("DataCollectorWebInterfaceModel").exception(e, False)
        return False, f"Error when starting backtesting: {e}"


async def _collect_initialize_and_run_independent_backtesting(
        data_collector_instance, independent_backtesting, config, tentacles_setup_config, files, run_on_common_part_only,
        start_timestamp, end_timestamp, enable_logs, auto_stop, collector_start_callback, start_callback):
    logger = bot_logging.get_logger("StartIndependentBacktestingModel")
    if data_collector_instance is not None:
        try:
            if collector_start_callback:
                collector_start_callback()
            files = [await backtesting_api.initialize_and_run_data_collector(data_collector_instance)]
        except Exception as e:
            bot_logging.get_logger("DataCollectorModel").exception(
                e, True, f"Error when collecting historical data: {e}")
            return
        finally:
            web_interface_root.WebInterface.tools[constants.BOT_TOOLS_DATA_COLLECTOR] = None
            web_interface_root.WebInterface.tools[constants.BOT_TOOLS_BACKTESTING] = None
    if independent_backtesting is None:
        try:
            if files is None:
                raise RuntimeError("No datafiles")
            independent_backtesting = octobot_api.create_independent_backtesting(
                config,
                tentacles_setup_config,
                files,
                run_on_common_part_only=run_on_common_part_only,
                start_timestamp=start_timestamp / 1000 if start_timestamp else None,
                end_timestamp=end_timestamp / 1000 if end_timestamp else None,
                enable_logs=enable_logs,
                stop_when_finished=auto_stop)
        except Exception as e:
            logger.exception(e, True, f"Error when initializing backtesting: {e}")
        finally:
            # only unregister collector now that we can associate a backtesting
            web_interface_root.WebInterface.tools[constants.BOT_TOOLS_BACKTESTING] = independent_backtesting
            web_interface_root.WebInterface.tools[constants.BOT_TOOLS_DATA_COLLECTOR] = None
    try:
        web_interface_root.WebInterface.tools[constants.BOT_PREPARING_BACKTESTING] = False
        if files is not None:
            if start_callback:
                start_callback()
            await octobot_api.initialize_and_run_independent_backtesting(independent_backtesting)
        else:
            logger.error(f"Data files is None when initializing backtesting: impossible to start")
    except Exception as e:
        logger.exception(e, True, f"Error when running backtesting: {e}")
        try:
            await octobot_api.stop_independent_backtesting(independent_backtesting)
            web_interface_root.WebInterface.tools[constants.BOT_TOOLS_BACKTESTING] = None
        except Exception as e:
            logger.exception(e, True, f"Error when stopping backtesting: {e}")


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


def get_latest_backtesting_run_id(trading_mode):
    tools = web_interface_root.WebInterface.tools
    if tools[constants.BOT_TOOLS_BACKTESTING]:
        backtesting = tools[constants.BOT_TOOLS_BACKTESTING]
        interfaces_util.run_in_bot_main_loop(octobot_api.join_independent_backtesting_stop(backtesting,
                                                                                           STOPPING_TIMEOUT))
        bot_id = octobot_api.get_independent_backtesting_bot_id(backtesting)
        return {
            "id": databases.RunDatabasesProvider.instance().get_run_databases_identifier(
                bot_id
            ).backtesting_id
        }
    return {}


def get_delete_data_file(file_name):
    deleted, error = backtesting_api.delete_data_file(file_name)
    if deleted:
        return deleted, f"{file_name} deleted"
    else:
        return deleted, f"Can't delete {file_name} ({error})"


def get_data_collector_status():
    progress = {"current_step": 0, "total_steps": 0, "current_step_percent": 0}
    if web_interface_root.WebInterface.tools[constants.BOT_TOOLS_DATA_COLLECTOR] is not None:
        data_collector = web_interface_root.WebInterface.tools[constants.BOT_TOOLS_DATA_COLLECTOR]
        if backtesting_api.is_data_collector_in_progress(data_collector):
            current_step, total_steps, current_step_percent = \
                backtesting_api.get_data_collector_progress(data_collector)
            progress["current_step"] = current_step
            progress["total_steps"] = total_steps
            progress["current_step_percent"] = current_step_percent
            return "collecting", progress
        if backtesting_api.is_data_collector_finished(data_collector):
            return "finished", progress
        return "starting", progress
    return "not started", progress


def stop_data_collector():
    success = False
    message = "Failed to stop data collector"
    if web_interface_root.WebInterface.tools[constants.BOT_TOOLS_DATA_COLLECTOR] is not None:
        success = interfaces_util.run_in_bot_main_loop(backtesting_api.stop_data_collector(web_interface_root.WebInterface.tools[constants.BOT_TOOLS_DATA_COLLECTOR]))
        message = "Data collector stopped"
        web_interface_root.WebInterface.tools[constants.BOT_TOOLS_DATA_COLLECTOR] = None
    return success, message


def create_snapshot_data_collector(exchange_id, start_timestamp, end_timestamp):
    exchange_manager = trading_api.get_exchange_manager_from_exchange_id(exchange_id)
    return backtesting_api.exchange_bot_snapshot_data_collector_factory(
        trading_api.get_exchange_name(exchange_manager),
        interfaces_util.get_bot_api().get_edited_tentacles_config(),
        trading_api.get_trading_symbols(exchange_manager),
        exchange_id,
        time_frames=trading_api.get_relevant_time_frames(exchange_manager),
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp)


def get_data_files_from_current_bot(exchange_id, start_timestamp, end_timestamp, collect=True):
    data_collector_instance = create_snapshot_data_collector(exchange_id, start_timestamp, end_timestamp)
    if not collect:
        return data_collector_instance.file_name
    web_interface_root.WebInterface.tools[constants.BOT_TOOLS_DATA_COLLECTOR] = data_collector_instance
    try:
        collected_files = interfaces_util.run_in_bot_main_loop(
            backtesting_api.initialize_and_run_data_collector(data_collector_instance),
            timeout=DATA_COLLECTOR_TIMEOUT
        )
        return collected_files
    finally:
        web_interface_root.WebInterface.tools[constants.BOT_TOOLS_DATA_COLLECTOR] = None


def collect_data_file(exchange, symbols, time_frames=None, start_timestamp=None, end_timestamp=None):
    if not exchange:
        return False, "Please select an exchange."
    if not symbols:
        return False, "Please select a trading pair."
    if web_interface_root.WebInterface.tools[constants.BOT_TOOLS_DATA_COLLECTOR] is None or \
            backtesting_api.is_data_collector_finished(
                web_interface_root.WebInterface.tools[constants.BOT_TOOLS_DATA_COLLECTOR]):
        if time_frames is not None:
            time_frames = time_frames if isinstance(time_frames, list) else [time_frames]
            if not any(isinstance(time_frame, commons_enums.TimeFrames) for time_frame in time_frames):
                time_frames = time_frame_manager.parse_time_frames(time_frames)
        first_symbol = commons_symbols.parse_symbol(symbols[0])
        exchange_type = trading_enums.ExchangeTypes.SPOT if first_symbol.is_spot() \
            else trading_enums.ExchangeTypes.FUTURE if first_symbol.is_future() \
            else trading_enums.ExchangeTypes.UNKNOWN
        _background_collect_exchange_historical_data(exchange, exchange_type, symbols, time_frames,
                                                     start_timestamp, end_timestamp)
        return True, f"Historical data collection started."
    else:
        return False, f"Can't collect data for {symbols} on {exchange} (Historical data collector is already running)"


async def _start_collect_and_notify(data_collector_instance):
    success = False
    message = "finished"
    try:
        await backtesting_api.initialize_and_run_data_collector(data_collector_instance)
        success = True
    except Exception as e:
        message = f"error: {e}"
    notification_level = services_enums.NotificationLevel.SUCCESS if success else services_enums.NotificationLevel.DANGER
    await web_interface_root.add_notification(notification_level, f"Data collection", message)


def _background_collect_exchange_historical_data(exchange, exchange_type, symbols, time_frames,
                                                 start_timestamp, end_timestamp):
    data_collector_instance = backtesting_api.exchange_historical_data_collector_factory(
        exchange,
        exchange_type,
        interfaces_util.get_bot_api().get_edited_tentacles_config(),
        [commons_symbols.parse_symbol(symbol) for symbol in symbols],
        time_frames=time_frames,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp)
    web_interface_root.WebInterface.tools[constants.BOT_TOOLS_DATA_COLLECTOR] = data_collector_instance
    coro = _start_collect_and_notify(data_collector_instance)
    threading.Thread(target=asyncio.run, args=(coro,), name=f"DataCollector{symbols}").start()


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
        bot_logging.get_logger("DataCollectorWebInterfaceModel").exception(e, True, message)
        return message


def save_data_file(name, file):
    try:
        output_file = f"{backtesting_constants.BACKTESTING_FILE_PATH}/{name}"
        file.save(output_file)
        message = interfaces_util.run_in_bot_async_executor(_convert_into_octobot_data_file_if_necessary(output_file))
        bot_logging.get_logger("DataCollectorWebInterfaceModel").info(message)
        return True, message
    except Exception as e:
        message = f"Error when saving file: {e}. File can't be saved."
        bot_logging.get_logger("DataCollectorWebInterfaceModel").error(message)
        return False, message
