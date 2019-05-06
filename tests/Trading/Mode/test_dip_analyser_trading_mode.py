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
import ccxt
import time
import asyncio

from config import OrderStatus, TradeOrderSide
from evaluator.Util.advanced_manager import AdvancedManager
from evaluator.cryptocurrency_evaluator import CryptocurrencyEvaluator
from evaluator.evaluator_creator import EvaluatorCreator
from evaluator.symbol_evaluator import SymbolEvaluator
from tests.test_utils.config import load_test_config
from trading.exchanges.exchange_manager import ExchangeManager
from trading.trader.modes import DipAnalyserTradingMode
from trading.trader.portfolio import Portfolio
from trading.trader.trader_simulator import TraderSimulator


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def _get_tools():
    symbol = "BTC/USDT"
    exchange_traders = {}
    exchange_traders2 = {}
    config = load_test_config()
    AdvancedManager.create_class_list(config)
    exchange_manager = ExchangeManager(config, ccxt.binance, is_simulated=True)
    await exchange_manager.initialize()
    exchange_inst = exchange_manager.get_exchange()
    trader = TraderSimulator(config, exchange_inst, 0.3)
    await trader.initialize()
    trader.stop_order_manager()
    trader_inst2 = TraderSimulator(config, exchange_inst, 0.3)
    await trader_inst2.initialize()
    trader_inst2.stop_order_manager()
    crypto_currency_evaluator = CryptocurrencyEvaluator(config, "Bitcoin", [])
    symbol_evaluator = SymbolEvaluator(config, symbol, crypto_currency_evaluator)
    exchange_traders[exchange_inst.get_name()] = trader
    exchange_traders2[exchange_inst.get_name()] = trader_inst2
    symbol_evaluator.set_trader_simulators(exchange_traders)
    symbol_evaluator.set_traders(exchange_traders2)
    symbol_evaluator.strategies_eval_lists[exchange_inst.get_name()] = \
        EvaluatorCreator.create_strategies_eval_list(config)

    trading_mode = DipAnalyserTradingMode(config, exchange_inst)
    trader.register_trading_mode(trading_mode)
    trading_mode.add_symbol_evaluator(symbol_evaluator)
    decider = trading_mode.get_only_decider_key(symbol)
    creator_key = trading_mode.get_only_creator_key(symbol)
    creator = trading_mode.get_creator(symbol, creator_key)

    dip_strategy_evaluator = symbol_evaluator.strategies_eval_lists[exchange_inst.get_name()][0]

    trader.portfolio.portfolio["USDT"] = {
        Portfolio.TOTAL: 2000,
        Portfolio.AVAILABLE: 2000
    }
    return decider, creator, dip_strategy_evaluator, trader


async def test_init():
    decider, creator, _, trader = await _get_tools()

    # trading mode
    assert decider.trading_mode == creator.trading_mode

    # decider
    assert decider.volume_weight is None
    assert decider.volume_weight == decider.price_weight
    assert decider.last_buy_candle == {
        "Simulator": None,
        "Real": None
    }
    assert decider.first_trigger
    assert decider.sell_targets_by_order == {}
    assert decider.sell_orders_per_buy == 3

    # creator
    assert creator.PRICE_WEIGH_TO_PRICE_PERCENT == {
        1: 1.04,
        2: 1.07,
        3: 1.1,
    }
    assert creator.VOLUME_WEIGH_TO_VOLUME_PERCENT == {
        1: 0.5,
        2: 0.7,
        3: 1,
    }


async def test_create_bottom_order():
    decider, creator, _, trader = await _get_tools()
    _, _, market_quantity, price, _ = \
        await creator.get_pre_order_data(trader.exchange, decider.symbol, trader.portfolio)
    decider.volume_weight = 1
    risk_multiplier = 1.1
    await decider._create_bottom_order(1)
    open_orders = trader.get_order_manager().get_open_orders()
    assert len(open_orders) == 1

    order = open_orders[0]
    expected_quantity = market_quantity * risk_multiplier * \
        creator.VOLUME_WEIGH_TO_VOLUME_PERCENT[decider.volume_weight] * creator.SOFT_MAX_CURRENCY_RATIO
    assert round(order.get_origin_quantity(), 7) == round(expected_quantity, 7)
    expected_price = price * creator.LIMIT_PRICE_MULTIPLIER
    assert round(order.get_origin_price(), 7) == round(expected_price, 7)
    assert trader.portfolio.portfolio["USDT"][Portfolio.AVAILABLE] > 0
    assert decider._get_order_identifier(order) in decider.sell_targets_by_order


async def test_create_too_large_bottom_order():
    decider, creator, _, trader = await _get_tools()
    trader.portfolio.portfolio["USDT"] = {
        Portfolio.TOTAL: 200000000000000,
        Portfolio.AVAILABLE: 200000000000000
    }
    decider.volume_weight = 1
    await decider._create_bottom_order(1)
    open_orders = trader.get_order_manager().get_open_orders()
    assert len(open_orders) == 37
    assert trader.portfolio.portfolio["USDT"][Portfolio.AVAILABLE] > 0


async def test_create_too_small_bottom_order():
    decider, creator, _, trader = await _get_tools()
    trader.portfolio.portfolio["USDT"] = {
        Portfolio.TOTAL: 0.1,
        Portfolio.AVAILABLE: 0.1
    }
    decider.volume_weight = 1
    await decider._create_bottom_order(1)
    open_orders = trader.get_order_manager().get_open_orders()
    assert not open_orders
    assert trader.portfolio.portfolio["USDT"][Portfolio.AVAILABLE] == 0.1


async def test_create_bottom_order_replace_current():
    decider, creator, _, trader = await _get_tools()
    _, _, market_quantity, price, _ = \
        await creator.get_pre_order_data(trader.exchange, decider.symbol, trader.portfolio)
    decider.volume_weight = 1
    risk_multiplier = 1.1

    # first order
    await decider._create_bottom_order(1)
    open_orders = trader.get_order_manager().get_open_orders()
    assert len(open_orders) == 1

    first_order = open_orders[0]
    assert first_order.get_status() == OrderStatus.OPEN
    expected_quantity = market_quantity * risk_multiplier * \
        creator.VOLUME_WEIGH_TO_VOLUME_PERCENT[decider.volume_weight] * creator.SOFT_MAX_CURRENCY_RATIO
    assert round(first_order.get_origin_quantity(), 7) == round(expected_quantity, 7)
    expected_price = price * creator.LIMIT_PRICE_MULTIPLIER
    assert round(first_order.get_origin_price(), 7) == round(expected_price, 7)
    available_after_order = trader.portfolio.portfolio["USDT"][Portfolio.AVAILABLE]
    assert available_after_order > 0
    assert decider._get_order_identifier(first_order) in decider.sell_targets_by_order

    # second order, same weight
    await asyncio.sleep(0.001)  # sleep to generate unique order identifier
    await decider._create_bottom_order(1)
    assert len(open_orders) == 1

    second_order = open_orders[0]
    assert first_order.get_status() == OrderStatus.CANCELED
    assert second_order.get_status() == OrderStatus.OPEN
    assert second_order is not first_order
    assert round(second_order.get_origin_quantity(), 7) == round(first_order.get_origin_quantity(), 7)
    assert round(second_order.get_origin_price(), 7) == round(first_order.get_origin_price(), 7)
    assert trader.portfolio.portfolio["USDT"][Portfolio.AVAILABLE] == available_after_order
    assert decider._get_order_identifier(first_order) not in decider.sell_targets_by_order
    assert decider._get_order_identifier(second_order) in decider.sell_targets_by_order

    # third order, different weight
    decider.volume_weight = 3
    await asyncio.sleep(0.001)  # sleep to generate unique order identifier
    await decider._create_bottom_order(1)
    assert len(open_orders) == 1

    third_order = open_orders[0]
    assert second_order.get_status() == OrderStatus.CANCELED
    assert third_order.get_status() == OrderStatus.OPEN
    assert third_order is not second_order and third_order is not first_order
    expected_quantity = market_quantity * \
        creator.VOLUME_WEIGH_TO_VOLUME_PERCENT[decider.volume_weight] * creator.SOFT_MAX_CURRENCY_RATIO
    assert round(third_order.get_origin_quantity(), 7) != round(first_order.get_origin_quantity(), 7)
    assert round(third_order.get_origin_quantity(), 7) == round(expected_quantity, 7)
    assert round(third_order.get_origin_price(), 7) == round(first_order.get_origin_price(), 7)
    available_after_third_order = trader.portfolio.portfolio["USDT"][Portfolio.AVAILABLE]
    assert available_after_third_order < available_after_order
    assert decider._get_order_identifier(second_order) not in decider.sell_targets_by_order
    assert decider._get_order_identifier(third_order) in decider.sell_targets_by_order

    # fill third order
    await _fill_order(third_order, trader, order_update_callback=False)

    # fifth order: can't be placed: an order on this candle got filled
    decider.volume_weight = 3
    await asyncio.sleep(0.001)  # sleep to generate unique order identifier
    await decider._create_bottom_order(1)
    assert len(open_orders) == 0

    # fifth order: in the next candle
    decider.volume_weight = 2
    await asyncio.sleep(0.001)  # sleep to generate unique order identifier
    _, _, new_market_quantity, price, _ = \
        await creator.get_pre_order_data(trader.exchange, decider.symbol, trader.portfolio)
    await decider._create_bottom_order(2)
    assert len(open_orders) == 1

    fifth_order = open_orders[0]
    assert third_order.get_status() == OrderStatus.FILLED
    assert fifth_order.get_status() == OrderStatus.OPEN
    assert fifth_order is not third_order and fifth_order is not second_order and fifth_order is not first_order
    expected_quantity = new_market_quantity * risk_multiplier * \
        creator.VOLUME_WEIGH_TO_VOLUME_PERCENT[decider.volume_weight] * creator.SOFT_MAX_CURRENCY_RATIO
    assert round(fifth_order.get_origin_quantity(), 7) != round(first_order.get_origin_quantity(), 7)
    assert round(fifth_order.get_origin_quantity(), 7) != round(third_order.get_origin_quantity(), 7)
    assert round(fifth_order.get_origin_quantity(), 7) == round(expected_quantity, 7)
    assert round(fifth_order.get_origin_price(), 7) == round(first_order.get_origin_price(), 7)
    assert trader.portfolio.portfolio["USDT"][Portfolio.AVAILABLE] < available_after_third_order
    assert decider._get_order_identifier(first_order) not in decider.sell_targets_by_order
    assert decider._get_order_identifier(second_order) not in decider.sell_targets_by_order

    # third_order still in _get_order_identifier to keep history
    assert decider._get_order_identifier(third_order) in decider.sell_targets_by_order
    assert decider._get_order_identifier(fifth_order) in decider.sell_targets_by_order


async def test_create_sell_orders():
    decider, creator, _, trader = await _get_tools()
    sell_quantity = 5
    sell_target = 2
    buy_price = 100
    await decider._create_order(trader, False, sell_quantity, sell_target, buy_price)
    open_orders = trader.get_order_manager().get_open_orders()
    assert len(open_orders) == decider.sell_orders_per_buy
    assert all(o.get_status() == OrderStatus.OPEN for o in open_orders)
    assert all(o.get_side() == TradeOrderSide.SELL for o in open_orders)
    total_sell_quantity = sum(o.get_origin_quantity() for o in open_orders)
    assert sell_quantity*0.9999 <= total_sell_quantity <= sell_quantity

    max_price = buy_price * creator.PRICE_WEIGH_TO_PRICE_PERCENT[sell_target]
    increment = (max_price - buy_price) / decider.sell_orders_per_buy
    assert round(open_orders[0].get_origin_price(), 7) == round(buy_price + increment, 7)
    assert round(open_orders[1].get_origin_price(), 7) == round(buy_price + 2 * increment, 7)
    assert round(open_orders[2].get_origin_price(), 7) == round(buy_price + 3 * increment, 7)

    # now fill a sell order
    await _fill_order(open_orders[0], trader)
    assert len(open_orders) == decider.sell_orders_per_buy - 1
    sell_quantity = 3
    sell_target = 3
    buy_price = 2525
    await decider._create_order(trader, False, sell_quantity, sell_target, buy_price)
    open_orders = trader.get_order_manager().get_open_orders()
    assert len(open_orders) == decider.sell_orders_per_buy * 2 - 1
    assert all(o.get_status() == OrderStatus.OPEN for o in open_orders)
    assert all(o.get_side() == TradeOrderSide.SELL for o in open_orders)
    total_sell_quantity = sum(o.get_origin_quantity() for o in open_orders if o.get_origin_price() > 150)
    assert sell_quantity*0.9999 <= total_sell_quantity <= sell_quantity

    max_price = buy_price * creator.PRICE_WEIGH_TO_PRICE_PERCENT[sell_target]
    increment = (max_price - buy_price) / decider.sell_orders_per_buy
    assert round(open_orders[2+0].get_origin_price(), 7) == round(buy_price + increment, 7)
    assert round(open_orders[2+1].get_origin_price(), 7) == round(buy_price + 2 * increment, 7)
    assert round(open_orders[2+2].get_origin_price(), 7) == round(buy_price + 3 * increment, 7)

    # now fill a sell order
    await _fill_order(open_orders[-1], trader)
    assert len(open_orders) == decider.sell_orders_per_buy * 2 - 2


async def test_create_too_large_sell_orders():
    decider, creator, _, trader = await _get_tools()

    # case 1: too many orders to create: problem
    sell_quantity = 500000000
    sell_target = 2
    buy_price = 10000000
    trader.portfolio.portfolio["BTC"] = {
        Portfolio.TOTAL: sell_quantity,
        Portfolio.AVAILABLE: sell_quantity
    }
    await decider._create_order(trader, False, sell_quantity, sell_target, buy_price)
    open_orders = trader.get_order_manager().get_open_orders()
    assert not open_orders

    # case 2: create split sell orders
    sell_quantity = 5000000
    sell_target = 2
    buy_price = 3000000
    await decider._create_order(trader, False, sell_quantity, sell_target, buy_price)
    assert len(open_orders) == 17
    assert all(o.get_status() == OrderStatus.OPEN for o in open_orders)
    assert all(o.get_side() == TradeOrderSide.SELL for o in open_orders)
    total_sell_quantity = sum(o.get_origin_quantity() for o in open_orders)
    assert sell_quantity*0.9999 <= total_sell_quantity <= sell_quantity

    max_price = buy_price * creator.PRICE_WEIGH_TO_PRICE_PERCENT[sell_target]
    increment = (max_price - buy_price) / 17
    assert round(open_orders[0].get_origin_price(), 7) == round(buy_price + increment, 7)
    assert round(open_orders[-1].get_origin_price(), 7) == round(max_price, 7)


async def test_create_too_small_sell_orders():
    decider, creator, _, trader = await _get_tools()

    # case 1: not enough to create any order: problem
    sell_quantity = 0.001
    sell_target = 2
    buy_price = 0.001
    await decider._create_order(trader, False, sell_quantity, sell_target, buy_price)
    open_orders = trader.get_order_manager().get_open_orders()
    assert not open_orders

    # case 2: create less than 3 orders: 1 order
    sell_quantity = 0.1
    sell_target = 2
    buy_price = 0.01
    await decider._create_order(trader, False, sell_quantity, sell_target, buy_price)
    assert len(open_orders) == 1
    assert all(o.get_status() == OrderStatus.OPEN for o in open_orders)
    assert all(o.get_side() == TradeOrderSide.SELL for o in open_orders)
    total_sell_quantity = sum(o.get_origin_quantity() for o in open_orders)
    assert sell_quantity*0.9999 <= total_sell_quantity <= sell_quantity

    max_price = buy_price * creator.PRICE_WEIGH_TO_PRICE_PERCENT[sell_target]
    assert round(open_orders[0].get_origin_price(), 7) == round(max_price, 7)

    # case 3: create less than 3 orders: 2 orders
    sell_quantity = 0.2
    sell_target = 2
    buy_price = 0.01
    await decider._create_order(trader, False, sell_quantity, sell_target, buy_price)
    assert len(open_orders) == 3
    assert all(o.get_status() == OrderStatus.OPEN for o in open_orders)
    assert all(o.get_side() == TradeOrderSide.SELL for o in open_orders)
    second_total_sell_quantity = sum(o.get_origin_quantity() for o in open_orders if o.get_origin_price() >= 0.0107)
    assert sell_quantity*0.9999 <= second_total_sell_quantity <= sell_quantity

    max_price = buy_price * creator.PRICE_WEIGH_TO_PRICE_PERCENT[sell_target]
    increment = (max_price - buy_price) / 2
    assert round(open_orders[1].get_origin_price(), 7) == round(buy_price + increment, 7)
    assert round(open_orders[2].get_origin_price(), 7) == round(max_price, 7)


async def test_order_fill_callback():
    decider, creator, _, trader = await _get_tools()
    decider.volume_weight = 1
    decider.price_weight = 1
    await decider._create_bottom_order(1)
    open_orders = trader.get_order_manager().get_open_orders()
    assert len(open_orders) == 1

    # change weights to ensure no interference
    decider.volume_weight = 3
    decider.price_weight = 3

    to_fill_order = open_orders[0]
    await _fill_order(to_fill_order, trader)

    assert to_fill_order.get_status() == OrderStatus.FILLED
    assert len(open_orders) == decider.sell_orders_per_buy
    assert all(o.get_status() == OrderStatus.OPEN for o in open_orders)
    assert all(o.get_side() == TradeOrderSide.SELL for o in open_orders)
    total_sell_quantity = sum(o.get_origin_quantity() for o in open_orders)
    assert to_fill_order.get_origin_quantity()*0.9999 <= total_sell_quantity <= to_fill_order.get_origin_quantity()

    price = to_fill_order.get_filled_price()
    max_price = price * creator.PRICE_WEIGH_TO_PRICE_PERCENT[1]
    increment = (max_price - price) / decider.sell_orders_per_buy
    assert round(open_orders[0].get_origin_price(), 7) == round(price + increment, 7)
    assert round(open_orders[1].get_origin_price(), 7) == round(price + 2 * increment, 7)
    assert round(open_orders[2].get_origin_price(), 7) == round(price + 3 * increment, 7)

    # now fill a sell order
    await _fill_order(open_orders[0], trader)
    assert len(open_orders) == decider.sell_orders_per_buy - 1

    # new buy order
    await decider._create_bottom_order(2)
    open_orders = trader.get_order_manager().get_open_orders()
    assert len(open_orders) == decider.sell_orders_per_buy


async def _fill_order(order, trader, trigger_price=None, order_update_callback=True):
    if trigger_price is None:
        trigger_price = order.origin_price * 0.99 if order.side == TradeOrderSide.BUY else order.origin_price * 1.01
    recent_trades = [{"price": trigger_price, "timestamp": time.time()}]
    order.last_prices = recent_trades
    errors = []
    initial_len = len(trader.get_order_manager().get_open_orders())
    if await trader.get_order_manager()._update_order_status(order, errors):
        assert len(trader.get_order_manager().get_open_orders()) == initial_len - 1
        if order_update_callback:
            await trader.get_order_manager().trader.call_order_update_callback(order)
