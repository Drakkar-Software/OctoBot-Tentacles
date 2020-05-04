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
from os.path import join
from asyncio import create_task

from octobot_backtesting.api.backtesting import initialize_backtesting, get_importers
from octobot_backtesting.api.importer import stop_importer
from octobot_channels.util.channel_creator import create_all_subclasses_channel
from octobot_commons.constants import PORTFOLIO_AVAILABLE, PORTFOLIO_TOTAL
from octobot_commons.tests.test_config import load_test_config, TEST_CONFIG_FOLDER
from octobot_trading.api.orders import get_open_orders
from octobot_trading.api.symbol_data import force_set_mark_price
from octobot_trading.channels.exchange_channel import ExchangeChannel, TimeFrameExchangeChannel, set_chan
from octobot_trading.constants import CONFIG_SIMULATOR, CONFIG_STARTING_PORTFOLIO
from octobot_trading.enums import OrderStatus, TradeOrderSide
from octobot_trading.exchanges.exchange_manager import ExchangeManager
from octobot_trading.exchanges.exchange_simulator import ExchangeSimulator
from octobot_trading.exchanges.rest_exchange import RestExchange
from octobot_trading.traders.trader_simulator import TraderSimulator
from tentacles.Trading.Mode import DipAnalyserTradingMode

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def _get_tools(symbol="BTC/USDT"):
    config = load_test_config()
    config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO]["USDT"] = 2000
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

    mode = DipAnalyserTradingMode(config, exchange_manager)
    mode.symbol = None if mode.get_is_symbol_wildcard() else symbol
    await mode.initialize()

    # set BTC/USDT price at 1000 USDT
    force_set_mark_price(exchange_manager, symbol, 1000)

    return mode.producers[0], mode.consumers[0], trader


async def _stop(trader):
    for importer in get_importers(trader.exchange_manager.exchange.backtesting):
        await stop_importer(importer)
    await trader.exchange_manager.stop()


async def test_init():
    try:
        producer, consumer, trader = await _get_tools()

        # trading mode
        assert producer.trading_mode is consumer.trading_mode
        assert producer.trading_mode.sell_orders_per_buy == 3

        # producer
        assert producer.last_buy_candle is None
        assert producer.first_trigger

        # consumer
        assert consumer.sell_targets_by_order_id == {}
        assert consumer.PRICE_WEIGH_TO_PRICE_PERCENT == {
            1: 1.04,
            2: 1.07,
            3: 1.1,
        }
        assert consumer.VOLUME_WEIGH_TO_VOLUME_PERCENT == {
            1: 0.5,
            2: 0.7,
            3: 1,
        }
    finally:
        await _stop(trader)


async def test_create_bottom_order():
    try:
        producer, consumer, trader = await _get_tools()

        price = 1000
        market_quantity = 2
        volume_weight = 1
        risk_multiplier = 1.1
        await producer._create_bottom_order(1, volume_weight, 1)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 1))

        order = get_open_orders(trader.exchange_manager)[0]
        expected_quantity = market_quantity * risk_multiplier * \
            consumer.VOLUME_WEIGH_TO_VOLUME_PERCENT[volume_weight] * \
            consumer.SOFT_MAX_CURRENCY_RATIO
        assert round(order.origin_quantity, 7) == round(expected_quantity, 7)
        expected_price = price * consumer.LIMIT_PRICE_MULTIPLIER
        assert round(order.origin_price, 7) == round(expected_price, 7)
        portfolio = trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio
        assert portfolio["USDT"][PORTFOLIO_AVAILABLE] > 0
        assert order.order_id in consumer.sell_targets_by_order_id
    finally:
        await _stop(trader)


async def test_create_too_large_bottom_order():
    try:
        producer, consumer, trader = await _get_tools()

        portfolio = trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio
        portfolio.portfolio["USDT"] = {
            PORTFOLIO_TOTAL: 200000000000000,
            PORTFOLIO_AVAILABLE: 200000000000000
        }
        await producer._create_bottom_order(1, 1, 1)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 37))
        assert portfolio.portfolio["USDT"][PORTFOLIO_AVAILABLE] > 0

    finally:
        await _stop(trader)


async def test_create_too_small_bottom_order():
    try:
        producer, consumer, trader = await _get_tools()

        portfolio = trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio
        portfolio.portfolio["USDT"] = {
            PORTFOLIO_TOTAL: 0.01,
            PORTFOLIO_AVAILABLE: 0.01
        }
        await producer._create_bottom_order(1, 1, 1)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 0))
        assert portfolio.portfolio["USDT"][PORTFOLIO_AVAILABLE] == 0.01

    finally:
        await _stop(trader)


async def test_create_bottom_order_replace_current():
    try:
        producer, consumer, trader = await _get_tools()

        price = 1000
        market_quantity = 2
        volume_weight = 1
        risk_multiplier = 1.1
        portfolio = trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio

        # first order
        await producer._create_bottom_order(1, volume_weight, 1)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 1))

        first_order = get_open_orders(trader.exchange_manager)[0]
        assert first_order.status == OrderStatus.OPEN
        expected_quantity = market_quantity * risk_multiplier * \
            consumer.VOLUME_WEIGH_TO_VOLUME_PERCENT[volume_weight] * consumer.SOFT_MAX_CURRENCY_RATIO
        assert round(first_order.origin_quantity, 7) == round(expected_quantity, 7)
        expected_price = price * consumer.LIMIT_PRICE_MULTIPLIER
        assert round(first_order.origin_price, 7) == round(expected_price, 7)
        available_after_order = portfolio.portfolio["USDT"][PORTFOLIO_AVAILABLE]
        assert available_after_order > 0
        assert first_order.order_id in consumer.sell_targets_by_order_id

        # second order, same weight
        await producer._create_bottom_order(1, volume_weight, 1)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 1))

        second_order = get_open_orders(trader.exchange_manager)[0]
        assert first_order.status == OrderStatus.CANCELED
        assert second_order.status == OrderStatus.OPEN
        assert second_order is not first_order
        assert round(second_order.origin_quantity, 7) == round(first_order.origin_quantity, 7)
        assert round(second_order.origin_price, 7) == round(first_order.origin_price, 7)
        assert portfolio.portfolio["USDT"][PORTFOLIO_AVAILABLE] == available_after_order
        assert first_order.order_id not in consumer.sell_targets_by_order_id
        assert second_order.order_id in consumer.sell_targets_by_order_id

        # third order, different weight
        volume_weight = 3
        await producer._create_bottom_order(1, volume_weight, 1)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 1))

        third_order = get_open_orders(trader.exchange_manager)[0]
        assert second_order.status == OrderStatus.CANCELED
        assert third_order.status == OrderStatus.OPEN
        assert third_order is not second_order and third_order is not first_order
        expected_quantity = market_quantity * \
            consumer.VOLUME_WEIGH_TO_VOLUME_PERCENT[volume_weight] * consumer.SOFT_MAX_CURRENCY_RATIO
        assert round(third_order.origin_quantity, 7) != round(first_order.origin_quantity, 7)
        assert round(third_order.origin_quantity, 7) == round(expected_quantity, 7)
        assert round(third_order.origin_price, 7) == round(first_order.origin_price, 7)
        available_after_third_order = portfolio.portfolio["USDT"][PORTFOLIO_AVAILABLE]
        assert available_after_third_order < available_after_order
        assert second_order.order_id not in consumer.sell_targets_by_order_id
        assert third_order.order_id in consumer.sell_targets_by_order_id

        # fill third order
        await _fill_order(third_order, trader, trigger_update_callback=False)

        # fourth order: can't be placed: an order on this candle got filled
        volume_weight = 3
        await producer._create_bottom_order(1, volume_weight, 1)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 0))

        # fifth order: in the next candle
        volume_weight = 2
        new_market_quantity = portfolio.portfolio["USDT"][PORTFOLIO_AVAILABLE] / price
        await producer._create_bottom_order(2, volume_weight, 1)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 1))

        fifth_order = get_open_orders(trader.exchange_manager)[0]
        assert third_order.status == OrderStatus.FILLED
        assert fifth_order.status == OrderStatus.OPEN
        assert fifth_order is not third_order and fifth_order is not second_order and fifth_order is not first_order
        expected_quantity = new_market_quantity * risk_multiplier * \
            consumer.VOLUME_WEIGH_TO_VOLUME_PERCENT[volume_weight] * consumer.SOFT_MAX_CURRENCY_RATIO
        assert round(fifth_order.origin_quantity, 7) != round(first_order.origin_quantity, 7)
        assert round(fifth_order.origin_quantity, 7) != round(third_order.origin_quantity, 7)
        assert round(fifth_order.origin_quantity, 7) == round(expected_quantity, 7)
        assert round(fifth_order.origin_price, 7) == round(first_order.origin_price, 7)
        assert portfolio.portfolio["USDT"][PORTFOLIO_AVAILABLE] < available_after_third_order
        assert first_order.order_id not in consumer.sell_targets_by_order_id
        assert second_order.order_id not in consumer.sell_targets_by_order_id

        # third_order still in _get_order_identifier to keep history
        assert third_order.order_id in consumer.sell_targets_by_order_id
        assert fifth_order.order_id in consumer.sell_targets_by_order_id
    finally:
        await _stop(trader)


async def test_create_sell_orders():
    try:
        producer, consumer, trader = await _get_tools()

        sell_quantity = 5
        sell_target = 2
        buy_price = 100
        order_id = "a"
        consumer.sell_targets_by_order_id[order_id] = sell_target
        await producer._create_sell_order_if_enabled(order_id, sell_quantity, buy_price)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, consumer.trading_mode.sell_orders_per_buy))
        open_orders = get_open_orders(trader.exchange_manager)
        assert all(o.status == OrderStatus.OPEN for o in open_orders)
        assert all(o.side == TradeOrderSide.SELL for o in open_orders)
        total_sell_quantity = sum(o.origin_quantity for o in open_orders)
        assert sell_quantity * 0.9999 <= total_sell_quantity <= sell_quantity

        max_price = buy_price * consumer.PRICE_WEIGH_TO_PRICE_PERCENT[sell_target]
        increment = (max_price - buy_price) / consumer.trading_mode.sell_orders_per_buy
        assert round(open_orders[0].origin_price, 7) == round(buy_price + increment, 7)
        assert round(open_orders[1].origin_price, 7) == round(buy_price + 2 * increment, 7)
        assert round(open_orders[2].origin_price, 7) == round(buy_price + 3 * increment, 7)

        # now fill a sell order
        await _fill_order(open_orders[0], trader, trigger_update_callback=False)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, consumer.trading_mode.sell_orders_per_buy - 1))
        sell_quantity = 3
        sell_target = 3
        buy_price = 2525
        order_id_2 = "b"
        consumer.sell_targets_by_order_id[order_id_2] = sell_target
        await producer._create_sell_order_if_enabled(order_id_2, sell_quantity, buy_price)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, consumer.trading_mode.sell_orders_per_buy * 2 - 1))
        open_orders = get_open_orders(trader.exchange_manager)
        assert all(o.status == OrderStatus.OPEN for o in open_orders)
        assert all(o.side == TradeOrderSide.SELL for o in open_orders)
        total_sell_quantity = sum(o.origin_quantity for o in open_orders if o.origin_price > 150)
        assert sell_quantity * 0.9999 <= total_sell_quantity <= sell_quantity

        max_price = buy_price * consumer.PRICE_WEIGH_TO_PRICE_PERCENT[sell_target]
        increment = (max_price - buy_price) / consumer.trading_mode.sell_orders_per_buy
        assert round(open_orders[2 + 0].origin_price, 7) == round(buy_price + increment, 7)
        assert round(open_orders[2 + 1].origin_price, 7) == round(buy_price + 2 * increment, 7)
        assert round(open_orders[2 + 2].origin_price, 7) == round(buy_price + 3 * increment, 7)

        # now fill a sell order
        await _fill_order(open_orders[-1], trader, trigger_update_callback=False)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, consumer.trading_mode.sell_orders_per_buy * 2 - 2))
    finally:
        await _stop(trader)


async def test_create_too_large_sell_orders():
    try:
        producer, consumer, trader = await _get_tools()

        # case 1: too many orders to create: problem
        sell_quantity = 500000000
        sell_target = 2
        buy_price = 10000000
        portfolio = trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio
        portfolio.portfolio["BTC"] = {
            PORTFOLIO_TOTAL: sell_quantity,
            PORTFOLIO_AVAILABLE: sell_quantity
        }
        order_id = "a"
        consumer.sell_targets_by_order_id[order_id] = sell_target
        await producer._create_sell_order_if_enabled(order_id, sell_quantity, buy_price)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 0))

        # case 2: create split sell orders
        sell_quantity = 5000000
        buy_price = 3000000
        await producer._create_sell_order_if_enabled(order_id, sell_quantity, buy_price)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 17))
        open_orders = get_open_orders(trader.exchange_manager)
        assert all(o.status == OrderStatus.OPEN for o in open_orders)
        assert all(o.side == TradeOrderSide.SELL for o in open_orders)
        total_sell_quantity = sum(o.origin_quantity for o in open_orders)
        assert sell_quantity * 0.9999 <= total_sell_quantity <= sell_quantity

        max_price = buy_price * consumer.PRICE_WEIGH_TO_PRICE_PERCENT[sell_target]
        increment = (max_price - buy_price) / 17
        assert round(open_orders[0].origin_price, 7) == round(buy_price + increment, 7)
        assert round(open_orders[-1].origin_price, 7) == round(max_price, 7)
    finally:
        await _stop(trader)


async def test_create_too_small_sell_orders():
    try:
        producer, consumer, trader = await _get_tools()

        # case 1: not enough to create any order: problem
        sell_quantity = 0.001
        sell_target = 2
        buy_price = 0.001
        order_id = "a"
        consumer.sell_targets_by_order_id[order_id] = sell_target
        await producer._create_sell_order_if_enabled(order_id, sell_quantity, buy_price)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 0))

        # case 2: create less than 3 orders: 1 order
        sell_quantity = 0.1
        buy_price = 0.01
        await producer._create_sell_order_if_enabled(order_id, sell_quantity, buy_price)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 1))
        open_orders = get_open_orders(trader.exchange_manager)
        assert len(open_orders) == 1
        assert all(o.status == OrderStatus.OPEN for o in open_orders)
        assert all(o.side == TradeOrderSide.SELL for o in open_orders)
        total_sell_quantity = sum(o.origin_quantity for o in open_orders)
        assert sell_quantity * 0.9999 <= total_sell_quantity <= sell_quantity

        max_price = buy_price * consumer.PRICE_WEIGH_TO_PRICE_PERCENT[sell_target]
        assert round(open_orders[0].origin_price, 7) == round(max_price, 7)

        # case 3: create less than 3 orders: 2 orders
        sell_quantity = 0.2
        sell_target = 2
        buy_price = 0.01
        # keep same order id to test no issue with it
        await producer._create_sell_order_if_enabled(order_id, sell_quantity, buy_price)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 3))
        open_orders = get_open_orders(trader.exchange_manager)
        assert all(o.status == OrderStatus.OPEN for o in open_orders)
        assert all(o.side == TradeOrderSide.SELL for o in open_orders)
        second_total_sell_quantity = sum(o.origin_quantity for o in open_orders if o.origin_price >= 0.0107)
        assert sell_quantity * 0.9999 <= second_total_sell_quantity <= sell_quantity

        max_price = buy_price * consumer.PRICE_WEIGH_TO_PRICE_PERCENT[sell_target]
        increment = (max_price - buy_price) / 2
        assert round(open_orders[1].origin_price, 7) == round(buy_price + increment, 7)
        assert round(open_orders[2].origin_price, 7) == round(max_price, 7)
    finally:
        await _stop(trader)


async def test_order_fill_callback():
    try:
        producer, consumer, trader = await _get_tools()

        volume_weight = 1
        price_weight = 1
        await producer._create_bottom_order(1, volume_weight, price_weight)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 1))

        # change weights to ensure no interference
        volume_weight = 3
        price_weight = 3

        open_orders = get_open_orders(trader.exchange_manager)
        to_fill_order = open_orders[0]
        await _fill_order(to_fill_order, trader, trading_mode=consumer.trading_mode)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, consumer.trading_mode.sell_orders_per_buy))

        assert to_fill_order.status == OrderStatus.FILLED
        open_orders = get_open_orders(trader.exchange_manager)
        assert all(o.status == OrderStatus.OPEN for o in open_orders)
        assert all(o.side == TradeOrderSide.SELL for o in open_orders)
        total_sell_quantity = sum(o.origin_quantity for o in open_orders)
        assert to_fill_order.origin_quantity * 0.95 <= total_sell_quantity <= to_fill_order.origin_quantity

        price = to_fill_order.filled_price
        max_price = price * consumer.PRICE_WEIGH_TO_PRICE_PERCENT[1]
        increment = (max_price - price) / consumer.trading_mode.sell_orders_per_buy
        assert round(open_orders[0].origin_price, 7) == round(price + increment, 7)
        assert round(open_orders[1].origin_price, 7) == round(price + 2 * increment, 7)
        assert round(open_orders[2].origin_price, 7) == round(price + 3 * increment, 7)

        # now fill a sell order
        await _fill_order(open_orders[0], trader, trading_mode=consumer.trading_mode)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, consumer.trading_mode.sell_orders_per_buy - 1))

        # new buy order
        await producer._create_bottom_order(2, volume_weight, price_weight)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, consumer.trading_mode.sell_orders_per_buy))
    finally:
        await _stop(trader)


async def test_order_fill_callback_not_in_db():
    try:
        producer, consumer, trader = await _get_tools()

        await producer._create_bottom_order(2, 1, 1)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 1))
        open_orders = get_open_orders(trader.exchange_manager)
        to_fill_order = open_orders[0]
        await _fill_order(to_fill_order, trader, trigger_update_callback=False)

        # remove order from db
        consumer.sell_targets_by_order_id = {}
        await consumer.trading_mode._order_notification_callback(None,
                                                                 trader.exchange_manager.id,
                                                                 None,
                                                                 symbol=to_fill_order.symbol,
                                                                 order=to_fill_order.to_dict(),
                                                                 is_from_bot=True,
                                                                 is_closed=True,
                                                                 is_updated=False)
        # create as task to allow creator's queue to get processed
        await create_task(_check_open_orders_count(trader, 3))
        open_orders = get_open_orders(trader.exchange_manager)

        assert all(o.status == OrderStatus.OPEN for o in open_orders)
        assert all(o.side == TradeOrderSide.SELL for o in open_orders)
        total_sell_quantity = sum(o.origin_quantity for o in open_orders)
        assert to_fill_order.origin_quantity * 0.95 <= total_sell_quantity <= to_fill_order.origin_quantity

        price = to_fill_order.filled_price
        max_price = price * consumer.PRICE_WEIGH_TO_PRICE_PERCENT[consumer.DEFAULT_SELL_TARGET]
        increment = (max_price - price) / consumer.trading_mode.sell_orders_per_buy
        assert round(open_orders[0].origin_price, 7) == round(price + increment, 7)
        assert round(open_orders[1].origin_price, 7) == round(price + 2 * increment, 7)
        assert round(open_orders[2].origin_price, 7) == round(price + 3 * increment, 7)
    finally:
        await _stop(trader)


async def _check_open_orders_count(trader, count):
    assert len(get_open_orders(trader.exchange_manager)) == count


async def _fill_order(order, trader, trigger_price=None, trigger_update_callback=True,
                      ignore_open_orders=False, trading_mode=None):
    if trigger_price is None:
        trigger_price = order.origin_price * 0.99 if order.side == TradeOrderSide.BUY else order.origin_price * 1.01
    last_prices = [{"price": trigger_price, "timestamp": time.time()}]
    initial_len = len(get_open_orders(trader.exchange_manager))
    await order.update_order_status(last_prices)
    if order.status == OrderStatus.FILLED:
        await order.close_order()
        if not ignore_open_orders:
            assert len(get_open_orders(trader.exchange_manager)) == initial_len - 1
        if trigger_update_callback:
            await trading_mode._order_notification_callback(None,
                                                            trader.exchange_manager.id,
                                                            None,
                                                            symbol=order.symbol,
                                                            order=order.to_dict(),
                                                            is_from_bot=True,
                                                            is_closed=True,
                                                            is_updated=False)
