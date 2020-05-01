#  Drakkar-Software OctoBot-Tentacles
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
from os.path import join
from asyncio import create_task

from octobot_channels.util.channel_creator import create_all_subclasses_channel
from octobot_commons.constants import INIT_EVAL_NOTE
from octobot_commons.tests.test_config import load_test_config, TEST_CONFIG_FOLDER
from octobot_evaluators.api.evaluators import create_matrix
from octobot_trading.api.exchange import get_exchange_name
from octobot_trading.api.orders import get_open_orders
from octobot_trading.api.symbol_data import force_set_mark_price
from octobot_trading.channels.exchange_channel import ExchangeChannel, TimeFrameExchangeChannel, set_chan
from octobot_trading.constants import CONFIG_SIMULATOR, CONFIG_STARTING_PORTFOLIO
from octobot_trading.enums import EvaluatorStates
from octobot_trading.exchanges.exchange_manager import ExchangeManager
from octobot_trading.exchanges.exchange_simulator import ExchangeSimulator
from octobot_trading.exchanges.rest_exchange import RestExchange
from octobot_trading.traders.trader_simulator import TraderSimulator
from tentacles.Trading.Mode import DailyTradingMode

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def _get_tools(symbol="BTC/USDT"):
    config = load_test_config()
    config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO]["USDT"] = 1000
    exchange_manager = ExchangeManager(config, "binance")

    # use backtesting not to spam exchanges apis
    exchange_manager.is_simulated = True
    exchange_manager.is_backtesting = True
    exchange_manager.backtesting_files = [join(TEST_CONFIG_FOLDER,
                                               "AbstractExchangeHistoryCollector_1586017993.616272.data")]
    exchange_manager.exchange_type = RestExchange.create_exchange_type(exchange_manager.exchange_class_string)
    exchange_manager.exchange = ExchangeSimulator(exchange_manager.config,
                                                  exchange_manager.exchange_type,
                                                  exchange_manager,
                                                  exchange_manager.backtesting_files)
    await exchange_manager.exchange.initialize()
    for exchange_channel_class_type in [ExchangeChannel, TimeFrameExchangeChannel]:
        await create_all_subclasses_channel(exchange_channel_class_type, set_chan, exchange_manager=exchange_manager)

    trader = TraderSimulator(config, exchange_manager)
    await trader.initialize()

    mode = DailyTradingMode(config, exchange_manager)
    await mode.initialize()

    # set BTC/USDT price at 1000 USDT
    force_set_mark_price(exchange_manager, symbol, 1000)

    return mode.producers[0], mode.consumers[0], trader


async def _stop(trader):
    await trader.exchange_manager.stop()


async def test_default_values():
    try:
        producer, _, trader = await _get_tools()
        assert producer.state is None
    finally:
        await _stop(trader)


async def test_set_state():
    try:
        currency = "BTC"
        symbol = "BTC/USDT"
        time_frame = "1h"
        producer, consumer, trader = await _get_tools(symbol)

        producer.final_eval = 0
        await producer._set_state(currency, symbol, EvaluatorStates.NEUTRAL)
        assert producer.state == EvaluatorStates.NEUTRAL
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 0))

        producer.final_eval = -1
        await producer._set_state(currency, symbol, EvaluatorStates.VERY_LONG)
        assert producer.state == EvaluatorStates.VERY_LONG
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 1))

        producer.final_eval = 0
        await producer._set_state(currency, symbol, EvaluatorStates.NEUTRAL)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 1))

        producer.final_eval = 1
        await producer._set_state(currency, symbol, EvaluatorStates.VERY_SHORT)
        assert producer.state == EvaluatorStates.VERY_SHORT
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 1))

        producer.final_eval = 0
        await producer._set_state(currency, symbol, EvaluatorStates.NEUTRAL)
        assert producer.state == EvaluatorStates.NEUTRAL
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 1))

        producer.final_eval = -0.5
        await producer._set_state(currency, symbol, EvaluatorStates.LONG)
        assert producer.state == EvaluatorStates.LONG
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 1))

        producer.final_eval = 0
        await producer._set_state(currency, symbol, EvaluatorStates.NEUTRAL)
        assert producer.state == EvaluatorStates.NEUTRAL
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 1))

        producer.final_eval = 0.5
        await producer._set_state(currency, symbol, EvaluatorStates.SHORT)
        assert producer.state == EvaluatorStates.SHORT
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 2))  # has stop loss
        # await task

        producer.final_eval = 0
        await producer._set_state(currency, symbol, EvaluatorStates.NEUTRAL)
        assert producer.state == EvaluatorStates.NEUTRAL
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 2))

    finally:
        await _stop(trader)


async def test_get_delta_risk():
    try:
        producer, consumer, trader = await _get_tools()
        for i in range(0, 100, 1):
            trader.risk = i/100
            assert round(producer._get_delta_risk(), 6) == round(producer.RISK_THRESHOLD * i/100, 6)

    finally:
        await _stop(trader)


async def test_create_state():
    try:
        producer, consumer, trader = await _get_tools()
        delta_risk = producer._get_delta_risk()
        for i in range(-100, 100, 1):
            producer.final_eval = i/100
            await producer.create_state(None, None)
            if producer.final_eval < producer.VERY_LONG_THRESHOLD + delta_risk:
                assert producer.state == EvaluatorStates.VERY_LONG
            elif producer.final_eval < producer.LONG_THRESHOLD + delta_risk:
                assert producer.state == EvaluatorStates.LONG
            elif producer.final_eval < producer.NEUTRAL_THRESHOLD - delta_risk:
                assert producer.state == EvaluatorStates.NEUTRAL
            elif producer.final_eval < producer.SHORT_THRESHOLD - delta_risk:
                assert producer.state == EvaluatorStates.SHORT
            else:
                assert producer.state == EvaluatorStates.VERY_SHORT
    finally:
        await _stop(trader)


async def test_set_final_eval():
    try:
        currency = "BTC"
        symbol = "BTC/USDT"
        time_frame = "1h"
        producer, consumer, trader = await _get_tools()
        matrix_id = create_matrix()

        await producer._set_state(currency, symbol, EvaluatorStates.SHORT)
        assert producer.state == EvaluatorStates.SHORT
        await create_task(_check_open_orders_count(trader, 2))  # has stop loss
        producer.final_eval = "val"
        await producer.set_final_eval(matrix_id, currency, symbol, time_frame)
        assert producer.state == EvaluatorStates.SHORT  # ensure did not change EvaluatorStates
        assert producer.final_eval == "val"  # ensure did not change EvaluatorStates
        await create_task(_check_open_orders_count(trader, 2))  # ensure did not change orders
    finally:
        await _stop(trader)


async def test_finalize():
    try:
        currency = "BTC"
        symbol = "BTC/USDT"
        producer, consumer, trader = await _get_tools()
        matrix_id = create_matrix()

        await producer.finalize(get_exchange_name(trader.exchange_manager), matrix_id, currency, symbol)
        assert producer.final_eval == INIT_EVAL_NOTE

        await producer._set_state(currency, symbol, EvaluatorStates.SHORT)
        assert producer.state == EvaluatorStates.SHORT
        await create_task(_check_open_orders_count(trader, 2))  # has stop loss

        await producer._set_state(currency, symbol, EvaluatorStates.SHORT)
        await create_task(_check_open_orders_count(trader, 2))  # ensure did not change orders because neutral state

    finally:
        await _stop(trader)


async def _check_open_orders_count(trader, count):
    assert len(get_open_orders(trader.exchange_manager)) == count
