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
import numpy as np
import math

import octobot_backtesting.api as backtesting_api
import octobot_services.interfaces.util as interfaces_util
import octobot_trading.api as trading_api
import octobot_trading.enums as trading_enums
import octobot_trading.constants as trading_constants
import tentacles.Services.Interfaces.web_interface as web_interface
import tentacles.Services.Interfaces.web_interface.constants as constants
import tentacles.Services.Interfaces.web_interface.enums as enums
import octobot_commons.timestamp_util as timestamp_util
import octobot_commons.time_frame_manager as time_frame_manager
import octobot_commons.enums as commons_enums
import octobot_commons.symbols as commons_symbols

GET_SYMBOL_SEPARATOR = "|"
DISPLAY_CANCELLED_TRADES = False


def parse_get_symbol(get_symbol):
    return get_symbol.replace(GET_SYMBOL_SEPARATOR, "/")


def get_value_from_dict_or_string(data):
    if isinstance(data, dict):
        return data["value"]
    else:
        return data


def format_trades(dict_trade_history):
    trade_time_key = "time"
    trade_price_key = "price"
    trade_description_key = "trade_description"
    trade_order_side_key = "order_side"
    trades = {
        trade_time_key: [],
        trade_price_key: [],
        trade_description_key: [],
        trade_order_side_key: []
    }

    for dict_trade in dict_trade_history:
        status = dict_trade.get(trading_enums.ExchangeConstantsOrderColumns.STATUS.value,
                                trading_enums.OrderStatus.UNKNOWN.value)
        trade_side = trading_enums.TradeOrderSide(dict_trade[trading_enums.ExchangeConstantsOrderColumns.SIDE.value])
        trade_type = trading_api.parse_trade_type(dict_trade)
        if trade_type == trading_enums.TraderOrderType.UNKNOWN:
            trade_type = trade_side
        if status is not trading_enums.OrderStatus.CANCELED.value or DISPLAY_CANCELLED_TRADES:
            trade_time = dict_trade[trading_enums.ExchangeConstantsOrderColumns.TIMESTAMP.value]
            if trade_time > trading_constants.MINIMUM_VAL_TRADE_TIME:
                trades[trade_time_key].append(
                    timestamp_util.convert_timestamp_to_datetime(trade_time, time_format="%y-%m-%d %H:%M:%S"))
                trades[trade_price_key].append(
                    float(dict_trade[trading_enums.ExchangeConstantsOrderColumns.PRICE.value]))
                trades[trade_description_key].append(
                    f"{trade_type.name.replace('_', ' ')}: "
                    f"{dict_trade[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value]}")
                trades[trade_order_side_key].append(trade_side.value)

    return trades


def _remove_invalid_chars(string):
    return string.split("[")[0]


def _get_candles_reply(exchange, exchange_id, symbol, time_frame):
    return {
        "exchange_name": _remove_invalid_chars(exchange),
        "exchange_id": exchange_id,
        "symbol": symbol,
        "time_frame": time_frame.value
    }


def _get_first_exchange_identifiers(exchange_name=None):
    for exchange_manager in interfaces_util.get_exchange_managers():
        name = trading_api.get_exchange_name(exchange_manager)
        if exchange_name is None or name == exchange_name:
            return exchange_manager, name, trading_api.get_exchange_manager_id(exchange_manager)
    raise KeyError("No exchange to be found")


def get_first_exchange_data(exchange_name=None):
    return _get_first_exchange_identifiers(exchange_name)


def get_watched_symbol_data(symbol):
    symbol_object = commons_symbols.parse_symbol(parse_get_symbol(symbol))
    try:
        last_possibility = {}
        for exchange_manager in interfaces_util.get_exchange_managers():
            exchange_id = trading_api.get_exchange_manager_id(exchange_manager)
            exchange_name = trading_api.get_exchange_name(exchange_manager)
            last_possibility = _get_candles_reply(
                    exchange_name,
                    exchange_id,
                    symbol,
                    _get_time_frame(exchange_name, exchange_id)
                )
            if symbol_object in trading_api.get_trading_symbols(exchange_manager):
                return last_possibility
        # symbol has not been found in exchange, still return the last exchange
        # in case it becomes available
        return last_possibility
    except KeyError:
        return {}


def _get_time_frame(exchange_name, exchange_id):
    try:
        return time_frame_manager.get_display_time_frame(interfaces_util.get_global_config(),
                                                         commons_enums.TimeFrames(constants.DEFAULT_TIMEFRAME))
    except IndexError:
        # second try with watched timeframes, there might be a real-time time frame available
        return trading_api.get_watched_timeframes(
            trading_api.get_exchange_manager_from_exchange_name_and_id(exchange_name, exchange_id)
        )[0]


def _is_symbol_data_available(exchange_manager, symbol):
    return symbol in trading_api.get_trading_pairs(exchange_manager)


def get_watched_symbols():
    config = interfaces_util.get_edited_config()
    if constants.CONFIG_WATCHED_SYMBOLS not in config:
        config[constants.CONFIG_WATCHED_SYMBOLS] = []
    return config[constants.CONFIG_WATCHED_SYMBOLS]


def get_startup_messages():
    return interfaces_util.get_bot_api().get_startup_messages()


def get_first_symbol_data():
    try:
        exchange, exchange_name, exchange_id = _get_first_exchange_identifiers()
        symbol = trading_api.get_trading_pairs(exchange)[0]
        time_frame = _get_time_frame(exchange_name, exchange_id)
        return _get_candles_reply(exchange_name, exchange_id, symbol, time_frame)
    except (KeyError, IndexError):
        return {}


def _create_candles_data(symbol, time_frame, historical_candles, kline, bot_api, list_arrays, in_backtesting,
                         ignore_trades):
    candles_key = "candles"
    real_trades_key = "real_trades"
    simulated_trades_key = "simulated_trades"
    result_dict = {
        candles_key: {},
        real_trades_key: {},
        simulated_trades_key: {},
    }
    try:
        if not in_backtesting:
            web_interface.add_to_symbol_data_history(symbol, historical_candles, time_frame, False)
            data = web_interface.get_symbol_data_history(symbol, time_frame)
        else:
            data = historical_candles

        # add kline as the last (current) candle that is not yet in history
        if math.nan not in kline and data[commons_enums.PriceIndexes.IND_PRICE_TIME.value][-1] != kline[
            commons_enums.PriceIndexes.IND_PRICE_TIME.value]:
            data[commons_enums.PriceIndexes.IND_PRICE_TIME.value] = np.append(
                data[commons_enums.PriceIndexes.IND_PRICE_TIME.value],
                kline[commons_enums.PriceIndexes.IND_PRICE_TIME.value])
            data[commons_enums.PriceIndexes.IND_PRICE_CLOSE.value] = np.append(
                data[commons_enums.PriceIndexes.IND_PRICE_CLOSE.value],
                kline[commons_enums.PriceIndexes.IND_PRICE_CLOSE.value])
            data[commons_enums.PriceIndexes.IND_PRICE_LOW.value] = np.append(
                data[commons_enums.PriceIndexes.IND_PRICE_LOW.value],
                kline[commons_enums.PriceIndexes.IND_PRICE_LOW.value])
            data[commons_enums.PriceIndexes.IND_PRICE_OPEN.value] = np.append(
                data[commons_enums.PriceIndexes.IND_PRICE_OPEN.value],
                kline[commons_enums.PriceIndexes.IND_PRICE_OPEN.value])
            data[commons_enums.PriceIndexes.IND_PRICE_HIGH.value] = np.append(
                data[commons_enums.PriceIndexes.IND_PRICE_HIGH.value],
                kline[commons_enums.PriceIndexes.IND_PRICE_HIGH.value])
            data[commons_enums.PriceIndexes.IND_PRICE_VOL.value] = np.append(
                data[commons_enums.PriceIndexes.IND_PRICE_VOL.value],
                kline[commons_enums.PriceIndexes.IND_PRICE_VOL.value])
        data_x = timestamp_util.convert_timestamps_to_datetime(data[commons_enums.PriceIndexes.IND_PRICE_TIME.value],
                                                               time_format="%y-%m-%d %H:%M:%S",
                                                               force_timezone=False)

        independent_backtesting = web_interface.WebInterface.tools[
            constants.BOT_TOOLS_BACKTESTING] if in_backtesting else None
        bot_api_for_history = None if in_backtesting else bot_api
        if not ignore_trades:
            # handle trades after the 1st displayed candle start time for dashboard
            first_time_to_handle_in_board = data[commons_enums.PriceIndexes.IND_PRICE_TIME.value][0]
            real_trades_history, simulated_trades_history = \
                interfaces_util.get_trades_history(bot_api_for_history,
                                                   symbol,
                                                   independent_backtesting,
                                                   since=first_time_to_handle_in_board,
                                                   as_dict=True)

            if real_trades_history:
                result_dict[real_trades_key] = format_trades(real_trades_history)

            if simulated_trades_history:
                result_dict[simulated_trades_key] = format_trades(simulated_trades_history)

        if list_arrays:
            result_dict[candles_key] = {
                enums.PriceStrings.STR_PRICE_TIME.value: data_x,
                enums.PriceStrings.STR_PRICE_CLOSE.value: data[
                    commons_enums.PriceIndexes.IND_PRICE_CLOSE.value].tolist(),
                enums.PriceStrings.STR_PRICE_LOW.value: data[commons_enums.PriceIndexes.IND_PRICE_LOW.value].tolist(),
                enums.PriceStrings.STR_PRICE_OPEN.value: data[commons_enums.PriceIndexes.IND_PRICE_OPEN.value].tolist(),
                enums.PriceStrings.STR_PRICE_HIGH.value: data[commons_enums.PriceIndexes.IND_PRICE_HIGH.value].tolist(),
                enums.PriceStrings.STR_PRICE_VOL.value: data[commons_enums.PriceIndexes.IND_PRICE_VOL.value].tolist()
            }
        else:
            result_dict[candles_key] = {
                enums.PriceStrings.STR_PRICE_TIME.value: data_x,
                enums.PriceStrings.STR_PRICE_CLOSE.value: data[commons_enums.PriceIndexes.IND_PRICE_CLOSE.value],
                enums.PriceStrings.STR_PRICE_LOW.value: data[commons_enums.PriceIndexes.IND_PRICE_LOW.value],
                enums.PriceStrings.STR_PRICE_OPEN.value: data[commons_enums.PriceIndexes.IND_PRICE_OPEN.value],
                enums.PriceStrings.STR_PRICE_HIGH.value: data[commons_enums.PriceIndexes.IND_PRICE_HIGH.value]
            }
    except IndexError:
        pass
    return result_dict


def get_currency_price_graph_update(exchange_id, symbol, time_frame, list_arrays=True, backtesting=False,
                                    minimal_candles=False, ignore_trades=False):
    bot_api = interfaces_util.get_bot_api()
    # TODO: handle on the fly backtesting price graph
    # if backtesting and WebInterface and WebInterface.tools[BOT_TOOLS_BACKTESTING]:
    #     bot = WebInterface.tools[BOT_TOOLS_BACKTESTING].get_bot()
    parsed_symbol = commons_symbols.parse_symbol(parse_get_symbol(symbol))
    in_backtesting = backtesting_api.is_backtesting_enabled(interfaces_util.get_global_config()) or backtesting
    exchange_manager = trading_api.get_exchange_manager_from_exchange_id(exchange_id)
    symbol_id = str(parsed_symbol)
    if time_frame is not None:
        try:
            symbol_data = trading_api.get_symbol_data(exchange_manager, symbol_id, allow_creation=False)
            limit = 1 if minimal_candles else -1
            historical_candles = trading_api.get_symbol_historical_candles(symbol_data, time_frame, limit=limit)
            kline = [math.nan]
            if trading_api.has_symbol_klines(symbol_data, time_frame):
                kline = trading_api.get_symbol_klines(symbol_data, time_frame)
            if historical_candles is not None:
                return _create_candles_data(symbol_id, time_frame, historical_candles,
                                            kline, bot_api, list_arrays, in_backtesting, ignore_trades)
        except KeyError:
            traded_pairs = trading_api.get_trading_pairs(exchange_manager)
            if not traded_pairs or symbol_id in traded_pairs:
                # not started yet
                return None
            else:
                return {"error": f"no data for {parsed_symbol}"}
    return None
