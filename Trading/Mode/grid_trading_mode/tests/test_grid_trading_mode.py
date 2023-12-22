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
import contextlib
import numpy
import pytest
import os.path
import asyncio
import decimal
import copy
import mock

import async_channel.util as channel_util
import octobot_tentacles_manager.api as tentacles_manager_api
import octobot_backtesting.api as backtesting_api
import octobot_commons.constants as commons_constants
import octobot_commons.tests.test_config as test_config
import octobot_commons.asyncio_tools as asyncio_tools
import octobot_trading.api as trading_api
import octobot_trading.exchange_channel as exchanges_channel
import octobot_trading.exchanges as exchanges
import octobot_trading.enums as trading_enums
import octobot_trading.personal_data as trading_personal_data
import octobot_trading.constants as trading_constants
import tentacles.Trading.Mode.grid_trading_mode.grid_trading as grid_trading
import tentacles.Trading.Mode.staggered_orders_trading_mode.staggered_orders_trading as staggered_orders_trading
import tests.test_utils.config as test_utils_config
import tests.test_utils.memory_check_util as memory_check_util
import tests.test_utils.test_exchanges as test_exchanges
import tests.test_utils.trading_modes as test_trading_modes

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def _init_trading_mode(config, exchange_manager, symbol):
    staggered_orders_trading.StaggeredOrdersTradingModeProducer.SCHEDULE_ORDERS_CREATION_ON_START = False
    mode = grid_trading.GridTradingMode(config, exchange_manager)
    mode.symbol = None if mode.get_is_symbol_wildcard() else symbol
    # mode.trading_config = _get_multi_symbol_staggered_config()
    await mode.initialize()
    # add mode to exchange manager so that it can be stopped and freed from memory
    exchange_manager.trading_modes.append(mode)
    mode.producers[0].PRICE_FETCHING_TIMEOUT = 0.5
    mode.producers[0].allow_order_funds_redispatch = True
    return mode, mode.producers[0]


@contextlib.asynccontextmanager
async def _get_tools(symbol, btc_holdings=None, additional_portfolio={}, fees=None):
    exchange_manager = None
    try:
        tentacles_manager_api.reload_tentacle_info()
        config = test_config.load_test_config()
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO]["USDT"] = 1000
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO][
            "BTC"] = 10 if btc_holdings is None else btc_holdings
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO].update(additional_portfolio)
        if fees is not None:
            config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_SIMULATOR_FEES][
                commons_constants.CONFIG_SIMULATOR_FEES_TAKER] = fees
            config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_SIMULATOR_FEES][
                commons_constants.CONFIG_SIMULATOR_FEES_MAKER] = fees
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

        # set BTC/USDT price at 1000 USDT
        trading_api.force_set_mark_price(exchange_manager, symbol, 1000)

        mode, producer = await _init_trading_mode(config, exchange_manager, symbol)

        producer.flat_spread = decimal.Decimal(10)
        producer.flat_increment = decimal.Decimal(5)
        producer.buy_orders_count = 25
        producer.sell_orders_count = 25
        producer.compensate_for_missed_mirror_order = True
        test_trading_modes.set_ready_to_start(producer)

        yield producer, mode.get_trading_mode_consumers()[0], exchange_manager
    finally:
        if exchange_manager:
            await _stop(exchange_manager)


async def _stop(exchange_manager):
    if exchange_manager is None:
        return
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
        grid_trading.GridTradingMode
    )
    await memory_check_util.run_independent_backtestings_with_memory_check(test_config.load_test_config(),
                                                                           tentacles_setup_config)


async def test_init_allowed_price_ranges_with_flat_values():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        producer.sell_price_range = grid_trading.AllowedPriceRange()
        producer.buy_price_range = grid_trading.AllowedPriceRange()
        producer.flat_spread = decimal.Decimal(12)
        producer.flat_increment = decimal.Decimal(5)
        producer.sell_orders_count = 20
        producer.buy_orders_count = 5
        producer._init_allowed_price_ranges(100)
        # price + half spread + increment for each order to create after 1st one
        assert producer.sell_price_range.higher_bound == 100 + 12/2 + 5*(20-1)
        assert producer.sell_price_range.lower_bound == 100 + 12/2
        assert producer.buy_price_range.higher_bound == 100 - 12/2
        # price - half spread - increment for each order to create after 1st one
        assert producer.buy_price_range.lower_bound == 100 - 12/2 - 5*(5-1)


async def test_init_allowed_price_ranges_with_percent_values():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        producer.sell_price_range = grid_trading.AllowedPriceRange()
        producer.buy_price_range = grid_trading.AllowedPriceRange()
        # used with default configuration
        producer.spread = decimal.Decimal("0.05")   # 5%
        producer.increment = decimal.Decimal("0.02")   # 2%
        producer.flat_spread = None
        producer.flat_increment = None
        producer.sell_orders_count = 20
        producer.buy_orders_count = 5
        _, _, _, _, symbol_market = await trading_personal_data.get_pre_order_data(exchange_manager,
                                                                                   symbol=producer.symbol,
                                                                                   timeout=1)
        producer.symbol_market = symbol_market
        producer._init_allowed_price_ranges(100)
        # price + half spread + increment for each order to create after 1st one
        assert producer.flat_spread == 5
        assert producer.flat_increment == 2
        assert producer.sell_price_range.higher_bound == decimal.Decimal(str(100 + 5/2 + 2*(20-1)))
        assert producer.sell_price_range.lower_bound == decimal.Decimal(str(100 + 5/2))
        assert producer.buy_price_range.higher_bound == decimal.Decimal(str(100 - 5/2))
        # price - half spread - increment for each order to create after 1st one
        assert producer.buy_price_range.lower_bound == decimal.Decimal(str(100 - 5/2 - 2*(5-1)))


async def test_create_orders_with_default_config():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        producer.spread = producer.increment = producer.flat_spread = producer.flat_increment = \
            producer.buy_orders_count = producer.sell_orders_count = None
        producer.trading_mode.trading_config[producer.trading_mode.CONFIG_PAIR_SETTINGS] = []

        assert producer._load_symbol_trading_config() is True
        producer.read_config()

        assert producer.spread is not None
        assert producer.increment is not None
        assert producer.flat_spread is None
        assert producer.flat_increment is None
        assert producer.buy_orders_count is not None
        assert producer.sell_orders_count is not None

        producer.sell_funds = decimal.Decimal("0.00006")  # 5 orders
        producer.buy_funds = decimal.Decimal("1")  # 24 orders

        # set BTC/USD price at 4000 USD
        trading_api.force_set_mark_price(exchange_manager, symbol, 4000)
        await producer._ensure_staggered_orders()
        # create orders as with normal config (except that it's the default one)
        btc_available_funds = producer._get_available_funds("BTC")
        usd_available_funds = producer._get_available_funds("USDT")

        used_btc = 10 - btc_available_funds
        used_usd = 1000 - usd_available_funds

        assert producer.buy_funds * decimal.Decimal(0.95) <= used_usd <= producer.buy_funds
        assert producer.sell_funds * decimal.Decimal(0.95) <= used_btc <= producer.sell_funds

        # btc_available_funds for reduced because orders are not created
        assert 10 - 0.001 <= btc_available_funds < 10
        assert 1000 - 100 <= usd_available_funds < 1000
        await asyncio.create_task(_check_open_orders_count(exchange_manager, 5 + producer.buy_orders_count))
        created_orders = trading_api.get_open_orders(exchange_manager)
        created_buy_orders = [o for o in created_orders if o.side is trading_enums.TradeOrderSide.BUY]
        created_sell_orders = [o for o in created_orders if o.side is trading_enums.TradeOrderSide.SELL]
        assert len(created_buy_orders) == producer.buy_orders_count == 20
        assert len(created_sell_orders) < producer.sell_orders_count
        assert len(created_sell_orders) == 5
        # ensure only orders closest to the current price have been created
        min_buy_price = 4000 - (producer.flat_spread / 2) - (producer.flat_increment * (len(created_buy_orders) - 1))
        assert all(
            o.origin_price >= min_buy_price for o in created_buy_orders
        )
        max_sell_price = 4000 + (producer.flat_spread / 2) + (producer.flat_increment * (len(created_sell_orders) - 1))
        assert all(
            o.origin_price <= max_sell_price for o in created_sell_orders
        )
        pf_btc_available_funds = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        pf_usd_available_funds = trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        assert pf_btc_available_funds >= 10 - 0.00006
        assert pf_usd_available_funds >= 1000 - 1

        assert pf_btc_available_funds >= btc_available_funds
        assert pf_usd_available_funds >= usd_available_funds


async def test_create_orders_without_enough_funds_for_all_orders_16_total_orders():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):

        producer.sell_funds = decimal.Decimal("0.00006")  # 5 orders
        producer.buy_funds = decimal.Decimal("0.5")  # 11 orders

        # set BTC/USD price at 4000 USD
        trading_api.force_set_mark_price(exchange_manager, symbol, 4000)
        await producer._ensure_staggered_orders()
        btc_available_funds = producer._get_available_funds("BTC")
        usd_available_funds = producer._get_available_funds("USDT")

        used_btc = 10 - btc_available_funds
        used_usd = 1000 - usd_available_funds

        assert used_usd >= producer.buy_funds * decimal.Decimal(0.99)
        assert used_btc >= producer.sell_funds * decimal.Decimal(0.99)

        # btc_available_funds for reduced because orders are not created
        assert 10 - 0.001 <= btc_available_funds < 10
        assert 1000 - 100 <= usd_available_funds < 1000
        await asyncio.create_task(_check_open_orders_count(exchange_manager, 5 + 11))
        created_orders = trading_api.get_open_orders(exchange_manager)
        created_buy_orders = [o for o in created_orders if o.side is trading_enums.TradeOrderSide.BUY]
        created_sell_orders = [o for o in created_orders if o.side is trading_enums.TradeOrderSide.SELL]
        assert len(created_buy_orders) < producer.buy_orders_count
        assert len(created_buy_orders) == 11
        assert len(created_sell_orders) < producer.sell_orders_count
        assert len(created_sell_orders) == 5
        # ensure only orders closest to the current price have been created
        min_buy_price = 4000 - (producer.flat_spread / 2) - (producer.flat_increment * (len(created_buy_orders) - 1))
        assert all(
            o.origin_price >= min_buy_price for o in created_buy_orders
        )
        max_sell_price = 4000 + (producer.flat_spread / 2) + (producer.flat_increment * (len(created_sell_orders) - 1))
        assert all(
            o.origin_price <= max_sell_price for o in created_sell_orders
        )
        pf_btc_available_funds = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        pf_usd_available_funds = trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        assert pf_btc_available_funds >= 10 - 0.00006
        assert pf_usd_available_funds >= 1000 - 0.5

        assert pf_btc_available_funds >= btc_available_funds
        assert pf_usd_available_funds >= usd_available_funds


async def test_create_orders_without_enough_funds_for_all_orders_3_total_orders():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):

        producer.buy_funds = decimal.Decimal("0.07")  # 1 order
        producer.sell_funds = decimal.Decimal("0.000025")  # 2 orders

        # set BTC/USD price at 4000 USD
        trading_api.force_set_mark_price(exchange_manager, symbol, 4000)
        await producer._ensure_staggered_orders()
        btc_available_funds = producer._get_available_funds("BTC")
        usd_available_funds = producer._get_available_funds("USDT")

        used_btc = 10 - btc_available_funds
        used_usd = 1000 - usd_available_funds

        assert used_usd >= producer.buy_funds * decimal.Decimal(0.99)
        assert used_btc >= producer.sell_funds * decimal.Decimal(0.99)

        # btc_available_funds for reduced because orders are not created
        assert 10 - 0.001 <= btc_available_funds < 10
        assert 1000 - 100 <= usd_available_funds < 1000
        await asyncio.create_task(_check_open_orders_count(exchange_manager, 1 + 2))
        created_orders = trading_api.get_open_orders(exchange_manager)
        created_buy_orders = [o for o in created_orders if o.side is trading_enums.TradeOrderSide.BUY]
        created_sell_orders = [o for o in created_orders if o.side is trading_enums.TradeOrderSide.SELL]
        assert len(created_buy_orders) < producer.buy_orders_count
        assert len(created_buy_orders) == 1
        assert len(created_sell_orders) < producer.sell_orders_count
        assert len(created_sell_orders) == 2
        # ensure only orders closest to the current price have been created
        min_buy_price = 4000 - (producer.flat_spread / 2) - (producer.flat_increment * (len(created_buy_orders) - 1))
        assert all(
            o.origin_price >= min_buy_price for o in created_buy_orders
        )
        max_sell_price = 4000 + (producer.flat_spread / 2) + (producer.flat_increment * (len(created_sell_orders) - 1))
        assert all(
            o.origin_price <= max_sell_price for o in created_sell_orders
        )
        pf_btc_available_funds = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        pf_usd_available_funds = trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        assert pf_btc_available_funds >= 10 - 0.000025
        assert pf_usd_available_funds >= 1000 - 0.07

        assert pf_btc_available_funds >= btc_available_funds
        assert pf_usd_available_funds >= usd_available_funds


async def test_create_orders_with_fixed_volume_per_order():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):

        producer.buy_volume_per_order = decimal.Decimal("0.1")
        producer.sell_volume_per_order = decimal.Decimal("0.3")

        # set BTC/USD price at 4000 USD
        trading_api.force_set_mark_price(exchange_manager, symbol, 4000)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, 27))
        created_orders = trading_api.get_open_orders(exchange_manager)
        created_buy_orders = [o for o in created_orders if o.side is trading_enums.TradeOrderSide.BUY]
        created_sell_orders = [o for o in created_orders if o.side is trading_enums.TradeOrderSide.SELL]
        assert len(created_buy_orders) == 2  # not enough funds to create more orders
        assert len(created_sell_orders) == producer.sell_orders_count  # 25

        # ensure only closest orders got created with the right value and in the right order
        assert created_buy_orders[0].origin_price == 3995
        assert created_buy_orders[1].origin_price == 3990
        assert created_sell_orders[0].origin_price == 4005
        assert created_sell_orders[1].origin_price == 4010
        assert created_sell_orders[0] is created_orders[0]
        assert all(o.origin_quantity == producer.buy_volume_per_order for o in created_buy_orders)
        assert all(o.origin_quantity == producer.sell_volume_per_order for o in created_sell_orders)
        _check_created_orders(producer, trading_api.get_open_orders(exchange_manager), 4000)


async def test_start_with_existing_valid_orders():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        # first start: setup orders
        orders_count = 20 + 24
        producer.sell_funds = decimal.Decimal("1")  # 25 sell orders
        producer.buy_funds = decimal.Decimal("1")  # 19 buy orders orders (price is negative for the last 6 orders)
        orders_count = 19 + 25

        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == orders_count

        # new evaluation, same price
        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        # did nothing
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        assert original_orders[0] is trading_api.get_open_orders(exchange_manager)[0]
        assert original_orders[-1] is trading_api.get_open_orders(exchange_manager)[-1]
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count
        first_buy_index = 25

        # new evaluation, price changed
        # order would be filled
        to_fill_order = original_orders[first_buy_index]
        price = 95
        assert price == to_fill_order.origin_price
        await _fill_order(to_fill_order, exchange_manager, price, producer=producer)
        await asyncio.create_task(_wait_for_orders_creation(2))
        # did nothing: orders got replaced
        assert len(original_orders) == len(trading_api.get_open_orders(exchange_manager))
        # simulate a start without StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS
        staggered_orders_trading.StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS.pop(exchange_manager.id, None)
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        # did nothing
        assert len(original_orders) == len(trading_api.get_open_orders(exchange_manager))

        # orders gets cancelled
        open_orders = trading_api.get_open_orders(exchange_manager)
        to_cancel = [open_orders[20], open_orders[18], open_orders[3]]
        for order in to_cancel:
            await exchange_manager.trader.cancel_order(order)
        post_available = trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - len(to_cancel)

        await producer._ensure_staggered_orders()
        await asyncio.create_task(_wait_for_orders_creation(orders_count))
        # restored orders
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USDT").available <= post_available
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        _check_created_orders(producer, trading_api.get_open_orders(exchange_manager), 100)


async def test_start_after_offline_filled_orders_without_recent_trades():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        # first start: setup orders
        producer.sell_funds = decimal.Decimal("1")  # 25 sell orders
        producer.buy_funds = decimal.Decimal("10000")  # 19 buy orders
        orders_count = 19 + 25

        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == orders_count
        pre_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USDT").available

        # offline simulation 1: orders get filled but not replaced => price got up to 110 and down to 90, now is 96s
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled = [o for o in open_orders if 90 <= o.origin_price <= 110]
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        # simulate a start without StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS
        staggered_orders_trading.StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS.pop(exchange_manager.id, None)
        # clear trades
        await trading_api.clear_trades_storage_history(exchange_manager)
        post_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        assert pre_portfolio < post_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - len(offline_filled)

        # back online: restore orders according to current price
        price = 96
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        with _assert_missing_orders_count(producer, len(offline_filled)):
            await producer._ensure_staggered_orders()
        # restored orders
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USDT").available <= post_portfolio
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        _check_created_orders(producer, trading_api.get_open_orders(exchange_manager), 100)

        # offline simulation 2: orders get filled but not replaced => price got down to 50
        pre_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        price = 50
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled = [o for o in open_orders if price <= o.origin_price <= 100]
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        # simulate a start without StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS
        staggered_orders_trading.StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS.pop(exchange_manager.id, None)
        # clear trades
        await trading_api.clear_trades_storage_history(exchange_manager)    #todo
        post_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        assert pre_portfolio < post_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - len(offline_filled)

        # back online: restore orders according to current price
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        with _assert_missing_orders_count(producer, len(offline_filled)):
            await producer._ensure_staggered_orders()
        # restored orders
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "BTC").available <= post_portfolio
        _check_created_orders(producer, trading_api.get_open_orders(exchange_manager), 100)


async def test_start_after_offline_filled_orders_with_recent_trades():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        # first start: setup orders
        producer.sell_funds = decimal.Decimal("1")  # 25 sell orders
        producer.buy_funds = decimal.Decimal("10000")  # 19 buy orders
        orders_count = 19 + 25

        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == orders_count
        pre_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USDT").available

        # offline simulation: orders get filled but not replaced => price got up to 110 and not down to 90, now is 96s
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled = [o for o in open_orders if 90 <= o.origin_price <= 110]
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        post_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        assert pre_portfolio < post_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - len(offline_filled)

        # back online: restore orders according to current price
        price = 95
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        with _assert_missing_orders_count(producer, len(offline_filled)):
            await producer._ensure_staggered_orders()
        # restored orders
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USDT").available <= post_portfolio
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        _check_created_orders(producer, trading_api.get_open_orders(exchange_manager), 100)

        # offline simulation 2: orders get filled but not replaced => price got down to 50
        pre_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        price = 50
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled = [o for o in open_orders if price <= o.origin_price <= 100]
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        # simulate a start without StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS
        staggered_orders_trading.StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS.pop(exchange_manager.id, None)
        post_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        assert pre_portfolio < post_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - len(offline_filled)

        # back online: restore orders according to current price
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        with _assert_missing_orders_count(producer, len(offline_filled)):
            await producer._ensure_staggered_orders()
        # restored orders
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "BTC").available <= post_portfolio
        _check_created_orders(producer, trading_api.get_open_orders(exchange_manager), 100)


async def test_start_after_offline_filled_orders_close_to_price_with_recent_trades():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        # first start: setup orders
        producer.sell_funds = decimal.Decimal("1")  # 25 sell orders
        producer.buy_funds = decimal.Decimal("10000")  # 25 buy orders
        producer.flat_spread = decimal.Decimal("200")
        producer.flat_increment = decimal.Decimal("75")
        orders_count = 25 + 25

        initial_price = 29247.16
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, initial_price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == orders_count
        pre_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available

        # offline simulation: orders get filled but not replaced => price got up to 110 and not down to 90, now is 96s
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled_orders = [o for o in open_orders if o.origin_price == decimal.Decimal('29147.16')]
        assert len(offline_filled_orders) == 1
        offline_filled = offline_filled_orders[0]
        await _fill_order(offline_filled, exchange_manager, trigger_update_callback=False, producer=producer)
        # offline_filled is a buy order: now have mode BTC
        post_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        assert pre_portfolio < post_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - 1

        # back online: restore orders according to current price => create sell missing order
        price = 29127.16
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        with _assert_missing_orders_count(producer, len(offline_filled_orders)):
            await producer._ensure_staggered_orders()
        # restored orders
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "BTC").available < post_portfolio
        open_orders = trading_api.get_open_orders(exchange_manager)
        _check_created_orders(producer, open_orders, initial_price)
        new_orders = [o for o in open_orders if o.origin_price == decimal.Decimal('29272.16')]
        assert len(new_orders) == 1
        new_order = new_orders[0]
        assert new_order.side is trading_enums.TradeOrderSide.SELL
        # offline_filled - fees
        trade = trading_api.get_trade_history(exchange_manager)[0]
        fees = trade.fee[trading_enums.FeePropertyColumns.COST.value]
        symbol_market = exchange_manager.exchange.get_market_status(symbol, with_fixer=False)
        assert new_order.origin_quantity == \
               trading_personal_data.decimal_adapt_quantity(symbol_market, offline_filled.origin_quantity - fees)


async def test_start_after_offline_full_sell_side_filled_orders_with_recent_trades():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        # first start: setup orders
        producer.sell_funds = decimal.Decimal("1")  # 25 sell orders
        producer.buy_funds = decimal.Decimal("1")  # 19 buy orders
        orders_count = 19 + 25

        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == orders_count
        pre_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USDT").available

        # offline simulation: orders get filled but not replaced => price got up to more than the max price
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled = [o for o in open_orders if o.side == trading_enums.TradeOrderSide.SELL]
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        # simulate a start without StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS
        staggered_orders_trading.StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS.pop(exchange_manager.id, None)
        post_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        assert pre_portfolio < post_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - len(offline_filled)

        # back online: restore orders according to current price
        price = max(order.origin_price for order in offline_filled) * 2
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        with _assert_missing_orders_count(producer, len(offline_filled)):
            await producer._ensure_staggered_orders()
        assert producer.operational_depth > orders_count
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USDT").available <= post_portfolio
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        open_orders = trading_api.get_open_orders(exchange_manager)
        assert all(
            order.side == trading_enums.TradeOrderSide.BUY
            for order in open_orders
        )
        _check_created_orders(producer, trading_api.get_open_orders(exchange_manager), 100)


async def test_start_after_offline_full_sell_side_filled_orders_price_back():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        # first start: setup orders
        producer.sell_funds = decimal.Decimal("1")  # 25 sell orders
        producer.buy_funds = decimal.Decimal("1")  # 19 buy orders
        orders_count = 19 + 25

        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == orders_count
        pre_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USDT").available

        # offline simulation: orders get filled but not replaced => price got up to more than the max price
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled = [o for o in open_orders if o.side == trading_enums.TradeOrderSide.SELL]
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        # simulate a start without StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS
        staggered_orders_trading.StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS.pop(exchange_manager.id, None)
        post_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        assert pre_portfolio < post_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - len(offline_filled)

        # back online: restore orders according to current price
        # simulate current price as back to average origin sell orders
        price = offline_filled[len(offline_filled)//2].origin_price
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)

        def _get_fees_for_currency(fee, currency):
            if currency == "USDT":
                return decimal.Decimal("0.022")
            return trading_constants.ZERO

        with _assert_missing_orders_count(producer, len(offline_filled)):
            with _assert_adapt_order_quantity_because_fees(_get_fees_for_currency) \
                as adapt_order_quantity_because_fees_mock:
                await producer._ensure_staggered_orders()
                adapt_order_quantity_because_fees_mock.assert_called_once_with(
                    producer.exchange_manager, producer.trading_mode.symbol, trading_enums.TraderOrderType.BUY_MARKET,
                    decimal.Decimal('0.25714721'),
                    decimal.Decimal('165'),
                    trading_enums.ExchangeConstantsMarketPropertyColumns.TAKER, trading_enums.TradeOrderSide.BUY,
                    decimal.Decimal('1104.16879661120')
                )
        # restored orders (and create up to 50 orders as all orders can be created)
        assert producer.operational_depth > orders_count
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USDT").available <= post_portfolio
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        open_orders = trading_api.get_open_orders(exchange_manager)
        assert not all(
            order.side == trading_enums.TradeOrderSide.BUY
            for order in open_orders
        )
        _check_created_orders(producer, trading_api.get_open_orders(exchange_manager), 100)


async def test_start_after_offline_full_buy_side_filled_orders_price_back_with_recent_trades():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        # first start: setup orders
        producer.sell_funds = decimal.Decimal("1")  # 25 sell orders
        producer.buy_funds = decimal.Decimal("1")  # 19 buy orders
        orders_count = 19 + 25

        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == orders_count
        pre_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available

        # offline simulation: orders get filled but not replaced => price got up to more than the max price
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled = [o for o in open_orders if o.side == trading_enums.TradeOrderSide.BUY]
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        post_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        assert pre_portfolio < post_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - len(offline_filled)

        # back online: restore orders according to current price
        # simulate current price as back to average origin buy orders
        price = offline_filled[len(offline_filled)//2].origin_price
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        with _assert_missing_orders_count(producer, len(offline_filled)):
            await producer._ensure_staggered_orders()
        # restored orders
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "BTC").available <= post_portfolio
        open_orders = trading_api.get_open_orders(exchange_manager)
        assert not all(
            order.side == trading_enums.TradeOrderSide.BUY
            for order in open_orders
        )
        _check_created_orders(producer, trading_api.get_open_orders(exchange_manager), 100)


async def test_start_after_offline_buy_side_10_filled():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        # first start: setup orders
        producer.sell_funds = decimal.Decimal("1")  # 25 sell orders
        producer.buy_funds = decimal.Decimal("1")  # 19 buy orders
        orders_count = 19 + 25

        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == orders_count
        pre_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available

        # offline simulation: orders get filled but not replaced => price got up to more than the max price
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled = [o for o in open_orders if o.side == trading_enums.TradeOrderSide.BUY][:10]
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        post_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        assert pre_portfolio < post_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - len(offline_filled)

        # back online: restore orders according to current price
        # simulate current price as back to average origin buy orders
        price = offline_filled[len(offline_filled)//2].origin_price + 1
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)

        with _assert_missing_orders_count(producer, len(offline_filled)):
            with _assert_adapt_order_quantity_because_fees(None) \
                as adapt_order_quantity_because_fees_mock:
                await producer._ensure_staggered_orders()
                adapt_order_quantity_because_fees_mock.assert_called_once_with(
                    producer.exchange_manager, producer.trading_mode.symbol, trading_enums.TraderOrderType.SELL_MARKET,
                    decimal.Decimal('0.00320847831'),
                    decimal.Decimal('71'),
                    trading_enums.ExchangeConstantsMarketPropertyColumns.TAKER, trading_enums.TradeOrderSide.SELL,
                    decimal.Decimal('9.33582078738')
                )
        # restored orders
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "BTC").available <= post_portfolio
        open_orders = trading_api.get_open_orders(exchange_manager)
        # created 5 more sell orders
        assert len([order for order in open_orders if order.side is trading_enums.TradeOrderSide.SELL]) == 25 + 5
        # restored 5 of the 10 filled buy orders
        assert len([order for order in open_orders if order.side is trading_enums.TradeOrderSide.BUY]) == 19 - 5
        _check_created_orders(producer, trading_api.get_open_orders(exchange_manager), 100)


async def test_start_after_offline_x_filled_and_price_back_should_sell_to_recreate_buy():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        orders_count = 25 + 25

        price = decimal.Decimal(200)
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == orders_count
        pre_btc_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        pre_usdt_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USDT").available

        # offline simulation: orders get filled but not replaced => price moved to 150
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled = [
            o
            for o in open_orders
            if o.side == trading_enums.TradeOrderSide.BUY and o.origin_price >= decimal.Decimal("150")
        ]
        # this is 10 orders
        assert len(offline_filled) == 10
        max_filled_order_price = max(o.origin_price for o in offline_filled)
        assert max_filled_order_price == decimal.Decimal(195)
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        post_btc_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        post_usdt_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        # buy orders filled: BTC increased
        assert pre_btc_portfolio < post_btc_portfolio
        # no sell order filled, available USDT is constant
        assert pre_usdt_portfolio == post_usdt_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - len(offline_filled)

        # back online: restore orders according to current price
        # simulate current price as back to 180: should quickly sell BTC bought between 150 and 180 to be able to
        # create buy orders between 150 and 180
        price = decimal.Decimal(180)
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        with _assert_missing_orders_count(producer, len(offline_filled)):
            await producer._ensure_staggered_orders()
        # restored orders
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "BTC").available <= post_btc_portfolio
        open_orders = trading_api.get_open_orders(exchange_manager)
        # created 4 additional sell orders
        assert len([order for order in open_orders if order.side is trading_enums.TradeOrderSide.SELL]) == 25 + 4
        # restored 6 out of 10 filled buy orders
        assert len([order for order in open_orders if order.side is trading_enums.TradeOrderSide.BUY]) == 25 - 10 + 6
        _check_created_orders(producer, trading_api.get_open_orders(exchange_manager), 200)


async def test_start_after_offline_x_filled_and_price_back_should_buy_to_recreate_sell():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        orders_count = 25 + 25

        price = decimal.Decimal(200)
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == orders_count
        pre_btc_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        pre_usdt_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USDT").available

        # offline simulation: orders get filled but not replaced => price moved to 150
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled = [
            o
            for o in open_orders
            if o.side == trading_enums.TradeOrderSide.SELL and o.origin_price <= decimal.Decimal("250")
        ]
        # this is 10 orders
        assert len(offline_filled) == 10
        max_filled_order_price = max(o.origin_price for o in offline_filled)
        assert max_filled_order_price == decimal.Decimal(250)
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        post_btc_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        post_usdt_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        # buy orders filled: available BTC is constant
        assert pre_btc_portfolio == post_btc_portfolio
        # no sell order filled, available USDT increased
        assert pre_usdt_portfolio <= post_usdt_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - len(offline_filled)

        # back online: restore orders according to current price
        # simulate current price as back to 220: should quickly buy BTC sold between 250 and 220 to be able to
        # create sell orders between 220 and 250
        price = decimal.Decimal(220)
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        with _assert_missing_orders_count(producer, len(offline_filled)):
            await producer._ensure_staggered_orders()
        # restored orders
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USDT").available <= post_usdt_portfolio
        open_orders = trading_api.get_open_orders(exchange_manager)
        # restored 6 out of 10 sell orders
        assert len([order for order in open_orders if order.side is trading_enums.TradeOrderSide.SELL]) == 25 - 10 + 6
        # created 4 additional buy orders
        assert len([order for order in open_orders if order.side is trading_enums.TradeOrderSide.BUY]) == 25 + 4
        _check_created_orders(producer, trading_api.get_open_orders(exchange_manager), 200)


async def test_start_after_offline_1_filled_should_create_buy():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        price = decimal.Decimal("26616.7")
        producer.flat_spread = decimal.Decimal(275)
        producer.flat_increment = decimal.Decimal(125)
        producer.buy_orders_count = 30
        producer.sell_orders_count = 30

        orders_count = producer.buy_orders_count + producer.sell_orders_count

        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == orders_count
        pre_btc_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        pre_usdt_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USDT").available

        # offline simulation: orders get filled but not replaced => price moved to 26756.2
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled = [
            o
            for o in open_orders
            if o.side == trading_enums.TradeOrderSide.SELL and o.origin_price <= decimal.Decimal("26756.2")
        ]
        # this is 1 order
        assert len(offline_filled) == 1
        assert offline_filled[0].origin_price == decimal.Decimal("26754.2")
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        post_btc_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        post_usdt_portfolio = trading_api.get_portfolio_currency(exchange_manager, "USDT").available
        # buy orders filled: available BTC is constant
        assert pre_btc_portfolio == post_btc_portfolio
        # no sell order filled, available USDT increased
        assert pre_usdt_portfolio <= post_usdt_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - len(offline_filled)

        # back online: restore orders according to current price
        # simulate current price at 26753.8
        price = decimal.Decimal("26753.8")
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        with _assert_missing_orders_count(producer, 1):
            await producer._ensure_staggered_orders()
        # restored orders
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        assert 0 <= trading_api.get_portfolio_currency(exchange_manager, "USDT").available <= post_usdt_portfolio
        open_orders = trading_api.get_open_orders(exchange_manager)
        # 1 sell order is filled
        assert len([order for order in open_orders if order.side is trading_enums.TradeOrderSide.SELL]) == 30 - 1
        # 1 buy order is added
        assert len([order for order in open_orders if order.side is trading_enums.TradeOrderSide.BUY]) == 30 + 1
        _check_created_orders(producer, trading_api.get_open_orders(exchange_manager), decimal.Decimal("26616.7"))


async def test_start_after_offline_1_filled_should_create_sell():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        price = decimal.Decimal("26616.7")
        producer.flat_spread = decimal.Decimal(275)
        producer.flat_increment = decimal.Decimal(125)
        producer.buy_orders_count = 30
        producer.sell_orders_count = 30

        orders_count = producer.buy_orders_count + producer.sell_orders_count

        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == orders_count
        # offline simulation: orders get filled but not replaced => price moved to 26756.2
        open_orders = trading_api.get_open_orders(exchange_manager)
        offline_filled = [
            o
            for o in open_orders
            if o.side == trading_enums.TradeOrderSide.BUY and o.origin_price >= decimal.Decimal("26459.2")
        ]
        # this is 1 order
        assert len(offline_filled) == 1
        assert offline_filled[0].origin_price == decimal.Decimal("26479.2")
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - len(offline_filled)

        # back online: restore orders according to current price
        # simulate current price at 26409.2
        price = decimal.Decimal("26409.2")
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        with _assert_missing_orders_count(producer, 1):
            await producer._ensure_staggered_orders()
        # restored orders
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        open_orders = trading_api.get_open_orders(exchange_manager)
        # 1 sell order is filled
        assert len([order for order in open_orders if order.side is trading_enums.TradeOrderSide.SELL]) == 30 + 1
        # 1 buy order is added
        assert len([order for order in open_orders if order.side is trading_enums.TradeOrderSide.BUY]) == 30 - 1
        _check_created_orders(producer, trading_api.get_open_orders(exchange_manager), decimal.Decimal("26616.7"))


async def test_start_after_offline_with_added_funds_increasing_orders_count():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        producer.sell_funds = decimal.Decimal("0.00005")  # 4 sell orders
        producer.buy_funds = decimal.Decimal("0.005")  # 4 buy orders

        # first start: setup orders
        orders_count = 4 + 4

        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == orders_count

        initial_buy_orders_average_cost = numpy.mean(
            [o.total_cost for o in original_orders if o.side == trading_enums.TradeOrderSide.BUY]
        )
        initial_sell_orders_average_cost = numpy.mean(
            [o.total_cost for o in original_orders if o.side == trading_enums.TradeOrderSide.SELL]
        )
        previous_orders = original_orders
        # 1. offline simulation: nothing happens: orders are not replaced
        with _assert_missing_orders_count(producer, 0):
            await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        assert all(order.is_open() for order in previous_orders)

        # 2. offline simulation: funds are added (here config changed)
        producer.sell_funds = decimal.Decimal("0.0001")  # 9 sell orders
        # triggering orders will cancel all open orders and recreate grid orders with new funds
        await producer._ensure_staggered_orders()
        # one more buy order
        new_orders_count = orders_count + 5
        await asyncio.create_task(_check_open_orders_count(exchange_manager, new_orders_count))
        new_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(new_orders) == new_orders_count
        # replaced orders
        assert new_orders[0] is not original_orders[0]
        assert all(order.is_cancelled() for order in original_orders)

        updated_buy_orders_average_cost = numpy.mean(
            [o.total_cost for o in new_orders if o.side == trading_enums.TradeOrderSide.BUY]
        )
        updated_sell_orders_average_cost = numpy.mean(
            [o.total_cost for o in new_orders if o.side == trading_enums.TradeOrderSide.SELL]
        )
        # use approx same order size
        assert initial_buy_orders_average_cost * decimal.Decimal(str(0.9)) < \
               updated_buy_orders_average_cost < \
               initial_buy_orders_average_cost * decimal.Decimal(str(1.1))
        assert initial_sell_orders_average_cost * decimal.Decimal(str(0.9)) < \
               updated_sell_orders_average_cost < \
               initial_sell_orders_average_cost * decimal.Decimal(str(1.1))

        # 3. offline simulation: funds are added (here config changed)
        producer.sell_funds = decimal.Decimal("1")  # 25 sell orders
        producer.buy_funds = decimal.Decimal("0.01")  # 9 sell orders
        # triggering orders will cancel all open orders and recreate grid orders with new funds
        await producer._ensure_staggered_orders()
        # one more buy order
        new_orders_count = 34
        await asyncio.create_task(_check_open_orders_count(exchange_manager, new_orders_count))
        new_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(new_orders) == new_orders_count
        # replaced orders
        assert new_orders[0] is not original_orders[0]
        assert all(order.is_cancelled() for order in original_orders)


async def test_start_after_offline_with_added_funds_increasing_order_sizes():
    symbol = "BTC/USDT"
    async with _get_tools(symbol) as (producer, _, exchange_manager):
        # first start: setup orders
        orders_count = 19 + 25

        price = 100
        trading_api.force_set_mark_price(exchange_manager, producer.symbol, price)
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        original_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(original_orders) == orders_count

        initial_buy_orders_average_cost = numpy.mean(
            [o.total_cost for o in original_orders if o.side == trading_enums.TradeOrderSide.BUY]
        )
        initial_sell_orders_average_cost = numpy.mean(
            [o.total_cost for o in original_orders if o.side == trading_enums.TradeOrderSide.SELL]
        )
        # offline simulation: funds are added
        def _increase_funds(asset, multiplier):
            asset.available = asset.available + asset.total * decimal.Decimal(str(multiplier - 1))
            asset.total = asset.total * decimal.Decimal(str(multiplier))
            return asset

        portfolio = exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio
        portfolio["BTC"] = _increase_funds(portfolio["BTC"], 2)
        portfolio["USDT"] = _increase_funds(portfolio["USDT"], 4)

        # triggering orders will cancel all open orders and recreate grid orders with new funds
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        new_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(new_orders) == orders_count
        # replaced orders
        assert new_orders[0] is not original_orders[0]
        assert all(order.is_cancelled() for order in original_orders)

        updated_buy_orders_average_cost = numpy.mean(
            [o.total_cost for o in new_orders if o.side == trading_enums.TradeOrderSide.BUY]
        )
        updated_sell_orders_average_cost = numpy.mean(
            [o.total_cost for o in new_orders if o.side == trading_enums.TradeOrderSide.SELL]
        )
        assert initial_buy_orders_average_cost * decimal.Decimal(str(3.5)) < \
               updated_buy_orders_average_cost < \
               initial_buy_orders_average_cost * decimal.Decimal(str(4.5))
        assert initial_sell_orders_average_cost * decimal.Decimal(str(1.5)) < \
               updated_sell_orders_average_cost < \
               initial_sell_orders_average_cost * decimal.Decimal(str(2.5))

        # increase again (2x BTC)
        portfolio["BTC"] = _increase_funds(portfolio["BTC"], 2)
        previous_orders = new_orders
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        new_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(new_orders) == orders_count
        # replaced orders
        assert new_orders[0] is not previous_orders[0]
        assert all(order.is_cancelled() for order in previous_orders)

        updated_buy_orders_average_cost = numpy.mean(
            [o.total_cost for o in new_orders if o.side == trading_enums.TradeOrderSide.BUY]
        )
        updated_sell_orders_average_cost = numpy.mean(
            [o.total_cost for o in new_orders if o.side == trading_enums.TradeOrderSide.SELL]
        )
        assert initial_buy_orders_average_cost * decimal.Decimal(str(3.5)) < \
               updated_buy_orders_average_cost < \
               initial_buy_orders_average_cost * decimal.Decimal(str(4.5))
        assert initial_sell_orders_average_cost * decimal.Decimal(str(1.5)) * decimal.Decimal(2) \
               < updated_sell_orders_average_cost < \
               initial_sell_orders_average_cost * decimal.Decimal(str(2.5)) * decimal.Decimal(2)

        # increase again (1.1x BTC)
        portfolio["BTC"] = _increase_funds(portfolio["BTC"], decimal.Decimal("1.1"))
        previous_orders = new_orders
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        new_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(new_orders) == orders_count
        # did not replace orders funds increase is not significant enough
        assert new_orders[0] is previous_orders[0]
        assert all(order.is_open() for order in previous_orders)

        # increase again (12x USDT)
        portfolio["USDT"] = _increase_funds(portfolio["USDT"], decimal.Decimal("12"))
        previous_orders = new_orders
        producer.allow_order_funds_redispatch = False
        await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        new_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(new_orders) == orders_count
        # did not replace orders: allow_order_funds_redispatch is False
        assert new_orders[0] is previous_orders[0]
        assert all(order.is_open() for order in previous_orders)
        producer.allow_order_funds_redispatch = True

        # fill orders before check
        pre_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        offline_filled = [o for o in new_orders if o.side == trading_enums.TradeOrderSide.BUY][:2]
        for order in offline_filled:
            await _fill_order(order, exchange_manager, trigger_update_callback=False, producer=producer)
        post_portfolio = trading_api.get_portfolio_currency(exchange_manager, "BTC").available
        assert pre_portfolio < post_portfolio
        assert len(trading_api.get_open_orders(exchange_manager)) == orders_count - len(offline_filled)
        with _assert_missing_orders_count(producer, len(offline_filled)):
            await producer._ensure_staggered_orders()
        await asyncio.create_task(_check_open_orders_count(exchange_manager, orders_count))
        new_orders = copy.copy(trading_api.get_open_orders(exchange_manager))
        assert len(new_orders) == orders_count
        # replaced orders
        assert new_orders[0] is not previous_orders[0]
        assert all(order.is_cancelled() for order in previous_orders if order not in offline_filled)

        updated_buy_orders_average_cost = numpy.mean(
            [o.total_cost for o in new_orders if o.side == trading_enums.TradeOrderSide.BUY]
        )
        updated_sell_orders_average_cost = numpy.mean(
            [o.total_cost for o in new_orders if o.side == trading_enums.TradeOrderSide.SELL]
        )
        assert initial_buy_orders_average_cost * decimal.Decimal(str(3.5)) * decimal.Decimal(12) < \
               updated_buy_orders_average_cost < \
               initial_buy_orders_average_cost * decimal.Decimal(str(4.5)) * decimal.Decimal(12)
        assert initial_sell_orders_average_cost * decimal.Decimal(str(1.5)) * decimal.Decimal(2) \
               < updated_sell_orders_average_cost < \
               initial_sell_orders_average_cost * decimal.Decimal(str(2.5)) * decimal.Decimal(2)


@contextlib.contextmanager
def _assert_adapt_order_quantity_because_fees(get_fees_for_currency=False):
    _origin_decimal_adapt_order_quantity_because_fees = trading_personal_data.decimal_adapt_order_quantity_because_fees

    with mock.patch.object(
        trading_personal_data, "decimal_adapt_order_quantity_because_fees",
        mock.Mock(side_effect=_origin_decimal_adapt_order_quantity_because_fees)
    ) as decimal_adapt_order_quantity_because_fees_mock:
        if get_fees_for_currency is None:
            yield decimal_adapt_order_quantity_because_fees_mock
        else:
            with mock.patch.object(
                trading_personal_data, "get_fees_for_currency",
                mock.Mock(side_effect=get_fees_for_currency)
            ):
                yield decimal_adapt_order_quantity_because_fees_mock


@contextlib.contextmanager
def _assert_missing_orders_count(trading_mode_producer, expected_count):
    origin_analyse_current_orders_situation = trading_mode_producer._analyse_current_orders_situation
    missing_orders = []

    def _local_analyse_current_orders_situation(*args, **kwargs):
        return_vals = origin_analyse_current_orders_situation(*args, **kwargs)
        created_missing_orders = return_vals[0]
        for order in created_missing_orders:
            missing_orders.append(order)
        return return_vals

    with mock.patch.object(trading_mode_producer, "_analyse_current_orders_situation", mock.Mock(
        side_effect=_local_analyse_current_orders_situation
    )) as _local_analyse_current_orders_situation_mock:
        yield
        _local_analyse_current_orders_situation_mock.assert_called_once()
        assert len(missing_orders) == expected_count


async def _wait_for_orders_creation(orders_count=1):
    for _ in range(orders_count):
        await asyncio_tools.wait_asyncio_next_cycle()


async def _check_open_orders_count(exchange_manager, count):
    await _wait_for_orders_creation(count)
    assert len(trading_api.get_open_orders(exchange_manager)) == count


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


def _check_created_orders(producer, orders, initial_price):
    previous_order = None
    sorted_orders = sorted(orders, key=lambda o: o.origin_price)
    for order in sorted_orders:
        # price
        if previous_order:
            if previous_order.side == order.side:
                assert order.origin_price == previous_order.origin_price + producer.flat_increment
            else:
                assert order.origin_price == previous_order.origin_price + producer.flat_spread
        previous_order = order
    min_price = max(
        0,
        decimal.Decimal(str(initial_price)) - producer.flat_spread / 2
        - (producer.flat_increment * (producer.buy_orders_count - 1))
    )
    max_price = decimal.Decimal(str(initial_price)) + producer.flat_spread / 2 + \
                (producer.flat_increment * (producer.sell_orders_count - 1))
    assert min_price <= sorted_orders[0].origin_price <= max_price
    assert min_price <= sorted_orders[-1].origin_price <= max_price
