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
    MULTIPLIER, INCREASING, AbstractTradingModeCreator, OrderData
from trading.trader.trader_simulator import TraderSimulator
from trading.trader.portfolio import Portfolio


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


def _add_symbol(crypto, symbol, config, exchange_traders, exchange_traders2, exchange_inst, trading_mode):
    crypto_currency_evaluator = CryptocurrencyEvaluator(config, crypto, [])
    symbol_evaluator = SymbolEvaluator(config, symbol, crypto_currency_evaluator)
    symbol_evaluator.set_trader_simulators(exchange_traders)
    symbol_evaluator.set_traders(exchange_traders2)
    symbol_evaluator.strategies_eval_lists[exchange_inst.get_name()] = \
        EvaluatorCreator.create_strategies_eval_list(config)

    trading_mode.add_symbol_evaluator(symbol_evaluator)

    staggered_strategy_evaluator = symbol_evaluator.strategies_eval_lists[exchange_inst.get_name()][0]

    return trading_mode.get_only_decider_key(symbol), staggered_strategy_evaluator


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
    exchange_traders[exchange_inst.get_name()] = trader_inst

    trading_mode = StaggeredOrdersTradingMode(config, exchange_inst)
    trading_mode.trading_config = _get_multi_symbol_staggered_config()
    trader_inst.register_trading_mode(trading_mode)

    final_evaluator, staggered_strategy_evaluator = _add_symbol("Bitcoin", symbol, config, exchange_traders,
                                                                exchange_traders2, exchange_inst, trading_mode)

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
    final_evaluator.spread = 0.06
    final_evaluator.increment = 0.04

    return final_evaluator, trader_inst, staggered_strategy_evaluator


async def _get_tools_multi_symbol():
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
    exchange_traders[exchange_inst.get_name()] = trader_inst

    trading_mode = StaggeredOrdersTradingMode(config, exchange_inst)
    trading_mode.trading_config = _get_multi_symbol_staggered_config()
    trader_inst.register_trading_mode(trading_mode)

    btcusd_final_evaluator, btcusd_staggered_strategy_evaluator = _add_symbol("Bitcoin", "BTC/USD", config,
                                                                              exchange_traders, exchange_traders2,
                                                                              exchange_inst, trading_mode)
    eth_usdt_final_evaluator, eth_usdt_staggered_strategy_evaluator = _add_symbol("Ethereum", "ETH/USDT", config,
                                                                                  exchange_traders, exchange_traders2,
                                                                                  exchange_inst, trading_mode)

    nano_usdt_final_evaluator, nano_usdt_staggered_strategy_evaluator = _add_symbol("NANO", "NANO/USDT", config,
                                                                                    exchange_traders, exchange_traders2,
                                                                                    exchange_inst, trading_mode)

    trader_inst.portfolio.portfolio["USD"] = {
        Portfolio.TOTAL: 1000,
        Portfolio.AVAILABLE: 1000
    }
    trader_inst.portfolio.portfolio["USDT"] = {
        Portfolio.TOTAL: 2000,
        Portfolio.AVAILABLE: 2000
    }
    trader_inst.portfolio.portfolio["BTC"] = {
        Portfolio.TOTAL: 10,
        Portfolio.AVAILABLE: 10
    }
    trader_inst.portfolio.portfolio["ETH"] = {
        Portfolio.TOTAL: 20,
        Portfolio.AVAILABLE: 20
    }
    trader_inst.portfolio.portfolio["NANO"] = {
        Portfolio.TOTAL: 2000,
        Portfolio.AVAILABLE: 2000
    }
    btcusd_final_evaluator.lowest_buy = 1
    btcusd_final_evaluator.highest_sell = 10000
    btcusd_final_evaluator.operational_depth = 50
    btcusd_final_evaluator.spread = 0.06
    btcusd_final_evaluator.increment = 0.04

    eth_usdt_final_evaluator.lowest_buy = 20
    eth_usdt_final_evaluator.highest_sell = 5000
    eth_usdt_final_evaluator.operational_depth = 30
    eth_usdt_final_evaluator.spread = 0.07
    eth_usdt_final_evaluator.increment = 0.03

    nano_usdt_final_evaluator.lowest_buy = 20
    nano_usdt_final_evaluator.highest_sell = 5000
    nano_usdt_final_evaluator.operational_depth = 30
    nano_usdt_final_evaluator.spread = 0.07
    nano_usdt_final_evaluator.increment = 0.03

    return btcusd_final_evaluator, eth_usdt_final_evaluator, nano_usdt_final_evaluator, trader_inst, \
        btcusd_staggered_strategy_evaluator, eth_usdt_staggered_strategy_evaluator, \
        nano_usdt_staggered_strategy_evaluator


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


async def test_multi_symbol():
    btcusd_final_evaluator, eth_usdt_final_evaluator, nano_usdt_final_evaluator, trader_inst, \
        btcusd_staggered_strategy_evaluator, eth_usdt_staggered_strategy_evaluator, \
        nano_usdt_staggered_strategy_evaluator = await _get_tools_multi_symbol()

    btcusd_staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 100}
    await btcusd_final_evaluator.finalize()
    orders = trader_inst.get_order_manager().get_open_orders()
    assert len(orders) == btcusd_final_evaluator.operational_depth
    assert len([o for o in orders if o.side == TradeOrderSide.SELL]) == 25
    assert len([o for o in orders if o.side == TradeOrderSide.BUY]) == 25

    eth_usdt_staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 200}
    await eth_usdt_final_evaluator.finalize()
    orders = trader_inst.get_order_manager().get_open_orders()
    assert len(orders) == btcusd_final_evaluator.operational_depth + eth_usdt_final_evaluator.operational_depth
    assert len([o for o in orders if o.side == TradeOrderSide.SELL]) == 40
    assert len([o for o in orders if o.side == TradeOrderSide.BUY]) == 40

    nano_usdt_staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 200}
    await nano_usdt_final_evaluator.finalize()
    orders = trader_inst.get_order_manager().get_open_orders()
    assert len(orders) == btcusd_final_evaluator.operational_depth + eth_usdt_final_evaluator.operational_depth
    assert len([o for o in orders if o.side == TradeOrderSide.SELL]) == 40
    assert len([o for o in orders if o.side == TradeOrderSide.BUY]) == 40

    assert nano_usdt_final_evaluator._get_interfering_orders_pairs(orders) == {"ETH/USDT"}

    # new ETH USDT evaluation, price changed
    # -2 order would be filled
    original_orders = copy.copy(orders)
    to_fill_order = original_orders[-2]
    await _fill_order(to_fill_order, trader_inst, 190)
    eth_usdt_staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 190}
    await eth_usdt_final_evaluator.finalize()
    # did nothing
    assert len(original_orders) == len(trader_inst.get_order_manager().get_open_orders())


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
    final_evaluator, trader_inst, staggered_strategy_evaluator = await _get_tools()
    portfolio = trader_inst.get_portfolio()
    portfolio.get_portfolio()["RDN"] = {
        Portfolio.AVAILABLE: 6740,
        Portfolio.TOTAL: 6740
    }
    portfolio.get_portfolio()["ETH"] = {
        Portfolio.AVAILABLE: 10,
        Portfolio.TOTAL: 10
    }
    final_evaluator.symbol = "RDN/ETH"
    final_evaluator._refresh_symbol_data()
    final_evaluator.min_max_order_details[final_evaluator.min_cost] = 0.01
    final_evaluator.min_max_order_details[final_evaluator.min_quantity] = 1.0
    final_evaluator.min_max_order_details[final_evaluator.max_quantity] = 90000000.0
    final_evaluator.min_max_order_details[final_evaluator.max_cost] = None
    final_evaluator.min_max_order_details[final_evaluator.max_price] = None
    final_evaluator.min_max_order_details[final_evaluator.min_price] = None

    price = 0.0024161
    # await _test_mode(StrategyModes.NEUTRAL, 0, 0, price)
    lowest_buy = 0.0013
    highest_sell = 0.0043
    expected_buy_count = 46
    expected_sell_count = 78

    final_evaluator.lowest_buy = lowest_buy
    final_evaluator.highest_sell = highest_sell
    final_evaluator.increment = 0.01
    final_evaluator.spread = 0.01
    final_evaluator.operational_depth = 10
    final_evaluator.final_eval = price
    final_evaluator.mode = StrategyModes.MOUNTAIN

    await _light_check_orders(final_evaluator, trader_inst, expected_buy_count, expected_sell_count, price, portfolio)

    original_orders = copy.copy(trader_inst.get_order_manager().get_open_orders())
    assert len(original_orders) == final_evaluator.operational_depth

    # test trigger refresh
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 0.0024161}
    await final_evaluator.finalize()
    # did nothing
    assert original_orders[0] is trader_inst.get_order_manager().get_open_orders()[0]
    assert original_orders[-1] is trader_inst.get_order_manager().get_open_orders()[-1]
    assert len(trader_inst.get_order_manager().get_open_orders()) == final_evaluator.operational_depth


async def test_create_orders_from_different_very_close_refresh():
    final_evaluator, trader_inst, staggered_strategy_evaluator = await _get_tools()
    portfolio = trader_inst.get_portfolio()
    portfolio.get_portfolio()["RDN"] = {
        Portfolio.AVAILABLE: 6740,
        Portfolio.TOTAL: 6740
    }
    portfolio.get_portfolio()["ETH"] = {
        Portfolio.AVAILABLE: 10,
        Portfolio.TOTAL: 10
    }
    final_evaluator.symbol = "RDN/ETH"
    final_evaluator._refresh_symbol_data()
    final_evaluator.min_max_order_details[final_evaluator.min_cost] = 0.01
    final_evaluator.min_max_order_details[final_evaluator.min_quantity] = 1.0
    final_evaluator.min_max_order_details[final_evaluator.max_quantity] = 90000000.0
    final_evaluator.min_max_order_details[final_evaluator.max_cost] = None
    final_evaluator.min_max_order_details[final_evaluator.max_price] = None
    final_evaluator.min_max_order_details[final_evaluator.min_price] = None

    price = 0.00231
    # await _test_mode(StrategyModes.NEUTRAL, 0, 0, price)
    lowest_buy = 0.00221
    highest_sell = 0.00242
    expected_buy_count = 2
    expected_sell_count = 2

    final_evaluator.lowest_buy = lowest_buy
    final_evaluator.highest_sell = highest_sell
    final_evaluator.increment = 0.02
    final_evaluator.spread = 0.02
    final_evaluator.operational_depth = 10
    final_evaluator.final_eval = price
    final_evaluator.mode = StrategyModes.MOUNTAIN

    await _light_check_orders(final_evaluator, trader_inst, expected_buy_count, expected_sell_count, price, portfolio)

    original_orders = copy.copy(trader_inst.get_order_manager().get_open_orders())
    original_length = len(original_orders)

    # test trigger refresh
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 0.0023185}
    await final_evaluator.finalize()
    # did nothing
    assert original_orders[0] is trader_inst.get_order_manager().get_open_orders()[0]
    assert original_orders[-1] is trader_inst.get_order_manager().get_open_orders()[-1]
    assert original_length == len(trader_inst.get_order_manager().get_open_orders())

    # test more trigger refresh
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 0.0022991}
    await final_evaluator.finalize()
    # did nothing
    assert original_orders[0] is trader_inst.get_order_manager().get_open_orders()[0]
    assert original_orders[-1] is trader_inst.get_order_manager().get_open_orders()[-1]
    assert original_length == len(trader_inst.get_order_manager().get_open_orders())


async def test_create_orders_from_different_markets_not_enough_market_to_create_all_orders():
    final_evaluator, trader_inst, _ = await _get_tools()
    portfolio = trader_inst.get_portfolio()
    portfolio.get_portfolio()["RDN"] = {
        Portfolio.AVAILABLE: 6740,
        Portfolio.TOTAL: 6740
    }
    portfolio.get_portfolio()["ETH"] = {
        Portfolio.AVAILABLE: 10,
        Portfolio.TOTAL: 10
    }
    final_evaluator.symbol = "RDN/ETH"
    final_evaluator._refresh_symbol_data()
    final_evaluator.min_max_order_details[final_evaluator.min_cost] = 1.0
    final_evaluator.min_max_order_details[final_evaluator.min_quantity] = 1.0
    final_evaluator.min_max_order_details[final_evaluator.max_quantity] = 90000000.0
    final_evaluator.min_max_order_details[final_evaluator.max_cost] = None
    final_evaluator.min_max_order_details[final_evaluator.max_price] = None
    final_evaluator.min_max_order_details[final_evaluator.min_price] = None

    price = 0.0024161
    # await _test_mode(StrategyModes.NEUTRAL, 0, 0, price)
    lowest_buy = 0.0013
    highest_sell = 0.0043
    expected_buy_count = 0
    expected_sell_count = 0

    final_evaluator.lowest_buy = lowest_buy
    final_evaluator.highest_sell = highest_sell
    final_evaluator.increment = 0.01
    final_evaluator.spread = 0.01
    final_evaluator.operational_depth = 10
    final_evaluator.final_eval = price
    final_evaluator.mode = StrategyModes.MOUNTAIN

    await _light_check_orders(final_evaluator, trader_inst, expected_buy_count, expected_sell_count, price, portfolio)


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

    # an orders gets cancelled
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
    assert 0 <= portfolio["USD"][Portfolio.AVAILABLE] <= post_available
    assert 0 <= portfolio["BTC"][Portfolio.AVAILABLE]


async def test_price_initially_out_of_range_1():
    final_evaluator, trader_inst, staggered_strategy_evaluator = await _get_tools()
    portfolio = trader_inst.get_portfolio().get_portfolio()
    assert not trader_inst.get_order_manager().get_open_orders()

    # new evaluation: price in range
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 0.1}
    portfolio["BTC"] = {
        Portfolio.AVAILABLE: 100000000,
        Portfolio.TOTAL: 100000000
    }
    await final_evaluator.finalize()
    original_orders = copy.copy(trader_inst.get_order_manager().get_open_orders())
    assert len(original_orders) == final_evaluator.operational_depth
    assert all(o.side == TradeOrderSide.SELL for o in original_orders)
    assert all(final_evaluator.highest_sell >= o.get_origin_price() >= final_evaluator.lowest_buy
               for o in original_orders)


async def test_price_initially_out_of_range_2():
    final_evaluator, trader_inst, staggered_strategy_evaluator = await _get_tools()
    portfolio = trader_inst.get_portfolio().get_portfolio()
    assert not trader_inst.get_order_manager().get_open_orders()

    # new evaluation: price in range
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 100000}
    portfolio["USD"] = {
        Portfolio.AVAILABLE: 10000000,
        Portfolio.TOTAL: 10000000
    }
    await final_evaluator.finalize()
    original_orders = copy.copy(trader_inst.get_order_manager().get_open_orders())
    assert len(original_orders) == 3
    assert all(o.side == TradeOrderSide.BUY for o in original_orders)
    assert all(final_evaluator.highest_sell >= o.get_origin_price() >= final_evaluator.lowest_buy
               for o in original_orders)


async def test_price_going_out_of_range():
    final_evaluator, trader_inst, staggered_strategy_evaluator = await _get_tools()
    assert not trader_inst.get_order_manager().get_open_orders()

    # new evaluation: price in range
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 100}
    await final_evaluator.finalize()
    original_orders = copy.copy(trader_inst.get_order_manager().get_open_orders())
    assert len(original_orders) == final_evaluator.operational_depth

    # new evaluation: price out of range: >
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 100000}
    final_evaluator.set_final_eval()
    existing_orders = trader_inst.get_open_orders(final_evaluator.symbol)
    sorted_orders = sorted(existing_orders, key=lambda order: order.origin_price)
    missing_orders, state, candidate_flat_increment = final_evaluator._analyse_current_orders_situation(sorted_orders)
    assert missing_orders is None
    assert candidate_flat_increment is None
    assert state == final_evaluator.ERROR

    # new evaluation: price out of range: <
    final_evaluator.set_final_eval()
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 0.1}
    existing_orders = trader_inst.get_open_orders(final_evaluator.symbol)
    sorted_orders = sorted(existing_orders, key=lambda order: order.origin_price)
    missing_orders, state, candidate_flat_increment = final_evaluator._analyse_current_orders_situation(sorted_orders)
    assert missing_orders is None
    assert candidate_flat_increment is None
    assert state == final_evaluator.ERROR


async def test_start_after_offline_filled_orders():
    # first start: setup orders
    final_evaluator, trader_inst, staggered_strategy_evaluator = await _get_tools()
    portfolio = trader_inst.get_portfolio().get_portfolio()
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 100}
    await final_evaluator.finalize()
    original_orders = copy.copy(trader_inst.get_order_manager().get_open_orders())
    assert len(original_orders) == final_evaluator.operational_depth
    pre_portfolio = portfolio["USD"][Portfolio.AVAILABLE]

    # offline simulation: orders get filled but not replaced => price got up to 110 and not down to 90, now is 96s
    open_orders = trader_inst.get_order_manager().get_open_orders()
    offline_filled = [o for o in open_orders if 90 <= o.get_origin_price() <= 110]
    for order in offline_filled:
        await _fill_order(order, trader_inst, order_update_callback=False)
    post_portfolio = portfolio["USD"][Portfolio.AVAILABLE]
    assert pre_portfolio < post_portfolio
    assert len(trader_inst.get_order_manager().get_open_orders()) == \
        final_evaluator.operational_depth - len(offline_filled)

    # back online: restore orders according to current price
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 96}
    await final_evaluator.finalize()
    # restored orders
    assert len(trader_inst.get_order_manager().get_open_orders()) == final_evaluator.operational_depth
    assert 0 <= portfolio["USD"][Portfolio.AVAILABLE] <= post_portfolio
    assert 0 <= portfolio["BTC"][Portfolio.AVAILABLE]


async def test_compute_minimum_funds_1():
    final_evaluator, trader_inst, staggered_strategy_evaluator = await _get_tools()
    buy_min_funds = final_evaluator._get_min_funds(25, 0.001, StrategyModes.MOUNTAIN, 100)
    sell_min_funds = final_evaluator._get_min_funds(2475.25, 0.00001, StrategyModes.MOUNTAIN, 100)
    assert buy_min_funds == 0.05
    assert sell_min_funds == 0.04950500000000001
    portfolio = trader_inst.get_portfolio().get_portfolio()
    portfolio["USD"][Portfolio.AVAILABLE] = buy_min_funds
    portfolio["USD"][Portfolio.TOTAL] = buy_min_funds
    portfolio["BTC"][Portfolio.AVAILABLE] = sell_min_funds
    portfolio["BTC"][Portfolio.TOTAL] = sell_min_funds
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 100}
    await final_evaluator.finalize()
    orders = trader_inst.get_order_manager().get_open_orders()
    assert len(orders) == final_evaluator.operational_depth
    assert len([o for o in orders if o.side == TradeOrderSide.SELL]) == 26
    assert len([o for o in orders if o.side == TradeOrderSide.BUY]) == 24


async def test_compute_minimum_funds_2():
    final_evaluator, trader_inst, staggered_strategy_evaluator = await _get_tools()
    final_evaluator._refresh_symbol_data()
    buy_min_funds = final_evaluator._get_min_funds(25, 0.001, StrategyModes.MOUNTAIN, 100)
    sell_min_funds = final_evaluator._get_min_funds(2475, 0.00001, StrategyModes.MOUNTAIN, 100)
    assert buy_min_funds == 0.05
    assert sell_min_funds == 0.0495
    portfolio = trader_inst.get_portfolio().get_portfolio()
    portfolio["USD"][Portfolio.AVAILABLE] = buy_min_funds*0.99999
    portfolio["USD"][Portfolio.TOTAL] = buy_min_funds*0.99999
    portfolio["BTC"][Portfolio.AVAILABLE] = sell_min_funds*0.99999
    portfolio["BTC"][Portfolio.TOTAL] = sell_min_funds*0.99999
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 100}
    await final_evaluator.finalize()
    orders = trader_inst.get_order_manager().get_open_orders()
    assert len(orders) == 0


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

    # trigger health check
    await final_evaluator.create_state()

    await _fill_order(orders[5], trader_inst)


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

    # trigger health check
    await final_evaluator.create_state()

    # check order fill callback recreates spread
    to_fill_order = orders[5]
    second_to_fill_order = orders[4]
    await _fill_order(to_fill_order, trader_inst)
    newly_created_sell_order = orders[-1]
    assert newly_created_sell_order.side == TradeOrderSide.SELL
    assert newly_created_sell_order.origin_price == to_fill_order.origin_price + \
        (final_evaluator.flat_spread - final_evaluator.flat_increment)

    await _fill_order(second_to_fill_order, trader_inst)
    second_newly_created_sell_order = orders[-1]
    assert second_newly_created_sell_order.side == TradeOrderSide.SELL
    assert second_newly_created_sell_order.origin_price == second_to_fill_order.origin_price + \
        (final_evaluator.flat_spread - final_evaluator.flat_increment)
    assert abs(second_newly_created_sell_order.origin_price - newly_created_sell_order.origin_price) == \
        final_evaluator.flat_increment


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


async def test_settings_for_just_one_order_on_a_side():
    final_evaluator, trader_inst, staggered_strategy_evaluator = await _get_tools()
    final_evaluator.highest_sell = 106
    staggered_strategy_evaluator.eval_note = {ExchangeConstantsTickersInfoColumns.LAST_PRICE.value: 100}
    await final_evaluator.finalize()
    orders = trader_inst.get_order_manager().get_open_orders()
    assert len([o for o in orders if o.get_side() == TradeOrderSide.SELL]) == 1


async def test_order_fill_callback():
    # create orders
    final_evaluator, trader_inst, _ = await _get_tools()
    final_evaluator.final_eval = 100
    final_evaluator.mode = StrategyModes.NEUTRAL
    previous_total = _get_total_usd(trader_inst, 100)

    now_btc = trader_inst.get_portfolio().get_portfolio()["BTC"][Portfolio.TOTAL]
    now_usd = trader_inst.get_portfolio().get_portfolio()["USD"][Portfolio.TOTAL]

    await final_evaluator.create_state()
    price_increment = final_evaluator.flat_increment
    price_spread = final_evaluator.flat_spread

    open_orders = trader_inst.get_order_manager().get_open_orders()
    assert len(open_orders) == final_evaluator.operational_depth

    # closest to centre buy order is filled => bought btc
    to_fill_order = open_orders[-2]
    await _fill_order(to_fill_order, trader_inst)

    # instantly create sell order at price * (1 + increment)
    assert len(open_orders) == final_evaluator.operational_depth
    assert to_fill_order not in open_orders
    newly_created_sell_order = open_orders[-1]
    assert newly_created_sell_order.symbol == to_fill_order.symbol
    price = to_fill_order.origin_price + (price_spread - price_increment)
    assert newly_created_sell_order.origin_price == AbstractTradingModeCreator._trunc_with_n_decimal_digits(price, 8)
    assert newly_created_sell_order.origin_quantity == \
        AbstractTradingModeCreator._trunc_with_n_decimal_digits(
            to_fill_order.filled_quantity * (1 - final_evaluator.max_fees),
            8)
    assert newly_created_sell_order.side == TradeOrderSide.SELL
    assert trader_inst.get_portfolio().get_portfolio()["BTC"][Portfolio.TOTAL] > now_btc
    now_btc = trader_inst.get_portfolio().get_portfolio()["BTC"][Portfolio.TOTAL]
    current_total = _get_total_usd(trader_inst, 100)
    assert previous_total < current_total
    previous_total_buy = current_total

    # now this new sell order is filled => sold btc
    to_fill_order = open_orders[-1]
    await _fill_order(to_fill_order, trader_inst)

    # instantly create buy order at price * (1 + increment)
    assert len(open_orders) == final_evaluator.operational_depth
    assert to_fill_order not in open_orders
    newly_created_buy_order = open_orders[-1]
    assert newly_created_buy_order.symbol == to_fill_order.symbol
    price = to_fill_order.origin_price - (price_spread - price_increment)
    assert newly_created_buy_order.origin_price == AbstractTradingModeCreator._trunc_with_n_decimal_digits(price, 8)
    assert newly_created_buy_order.origin_quantity == \
        AbstractTradingModeCreator._trunc_with_n_decimal_digits(
            to_fill_order.filled_price / price * to_fill_order.filled_quantity * (1 - final_evaluator.max_fees),
            8)
    assert newly_created_buy_order.side == TradeOrderSide.BUY
    assert trader_inst.get_portfolio().get_portfolio()["USD"][Portfolio.TOTAL] > now_usd
    now_usd = trader_inst.get_portfolio().get_portfolio()["USD"][Portfolio.TOTAL]
    current_total = _get_total_usd(trader_inst, 100)
    assert previous_total < current_total
    previous_total_sell = current_total

    # now this new buy order is filled => bought btc
    to_fill_order = open_orders[-1]
    await _fill_order(to_fill_order, trader_inst)

    # instantly create sell order at price * (1 + increment)
    assert len(open_orders) == final_evaluator.operational_depth
    assert to_fill_order not in open_orders
    newly_created_sell_order = open_orders[-1]
    assert newly_created_sell_order.symbol == to_fill_order.symbol
    price = to_fill_order.origin_price + (price_spread - price_increment)
    assert newly_created_sell_order.origin_price == AbstractTradingModeCreator._trunc_with_n_decimal_digits(price, 8)
    assert newly_created_sell_order.origin_quantity == \
        AbstractTradingModeCreator._trunc_with_n_decimal_digits(
            to_fill_order.filled_quantity * (1 - final_evaluator.max_fees),
            8)
    assert newly_created_sell_order.side == TradeOrderSide.SELL
    assert trader_inst.get_portfolio().get_portfolio()["BTC"][Portfolio.TOTAL] > now_btc
    current_total = _get_total_usd(trader_inst, 100)
    assert previous_total_buy < current_total

    # now this new sell order is filled => sold btc
    to_fill_order = open_orders[-1]
    await _fill_order(to_fill_order, trader_inst)

    # instantly create buy order at price * (1 + increment)
    assert len(open_orders) == final_evaluator.operational_depth
    assert to_fill_order not in open_orders
    newly_created_buy_order = open_orders[-1]
    assert newly_created_buy_order.symbol == to_fill_order.symbol
    price = to_fill_order.origin_price - (price_spread - price_increment)
    assert newly_created_buy_order.origin_price == AbstractTradingModeCreator._trunc_with_n_decimal_digits(price, 8)
    assert newly_created_buy_order.origin_quantity == \
        AbstractTradingModeCreator._trunc_with_n_decimal_digits(
            to_fill_order.filled_price / price * to_fill_order.filled_quantity * (1 - final_evaluator.max_fees),
            8)
    assert newly_created_buy_order.side == TradeOrderSide.BUY
    assert trader_inst.get_portfolio().get_portfolio()["USD"][Portfolio.TOTAL] > now_usd
    current_total = _get_total_usd(trader_inst, 100)
    assert previous_total_sell < current_total


async def test_create_order():
    final_evaluator, trader_inst, _ = await _get_tools()
    symbol = "BTC/USD"
    portfolio = trader_inst.get_portfolio()
    creator_key = final_evaluator.trading_mode.get_only_creator_key(final_evaluator.symbol)
    creator = final_evaluator.trading_mode.get_creator(final_evaluator.symbol, creator_key)
    final_evaluator._refresh_symbol_data()
    symbol_market = final_evaluator.symbol_market

    # SELL

    # enough quantity in portfolio
    price = 100
    quantity = 1
    side = TradeOrderSide.SELL
    to_create_order = OrderData(side, quantity, price, symbol, False)
    created_order = await creator.create_order(to_create_order, price, symbol_market, trader_inst, portfolio)
    assert created_order.origin_quantity == quantity
    assert created_order is not None

    # not enough quantity in portfolio
    price = 100
    quantity = 10
    side = TradeOrderSide.SELL
    to_create_order = OrderData(side, quantity, price, symbol, False)
    created_order = await creator.create_order(to_create_order, price, symbol_market, trader_inst, portfolio)
    assert created_order is None

    # just enough quantity in portfolio
    price = 100
    quantity = 9
    side = TradeOrderSide.SELL
    to_create_order = OrderData(side, quantity, price, symbol, False)
    created_order = await creator.create_order(to_create_order, price, symbol_market, trader_inst, portfolio)
    assert created_order.origin_quantity == quantity
    assert portfolio.get_portfolio()["BTC"][Portfolio.AVAILABLE] == 0
    assert created_order is not None

    # not enough quantity anymore
    price = 100
    quantity = 0.0001
    side = TradeOrderSide.SELL
    to_create_order = OrderData(side, quantity, price, symbol, False)
    created_order = await creator.create_order(to_create_order, price, symbol_market, trader_inst, portfolio)
    assert portfolio.get_portfolio()["BTC"][Portfolio.AVAILABLE] == 0
    assert created_order is None

    # BUY

    # enough quantity in portfolio
    price = 100
    quantity = 1
    side = TradeOrderSide.BUY
    to_create_order = OrderData(side, quantity, price, symbol, False)
    created_order = await creator.create_order(to_create_order, price, symbol_market, trader_inst, portfolio)
    assert created_order.origin_quantity == quantity
    assert portfolio.get_portfolio()["USD"][Portfolio.AVAILABLE] == 900
    assert created_order is not None

    # not enough quantity in portfolio
    price = 585
    quantity = 2
    side = TradeOrderSide.BUY
    to_create_order = OrderData(side, quantity, price, symbol, False)
    created_order = await creator.create_order(to_create_order, price, symbol_market, trader_inst, portfolio)
    assert portfolio.get_portfolio()["USD"][Portfolio.AVAILABLE] == 900
    assert created_order is None

    # enough quantity in portfolio
    price = 40
    quantity = 2
    side = TradeOrderSide.BUY
    to_create_order = OrderData(side, quantity, price, symbol, False)
    created_order = await creator.create_order(to_create_order, price, symbol_market, trader_inst, portfolio)
    assert created_order.origin_quantity == quantity
    assert portfolio.get_portfolio()["USD"][Portfolio.AVAILABLE] == 820
    assert created_order is not None

    # enough quantity in portfolio
    price = 205
    quantity = 4
    side = TradeOrderSide.BUY
    to_create_order = OrderData(side, quantity, price, symbol, False)
    created_order = await creator.create_order(to_create_order, price, symbol_market, trader_inst, portfolio)
    assert created_order.origin_quantity == quantity
    assert portfolio.get_portfolio()["USD"][Portfolio.AVAILABLE] == 0
    assert created_order is not None

    # not enough quantity in portfolio anymore
    price = 205
    quantity = 1
    side = TradeOrderSide.BUY
    to_create_order = OrderData(side, quantity, price, symbol, False)
    created_order = await creator.create_order(to_create_order, price, symbol_market, trader_inst, portfolio)
    assert portfolio.get_portfolio()["USD"][Portfolio.AVAILABLE] == 0
    assert created_order is None


def _get_total_usd(trader, btc_price):
    pf = trader.get_portfolio().get_portfolio()
    return pf["USD"][Portfolio.TOTAL] + pf["BTC"][Portfolio.TOTAL] * btc_price


async def _fill_order(order, trader, trigger_price=None, order_update_callback=True):
    if trigger_price is None:
        trigger_price = order.origin_price*0.99 if order.side == TradeOrderSide.BUY else order.origin_price*1.01
    recent_trades = [{"price": trigger_price, "timestamp": time.time()}]
    order.last_prices = recent_trades
    errors = []
    initial_len = len(trader.get_order_manager().get_open_orders())
    if await trader.get_order_manager()._update_order_status(order, errors):
        assert len(trader.get_order_manager().get_open_orders()) == initial_len - 1
        if order_update_callback:
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

    assert portfolio["BTC"][Portfolio.AVAILABLE] >= 0
    assert portfolio["USD"][Portfolio.AVAILABLE] >= 0


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
        assert sum(order.quantity for order in sell_orders) <= sell_holdings

        staggered_orders = decider._alternate_not_virtual_orders(buy_orders, sell_orders)
        if staggered_orders:
            assert not any(order for order in staggered_orders if order.is_virtual)

        await decider._create_multiple_not_virtual_orders(staggered_orders, trader)

        assert all(decider.highest_sell >= o.price >= decider.lowest_buy
                   for o in sell_orders)

        assert all(decider.highest_sell >= o.price >= decider.lowest_buy
                   for o in buy_orders)


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
                assert current_sell.origin_price > order.origin_price
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

        if strategy_mode not in [StrategyModes.NEUTRAL, StrategyModes.VALLEY, StrategyModes.SELL_SLOPE]:
            # not exactly multiplier because of virtual orders and rounds
            if sell_increase_towards_center:
                expected_quantity = AbstractTradingModeCreator._trunc_with_n_decimal_digits(
                    average_order_quantity * (1 + multiplier/2),
                    8)
                assert abs(current_sell.origin_quantity - expected_quantity) < \
                    multiplier*final_evaluator.increment/(2*final_evaluator.final_eval)
            else:
                expected_quantity = AbstractTradingModeCreator._trunc_with_n_decimal_digits(
                    average_order_quantity * (1 - multiplier/2),
                    8)
                assert abs(current_sell.origin_quantity == expected_quantity) < \
                    multiplier*final_evaluator.increment/(2*final_evaluator.final_eval)


async def _light_check_orders(final_evaluator, trader_inst, expected_buy_count, expected_sell_count, price, portfolio):

    buy_orders, sell_orders = await final_evaluator._generate_staggered_orders(final_evaluator.final_eval, trader_inst)
    assert len(buy_orders) == expected_buy_count
    assert len(sell_orders) == expected_sell_count

    assert all(o.price < price for o in buy_orders)
    assert all(o.price > price for o in sell_orders)

    buy_holdings = trader_inst.get_portfolio().get_portfolio()["ETH"][Portfolio.AVAILABLE]
    assert sum(order.price * order.quantity for order in buy_orders) <= buy_holdings

    sell_holdings = trader_inst.get_portfolio().get_portfolio()["RDN"][Portfolio.AVAILABLE]
    assert sum(order.quantity for order in sell_orders) <= sell_holdings

    staggered_orders = final_evaluator._alternate_not_virtual_orders(buy_orders, sell_orders)
    if staggered_orders:
        assert not any(order for order in staggered_orders if order.is_virtual)

    creator_key = final_evaluator.trading_mode.get_only_creator_key("BTC/USD")
    final_evaluator.trading_mode.creators[final_evaluator.symbol] = final_evaluator.trading_mode.creators["BTC/USD"]
    await final_evaluator._create_not_virtual_orders(final_evaluator.notifier, trader_inst,
                                                     staggered_orders, creator_key)

    open_orders = trader_inst.get_order_manager().get_open_orders()
    if expected_buy_count or expected_sell_count:
        assert len(open_orders) <= final_evaluator.operational_depth

    strategy_mode = final_evaluator.mode
    buy_increase_towards_center = StrategyModeMultipliersDetails[strategy_mode][TradeOrderSide.BUY] == INCREASING

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

    assert portfolio.get_portfolio()["ETH"][Portfolio.AVAILABLE] >= 0
    assert portfolio.get_portfolio()["RDN"][Portfolio.AVAILABLE] >= 0


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
