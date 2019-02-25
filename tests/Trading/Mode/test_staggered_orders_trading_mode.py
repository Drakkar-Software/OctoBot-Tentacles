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
import copy

from config import ExchangeConstantsTickersInfoColumns, INIT_EVAL_NOTE, CONFIG_EVALUATOR, CONFIG_TRADING_TENTACLES, \
    EvaluatorStates, TradeOrderSide
from evaluator.Util.advanced_manager import AdvancedManager
from evaluator.cryptocurrency_evaluator import CryptocurrencyEvaluator
from evaluator.evaluator_creator import EvaluatorCreator
from evaluator.symbol_evaluator import SymbolEvaluator
from tests.test_utils.config import load_test_config
from trading.exchanges.exchange_manager import ExchangeManager
from trading.trader.modes import StaggeredOrdersTradingMode, StrategyModes, StrategyModeMultipliersDetails, \
    MULTIPLIER, INCREASING, AbstractTradingModeCreator
from trading.trader.trader_simulator import TraderSimulator
from trading.trader.portfolio import Portfolio


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def _get_tools():
    symbol = "BTC/USD"
    exchange_traders = {}
    exchange_traders2 = {}
    config = load_test_config()
    config[CONFIG_EVALUATOR]["FullMixedStrategiesEvaluator"] = False
    config[CONFIG_EVALUATOR]["StaggeredStrategiesEvaluator"] = True
    config[CONFIG_TRADING_TENTACLES]["DailyTradingMode"] = False
    config[CONFIG_TRADING_TENTACLES]["StaggeredOrdersTradingMode"] = True
    AdvancedManager.create_class_list(config)
    exchange_manager = ExchangeManager(config, ccxt.binance, is_simulated=True)
    await exchange_manager.initialize()
    exchange_inst = exchange_manager.get_exchange()
    trader_inst = TraderSimulator(config, exchange_inst, 0.3)
    await trader_inst.initialize()
    trader_inst.stop_order_manager()
    crypto_currency_evaluator = CryptocurrencyEvaluator(config, "Bitcoin", [])
    symbol_evaluator = SymbolEvaluator(config, symbol, crypto_currency_evaluator)
    exchange_traders[exchange_inst.get_name()] = trader_inst
    symbol_evaluator.set_trader_simulators(exchange_traders)
    symbol_evaluator.set_traders(exchange_traders2)
    symbol_evaluator.strategies_eval_lists[exchange_inst.get_name()] = \
        EvaluatorCreator.create_strategies_eval_list(config)

    trading_mode = StaggeredOrdersTradingMode(config, exchange_inst)
    trading_mode.add_symbol_evaluator(symbol_evaluator)
    final_evaluator = trading_mode.get_only_decider_key(symbol)

    trader_inst.register_trading_mode(trading_mode)

    staggered_strategy_evaluator = symbol_evaluator.strategies_eval_lists[exchange_inst.get_name()][0]

    trader_inst.portfolio.portfolio["USD"] = {
        Portfolio.TOTAL: 1000,
        Portfolio.AVAILABLE: 1000
    }
    trader_inst.portfolio.portfolio["BTC"] = {
        Portfolio.TOTAL: 10,
        Portfolio.AVAILABLE: 10
    }
    final_evaluator.lowest_buy = 1
    final_evaluator.highest_sell = 10000
    final_evaluator.operational_depth = 50

    return final_evaluator, trader_inst, staggered_strategy_evaluator


async def test_finalize():
    final_evaluator, trader_inst, staggered_strategy_evaluator = await _get_tools()
    assert final_evaluator.state == EvaluatorStates.NEUTRAL
    assert final_evaluator.final_eval == INIT_EVAL_NOTE
    assert not trader_inst.get_order_manager().get_open_orders()
    await final_evaluator.finalize()
    # no price info: do nothing
    assert final_evaluator.final_eval == INIT_EVAL_NOTE
    assert not trader_inst.get_order_manager().get_open_orders()

    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 4000}
    await final_evaluator.finalize()
    # price info: create trades
    assert final_evaluator.final_eval == 4000
    assert final_evaluator.state == EvaluatorStates.NEUTRAL
    assert trader_inst.get_order_manager().get_open_orders()


async def test_create_orders_without_existing_orders_symmetrical_case_all_modes_price_100():
    price = 100
    await _test_mode(StrategyModes.NEUTRAL, 25, 90, price)
    await _test_mode(StrategyModes.MOUNTAIN, 25, 121, price)
    await _test_mode(StrategyModes.VALLEY, 25, 26, price)
    await _test_mode(StrategyModes.BUY_SLOPE, 25, 121, price)
    await _test_mode(StrategyModes.SELL_SLOPE, 25, 26, price)


async def test_create_orders_without_existing_orders_symmetrical_case_all_modes_price_347():
    price = 347
    await _test_mode(StrategyModes.NEUTRAL, 25, 89, price)
    await _test_mode(StrategyModes.MOUNTAIN, 25, 113, price)
    await _test_mode(StrategyModes.VALLEY, 25, 30, price)
    await _test_mode(StrategyModes.BUY_SLOPE, 25, 113, price)
    await _test_mode(StrategyModes.SELL_SLOPE, 25, 30, price)


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


async def test_start_with_existing_valid_orders():
    final_evaluator, trader_inst, staggered_strategy_evaluator = await _get_tools()
    portfolio = trader_inst.get_portfolio().get_portfolio()
    assert not trader_inst.get_order_manager().get_open_orders()

    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 100}
    await final_evaluator.finalize()
    original_orders = copy.copy(trader_inst.get_order_manager().get_open_orders())
    assert len(original_orders) == final_evaluator.operational_depth

    # new evaluation, same price
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 100}
    await final_evaluator.finalize()
    # did nothing
    assert original_orders[0] is trader_inst.get_order_manager().get_open_orders()[0]
    assert original_orders[-1] is trader_inst.get_order_manager().get_open_orders()[-1]
    assert len(trader_inst.get_order_manager().get_open_orders()) == final_evaluator.operational_depth

    # new evaluation, price changed
    # -2 order would be filled
    to_fill_order = original_orders[-2]
    await _fill_order(to_fill_order, trader_inst, 95)
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 95}
    await final_evaluator.finalize()
    # did nothing
    assert len(original_orders) == len(trader_inst.get_order_manager().get_open_orders())

    # a orders gets cancelled
    open_orders = trader_inst.get_order_manager().get_open_orders()
    to_cancel = [open_orders[20], open_orders[19], open_orders[40]]
    for order in to_cancel:
        await trader_inst.cancel_order(order)
    post_available = portfolio["USD"][Portfolio.AVAILABLE]
    assert len(trader_inst.get_order_manager().get_open_orders()) == final_evaluator.operational_depth - len(to_cancel)
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 95}
    await final_evaluator.finalize()
    # restored orders
    assert len(trader_inst.get_order_manager().get_open_orders()) == final_evaluator.operational_depth
    assert 0 < portfolio["USD"][Portfolio.AVAILABLE] <= post_available


async def test_start_without_enough_funds_to_buy():
    final_evaluator, trader_inst, staggered_strategy_evaluator = await _get_tools()
    portfolio = trader_inst.get_portfolio().get_portfolio()
    portfolio["USD"][Portfolio.AVAILABLE] = 0.00005
    portfolio["USD"][Portfolio.TOTAL] = 0.00005
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 100}
    await final_evaluator.finalize()
    orders = trader_inst.get_order_manager().get_open_orders()
    assert len(orders) == final_evaluator.operational_depth
    assert all([o.side == TradeOrderSide.SELL for o in orders])


async def test_start_without_enough_funds_to_sell():
    final_evaluator, trader_inst, staggered_strategy_evaluator = await _get_tools()
    portfolio = trader_inst.get_portfolio().get_portfolio()
    portfolio["BTC"][Portfolio.AVAILABLE] = 0.00001
    portfolio["BTC"][Portfolio.TOTAL] = 0.00001
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 100}
    await final_evaluator.finalize()
    orders = trader_inst.get_order_manager().get_open_orders()
    assert len(orders) == 25
    assert all([o.side == TradeOrderSide.BUY for o in orders])


async def test_start_without_enough_funds_at_all():
    final_evaluator, trader_inst, staggered_strategy_evaluator = await _get_tools()
    portfolio = trader_inst.get_portfolio().get_portfolio()
    portfolio["BTC"][Portfolio.AVAILABLE] = 0.00001
    portfolio["BTC"][Portfolio.TOTAL] = 0.00001
    portfolio["USD"][Portfolio.AVAILABLE] = 0.00005
    portfolio["USD"][Portfolio.TOTAL] = 0.00005
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 100}
    await final_evaluator.finalize()
    orders = trader_inst.get_order_manager().get_open_orders()
    assert len(orders) == 0


async def test_order_fill_callback():
    # create orders
    final_evaluator, trader_inst, _ = await _get_tools()
    final_evaluator.final_eval = 100
    final_evaluator.mode = StrategyModes.NEUTRAL
    previous_total = _get_total_usd(trader_inst, 100)

    await final_evaluator.create_state()
    price_increment = final_evaluator._get_prince_increment(trader_inst)

    open_orders = trader_inst.get_order_manager().get_open_orders()
    assert len(open_orders) == final_evaluator.operational_depth

    # closest to centre buy order is filled
    to_fill_order = open_orders[-2]
    closest_order_with_price = final_evaluator._get_closest_price_order(trader_inst, TradeOrderSide.SELL)
    await _fill_order(to_fill_order, trader_inst)

    # instantly create sell order at price * (1 + increment)
    assert len(open_orders) == final_evaluator.operational_depth
    assert to_fill_order not in open_orders
    newly_created_sell_order = open_orders[-1]
    assert newly_created_sell_order.symbol == to_fill_order.symbol
    price = closest_order_with_price.origin_price - price_increment
    assert newly_created_sell_order.origin_price == AbstractTradingModeCreator._trunc_with_n_decimal_digits(price, 8)
    assert newly_created_sell_order.origin_quantity == \
        AbstractTradingModeCreator._trunc_with_n_decimal_digits(
            to_fill_order.origin_quantity * (1 - final_evaluator.increment),
            8)
    assert newly_created_sell_order.side == TradeOrderSide.SELL
    current_total = _get_total_usd(trader_inst, 100)
    assert previous_total < current_total
    previous_total_buy = current_total

    # now this new sell order is filled
    to_fill_order = open_orders[-1]
    closest_order_with_price = final_evaluator._get_closest_price_order(trader_inst, TradeOrderSide.BUY)
    await _fill_order(to_fill_order, trader_inst)

    # instantly create buy order at price * (1 + increment)
    assert len(open_orders) == final_evaluator.operational_depth
    assert to_fill_order not in open_orders
    newly_created_buy_order = open_orders[-1]
    assert newly_created_buy_order.symbol == to_fill_order.symbol
    price = closest_order_with_price.origin_price + price_increment
    assert newly_created_buy_order.origin_price == AbstractTradingModeCreator._trunc_with_n_decimal_digits(price, 8)
    assert newly_created_buy_order.origin_quantity == \
        AbstractTradingModeCreator._trunc_with_n_decimal_digits(
            to_fill_order.origin_quantity * (1 + final_evaluator.increment),
            8)
    assert newly_created_buy_order.side == TradeOrderSide.BUY
    assert trader_inst.get_portfolio().get_portfolio()["BTC"][Portfolio.TOTAL] > 10
    current_total = _get_total_usd(trader_inst, 100)
    assert previous_total < current_total
    previous_total_sell = current_total

    # now this new buy order is filled
    to_fill_order = open_orders[-1]
    closest_order_with_price = final_evaluator._get_closest_price_order(trader_inst, TradeOrderSide.SELL)
    await _fill_order(to_fill_order, trader_inst)

    # instantly create sell order at price * (1 + increment)
    assert len(open_orders) == final_evaluator.operational_depth
    assert to_fill_order not in open_orders
    newly_created_sell_order = open_orders[-1]
    assert newly_created_sell_order.symbol == to_fill_order.symbol
    price = closest_order_with_price.origin_price - price_increment
    assert newly_created_sell_order.origin_price == AbstractTradingModeCreator._trunc_with_n_decimal_digits(price, 8)
    assert newly_created_sell_order.origin_quantity == \
        AbstractTradingModeCreator._trunc_with_n_decimal_digits(
            to_fill_order.origin_quantity * (1 - final_evaluator.increment),
            8)
    assert newly_created_sell_order.side == TradeOrderSide.SELL
    current_total = _get_total_usd(trader_inst, 100)
    assert previous_total_buy < current_total

    # now this new sell order is filled
    to_fill_order = open_orders[-1]
    closest_order_with_price = final_evaluator._get_closest_price_order(trader_inst, TradeOrderSide.BUY)
    await _fill_order(to_fill_order, trader_inst)

    # instantly create buy order at price * (1 + increment)
    assert len(open_orders) == final_evaluator.operational_depth
    assert to_fill_order not in open_orders
    newly_created_buy_order = open_orders[-1]
    assert newly_created_buy_order.symbol == to_fill_order.symbol
    price = closest_order_with_price.origin_price + price_increment
    assert newly_created_buy_order.origin_price == AbstractTradingModeCreator._trunc_with_n_decimal_digits(price, 8)
    assert newly_created_buy_order.origin_quantity == \
        AbstractTradingModeCreator._trunc_with_n_decimal_digits(
            to_fill_order.origin_quantity * (1 + final_evaluator.increment),
            8)
    assert newly_created_buy_order.side == TradeOrderSide.BUY
    current_total = _get_total_usd(trader_inst, 100)
    assert previous_total_sell < current_total


def _get_total_usd(trader, btc_price):
    pf = trader.get_portfolio().get_portfolio()
    return pf["USD"][Portfolio.TOTAL] + pf["BTC"][Portfolio.TOTAL] * btc_price


async def _fill_order(order, trader, trigger_price=None):
    if trigger_price is None:
        trigger_price = order.origin_price*0.99 if order.side == TradeOrderSide.BUY else order.origin_price*1.01
    recent_trades = [{"price": trigger_price, "timestamp": time.time()}]
    order.last_prices = recent_trades
    errors = []
    initial_len = len(trader.get_order_manager().get_open_orders())
    if await trader.get_order_manager()._update_order_status(order, errors):
        assert len(trader.get_order_manager().get_open_orders()) == initial_len - 1
        await trader.get_order_manager().trader.call_order_update_callback(order)


async def _test_mode(mode, expected_buy_count, expected_sell_count, price, lowest_buy=None, highest_sell=None,
                     btc_holdings=None):
    final_evaluator, trader_inst, _ = await _get_tools()
    portfolio = trader_inst.get_portfolio().get_portfolio()
    if btc_holdings is not None:
        portfolio["BTC"][Portfolio.AVAILABLE] = btc_holdings
        portfolio["BTC"][Portfolio.TOTAL] = btc_holdings
    if lowest_buy is not None:
        final_evaluator.lowest_buy = lowest_buy
    if highest_sell is not None:
        final_evaluator.highest_sell = highest_sell
    final_evaluator.final_eval = price
    final_evaluator.mode = mode

    await _check_generate_orders(trader_inst, final_evaluator, expected_buy_count, expected_sell_count, price)

    open_orders = trader_inst.get_order_manager().get_open_orders()
    if expected_buy_count or expected_sell_count:
        assert len(open_orders) <= final_evaluator.operational_depth
    _check_orders(open_orders, mode, final_evaluator, trader_inst)


async def _check_generate_orders(trader, decider, expected_buy_count, expected_sell_count, price):
    async with trader.get_portfolio().get_lock():
        decider._refresh_symbol_data()
        buy_orders, sell_orders = await decider._generate_staggered_orders(decider.final_eval, trader)
        assert len(buy_orders) == expected_buy_count
        assert len(sell_orders) == expected_sell_count

        assert all(o.price < price for o in buy_orders)
        assert all(o.price > price for o in sell_orders)

        if buy_orders:
            assert not any(order for order in buy_orders if order.is_virtual)

        if sell_orders:
            assert any(order for order in sell_orders if order.is_virtual)

        buy_holdings = trader.get_portfolio().get_portfolio()["USD"][Portfolio.AVAILABLE]
        assert sum(order.price*order.quantity for order in buy_orders) <= buy_holdings

        sell_holdings = trader.get_portfolio().get_portfolio()["BTC"][Portfolio.AVAILABLE]
        assert sum(order.price*order.quantity for order in sell_orders) <= sell_holdings

        staggered_orders = decider._alternate_not_virtual_orders(buy_orders, sell_orders)
        if staggered_orders:
            assert not any(order for order in staggered_orders if order.is_virtual)

        await decider._create_multiple_not_virtual_orders(staggered_orders, trader)


def _check_orders(orders, strategy_mode, final_evaluator, trader_inst):
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
                # place sell orders from the highest price down to the current price
                # round because of python accuracy with small numbers combined with virtual orders
                assert current_sell.origin_price > order.origin_price
                if sell_increase_towards_center:
                    assert round(current_sell.origin_quantity * current_sell.origin_price, 5) <= \
                        round(order.origin_quantity * order.origin_price, 5)
                else:
                    assert round(current_sell.origin_quantity * current_sell.origin_price, 5) >= \
                        round(order.origin_quantity * order.origin_price, 5)
                current_sell = order

    order_limiting_currency_amount = trader_inst.get_portfolio().portfolio["USD"][Portfolio.TOTAL]
    _, average_order_quantity = \
        final_evaluator._get_order_count_and_average_quantity(final_evaluator.final_eval,
                                                              False,
                                                              final_evaluator.lowest_buy,
                                                              final_evaluator.final_eval,
                                                              order_limiting_currency_amount)
    if orders:
        if buy_increase_towards_center:
            assert round(current_buy.origin_quantity * current_buy.origin_price -
                         first_buy.origin_quantity * first_buy.origin_price) == round(multiplier * average_order_quantity)
        else:
            assert round(first_buy.origin_quantity * first_buy.origin_price -
                         current_buy.origin_quantity * current_buy.origin_price) == round(multiplier *
                                                                                          average_order_quantity)

        order_limiting_currency_amount = trader_inst.get_portfolio().portfolio["BTC"][Portfolio.TOTAL]
        _, average_order_quantity = \
            final_evaluator._get_order_count_and_average_quantity(final_evaluator.final_eval,
                                                                  True,
                                                                  final_evaluator.final_eval,
                                                                  final_evaluator.highest_sell,
                                                                  order_limiting_currency_amount)

        # not exactly multiplier because of virtual orders and rounds
        if sell_increase_towards_center:
            expected_quantity = AbstractTradingModeCreator._trunc_with_n_decimal_digits(
                average_order_quantity * (1 + multiplier/2),
                8)
            assert abs(current_sell.origin_quantity * current_sell.origin_price - expected_quantity) < \
                multiplier*final_evaluator.increment/(2*final_evaluator.final_eval)
        else:
            expected_quantity = AbstractTradingModeCreator._trunc_with_n_decimal_digits(
                average_order_quantity * (1 - multiplier/2),
                8)
            assert abs(current_sell.origin_quantity * current_sell.origin_price == expected_quantity) < \
                multiplier*final_evaluator.increment/(2*final_evaluator.final_eval)
