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
import os.path
import asyncio

import async_channel.util as channel_util
import octobot_backtesting.api as backtesting_api
import octobot_commons.asyncio_tools as asyncio_tools
import octobot_commons.constants as commons_constants
import octobot_commons.tests.test_config as test_config
import octobot_evaluators.api as evaluators_api
import octobot_trading.api as trading_api
import octobot_trading.exchange_channel as exchanges_channel
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges
import tentacles.Trading.Mode as Mode

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def _get_tools(symbol="BTC/USDT"):
    config = test_config.load_test_config()
    config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO]["USDT"] = 1000
    exchange_manager = exchanges.ExchangeManager(config, "binance")

    # use backtesting not to spam exchanges apis
    exchange_manager.is_simulated = True
    exchange_manager.is_backtesting = True
    backtesting = await backtesting_api.initialize_backtesting(
        config,
        exchange_ids=[exchange_manager.id],
        matrix_id=None,
        data_files=[
            os.path.join(test_config.TEST_CONFIG_FOLDER, "AbstractExchangeHistoryCollector_1586017993.616272.data")])
    exchange_manager.exchange = exchanges.ExchangeSimulator(exchange_manager.config,
                                                            exchange_manager,
                                                            backtesting)
    await exchange_manager.exchange.initialize()
    for exchange_channel_class_type in [exchanges_channel.ExchangeChannel, exchanges_channel.TimeFrameExchangeChannel]:
        await channel_util.create_all_subclasses_channel(exchange_channel_class_type, exchanges_channel.set_chan,
                                                         exchange_manager=exchange_manager)

    trader = exchanges.TraderSimulator(config, exchange_manager)
    await trader.initialize()

    mode = Mode.DailyTradingMode(config, exchange_manager)
    await mode.initialize()
    # add mode to exchange manager so that it can be stopped and freed from memory
    exchange_manager.trading_modes.append(mode)

    # set BTC/USDT price at 1000 USDT
    trading_api.force_set_mark_price(exchange_manager, symbol, 1000)

    return mode.producers[0], mode.consumers[0], trader


async def _stop(trader):
    for importer in backtesting_api.get_importers(trader.exchange_manager.exchange.backtesting):
        await backtesting_api.stop_importer(importer)
    await trader.exchange_manager.exchange.backtesting.stop()
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
        await producer._set_state(currency, symbol, trading_enums.EvaluatorStates.NEUTRAL)
        assert producer.state == trading_enums.EvaluatorStates.NEUTRAL
        # create as task to allow creator's queue to get processed
        await asyncio.create_task(_check_open_orders_count(trader, 0))

        producer.final_eval = -1
        await producer._set_state(currency, symbol, trading_enums.EvaluatorStates.VERY_LONG)
        assert producer.state == trading_enums.EvaluatorStates.VERY_LONG
        # create as task to allow creator's queue to get processed
        await asyncio.create_task(_check_open_orders_count(trader, 1))
        # market order got filled
        await asyncio.create_task(_check_open_orders_count(trader, 0))

        producer.final_eval = 0
        await producer._set_state(currency, symbol, trading_enums.EvaluatorStates.NEUTRAL)
        # create as task to allow creator's queue to get processed
        await asyncio.create_task(_check_open_orders_count(trader, 0))

        producer.final_eval = 1
        await producer._set_state(currency, symbol, trading_enums.EvaluatorStates.VERY_SHORT)
        assert producer.state == trading_enums.EvaluatorStates.VERY_SHORT
        # create as task to allow creator's queue to get processed
        await asyncio.create_task(_check_open_orders_count(trader, 1))
        # market order got filled
        await asyncio.create_task(_check_open_orders_count(trader, 0))

        producer.final_eval = 0
        await producer._set_state(currency, symbol, trading_enums.EvaluatorStates.NEUTRAL)
        assert producer.state == trading_enums.EvaluatorStates.NEUTRAL
        # create as task to allow creator's queue to get processed
        await asyncio.create_task(_check_open_orders_count(trader, 0))

        producer.final_eval = -0.5
        await producer._set_state(currency, symbol, trading_enums.EvaluatorStates.LONG)
        assert producer.state == trading_enums.EvaluatorStates.LONG
        # create as task to allow creator's queue to get processed
        await asyncio.create_task(_check_open_orders_count(trader, 1))

        producer.final_eval = 0
        await producer._set_state(currency, symbol, trading_enums.EvaluatorStates.NEUTRAL)
        assert producer.state == trading_enums.EvaluatorStates.NEUTRAL
        # create as task to allow creator's queue to get processed
        await asyncio.create_task(_check_open_orders_count(trader, 1))

        producer.final_eval = 0.5
        await producer._set_state(currency, symbol, trading_enums.EvaluatorStates.SHORT)
        assert producer.state == trading_enums.EvaluatorStates.SHORT
        # let both other be created
        await asyncio_tools.wait_asyncio_next_cycle()
        # create as task to allow creator's queue to get processed
        await asyncio.create_task(_check_open_orders_count(trader, 2))  # has stop loss
        # await task

        producer.final_eval = 0
        await producer._set_state(currency, symbol, trading_enums.EvaluatorStates.NEUTRAL)
        assert producer.state == trading_enums.EvaluatorStates.NEUTRAL
        # create as task to allow creator's queue to get processed
        await asyncio.create_task(_check_open_orders_count(trader, 2))

    finally:
        await _stop(trader)


async def test_get_delta_risk():
    try:
        producer, consumer, trader = await _get_tools()
        for i in range(0, 100, 1):
            trader.risk = i / 100
            assert round(producer._get_delta_risk(), 6) == round(producer.RISK_THRESHOLD * i / 100, 6)

    finally:
        await _stop(trader)


async def test_create_state():
    try:
        producer, consumer, trader = await _get_tools()
        delta_risk = producer._get_delta_risk()
        for i in range(-100, 100, 1):
            producer.final_eval = i / 100
            await producer.create_state(None, None)
            if producer.final_eval < producer.VERY_LONG_THRESHOLD + delta_risk:
                assert producer.state == trading_enums.EvaluatorStates.VERY_LONG
            elif producer.final_eval < producer.LONG_THRESHOLD + delta_risk:
                assert producer.state == trading_enums.EvaluatorStates.LONG
            elif producer.final_eval < producer.NEUTRAL_THRESHOLD - delta_risk:
                assert producer.state == trading_enums.EvaluatorStates.NEUTRAL
            elif producer.final_eval < producer.SHORT_THRESHOLD - delta_risk:
                assert producer.state == trading_enums.EvaluatorStates.SHORT
            else:
                assert producer.state == trading_enums.EvaluatorStates.VERY_SHORT
    finally:
        await _stop(trader)


async def test_set_final_eval():
    try:
        currency = "BTC"
        symbol = "BTC/USDT"
        time_frame = "1h"
        producer, consumer, trader = await _get_tools()
        matrix_id = evaluators_api.create_matrix()

        await producer._set_state(currency, symbol, trading_enums.EvaluatorStates.SHORT)
        assert producer.state == trading_enums.EvaluatorStates.SHORT
        # let both other be created
        await asyncio_tools.wait_asyncio_next_cycle()
        await asyncio.create_task(_check_open_orders_count(trader, 2))  # has stop loss
        producer.final_eval = "val"
        await producer.set_final_eval(matrix_id, currency, symbol, time_frame)
        assert producer.state == trading_enums.EvaluatorStates.SHORT  # ensure did not change trading_enums.EvaluatorStates
        assert producer.final_eval == "val"  # ensure did not change trading_enums.EvaluatorStates
        await asyncio.create_task(_check_open_orders_count(trader, 2))  # ensure did not change orders
    finally:
        await _stop(trader)


async def test_finalize():
    try:
        currency = "BTC"
        symbol = "BTC/USDT"
        producer, consumer, trader = await _get_tools()
        matrix_id = evaluators_api.create_matrix()

        await producer.finalize(trading_api.get_exchange_name(trader.exchange_manager), matrix_id, currency, symbol)
        assert producer.final_eval == commons_constants.INIT_EVAL_NOTE

        await producer._set_state(currency, symbol, trading_enums.EvaluatorStates.SHORT)
        assert producer.state == trading_enums.EvaluatorStates.SHORT
        # let both other be created
        await asyncio_tools.wait_asyncio_next_cycle()
        await asyncio.create_task(_check_open_orders_count(trader, 2))  # has stop loss

        await producer._set_state(currency, symbol, trading_enums.EvaluatorStates.SHORT)
        await asyncio.create_task(
            _check_open_orders_count(trader, 2))  # ensure did not change orders because neutral state

    finally:
        await _stop(trader)


async def _check_open_orders_count(trader, count):
    assert len(trading_api.get_open_orders(trader.exchange_manager)) == count
