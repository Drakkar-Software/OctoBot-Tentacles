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
import pytest

import numpy as np

import octobot_trading.api
import octobot_trading.constants
import octobot_commons.errors
import tentacles.Meta.DSL_operators.exchange_operators as exchange_operators


from tentacles.Meta.DSL_operators.exchange_operators.tests import (
    SYMBOL,
    TIME_FRAME,
    historical_prices,
    historical_volume,
    exchange_manager_with_candles,
    candle_manager_by_time_frame_by_symbol,
    interpreter_with_candle_manager_by_time_frame_by_symbol,
    interpreter,
)


@pytest.fixture
def expected_values(request, historical_prices, historical_volume):
    select_value = request.param
    if select_value == "price":
        return historical_prices
    elif select_value == "volume":
        return historical_volume
    raise octobot_commons.errors.InvalidParametersError(f"Invalid select_value: {select_value}")


@pytest.fixture
def operator(request):
    return request.param


@pytest.mark.asyncio
@pytest.mark.parametrize("operator, expected_values", [
    ("close", "price"), 
    ("volume", "volume")
], indirect=True) # use indirect=True to pass fixtures as a parameter
async def test_ohlcv_operators_basic_calls(
    interpreter, interpreter_with_candle_manager_by_time_frame_by_symbol,
    operator, expected_values
):
    # test with both interpreter data sources
    for _interpreter in [interpreter, interpreter_with_candle_manager_by_time_frame_by_symbol]:
        # no param, use context values: SYMBOL, TIME_FRAME: BTC/USDT, 1h
        operator_value = await _interpreter.interprete(operator)
        assert np.array_equal(operator_value, expected_values)
        # ensure symbol parameters are used when provided
        assert np.array_equal(await _interpreter.interprete(f"{operator}('ETH/USDT')"), expected_values / 2) # 1h ETH
        assert np.array_equal(await _interpreter.interprete(f"{operator}('BTC/USDT')"), expected_values) # 1h BTC

        # ensure time frame is used when provided
        assert np.array_equal(await _interpreter.interprete(f"{operator}(None, '4h')"), expected_values * 2) # 4h BTC
        assert np.array_equal(await _interpreter.interprete(f"{operator}(None, '1h')"), expected_values) # 1h BTC

        # ensure symbol and time frame are used when provided
        assert np.array_equal(await _interpreter.interprete(f"{operator}('BTC/USDT', '1h')"), expected_values) # 4h BTC rsi value
        assert np.array_equal(await _interpreter.interprete(f"{operator}('BTC/USDT', '4h')"), expected_values * 2) # 4h BTC rsi value
        assert np.array_equal(await _interpreter.interprete(f"{operator}('ETH/USDT', '1h')"), expected_values / 2) # 1h ETH rsi value
        with pytest.raises(KeyError): # no 4h ETH candles
            await _interpreter.interprete(f"{operator}('ETH/USDT', '4h')")


@pytest.mark.asyncio
@pytest.mark.parametrize("operator", [
    ("close"), 
    ("volume")
])
async def test_ohlcv_operators_dependencies(interpreter, operator, exchange_manager_with_candles):
    interpreter.prepare(f"{operator}")
    assert interpreter.get_dependencies() == [
        exchange_operators.ExchangeDataDependency(
            exchange_manager_id=octobot_trading.api.get_exchange_manager_id(exchange_manager_with_candles),
            symbol=SYMBOL,
            time_frame=TIME_FRAME,
            data_source=octobot_trading.constants.OHLCV_CHANNEL
        )
    ]

    # same dependency for all operators
    interpreter.prepare(f"{operator} + close + volume")
    assert interpreter.get_dependencies() == [
        exchange_operators.ExchangeDataDependency(
            exchange_manager_id=octobot_trading.api.get_exchange_manager_id(exchange_manager_with_candles),
            symbol=SYMBOL,
            time_frame=TIME_FRAME,
            data_source=octobot_trading.constants.OHLCV_CHANNEL
        )
    ]

    # SYMBOL + ETH/USDT dependency
    # => dynamic dependencies are not yet supported. Update this test when supported.
    interpreter.prepare(f"{operator} + close('ETH/USDT') + volume")
    assert interpreter.get_dependencies() == [
        exchange_operators.ExchangeDataDependency(
            exchange_manager_id=octobot_trading.api.get_exchange_manager_id(exchange_manager_with_candles),
            symbol=SYMBOL,
            time_frame=TIME_FRAME,
            data_source=octobot_trading.constants.OHLCV_CHANNEL
        ),
        # not identified as a dependency
        # exchange_operators.ExchangeDataDependency(
        #     exchange_manager_id=octobot_trading.api.get_exchange_manager_id(exchange_manager_with_candles),
        #     symbol="ETH/USDT",
        #     time_frame=TIME_FRAME,
        #     data_source=octobot_trading.constants.OHLCV_CHANNEL
        # ),
    ]
