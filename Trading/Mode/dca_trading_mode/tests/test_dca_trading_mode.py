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
import pytest_asyncio
import os.path
import asyncio
import mock
import decimal

import async_channel.util as channel_util
import octobot_commons.asyncio_tools as asyncio_tools
import octobot_commons.enums as commons_enum
import octobot_commons.tests.test_config as test_config
import octobot_backtesting.api as backtesting_api
import octobot_tentacles_manager.api as tentacles_manager_api
import octobot_trading.api as trading_api
import octobot_trading.exchange_channel as exchanges_channel
import octobot_trading.exchanges as exchanges
import octobot_trading.personal_data as trading_personal_data
import octobot_trading.enums as trading_enums
import octobot_trading.constants as trading_constants
import octobot_trading.modes.script_keywords as script_keywords
import octobot_commons.constants as commons_constants
import tentacles.Evaluator.TA as TA
import tentacles.Evaluator.Strategies as Strategies
import tentacles.Trading.Mode as Mode
import tests.test_utils.memory_check_util as memory_check_util
import tests.test_utils.config as test_utils_config
import tests.test_utils.test_exchanges as test_exchanges

import tentacles.Trading.Mode.dca_trading_mode.dca_trading as dca_trading

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def tools():
    trader = None
    try:
        tentacles_manager_api.reload_tentacle_info()
        mode, trader = await _get_tools()
        yield mode, trader
    finally:
        if trader:
            await _stop(trader.exchange_manager)


async def _test_run_independent_backtestings_with_memory_check():
    """
    Should always be called first here to avoid other tests' related memory check issues
    """
    tentacles_setup_config = tentacles_manager_api.create_tentacles_setup_config_with_tentacles(
        Mode.DipAnalyserTradingMode,
        Strategies.DipAnalyserStrategyEvaluator,
        TA.KlingerOscillatorReversalConfirmationMomentumEvaluator,
        TA.RSIWeightMomentumEvaluator
    )
    config = test_config.load_test_config()
    config[commons_constants.CONFIG_TIME_FRAME] = [commons_enum.TimeFrames.FOUR_HOURS]
    await memory_check_util.run_independent_backtestings_with_memory_check(config, tentacles_setup_config)


def _get_config(tools, update):
    mode, trader = tools
    config = tentacles_manager_api.get_tentacle_config(trader.exchange_manager.tentacles_setup_config, mode.__class__)
    return {**config, **update}


async def test_init_default_values(tools):
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, {}))
    assert mode.use_market_entry_orders is True
    assert mode.trigger_mode is dca_trading.TriggerMode.TIME_BASED
    assert mode.minutes_before_next_buy == 10080

    assert mode.entry_limit_orders_price_multiplier == decimal.Decimal("0.05")
    assert mode.use_secondary_entry_orders is False
    assert mode.secondary_entry_orders_count == 0
    assert mode.secondary_entry_orders_amount == ""
    assert mode.secondary_entry_orders_price_multiplier == decimal.Decimal("0.05")

    assert mode.use_take_profit_exit_orders is False
    assert mode.exit_limit_orders_price_multiplier == decimal.Decimal("0.05")
    assert mode.use_secondary_exit_orders is False
    assert mode.secondary_exit_orders_count == 0
    assert mode.secondary_exit_orders_price_multiplier == decimal.Decimal("0.05")

    assert mode.use_stop_loss is False
    assert mode.stop_loss_price_multiplier == decimal.Decimal("0.1")


async def test_init_config_values(tools):
    update = {
        "buy_order_amount": "50q",
        "entry_limit_orders_price_percent": 3,
        "exit_limit_orders_price_percent": 1,
        "minutes_before_next_buy": 333,
        "secondary_entry_orders_amount": "12%",
        "secondary_entry_orders_count": 0,
        "secondary_entry_orders_price_percent": 5,
        "secondary_exit_orders_count": 333,
        "secondary_exit_orders_price_percent": 2,
        "stop_loss_price_percent": 10,
        "trigger_mode": "Maximum evaluators signals based",
        "use_market_entry_orders": False,
        "use_secondary_entry_orders": True,
        "use_secondary_exit_orders": True,
        "use_stop_losses": True,
        "use_take_profit_exit_orders": True
    }
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    assert mode.use_market_entry_orders is False
    assert mode.trigger_mode is dca_trading.TriggerMode.MAXIMUM_EVALUATORS_SIGNALS_BASED
    assert mode.minutes_before_next_buy == 333

    assert mode.entry_limit_orders_price_multiplier == decimal.Decimal("0.03")
    assert mode.use_secondary_entry_orders is True
    assert mode.secondary_entry_orders_count == 0
    assert mode.secondary_entry_orders_amount == "12%"
    assert mode.secondary_entry_orders_price_multiplier == decimal.Decimal("0.05")

    assert mode.use_take_profit_exit_orders is True
    assert mode.exit_limit_orders_price_multiplier == decimal.Decimal("0.01")
    assert mode.use_secondary_exit_orders is True
    assert mode.secondary_exit_orders_count == 333
    assert mode.secondary_exit_orders_price_multiplier == decimal.Decimal("0.02")

    assert mode.use_stop_loss is True
    assert mode.stop_loss_price_multiplier == decimal.Decimal("0.1")


async def test_trigger_dca_for_symbol(tools):
    update = {
        "buy_order_amount": "50q",
        "entry_limit_orders_price_percent": 3,
        "exit_limit_orders_price_percent": 1,
        "minutes_before_next_buy": 333,
        "secondary_entry_orders_amount": "12%",
        "secondary_entry_orders_count": 0,
        "secondary_entry_orders_price_percent": 5,
        "secondary_exit_orders_count": 333,
        "secondary_exit_orders_price_percent": 2,
        "stop_loss_price_percent": 10,
        "trigger_mode": "Maximum evaluators signals based",
        "use_market_entry_orders": False,
        "use_secondary_entry_orders": True,
        "use_secondary_exit_orders": True,
        "use_stop_losses": True,
        "use_take_profit_exit_orders": True
    }
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))


async def _check_open_orders_count(trader, count):
    assert len(trading_api.get_open_orders(trader.exchange_manager)) == count


async def _get_tools(symbol="BTC/USDT"):
    config = test_config.load_test_config()
    config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO]["USDT"] = 2000
    exchange_manager = test_exchanges.get_test_exchange_manager(config, "binance")
    exchange_manager.tentacles_setup_config = test_utils_config.get_tentacles_setup_config()

    # use backtesting not to spam exchanges apis
    exchange_manager.is_simulated = True
    exchange_manager.is_backtesting = True
    backtesting = await backtesting_api.initialize_backtesting(
        config,
        exchange_ids=[exchange_manager.id],
        matrix_id=None,
        data_files=[os.path.join(test_config.TEST_CONFIG_FOLDER,
                                 "AbstractExchangeHistoryCollector_1586017993.616272.data")])
    exchange_manager.exchange = exchanges.ExchangeSimulator(
        exchange_manager.config, exchange_manager, backtesting
    )
    await exchange_manager.exchange.initialize()
    for exchange_channel_class_type in [exchanges_channel.ExchangeChannel, exchanges_channel.TimeFrameExchangeChannel]:
        await channel_util.create_all_subclasses_channel(exchange_channel_class_type, exchanges_channel.set_chan,
                                                         exchange_manager=exchange_manager)

    trader = exchanges.TraderSimulator(config, exchange_manager)
    await trader.initialize()

    mode = Mode.DCATradingMode(config, exchange_manager)
    mode.symbol = None if mode.get_is_symbol_wildcard() else symbol
    # trading mode is not initialized: to be initialized with the required config in tests

    # add mode to exchange manager so that it can be stopped and freed from memory
    exchange_manager.trading_modes.append(mode)

    # set BTC/USDT price at 1000 USDT
    trading_api.force_set_mark_price(exchange_manager, symbol, 1000)

    return mode, trader


async def _init_mode(tools, config):
    mode, trader = tools
    await mode.initialize(trading_config=config)
    return mode, mode.producers[0], mode.get_trading_mode_consumers()[0], trader


async def _fill_order(order, trader, trigger_update_callback=True, ignore_open_orders=False, consumer=None,
                      closed_orders_count=1):
    initial_len = len(trading_api.get_open_orders(trader.exchange_manager))
    await order.on_fill(force_fill=True)
    if order.status == trading_enums.OrderStatus.FILLED:
        if not ignore_open_orders:
            assert len(trading_api.get_open_orders(trader.exchange_manager)) == initial_len - closed_orders_count
        if trigger_update_callback:
            await asyncio_tools.wait_asyncio_next_cycle()
        else:
            with mock.patch.object(consumer, "create_new_orders", new=mock.AsyncMock()):
                await asyncio_tools.wait_asyncio_next_cycle()


async def _stop(exchange_manager):
    for importer in backtesting_api.get_importers(exchange_manager.exchange.backtesting):
        await backtesting_api.stop_importer(importer)
    await exchange_manager.exchange.backtesting.stop()
    await exchange_manager.stop()
