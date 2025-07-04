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
import copy
import os.path
import asyncio
import mock
import decimal
import contextlib

import async_channel.util as channel_util

import octobot_tentacles_manager.api as tentacles_manager_api

import octobot_backtesting.api as backtesting_api

import octobot_commons.asyncio_tools as asyncio_tools
import octobot_commons.constants as commons_constants
import octobot_commons.tests.test_config as test_config

import octobot_trading.api as trading_api
import octobot_trading.exchange_channel as exchanges_channel
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges
import octobot_trading.personal_data as trading_personal_data
import octobot_trading.constants as trading_constants
import octobot_trading.modes

import tentacles.Trading.Mode.staggered_orders_trading_mode.staggered_orders_trading as staggered_orders_trading

import tests.test_utils.config as test_utils_config
import tests.test_utils.memory_check_util as memory_check_util
import tests.test_utils.test_exchanges as test_exchanges
import tests.test_utils.trading_modes as test_trading_modes

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def _init_trading_mode(config, exchange_manager, symbol):
    staggered_orders_trading.StaggeredOrdersTradingModeProducer.SCHEDULE_ORDERS_CREATION_ON_START = False
    mode = staggered_orders_trading.StaggeredOrdersTradingMode(config, exchange_manager)
    mode.symbol = None if mode.get_is_symbol_wildcard() else symbol
    mode.trading_config = _get_multi_symbol_staggered_config()
    await mode.initialize()
    # add mode to exchange manager so that it can be stopped and freed from memory
    exchange_manager.trading_modes.append(mode)
    mode.producers[0].PRICE_FETCHING_TIMEOUT = 0.5
    mode.producers[0].allow_order_funds_redispatch = True
    test_trading_modes.set_ready_to_start(mode.producers[0])
    return mode, mode.producers[0]


@contextlib.asynccontextmanager
async def _get_tools(symbol, btc_holdings=None, additional_portfolio={}, fees=None):
    tentacles_manager_api.reload_tentacle_info()
    exchange_manager = None
    try:
        config = test_config.load_test_config()
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO]["USD"] = 1000
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO][
            "BTC"] = 10 if btc_holdings is None else btc_holdings
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO].update(additional_portfolio)
        if fees is not None:
            config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_SIMULATOR_FEES][
                commons_constants.CONFIG_SIMULATOR_FEES_TAKER] = fees
            config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_SIMULATOR_FEES][
                commons_constants.CONFIG_SIMULATOR_FEES_MAKER] = fees
        exchange_manager = test_exchanges.get_test_exchange_manager(config, "binance")
        exchange_manager.tentacles_setup_config = test_utils_config.load_test_tentacles_config()

        # use backtesting not to spam exchanges apis
        exchange_manager.is_simulated = True
        exchange_manager.is_backtesting = True
        exchange_manager.use_cached_markets = False
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

        # set BTC/USDT price at 1000 USDT
        if symbol not in exchange_manager.client_symbols:
            exchange_manager.client_symbols.append(symbol)
        trading_api.force_set_mark_price(exchange_manager, symbol, 1000)

        mode, producer = await _init_trading_mode(config, exchange_manager, symbol)

        producer.lowest_buy = decimal.Decimal(1)
        producer.highest_sell = decimal.Decimal(10000)
        producer.operational_depth = 50
        producer.spread = decimal.Decimal("0.06")
        producer.increment = decimal.Decimal("0.04")
        producer.mode = staggered_orders_trading.StrategyModes.MOUNTAIN

        yield producer, mode.get_trading_mode_consumers()[0], exchange_manager
    finally:
        if exchange_manager:
            await _stop(exchange_manager)


@contextlib.asynccontextmanager
async def _get_tools_multi_symbol():
    exchange_manager = None
    try:
        config = test_config.load_test_config()
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO]["USD"] = 1000
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO]["USDT"] = 2000
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO]["BTC"] = 10
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO]["ETH"] = 20
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO]["NANO"] = 2000
        exchange_manager = test_exchanges.get_test_exchange_manager(config, "binance")
        exchange_manager.tentacles_setup_config = test_utils_config.get_tentacles_setup_config()

        # use backtesting not to spam exchanges apis
        exchange_manager.is_simulated = True
        exchange_manager.is_backtesting = True
        exchange_manager.use_cached_markets = False
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

        btc_usd_mode, btcusd_producer = await _init_trading_mode(config, exchange_manager, "BTC/USD")
        eth_usdt_mode, eth_usdt_producer = await _init_trading_mode(config, exchange_manager, "ETH/USDT")
        nano_usdt_mode, nano_usdt_producer = await _init_trading_mode(config, exchange_manager, "NANO/USDT")

        btcusd_producer.lowest_buy = decimal.Decimal(1)
        btcusd_producer.highest_sell = decimal.Decimal(10000)
        btcusd_producer.operational_depth = 50
        btcusd_producer.spread = decimal.Decimal("0.06")
        btcusd_producer.increment = decimal.Decimal("0.04")
        btcusd_producer.mode = staggered_orders_trading.StrategyModes.MOUNTAIN

        eth_usdt_producer.lowest_buy = decimal.Decimal(20)
        eth_usdt_producer.highest_sell = decimal.Decimal(5000)
        eth_usdt_producer.operational_depth = 30
        eth_usdt_producer.spread = decimal.Decimal("0.07")
        eth_usdt_producer.increment = decimal.Decimal("0.03")
        eth_usdt_producer.mode = staggered_orders_trading.StrategyModes.MOUNTAIN

        nano_usdt_producer.lowest_buy = decimal.Decimal(20)
        nano_usdt_producer.highest_sell = decimal.Decimal(5000)
        nano_usdt_producer.operational_depth = 30
        nano_usdt_producer.spread = decimal.Decimal("0.07")
        nano_usdt_producer.increment = decimal.Decimal("0.03")
        nano_usdt_producer.mode = staggered_orders_trading.StrategyModes.MOUNTAIN

        yield btcusd_producer, eth_usdt_producer, nano_usdt_producer, exchange_manager
    finally:
        if exchange_manager:
            await _stop(exchange_manager)


async def _stop(exchange_manager):
    for importer in backtesting_api.get_importers(exchange_manager.exchange.backtesting):
        await backtesting_api.stop_importer(importer)
    await exchange_manager.exchange.backtesting.stop()
    await exchange_manager.stop()


async def test_run_independent_backtestings_with_memory_check():
    """
    Should always be called first here to avoid other tests' related memory check issues
    """
    staggered_orders_trading.StaggeredOrdersTradingModeProducer.SCHEDULE_ORDERS_CREATION_ON_START = True
    tentacles_setup_config = tentacles_manager_api.create_tentacles_setup_config_with_tentacles(
        staggered_orders_trading.StaggeredOrdersTradingMode
    )
    await memory_check_util.run_independent_backtestings_with_memory_check(test_config.load_test_config(),
                                                                           tentacles_setup_config)


async def test_ensure_staggered_orders():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, _, exchange_manager = tools
        assert producer.state == trading_enums.EvaluatorStates.NEUTRAL
        assert producer.current_price is None
        # create as task to allow creator's queue to get processed
        await asyncio.create_task(_check_open_orders_count(exchange_manager, 0))

        # set BTC/USD price at 4000 USD
        trading_api.force_set_mark_price(exchange_manager, symbol, 4000)
        with mock.patch.object(producer, "_ensure_current_price_in_limit_parameters", mock.Mock()) \
                as _ensure_current_price_in_limit_parameters_mock:
            await producer._ensure_staggered_orders()
            _ensure_current_price_in_limit_parameters_mock.assert_called_once()
        # price info: create trades
        assert producer.current_price == 4000
        assert producer.state == trading_enums.EvaluatorStates.NEUTRAL
        await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))


async def test_multi_symbol():
    async with _get_tools_multi_symbol() as tools:
        btcusd_producer, eth_usdt_producer, nano_usdt_producer, exchange_manager = tools
        trading_api.force_set_mark_price(exchange_manager, btcusd_producer.symbol, 100)
        await btcusd_producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, btcusd_producer.operational_depth))
        orders = trading_api.get_open_orders(exchange_manager)
        assert len(orders) == btcusd_producer.operational_depth
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.SELL]) == 25
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.BUY]) == 25

        trading_api.force_set_mark_price(exchange_manager, eth_usdt_producer.symbol, 200)
        await eth_usdt_producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, btcusd_producer.operational_depth +
                                                           eth_usdt_producer.operational_depth))
        orders = trading_api.get_open_orders(exchange_manager)
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.SELL]) == 40
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.BUY]) == 40

        trading_api.force_set_mark_price(exchange_manager, nano_usdt_producer.symbol, 200)
        await nano_usdt_producer._ensure_staggered_orders()
        # no new order
        await asyncio.create_task(_check_open_orders_count(exchange_manager, btcusd_producer.operational_depth +
                                                           eth_usdt_producer.operational_depth))
        orders = trading_api.get_open_orders(exchange_manager)
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.SELL]) == 40
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.BUY]) == 40

        assert nano_usdt_producer._get_interfering_orders_pairs(orders) == {"ETH/USDT"}

        # new ETH USDT evaluation, price changed
        # -2 order would be filled
        original_orders = copy.copy(orders)
        to_fill_order = original_orders[-2]
        await _fill_order(to_fill_order, exchange_manager, producer=eth_usdt_producer)
        # filled order and created a new one
        await asyncio.create_task(_check_open_orders_count(exchange_manager, len(original_orders)))
        trading_api.force_set_mark_price(exchange_manager, eth_usdt_producer.symbol, 190)
        await nano_usdt_producer._ensure_staggered_orders()
        # did nothing
        await asyncio.create_task(_check_open_orders_count(exchange_manager, len(original_orders)))
    assert staggered_orders_trading.StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS == {}


async def test_available_funds_management():
    async with _get_tools_multi_symbol() as tools:
        btcusd_producer, eth_usdt_producer, nano_usdt_producer, exchange_manager = tools
        assert staggered_orders_trading.StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS == {}

        trading_api.force_set_mark_price(exchange_manager, btcusd_producer.symbol, 100)
        await btcusd_producer._ensure_staggered_orders()
        available_funds = \
            staggered_orders_trading.StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS[exchange_manager.id]
        assert len(available_funds) == 2
        btc_available_funds = available_funds["BTC"]
        usd_available_funds = available_funds["USD"]
        assert btc_available_funds < decimal.Decimal("9.9")
        assert usd_available_funds < decimal.Decimal("31")
        await asyncio.create_task(_check_open_orders_count(exchange_manager, btcusd_producer.operational_depth))
        orders = trading_api.get_open_orders(exchange_manager)
        pf_btc_available_funds = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        # ensure there at least the same (or more) actual portfolio available funds than on the producer value
        # (due to exchange rounding reducing some amounts)
        assert pf_btc_available_funds * decimal.Decimal("0.999") <= btc_available_funds <= pf_btc_available_funds
        pf_usd_available_funds = trading_api.get_portfolio_currency(exchange_manager, "USD").available
        assert pf_usd_available_funds * decimal.Decimal("0.999") <= usd_available_funds <= pf_usd_available_funds
        assert len(orders) == btcusd_producer.operational_depth
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.SELL]) == 25
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.BUY]) == 25

        trading_api.force_set_mark_price(exchange_manager, eth_usdt_producer.symbol, 200)
        await eth_usdt_producer._ensure_staggered_orders()
        assert len(available_funds) == 4
        # did not change previous funds
        assert btc_available_funds == available_funds["BTC"]
        assert usd_available_funds == available_funds["USD"]
        eth_available_funds = available_funds["ETH"]
        usdt_available_funds = available_funds["USDT"]
        assert eth_available_funds < decimal.Decimal("19.6")
        assert usdt_available_funds < decimal.Decimal("753")
        await asyncio.create_task(_check_open_orders_count(exchange_manager, btcusd_producer.operational_depth +
                                                           eth_usdt_producer.operational_depth))
        orders = trading_api.get_open_orders(exchange_manager)
        pf_eth_available_funds = trading_api.get_portfolio_currency(exchange_manager, "ETH").available
        assert pf_eth_available_funds * decimal.Decimal("0.999") <= eth_available_funds <= pf_eth_available_funds
        pf_usdt_available_funds = trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        assert pf_usdt_available_funds * decimal.Decimal("0.999") <= usdt_available_funds <= pf_usdt_available_funds
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.SELL]) == 40
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.BUY]) == 40

        trading_api.force_set_mark_price(exchange_manager, nano_usdt_producer.symbol, 200)
        await nano_usdt_producer._ensure_staggered_orders()
        # did not change available funds
        assert len(available_funds) == 4
        assert btc_available_funds == available_funds["BTC"]
        assert usd_available_funds == available_funds["USD"]
        assert eth_available_funds == available_funds["ETH"]
        assert usdt_available_funds == available_funds["USDT"]
        # no new order
        await asyncio.create_task(_check_open_orders_count(exchange_manager, btcusd_producer.operational_depth +
                                                           eth_usdt_producer.operational_depth))
        orders = trading_api.get_open_orders(exchange_manager)
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.SELL]) == 40
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.BUY]) == 40

        assert nano_usdt_producer._get_interfering_orders_pairs(orders) == {"ETH/USDT"}

        # new ETH USDT evaluation, price changed
        # -2 order would be filled
        original_orders = copy.copy(orders)
        to_fill_order = original_orders[-2]
        await _fill_order(to_fill_order, exchange_manager, producer=eth_usdt_producer)
        trading_api.force_set_mark_price(exchange_manager, eth_usdt_producer.symbol, 190)
        await nano_usdt_producer._ensure_staggered_orders()
        # did nothing
        # did not change available funds
        assert len(available_funds) == 4
        assert btc_available_funds == available_funds["BTC"]
        assert usd_available_funds == available_funds["USD"]
        assert eth_available_funds == available_funds["ETH"]
        assert usdt_available_funds == available_funds["USDT"]
        await asyncio.create_task(_check_open_orders_count(exchange_manager, len(original_orders)))
    # clear available funds
    assert staggered_orders_trading.StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS == {}


async def test_ensure_staggered_orders_with_target_sell_and_buy_funds():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, _, exchange_manager = tools

        producer.sell_funds = decimal.Decimal("0.001")
        producer.buy_funds = decimal.Decimal(100)

        # set BTC/USD price at 4000 USD
        trading_api.force_set_mark_price(exchange_manager, symbol, 4000)
        await producer._ensure_staggered_orders()
        btc_available_funds = producer._get_available_funds("BTC")
        usd_available_funds = producer._get_available_funds("USD")
        # btc_available_funds for reduced because orders are not created
        assert 10 - 0.001 <= btc_available_funds < 10
        assert 1000 - 100 <= usd_available_funds < 1000
        # price info: create trades
        assert producer.current_price == 4000
        assert producer.state == trading_enums.EvaluatorStates.NEUTRAL
        await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
        pf_btc_available_funds = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        pf_usd_available_funds = trading_api.get_portfolio_currency(exchange_manager, "USD").available
        assert pf_btc_available_funds >= 9.999
        assert pf_usd_available_funds >= 900

        assert pf_btc_available_funds >= btc_available_funds
        assert pf_usd_available_funds >= usd_available_funds


async def test_ensure_staggered_orders_with_unavailable_funds():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, _, exchange_manager = tools

        producer._set_initially_available_funds("BTC", decimal.Decimal(1))
        producer._set_initially_available_funds("USD", decimal.Decimal(400))

        # set BTC/USD price at 4000 USD
        trading_api.force_set_mark_price(exchange_manager, symbol, 4000)
        await producer._ensure_staggered_orders()
        btc_available_funds = producer._get_available_funds("BTC")
        usd_available_funds = producer._get_available_funds("USD")
        # btc_available_funds for reduced because orders are not created
        assert btc_available_funds < 1
        assert usd_available_funds < 400
        # price info: create trades
        assert producer.current_price == 4000
        assert producer.state == trading_enums.EvaluatorStates.NEUTRAL
        await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
        pf_btc_available_funds = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        pf_usd_available_funds = trading_api.get_portfolio_currency(exchange_manager, "USD").available
        assert pf_btc_available_funds >= 9
        assert pf_usd_available_funds >= 600

        # - 9 to make it as if itr was starting with 1 btc (to compare with btc_available_funds)
        assert pf_btc_available_funds - 9 >= btc_available_funds
        # - 600 to make it as if itr was starting with 1 btc (to compare with btc_available_funds)
        assert pf_usd_available_funds - 600 >= usd_available_funds


async def test_get_maximum_traded_funds():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, _, exchange_manager = tools

        # part 1: no available funds set
        # no allowed_funds set
        # can trade total_available_funds
        assert producer._get_maximum_traded_funds(0, 10, "BTC", True, False) == 10 == decimal.Decimal(10)
        # allowed_funds set
        # can trade allowed_funds
        assert producer._get_maximum_traded_funds(5, 10, "BTC", False, False) == 5
        # allowed_funds set, allowed_funds larger than total_available_funds
        # can trade total_available_funds
        assert producer._get_maximum_traded_funds(15, 10, "BTC", True, False) == 10

        # part 2: available funds set is set
        producer._set_initially_available_funds("BTC", decimal.Decimal(8))
        # no allowed_funds set
        # can trade available funds only
        assert producer._get_maximum_traded_funds(0, 10, "BTC", False, False) == 8
        # allowed_funds set
        # can trade allowed_funds (lower than available funds)
        assert producer._get_maximum_traded_funds(5, 10, "BTC", True, False) == 5
        # allowed_funds set, allowed_funds larger than total_available_funds
        # can trade available funds only
        assert producer._get_maximum_traded_funds(15, 10, "BTC", False, False) == 8


async def test_get_new_state_price():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, _, exchange_manager = tools
        producer.current_price = 4000
        assert producer._get_new_state_price() == 4000

        producer.starting_price = 2
        assert producer._get_new_state_price() == 2


async def test_set_increment_and_spread():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, _, exchange_manager = tools
        _, _, _, _, symbol_market = await trading_personal_data.get_pre_order_data(exchange_manager,
                                                                                   symbol=producer.symbol,
                                                                                   timeout=1)
        producer.symbol_market = symbol_market
        assert producer.flat_increment is None
        assert producer.flat_spread is None
        producer._set_increment_and_spread(1000)
        assert producer.flat_increment == 1000 * producer.increment
        assert producer.flat_spread == 1000 * producer.spread

        producer._set_increment_and_spread(2000)
        # no change: producer.flat_increment and producer.flat_spread are not None
        assert producer.flat_increment == 1000 * producer.increment
        assert producer.flat_spread == 1000 * producer.spread

        # reset
        producer.flat_increment = None
        producer.flat_spread = None
        # use candidate_flat_increment
        producer._set_increment_and_spread(3000, candidate_flat_increment=500)
        assert producer.flat_increment == 500
        assert producer.flat_spread == 500 * producer.spread / producer.increment


async def test_use_existing_orders_only():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, _, exchange_manager = tools
        _, _, _, _, symbol_market = await trading_personal_data.get_pre_order_data(exchange_manager,
                                                                                   symbol=producer.symbol,
                                                                                   timeout=1)
        producer.symbol_market = symbol_market
        producer.use_existing_orders_only = True
        assert producer.flat_increment is None
        assert producer.flat_spread is None
        with mock.patch.object(producer, '_create_order', new=mock.AsyncMock()) as mocked_producer_create_order:
            trading_api.force_set_mark_price(exchange_manager, symbol, 4000)
            await producer._ensure_staggered_orders()
            # price info: create trades
            assert producer.current_price == 4000
            assert producer.state == trading_enums.EvaluatorStates.NEUTRAL
            mocked_producer_create_order.assert_not_called()
        assert producer.flat_increment is not None
        assert producer.flat_spread is not None
        await asyncio.create_task(_wait_for_orders_creation(2))
        # did not create orders
        assert not trading_api.get_open_orders(exchange_manager)


async def test_create_orders_without_existing_orders_symmetrical_case_all_modes_price_100():
    price = 100
    await _test_mode(staggered_orders_trading.StrategyModes.NEUTRAL, 25, 2475, price)
    await _test_mode(staggered_orders_trading.StrategyModes.MOUNTAIN, 25, 2475, price)
    await _test_mode(staggered_orders_trading.StrategyModes.VALLEY, 25, 2475, price)
    await _test_mode(staggered_orders_trading.StrategyModes.BUY_SLOPE, 25, 2475, price)
    await _test_mode(staggered_orders_trading.StrategyModes.SELL_SLOPE, 25, 2475, price)
    await _test_mode(staggered_orders_trading.StrategyModes.FLAT, 25, 2475, price)


async def test_create_orders_without_existing_orders_symmetrical_case_all_modes_price_347():
    price = 347
    await _test_mode(staggered_orders_trading.StrategyModes.NEUTRAL, 25, 695, price)
    await _test_mode(staggered_orders_trading.StrategyModes.MOUNTAIN, 25, 695, price)
    await _test_mode(staggered_orders_trading.StrategyModes.VALLEY, 25, 695, price)
    await _test_mode(staggered_orders_trading.StrategyModes.BUY_SLOPE, 25, 695, price)
    await _test_mode(staggered_orders_trading.StrategyModes.SELL_SLOPE, 25, 695, price)
    await _test_mode(staggered_orders_trading.StrategyModes.FLAT, 25, 695, price)


async def test_create_orders_without_existing_orders_symmetrical_case_all_modes_price_0_347():
    price = 0.347
    lowest_buy = 0.001
    highest_sell = 400
    btc_holdings = 400
    await _test_mode(staggered_orders_trading.StrategyModes.NEUTRAL, 25, 28793, price, lowest_buy, highest_sell,
                     btc_holdings)
    await _test_mode(staggered_orders_trading.StrategyModes.MOUNTAIN, 25, 28793, price, lowest_buy, highest_sell,
                     btc_holdings)
    await _test_mode(staggered_orders_trading.StrategyModes.VALLEY, 25, 28793, price, lowest_buy, highest_sell,
                     btc_holdings)
    await _test_mode(staggered_orders_trading.StrategyModes.BUY_SLOPE, 25, 28793, price, lowest_buy, highest_sell,
                     btc_holdings)
    await _test_mode(staggered_orders_trading.StrategyModes.SELL_SLOPE, 25, 28793, price, lowest_buy, highest_sell,
                     btc_holdings)
    await _test_mode(staggered_orders_trading.StrategyModes.FLAT, 25, 28793, price, lowest_buy, highest_sell,
                     btc_holdings)


async def test_create_orders_from_different_markets():
    async with _get_tools("BTC/USD", additional_portfolio={"RDN": 6740, "ETH": 10}) as tools:
        producer, _, exchange_manager = tools
        producer.symbol = "RDN/ETH"

        price = 0.0024161
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        _, _, _, _, symbol_market = await trading_personal_data.get_pre_order_data(exchange_manager,
                                                                                   symbol=producer.symbol,
                                                                                   timeout=1)
        producer.symbol_market = symbol_market
        producer.current_price = decimal.Decimal(str(price))
        producer._refresh_symbol_data(symbol_market)
        producer.min_max_order_details[producer.min_cost] = decimal.Decimal(str(0.01))
        producer.min_max_order_details[producer.min_quantity] = decimal.Decimal(str(1.0))
        producer.min_max_order_details[producer.max_quantity] = decimal.Decimal(str(90000000.0))
        producer.min_max_order_details[producer.max_cost] = None
        producer.min_max_order_details[producer.max_price] = None
        producer.min_max_order_details[producer.min_price] = None

        # await _test_mode(staggered_orders_trading.StrategyModes.NEUTRAL, 0, 0, price)
        lowest_buy = 0.0013
        highest_sell = 0.0043
        expected_buy_count = 46
        expected_sell_count = 78

        producer.lowest_buy = decimal.Decimal(str(lowest_buy))
        producer.highest_sell = decimal.Decimal(str(highest_sell))
        producer.increment = decimal.Decimal(str(0.01))
        producer.spread = decimal.Decimal(str(0.01))
        producer.operational_depth = 10
        producer.final_eval = price
        producer.mode = staggered_orders_trading.StrategyModes.MOUNTAIN

        await _light_check_orders(producer, exchange_manager, expected_buy_count, expected_sell_count, price)

        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == producer.operational_depth

        # test trigger refresh
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, 0.0024161)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))
        # did nothing
        assert original_orders[0] is trading_api.get_open_orders(exchange_manager)[0]
        assert original_orders[-1] is trading_api.get_open_orders(exchange_manager)[-1]
        assert len(trading_api.get_open_orders(exchange_manager)) == producer.operational_depth


async def test_create_orders_from_different_very_close_refresh():
    async with _get_tools("BTC/USD", additional_portfolio={"RDN": 6740, "ETH": 10}) as tools:
        producer, _, exchange_manager = tools
        producer.symbol = "RDN/ETH"
        price = 0.00231
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        _, _, _, _, symbol_market = await trading_personal_data.get_pre_order_data(exchange_manager,
                                                                                   symbol=producer.symbol,
                                                                                   timeout=1)
        producer.symbol_market = symbol_market
        producer.current_price = price
        producer._refresh_symbol_data(symbol_market)
        producer.min_max_order_details[producer.min_cost] = decimal.Decimal(str(0.01))
        producer.min_max_order_details[producer.min_quantity] = decimal.Decimal(str(1.0))
        producer.min_max_order_details[producer.max_quantity] = decimal.Decimal(str(90000000.0))
        producer.min_max_order_details[producer.max_cost] = None
        producer.min_max_order_details[producer.max_price] = None
        producer.min_max_order_details[producer.min_price] = None

        # await _test_mode(staggered_orders_trading.StrategyModes.NEUTRAL, 0, 0, price)
        lowest_buy = 0.00221
        highest_sell = 0.00242
        expected_buy_count = 2
        expected_sell_count = 2

        producer.lowest_buy = decimal.Decimal(str(lowest_buy))
        producer.highest_sell = decimal.Decimal(str(highest_sell))
        producer.increment = decimal.Decimal(str(0.02))
        producer.spread = decimal.Decimal(str(0.02))
        producer.operational_depth = 10
        producer.final_eval = price
        producer.mode = staggered_orders_trading.StrategyModes.MOUNTAIN

        await _light_check_orders(producer, exchange_manager, expected_buy_count, expected_sell_count, price)

        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        original_length = len(original_orders)

        # test trigger refresh
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, 0.0023185)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))
        # did nothing
        assert original_orders[0] is trading_api.get_open_orders(exchange_manager)[0]
        assert original_orders[-1] is trading_api.get_open_orders(exchange_manager)[-1]
        assert original_length == len(trading_api.get_open_orders(exchange_manager))

        # test more trigger refresh
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, 0.0022991)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))
        # did nothing
        assert original_orders[0] is trading_api.get_open_orders(exchange_manager)[0]
        assert original_orders[-1] is trading_api.get_open_orders(exchange_manager)[-1]
        assert original_length == len(trading_api.get_open_orders(exchange_manager))


async def test_create_orders_from_different_markets_not_enough_market_to_create_all_orders():
    async with _get_tools("BTC/USD", additional_portfolio={"RDN": 6740, "ETH": 10}) as tools:
        producer, _, exchange_manager = tools
        producer.symbol = "RDN/ETH"
        price = 0.0024161
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        _, _, _, _, symbol_market = await trading_personal_data.get_pre_order_data(exchange_manager,
                                                                                   symbol=producer.symbol,
                                                                                   timeout=1)
        producer.symbol_market = symbol_market
        producer.current_price = price
        producer._refresh_symbol_data(symbol_market)
        producer.min_max_order_details[producer.min_cost] = decimal.Decimal(str(1.0))
        producer.min_max_order_details[producer.min_quantity] = decimal.Decimal(str(1.0))
        producer.min_max_order_details[producer.max_quantity] = decimal.Decimal(str(90000000.0))
        producer.min_max_order_details[producer.max_cost] = None
        producer.min_max_order_details[producer.max_price] = None
        producer.min_max_order_details[producer.min_price] = None

        # await _test_mode(staggered_orders_trading.StrategyModes.NEUTRAL, 0, 0, price)
        lowest_buy = 0.0013
        highest_sell = 0.0043
        expected_buy_count = 0
        expected_sell_count = 0

        producer.lowest_buy = decimal.Decimal(str(lowest_buy))
        producer.highest_sell = decimal.Decimal(str(highest_sell))
        producer.increment = decimal.Decimal(str(0.01))
        producer.spread = decimal.Decimal(str(0.01))
        producer.operational_depth = 10
        producer.final_eval = price
        producer.mode = staggered_orders_trading.StrategyModes.MOUNTAIN

        await _light_check_orders(producer, exchange_manager, expected_buy_count, expected_sell_count, price)


async def test_start_with_existing_valid_orders():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, _, exchange_manager = tools
        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == producer.operational_depth

        # new evaluation, same price
        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        # did nothing
        await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
        assert original_orders[0] is trading_api.get_open_orders(exchange_manager)[0]
        assert original_orders[-1] is trading_api.get_open_orders(exchange_manager)[-1]
        assert len(trading_api.get_open_orders(exchange_manager)) == producer.operational_depth
        first_buy_index = int(len(trading_api.get_open_orders(exchange_manager)) / 2)

        # new evaluation, price changed
        # -2 order would be filled
        to_fill_order = original_orders[first_buy_index]
        price = 95
        await _fill_order(to_fill_order, exchange_manager, price, producer=producer)
        await asyncio.create_task(_wait_for_orders_creation(2))
        # did nothing: orders got replaced
        assert len(original_orders) == len(trading_api.get_open_orders(exchange_manager))
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        # did nothing
        assert len(original_orders) == len(trading_api.get_open_orders(exchange_manager))

        # orders gets cancelled
        open_orders = trading_api.get_open_orders(exchange_manager)
        to_cancel = [open_orders[20], open_orders[18], open_orders[3]]
        for order in to_cancel:
            await exchange_manager.trader.cancel_order(order)
        post_available = trading_api.get_portfolio_currency(exchange_manager, "USD").available
        assert len(trading_api.get_open_orders(exchange_manager)) == producer.operational_depth - len(to_cancel)

        producer.RECENT_TRADES_ALLOWED_TIME = -1
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))
        # restored orders
        assert len(trading_api.get_open_orders(exchange_manager)) == producer.operational_depth
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USD").available <= post_available
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "BTC").available


async def test_price_initially_out_of_range_1():
    async with _get_tools("BTC/USD", btc_holdings=100000000) as tools:
        producer, _, exchange_manager = tools
        # new evaluation: price in range
        # ~300k sell orders, 0 buy orders
        price = 0.8
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == producer.operational_depth
        assert all(o.side == trading_enums.TradeOrderSide.SELL for o in original_orders)
        assert all(producer.highest_sell >= o.origin_price >= producer.lowest_buy
                   for o in original_orders)


async def test_price_initially_out_of_range_2():
    async with _get_tools("BTC/USD", btc_holdings=10000000) as tools:
        producer, _, exchange_manager = tools
        # new evaluation: price in range
        price = 100000
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == 2
        assert all(o.side == trading_enums.TradeOrderSide.BUY for o in original_orders)
        assert all(producer.highest_sell >= o.origin_price >= producer.lowest_buy
                   for o in original_orders)


async def test_price_going_out_of_range():
    async with _get_tools("BTC/USD") as tools:
        producer, _, exchange_manager = tools
        # new evaluation: price in range
        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))

        # new evaluation: price out of range: >
        price = 100000
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        producer.current_price = price
        existing_orders = trading_api.get_open_orders(exchange_manager)
        sorted_orders = sorted(existing_orders, key=lambda order: order.origin_price)
        missing_orders, state, candidate_flat_increment = producer._analyse_current_orders_situation(
            sorted_orders, [], sorted_orders[0].origin_price, sorted_orders[-1].origin_price, price
        )
        assert missing_orders is None
        assert candidate_flat_increment is None
        assert state == producer.ERROR

        # new evaluation: price out of range: <
        price = 0.1
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        producer.current_price = price
        existing_orders = trading_api.get_open_orders(exchange_manager)
        sorted_orders = sorted(existing_orders, key=lambda order: order.origin_price)
        missing_orders, state, candidate_flat_increment = producer._analyse_current_orders_situation(
            sorted_orders, [], sorted_orders[0].origin_price, sorted_orders[-1].origin_price, price
        )
        assert missing_orders is None
        assert candidate_flat_increment is None
        assert state == producer.ERROR


async def test_start_after_offline_filled_orders():
    async with _get_tools("BTC/USD") as tools:
        producer, _, exchange_manager = tools
        # first start: setup orders
        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == producer.operational_depth
        pre_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USD").available

        # offline simulation: orders get filled but not replaced => price got up to 110 and not down to 90, now is 96s
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled = [o for o in open_orders if 90 <= o.origin_price <= 110]
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        post_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USD").available
        assert pre_portfolio < post_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == producer.operational_depth - len(offline_filled)

        # back online: restore orders according to current price
        price = 96
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        # force not use recent trades
        producer.RECENT_TRADES_ALLOWED_TIME = -1
        await producer._ensure_staggered_orders()
        # restored orders
        await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USD").available <= post_portfolio
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "BTC").available


async def test_health_check_during_filled_orders():
    async with _get_tools("BTC/USD") as tools:
        producer, _, exchange_manager = tools
        # first start: setup orders
        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
        pre_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USD").available

        # offline simulation: orders get filled but not replaced => price got up to 110 and not down to 90, now is 96s
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled = [o for o in open_orders if 90 <= o.origin_price <= 110]
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        post_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USD").available
        assert pre_portfolio < post_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == producer.operational_depth - len(offline_filled)

        # back online: restore orders according to current price
        price = 96
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        # did not restore orders: they are being closed and callback will proceed (considered as recently closed
        # and consumer in queue)
        await asyncio.create_task(
            _check_open_orders_count(exchange_manager, producer.operational_depth - len(offline_filled)))
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USD").available <= post_portfolio
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "BTC").available


async def test_compute_minimum_funds_1():
    async with _get_tools("BTC/USD") as tools:
        producer, _, exchange_manager = tools
        # first start: setup orders
        buy_min_funds = producer._get_min_funds(decimal.Decimal(str(25)), decimal.Decimal(str(0.001)),
                                                staggered_orders_trading.StrategyModes.MOUNTAIN,
                                                decimal.Decimal(100))
        sell_min_funds = producer._get_min_funds(decimal.Decimal(str(2475.25)), decimal.Decimal(str(0.00001)),
                                                 staggered_orders_trading.StrategyModes.MOUNTAIN,
                                                 decimal.Decimal(100))
        assert buy_min_funds == decimal.Decimal(str(0.05)) * staggered_orders_trading.TEN_PERCENT_DECIMAL
        assert sell_min_funds == decimal.Decimal(str(0.049505)) * staggered_orders_trading.TEN_PERCENT_DECIMAL
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("USD").available = buy_min_funds
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("USD").total = buy_min_funds
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("BTC").available = sell_min_funds
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("BTC").total = sell_min_funds
        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))
        orders = trading_api.get_open_orders(exchange_manager)
        assert len(orders) == producer.operational_depth
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.SELL]) == 25
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.BUY]) == 25


async def test_compute_minimum_funds_2():
    async with _get_tools("BTC/USD") as tools:
        producer, _, exchange_manager = tools
        # first start: setup orders
        _, _, _, _, symbol_market = await trading_personal_data.get_pre_order_data(exchange_manager,
                                                                                   symbol=producer.symbol,
                                                                                   timeout=1)
        producer._refresh_symbol_data(symbol_market)
        buy_min_funds = producer._get_min_funds(decimal.Decimal(str(25)), decimal.Decimal(str(0.001)),
                                                staggered_orders_trading.StrategyModes.MOUNTAIN,
                                                decimal.Decimal(str(100)))
        sell_min_funds = producer._get_min_funds(decimal.Decimal(str(2475)), decimal.Decimal(str(0.00001)),
                                                 staggered_orders_trading.StrategyModes.MOUNTAIN,
                                                 decimal.Decimal(str(100)))
        assert buy_min_funds == decimal.Decimal(str(0.05)) * staggered_orders_trading.TEN_PERCENT_DECIMAL
        assert sell_min_funds == decimal.Decimal(str(0.0495)) * staggered_orders_trading.TEN_PERCENT_DECIMAL
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("USD").available = buy_min_funds * decimal.Decimal("0.99999")
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("USD").total = buy_min_funds * decimal.Decimal("0.99999")
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("BTC").available = sell_min_funds * decimal.Decimal("0.99999")
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("BTC").total = sell_min_funds * decimal.Decimal("0.99999")
        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, 0))


async def test_start_without_enough_funds_to_buy():
    async with _get_tools("BTC/USD") as tools:
        producer, _, exchange_manager = tools
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio(
            "USD").available = decimal.Decimal("0.00005")
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio(
            "USD").total = decimal.Decimal("0.00005")
        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))
        orders = trading_api.get_open_orders(exchange_manager)
        assert len(orders) == producer.operational_depth
        assert all([o.side == trading_enums.TradeOrderSide.SELL for o in orders])

        # trigger health check
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))

        await _fill_order(orders[5], exchange_manager, producer=producer)


async def test_start_without_enough_funds_to_sell():
    async with _get_tools("BTC/USD", btc_holdings=0.00001) as tools:
        producer, _, exchange_manager = tools
        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))
        orders = trading_api.get_open_orders(exchange_manager)
        assert len(orders) == 25
        assert all([o.side == trading_enums.TradeOrderSide.BUY for o in orders])

        # trigger health check
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))
        orders = trading_api.get_open_orders(exchange_manager)

        # check order fill callback recreates spread
        to_fill_order = orders[5]
        second_to_fill_order = orders[4]
        await _fill_order(to_fill_order, exchange_manager, producer=producer)
        await asyncio.create_task(_wait_for_orders_creation(2))
        orders = trading_api.get_open_orders(exchange_manager)
        newly_created_sell_order = orders[-1]
        assert newly_created_sell_order.side == trading_enums.TradeOrderSide.SELL
        assert newly_created_sell_order.origin_price == to_fill_order.origin_price + \
               producer.flat_spread - producer.flat_increment

        await _fill_order(second_to_fill_order, exchange_manager, producer=producer)
        await asyncio.create_task(_wait_for_orders_creation(2))
        orders = trading_api.get_open_orders(exchange_manager)
        second_newly_created_sell_order = orders[-1]
        assert second_newly_created_sell_order.side == trading_enums.TradeOrderSide.SELL
        assert second_newly_created_sell_order.origin_price == second_to_fill_order.origin_price + \
               producer.flat_spread - producer.flat_increment
        assert abs(second_newly_created_sell_order.origin_price - newly_created_sell_order.origin_price) == \
               producer.flat_increment


async def test_start_without_enough_funds_at_all():
    async with _get_tools("BTC/USD", btc_holdings=0.00001) as tools:
        producer, _, exchange_manager = tools
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio(
            "USD").available = decimal.Decimal("0.00005")
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio(
            "USD").total = decimal.Decimal("0.00005")
        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, 0))


async def test_settings_for_just_one_order_on_a_side():
    async with _get_tools("BTC/USD") as tools:
        producer, _, exchange_manager = tools
        producer.highest_sell = 106
        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))
        orders = trading_api.get_open_orders(exchange_manager)
        assert len([o for o in orders if o.side == trading_enums.TradeOrderSide.SELL]) == 1


async def test_order_fill_callback():
    async with _get_tools("BTC/USD", fees=0) as tools:
        producer, _, exchange_manager = tools
        # create orders
        price = 100
        producer.mode = staggered_orders_trading.StrategyModes.NEUTRAL
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        previous_total = _get_total_usd(exchange_manager, 100)

        now_btc = trading_api.get_portfolio_currency(exchange_manager, "BTC").total
        now_usd = trading_api.get_portfolio_currency(exchange_manager, "USD").total

        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))
        price_increment = producer.flat_increment
        price_spread = producer.flat_spread

        open_orders = trading_api.get_open_orders(exchange_manager)
        assert len(open_orders) == producer.operational_depth

        # closest to centre buy order is filled => bought btc
        to_fill_order = open_orders[-2]
        await _fill_order(to_fill_order, exchange_manager, producer=producer)
        open_orders = trading_api.get_open_orders(exchange_manager)

        # instantly create sell order at price * (1 + increment)
        assert len(open_orders) == producer.operational_depth
        assert to_fill_order not in open_orders
        newly_created_sell_order = open_orders[-1]
        assert newly_created_sell_order.associated_entry_ids == [to_fill_order.order_id]
        assert newly_created_sell_order.symbol == to_fill_order.symbol
        price = to_fill_order.origin_price + (price_spread - price_increment)
        assert newly_created_sell_order.origin_price == trading_personal_data.decimal_trunc_with_n_decimal_digits(price,
                                                                                                                  8)
        assert newly_created_sell_order.origin_quantity == \
               trading_personal_data.decimal_trunc_with_n_decimal_digits(
                   to_fill_order.filled_quantity * (1 - producer.max_fees),8)
        assert newly_created_sell_order.side == trading_enums.TradeOrderSide.SELL
        assert trading_api.get_portfolio_currency(exchange_manager, "BTC").total > now_btc
        now_btc = trading_api.get_portfolio_currency(exchange_manager, "BTC").total
        current_total = _get_total_usd(exchange_manager, 100)
        assert previous_total < current_total
        previous_total_buy = current_total

        # now this new sell order is filled => sold btc
        to_fill_order = open_orders[-1]
        await _fill_order(to_fill_order, exchange_manager, producer=producer)
        open_orders = trading_api.get_open_orders(exchange_manager)

        # instantly create buy order at price * (1 + increment)
        assert len(open_orders) == producer.operational_depth
        assert to_fill_order not in open_orders
        newly_created_buy_order = open_orders[-1]
        assert newly_created_buy_order.associated_entry_ids is None # buy order => previous sell order is not an entry
        assert newly_created_buy_order.symbol == to_fill_order.symbol
        price = to_fill_order.origin_price - (price_spread - price_increment)
        assert newly_created_buy_order.origin_price == trading_personal_data.decimal_trunc_with_n_decimal_digits(price, 8)
        assert newly_created_buy_order.origin_quantity == \
               trading_personal_data.decimal_trunc_with_n_decimal_digits(
                   to_fill_order.filled_price / price * to_fill_order.filled_quantity * (1 - producer.max_fees), 8)
        assert newly_created_buy_order.side == trading_enums.TradeOrderSide.BUY
        assert trading_api.get_portfolio_currency(exchange_manager, "USD").total > now_usd
        now_usd = trading_api.get_portfolio_currency(exchange_manager, "USD").total
        current_total = _get_total_usd(exchange_manager, 100)
        assert previous_total < current_total
        previous_total_sell = current_total

        # now this new buy order is filled => bought btc
        to_fill_order = open_orders[-1]
        await _fill_order(to_fill_order, exchange_manager, producer=producer)
        open_orders = trading_api.get_open_orders(exchange_manager)

        # instantly create sell order at price * (1 + increment)
        assert len(open_orders) == producer.operational_depth
        assert to_fill_order not in open_orders
        newly_created_sell_order = open_orders[-1]
        assert newly_created_sell_order.associated_entry_ids == [to_fill_order.order_id]
        assert newly_created_sell_order.symbol == to_fill_order.symbol
        price = to_fill_order.origin_price + (price_spread - price_increment)
        assert newly_created_sell_order.origin_price == trading_personal_data.decimal_trunc_with_n_decimal_digits(price, 8)
        assert newly_created_sell_order.origin_quantity == \
               trading_personal_data.decimal_trunc_with_n_decimal_digits(
                   to_fill_order.filled_quantity * (1 - producer.max_fees),
                   8)
        assert newly_created_sell_order.side == trading_enums.TradeOrderSide.SELL
        assert trading_api.get_portfolio_currency(exchange_manager, "BTC").total > now_btc
        current_total = _get_total_usd(exchange_manager, 100)
        assert previous_total_buy < current_total

        # now this new sell order is filled => sold btc
        to_fill_order = open_orders[-1]
        await _fill_order(to_fill_order, exchange_manager, producer=producer)
        open_orders = trading_api.get_open_orders(exchange_manager)

        # instantly create buy order at price * (1 + increment)
        assert len(open_orders) == producer.operational_depth
        assert to_fill_order not in open_orders
        newly_created_buy_order = open_orders[-1]
        assert newly_created_buy_order.associated_entry_ids is None # buy order => previous sell order is not an entry
        assert newly_created_buy_order.symbol == to_fill_order.symbol
        price = to_fill_order.origin_price - (price_spread - price_increment)
        assert newly_created_buy_order.origin_price == trading_personal_data.decimal_trunc_with_n_decimal_digits(price, 8)
        assert newly_created_buy_order.origin_quantity == \
               trading_personal_data.decimal_trunc_with_n_decimal_digits(
                   to_fill_order.filled_price / price * to_fill_order.filled_quantity * (1 - producer.max_fees),
                   8)
        assert newly_created_buy_order.side == trading_enums.TradeOrderSide.BUY
        assert trading_api.get_portfolio_currency(exchange_manager, "USD").total > now_usd
        current_total = _get_total_usd(exchange_manager, 100)
        assert previous_total_sell < current_total


async def test_order_fill_callback_with_mirror_delay():
    async with _get_tools("BTC/USD", fees=0) as tools:
        producer, _, exchange_manager = tools
        # create orders
        price = 100
        producer.mode = staggered_orders_trading.StrategyModes.NEUTRAL
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)

        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(producer.operational_depth))

        open_orders = trading_api.get_open_orders(exchange_manager)
        assert len(open_orders) == producer.operational_depth

        # closest to centre buy order is filled => bought btc
        producer.mirror_order_delay = 0.1
        to_fill_order = open_orders[-2]
        in_backtesting = "tentacles.Trading.Mode.staggered_orders_trading_mode.staggered_orders_trading.trading_api.get_is_backtesting"
        with mock.patch(in_backtesting, return_value=False), \
             mock.patch.object(producer, "_create_order") as producer_create_order_mock:
            await _fill_order(to_fill_order, exchange_manager, producer=producer)
            assert len(producer.mirror_orders_tasks)
            producer_create_order_mock.assert_not_called()
            await asyncio.sleep(0.05)
            producer_create_order_mock.assert_not_called()
            await asyncio.sleep(0.1)
            producer_create_order_mock.assert_called_once()


async def test_compute_mirror_order_volume():
    async with _get_tools("BTC/USD", fees=0) as tools:
        producer, _, exchange_manager = tools
        # no ignore_exchange_fees
        # no fixed volumes
        producer.ignore_exchange_fees = False
        # 1% max fees
        producer.max_fees = decimal.Decimal("0.01")
        # take exchange fees into account
        assert producer._compute_mirror_order_volume(
            True, decimal.Decimal("100"), decimal.Decimal("120"), decimal.Decimal("2"), None
        ) == 2 * (1 - producer.max_fees)
        assert producer._compute_mirror_order_volume(
            False, decimal.Decimal("100"), decimal.Decimal("80"), decimal.Decimal("2"), {}
        ) == 2 * (decimal.Decimal("100") / decimal.Decimal("80")) * (1 - producer.max_fees)
        # with given fees
        fees = {
            trading_enums.FeePropertyColumns.COST.value: decimal.Decimal("0.032"),
            trading_enums.FeePropertyColumns.CURRENCY.value: "BTC"
        }
        assert producer._compute_mirror_order_volume(
            False, decimal.Decimal("100"), decimal.Decimal("80"), decimal.Decimal("2"), fees
        ) == 2 * (decimal.Decimal("100") / decimal.Decimal("80")) - decimal.Decimal("0.032")
        fees = {
            trading_enums.FeePropertyColumns.COST.value: decimal.Decimal("2.3"),
            trading_enums.FeePropertyColumns.CURRENCY.value: "USD"
        }
        assert producer._compute_mirror_order_volume(
            False, decimal.Decimal("100"), decimal.Decimal("80"), decimal.Decimal("2"), fees
        ) == 2 * (decimal.Decimal("100") / decimal.Decimal("80")) - (decimal.Decimal("2.3") / decimal.Decimal("100"))

        # with ignore_exchange_fees
        producer.ignore_exchange_fees = True
        # consider fees already taken, sell everything
        assert producer._compute_mirror_order_volume(
            True, decimal.Decimal("100"), decimal.Decimal("120"), decimal.Decimal("2"), None
        ) == 2
        assert producer._compute_mirror_order_volume(
            False, decimal.Decimal("100"), decimal.Decimal("80"), decimal.Decimal("2"), {}
        ) == 2 * (decimal.Decimal("100") / decimal.Decimal("80"))
        assert producer._compute_mirror_order_volume(
            False, decimal.Decimal("100"), decimal.Decimal("80"), decimal.Decimal("2"), fees
        ) == 2 * (decimal.Decimal("100") / decimal.Decimal("80"))

        # with fixed volumes
        producer.ignore_exchange_fees = False
        producer.sell_volume_per_order = 3
        # consider fees already taken, sell everything
        assert producer._compute_mirror_order_volume(
            True, decimal.Decimal("100"), decimal.Decimal("120"), decimal.Decimal("2"), fees
        ) == 3
        # buy order
        assert producer._compute_mirror_order_volume(
            False, decimal.Decimal("100"), decimal.Decimal("80"), decimal.Decimal("2"), None
        ) == 2 * (decimal.Decimal("100") / decimal.Decimal("80")) * (1 - producer.max_fees)
        producer.buy_volume_per_order = 5
        assert producer._compute_mirror_order_volume(
            False, decimal.Decimal("100"), decimal.Decimal("80"), decimal.Decimal("2"), {}
        ) == 5

        # with fixed volumes and ignore_exchange_fees
        producer.ignore_exchange_fees = True
        assert producer._compute_mirror_order_volume(
            True, decimal.Decimal("100"), decimal.Decimal("120"), decimal.Decimal("2"), None
        ) == 3
        assert producer._compute_mirror_order_volume(
            False, decimal.Decimal("100"), decimal.Decimal("80"), decimal.Decimal("2"), {}
        ) == 5
        assert producer._compute_mirror_order_volume(
            False, decimal.Decimal("100"), decimal.Decimal("80"), decimal.Decimal("2"), fees
        ) == 5


async def test_create_order():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, consumer, exchange_manager = tools
        _, _, _, _, symbol_market = await trading_personal_data.get_pre_order_data(exchange_manager,
                                                                                   symbol=producer.symbol,
                                                                                   timeout=1)
        producer.symbol_market = symbol_market
        producer._refresh_symbol_data(symbol_market)

        _origin_decimal_adapt_order_quantity_because_fees = trading_personal_data.decimal_adapt_order_quantity_because_fees

        def _decimal_adapt_order_quantity_because_fees(
            exchange_manager, symbol: str, order_type: trading_enums.TraderOrderType, quantity: decimal.Decimal,
            price: decimal.Decimal, side: trading_enums.TradeOrderSide
        ):
            return quantity

        with mock.patch.object(
                trading_personal_data, "decimal_adapt_order_quantity_because_fees",
                mock.Mock(side_effect=_decimal_adapt_order_quantity_because_fees)
        ) as decimal_adapt_order_quantity_because_fees_mock:

            # SELL

            # enough quantity in portfolio
            price = decimal.Decimal(100)
            quantity = decimal.Decimal(1)
            side = trading_enums.TradeOrderSide.SELL
            to_create_order = staggered_orders_trading.OrderData(side, quantity, price, symbol, False)
            created_order = (await consumer.create_order(to_create_order, price, symbol_market))[0]
            assert created_order.origin_quantity == quantity
            decimal_adapt_order_quantity_because_fees_mock.assert_called_with(
                exchange_manager, symbol, trading_enums.TraderOrderType.SELL_LIMIT,
                created_order.origin_quantity, created_order.origin_price, trading_enums.TradeOrderSide.SELL,
            )
            decimal_adapt_order_quantity_because_fees_mock.reset_mock()

            # not enough quantity in portfolio
            price = decimal.Decimal(100)
            quantity = decimal.Decimal(10)
            side = trading_enums.TradeOrderSide.SELL
            to_create_order = staggered_orders_trading.OrderData(side, quantity, price, symbol, False)
            created_order = await consumer.create_order(to_create_order, price, symbol_market)
            decimal_adapt_order_quantity_because_fees_mock.assert_called_with(
                exchange_manager, symbol, trading_enums.TraderOrderType.SELL_LIMIT,
                decimal.Decimal('10'), decimal.Decimal('100'), trading_enums.TradeOrderSide.SELL
            )
            decimal_adapt_order_quantity_because_fees_mock.reset_mock()
            assert created_order == []

            # just enough quantity in portfolio
            price = decimal.Decimal(100)
            quantity = decimal.Decimal(9)
            side = trading_enums.TradeOrderSide.SELL
            to_create_order = staggered_orders_trading.OrderData(side, quantity, price, symbol, False)
            created_order = (await consumer.create_order(to_create_order, price, symbol_market))[0]
            decimal_adapt_order_quantity_because_fees_mock.assert_called_once()
            decimal_adapt_order_quantity_because_fees_mock.reset_mock()
            assert created_order.origin_quantity == quantity
            assert trading_api.get_portfolio_currency(exchange_manager, "BTC").available == decimal.Decimal(0)

            # not enough quantity anymore
            price = decimal.Decimal(100)
            quantity = decimal.Decimal("0.0001")
            side = trading_enums.TradeOrderSide.SELL
            to_create_order = staggered_orders_trading.OrderData(side, quantity, price, symbol, False)
            created_orders = await consumer.create_order(to_create_order, price, symbol_market)
            decimal_adapt_order_quantity_because_fees_mock.assert_called_once()
            decimal_adapt_order_quantity_because_fees_mock.reset_mock()
            assert trading_api.get_portfolio_currency(exchange_manager, "BTC").available == decimal.Decimal(0)
            assert created_orders == []

            # BUY

            # enough quantity in portfolio
            price = decimal.Decimal(100)
            quantity = decimal.Decimal(1)
            side = trading_enums.TradeOrderSide.BUY
            to_create_order = staggered_orders_trading.OrderData(side, quantity, price, symbol, False)
            created_order = (await consumer.create_order(to_create_order, price, symbol_market))[0]
            decimal_adapt_order_quantity_because_fees_mock.assert_called_with(
                exchange_manager, symbol, trading_enums.TraderOrderType.BUY_LIMIT,
                created_order.origin_quantity, created_order.origin_price, trading_enums.TradeOrderSide.BUY,
            )
            decimal_adapt_order_quantity_because_fees_mock.reset_mock()
            assert created_order.origin_quantity == quantity
            assert trading_api.get_portfolio_currency(exchange_manager, "USD").available == 900
            assert created_order is not None

            # not enough quantity in portfolio
            price = decimal.Decimal(585)
            quantity = decimal.Decimal(2)
            side = trading_enums.TradeOrderSide.BUY
            to_create_order = staggered_orders_trading.OrderData(side, quantity, price, symbol, False)
            created_orders = await consumer.create_order(to_create_order, price, symbol_market)
            decimal_adapt_order_quantity_because_fees_mock.assert_called_with(
                exchange_manager, symbol, trading_enums.TraderOrderType.BUY_LIMIT,
                decimal.Decimal('2'), decimal.Decimal('585'), trading_enums.TradeOrderSide.BUY
            )
            decimal_adapt_order_quantity_because_fees_mock.reset_mock()
            assert trading_api.get_portfolio_currency(exchange_manager, "USD").available == 900
            assert created_orders == []

            # enough quantity in portfolio
            price = decimal.Decimal(40)
            quantity = decimal.Decimal(2)
            side = trading_enums.TradeOrderSide.BUY
            to_create_order = staggered_orders_trading.OrderData(side, quantity, price, symbol, False)
            created_order = (await consumer.create_order(to_create_order, price, symbol_market))[0]
            decimal_adapt_order_quantity_because_fees_mock.assert_called_once()
            decimal_adapt_order_quantity_because_fees_mock.reset_mock()
            assert created_order.origin_quantity == quantity
            assert trading_api.get_portfolio_currency(exchange_manager, "USD").available == 820

            # enough quantity in portfolio
            price = decimal.Decimal(205)
            quantity = decimal.Decimal(4)
            side = trading_enums.TradeOrderSide.BUY
            to_create_order = staggered_orders_trading.OrderData(side, quantity, price, symbol, False)
            created_order = (await consumer.create_order(to_create_order, price, symbol_market))[0]
            decimal_adapt_order_quantity_because_fees_mock.assert_called_once()
            decimal_adapt_order_quantity_because_fees_mock.reset_mock()
            assert created_order.origin_quantity == quantity
            assert trading_api.get_portfolio_currency(exchange_manager, "USD").available == 0
            assert created_order is not None

            # not enough quantity in portfolio anymore
            price = decimal.Decimal(205)
            quantity = decimal.Decimal(1)
            side = trading_enums.TradeOrderSide.BUY
            to_create_order = staggered_orders_trading.OrderData(side, quantity, price, symbol, False)
            created_orders = await consumer.create_order(to_create_order, price, symbol_market)
            decimal_adapt_order_quantity_because_fees_mock.assert_called_once()
            decimal_adapt_order_quantity_because_fees_mock.reset_mock()
            assert trading_api.get_portfolio_currency(exchange_manager, "USD").available == 0
            assert created_orders == []


async def test_create_state():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, consumer, exchange_manager = tools
        price = decimal.Decimal(1000)
        ignore_mirror_orders_only = False
        ignore_available_funds = False
        trigger_trailing = False
        _, _, _, _, producer.symbol_market = await trading_personal_data.get_pre_order_data(exchange_manager, symbol)
        # not triggering trailing
        with mock.patch.object(producer, "_generate_staggered_orders", mock.AsyncMock(return_value=([], [], False))) \
            as _generate_staggered_orders_mock, mock.patch.object(producer, "_create_not_virtual_orders", mock.AsyncMock()) \
            as _create_not_virtual_orders_mock:
            await producer.create_state(price, ignore_mirror_orders_only, ignore_available_funds, trigger_trailing)
            _generate_staggered_orders_mock.assert_awaited_once_with(price, ignore_available_funds, trigger_trailing)
            _create_not_virtual_orders_mock.assert_awaited_once_with([], price, False)

        # triggering trailing
        with mock.patch.object(producer, "_generate_staggered_orders", mock.AsyncMock(return_value=([], [], True))) \
            as _generate_staggered_orders_mock, mock.patch.object(producer, "_create_not_virtual_orders", mock.AsyncMock()) \
            as _create_not_virtual_orders_mock:
            await producer.create_state(price, ignore_mirror_orders_only, ignore_available_funds, trigger_trailing)
            _generate_staggered_orders_mock.assert_awaited_once_with(price, ignore_available_funds, trigger_trailing)
            _create_not_virtual_orders_mock.assert_awaited_once_with([], price, True)
        trigger_trailing = True
        with mock.patch.object(producer, "_generate_staggered_orders", mock.AsyncMock(return_value=([], [], True))) \
            as _generate_staggered_orders_mock, mock.patch.object(producer, "_create_not_virtual_orders", mock.AsyncMock()) \
            as _create_not_virtual_orders_mock:
            await producer.create_state(price, ignore_mirror_orders_only, ignore_available_funds, trigger_trailing)
            _generate_staggered_orders_mock.assert_awaited_once_with(price, ignore_available_funds, trigger_trailing)
            _create_not_virtual_orders_mock.assert_awaited_once_with([], price, True)

        # already trailing: skip call
        producer.is_currently_trailing = True
        with mock.patch.object(producer, "_generate_staggered_orders", mock.AsyncMock(return_value=([], [], True))) \
            as _generate_staggered_orders_mock, mock.patch.object(producer, "_create_not_virtual_orders", mock.AsyncMock()) \
            as _create_not_virtual_orders_mock:
            await producer.create_state(price, ignore_mirror_orders_only, ignore_available_funds, trigger_trailing)
            _generate_staggered_orders_mock.assert_not_called()
            _create_not_virtual_orders_mock.assert_not_called()
        with mock.patch.object(producer, "_generate_staggered_orders", mock.AsyncMock(return_value=([], [], False))) \
            as _generate_staggered_orders_mock, mock.patch.object(producer, "_create_not_virtual_orders", mock.AsyncMock()) \
            as _create_not_virtual_orders_mock:
            await producer.create_state(price, ignore_mirror_orders_only, ignore_available_funds, trigger_trailing)
            _generate_staggered_orders_mock.assert_not_called()
            _create_not_virtual_orders_mock.assert_not_called()

        # not tailing anymore: can now call
        producer.is_currently_trailing = False
        with mock.patch.object(producer, "_generate_staggered_orders", mock.AsyncMock(return_value=([], [], True))) \
            as _generate_staggered_orders_mock, mock.patch.object(producer, "_create_not_virtual_orders", mock.AsyncMock()) \
            as _create_not_virtual_orders_mock:
            await producer.create_state(price, ignore_mirror_orders_only, ignore_available_funds, trigger_trailing)
            _generate_staggered_orders_mock.assert_awaited_once_with(price, ignore_available_funds, trigger_trailing)
            _create_not_virtual_orders_mock.assert_awaited_once_with([], price, True)
        trigger_trailing = True
        with mock.patch.object(producer, "_generate_staggered_orders", mock.AsyncMock(return_value=([], [], False))) \
            as _generate_staggered_orders_mock, mock.patch.object(producer, "_create_not_virtual_orders", mock.AsyncMock()) \
            as _create_not_virtual_orders_mock:
            await producer.create_state(price, ignore_mirror_orders_only, ignore_available_funds, trigger_trailing)
            _generate_staggered_orders_mock.assert_awaited_once_with(price, ignore_available_funds, trigger_trailing)
            _create_not_virtual_orders_mock.assert_awaited_once_with([], price, False)


async def test_create_new_orders():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, consumer, exchange_manager = tools
        _, _, _, _, symbol_market = await trading_personal_data.get_pre_order_data(exchange_manager,
                                                                                   symbol=producer.symbol,
                                                                                   timeout=1)
        producer.symbol_market = symbol_market
        producer._refresh_symbol_data(symbol_market)

        # valid input
        price = decimal.Decimal(205)
        quantity = decimal.Decimal(1)
        side = trading_enums.TradeOrderSide.BUY
        to_create_order = staggered_orders_trading.OrderData(side, quantity, price, symbol, False)
        producer.is_currently_trailing = True
        data = {
            consumer.ORDER_DATA_KEY: to_create_order,
            consumer.CURRENT_PRICE_KEY: price,
            consumer.SYMBOL_MARKET_KEY: symbol_market,
            consumer.COMPLETING_TRAILING_KEY: False,
        }
        assert await consumer.create_new_orders(symbol, None, None, data=data)
        assert producer.is_currently_trailing is True
        data = {
            consumer.ORDER_DATA_KEY: to_create_order,
            consumer.CURRENT_PRICE_KEY: price,
            consumer.SYMBOL_MARKET_KEY: symbol_market,
            consumer.COMPLETING_TRAILING_KEY: True, # will update producer.is_currently_trailing
        }
        assert await consumer.create_new_orders(symbol, None, None, data=data)
        assert producer.is_currently_trailing is False  # updated to false

        # invalid input 1
        data = {
            consumer.ORDER_DATA_KEY: to_create_order,
            consumer.CURRENT_PRICE_KEY: price
        }
        with pytest.raises(KeyError):
            await consumer.create_new_orders(symbol, None, None, data=data)

        # invalid input 2
        data = {}
        with pytest.raises(KeyError):
            await consumer.create_new_orders(symbol, None, None, data=data)

        # invalid input 3
        with pytest.raises(KeyError):
            await consumer.create_new_orders(symbol, None, None)


async def test_ensure_current_price_in_limit_parameters():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, _, exchange_manager = tools
        producer.already_errored_on_out_of_window_price = False

        with mock.patch.object(producer, "_log_window_error_or_warning", mock.Mock()) \
                as _log_window_error_or_warning_mock:
            # price too low (lower bound is 1)
            producer._ensure_current_price_in_limit_parameters(0.1)
            _log_window_error_or_warning_mock.assert_called_once()
            assert _log_window_error_or_warning_mock.mock_calls[0].args[1] is True
            _log_window_error_or_warning_mock.reset_mock()
            assert producer.already_errored_on_out_of_window_price is True
            producer._ensure_current_price_in_limit_parameters(0.1)
            assert _log_window_error_or_warning_mock.mock_calls[0].args[1] is False
            _log_window_error_or_warning_mock.reset_mock()
            assert producer.already_errored_on_out_of_window_price is True

            producer.already_errored_on_out_of_window_price = False
            # price too high (higher bound is 10000)
            producer._ensure_current_price_in_limit_parameters(999999)
            assert _log_window_error_or_warning_mock.mock_calls[0].args[1] is True
            _log_window_error_or_warning_mock.reset_mock()
            assert producer.already_errored_on_out_of_window_price is True
            producer._ensure_current_price_in_limit_parameters(999999)
            assert _log_window_error_or_warning_mock.mock_calls[0].args[1] is False
            _log_window_error_or_warning_mock.reset_mock()
            assert producer.already_errored_on_out_of_window_price is True


async def test_single_exchange_process_optimize_initial_portfolio():
    async with _get_tools("BTC/USD") as tools:
        producer, _, exchange_manager = tools
        mode = producer.trading_mode
        exchange_manager.exchange_config.traded_symbol_pairs = ["BTC/USD"]
        exchange_manager.client_symbols = ["BTC/USD"]

        initial_portfolio = exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio
        assert initial_portfolio["BTC"].available == decimal.Decimal("10")
        assert initial_portfolio["USD"].available == decimal.Decimal("1000")

        limit_buy = trading_personal_data.BuyLimitOrder(exchange_manager.trader)
        limit_buy.update(order_type=trading_enums.TraderOrderType.BUY_LIMIT,
                         symbol="BTC/USD",
                         current_price=decimal.Decimal(str(50)),
                         quantity=decimal.Decimal(str(2)),
                         price=decimal.Decimal(str(50)))
        await exchange_manager.exchange_personal_data.orders_manager.upsert_order_instance(limit_buy)

        orders = await mode.single_exchange_process_optimize_initial_portfolio(
            ["BTC", "ETH"], "USD", {"BTC/USD": {trading_enums.ExchangeConstantsTickersColumns.CLOSE.value: 1000}}
        )
        cancelled_orders, part_1_orders, part_2_orders = [orders[0], orders[1], orders[2]]

        assert len(cancelled_orders) == 1
        assert cancelled_orders[0] is limit_buy

        assert len(part_1_orders) == 1
        part_1_order = part_1_orders[0]
        assert isinstance(part_1_order, trading_personal_data.SellMarketOrder)
        assert part_1_order.created_last_price == decimal.Decimal("1000")
        assert part_1_order.origin_quantity == decimal.Decimal("10")    # 10 BTC to sell into 10 000 USD
        assert part_1_order.status == trading_enums.OrderStatus.FILLED

        assert part_2_orders
        part_2_order = part_2_orders[0]
        assert isinstance(part_2_order, trading_personal_data.BuyMarketOrder)
        assert part_2_order.created_last_price == decimal.Decimal("1000")
        assert part_2_order.origin_quantity == decimal.Decimal("5.545")    # 50% of funds
        assert part_2_order.status == trading_enums.OrderStatus.FILLED

        # check portfolio is rebalanced
        final_portfolio = exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio
        assert final_portfolio["BTC"].available == decimal.Decimal('5.539455')  # 5.545 - fees
        assert final_portfolio["USD"].available == decimal.Decimal("5545")


async def test_prepare_trailing():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, _, exchange_manager = tools

        trading_api.force_set_mark_price(exchange_manager, symbol, 4000)
        with mock.patch.object(producer, "_ensure_current_price_in_limit_parameters", mock.Mock()) \
                as _ensure_current_price_in_limit_parameters_mock:
            await producer._ensure_staggered_orders()
            _ensure_current_price_in_limit_parameters_mock.assert_called_once()
        # price info: create orders
        assert producer.current_price == 4000
        await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
        # now has buy and sell orders
        open_orders = exchange_manager.exchange_personal_data.orders_manager.get_open_orders()
        # simulate price being stable
        cancelled_orders, created_orders = await producer._prepare_trailing(open_orders, current_price=4000)
        assert len(cancelled_orders) == len(open_orders)
        # cancelled orders
        updated_open_orders = exchange_manager.exchange_personal_data.orders_manager.get_open_orders()
        assert updated_open_orders == []

        # created order to balance BTC and USD (sell BTC)
        assert len(created_orders) == 1
        assert created_orders[0].symbol == symbol
        assert created_orders[0].origin_quantity == decimal.Decimal("4.87500000")
        fees = created_orders[0].fee[trading_enums.FeePropertyColumns.COST.value]
        assert fees == decimal.Decimal("19.5")
        assert isinstance(created_orders[0], trading_personal_data.SellMarketOrder)

        portfolio = exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio
        # portfolio is now balanced
        assert portfolio["BTC"].available == decimal.Decimal("5.125")   # 5.125 x 4000 = 20500
        assert portfolio["USD"].available == decimal.Decimal("20480.5") == decimal.Decimal("20500") - fees

        # price change (going down), no order to cancel: just adapt pf
        trading_api.force_set_mark_price(exchange_manager, symbol, 3000)
        cancelled_orders, created_orders = await producer._prepare_trailing(open_orders, current_price=3000)
        # no order to cancel (orders are already cancelled)
        assert len(cancelled_orders) == 0
        # created order to balance BTC and USD (buy BTC)
        assert len(created_orders) == 1
        assert created_orders[0].symbol == symbol
        assert created_orders[0].origin_quantity == decimal.Decimal('0.85091666')
        fees = created_orders[0].fee[trading_enums.FeePropertyColumns.COST.value]
        assert fees == decimal.Decimal('0.00085091666')
        assert isinstance(created_orders[0], trading_personal_data.BuyMarketOrder)

        assert portfolio["BTC"].available == decimal.Decimal('5.97506574334')   # Decimal('5.97506574334') x 3000 = Decimal('17925.19723002000')
        assert portfolio["USD"].available == decimal.Decimal('17927.75002000000')

        # price change (going up), no order to cancel: just adapt pf
        trading_api.force_set_mark_price(exchange_manager, symbol, 8000)
        cancelled_orders, created_orders = await producer._prepare_trailing([], current_price=8000)
        # no order to cancel
        assert len(cancelled_orders) == 0
        # created order to balance BTC and USD (buy BTC)
        assert len(created_orders) == 1
        assert created_orders[0].symbol == symbol
        assert created_orders[0].origin_quantity == decimal.Decimal('1.86704849')
        fees = created_orders[0].fee[trading_enums.FeePropertyColumns.COST.value]
        assert fees == decimal.Decimal('14.93638792000')
        assert isinstance(created_orders[0], trading_personal_data.SellMarketOrder)

        assert portfolio["BTC"].available == decimal.Decimal('4.10801725334')   # Decimal('4.10801725334') x 8000 = Decimal('32864.13802672000')
        assert portfolio["USD"].available == decimal.Decimal('32849.20155208000')


async def test_should_trigger_trailing_not_all_buy_order_created():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        current_price = decimal.Decimal(4000)
        producer, _, exchange_manager = tools
        # A. no open order: no trailing
        assert producer._should_trigger_trailing([], current_price, False) is False
        producer.enable_trailing_up = producer.enable_trailing_down = True
        assert producer._should_trigger_trailing([], current_price, False) is False

        # create orders
        trading_api.force_set_mark_price(exchange_manager, symbol, 4000)
        with mock.patch.object(producer, "_ensure_current_price_in_limit_parameters", mock.Mock()) \
                as _ensure_current_price_in_limit_parameters_mock:
            await producer._ensure_staggered_orders()
            _ensure_current_price_in_limit_parameters_mock.assert_called_once()

        assert producer.current_price == 4000
        await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
        # now has buy and sell orders

        # B. trailing disabled
        producer.enable_trailing_up = producer.enable_trailing_down = False
        assert producer._should_trigger_trailing([], current_price, False) is False
        open_orders = exchange_manager.exchange_personal_data.orders_manager.get_open_orders()
        buy_orders = [order for order in open_orders if order.side == trading_enums.TradeOrderSide.BUY]
        sell_orders = [order for order in open_orders if order.side == trading_enums.TradeOrderSide.SELL]
        assert len(buy_orders) > 10
        assert len(sell_orders) > 10
        assert producer._should_trigger_trailing(buy_orders, current_price, False) is False
        assert producer._should_trigger_trailing(sell_orders, current_price, False) is False

        # C. trailing enabled
        producer.enable_trailing_up = True
        assert producer._should_trigger_trailing(sell_orders, current_price, False) is False
        # True because all buy orders couldn't be created: impossible to check accurately
        assert producer._should_trigger_trailing(buy_orders, current_price, False) is True

        producer.enable_trailing_down = True
        assert producer._should_trigger_trailing(sell_orders, current_price, False) is False
        assert producer._should_trigger_trailing(sell_orders, decimal.Decimal(100), False) is True
        assert producer._should_trigger_trailing(buy_orders, current_price, False) is True

        # D. no trailing if at least 1 order on each side
        assert producer._should_trigger_trailing(buy_orders + sell_orders, current_price, False) is False
        assert producer._should_trigger_trailing([buy_orders[0]] + sell_orders, current_price, False) is False

        # E. use open orders
        assert producer._should_trigger_trailing([], current_price, False) is False
        assert producer._should_trigger_trailing([], current_price, True) is False


async def test_should_trigger_trailing_all_buy_order_created():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        current_price = decimal.Decimal(4000)
        producer, _, exchange_manager = tools
        producer.increment = decimal.Decimal("0.02")    # instead of 0.04
        # A. no open order: no trailing
        assert producer._should_trigger_trailing([], current_price, False) is False
        producer.enable_trailing_up = producer.enable_trailing_down = True
        assert producer._should_trigger_trailing([], current_price, False) is False

        # create orders
        trading_api.force_set_mark_price(exchange_manager, symbol, 4000)
        with mock.patch.object(producer, "_ensure_current_price_in_limit_parameters", mock.Mock()) \
                as _ensure_current_price_in_limit_parameters_mock:
            await producer._ensure_staggered_orders()
            _ensure_current_price_in_limit_parameters_mock.assert_called_once()

        assert producer.current_price == 4000
        await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
        # now has buy and sell orders

        # B. trailing disabled
        producer.enable_trailing_up = producer.enable_trailing_down = False
        assert producer._should_trigger_trailing([], current_price, False) is False
        open_orders = exchange_manager.exchange_personal_data.orders_manager.get_open_orders()
        buy_orders = [order for order in open_orders if order.side == trading_enums.TradeOrderSide.BUY]
        sell_orders = [order for order in open_orders if order.side == trading_enums.TradeOrderSide.SELL]
        assert len(buy_orders) > 10
        assert len(sell_orders) > 10
        assert producer._should_trigger_trailing(buy_orders, current_price, False) is False
        assert producer._should_trigger_trailing(sell_orders, current_price, False) is False

        # C. trailing enabled
        producer.enable_trailing_up = True
        assert producer._should_trigger_trailing(sell_orders, current_price, False) is False
        assert producer._should_trigger_trailing(sell_orders, None, False) is False
        assert producer._should_trigger_trailing(buy_orders, current_price, False) is False
        assert producer._should_trigger_trailing(buy_orders, decimal.Decimal(6000), False) is True
        assert producer._should_trigger_trailing(buy_orders, None, True) is True
        assert producer._should_trigger_trailing(buy_orders, None, False) is False

        producer.enable_trailing_down = True
        assert producer._should_trigger_trailing(sell_orders, current_price, False) is False
        assert producer._should_trigger_trailing(sell_orders, decimal.Decimal(2000), False) is True
        assert producer._should_trigger_trailing(sell_orders, None, True) is True
        assert producer._should_trigger_trailing(buy_orders, current_price, False) is False
        assert producer._should_trigger_trailing(buy_orders, None, False) is False
        assert producer._should_trigger_trailing(buy_orders, None, True) is True

        # D. no trailing if at least 1 order on each side
        assert producer._should_trigger_trailing(buy_orders + sell_orders, current_price, False) is False
        assert producer._should_trigger_trailing([buy_orders[0]] + sell_orders, current_price, False) is False

        # E. use open orders
        assert producer._should_trigger_trailing([], current_price, False) is False
        assert producer._should_trigger_trailing([], current_price, True) is False  # has open orders on the other side


async def test_order_notification_callback():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, _, exchange_manager = tools
        producer.increment = decimal.Decimal("0.02") # replaces 0.04

        # create orders
        trading_api.force_set_mark_price(exchange_manager, symbol, 4000)
        with mock.patch.object(producer, "_ensure_current_price_in_limit_parameters", mock.Mock()) \
                as _ensure_current_price_in_limit_parameters_mock:
            await producer._ensure_staggered_orders()
            _ensure_current_price_in_limit_parameters_mock.assert_called_once()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))

        # cancel sell orders and change reference price to 6000: should trigger trailing
        open_orders = exchange_manager.exchange_personal_data.orders_manager.get_open_orders()
        buy_orders = [order for order in open_orders if order.side == trading_enums.TradeOrderSide.BUY]
        sell_orders = [order for order in open_orders if order.side == trading_enums.TradeOrderSide.SELL]
        for order in sell_orders:
            await exchange_manager.trader.cancel_order(order)
        trading_api.force_set_mark_price(exchange_manager, symbol, 6000)
        filled_order = buy_orders[0]
        filled_order.filled_price = 6000
        producer.enable_trailing_up = producer.enable_trailing_down = False
        with mock.patch.object(producer, "_lock_portfolio_and_create_order_when_possible", mock.AsyncMock()) as _lock_portfolio_and_create_order_when_possible:
            await _fill_order(filled_order, exchange_manager, trigger_update_callback=True)
            # trailing disabled
            _lock_portfolio_and_create_order_when_possible.assert_called_once()
        assert len(exchange_manager.exchange_personal_data.orders_manager.get_open_orders()) == len(sell_orders) - 1

        # will trail
        filled_order = buy_orders[1]
        filled_order.filled_price = 6000
        producer.enable_trailing_up = producer.enable_trailing_down = True
        with mock.patch.object(producer, "_lock_portfolio_and_create_order_when_possible", mock.AsyncMock()) as _lock_portfolio_and_create_order_when_possible:
            await _fill_order(filled_order, exchange_manager, trigger_update_callback=True)
            # trailing trigger
            await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
            updated_open_orders = exchange_manager.exchange_personal_data.orders_manager.get_open_orders()
            buy_orders = [order for order in updated_open_orders if order.side == trading_enums.TradeOrderSide.BUY]
            sell_orders = [order for order in updated_open_orders if order.side == trading_enums.TradeOrderSide.SELL]
            assert len(buy_orders) == 25
            assert len(sell_orders) == 25
            # trailed instead
            _lock_portfolio_and_create_order_when_possible.assert_not_called()

        filled_order = buy_orders[0]
        with mock.patch.object(producer, "_lock_portfolio_and_create_order_when_possible", mock.AsyncMock()) as _lock_portfolio_and_create_order_when_possible:
            await _fill_order(filled_order, exchange_manager, trigger_update_callback=True)
            # do not trail again, create mirror order instead
            _lock_portfolio_and_create_order_when_possible.assert_called_once()


async def test_create_mirror_order_considering_exchange_fees():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, _, exchange_manager = tools
        producer.ignore_exchange_fees = False
        # create orders
        price = 100
        producer.mode = staggered_orders_trading.StrategyModes.NEUTRAL
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))

        open_orders = exchange_manager.exchange_personal_data.orders_manager.get_open_orders()
        buy_orders = [order for order in open_orders if order.side == trading_enums.TradeOrderSide.BUY]
        sell_orders = [order for order in open_orders if order.side == trading_enums.TradeOrderSide.SELL]
        buy_sell_increment = producer.flat_spread - producer.flat_increment

        # mirroring buy order
        buy_1 = buy_orders[0]
        assert buy_1.origin_price == decimal.Decimal("97")
        assert buy_1.origin_quantity == decimal.Decimal("0.46")
        assert buy_1.side == trading_enums.TradeOrderSide.BUY
        buy_1_mirror_order = producer._create_mirror_order(buy_1.to_dict())
        assert isinstance(buy_1_mirror_order, staggered_orders_trading.OrderData)
        assert buy_1_mirror_order.associated_entry_id == buy_1.order_id
        assert buy_1_mirror_order.side == trading_enums.TradeOrderSide.SELL
        assert buy_1_mirror_order.symbol == symbol
        assert buy_1_mirror_order.price == decimal.Decimal("99") == buy_1.origin_price + buy_sell_increment
        assert buy_1_mirror_order.quantity < buy_1.origin_quantity  # adapted for exchange fees
        assert buy_1_mirror_order.quantity == decimal.Decimal('0.4595400')

        # mirroring sell order
        sell_1 = sell_orders[0]
        assert sell_1.origin_price == decimal.Decimal("103")
        assert sell_1.origin_quantity == decimal.Decimal('0.00464646')
        assert sell_1.side == trading_enums.TradeOrderSide.SELL
        sell_1_mirror_order = producer._create_mirror_order(sell_1.to_dict())
        assert isinstance(sell_1_mirror_order, staggered_orders_trading.OrderData)
        assert sell_1_mirror_order.associated_entry_id is None
        assert sell_1_mirror_order.side == trading_enums.TradeOrderSide.BUY
        assert sell_1_mirror_order.symbol == symbol
        assert sell_1_mirror_order.price == decimal.Decimal("101") == sell_1.origin_price - buy_sell_increment
        assert sell_1_mirror_order.quantity > sell_1.origin_quantity
        assert sell_1_mirror_order.quantity == decimal.Decimal('0.004733730639801980198019801981')

        # fill price is != from origin price => use origin price to avoid moving grid orders
        assert buy_1.origin_price == decimal.Decimal("97")
        buy_1.filled_price = decimal.Decimal("96")  # simulate fill at 96
        buy_2_mirror_order = producer._create_mirror_order(buy_1.to_dict())
        assert isinstance(buy_2_mirror_order, staggered_orders_trading.OrderData)
        # mirror order price is still 99, even if fill price is not 97
        assert buy_2_mirror_order.price == decimal.Decimal("99") == buy_1.origin_price + buy_sell_increment
        assert buy_2_mirror_order.associated_entry_id == buy_1.order_id
        assert buy_2_mirror_order.side == trading_enums.TradeOrderSide.SELL
        # new sell order quantity is equal to previous mirror order quantity: only the amount of USDT spend is smaller
        assert buy_2_mirror_order.quantity == buy_1_mirror_order.quantity
        assert buy_2_mirror_order.quantity == decimal.Decimal('0.4595400')

        # sell_1 will be found in trades
        assert sell_1.origin_price == decimal.Decimal("103")
        sell_1.filled_price = decimal.Decimal("110")  # simulate fill at 110
        await _fill_order(sell_1, exchange_manager, trigger_update_callback=False, producer=producer)
        maybe_trade, maybe_order = exchange_manager.exchange_personal_data.get_trade_or_open_order(
            sell_1.order_id
        )
        assert maybe_trade
        assert maybe_trade.origin_price == decimal.Decimal("103")
        assert maybe_order is None
        sell_2_mirror_order = producer._create_mirror_order(sell_1.to_dict())
        assert sell_2_mirror_order.associated_entry_id is None
        # mirror order price is still 101, even if fill price is not 110
        assert sell_2_mirror_order.price == decimal.Decimal("101") == sell_1.origin_price - buy_sell_increment
        assert sell_2_mirror_order.side == trading_enums.TradeOrderSide.BUY
        # new buy order quantity is larger than previous one as sell order was filled at a higher price
        assert sell_2_mirror_order.quantity > sell_1_mirror_order.quantity
        assert sell_2_mirror_order.quantity == decimal.Decimal('0.005055854530099009900990099009')


async def test_create_mirror_order_ignoring_exchange_fees():
    symbol = "BTC/USD"
    async with _get_tools(symbol) as tools:
        producer, _, exchange_manager = tools
        producer.ignore_exchange_fees = True
        # create orders
        price = 100
        producer.mode = staggered_orders_trading.StrategyModes.NEUTRAL
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))

        open_orders = exchange_manager.exchange_personal_data.orders_manager.get_open_orders()
        buy_orders = [order for order in open_orders if order.side == trading_enums.TradeOrderSide.BUY]
        sell_orders = [order for order in open_orders if order.side == trading_enums.TradeOrderSide.SELL]
        buy_sell_increment = producer.flat_spread - producer.flat_increment

        # mirroring buy order with enough remaining funds in portfolio to keep the same quantity
        buy_1 = buy_orders[0]
        assert buy_1.origin_price == decimal.Decimal("97")
        assert buy_1.origin_quantity == decimal.Decimal("0.46")
        assert buy_1.side == trading_enums.TradeOrderSide.BUY
        buy_1_mirror_order = producer._create_mirror_order(buy_1.to_dict())
        assert isinstance(buy_1_mirror_order, staggered_orders_trading.OrderData)
        assert buy_1_mirror_order.associated_entry_id == buy_1.order_id
        assert buy_1_mirror_order.side == trading_enums.TradeOrderSide.SELL
        assert buy_1_mirror_order.symbol == symbol
        assert buy_1_mirror_order.price == decimal.Decimal("99") == buy_1.origin_price + buy_sell_increment
        assert buy_1_mirror_order.quantity == buy_1.origin_quantity  # NOT adapted for exchange fees
        assert buy_1_mirror_order.quantity == decimal.Decimal('0.46')

        # mirroring buy order WITHOUT enough remaining funds in portfolio to keep the same quantity:
        # => sell order adapted to available funds
        buy_1 = buy_orders[0]
        assert buy_1.origin_price == decimal.Decimal("97")
        assert buy_1.origin_quantity == decimal.Decimal("0.46")
        assert buy_1.side == trading_enums.TradeOrderSide.BUY
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio["BTC"].available = decimal.Decimal("0.3")
        buy_1_mirror_order = producer._create_mirror_order(buy_1.to_dict())
        assert isinstance(buy_1_mirror_order, staggered_orders_trading.OrderData)
        assert buy_1_mirror_order.associated_entry_id == buy_1.order_id
        assert buy_1_mirror_order.side == trading_enums.TradeOrderSide.SELL
        assert buy_1_mirror_order.symbol == symbol
        assert buy_1_mirror_order.price == decimal.Decimal("99") == buy_1.origin_price + buy_sell_increment
        assert buy_1_mirror_order.quantity < buy_1.origin_quantity  # adapted for available funds
        assert buy_1_mirror_order.quantity == decimal.Decimal('0.3')    # equals to available funds

        # => buy order adapted to available funds
        sell_1 = sell_orders[0]
        assert sell_1.origin_price == decimal.Decimal("103")
        assert sell_1.origin_quantity == decimal.Decimal('0.00464646') # cost ~= 0.04
        assert sell_1.side == trading_enums.TradeOrderSide.SELL
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio["USD"].available = decimal.Decimal("0.33")
        sell_1_mirror_order = producer._create_mirror_order(sell_1.to_dict())
        assert isinstance(sell_1_mirror_order, staggered_orders_trading.OrderData)
        assert sell_1_mirror_order.associated_entry_id is None
        assert sell_1_mirror_order.side == trading_enums.TradeOrderSide.BUY
        assert sell_1_mirror_order.symbol == symbol
        assert sell_1_mirror_order.price == decimal.Decimal("101") == sell_1.origin_price - buy_sell_increment
        assert sell_1_mirror_order.quantity < sell_1.origin_quantity
        assert sell_1_mirror_order.quantity == decimal.Decimal('0.003267326732673267326732673267')  # adapted to available USDT


async def _wait_for_orders_creation(orders_count=1):
    for _ in range(orders_count):
        await asyncio_tools.wait_asyncio_next_cycle()


async def _check_open_orders_count(exchange_manager, count):
    await _wait_for_orders_creation(count)
    assert len(trading_api.get_open_orders(exchange_manager)) == count


def _get_total_usd(exchange_manager, btc_price):
    return trading_api.get_portfolio_currency(exchange_manager, "USD", ).total \
           + trading_api.get_portfolio_currency(exchange_manager, "BTC",
                                                ).total * btc_price


async def _fill_order(order, exchange_manager, trigger_update_callback=True, producer=None):
    initial_len = len(trading_api.get_open_orders(exchange_manager))
    await order.on_fill(force_fill=True)
    if order.status == trading_enums.OrderStatus.FILLED:
        assert len(trading_api.get_open_orders(exchange_manager)) == initial_len - 1
        if trigger_update_callback:
            # Wait twice so allow `await asyncio_tools.wait_asyncio_next_cycle()` in order.initialize() to finish and complete
            # order creation AND roll the next cycle that will wake up any pending portfolio lock and allow it to
            # proceed (here `filled_order_state.terminate()` can be locked if an order has been previously filled AND
            # a mirror order is being created (and its `await asyncio_tools.wait_asyncio_next_cycle()` in order.initialize()
            # is pending: in this case `AbstractTradingModeConsumer.create_order_if_possible()` is still
            # locking the portfolio cause of the previous order's `await asyncio_tools.wait_asyncio_next_cycle()`)).
            # This lock issue can appear here because we don't use `asyncio_tools.wait_asyncio_next_cycle()` after mirror order
            # creation (unlike anywhere else in this test file).
            for _ in range(2):
                await asyncio_tools.wait_asyncio_next_cycle()
        else:
            with mock.patch.object(producer, "order_filled_callback", new=mock.AsyncMock()):
                await asyncio_tools.wait_asyncio_next_cycle()


async def _test_mode(mode, expected_buy_count, expected_sell_count, price, lowest_buy=None, highest_sell=None,
                     btc_holdings=None):
    symbol = "BTC/USD"
    async with _get_tools(symbol, btc_holdings=btc_holdings) as tools:
        producer, _, exchange_manager = tools
        if lowest_buy is not None:
            producer.lowest_buy = decimal.Decimal(str(lowest_buy))
        if highest_sell is not None:
            producer.highest_sell = decimal.Decimal(str(highest_sell))
        producer.mode = mode
        trading_api.force_set_mark_price(exchange_manager, symbol, price)
        _, _, _, _, symbol_market = await trading_personal_data.get_pre_order_data(exchange_manager,
                                                                                   symbol=symbol,
                                                                                   timeout=1)
        producer.symbol_market = symbol_market
        producer.current_price = price
        orders = await _check_generate_orders(exchange_manager, producer, expected_buy_count,
                                              expected_sell_count, price, symbol_market)

        await asyncio.create_task(_wait_for_orders_creation(len(orders)))
        open_orders = trading_api.get_open_orders(exchange_manager)
        if expected_buy_count or expected_sell_count:
            assert len(open_orders) <= producer.operational_depth
        _check_orders(open_orders, mode, producer, exchange_manager)

        assert trading_api.get_portfolio_currency(exchange_manager, "BTC").available >= trading_constants.ZERO
        assert trading_api.get_portfolio_currency(exchange_manager, "USD").available >= trading_constants.ZERO


async def _check_generate_orders(exchange_manager, producer, expected_buy_count,
                                 expected_sell_count, price, symbol_market):
    async with exchange_manager.exchange_personal_data.portfolio_manager.portfolio.lock:
        producer._refresh_symbol_data(symbol_market)
        buy_orders, sell_orders, triggering_trailing = await producer._generate_staggered_orders(decimal.Decimal(str(price)), False, False)
        assert len(buy_orders) == expected_buy_count
        assert len(sell_orders) == expected_sell_count
        assert triggering_trailing is False

        assert all(o.price < price for o in buy_orders)
        assert all(o.price > price for o in sell_orders)

        if buy_orders:
            assert not any(order for order in buy_orders if order.is_virtual)

        if sell_orders:
            assert any(order for order in sell_orders if order.is_virtual)

        buy_holdings = trading_api.get_portfolio_currency(exchange_manager, "USD").available
        assert sum(order.price * order.quantity for order in buy_orders) <= buy_holdings

        sell_holdings = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        assert sum(order.quantity for order in sell_orders) <= sell_holdings

        staggered_orders = producer._merged_and_sort_not_virtual_orders(buy_orders, sell_orders)
        if staggered_orders:
            assert not any(order for order in staggered_orders if order.is_virtual)

        await producer._create_not_virtual_orders(staggered_orders, price, triggering_trailing)

        assert all(producer.highest_sell >= o.price >= producer.lowest_buy
                   for o in sell_orders)

        assert all(producer.highest_sell >= o.price >= producer.lowest_buy
                   for o in buy_orders)
        return staggered_orders


def _check_orders(orders, strategy_mode, producer, exchange_manager):
    buy_increase_towards_center = staggered_orders_trading.StrategyModeMultipliersDetails[strategy_mode][
                                      trading_enums.TradeOrderSide.BUY] == staggered_orders_trading.INCREASING
    sell_increase_towards_center = staggered_orders_trading.StrategyModeMultipliersDetails[strategy_mode][
                                       trading_enums.TradeOrderSide.SELL] == staggered_orders_trading.INCREASING
    buy_flat_towards_center = staggered_orders_trading.StrategyModeMultipliersDetails[strategy_mode][
                                       trading_enums.TradeOrderSide.SELL] == staggered_orders_trading.STABLE
    sell_flat_towards_center = staggered_orders_trading.StrategyModeMultipliersDetails[strategy_mode][
                                       trading_enums.TradeOrderSide.SELL] == staggered_orders_trading.STABLE
    multiplier = staggered_orders_trading.StrategyModeMultipliersDetails[strategy_mode][
        staggered_orders_trading.MULTIPLIER]

    first_buy = None
    first_sell = None
    current_buy = None
    current_sell = None
    in_sell_orders = True
    for order in orders:
        # first should be sell orders followed by buy orders
        if order.side is trading_enums.TradeOrderSide.BUY:
            in_sell_orders = False
        assert order.side is (trading_enums.TradeOrderSide.SELL if in_sell_orders else trading_enums.TradeOrderSide.BUY)

        if order.side == trading_enums.TradeOrderSide.BUY:
            if current_buy is None:
                current_buy = order
                first_buy = order
            else:
                # place buy orders from the lowest price up to the current price
                assert current_buy.origin_price > order.origin_price
                if buy_increase_towards_center:
                    assert current_buy.origin_quantity * current_buy.origin_price > \
                           order.origin_quantity * order.origin_price
                elif buy_flat_towards_center:
                    assert first_buy.origin_quantity * first_buy.origin_price * decimal.Decimal("0.99")\
                           <= current_buy.origin_quantity * current_buy.origin_price \
                           <= first_buy.origin_quantity * first_buy.origin_price * decimal.Decimal("1.01")
                else:
                    assert current_buy.origin_quantity * current_buy.origin_price < \
                           order.origin_quantity * order.origin_price
                current_buy = order

        if order.side == trading_enums.TradeOrderSide.SELL:
            if current_sell is None:
                current_sell = order
                first_sell = order
            else:
                assert current_sell.origin_price < order.origin_price
                current_sell = order
                if sell_flat_towards_center:
                    assert first_sell.origin_quantity * first_sell.origin_price * decimal.Decimal("0.99")\
                           <= current_sell.origin_quantity * current_sell.origin_price \
                           <= first_sell.origin_quantity * first_sell.origin_price * decimal.Decimal("1.01")

    order_limiting_currency_amount = trading_api.get_portfolio_currency(exchange_manager, "USD").total
    decimal_current_price = decimal.Decimal(str(producer.current_price))
    _, average_order_quantity = \
        producer._get_order_count_and_average_quantity(decimal_current_price,
                                                       False,
                                                       producer.lowest_buy,
                                                       decimal_current_price,
                                                       decimal.Decimal(str(order_limiting_currency_amount)),
                                                       "USD",
                                                       strategy_mode)
    if orders:
        if buy_increase_towards_center:
            assert round(multiplier * average_order_quantity * decimal_current_price) - 1 \
                   <= round(first_buy.origin_quantity * first_buy.origin_price -
                            current_buy.origin_quantity * current_buy.origin_price) \
                   <= round(multiplier * average_order_quantity * decimal_current_price) + 1
        else:
            assert round(multiplier * average_order_quantity * decimal_current_price) - 1 \
                   <= round(current_buy.origin_quantity * current_buy.origin_price -
                            first_buy.origin_quantity * first_buy.origin_price) \
                   <= round(multiplier * average_order_quantity * decimal_current_price) + 1

        order_limiting_currency_amount = trading_api.get_portfolio_currency(exchange_manager, "BTC").total
        _, average_order_quantity = \
            producer._get_order_count_and_average_quantity(decimal_current_price,
                                                           True,
                                                           decimal_current_price,
                                                           producer.highest_sell,
                                                           decimal.Decimal(str(order_limiting_currency_amount)),
                                                           "BTC",
                                                           strategy_mode)

        if strategy_mode not in [staggered_orders_trading.StrategyModes.NEUTRAL,
                                 staggered_orders_trading.StrategyModes.VALLEY,
                                 staggered_orders_trading.StrategyModes.SELL_SLOPE]:
            # not exactly multiplier because of virtual orders and rounds
            if sell_increase_towards_center:
                expected_quantity = trading_personal_data.decimal_trunc_with_n_decimal_digits(
                    average_order_quantity * (1 + multiplier / 2),
                    8)
                assert abs(first_sell.origin_quantity - expected_quantity) < \
                       multiplier * producer.increment / (2 * decimal_current_price)
            elif not sell_flat_towards_center:
                expected_quantity = trading_personal_data.decimal_trunc_with_n_decimal_digits(
                    average_order_quantity * (1 - multiplier / 2),
                    8)
                assert abs(first_sell.origin_quantity - expected_quantity) < \
                       multiplier * producer.increment / (2 * decimal_current_price)


async def _light_check_orders(producer, exchange_manager, expected_buy_count, expected_sell_count, price):
    buy_orders, sell_orders, triggering_trailing = await producer._generate_staggered_orders(decimal.Decimal(str(price)), False, False)
    assert len(buy_orders) == expected_buy_count
    assert len(sell_orders) == expected_sell_count
    assert triggering_trailing is False

    assert all(o.price < price for o in buy_orders)
    assert all(o.price > price for o in sell_orders)

    buy_holdings = trading_api.get_portfolio_currency(exchange_manager, "ETH").available
    assert sum(order.price * order.quantity for order in buy_orders) <= buy_holdings

    sell_holdings = trading_api.get_portfolio_currency(exchange_manager, "RDN").available
    assert sum(order.quantity for order in sell_orders) <= sell_holdings

    staggered_orders = producer._merged_and_sort_not_virtual_orders(buy_orders, sell_orders)
    if staggered_orders:
        assert not any(order for order in staggered_orders if order.is_virtual)

    await producer._create_not_virtual_orders(staggered_orders, price, triggering_trailing)

    await asyncio.create_task(_wait_for_orders_creation(len(staggered_orders)))
    open_orders = trading_api.get_open_orders(exchange_manager)
    if expected_buy_count or expected_sell_count:
        assert len(open_orders) <= producer.operational_depth

    trading_mode = producer.mode
    buy_increase_towards_center = staggered_orders_trading.StrategyModeMultipliersDetails[trading_mode][
                                      trading_enums.TradeOrderSide.BUY] == staggered_orders_trading.INCREASING

    current_buy = None
    current_sell = None
    in_sell_orders = True
    for order in open_orders:
        # first should be sell orders followed by buy orders
        if order.side is trading_enums.TradeOrderSide.BUY:
            in_sell_orders = False
        assert order.side is (trading_enums.TradeOrderSide.SELL if in_sell_orders else trading_enums.TradeOrderSide.BUY)

        if order.side == trading_enums.TradeOrderSide.BUY:
            if current_buy is None:
                current_buy = order
            else:
                # place buy orders from the current price down to the lowest price
                assert current_buy.origin_price > order.origin_price
                if buy_increase_towards_center:
                    assert current_buy.origin_quantity * current_buy.origin_price > \
                           order.origin_quantity * order.origin_price
                else:
                    assert current_buy.origin_quantity * current_buy.origin_price < \
                           order.origin_quantity * order.origin_price
                current_buy = order

        if order.side == trading_enums.TradeOrderSide.SELL:
            if current_sell is None:
                current_sell = order
            else:
                assert current_sell.origin_price < order.origin_price
                current_sell = order

    assert trading_api.get_portfolio_currency(exchange_manager, "ETH").available >= 0
    assert trading_api.get_portfolio_currency(exchange_manager, "RDN").available >= 0


def _get_multi_symbol_staggered_config():
    return {
        "required_strategies": [],
        "pair_settings": [
            {
                "pair": "BTC/USD",
                "mode": "mountain",
                "spread_percent": 4,
                "increment_percent": 3,
                "lower_bound": 4300,
                "upper_bound": 5500,
                "allow_instant_fill": True,
                "operational_depth": 100
            },
            {
                "pair": "ETH/USDT",
                "mode": "mountain",
                "spread_percent": 4,
                "increment_percent": 3,
                "lower_bound": 4300,
                "upper_bound": 5500,
                "allow_instant_fill": True,
                "operational_depth": 100
            },
            {
                "pair": "NANO/USDT",
                "mode": "mountain",
                "spread_percent": 4,
                "increment_percent": 3,
                "lower_bound": 4300,
                "upper_bound": 5500,
                "allow_instant_fill": True,
                "operational_depth": 100
            }
        ]
    }
