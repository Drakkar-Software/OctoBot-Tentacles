#  Drakkar-Software OctoBot-Commons
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
import mock
import pytest

import numpy as np

import octobot_commons.enums
import octobot_commons.errors
import octobot_commons.dsl_interpreter as dsl_interpreter
import tentacles.Meta.DSL_operators.exchange_operators as exchange_operators


SYMBOL = "BTC/USDT"
SYMBOL2 = "ETH/USDT"
TIME_FRAME = "1h"
TIME_FRAME2 = "4h"


@pytest.fixture
def historical_prices():
    return np.array([
        81.59, 81.06, 82.87, 83, 83.61, 83.15, 82.84, 83.99, 84.55, 84.36, 85.53, 86.54, 86.89, 
        87.77, 87.29, 87.18, 87.01, 89.02, 89.68, 90.36, 92.83, 93.37, 93.02, 93.45, 94.13, 
        93.12, 93.18, 92.08, 92.82, 92.92, 92.25, 92.22
    ])


@pytest.fixture
def historical_volume(historical_prices):
    base_volume_pattern = [
        # will create an int np.array, which will updated to float64 to comply with tulipy requirements
        903, 1000, 2342, 992, 900, 1231, 1211, 1113
    ]
    return np.array(base_volume_pattern*(len(historical_prices) // len(base_volume_pattern) + 1))[:len(historical_prices)]


def _get_candle_managers(historical_prices, historical_volume):
    btc_1h_candles_manager = mock.Mock(
        get_symbol_open_candles=mock.Mock(return_value=historical_prices),
        get_symbol_high_candles=mock.Mock(return_value=historical_prices),
        get_symbol_low_candles=mock.Mock(return_value=historical_prices),
        get_symbol_close_candles=mock.Mock(return_value=historical_prices),
        get_symbol_volume_candles=mock.Mock(return_value=historical_volume),
        get_symbol_time_candles=mock.Mock(return_value=historical_prices),
    )
    eth_1h_candles_manager = mock.Mock(
        get_symbol_open_candles=mock.Mock(return_value=historical_prices / 2),
        get_symbol_high_candles=mock.Mock(return_value=historical_prices / 2),
        get_symbol_low_candles=mock.Mock(return_value=historical_prices / 2),
        get_symbol_close_candles=mock.Mock(return_value=historical_prices / 2),
        get_symbol_volume_candles=mock.Mock(return_value=historical_volume / 2),
        get_symbol_time_candles=mock.Mock(return_value=historical_prices / 2),
    )
    btc_4h_candles_manager = mock.Mock(
        get_symbol_open_candles=mock.Mock(return_value=historical_prices * 2),
        get_symbol_high_candles=mock.Mock(return_value=historical_prices * 2),
        get_symbol_low_candles=mock.Mock(return_value=historical_prices * 2),
        get_symbol_close_candles=mock.Mock(return_value=historical_prices * 2),
        get_symbol_volume_candles=mock.Mock(return_value=historical_volume * 2),
        get_symbol_time_candles=mock.Mock(return_value=historical_prices * 2),
    )
    return (
        btc_1h_candles_manager,
        eth_1h_candles_manager,
        btc_4h_candles_manager,
    )


@pytest.fixture
def exchange_manager_with_candles(historical_prices, historical_volume):
    btc_1h_candles_manager, eth_1h_candles_manager, btc_4h_candles_manager = _get_candle_managers(
        historical_prices, historical_volume
    )
    def _get_symbol_data(symbol: str, **kwargs):
        symbol_candles = {}
        one_h_candles_manager = btc_1h_candles_manager if symbol == SYMBOL else eth_1h_candles_manager if symbol == SYMBOL2 else None
        four_h_candles_manager = btc_4h_candles_manager if symbol == SYMBOL else None # no 4h eth candles
        if one_h_candles_manager is None and four_h_candles_manager is None:
            raise octobot_commons.errors.InvalidParametersError(f"Symbol {symbol} not found")
        symbol_candles[octobot_commons.enums.TimeFrames(TIME_FRAME)] = one_h_candles_manager
        if four_h_candles_manager:
            symbol_candles[octobot_commons.enums.TimeFrames(TIME_FRAME2)] = four_h_candles_manager
        return mock.Mock(symbol_candles=symbol_candles)
    return mock.Mock(
        id="exchange_manager_id",
        exchange_symbols_data=mock.Mock(
            get_exchange_symbol_data=mock.Mock(
                side_effect=_get_symbol_data
            )
        )
    )


@pytest.fixture
def candle_manager_by_time_frame_by_symbol(historical_prices, historical_volume):
    btc_1h_candles_manager, eth_1h_candles_manager, btc_4h_candles_manager = _get_candle_managers(
        historical_prices, historical_volume
    )
    return {
        TIME_FRAME: {
            SYMBOL: btc_1h_candles_manager,
            SYMBOL2: eth_1h_candles_manager,
        },
        TIME_FRAME2: {
            SYMBOL: btc_4h_candles_manager,
        },
    }


@pytest.fixture
def interpreter(exchange_manager_with_candles):
    return dsl_interpreter.Interpreter(
        dsl_interpreter.get_all_operators() + 
        exchange_operators.create_ohlcv_operators(exchange_manager_with_candles, SYMBOL, TIME_FRAME)
    )


@pytest.fixture
def interpreter_with_candle_manager_by_time_frame_by_symbol(candle_manager_by_time_frame_by_symbol):
    return dsl_interpreter.Interpreter(
        dsl_interpreter.get_all_operators() + 
        exchange_operators.create_ohlcv_operators(None, SYMBOL, TIME_FRAME, candle_manager_by_time_frame_by_symbol)
    )
