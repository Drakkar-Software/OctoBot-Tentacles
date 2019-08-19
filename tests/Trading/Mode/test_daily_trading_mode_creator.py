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
import ccxt

from config import EvaluatorStates
from tests.unit_tests.trading_modes_tests.trading_mode_test_toolkit import check_order_limits, check_linked_order, \
    check_orders, check_portfolio, fill_orders
from tests.test_utils.config import load_test_config
from trading.exchanges.exchange_manager import ExchangeManager
from trading.trader.modes import DailyTradingModeCreator
from trading.trader.order import *
from trading.trader.portfolio import Portfolio
from trading.trader.trader_simulator import TraderSimulator


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def _get_tools():
    config = load_test_config()
    symbol = "BTC/USDT"
    exchange_manager = ExchangeManager(config, ccxt.binance, is_simulated=True)
    await exchange_manager.initialize()
    exchange_inst = exchange_manager.get_exchange()
    trader_inst = TraderSimulator(config, exchange_inst, 0.3)
    await trader_inst.portfolio.initialize()
    trader_inst.stop_order_manager()
    trader_inst.portfolio.portfolio["SUB"] = {
        Portfolio.TOTAL: 0.000000000000000000005,
        Portfolio.AVAILABLE: 0.000000000000000000005
    }
    trader_inst.portfolio.portfolio["BNB"] = {
        Portfolio.TOTAL: 0.000000000000000000005,
        Portfolio.AVAILABLE: 0.000000000000000000005
    }
    trader_inst.portfolio.portfolio["USDT"] = {
        Portfolio.TOTAL: 2000,
        Portfolio.AVAILABLE: 2000
    }

    return config, exchange_inst, trader_inst, symbol


async def test_can_create_order():
    config, exchange, trader, symbol = await _get_tools()
    portfolio = trader.get_portfolio()
    # portfolio: "BTC": 10 "USD": 1000
    not_owned_symbol = "ETH/BTC"
    not_owned_market = "BTC/ETH"
    min_trigger_symbol = "SUB/BTC"
    min_trigger_market = "ADA/BNB"

    # order from neutral state => false
    assert not await DailyTradingModeCreator(None).can_create_order(symbol, exchange,
                                                                    EvaluatorStates.NEUTRAL, portfolio)

    # sell order using a currency with 0 available
    assert not await DailyTradingModeCreator(None).can_create_order(not_owned_symbol, exchange,
                                                                    EvaluatorStates.SHORT, portfolio)
    assert not await DailyTradingModeCreator(None).can_create_order(not_owned_symbol, exchange,
                                                                    EvaluatorStates.VERY_SHORT, portfolio)

    # sell order using a currency with < min available
    assert not await DailyTradingModeCreator(None).can_create_order(min_trigger_symbol, exchange,
                                                                    EvaluatorStates.SHORT, portfolio)
    assert not await DailyTradingModeCreator(None).can_create_order(min_trigger_symbol, exchange,
                                                                    EvaluatorStates.VERY_SHORT, portfolio)

    # sell order using a currency with > min available
    assert await DailyTradingModeCreator(None).can_create_order(not_owned_market, exchange,
                                                                EvaluatorStates.SHORT, portfolio)
    assert await DailyTradingModeCreator(None).can_create_order(not_owned_market, exchange,
                                                                EvaluatorStates.VERY_SHORT, portfolio)

    # buy order using a market with 0 available
    assert not await DailyTradingModeCreator(None).can_create_order(not_owned_market, exchange,
                                                                    EvaluatorStates.LONG, portfolio)
    assert not await DailyTradingModeCreator(None).can_create_order(not_owned_market, exchange,
                                                                    EvaluatorStates.VERY_LONG, portfolio)

    # buy order using a market with < min available
    assert not await DailyTradingModeCreator(None).can_create_order(min_trigger_market, exchange,
                                                                    EvaluatorStates.LONG, portfolio)
    assert not await DailyTradingModeCreator(None).can_create_order(min_trigger_market, exchange,
                                                                    EvaluatorStates.VERY_LONG, portfolio)

    # buy order using a market with > min available
    assert await DailyTradingModeCreator(None).can_create_order(not_owned_symbol, exchange,
                                                                EvaluatorStates.LONG, portfolio)
    assert await DailyTradingModeCreator(None).can_create_order(not_owned_symbol, exchange,
                                                                EvaluatorStates.VERY_LONG, portfolio)


async def test_can_create_order_unknown_symbols():
    config, exchange, trader, symbol = await _get_tools()
    portfolio = trader.get_portfolio()
    unknown_symbol = "VI?/BTC"
    unknown_market = "BTC/*s?"
    unknown_everything = "VI?/*s?"

    # buy order with unknown market
    assert not await DailyTradingModeCreator(None).can_create_order(unknown_market, exchange,
                                                                    EvaluatorStates.LONG, portfolio)
    assert not await DailyTradingModeCreator(None).can_create_order(unknown_market, exchange,
                                                                    EvaluatorStates.VERY_LONG, portfolio)
    assert await DailyTradingModeCreator(None).can_create_order(unknown_market, exchange,
                                                                EvaluatorStates.SHORT, portfolio)
    assert await DailyTradingModeCreator(None).can_create_order(unknown_market, exchange,
                                                                EvaluatorStates.VERY_SHORT, portfolio)

    # sell order with unknown symbol
    assert not await DailyTradingModeCreator(None).can_create_order(unknown_symbol, exchange,
                                                                    EvaluatorStates.SHORT, portfolio)
    assert not await DailyTradingModeCreator(None).can_create_order(unknown_symbol, exchange,
                                                                    EvaluatorStates.VERY_SHORT, portfolio)
    assert await DailyTradingModeCreator(None).can_create_order(unknown_symbol, exchange,
                                                                EvaluatorStates.LONG, portfolio)
    assert await DailyTradingModeCreator(None).can_create_order(unknown_symbol, exchange,
                                                                EvaluatorStates.VERY_LONG, portfolio)

    # neutral state with unknown symbol, market and everything
    assert not await DailyTradingModeCreator(None).can_create_order(unknown_symbol, exchange,
                                                                    EvaluatorStates.NEUTRAL, portfolio)
    assert not await DailyTradingModeCreator(None).can_create_order(unknown_market, exchange,
                                                                    EvaluatorStates.NEUTRAL, portfolio)
    assert not await DailyTradingModeCreator(None).can_create_order(unknown_everything, exchange,
                                                                    EvaluatorStates.NEUTRAL, portfolio)


async def test_valid_create_new_order_no_ref_market_as_quote():
    config, exchange, trader, symbol = await _get_tools()

    # change reference market to USDT
    trader.get_trades_manager().reference_market = "USDT"

    portfolio = trader.get_portfolio()
    order_creator = DailyTradingModeCreator(None)

    market_status = exchange.get_market_status(symbol)

    # portfolio: "BTC": 10 "USD": 1000
    last_btc_price = 7009.194999999998

    # order from neutral state
    assert await order_creator.create_new_order(-1, symbol, exchange, trader, portfolio, EvaluatorStates.NEUTRAL) \
        is None
    assert await order_creator.create_new_order(0.5, symbol, exchange, trader, portfolio, EvaluatorStates.NEUTRAL) \
        is None
    assert await order_creator.create_new_order(0, symbol, exchange, trader, portfolio, EvaluatorStates.NEUTRAL) \
        is None
    assert await order_creator.create_new_order(-0.5, symbol, exchange, trader, portfolio, EvaluatorStates.NEUTRAL) \
        is None
    assert await order_creator.create_new_order(-1, symbol, exchange, trader, portfolio, EvaluatorStates.NEUTRAL) \
        is None

    # valid sell limit order (price adapted)
    orders = await order_creator.create_new_order(0.65, symbol, exchange, trader, portfolio, EvaluatorStates.SHORT)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, SellLimitOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == 7062.64011187
    assert order.created_last_price == last_btc_price
    assert order.order_type == TraderOrderType.SELL_LIMIT
    assert order.side == TradeOrderSide.SELL
    assert order.status == OrderStatus.OPEN
    assert order.exchange == exchange
    assert order.trader == trader
    assert order.fee is None
    assert order.market_total_fees == 0
    assert order.filled_price == 0
    assert order.origin_quantity == 7.6
    assert order.filled_quantity == order.origin_quantity
    assert order.is_simulated is True
    assert order.linked_to is None

    check_order_limits(order, market_status)

    assert len(order.linked_orders) == 1
    check_linked_order(order, order.linked_orders[0], TraderOrderType.STOP_LOSS, 6658.73524999, market_status)

    # valid buy limit order with (price and quantity adapted)
    orders = await order_creator.create_new_order(-0.65, symbol, exchange, trader, portfolio, EvaluatorStates.LONG)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, BuyLimitOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == 6955.74988812
    assert order.created_last_price == last_btc_price
    assert order.order_type == TraderOrderType.BUY_LIMIT
    assert order.side == TradeOrderSide.BUY
    assert order.status == OrderStatus.OPEN
    assert order.exchange == exchange
    assert order.trader == trader
    assert order.fee is None
    assert order.market_total_fees == 0
    assert order.filled_price == 0
    assert order.origin_quantity == 0.12554936
    assert order.filled_quantity == order.origin_quantity
    assert order.is_simulated is True
    assert order.linked_to is None

    check_order_limits(order, market_status)

    # assert len(order.linked_orders) == 1  # check linked orders when it will be developed

    truncated_last_price = order_creator._trunc_with_n_decimal_digits(last_btc_price, 8)

    # valid buy market order with (price and quantity adapted)
    orders = await order_creator.create_new_order(-1, symbol, exchange, trader, portfolio, EvaluatorStates.VERY_LONG)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, BuyMarketOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == truncated_last_price
    assert order.created_last_price == truncated_last_price
    assert order.order_type == TraderOrderType.BUY_MARKET
    assert order.side == TradeOrderSide.BUY
    assert order.status == OrderStatus.OPEN
    assert order.exchange == exchange
    assert order.trader == trader
    assert order.fee is None
    assert order.market_total_fees == 0
    assert order.filled_price == 0
    assert order.origin_quantity == 0.11573814
    assert order.filled_quantity == order.origin_quantity
    assert order.is_simulated is True
    assert order.linked_to is None

    check_order_limits(order, market_status)

    # valid buy market order with (price and quantity adapted)
    orders = await order_creator.create_new_order(1, symbol, exchange, trader, portfolio, EvaluatorStates.VERY_SHORT)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, SellMarketOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == truncated_last_price
    assert order.created_last_price == truncated_last_price
    assert order.order_type == TraderOrderType.SELL_MARKET
    assert order.side == TradeOrderSide.SELL
    assert order.status == OrderStatus.OPEN
    assert order.exchange == exchange
    assert order.trader == trader
    assert order.fee is None
    assert order.market_total_fees == 0
    assert order.filled_price == 0
    assert order.origin_quantity == 2.4
    assert order.filled_quantity == order.origin_quantity
    assert order.is_simulated is True
    assert order.linked_to is None

    check_order_limits(order, market_status)


async def test_valid_create_new_order_ref_market_as_quote():
    config, exchange, trader, symbol = await _get_tools()
    portfolio = trader.get_portfolio()
    order_creator = DailyTradingModeCreator(None)

    market_status = exchange.get_market_status(symbol)

    # portfolio: "BTC": 10 "USD": 1000
    last_btc_price = 7009.194999999998

    # order from neutral state
    assert await order_creator.create_new_order(-1, symbol, exchange, trader, portfolio, EvaluatorStates.NEUTRAL) \
        is None
    assert await order_creator.create_new_order(0.5, symbol, exchange, trader, portfolio, EvaluatorStates.NEUTRAL) \
        is None
    assert await order_creator.create_new_order(0, symbol, exchange, trader, portfolio, EvaluatorStates.NEUTRAL) \
        is None
    assert await order_creator.create_new_order(-0.5, symbol, exchange, trader, portfolio, EvaluatorStates.NEUTRAL) \
        is None
    assert await order_creator.create_new_order(-1, symbol, exchange, trader, portfolio, EvaluatorStates.NEUTRAL) \
        is None

    # valid sell limit order (price adapted)
    orders = await order_creator.create_new_order(0.65, symbol, exchange, trader, portfolio, EvaluatorStates.SHORT)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, SellLimitOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == 7062.64011187
    assert order.created_last_price == last_btc_price
    assert order.order_type == TraderOrderType.SELL_LIMIT
    assert order.side == TradeOrderSide.SELL
    assert order.status == OrderStatus.OPEN
    assert order.exchange == exchange
    assert order.trader == trader
    assert order.fee is None
    assert order.market_total_fees == 0
    assert order.filled_price == 0
    assert order.origin_quantity == 4.4
    assert order.filled_quantity == order.origin_quantity
    assert order.is_simulated is True
    assert order.linked_to is None

    check_order_limits(order, market_status)

    assert len(order.linked_orders) == 1
    check_linked_order(order, order.linked_orders[0], TraderOrderType.STOP_LOSS, 6658.73524999, market_status)

    # valid buy limit order with (price and quantity adapted)
    orders = await order_creator.create_new_order(-0.65, symbol, exchange, trader, portfolio, EvaluatorStates.LONG)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, BuyLimitOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == 6955.74988812
    assert order.created_last_price == last_btc_price
    assert order.order_type == TraderOrderType.BUY_LIMIT
    assert order.side == TradeOrderSide.BUY
    assert order.status == OrderStatus.OPEN
    assert order.exchange == exchange
    assert order.trader == trader
    assert order.fee is None
    assert order.market_total_fees == 0
    assert order.filled_price == 0
    assert order.origin_quantity == 0.21685799
    assert order.filled_quantity == order.origin_quantity
    assert order.is_simulated is True
    assert order.linked_to is None

    check_order_limits(order, market_status)

    # assert len(order.linked_orders) == 1  # check linked orders when it will be developed

    truncated_last_price = order_creator._trunc_with_n_decimal_digits(last_btc_price, 8)

    # valid buy market order with (price and quantity adapted)
    orders = await order_creator.create_new_order(-1, symbol, exchange, trader, portfolio, EvaluatorStates.VERY_LONG)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, BuyMarketOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == truncated_last_price
    assert order.created_last_price == truncated_last_price
    assert order.order_type == TraderOrderType.BUY_MARKET
    assert order.side == TradeOrderSide.BUY
    assert order.status == OrderStatus.OPEN
    assert order.exchange == exchange
    assert order.trader == trader
    assert order.fee is None
    assert order.market_total_fees == 0
    assert order.filled_price == 0
    assert order.origin_quantity == 0.07013502
    assert order.filled_quantity == order.origin_quantity
    assert order.is_simulated is True
    assert order.linked_to is None

    check_order_limits(order, market_status)

    # valid buy market order with (price and quantity adapted)
    orders = await order_creator.create_new_order(1, symbol, exchange, trader, portfolio, EvaluatorStates.VERY_SHORT)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, SellMarketOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == truncated_last_price
    assert order.created_last_price == truncated_last_price
    assert order.order_type == TraderOrderType.SELL_MARKET
    assert order.side == TradeOrderSide.SELL
    assert order.status == OrderStatus.OPEN
    assert order.exchange == exchange
    assert order.trader == trader
    assert order.fee is None
    assert order.market_total_fees == 0
    assert order.filled_price == 0
    assert order.origin_quantity == 4.032
    assert order.filled_quantity == order.origin_quantity
    assert order.is_simulated is True
    assert order.linked_to is None

    check_order_limits(order, market_status)


async def test_invalid_create_new_order():
    config, exchange, trader, symbol = await _get_tools()
    portfolio = trader.get_portfolio()
    order_creator = DailyTradingModeCreator(None)

    # portfolio: "BTC": 10 "USD": 1000
    min_trigger_market = "ADA/BNB"

    # invalid buy order with not trade data
    orders = await order_creator.create_new_order(0.6, min_trigger_market, exchange,
                                                  trader, portfolio, EvaluatorStates.SHORT)
    assert orders is None

    trader.portfolio.portfolio["BTC"] = {
        Portfolio.TOTAL: 2000,
        Portfolio.AVAILABLE: 0.000000000000000000005
    }

    # invalid buy order with not enough currency to sell
    orders = await order_creator.create_new_order(0.6, symbol, exchange, trader, portfolio, EvaluatorStates.SHORT)
    assert len(orders) == 0

    trader.portfolio.portfolio["USDT"] = {
        Portfolio.TOTAL: 2000,
        Portfolio.AVAILABLE: 0.000000000000000000005
    }

    # invalid buy order with not enough currency to buy
    orders = await order_creator.create_new_order(-0.6, symbol, exchange, trader, portfolio, EvaluatorStates.LONG)
    assert len(orders) == 0


async def test_create_new_order_with_dusts_included():
    config, exchange, trader, symbol = await _get_tools()
    portfolio = trader.get_portfolio()
    order_creator = DailyTradingModeCreator(None)

    trader.portfolio.portfolio["BTC"] = {
        Portfolio.TOTAL: 0.000015,
        Portfolio.AVAILABLE: 0.000015
    }
    # trigger order that should not sell everything but does sell everything because remaining amount is not sellable
    orders = await order_creator.create_new_order(0.6, symbol, exchange, trader, portfolio, EvaluatorStates.VERY_SHORT)
    assert len(orders) == 1
    assert trader.portfolio.portfolio["BTC"][Portfolio.AVAILABLE] == 0
    assert trader.portfolio.portfolio["BTC"][Portfolio.TOTAL] == orders[0].origin_quantity

    test_currency = "NEO"
    test_pair = f"{test_currency}/BTC"
    trader.portfolio.portfolio[test_currency] = {
        Portfolio.TOTAL: 0.44,
        Portfolio.AVAILABLE: 0.44
    }
    # trigger order that should not sell everything but does sell everything because remaining amount is not sellable
    orders = await order_creator.create_new_order(0.75445456165478, test_pair,
                                                  exchange, trader, portfolio, EvaluatorStates.SHORT)
    assert len(orders) == 1
    assert trader.portfolio.portfolio[test_currency][Portfolio.AVAILABLE] == 0
    assert trader.portfolio.portfolio[test_currency][Portfolio.TOTAL] == orders[0].origin_quantity


async def test_split_create_new_order():
    config, exchange, trader, symbol = await _get_tools()
    portfolio = trader.get_portfolio()

    # change reference market to get more orders
    trader.get_trades_manager().reference_market = "USDT"

    order_creator = DailyTradingModeCreator(None)
    last_btc_price = 7009.194999999998

    market_status = exchange.get_market_status(symbol)
    trader.portfolio.portfolio["BTC"] = {
        Portfolio.TOTAL: 2000000001,
        Portfolio.AVAILABLE: 2000000001
    }
    # split orders because order too big and coin price too high
    orders = await order_creator.create_new_order(0.6, symbol, exchange, trader, portfolio, EvaluatorStates.SHORT)
    assert len(orders) == 11
    adapted_order = orders[0]
    identical_orders = orders[1:]

    assert isinstance(adapted_order, SellLimitOrder)
    assert adapted_order.currency == "BTC"
    assert adapted_order.symbol == "BTC/USDT"
    assert adapted_order.origin_price == 7065.26855999
    assert adapted_order.created_last_price == last_btc_price
    assert adapted_order.order_type == TraderOrderType.SELL_LIMIT
    assert adapted_order.side == TradeOrderSide.SELL
    assert adapted_order.status == OrderStatus.OPEN
    assert adapted_order.exchange == exchange
    assert adapted_order.trader == trader
    assert adapted_order.fee is None
    assert adapted_order.market_total_fees == 0
    assert adapted_order.filled_price == 0
    assert adapted_order.origin_quantity == 64625635.97358092
    assert adapted_order.filled_quantity == adapted_order.origin_quantity
    assert adapted_order.is_simulated is True
    assert adapted_order.linked_to is None

    check_order_limits(adapted_order, market_status)

    assert len(adapted_order.linked_orders) == 1
    check_linked_order(adapted_order, adapted_order.linked_orders[0],
                       TraderOrderType.STOP_LOSS, 6658.73524999, market_status)

    for order in identical_orders:
        assert isinstance(order, SellLimitOrder)
        assert order.currency == adapted_order.currency
        assert order.symbol == adapted_order.symbol
        assert order.origin_price == adapted_order.origin_price
        assert order.created_last_price == adapted_order.created_last_price
        assert order.order_type == adapted_order.order_type
        assert order.side == adapted_order.side
        assert order.status == adapted_order.status
        assert order.exchange == adapted_order.exchange
        assert order.trader == adapted_order.trader
        assert order.fee == adapted_order.fee
        assert order.market_total_fees == adapted_order.market_total_fees
        assert order.filled_price == adapted_order.filled_price
        assert order.origin_quantity == 141537436.47664192
        assert order.origin_quantity > adapted_order.origin_quantity
        assert order.filled_quantity > adapted_order.filled_quantity
        assert order.is_simulated == adapted_order.is_simulated
        assert order.linked_to == adapted_order.linked_to
        assert len(order.linked_orders) == 1

        check_order_limits(order, market_status)
        check_linked_order(order, order.linked_orders[0], TraderOrderType.STOP_LOSS, 6658.73524999, market_status)

    trader.portfolio.portfolio["USDT"] = {
        Portfolio.TOTAL: 40000000000,
        Portfolio.AVAILABLE: 40000000000
    }

    # set btc last price to 6998.55407999 * 0.000001 = 0.00699855408
    exchange.get_exchange().set_recent_trades_multiplier_factor(0.000001)
    # split orders because order too big and too many coins
    orders = await order_creator.create_new_order(-0.6, symbol, exchange, trader, portfolio, EvaluatorStates.LONG)
    assert len(orders) == 3
    adapted_order = orders[0]
    identical_orders = orders[1:]

    assert isinstance(adapted_order, BuyLimitOrder)
    assert adapted_order.currency == "BTC"
    assert adapted_order.symbol == "BTC/USDT"
    assert adapted_order.origin_price == 0.00695312
    assert adapted_order.created_last_price == 0.0070091949999999984
    assert adapted_order.order_type == TraderOrderType.BUY_LIMIT
    assert adapted_order.side == TradeOrderSide.BUY
    assert adapted_order.status == OrderStatus.OPEN
    assert adapted_order.exchange == exchange
    assert adapted_order.trader == trader
    assert adapted_order.fee is None
    assert adapted_order.market_total_fees == 0
    assert adapted_order.filled_price == 0
    assert adapted_order.origin_quantity == 396851564266.65326
    assert adapted_order.filled_quantity == adapted_order.origin_quantity
    assert adapted_order.is_simulated is True
    assert adapted_order.linked_to is None

    check_order_limits(adapted_order, market_status)

    # assert len(order.linked_orders) == 1  # check linked orders when it will be developed

    for order in identical_orders:
        assert isinstance(order, BuyLimitOrder)
        assert order.currency == adapted_order.currency
        assert order.symbol == adapted_order.symbol
        assert order.origin_price == adapted_order.origin_price
        assert order.created_last_price == adapted_order.created_last_price
        assert order.order_type == adapted_order.order_type
        assert order.side == adapted_order.side
        assert order.status == adapted_order.status
        assert order.exchange == adapted_order.exchange
        assert order.trader == adapted_order.trader
        assert order.fee == adapted_order.fee
        assert order.market_total_fees == adapted_order.market_total_fees
        assert order.filled_price == adapted_order.filled_price
        assert order.origin_quantity == 1000000000000.0
        assert order.origin_quantity > adapted_order.origin_quantity
        assert order.filled_quantity > adapted_order.filled_quantity
        assert order.is_simulated == adapted_order.is_simulated
        assert order.linked_to == adapted_order.linked_to

        check_order_limits(order, market_status)

        # assert len(order.linked_orders) == 1 # check linked orders when it will be developed


async def test_valid_create_new_order_without_stop_order():
    config, exchange, trader, symbol = await _get_tools()

    # change reference market to USDT
    trader.get_trades_manager().reference_market = "USDT"

    portfolio = trader.get_portfolio()
    order_creator = DailyTradingModeCreator(None)

    # force no stop orders
    order_creator.USE_STOP_ORDERS = False

    market_status = exchange.get_market_status(symbol)

    # portfolio: "BTC": 10 "USD": 1000
    last_btc_price = 7009.194999999998

    # valid sell limit order (price adapted)
    orders = await order_creator.create_new_order(0.65, symbol, exchange, trader, portfolio, EvaluatorStates.SHORT)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, SellLimitOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == 7062.64011187
    assert order.created_last_price == last_btc_price
    assert order.order_type == TraderOrderType.SELL_LIMIT
    assert order.side == TradeOrderSide.SELL
    assert order.status == OrderStatus.OPEN
    assert order.exchange == exchange
    assert order.trader == trader
    assert order.fee is None
    assert order.market_total_fees == 0
    assert order.filled_price == 0
    assert order.origin_quantity == 7.6
    assert order.filled_quantity == order.origin_quantity
    assert order.is_simulated is True
    assert order.linked_to is None

    check_order_limits(order, market_status)

    # assert no stop orders
    assert len(order.linked_orders) == 0


def _get_evaluations_gradient(step):
    nb_steps = 1/step
    return [i/nb_steps for i in range(int(-nb_steps), int(nb_steps+1), 1)]


def _get_states_gradient_with_invald_states():
    states = [state for state in EvaluatorStates]
    states += [None, 1, {'toto': 1}, math.nan]
    return states


def _get_irrationnal_numbers():
    irrationals = [math.pi, math.sqrt(2), math.sqrt(3), math.sqrt(5), math.sqrt(7), math.sqrt(11), math.sqrt(73), 10/3]
    return [1/i for i in irrationals]


def _reset_portfolio(portfolio):
    portfolio.set_starting_simulated_portfolio()
    portfolio.portfolio["USDT"] = {
        Portfolio.TOTAL: 2000,
        Portfolio.AVAILABLE: 2000
    }


async def test_create_order_using_a_lot_of_different_inputs_with_portfolio_reset():
    config, exchange, trader, symbol = await _get_tools()
    portfolio = trader.get_portfolio()
    order_creator = DailyTradingModeCreator(None)
    gradient_step = 0.001
    nb_orders = 1
    market_status = exchange.get_market_status(symbol)
    initial_portfolio = copy.deepcopy(portfolio.portfolio)
    # portfolio: "BTC": 10 "USD": 1000
    min_trigger_market = "ADA/BNB"

    for state in _get_states_gradient_with_invald_states():
        for evaluation in _get_evaluations_gradient(gradient_step):
            _reset_portfolio(portfolio)
            # orders are possible
            orders = await order_creator.create_new_order(evaluation, symbol, exchange, trader, portfolio, state)
            check_orders(orders, evaluation, state, nb_orders, market_status)
            check_portfolio(portfolio, initial_portfolio, orders)
            # orders are impossible
            orders = await order_creator.create_new_order(evaluation, min_trigger_market, exchange,
                                                          trader, portfolio, state)
            check_orders(orders, evaluation, state, 0, market_status)
            check_portfolio(portfolio, initial_portfolio, orders)

        for evaluation in _get_irrationnal_numbers():
            # orders are possible
            _reset_portfolio(portfolio)
            orders = await order_creator.create_new_order(evaluation, symbol, exchange, trader, portfolio, state)
            check_orders(orders, evaluation, state, nb_orders, market_status)
            check_portfolio(portfolio, initial_portfolio, orders)
            # orders are impossible
            orders = await order_creator.create_new_order(evaluation, min_trigger_market, exchange,
                                                          trader, portfolio, state)
            check_orders(orders, evaluation, state, 0, market_status)
            check_portfolio(portfolio, initial_portfolio, orders)

        _reset_portfolio(portfolio)
        # orders are possible
        orders = await order_creator.create_new_order(math.nan, symbol, exchange, trader, portfolio, state)
        check_orders(orders, math.nan, state, nb_orders, market_status)
        check_portfolio(portfolio, initial_portfolio, orders)
        # orders are impossible
        orders = await order_creator.create_new_order(math.nan, min_trigger_market, exchange, trader, portfolio, state)
        check_orders(orders, math.nan, state, 0, market_status)
        check_portfolio(portfolio, initial_portfolio, orders)


async def test_create_order_using_a_lot_of_different_inputs_without_portfolio_reset():
    config, exchange, trader, symbol = await _get_tools()
    portfolio = trader.get_portfolio()
    order_creator = DailyTradingModeCreator(None)
    gradient_step = 0.001
    nb_orders = "unknown"
    market_status = exchange.get_market_status(symbol)
    # portfolio: "BTC": 10 "USD": 1000
    min_trigger_market = "ADA/BNB"

    _reset_portfolio(portfolio)
    initial_portfolio = portfolio.portfolio
    for state in _get_states_gradient_with_invald_states():
        for evaluation in _get_evaluations_gradient(gradient_step):
            # orders are possible
            orders = await order_creator.create_new_order(evaluation, symbol, exchange, trader, portfolio, state)
            check_orders(orders, evaluation, state, nb_orders, market_status)
            check_portfolio(portfolio, initial_portfolio, orders, True)
            await fill_orders(orders, trader)
            # orders are impossible
            orders = await order_creator.create_new_order(evaluation, min_trigger_market,
                                                          exchange, trader, portfolio, state)
            check_orders(orders, evaluation, state, 0, market_status)
            check_portfolio(portfolio, initial_portfolio, orders, True)
            await fill_orders(orders, trader)

    _reset_portfolio(portfolio)
    initial_portfolio = portfolio.portfolio
    for state in _get_states_gradient_with_invald_states():
        for evaluation in _get_irrationnal_numbers():
            # orders are possible
            orders = await order_creator.create_new_order(evaluation, symbol, exchange, trader, portfolio, state)
            check_orders(orders, evaluation, state, nb_orders, market_status)
            check_portfolio(portfolio, initial_portfolio, orders, True)
            await fill_orders(orders, trader)
            # orders are impossible
            orders = await order_creator.create_new_order(evaluation, min_trigger_market,
                                                          exchange, trader, portfolio, state)
            check_orders(orders, evaluation, state, 0, market_status)
            check_portfolio(portfolio, initial_portfolio, orders, True)
            await fill_orders(orders, trader)

    _reset_portfolio(portfolio)
    initial_portfolio = portfolio.portfolio
    for state in _get_states_gradient_with_invald_states():
        # orders are possible
        orders = await order_creator.create_new_order(math.nan, symbol, exchange, trader, portfolio, state)
        check_orders(orders, math.nan, state, nb_orders, market_status)
        check_portfolio(portfolio, initial_portfolio, orders, True)
        await fill_orders(orders, trader)
        # orders are impossible
        orders = await order_creator.create_new_order(math.nan, min_trigger_market, exchange, trader, portfolio, state)
        check_orders(orders, math.nan, state, 0, market_status)
        check_portfolio(portfolio, initial_portfolio, orders, True)
        await fill_orders(orders, trader)


async def test_create_multiple_buy_orders_after_fill():
    config, exchange, trader, symbol = await _get_tools()
    await trader.trades_manager.initialize()
    order_creator = DailyTradingModeCreator(None)
    nb_traded_symbols = order_creator.get_number_of_traded_assets(trader)
    assert nb_traded_symbols > 2
    portfolio = trader.get_portfolio()

    # with BTC/USDT
    await ensure_smaller_orders(order_creator, symbol, exchange, trader, portfolio)

    # with another symbol with 0 quantity when start
    await ensure_smaller_orders(order_creator, "ADA/BTC", exchange, trader, portfolio)


async def ensure_smaller_orders(order_creator, symbol, exchange, trader, portfolio):
    state = EvaluatorStates.VERY_LONG

    # first call: biggest order
    orders1 = (await order_creator.create_new_order(-1, symbol, exchange, trader, portfolio, state))
    await fill_orders(orders1, trader)

    state = EvaluatorStates.LONG
    # second call: smaller order (same with very long as with long)
    orders2 = (await order_creator.create_new_order(-0.6, symbol, exchange, trader, portfolio, state))
    assert orders1[0].origin_quantity > orders2[0].origin_quantity
    await fill_orders(orders2, trader)

    # third call: even smaller order
    orders3 = (await order_creator.create_new_order(-0.6, symbol, exchange, trader, portfolio, state))
    assert orders2[0].origin_quantity > orders3[0].origin_quantity
    await fill_orders(orders3, trader)

    # third call: even-even smaller order
    orders4 = (await order_creator.create_new_order(-0.6, symbol, exchange, trader, portfolio, state))
    assert orders3[0].origin_quantity > orders4[0].origin_quantity
    await fill_orders(orders4, trader)
