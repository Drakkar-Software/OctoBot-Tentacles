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
from math import nan

from octobot_backtesting.api.backtesting import is_backtesting_enabled
from octobot_services.interfaces.util.bot import get_global_config, get_bot_api
from octobot_services.interfaces.util.util import get_exchange_managers
from octobot_trading.api.exchange import get_trading_pairs, get_exchange_manager_from_exchange_id, \
    get_exchange_manager_id, get_exchange_manager_from_exchange_name_and_id, get_watched_timeframes, get_exchange_name
from octobot_trading.api.trades import parse_trade_type
from octobot_trading.enums import OrderStatus, ExchangeConstantsOrderColumns, TradeOrderSide, TraderOrderType
from octobot_trading.api.symbol_data import get_symbol_data, get_symbol_historical_candles, get_symbol_klines, \
    has_symbol_klines
from tentacles.Services.Interfaces.web_interface import WebInterface
from tentacles.Services.Interfaces.web_interface import add_to_symbol_data_history, get_symbol_data_history
from tentacles.Services.Interfaces.web_interface.constants import DEFAULT_TIMEFRAME, BOT_TOOLS_BACKTESTING
from tentacles.Services.Interfaces.web_interface.enums import PriceStrings
from octobot_commons.timestamp_util import convert_timestamps_to_datetime, convert_timestamp_to_datetime
from octobot_commons.time_frame_manager import get_display_time_frame
from octobot_commons.constants import CONFIG_WILDCARD
from octobot_commons.enums import PriceIndexes, TimeFrames
from octobot_services.interfaces.util.trader import get_trades_history

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
        status = dict_trade[ExchangeConstantsOrderColumns.STATUS.value]
        trade_side = TradeOrderSide(dict_trade[ExchangeConstantsOrderColumns.SIDE.value])
        trade_type = parse_trade_type(dict_trade)
        if trade_type == TraderOrderType.UNKNOWN:
            trade_type = trade_side
        if status is not OrderStatus.CANCELED.value or DISPLAY_CANCELLED_TRADES:
            trade_time = dict_trade[ExchangeConstantsOrderColumns.TIMESTAMP.value]
            trades[trade_time_key].append(convert_timestamp_to_datetime(trade_time, time_format="%y-%m-%d %H:%M:%S"))
            trades[trade_price_key].append(dict_trade[ExchangeConstantsOrderColumns.PRICE.value])
            trades[trade_description_key].append(
                f"{trade_type.name.replace('_', ' ')}: {dict_trade[ExchangeConstantsOrderColumns.AMOUNT.value]}")
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


def _get_first_exchange_identifiers():
    for exchange_manager in get_exchange_managers():
        return exchange_manager, get_exchange_name(exchange_manager), get_exchange_manager_id(exchange_manager)
    raise KeyError("No exchange to be found")


def get_watched_symbol_data(symbol):
    symbol = parse_get_symbol(symbol)
    try:
        _, exchange_name, exchange_id = _get_first_exchange_identifiers()
        time_frame = _get_time_frame(exchange_name, exchange_id)
        return _get_candles_reply(exchange_name, exchange_id, symbol, time_frame)
    except KeyError:
        return {}


def _find_symbol_evaluator_with_data(evaluators, exchange):
    symbol_evaluator = next(iter(evaluators.values()))
    first_symbol = symbol_evaluator.get_symbol()
    exchange_traded_pairs = exchange.get_exchange_manager().get_traded_pairs()
    if first_symbol in exchange_traded_pairs:
        return symbol_evaluator
    elif first_symbol == CONFIG_WILDCARD:
        return evaluators[exchange_traded_pairs[0]]
    else:
        for symbol in evaluators.keys():
            if symbol in exchange_traded_pairs:
                return evaluators[symbol]
    return symbol_evaluator


def _get_time_frame(exchange_name, exchange_id):
    try:
        return get_display_time_frame(get_global_config(), TimeFrames(DEFAULT_TIMEFRAME))
    except IndexError:
        # second try with watched timeframes, there might be a real-time time frame available
        return get_watched_timeframes(
            get_exchange_manager_from_exchange_name_and_id(exchange_name, exchange_id)
        )[0]


def get_first_symbol_data():
    try:
        exchange, exchange_name, exchange_id = _get_first_exchange_identifiers()
        symbol = get_trading_pairs(exchange)[0]
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

    if not in_backtesting:
        add_to_symbol_data_history(symbol, historical_candles, time_frame, False)
        data = get_symbol_data_history(symbol, time_frame)
    else:
        data = historical_candles

    # add kline as the last (current) candle that is not yet in history
    if nan not in kline and data[PriceIndexes.IND_PRICE_TIME.value][-1] != kline[PriceIndexes.IND_PRICE_TIME.value]:
        data[PriceIndexes.IND_PRICE_TIME.value] = np.append(data[PriceIndexes.IND_PRICE_TIME.value],
                                                            kline[PriceIndexes.IND_PRICE_TIME.value])
        data[PriceIndexes.IND_PRICE_CLOSE.value] = np.append(data[PriceIndexes.IND_PRICE_CLOSE.value],
                                                             kline[PriceIndexes.IND_PRICE_CLOSE.value])
        data[PriceIndexes.IND_PRICE_LOW.value] = np.append(data[PriceIndexes.IND_PRICE_LOW.value],
                                                           kline[PriceIndexes.IND_PRICE_LOW.value])
        data[PriceIndexes.IND_PRICE_OPEN.value] = np.append(data[PriceIndexes.IND_PRICE_OPEN.value],
                                                            kline[PriceIndexes.IND_PRICE_OPEN.value])
        data[PriceIndexes.IND_PRICE_HIGH.value] = np.append(data[PriceIndexes.IND_PRICE_HIGH.value],
                                                            kline[PriceIndexes.IND_PRICE_HIGH.value])
        data[PriceIndexes.IND_PRICE_VOL.value] = np.append(data[PriceIndexes.IND_PRICE_VOL.value],
                                                           kline[PriceIndexes.IND_PRICE_VOL.value])
    data_x = convert_timestamps_to_datetime(data[PriceIndexes.IND_PRICE_TIME.value],
                                            time_format="%y-%m-%d %H:%M:%S",
                                            force_timezone=False)

    independent_backtesting = WebInterface.tools[BOT_TOOLS_BACKTESTING] if in_backtesting else None
    bot_api_for_history = None if in_backtesting else bot_api
    if not ignore_trades:
        # handle trades after the 1st displayed candle start time for dashboard
        first_time_to_handle_in_board = data[PriceIndexes.IND_PRICE_TIME.value][0]
        real_trades_history, simulated_trades_history = get_trades_history(bot_api_for_history,
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
            PriceStrings.STR_PRICE_TIME.value: data_x,
            PriceStrings.STR_PRICE_CLOSE.value: data[PriceIndexes.IND_PRICE_CLOSE.value].tolist(),
            PriceStrings.STR_PRICE_LOW.value: data[PriceIndexes.IND_PRICE_LOW.value].tolist(),
            PriceStrings.STR_PRICE_OPEN.value: data[PriceIndexes.IND_PRICE_OPEN.value].tolist(),
            PriceStrings.STR_PRICE_HIGH.value: data[PriceIndexes.IND_PRICE_HIGH.value].tolist(),
            PriceStrings.STR_PRICE_VOL.value: data[PriceIndexes.IND_PRICE_VOL.value].tolist()
        }
    else:
        result_dict[candles_key] = {
            PriceStrings.STR_PRICE_TIME.value: data_x,
            PriceStrings.STR_PRICE_CLOSE.value: data[PriceIndexes.IND_PRICE_CLOSE.value],
            PriceStrings.STR_PRICE_LOW.value: data[PriceIndexes.IND_PRICE_LOW.value],
            PriceStrings.STR_PRICE_OPEN.value: data[PriceIndexes.IND_PRICE_OPEN.value],
            PriceStrings.STR_PRICE_HIGH.value: data[PriceIndexes.IND_PRICE_HIGH.value]
        }
    return result_dict


def get_currency_price_graph_update(exchange_id, symbol, time_frame, list_arrays=True, backtesting=False,
                                    minimal_candles=False, ignore_trades=False):
    bot_api = get_bot_api()
    # TODO: handle on the fly backtesting price graph
    # if backtesting and WebInterface and WebInterface.tools[BOT_TOOLS_BACKTESTING]:
    #     bot = WebInterface.tools[BOT_TOOLS_BACKTESTING].get_bot()
    symbol = parse_get_symbol(symbol)
    in_backtesting = is_backtesting_enabled(get_global_config()) or backtesting
    exchange_manager = get_exchange_manager_from_exchange_id(exchange_id)
    if time_frame is not None:
        try:
            symbol_data = get_symbol_data(exchange_manager, symbol, allow_creation=False)
            limit = 1 if minimal_candles else -1
            historical_candles = get_symbol_historical_candles(symbol_data, time_frame, limit=limit)
            kline = [nan]
            if has_symbol_klines(symbol_data, time_frame):
                kline = get_symbol_klines(symbol_data, time_frame)
            if historical_candles is not None:
                return _create_candles_data(symbol, time_frame, historical_candles,
                                            kline, bot_api, list_arrays, in_backtesting, ignore_trades)
        except KeyError:
            # not started yet
            return None
    return None
