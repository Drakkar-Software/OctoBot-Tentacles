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

from octobot_backtesting.api.backtesting import is_backtesting_enabled
from octobot_interfaces.util.bot import get_bot, get_global_config
from octobot_trading.api.exchange import get_exchange_manager_from_exchange_name, get_exchange_names
from octobot_trading.api.symbol_data import get_symbol_candles_manager, get_symbol_data
from tentacles.Interfaces.interfaces.web import add_to_symbol_data_history, get_symbol_data_history
from tentacles.Interfaces.interfaces.web.constants import DEFAULT_TIMEFRAME
from octobot_commons.timestamp_util import convert_timestamps_to_datetime, convert_timestamp_to_datetime
from octobot_commons.time_frame_manager import get_display_time_frame
from octobot_commons.constants import CONFIG_WILDCARD
from octobot_commons.enums import PriceIndexes, PriceStrings, TimeFrames
from octobot_interfaces.util.trader import get_trades_history

GET_SYMBOL_SEPARATOR = "|"


def parse_get_symbol(get_symbol):
    return get_symbol.replace(GET_SYMBOL_SEPARATOR, "/")


def get_value_from_dict_or_string(data):
    if isinstance(data, dict):
        return data["value"]
    else:
        return data


def _format_trades(trade_history):
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

    for trade in trade_history:
        trades[trade_time_key].append(convert_timestamp_to_datetime(trade.filled_time,
                                                                    time_format="%y-%m-%d %H:%M:%S"))
        trades[trade_price_key].append(trade.price)
        trades[trade_description_key].append(f"{trade.order_type.name}: {trade.quantity}")
        trades[trade_order_side_key].append(trade.side.value)

    return trades


def remove_invalid_chars(string):
    return string.split("[")[0]


def _get_candles_reply(exchange, symbol, time_frame):
    return {
        "exchange": remove_invalid_chars(exchange),
        "symbol": symbol,
        "time_frame": time_frame.value
    }


def get_watched_symbol_data(symbol):
    exchanges = get_exchange_names()
    symbol = parse_get_symbol(symbol)
    try:
        if exchanges:
            exchange = next(iter(exchanges))
            time_frame = get_display_time_frame(get_global_config(), TimeFrames(DEFAULT_TIMEFRAME))
            return _get_candles_reply(exchange, symbol, time_frame)
    except KeyError:
        return {}
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


def get_first_symbol_data():
    bot = get_bot()
    exchanges = bot.get_exchanges_list()

    try:
        if exchanges:
            exchange = next(iter(exchanges.values()))
            evaluators = bot.get_symbol_evaluator_list()
            if evaluators:
                symbol_evaluator = _find_symbol_evaluator_with_data(evaluators, exchange)
                time_frame = get_display_time_frame(bot.get_config())
                return _get_candles_reply(exchange, symbol_evaluator, time_frame)
    except KeyError:
        return {}
    return {}


# TODO remove this function and its calls when https://github.com/Drakkar-Software/OctoBot-Trading/issues/31 is fixed
def _filter_invalid_values(data_array):
    return [val for val in data_array if val != -1]


def _create_candles_data(symbol, time_frame, new_data, bot, list_arrays, in_backtesting):
    candles_key = "candles"
    real_trades_key = "real_trades"
    simulated_trades_key = "simulated_trades"
    result_dict = {
        candles_key: [],
        real_trades_key: [],
        simulated_trades_key: [],
    }

    if not in_backtesting:
        add_to_symbol_data_history(symbol, new_data, time_frame, False)
        data = get_symbol_data_history(symbol, time_frame)
    else:
        data = new_data

    data_x = convert_timestamps_to_datetime(_filter_invalid_values(data[PriceIndexes.IND_PRICE_TIME.value]),
                                            time_format="%y-%m-%d %H:%M:%S",
                                            force_timezone=False)

    real_trades_history, simulated_trades_history = get_trades_history(bot, symbol)

    if real_trades_history:
        result_dict[real_trades_key] = _format_trades(real_trades_history)

    if simulated_trades_history:
        result_dict[simulated_trades_key] = _format_trades(simulated_trades_history)

    if list_arrays:
        result_dict[candles_key] = {
            PriceStrings.STR_PRICE_TIME.value: _filter_invalid_values(data_x),
            PriceStrings.STR_PRICE_CLOSE.value: _filter_invalid_values(data[PriceIndexes.IND_PRICE_CLOSE.value].tolist()),
            PriceStrings.STR_PRICE_LOW.value: _filter_invalid_values(data[PriceIndexes.IND_PRICE_LOW.value].tolist()),
            PriceStrings.STR_PRICE_OPEN.value: _filter_invalid_values(data[PriceIndexes.IND_PRICE_OPEN.value].tolist()),
            PriceStrings.STR_PRICE_HIGH.value: _filter_invalid_values(data[PriceIndexes.IND_PRICE_HIGH.value].tolist()),
            PriceStrings.STR_PRICE_VOL.value: _filter_invalid_values(data[PriceIndexes.IND_PRICE_VOL.value].tolist())
        }
    else:
        result_dict[candles_key] = {
            PriceStrings.STR_PRICE_TIME.value: _filter_invalid_values(data_x),
            PriceStrings.STR_PRICE_CLOSE.value: _filter_invalid_values(data[PriceIndexes.IND_PRICE_CLOSE.value]),
            PriceStrings.STR_PRICE_LOW.value: _filter_invalid_values(data[PriceIndexes.IND_PRICE_LOW.value]),
            PriceStrings.STR_PRICE_OPEN.value: _filter_invalid_values(data[PriceIndexes.IND_PRICE_OPEN.value]),
            PriceStrings.STR_PRICE_HIGH.value: _filter_invalid_values(data[PriceIndexes.IND_PRICE_HIGH.value])
        }
    return result_dict


def get_currency_price_graph_update(exchange_name, symbol, time_frame, list_arrays=True, backtesting=False):
    bot = get_bot()
    # TODO: handle on the fly backtesting price graph
    # if backtesting and WebInterface and WebInterface.tools[BOT_TOOLS_BACKTESTING]:
    #     bot = WebInterface.tools[BOT_TOOLS_BACKTESTING].get_bot()
    symbol = parse_get_symbol(symbol)
    in_backtesting = is_backtesting_enabled(get_global_config()) or backtesting

    exchange_manager = get_exchange_manager_from_exchange_name(exchange_name)
    if backtesting:
        exchanges = get_exchange_names()
        if exchanges:
            exchange_manager =  get_exchange_manager_from_exchange_name(exchanges[0])

    if time_frame is not None:
        symbol_data = get_symbol_data(exchange_manager, symbol)
        try:
            data = get_symbol_candles_manager(symbol_data, time_frame).get_symbol_prices()
            if data is not None:
                return _create_candles_data(symbol, time_frame, data, bot, list_arrays, in_backtesting)
        except KeyError:
            # not started yet
            return None
    return None
