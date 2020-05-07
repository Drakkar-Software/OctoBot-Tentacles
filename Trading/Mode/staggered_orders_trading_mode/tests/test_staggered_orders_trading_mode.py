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
import time
import copy
from asyncio import create_task
from os.path import join

from octobot_backtesting.api.backtesting import initialize_backtesting, get_importers
from octobot_backtesting.api.importer import stop_importer
from octobot_channels.util.channel_creator import create_all_subclasses_channel
from octobot_commons.constants import PORTFOLIO_TOTAL, PORTFOLIO_AVAILABLE, CONFIG_TIME_FRAME
from octobot_commons.tests.test_config import load_test_config, TEST_CONFIG_FOLDER
from octobot_tentacles_manager.api.configurator import create_tentacles_setup_config_with_tentacles
from octobot_trading.api.orders import get_open_orders
from octobot_trading.api.portfolio import get_portfolio_currency
from octobot_trading.api.symbol_data import force_set_mark_price
from octobot_trading.channels.exchange_channel import ExchangeChannel, TimeFrameExchangeChannel, set_chan
from octobot_trading.constants import CONFIG_SIMULATOR, CONFIG_STARTING_PORTFOLIO, CONFIG_SIMULATOR_FEES_TAKER, \
    CONFIG_SIMULATOR_FEES, CONFIG_SIMULATOR_FEES_MAKER
from octobot_trading.enums import TradeOrderSide, EvaluatorStates, OrderStatus
from octobot_trading.exchanges.exchange_manager import ExchangeManager
from octobot_trading.exchanges.exchange_simulator import ExchangeSimulator
from octobot_trading.exchanges.rest_exchange import RestExchange
from octobot_trading.orders.order_adapter import trunc_with_n_decimal_digits
from octobot_trading.orders.order_util import get_pre_order_data
from octobot_trading.traders.trader_simulator import TraderSimulator
from tentacles.Trading.Mode.staggered_orders_trading_mode.staggered_orders_trading_mode \
    import StaggeredOrdersTradingMode, StrategyModes, StrategyModeMultipliersDetails, \
    MULTIPLIER, INCREASING, OrderData, StaggeredOrdersTradingModeProducer

# All test coroutines will be treated as marked.
from tests.test_utils.memory_check_util import run_independent_backtestings_with_memory_check

pytestmark = pytest.mark.asyncio


async def _init_trading_mode(config, exchange_manager, symbol):
    StaggeredOrdersTradingModeProducer.SCHEDULE_ORDERS_CREATION_ON_START = False
    mode = StaggeredOrdersTradingMode(config, exchange_manager)
    mode.symbol = None if mode.get_is_symbol_wildcard() else symbol
    mode.trading_config = _get_multi_symbol_staggered_config()
    await mode.initialize()
    mode.producers[0].PRICE_FETCHING_TIMEOUT = 0.5
    return mode, mode.producers[0]


async def _get_tools(symbol, btc_holdings=None, additional_portfolio={}, fees=None):
    config = load_test_config()
    config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO]["USD"] = 1000
    config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO]["BTC"] = 10 if btc_holdings is None else btc_holdings
    config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO].update(additional_portfolio)
    if fees is not None:
        config[CONFIG_SIMULATOR][CONFIG_SIMULATOR_FEES][CONFIG_SIMULATOR_FEES_TAKER] = fees
        config[CONFIG_SIMULATOR][CONFIG_SIMULATOR_FEES][CONFIG_SIMULATOR_FEES_MAKER] = fees
    exchange_manager = ExchangeManager(config, "binance")

    # use backtesting not to spam exchanges apis
    exchange_manager.is_simulated = True
    exchange_manager.is_backtesting = True
    backtesting = await initialize_backtesting(
        config,
        exchange_ids=[exchange_manager.id],
        matrix_id=None,
        data_files=[join(TEST_CONFIG_FOLDER, "AbstractExchangeHistoryCollector_1586017993.616272.data")])
    exchange_manager.exchange_type = RestExchange.create_exchange_type(exchange_manager.exchange_class_string)
    exchange_manager.exchange = ExchangeSimulator(exchange_manager.config,
                                                  exchange_manager.exchange_type,
                                                  exchange_manager,
                                                  backtesting)
    await exchange_manager.exchange.initialize()
    for exchange_channel_class_type in [ExchangeChannel, TimeFrameExchangeChannel]:
        await create_all_subclasses_channel(exchange_channel_class_type, set_chan, exchange_manager=exchange_manager)

    trader = TraderSimulator(config, exchange_manager)
    await trader.initialize()

    # set BTC/USDT price at 1000 USDT
    force_set_mark_price(exchange_manager, symbol, 1000)

    mode, producer = await _init_trading_mode(config, exchange_manager, symbol)

    producer.lowest_buy = 1
    producer.highest_sell = 10000
    producer.operational_depth = 50
    producer.spread = 0.06
    producer.increment = 0.04

    return producer, mode.consumers[0], exchange_manager


async def _get_tools_multi_symbol():
    config = load_test_config()
    config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO]["USD"] = 1000
    config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO]["USDT"] = 2000
    config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO]["BTC"] = 10
    config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO]["ETH"] = 20
    config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO]["NANO"] = 2000
    exchange_manager = ExchangeManager(config, "binance")

    # use backtesting not to spam exchanges apis
    exchange_manager.is_simulated = True
    exchange_manager.is_backtesting = True
    backtesting = await initialize_backtesting(
        config,
        exchange_ids=[exchange_manager.id],
        matrix_id=None,
        data_files=[join(TEST_CONFIG_FOLDER, "AbstractExchangeHistoryCollector_1586017993.616272.data")])
    exchange_manager.exchange_type = RestExchange.create_exchange_type(exchange_manager.exchange_class_string)
    exchange_manager.exchange = ExchangeSimulator(exchange_manager.config,
                                                  exchange_manager.exchange_type,
                                                  exchange_manager,
                                                  backtesting)
    await exchange_manager.exchange.initialize()
    for exchange_channel_class_type in [ExchangeChannel, TimeFrameExchangeChannel]:
        await create_all_subclasses_channel(exchange_channel_class_type, set_chan, exchange_manager=exchange_manager)

    trader = TraderSimulator(config, exchange_manager)
    await trader.initialize()

    btc_usd_mode, btcusd_producer = await _init_trading_mode(config, exchange_manager, "BTC/USD")
    eth_usdt_mode, eth_usdt_producer = await _init_trading_mode(config, exchange_manager, "ETH/USDT")
    nano_usdt_mode, nano_usdt_producer = await _init_trading_mode(config, exchange_manager, "NANO/USDT")

    btcusd_producer.lowest_buy = 1
    btcusd_producer.highest_sell = 10000
    btcusd_producer.operational_depth = 50
    btcusd_producer.spread = 0.06
    btcusd_producer.increment = 0.04

    eth_usdt_producer.lowest_buy = 20
    eth_usdt_producer.highest_sell = 5000
    eth_usdt_producer.operational_depth = 30
    eth_usdt_producer.spread = 0.07
    eth_usdt_producer.increment = 0.03

    nano_usdt_producer.lowest_buy = 20
    nano_usdt_producer.highest_sell = 5000
    nano_usdt_producer.operational_depth = 30
    nano_usdt_producer.spread = 0.07
    nano_usdt_producer.increment = 0.03

    return btcusd_producer, eth_usdt_producer, nano_usdt_producer, exchange_manager


async def _stop(exchange_manager):
    for importer in get_importers(exchange_manager.exchange.backtesting):
        await stop_importer(importer)
    await exchange_manager.stop()


async def test_run_independent_backtestings_with_memory_check():
    """
    Should always be called first here to avoid other tests' related memory check issues
    """
    tentacles_setup_config = create_tentacles_setup_config_with_tentacles(
        StaggeredOrdersTradingMode
    )
    config = load_test_config()
    config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO]["USDT"] = 10000
    config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO]["ETH"] = 20
    await run_independent_backtestings_with_memory_check(config, tentacles_setup_config)


async def test_ensure_staggered_orders():
    try:
        symbol = "BTC/USD"
        producer, _, exchange_manager = await _get_tools(symbol)
        assert producer.state == EvaluatorStates.NEUTRAL
        assert producer.current_price is None
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(exchange_manager, 0))

        # set BTC/USD price at 4000 USD
        force_set_mark_price(exchange_manager, symbol, 4000)
        await producer._ensure_staggered_orders()
        # price info: create trades
        assert producer.current_price == 4000
        assert producer.state == EvaluatorStates.NEUTRAL
        await create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
    finally:
        await _stop(exchange_manager)


async def test_multi_symbol():
    try:
        btcusd_producer, eth_usdt_producer, nano_usdt_producer, exchange_manager = await _get_tools_multi_symbol()

        force_set_mark_price(exchange_manager, btcusd_producer.symbol, 100)
        await btcusd_producer._ensure_staggered_orders()
        await create_task(_check_open_orders_count(exchange_manager, btcusd_producer.operational_depth))
        orders = get_open_orders(exchange_manager)
        assert len(orders) == btcusd_producer.operational_depth
        assert len([o for o in orders if o.side == TradeOrderSide.SELL]) == 25
        assert len([o for o in orders if o.side == TradeOrderSide.BUY]) == 25

        force_set_mark_price(exchange_manager, eth_usdt_producer.symbol, 200)
        await eth_usdt_producer._ensure_staggered_orders()
        await create_task(_check_open_orders_count(exchange_manager, btcusd_producer.operational_depth +
                                                   eth_usdt_producer.operational_depth))
        orders = get_open_orders(exchange_manager)
        assert len([o for o in orders if o.side == TradeOrderSide.SELL]) == 40
        assert len([o for o in orders if o.side == TradeOrderSide.BUY]) == 40

        force_set_mark_price(exchange_manager, nano_usdt_producer.symbol, 200)
        await nano_usdt_producer._ensure_staggered_orders()
        # no new order
        await create_task(_check_open_orders_count(exchange_manager, btcusd_producer.operational_depth +
                                                   eth_usdt_producer.operational_depth))
        orders = get_open_orders(exchange_manager)
        assert len([o for o in orders if o.side == TradeOrderSide.SELL]) == 40
        assert len([o for o in orders if o.side == TradeOrderSide.BUY]) == 40

        assert nano_usdt_producer._get_interfering_orders_pairs(orders) == {"ETH/USDT"}

        # new ETH USDT evaluation, price changed
        # -2 order would be filled
        original_orders = copy.copy(orders)
        to_fill_order = original_orders[-2]
        await _fill_order(to_fill_order, exchange_manager, 190, trading_mode=eth_usdt_producer.trading_mode)
        force_set_mark_price(exchange_manager, eth_usdt_producer.symbol, 190)
        await nano_usdt_producer._ensure_staggered_orders()
        # did nothing
        await create_task(_check_open_orders_count(exchange_manager, len(original_orders)))
    finally:
        await _stop(exchange_manager)


async def test_create_orders_without_existing_orders_symmetrical_case_all_modes_price_100():
    price = 100
    await _test_mode(StrategyModes.NEUTRAL, 25, 2475, price)
    await _test_mode(StrategyModes.MOUNTAIN, 25, 2475, price)
    await _test_mode(StrategyModes.VALLEY, 25, 2475, price)
    await _test_mode(StrategyModes.BUY_SLOPE, 25, 2475, price)
    await _test_mode(StrategyModes.SELL_SLOPE, 25, 2475, price)


async def test_create_orders_without_existing_orders_symmetrical_case_all_modes_price_347():
    price = 347
    await _test_mode(StrategyModes.NEUTRAL, 25, 695, price)
    await _test_mode(StrategyModes.MOUNTAIN, 25, 695, price)
    await _test_mode(StrategyModes.VALLEY, 25, 695, price)
    await _test_mode(StrategyModes.BUY_SLOPE, 25, 695, price)
    await _test_mode(StrategyModes.SELL_SLOPE, 25, 695, price)


async def test_create_orders_without_existing_orders_symmetrical_case_all_modes_price_0_347():
    price = 0.347
    # await _test_mode(StrategyModes.NEUTRAL, 0, 0, price)
    lowest_buy = 0.001
    highest_sell = 400
    btc_holdings = 400
    await _test_mode(StrategyModes.NEUTRAL, 25, 28793, price, lowest_buy, highest_sell, btc_holdings)
    await _test_mode(StrategyModes.MOUNTAIN, 25, 28793, price, lowest_buy, highest_sell, btc_holdings)
    await _test_mode(StrategyModes.VALLEY, 25, 28793, price, lowest_buy, highest_sell, btc_holdings)
    await _test_mode(StrategyModes.BUY_SLOPE, 25, 28793, price, lowest_buy, highest_sell, btc_holdings)
    await _test_mode(StrategyModes.SELL_SLOPE, 25, 28793, price, lowest_buy, highest_sell, btc_holdings)


async def test_create_orders_from_different_markets():
    try:
        producer, _, exchange_manager = await _get_tools("BTC/USD", additional_portfolio={"RDN": 6740, "ETH": 10})
        producer.symbol = "RDN/ETH"

        price = 0.0024161
        force_set_mark_price(exchange_manager, producer.symbol, price)
        _, _, _, _, symbol_market = await get_pre_order_data(exchange_manager,
                                                             symbol=producer.symbol,
                                                             timeout=1)
        producer.symbol_market = symbol_market
        producer.current_price = price
        producer._refresh_symbol_data(symbol_market)
        producer.min_max_order_details[producer.min_cost] = 0.01
        producer.min_max_order_details[producer.min_quantity] = 1.0
        producer.min_max_order_details[producer.max_quantity] = 90000000.0
        producer.min_max_order_details[producer.max_cost] = None
        producer.min_max_order_details[producer.max_price] = None
        producer.min_max_order_details[producer.min_price] = None

        # await _test_mode(StrategyModes.NEUTRAL, 0, 0, price)
        lowest_buy = 0.0013
        highest_sell = 0.0043
        expected_buy_count = 46
        expected_sell_count = 78

        producer.lowest_buy = lowest_buy
        producer.highest_sell = highest_sell
        producer.increment = 0.01
        producer.spread = 0.01
        producer.operational_depth = 10
        producer.final_eval = price
        producer.mode = StrategyModes.MOUNTAIN

        await _light_check_orders(producer, exchange_manager, expected_buy_count, expected_sell_count, price)

        original_orders = copy.copy(get_open_orders(exchange_manager))
        assert len(original_orders) == producer.operational_depth

        # test trigger refresh
        force_set_mark_price(exchange_manager, producer.symbol, 0.0024161)
        await producer._ensure_staggered_orders()
        await create_task(_wait_for_orders_creation())
        # did nothing
        assert original_orders[0] is get_open_orders(exchange_manager)[0]
        assert original_orders[-1] is get_open_orders(exchange_manager)[-1]
        assert len(get_open_orders(exchange_manager)) == producer.operational_depth
    finally:
        await _stop(exchange_manager)


async def test_create_orders_from_different_very_close_refresh():
    try:
        producer, _, exchange_manager = await _get_tools("BTC/USD", additional_portfolio={"RDN": 6740, "ETH": 10})
        producer.symbol = "RDN/ETH"
        price = 0.00231
        force_set_mark_price(exchange_manager, producer.symbol, price)
        _, _, _, _, symbol_market = await get_pre_order_data(exchange_manager,
                                                             symbol=producer.symbol,
                                                             timeout=1)
        producer.symbol_market = symbol_market
        producer.current_price = price
        producer._refresh_symbol_data(symbol_market)
        producer.min_max_order_details[producer.min_cost] = 0.01
        producer.min_max_order_details[producer.min_quantity] = 1.0
        producer.min_max_order_details[producer.max_quantity] = 90000000.0
        producer.min_max_order_details[producer.max_cost] = None
        producer.min_max_order_details[producer.max_price] = None
        producer.min_max_order_details[producer.min_price] = None

        # await _test_mode(StrategyModes.NEUTRAL, 0, 0, price)
        lowest_buy = 0.00221
        highest_sell = 0.00242
        expected_buy_count = 2
        expected_sell_count = 2

        producer.lowest_buy = lowest_buy
        producer.highest_sell = highest_sell
        producer.increment = 0.02
        producer.spread = 0.02
        producer.operational_depth = 10
        producer.final_eval = price
        producer.mode = StrategyModes.MOUNTAIN

        await _light_check_orders(producer, exchange_manager, expected_buy_count, expected_sell_count, price)

        original_orders = copy.copy(get_open_orders(exchange_manager))
        original_length = len(original_orders)

        # test trigger refresh
        force_set_mark_price(exchange_manager, producer.symbol, 0.0023185)
        await producer._ensure_staggered_orders()
        await create_task(_wait_for_orders_creation())
        # did nothing
        assert original_orders[0] is get_open_orders(exchange_manager)[0]
        assert original_orders[-1] is get_open_orders(exchange_manager)[-1]
        assert original_length == len(get_open_orders(exchange_manager))

        # test more trigger refresh
        force_set_mark_price(exchange_manager, producer.symbol, 0.0022991)
        await producer._ensure_staggered_orders()
        await create_task(_wait_for_orders_creation())
        # did nothing
        assert original_orders[0] is get_open_orders(exchange_manager)[0]
        assert original_orders[-1] is get_open_orders(exchange_manager)[-1]
        assert original_length == len(get_open_orders(exchange_manager))
    finally:
        await _stop(exchange_manager)


async def test_create_orders_from_different_markets_not_enough_market_to_create_all_orders():
    try:
        producer, _, exchange_manager = await _get_tools("BTC/USD", additional_portfolio={"RDN": 6740, "ETH": 10})
        producer.symbol = "RDN/ETH"
        price = 0.0024161
        force_set_mark_price(exchange_manager, producer.symbol, price)
        _, _, _, _, symbol_market = await get_pre_order_data(exchange_manager,
                                                             symbol=producer.symbol,
                                                             timeout=1)
        producer.symbol_market = symbol_market
        producer.current_price = price
        producer._refresh_symbol_data(symbol_market)
        producer.min_max_order_details[producer.min_cost] = 1.0
        producer.min_max_order_details[producer.min_quantity] = 1.0
        producer.min_max_order_details[producer.max_quantity] = 90000000.0
        producer.min_max_order_details[producer.max_cost] = None
        producer.min_max_order_details[producer.max_price] = None
        producer.min_max_order_details[producer.min_price] = None

        # await _test_mode(StrategyModes.NEUTRAL, 0, 0, price)
        lowest_buy = 0.0013
        highest_sell = 0.0043
        expected_buy_count = 0
        expected_sell_count = 0

        producer.lowest_buy = lowest_buy
        producer.highest_sell = highest_sell
        producer.increment = 0.01
        producer.spread = 0.01
        producer.operational_depth = 10
        producer.final_eval = price
        producer.mode = StrategyModes.MOUNTAIN

        await _light_check_orders(producer, exchange_manager, expected_buy_count, expected_sell_count, price)
    finally:
        await _stop(exchange_manager)


async def test_start_with_existing_valid_orders():
    try:
        producer, _, exchange_manager = await _get_tools("BTC/USD")
        price = 100
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
        original_orders = copy.copy(get_open_orders(exchange_manager))
        assert len(original_orders) == producer.operational_depth

        # new evaluation, same price
        price = 100
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        # did nothing
        await create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
        assert original_orders[0] is get_open_orders(exchange_manager)[0]
        assert original_orders[-1] is get_open_orders(exchange_manager)[-1]
        assert len(get_open_orders(exchange_manager)) == producer.operational_depth

        # new evaluation, price changed
        # -2 order would be filled
        to_fill_order = original_orders[-2]
        price = 95
        await _fill_order(to_fill_order, exchange_manager, price, trading_mode=producer.trading_mode)
        await create_task(_wait_for_orders_creation())
        # did nothing: orders got replaced
        assert len(original_orders) == len(get_open_orders(exchange_manager))
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        # did nothing
        assert len(original_orders) == len(get_open_orders(exchange_manager))

        # a orders gets cancelled
        open_orders = get_open_orders(exchange_manager)
        to_cancel = [open_orders[20], open_orders[19], open_orders[40]]
        for order in to_cancel:
            await exchange_manager.trader.cancel_order(order)
        post_available = get_portfolio_currency(exchange_manager, "USD")
        assert len(get_open_orders(exchange_manager)) == producer.operational_depth - len(to_cancel)

        producer.RECENT_TRADES_ALLOWED_TIME = 0
        await producer._ensure_staggered_orders()
        await create_task(_wait_for_orders_creation())
        # restored orders
        assert len(get_open_orders(exchange_manager)) == producer.operational_depth
        assert 0 <= get_portfolio_currency(exchange_manager, "USD") <= post_available
        assert 0 <= get_portfolio_currency(exchange_manager, "BTC")
    finally:
        await _stop(exchange_manager)


async def test_price_initially_out_of_range_1():
    try:
        producer, _, exchange_manager = await _get_tools("BTC/USD", btc_holdings=100000000)
        # new evaluation: price in range
        price = 0.1
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await create_task(_wait_for_orders_creation())
        original_orders = copy.copy(get_open_orders(exchange_manager))
        assert len(original_orders) == producer.operational_depth
        assert all(o.side == TradeOrderSide.SELL for o in original_orders)
        assert all(producer.highest_sell >= o.origin_price >= producer.lowest_buy
                   for o in original_orders)
    finally:
        await _stop(exchange_manager)


async def test_price_initially_out_of_range_2():
    try:
        producer, _, exchange_manager = await _get_tools("BTC/USD", btc_holdings=10000000)
        # new evaluation: price in range
        price = 100000
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await create_task(_wait_for_orders_creation())
        original_orders = copy.copy(get_open_orders(exchange_manager))
        assert len(original_orders) == 2
        assert all(o.side == TradeOrderSide.BUY for o in original_orders)
        assert all(producer.highest_sell >= o.origin_price >= producer.lowest_buy
                   for o in original_orders)
    finally:
        await _stop(exchange_manager)


async def test_price_going_out_of_range():
    try:
        producer, _, exchange_manager = await _get_tools("BTC/USD")
        # new evaluation: price in range
        price = 100
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))

        # new evaluation: price out of range: >
        price = 100000
        force_set_mark_price(exchange_manager, producer.symbol, price)
        producer.current_price = price
        existing_orders = get_open_orders(exchange_manager)
        sorted_orders = sorted(existing_orders, key=lambda order: order.origin_price)
        missing_orders, state, candidate_flat_increment = producer._analyse_current_orders_situation(sorted_orders, [])
        assert missing_orders is None
        assert candidate_flat_increment is None
        assert state == producer.ERROR

        # new evaluation: price out of range: <
        price = 0.1
        force_set_mark_price(exchange_manager, producer.symbol, price)
        producer.current_price = price
        existing_orders = get_open_orders(exchange_manager)
        sorted_orders = sorted(existing_orders, key=lambda order: order.origin_price)
        missing_orders, state, candidate_flat_increment = producer._analyse_current_orders_situation(sorted_orders, [])
        assert missing_orders is None
        assert candidate_flat_increment is None
        assert state == producer.ERROR
    finally:
        await _stop(exchange_manager)


async def test_start_after_offline_filled_orders():
    try:
        # first start: setup orders
        producer, _, exchange_manager = await _get_tools("BTC/USD")
        price = 100
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await create_task(_wait_for_orders_creation())
        original_orders = copy.copy(get_open_orders(exchange_manager))
        assert len(original_orders) == producer.operational_depth
        pre_portfolio = get_portfolio_currency(exchange_manager, "USD")

        # offline simulation: orders get filled but not replaced => price got up to 110 and not down to 90, now is 96s
        open_orders = get_open_orders(exchange_manager)
        offline_filled = [o for o in open_orders if 90 <= o.origin_price <= 110]
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False)
        post_portfolio = get_portfolio_currency(exchange_manager, "USD")
        assert pre_portfolio < post_portfolio
        assert len(get_open_orders(exchange_manager)) == producer.operational_depth - len(offline_filled)

        # back online: restore orders according to current price
        price = 96
        force_set_mark_price(exchange_manager, producer.symbol, price)
        # force not use recent trades
        producer.RECENT_TRADES_ALLOWED_TIME = 0
        await producer._ensure_staggered_orders()
        # restored orders
        await create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
        assert 0 <= get_portfolio_currency(exchange_manager, "USD") <= post_portfolio
        assert 0 <= get_portfolio_currency(exchange_manager, "BTC")
    finally:
        await _stop(exchange_manager)


async def test_health_check_during_filled_orders():
    try:
        # first start: setup orders
        producer, _, exchange_manager = await _get_tools("BTC/USD")
        price = 100
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await create_task(_check_open_orders_count(exchange_manager, producer.operational_depth))
        pre_portfolio = get_portfolio_currency(exchange_manager, "USD")

        # offline simulation: orders get filled but not replaced => price got up to 110 and not down to 90, now is 96s
        open_orders = get_open_orders(exchange_manager)
        offline_filled = [o for o in open_orders if 90 <= o.origin_price <= 110]
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False)
        post_portfolio = get_portfolio_currency(exchange_manager, "USD")
        assert pre_portfolio < post_portfolio
        assert len(get_open_orders(exchange_manager)) == producer.operational_depth - len(offline_filled)

        # back online: restore orders according to current price
        price = 96
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        # did not restore orders: they are being closed and callback will proceed (considered as recently closed
        # and consumer in queue)
        await create_task(_check_open_orders_count(exchange_manager, producer.operational_depth - len(offline_filled)))
        assert 0 <= get_portfolio_currency(exchange_manager, "USD") <= post_portfolio
        assert 0 <= get_portfolio_currency(exchange_manager, "BTC")
    finally:
        await _stop(exchange_manager)


async def test_compute_minimum_funds_1():
    try:
        # first start: setup orders
        producer, _, exchange_manager = await _get_tools("BTC/USD")
        buy_min_funds = producer._get_min_funds(25, 0.001, StrategyModes.MOUNTAIN, 100)
        sell_min_funds = producer._get_min_funds(2475.25, 0.00001, StrategyModes.MOUNTAIN, 100)
        assert buy_min_funds == 0.05
        assert sell_min_funds == 0.04950500000000001
        portfolio = exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio
        portfolio["USD"][PORTFOLIO_AVAILABLE] = buy_min_funds
        portfolio["USD"][PORTFOLIO_TOTAL] = buy_min_funds
        portfolio["BTC"][PORTFOLIO_AVAILABLE] = sell_min_funds
        portfolio["BTC"][PORTFOLIO_TOTAL] = sell_min_funds
        price = 100
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await create_task(_wait_for_orders_creation())
        orders = get_open_orders(exchange_manager)
        assert len(orders) == producer.operational_depth
        assert len([o for o in orders if o.side == TradeOrderSide.SELL]) == 26
        assert len([o for o in orders if o.side == TradeOrderSide.BUY]) == 24
    finally:
        await _stop(exchange_manager)


async def test_compute_minimum_funds_2():
    try:
        # first start: setup orders
        producer, _, exchange_manager = await _get_tools("BTC/USD")
        _, _, _, _, symbol_market = await get_pre_order_data(exchange_manager,
                                                             symbol=producer.symbol,
                                                             timeout=1)
        producer._refresh_symbol_data(symbol_market)
        buy_min_funds = producer._get_min_funds(25, 0.001, StrategyModes.MOUNTAIN, 100)
        sell_min_funds = producer._get_min_funds(2475, 0.00001, StrategyModes.MOUNTAIN, 100)
        assert buy_min_funds == 0.05
        assert sell_min_funds == 0.0495
        portfolio = exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio
        portfolio["USD"][PORTFOLIO_AVAILABLE] = buy_min_funds*0.99999
        portfolio["USD"][PORTFOLIO_TOTAL] = buy_min_funds*0.99999
        portfolio["BTC"][PORTFOLIO_AVAILABLE] = sell_min_funds*0.99999
        portfolio["BTC"][PORTFOLIO_TOTAL] = sell_min_funds*0.99999
        price = 100
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await create_task(_check_open_orders_count(exchange_manager, 0))
    finally:
        await _stop(exchange_manager)


async def test_start_without_enough_funds_to_buy():
    try:
        producer, _, exchange_manager = await _get_tools("BTC/USD")
        portfolio = exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio
        portfolio["USD"][PORTFOLIO_AVAILABLE] = 0.00005
        portfolio["USD"][PORTFOLIO_TOTAL] = 0.00005
        price = 100
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await create_task(_wait_for_orders_creation())
        orders = get_open_orders(exchange_manager)
        assert len(orders) == producer.operational_depth
        assert all([o.side == TradeOrderSide.SELL for o in orders])

        # trigger health check
        await producer._ensure_staggered_orders()
        await create_task(_wait_for_orders_creation())

        await _fill_order(orders[5], exchange_manager, trading_mode=producer.trading_mode)
    finally:
        await _stop(exchange_manager)


async def test_start_without_enough_funds_to_sell():
    try:
        producer, _, exchange_manager = await _get_tools("BTC/USD", btc_holdings=0.00001)
        price = 100
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await create_task(_wait_for_orders_creation())
        orders = get_open_orders(exchange_manager)
        assert len(orders) == 25
        assert all([o.side == TradeOrderSide.BUY for o in orders])

        # trigger health check
        await producer._ensure_staggered_orders()
        await create_task(_wait_for_orders_creation())
        orders = get_open_orders(exchange_manager)

        # check order fill callback recreates spread
        to_fill_order = orders[5]
        second_to_fill_order = orders[4]
        await _fill_order(to_fill_order, exchange_manager, trading_mode=producer.trading_mode)
        await create_task(_wait_for_orders_creation())
        orders = get_open_orders(exchange_manager)
        newly_created_sell_order = orders[-1]
        assert newly_created_sell_order.side == TradeOrderSide.SELL
        assert newly_created_sell_order.origin_price == to_fill_order.origin_price + \
            (producer.flat_spread - producer.flat_increment)

        await _fill_order(second_to_fill_order, exchange_manager, trading_mode=producer.trading_mode)
        await create_task(_wait_for_orders_creation())
        orders = get_open_orders(exchange_manager)
        second_newly_created_sell_order = orders[-1]
        assert second_newly_created_sell_order.side == TradeOrderSide.SELL
        assert second_newly_created_sell_order.origin_price == second_to_fill_order.origin_price + \
            (producer.flat_spread - producer.flat_increment)
        assert abs(second_newly_created_sell_order.origin_price - newly_created_sell_order.origin_price) == \
            producer.flat_increment
    finally:
        await _stop(exchange_manager)


async def test_start_without_enough_funds_at_all():
    try:
        producer, _, exchange_manager = await _get_tools("BTC/USD", btc_holdings=0.00001)
        portfolio = exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio
        portfolio["USD"][PORTFOLIO_AVAILABLE] = 0.00005
        portfolio["USD"][PORTFOLIO_TOTAL] = 0.00005
        price = 100
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await create_task(_check_open_orders_count(exchange_manager, 0))
    finally:
        await _stop(exchange_manager)


async def test_settings_for_just_one_order_on_a_side():
    try:
        producer, _, exchange_manager = await _get_tools("BTC/USD")
        producer.highest_sell = 106
        price = 100
        force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await create_task(_wait_for_orders_creation())
        orders = get_open_orders(exchange_manager)
        assert len([o for o in orders if o.side == TradeOrderSide.SELL]) == 1
    finally:
        await _stop(exchange_manager)


async def test_order_fill_callback():
    try:
        producer, _, exchange_manager = await _get_tools("BTC/USD", fees=0)
        # create orders
        price = 100
        producer.mode = StrategyModes.NEUTRAL
        force_set_mark_price(exchange_manager, producer.symbol, price)
        previous_total = _get_total_usd(exchange_manager, 100)

        now_btc = get_portfolio_currency(exchange_manager, "BTC", portfolio_type=PORTFOLIO_TOTAL)
        now_usd = get_portfolio_currency(exchange_manager, "USD", portfolio_type=PORTFOLIO_TOTAL)

        await producer._ensure_staggered_orders()
        await create_task(_wait_for_orders_creation())
        price_increment = producer.flat_increment
        price_spread = producer.flat_spread

        open_orders = get_open_orders(exchange_manager)
        assert len(open_orders) == producer.operational_depth

        # closest to centre buy order is filled => bought btc
        to_fill_order = open_orders[-2]
        await _fill_order(to_fill_order, exchange_manager, trading_mode=producer.trading_mode)
        await create_task(_wait_for_orders_creation())
        open_orders = get_open_orders(exchange_manager)

        # instantly create sell order at price * (1 + increment)
        assert len(open_orders) == producer.operational_depth
        assert to_fill_order not in open_orders
        newly_created_sell_order = open_orders[-1]
        assert newly_created_sell_order.symbol == to_fill_order.symbol
        price = to_fill_order.origin_price + (price_spread - price_increment)
        assert newly_created_sell_order.origin_price == trunc_with_n_decimal_digits(price, 8)
        assert newly_created_sell_order.origin_quantity == \
            trunc_with_n_decimal_digits(
                to_fill_order.filled_quantity * (1 - producer.max_fees),
                8)
        assert newly_created_sell_order.side == TradeOrderSide.SELL
        assert get_portfolio_currency(exchange_manager, "BTC", portfolio_type=PORTFOLIO_TOTAL) > now_btc
        now_btc = get_portfolio_currency(exchange_manager, "BTC", portfolio_type=PORTFOLIO_TOTAL)
        current_total = _get_total_usd(exchange_manager, 100)
        assert previous_total < current_total
        previous_total_buy = current_total

        # now this new sell order is filled => sold btc
        to_fill_order = open_orders[-1]
        await _fill_order(to_fill_order, exchange_manager, trading_mode=producer.trading_mode)
        await create_task(_wait_for_orders_creation())
        open_orders = get_open_orders(exchange_manager)

        # instantly create buy order at price * (1 + increment)
        assert len(open_orders) == producer.operational_depth
        assert to_fill_order not in open_orders
        newly_created_buy_order = open_orders[-1]
        assert newly_created_buy_order.symbol == to_fill_order.symbol
        price = to_fill_order.origin_price - (price_spread - price_increment)
        assert newly_created_buy_order.origin_price == trunc_with_n_decimal_digits(price, 8)
        assert newly_created_buy_order.origin_quantity == \
            trunc_with_n_decimal_digits(
                to_fill_order.filled_price / price * to_fill_order.filled_quantity * (1 - producer.max_fees),
                8)
        assert newly_created_buy_order.side == TradeOrderSide.BUY
        assert get_portfolio_currency(exchange_manager, "USD", portfolio_type=PORTFOLIO_TOTAL) > now_usd
        now_usd = get_portfolio_currency(exchange_manager, "USD", portfolio_type=PORTFOLIO_TOTAL)
        current_total = _get_total_usd(exchange_manager, 100)
        assert previous_total < current_total
        previous_total_sell = current_total

        # now this new buy order is filled => bought btc
        to_fill_order = open_orders[-1]
        await _fill_order(to_fill_order, exchange_manager, trading_mode=producer.trading_mode)
        await create_task(_wait_for_orders_creation())
        open_orders = get_open_orders(exchange_manager)

        # instantly create sell order at price * (1 + increment)
        assert len(open_orders) == producer.operational_depth
        assert to_fill_order not in open_orders
        newly_created_sell_order = open_orders[-1]
        assert newly_created_sell_order.symbol == to_fill_order.symbol
        price = to_fill_order.origin_price + (price_spread - price_increment)
        assert newly_created_sell_order.origin_price == trunc_with_n_decimal_digits(price, 8)
        assert newly_created_sell_order.origin_quantity == \
            trunc_with_n_decimal_digits(
                to_fill_order.filled_quantity * (1 - producer.max_fees),
                8)
        assert newly_created_sell_order.side == TradeOrderSide.SELL
        assert get_portfolio_currency(exchange_manager, "BTC", portfolio_type=PORTFOLIO_TOTAL) > now_btc
        current_total = _get_total_usd(exchange_manager, 100)
        assert previous_total_buy < current_total

        # now this new sell order is filled => sold btc
        to_fill_order = open_orders[-1]
        await _fill_order(to_fill_order, exchange_manager, trading_mode=producer.trading_mode)
        await create_task(_wait_for_orders_creation())
        open_orders = get_open_orders(exchange_manager)

        # instantly create buy order at price * (1 + increment)
        assert len(open_orders) == producer.operational_depth
        assert to_fill_order not in open_orders
        newly_created_buy_order = open_orders[-1]
        assert newly_created_buy_order.symbol == to_fill_order.symbol
        price = to_fill_order.origin_price - (price_spread - price_increment)
        assert newly_created_buy_order.origin_price == trunc_with_n_decimal_digits(price, 8)
        assert newly_created_buy_order.origin_quantity == \
            trunc_with_n_decimal_digits(
                to_fill_order.filled_price / price * to_fill_order.filled_quantity * (1 - producer.max_fees),
                8)
        assert newly_created_buy_order.side == TradeOrderSide.BUY
        assert get_portfolio_currency(exchange_manager, "USD", portfolio_type=PORTFOLIO_TOTAL) > now_usd
        current_total = _get_total_usd(exchange_manager, 100)
        assert previous_total_sell < current_total
    finally:
        await _stop(exchange_manager)


async def test_create_order():
    try:
        symbol = "BTC/USD"
        producer, consumer, exchange_manager = await _get_tools(symbol)
        _, _, _, _, symbol_market = await get_pre_order_data(exchange_manager,
                                                             symbol=producer.symbol,
                                                             timeout=1)
        producer.symbol_market = symbol_market
        producer._refresh_symbol_data(symbol_market)

        # SELL

        # enough quantity in portfolio
        price = 100
        quantity = 1
        side = TradeOrderSide.SELL
        to_create_order = OrderData(side, quantity, price, symbol, False)
        created_order = await consumer.create_order(to_create_order, price, symbol_market)
        assert created_order.origin_quantity == quantity
        assert created_order is not None

        # not enough quantity in portfolio
        price = 100
        quantity = 10
        side = TradeOrderSide.SELL
        to_create_order = OrderData(side, quantity, price, symbol, False)
        created_order = await consumer.create_order(to_create_order, price, symbol_market)
        assert created_order is None

        # just enough quantity in portfolio
        price = 100
        quantity = 9
        side = TradeOrderSide.SELL
        to_create_order = OrderData(side, quantity, price, symbol, False)
        created_order = await consumer.create_order(to_create_order, price, symbol_market)
        assert created_order.origin_quantity == quantity
        assert get_portfolio_currency(exchange_manager, "BTC") == 0
        assert created_order is not None

        # not enough quantity anymore
        price = 100
        quantity = 0.0001
        side = TradeOrderSide.SELL
        to_create_order = OrderData(side, quantity, price, symbol, False)
        created_order = await consumer.create_order(to_create_order, price, symbol_market)
        assert get_portfolio_currency(exchange_manager, "BTC") == 0
        assert created_order is None

        # BUY

        # enough quantity in portfolio
        price = 100
        quantity = 1
        side = TradeOrderSide.BUY
        to_create_order = OrderData(side, quantity, price, symbol, False)
        created_order = await consumer.create_order(to_create_order, price, symbol_market)
        assert created_order.origin_quantity == quantity
        assert get_portfolio_currency(exchange_manager, "USD") == 900
        assert created_order is not None

        # not enough quantity in portfolio
        price = 585
        quantity = 2
        side = TradeOrderSide.BUY
        to_create_order = OrderData(side, quantity, price, symbol, False)
        created_order = await consumer.create_order(to_create_order, price, symbol_market)
        assert get_portfolio_currency(exchange_manager, "USD") == 900
        assert created_order is None

        # enough quantity in portfolio
        price = 40
        quantity = 2
        side = TradeOrderSide.BUY
        to_create_order = OrderData(side, quantity, price, symbol, False)
        created_order = await consumer.create_order(to_create_order, price, symbol_market)
        assert created_order.origin_quantity == quantity
        assert get_portfolio_currency(exchange_manager, "USD") == 820
        assert created_order is not None

        # enough quantity in portfolio
        price = 205
        quantity = 4
        side = TradeOrderSide.BUY
        to_create_order = OrderData(side, quantity, price, symbol, False)
        created_order = await consumer.create_order(to_create_order, price, symbol_market)
        assert created_order.origin_quantity == quantity
        assert get_portfolio_currency(exchange_manager, "USD") == 0
        assert created_order is not None

        # not enough quantity in portfolio anymore
        price = 205
        quantity = 1
        side = TradeOrderSide.BUY
        to_create_order = OrderData(side, quantity, price, symbol, False)
        created_order = await consumer.create_order(to_create_order, price, symbol_market)
        assert get_portfolio_currency(exchange_manager, "USD") == 0
        assert created_order is None
    finally:
        await _stop(exchange_manager)


async def test_create_new_orders():
    try:
        symbol = "BTC/USD"
        producer, consumer, exchange_manager = await _get_tools(symbol)
        _, _, _, _, symbol_market = await get_pre_order_data(exchange_manager,
                                                             symbol=producer.symbol,
                                                             timeout=1)
        producer.symbol_market = symbol_market
        producer._refresh_symbol_data(symbol_market)

        # valid input
        price = 205
        quantity = 4
        side = TradeOrderSide.BUY
        to_create_order = OrderData(side, quantity, price, symbol, False)
        data = {
            consumer.ORDER_DATA_KEY: to_create_order,
            consumer.CURRENT_PRICE_KEY: price,
            consumer.SYMBOL_MARKET_KEY: symbol_market
        }
        assert await consumer.create_new_orders(symbol, None, None, data=data) is not None

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
    finally:
        await _stop(exchange_manager)


async def _wait_for_orders_creation():
    pass


async def _check_open_orders_count(exchange_manager, count):
    assert len(get_open_orders(exchange_manager)) == count


def _get_total_usd(exchange_manager, btc_price):
    return get_portfolio_currency(exchange_manager, "USD", portfolio_type=PORTFOLIO_TOTAL)\
        + get_portfolio_currency(exchange_manager, "BTC", portfolio_type=PORTFOLIO_TOTAL) * btc_price


async def _fill_order(order, exchange_manager, trigger_price=None, trigger_update_callback=True,
                      trading_mode=None):
    if trigger_price is None:
        trigger_price = order.origin_price*0.99 if order.side == TradeOrderSide.BUY else order.origin_price*1.01
    last_prices = [{"price": trigger_price, "timestamp": time.time()}]
    initial_len = len(get_open_orders(exchange_manager))
    await order.update_order_status(last_prices)
    if order.status == OrderStatus.FILLED:
        await order.close_order()
        assert len(get_open_orders(exchange_manager)) == initial_len - 1
        if trigger_update_callback:
            await trading_mode._order_notification_callback(None,
                                                            exchange_manager.id,
                                                            None,
                                                            symbol=order.symbol,
                                                            order=order.to_dict(),
                                                            is_from_bot=True,
                                                            is_closed=True,
                                                            is_updated=False)


async def _test_mode(mode, expected_buy_count, expected_sell_count, price, lowest_buy=None, highest_sell=None,
                     btc_holdings=None):

    try:
        symbol = "BTC/USD"
        producer, _, exchange_manager = await _get_tools(symbol, btc_holdings=btc_holdings)
        if lowest_buy is not None:
            producer.lowest_buy = lowest_buy
        if highest_sell is not None:
            producer.highest_sell = highest_sell
        producer.mode = mode
        force_set_mark_price(exchange_manager, symbol, price)
        _, _, _, _, symbol_market = await get_pre_order_data(exchange_manager,
                                                             symbol=symbol,
                                                             timeout=1)
        producer.symbol_market = symbol_market
        producer.current_price = price
        await _check_generate_orders(exchange_manager, producer, expected_buy_count,
                                     expected_sell_count, price, symbol_market)

        await create_task(_wait_for_orders_creation())
        open_orders = get_open_orders(exchange_manager)
        if expected_buy_count or expected_sell_count:
            assert len(open_orders) <= producer.operational_depth
        _check_orders(open_orders, mode, producer, exchange_manager)

        assert get_portfolio_currency(exchange_manager, "BTC") >= 0
        assert get_portfolio_currency(exchange_manager, "USD") >= 0
    finally:
        await _stop(exchange_manager)


async def _check_generate_orders(exchange_manager, producer, expected_buy_count,
                                 expected_sell_count, price, symbol_market):
    async with exchange_manager.exchange_personal_data.portfolio_manager.portfolio.lock:
        producer._refresh_symbol_data(symbol_market)
        buy_orders, sell_orders = await producer._generate_staggered_orders(price)
        assert len(buy_orders) == expected_buy_count
        assert len(sell_orders) == expected_sell_count

        assert all(o.price < price for o in buy_orders)
        assert all(o.price > price for o in sell_orders)

        if buy_orders:
            assert not any(order for order in buy_orders if order.is_virtual)

        if sell_orders:
            assert any(order for order in sell_orders if order.is_virtual)

        buy_holdings = get_portfolio_currency(exchange_manager, "USD")
        assert sum(order.price*order.quantity for order in buy_orders) <= buy_holdings

        sell_holdings = get_portfolio_currency(exchange_manager, "BTC")
        assert sum(order.quantity for order in sell_orders) <= sell_holdings

        staggered_orders = producer._alternate_not_virtual_orders(buy_orders, sell_orders)
        if staggered_orders:
            assert not any(order for order in staggered_orders if order.is_virtual)

        await producer._create_not_virtual_orders(staggered_orders, price)

        assert all(producer.highest_sell >= o.price >= producer.lowest_buy
                   for o in sell_orders)

        assert all(producer.highest_sell >= o.price >= producer.lowest_buy
                   for o in buy_orders)


def _check_orders(orders, strategy_mode, producer, exchange_manager):
    buy_increase_towards_center = StrategyModeMultipliersDetails[strategy_mode][TradeOrderSide.BUY] == INCREASING
    sell_increase_towards_center = StrategyModeMultipliersDetails[strategy_mode][TradeOrderSide.SELL] == INCREASING
    multiplier = StrategyModeMultipliersDetails[strategy_mode][MULTIPLIER]

    first_buy = None
    current_buy = None
    current_sell = None
    last_order_side = None
    for order in orders:

        if last_order_side is not None:
            # alternate sell and buy orders
            assert last_order_side == (TradeOrderSide.BUY if order.side == TradeOrderSide.SELL else TradeOrderSide.SELL)
        last_order_side = order.side

        if order.side == TradeOrderSide.BUY:
            if current_buy is None:
                current_buy = order
                first_buy = order
            else:
                # place buy orders from the lowest price up to the current price
                assert current_buy.origin_price < order.origin_price
                if buy_increase_towards_center:
                    assert current_buy.origin_quantity * current_buy.origin_price < \
                        order.origin_quantity * order.origin_price
                else:
                    assert current_buy.origin_quantity * current_buy.origin_price > \
                        order.origin_quantity * order.origin_price
                current_buy = order

        if order.side == TradeOrderSide.SELL:
            if current_sell is None:
                current_sell = order
            else:
                assert current_sell.origin_price > order.origin_price
                current_sell = order

    order_limiting_currency_amount = get_portfolio_currency(exchange_manager, "USD", portfolio_type=PORTFOLIO_TOTAL)
    _, average_order_quantity = \
        producer._get_order_count_and_average_quantity(producer.current_price,
                                                       False,
                                                       producer.lowest_buy,
                                                       producer.current_price,
                                                       order_limiting_currency_amount)
    if orders:
        if buy_increase_towards_center:
            assert round(current_buy.origin_quantity * current_buy.origin_price -
                         first_buy.origin_quantity * first_buy.origin_price) == round(multiplier *
                                                                                      average_order_quantity)
        else:
            assert round(first_buy.origin_quantity * first_buy.origin_price -
                         current_buy.origin_quantity * current_buy.origin_price) == round(multiplier *
                                                                                          average_order_quantity)

        order_limiting_currency_amount = get_portfolio_currency(exchange_manager, "BTC", portfolio_type=PORTFOLIO_TOTAL)
        _, average_order_quantity = \
            producer._get_order_count_and_average_quantity(producer.current_price,
                                                           True,
                                                           producer.current_price,
                                                           producer.highest_sell,
                                                           order_limiting_currency_amount)

        if strategy_mode not in [StrategyModes.NEUTRAL, StrategyModes.VALLEY, StrategyModes.SELL_SLOPE]:
            # not exactly multiplier because of virtual orders and rounds
            if sell_increase_towards_center:
                expected_quantity = trunc_with_n_decimal_digits(
                    average_order_quantity * (1 + multiplier/2),
                    8)
                assert abs(current_sell.origin_quantity - expected_quantity) < \
                    multiplier * producer.increment / (2 * producer.current_price)
            else:
                expected_quantity = trunc_with_n_decimal_digits(
                    average_order_quantity * (1 - multiplier/2),
                    8)
                assert abs(current_sell.origin_quantity == expected_quantity) < \
                    multiplier * producer.increment / (2 * producer.current_price)


async def _light_check_orders(producer, exchange_manager, expected_buy_count, expected_sell_count, price):

    buy_orders, sell_orders = await producer._generate_staggered_orders(price)
    assert len(buy_orders) == expected_buy_count
    assert len(sell_orders) == expected_sell_count

    assert all(o.price < price for o in buy_orders)
    assert all(o.price > price for o in sell_orders)

    buy_holdings = get_portfolio_currency(exchange_manager, "ETH")
    assert sum(order.price * order.quantity for order in buy_orders) <= buy_holdings

    sell_holdings = get_portfolio_currency(exchange_manager, "RDN")
    assert sum(order.quantity for order in sell_orders) <= sell_holdings

    staggered_orders = producer._alternate_not_virtual_orders(buy_orders, sell_orders)
    if staggered_orders:
        assert not any(order for order in staggered_orders if order.is_virtual)

    await producer._create_not_virtual_orders(staggered_orders, price)

    await create_task(_wait_for_orders_creation())
    open_orders = get_open_orders(exchange_manager)
    if expected_buy_count or expected_sell_count:
        assert len(open_orders) <= producer.operational_depth

    trading_mode = producer.mode
    buy_increase_towards_center = StrategyModeMultipliersDetails[trading_mode][TradeOrderSide.BUY] == INCREASING

    current_buy = None
    current_sell = None
    last_order_side = None
    for order in open_orders:

        if last_order_side is not None:
            # alternate sell and buy orders
            assert last_order_side == (TradeOrderSide.BUY if order.side == TradeOrderSide.SELL else TradeOrderSide.SELL)
        last_order_side = order.side

        if order.side == TradeOrderSide.BUY:
            if current_buy is None:
                current_buy = order
            else:
                # place buy orders from the lowest price up to the current price
                assert current_buy.origin_price < order.origin_price
                if buy_increase_towards_center:
                    assert current_buy.origin_quantity * current_buy.origin_price < \
                        order.origin_quantity * order.origin_price
                else:
                    assert current_buy.origin_quantity * current_buy.origin_price > \
                        order.origin_quantity * order.origin_price
                current_buy = order

        if order.side == TradeOrderSide.SELL:
            if current_sell is None:
                current_sell = order
            else:
                assert current_sell.origin_price > order.origin_price
                current_sell = order

    assert get_portfolio_currency(exchange_manager, "ETH") >= 0
    assert get_portfolio_currency(exchange_manager, "RDN") >= 0


def _get_multi_symbol_staggered_config():
    return {
        "required_strategies": ["StaggeredOrdersStrategiesEvaluator"],
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
