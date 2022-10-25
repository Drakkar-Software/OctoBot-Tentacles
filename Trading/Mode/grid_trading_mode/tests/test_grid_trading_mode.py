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
import decimal

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
import tentacles.Trading.Mode.grid_trading_mode.grid_trading as grid_trading
import tentacles.Trading.Mode.staggered_orders_trading_mode.staggered_orders_trading as staggered_orders_trading
import tests.test_utils.config as test_utils_config
import tests.test_utils.memory_check_util as memory_check_util
import tests.test_utils.test_exchanges as test_exchanges

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
    return mode, mode.producers[0]


async def _get_tools(symbol, btc_holdings=None, additional_portfolio={}, fees=None):
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

    return producer, mode.get_trading_mode_consumers()[0], exchange_manager


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


async def test_init_allowed_price_ranges():
    exchange_manager = None
    try:
        symbol = "BTC/USDT"
        producer, _, exchange_manager = await _get_tools(symbol)
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
    finally:
        await _stop(exchange_manager)


async def test_create_orders_without_enough_funds_for_all_orders_17_total_orders():
    exchange_manager = None
    try:
        symbol = "BTC/USDT"
        producer, _, exchange_manager = await _get_tools(symbol)

        producer.sell_funds = decimal.Decimal("0.00006")  # 5 orders
        producer.buy_funds = decimal.Decimal("0.5")  # 12 orders

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
        await asyncio.create_task(_check_open_orders_count(exchange_manager, 5 + 12))
        created_orders = trading_api.get_open_orders(exchange_manager)
        created_buy_orders = [o for o in created_orders if o.side is trading_enums.TradeOrderSide.BUY]
        created_sell_orders = [o for o in created_orders if o.side is trading_enums.TradeOrderSide.SELL]
        assert len(created_buy_orders) < producer.buy_orders_count
        assert len(created_buy_orders) == 12
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
    finally:
        await _stop(exchange_manager)


async def test_create_orders_without_enough_funds_for_all_orders_3_total_orders():
    exchange_manager = None
    try:
        symbol = "BTC/USDT"
        producer, _, exchange_manager = await _get_tools(symbol)

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
    finally:
        await _stop(exchange_manager)


async def test_create_orders_with_fixed_volume_per_order():
    exchange_manager = None
    try:
        symbol = "BTC/USDT"
        producer, _, exchange_manager = await _get_tools(symbol)

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
    finally:
        await _stop(exchange_manager)


async def _wait_for_orders_creation(orders_count=1):
    for _ in range(orders_count):
        await asyncio_tools.wait_asyncio_next_cycle()


async def _check_open_orders_count(exchange_manager, count):
    await _wait_for_orders_creation(count)
    assert len(trading_api.get_open_orders(exchange_manager)) == count
