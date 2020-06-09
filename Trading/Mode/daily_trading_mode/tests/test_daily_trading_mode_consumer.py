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
import math
import pytest
from os.path import join
import copy

from octobot_backtesting.api.backtesting import initialize_backtesting, get_importers
from octobot_backtesting.api.importer import stop_importer
from octobot_channels.util.channel_creator import create_all_subclasses_channel
from octobot_commons.asyncio_tools import wait_asyncio_next_cycle
from octobot_commons.constants import PORTFOLIO_TOTAL, PORTFOLIO_AVAILABLE
from octobot_commons.tests.test_config import load_test_config, TEST_CONFIG_FOLDER
from octobot_trading.api.symbol_data import force_set_mark_price
from octobot_trading.channels.exchange_channel import ExchangeChannel, TimeFrameExchangeChannel, set_chan
from octobot_trading.constants import CONFIG_SIMULATOR, CONFIG_STARTING_PORTFOLIO
from octobot_trading.enums import EvaluatorStates, TraderOrderType, TradeOrderSide, OrderStatus
from octobot_trading.exchanges.exchange_manager import ExchangeManager
from octobot_trading.exchanges.exchange_simulator import ExchangeSimulator
from octobot_trading.exchanges.rest_exchange import RestExchange
from octobot_trading.orders.order_adapter import trunc_with_n_decimal_digits
from octobot_trading.orders.types import SellMarketOrder, BuyMarketOrder, SellLimitOrder, BuyLimitOrder
from octobot_trading.traders.trader_simulator import TraderSimulator
from tentacles.Trading.Mode import DailyTradingMode
from tests.unit_tests.trading_modes_tests.trading_mode_test_toolkit import check_order_limits, check_linked_order, \
    check_orders, check_portfolio, fill_orders


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def _get_tools():
    symbol = "BTC/USDT"
    config = load_test_config()
    config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO]["SUB"] = 0.000000000000000000005
    config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO]["BNB"] = 0.000000000000000000005
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

    mode = DailyTradingMode(config, exchange_manager)
    await mode.initialize()
    # add mode to exchange manager so that it can be stopped and freed from memory
    exchange_manager.trading_modes.append(mode)
    consumer = mode.consumers[0]

    # set BTC/USDT price at 7009.194999999998 USDT
    last_btc_price = 7009.194999999998
    force_set_mark_price(exchange_manager, symbol, last_btc_price)

    return exchange_manager, trader, symbol, consumer, last_btc_price


async def _stop(exchange_manager):
    for importer in get_importers(exchange_manager.exchange.backtesting):
        await stop_importer(importer)
    await exchange_manager.exchange.backtesting.stop()
    await exchange_manager.stop()
    # let updaters gracefully shutdown
    await wait_asyncio_next_cycle()


async def test_valid_create_new_orders_no_ref_market_as_quote():
    try:
        exchange_manager, trader, symbol, consumer, last_btc_price = await _get_tools()

        # change reference market to USDT
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio_profitability.reference_market = "USDT"
        exchange_manager.exchange_personal_data.portfolio_manager.reference_market = "USDT"
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio_profitability.currencies_last_prices[
            symbol] = last_btc_price
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio_profitability.portfolio_current_value = \
            last_btc_price * 10 + 1000

        market_status = exchange_manager.exchange.get_market_status(symbol, with_fixer=False)

        # portfolio: "BTC": 10 "USD": 1000
        # order from neutral state
        assert await consumer.create_new_orders(symbol, -1, EvaluatorStates.NEUTRAL.value) == []
        assert await consumer.create_new_orders(symbol, 0.5, EvaluatorStates.NEUTRAL.value) == []
        assert await consumer.create_new_orders(symbol, 0, EvaluatorStates.NEUTRAL.value) == []
        assert await consumer.create_new_orders(symbol, -0.5, EvaluatorStates.NEUTRAL.value) == []
        assert await consumer.create_new_orders(symbol, -1, EvaluatorStates.NEUTRAL.value) == []

        # valid sell limit order (price adapted)
        orders = await consumer.create_new_orders(symbol, 0.65, EvaluatorStates.SHORT.value)
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
        assert order.exchange_manager == exchange_manager
        assert order.trader == trader
        assert order.fee is None
        assert order.filled_price == 0
        assert order.origin_quantity == 7.6
        assert order.filled_quantity == order.origin_quantity
        assert order.simulated is True
        assert order.linked_to is None

        check_order_limits(order, market_status)

        assert len(order.linked_orders) == 1
        check_linked_order(order, order.linked_orders[0], TraderOrderType.STOP_LOSS, 6658.73524999, market_status)

        # valid buy limit order with (price and quantity adapted)
        orders = await consumer.create_new_orders(symbol, -0.65, EvaluatorStates.LONG.value)
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
        assert order.exchange_manager == exchange_manager
        assert order.trader == trader
        assert order.fee is None
        assert order.filled_price == 0
        assert order.origin_quantity == 0.12554936
        assert order.filled_quantity == order.origin_quantity
        assert order.simulated is True
        assert order.linked_to is None

        check_order_limits(order, market_status)

        # assert len(order.linked_orders) == 1  # check linked orders when it will be developed

        truncated_last_price = trunc_with_n_decimal_digits(last_btc_price, 8)

        # valid buy market order with (price and quantity adapted)
        orders = await consumer.create_new_orders(symbol, -1, EvaluatorStates.VERY_LONG.value)
        assert len(orders) == 1
        order = orders[0]
        assert isinstance(order, BuyMarketOrder)
        assert order.currency == "BTC"
        assert order.symbol == "BTC/USDT"
        assert order.origin_price == truncated_last_price
        assert order.created_last_price == truncated_last_price
        assert order.order_type == TraderOrderType.BUY_MARKET
        assert order.side == TradeOrderSide.BUY
        assert order.status == OrderStatus.FILLED
        # order has been cleared
        assert order.exchange_manager is None
        assert order.trader is None
        assert order.fee
        assert order.filled_price == 7009.19499999
        assert order.origin_quantity == 0.11573814
        assert order.filled_quantity == order.origin_quantity
        assert order.simulated is True
        assert order.linked_to is None

        check_order_limits(order, market_status)

        # valid buy market order with (price and quantity adapted)
        orders = await consumer.create_new_orders(symbol, 1, EvaluatorStates.VERY_SHORT.value)
        assert len(orders) == 1
        order = orders[0]
        assert isinstance(order, SellMarketOrder)
        assert order.currency == "BTC"
        assert order.symbol == "BTC/USDT"
        assert order.origin_price == truncated_last_price
        assert order.created_last_price == truncated_last_price
        assert order.order_type == TraderOrderType.SELL_MARKET
        assert order.side == TradeOrderSide.SELL
        assert order.status == OrderStatus.FILLED
        assert order.exchange_manager is None
        assert order.trader is None
        assert order.fee
        assert order.filled_price == 7009.19499999
        assert order.origin_quantity == 2.5156224
        assert order.filled_quantity == order.origin_quantity
        assert order.simulated is True
        assert order.linked_to is None

        check_order_limits(order, market_status)
    finally:
        await _stop(exchange_manager)


async def test_valid_create_new_orders_ref_market_as_quote():
    try:
        exchange_manager, trader, symbol, consumer, last_btc_price = await _get_tools()

        exchange_manager.exchange_personal_data.portfolio_manager.portfolio_profitability.currencies_last_prices[
            symbol] = last_btc_price
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio_profitability.portfolio_current_value = \
            10 + 1000/last_btc_price

        # portfolio: "BTC": 10 "USD": 1000
        # order from neutral state
        assert await consumer.create_new_orders(symbol, -1, EvaluatorStates.NEUTRAL.value) == []
        assert await consumer.create_new_orders(symbol, 0.5, EvaluatorStates.NEUTRAL.value) == []
        assert await consumer.create_new_orders(symbol, 0, EvaluatorStates.NEUTRAL.value) == []
        assert await consumer.create_new_orders(symbol, -0.5, EvaluatorStates.NEUTRAL.value) == []
        assert await consumer.create_new_orders(symbol, -1, EvaluatorStates.NEUTRAL.value) == []

        # valid sell limit order (price adapted)
        orders = await consumer.create_new_orders(symbol, 0.65, EvaluatorStates.SHORT.value)
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
        assert order.exchange_manager == exchange_manager
        assert order.trader == trader
        assert order.fee is None
        assert order.filled_price == 0
        assert order.origin_quantity == 4.4
        assert order.filled_quantity == order.origin_quantity
        assert order.simulated is True
        assert order.linked_to is None

        market_status = exchange_manager.exchange.get_market_status(symbol, with_fixer=False)
        check_order_limits(order, market_status)

        assert len(order.linked_orders) == 1
        check_linked_order(order, order.linked_orders[0], TraderOrderType.STOP_LOSS, 6658.73524999, market_status)

        # valid buy limit order with (price and quantity adapted)
        orders = await consumer.create_new_orders(symbol, -0.65, EvaluatorStates.LONG.value)
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
        assert order.exchange_manager == exchange_manager
        assert order.trader == trader
        assert order.fee is None
        assert order.filled_price == 0
        assert order.origin_quantity == 0.21685799
        assert order.filled_quantity == order.origin_quantity
        assert order.simulated is True
        assert order.linked_to is None

        check_order_limits(order, market_status)

        # assert len(order.linked_orders) == 1  # check linked orders when it will be developed

        truncated_last_price = trunc_with_n_decimal_digits(last_btc_price, 8)

        # valid buy market order with (price and quantity adapted)
        orders = await consumer.create_new_orders(symbol, -1, EvaluatorStates.VERY_LONG.value)
        assert len(orders) == 1
        order = orders[0]
        assert isinstance(order, BuyMarketOrder)
        assert order.currency == "BTC"
        assert order.symbol == "BTC/USDT"
        assert order.origin_price == truncated_last_price
        assert order.created_last_price == truncated_last_price
        assert order.order_type == TraderOrderType.BUY_MARKET
        assert order.side == TradeOrderSide.BUY
        assert order.status == OrderStatus.FILLED
        assert order.filled_price == 7009.19499999
        assert order.origin_quantity == 0.07013502
        assert order.filled_quantity == order.origin_quantity
        assert order.simulated is True
        assert order.linked_to is None

        check_order_limits(order, market_status)

        # valid buy market order with (price and quantity adapted)
        orders = await consumer.create_new_orders(symbol, 1, EvaluatorStates.VERY_SHORT.value)
        assert len(orders) == 1
        order = orders[0]
        assert isinstance(order, SellMarketOrder)
        assert order.currency == "BTC"
        assert order.symbol == "BTC/USDT"
        assert order.origin_price == truncated_last_price
        assert order.created_last_price == truncated_last_price
        assert order.order_type == TraderOrderType.SELL_MARKET
        assert order.side == TradeOrderSide.SELL
        assert order.status == OrderStatus.FILLED
        assert order.fee
        assert order.filled_price == 7009.19499999
        assert order.origin_quantity == 4.08244671
        assert order.filled_quantity == order.origin_quantity
        assert order.simulated is True
        assert order.linked_to is None

        check_order_limits(order, market_status)
    finally:
        await _stop(exchange_manager)


async def test_invalid_create_new_orders():
    try:
        exchange_manager, trader, symbol, consumer, last_btc_price = await _get_tools()

        # portfolio: "BTC": 10 "USD": 1000
        min_trigger_market = "ADA/BNB"

        # invalid sell order with not trade data
        import octobot_trading.constants
        octobot_trading.constants.ORDER_DATA_FETCHING_TIMEOUT = 0.1
        assert await consumer.create_new_orders(min_trigger_market, 0.6, EvaluatorStates.SHORT.value, timeout=1) == []

        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio = {
            "BTC": {
                PORTFOLIO_TOTAL: 2000,
                PORTFOLIO_AVAILABLE: 0.000000000000000000005
            }
        }

        # invalid sell order with not enough currency to sell
        orders = await consumer.create_new_orders(symbol, 0.6, EvaluatorStates.SHORT.value)
        assert len(orders) == 0

        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio = {
            "USDT": {
                PORTFOLIO_TOTAL: 2000,
                PORTFOLIO_AVAILABLE: 0.000000000000000000005
            }
        }

        # invalid buy order with not enough currency to buy
        orders = await consumer.create_new_orders(symbol, -0.6, EvaluatorStates.LONG.value)
        assert len(orders) == 0
    finally:
        await _stop(exchange_manager)


async def test_create_new_orders_with_dusts_included():
    try:
        exchange_manager, trader, symbol, consumer, last_btc_price = await _get_tools()

        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio = {
            "BTC": {
                PORTFOLIO_TOTAL: 0.000015,
                PORTFOLIO_AVAILABLE: 0.000015
            }
        }
        # trigger order that should not sell everything but does sell everything because remaining amount
        # is not sellable
        orders = await consumer.create_new_orders(symbol, 0.6, EvaluatorStates.VERY_SHORT.value)
        assert len(orders) == 1
        assert exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio["BTC"] == {
            PORTFOLIO_TOTAL:  0,
            PORTFOLIO_AVAILABLE: 0
        }

        test_currency = "NEO"
        test_pair = f"{test_currency}/BTC"
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio = {
            test_currency: {
                PORTFOLIO_TOTAL: 0.44,
                PORTFOLIO_AVAILABLE: 0.44
            }
        }
        force_set_mark_price(exchange_manager, test_pair, 0.005318)
        # trigger order that should not sell everything but does sell everything because remaining amount
        # is not sellable
        orders = await consumer.create_new_orders(test_pair, 0.75445456165478, EvaluatorStates.SHORT.value)
        assert len(orders) == 1
        assert exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio[test_currency] == {
            PORTFOLIO_TOTAL:  orders[0].origin_quantity,
            PORTFOLIO_AVAILABLE: 0
        }
    finally:
        await _stop(exchange_manager)


async def test_split_create_new_orders():
    try:
        exchange_manager, trader, symbol, consumer, last_btc_price = await _get_tools()

        # change reference market to get more orders
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio_profitability.reference_market = "USDT"
        exchange_manager.exchange_personal_data.portfolio_manager.reference_market = "USDT"
        market_status = exchange_manager.exchange.get_market_status(symbol, with_fixer=False)
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio = {
            "BTC": {
                PORTFOLIO_TOTAL: 2000000001,
                PORTFOLIO_AVAILABLE: 2000000001
            }
        }
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio_profitability.currencies_last_prices[
            symbol] = last_btc_price
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio_profitability.portfolio_current_value = \
            last_btc_price * 2000000001 + 1000

        # split orders because order too big and coin price too high
        orders = await consumer.create_new_orders(symbol, 0.6, EvaluatorStates.SHORT.value)
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
        assert adapted_order.exchange_manager == exchange_manager
        assert adapted_order.trader == trader
        assert adapted_order.fee is None
        assert adapted_order.filled_price == 0
        assert adapted_order.origin_quantity == 64625635.97358092
        assert adapted_order.filled_quantity == adapted_order.origin_quantity
        assert adapted_order.simulated is True
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
            assert order.exchange_manager == adapted_order.exchange_manager
            assert order.trader == adapted_order.trader
            assert order.fee == adapted_order.fee
            assert order.filled_price == adapted_order.filled_price
            assert order.origin_quantity == 141537436.47664192
            assert order.origin_quantity > adapted_order.origin_quantity
            assert order.filled_quantity > adapted_order.filled_quantity
            assert order.simulated == adapted_order.simulated
            assert order.linked_to == adapted_order.linked_to
            assert len(order.linked_orders) == 1

            check_order_limits(order, market_status)
            check_linked_order(order, order.linked_orders[0], TraderOrderType.STOP_LOSS, 6658.73524999, market_status)

        exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio = {
            "USDT": {
                PORTFOLIO_TOTAL: 40000000000,
                PORTFOLIO_AVAILABLE: 40000000000
            }
        }

        # set btc last price to 6998.55407999 * 0.000001 = 0.00699855408
        force_set_mark_price(exchange_manager, symbol, last_btc_price*0.000001)
        # split orders because order too big and too many coins
        orders = await consumer.create_new_orders(symbol, -0.6,  EvaluatorStates.LONG.value)
        assert len(orders) == 3
        adapted_order = orders[0]
        identical_orders = orders[1:]

        assert isinstance(adapted_order, BuyLimitOrder)
        assert adapted_order.currency == "BTC"
        assert adapted_order.symbol == "BTC/USDT"
        assert adapted_order.origin_price == 0.00695312
        assert adapted_order.created_last_price == 0.007009194999999998
        assert adapted_order.order_type == TraderOrderType.BUY_LIMIT
        assert adapted_order.side == TradeOrderSide.BUY
        assert adapted_order.status == OrderStatus.OPEN
        assert adapted_order.exchange_manager == exchange_manager
        assert adapted_order.trader == trader
        assert adapted_order.fee is None
        assert adapted_order.filled_price == 0
        assert adapted_order.origin_quantity == 396851564266.65326
        assert adapted_order.filled_quantity == adapted_order.origin_quantity
        assert adapted_order.simulated is True
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
            assert order.exchange_manager == adapted_order.exchange_manager
            assert order.trader == adapted_order.trader
            assert order.fee == adapted_order.fee
            assert order.filled_price == adapted_order.filled_price
            assert order.origin_quantity == 1000000000000.0
            assert order.origin_quantity > adapted_order.origin_quantity
            assert order.filled_quantity > adapted_order.filled_quantity
            assert order.simulated == adapted_order.simulated
            assert order.linked_to == adapted_order.linked_to

            check_order_limits(order, market_status)

            # assert len(order.linked_orders) == 1 # check linked orders when it will be developed
    finally:
        await _stop(exchange_manager)


async def test_valid_create_new_orders_without_stop_order():
    try:
        exchange_manager, trader, symbol, consumer, last_btc_price = await _get_tools()

        # change reference market to get more orders
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio_profitability.reference_market = "USDT"
        exchange_manager.exchange_personal_data.portfolio_manager.reference_market = "USDT"
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio_profitability.currencies_last_prices[
            symbol] = last_btc_price
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio_profitability.portfolio_current_value = \
            last_btc_price * 10 + 1000
        market_status = exchange_manager.exchange.get_market_status(symbol, with_fixer=False)

        # force no stop orders
        consumer.USE_STOP_ORDERS = False

        # valid sell limit order (price adapted)
        orders = await consumer.create_new_orders(symbol, 0.65, EvaluatorStates.SHORT.value)
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
        assert order.exchange_manager == exchange_manager
        assert order.trader == trader
        assert order.fee is None
        assert order.filled_price == 0
        assert order.origin_quantity == 7.6
        assert order.filled_quantity == order.origin_quantity
        assert order.simulated is True
        assert order.linked_to is None

        check_order_limits(order, market_status)

        # assert no stop orders
        assert len(order.linked_orders) == 0
    finally:
        await _stop(exchange_manager)


def _get_evaluations_gradient(step):
    nb_steps = 1/step
    return [i/nb_steps for i in range(int(-nb_steps), int(nb_steps+1), 1)]


def _get_states_gradient_with_invald_states():
    states = [state.value for state in EvaluatorStates]
    states += [None, 1, {'toto': 1}, math.nan]
    return states


def _get_irrationnal_numbers():
    irrationals = [math.pi, math.sqrt(2), math.sqrt(3), math.sqrt(5), math.sqrt(7), math.sqrt(11), math.sqrt(73), 10/3]
    return [1/i for i in irrationals]


def _reset_portfolio(exchange_manager):
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio = {
        "BTC": {
            PORTFOLIO_TOTAL: 10,
            PORTFOLIO_AVAILABLE: 10
        },
        "USDT": {
            PORTFOLIO_TOTAL: 2000,
            PORTFOLIO_AVAILABLE: 2000
        }
    }


async def test_create_orders_using_a_lot_of_different_inputs_with_portfolio_reset():
    exchange_manager, trader, symbol, consumer, last_btc_price = await _get_tools()
    gradient_step = 0.005
    nb_orders = 1
    initial_portfolio = copy.deepcopy(exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio)
    portfolio_wrapper = exchange_manager.exchange_personal_data.portfolio_manager.portfolio
    market_status = exchange_manager.exchange.get_market_status(symbol, with_fixer=False)
    min_trigger_market = "ADA/BNB"
    force_set_mark_price(exchange_manager, min_trigger_market, 0.001)

    for state in _get_states_gradient_with_invald_states():
        for evaluation in _get_evaluations_gradient(gradient_step):
            _reset_portfolio(exchange_manager)
            # orders are possible
            orders = await consumer.create_new_orders(symbol, evaluation, state)
            check_orders(orders, evaluation, state, nb_orders, market_status)
            check_portfolio(portfolio_wrapper.portfolio, initial_portfolio, orders)
            # orders are impossible
            orders = await consumer.create_new_orders(min_trigger_market, evaluation, state)
            check_orders(orders, evaluation, state, 0, market_status)
            check_portfolio(portfolio_wrapper.portfolio, initial_portfolio, orders)

        for evaluation in _get_irrationnal_numbers():
            # orders are possible
            _reset_portfolio(exchange_manager)
            orders = await consumer.create_new_orders(symbol, evaluation, state)
            check_orders(orders, evaluation, state, nb_orders, market_status)
            check_portfolio(portfolio_wrapper.portfolio, initial_portfolio, orders)
            # orders are impossible
            orders = await consumer.create_new_orders(min_trigger_market, evaluation, state)
            check_orders(orders, evaluation, state, 0, market_status)
            check_portfolio(portfolio_wrapper.portfolio, initial_portfolio, orders)

        _reset_portfolio(exchange_manager)
        # orders are possible
        orders = await consumer.create_new_orders(symbol, math.nan, state)
        check_orders(orders, math.nan, state, nb_orders, market_status)
        check_portfolio(portfolio_wrapper.portfolio, initial_portfolio, orders)
        # orders are impossible
        orders = await consumer.create_new_orders(min_trigger_market, math.nan, state)
        check_orders(orders, math.nan, state, 0, market_status)
        check_portfolio(portfolio_wrapper.portfolio, initial_portfolio, orders)
    await _stop(exchange_manager)


async def test_create_order_using_a_lot_of_different_inputs_without_portfolio_reset():
    exchange_manager, trader, symbol, consumer, last_btc_price = await _get_tools()

    gradient_step = 0.001
    nb_orders = "unknown"
    initial_portfolio = copy.deepcopy(exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio)
    portfolio_wrapper = exchange_manager.exchange_personal_data.portfolio_manager.portfolio
    market_status = exchange_manager.exchange.get_market_status(symbol, with_fixer=False)
    min_trigger_market = "ADA/BNB"
    force_set_mark_price(exchange_manager, min_trigger_market, 0.001)

    _reset_portfolio(exchange_manager)
    for state in _get_states_gradient_with_invald_states():
        for evaluation in _get_evaluations_gradient(gradient_step):
            # orders are possible
            orders = await consumer.create_new_orders(symbol, evaluation, state)
            check_orders(orders, evaluation, state, nb_orders, market_status)
            check_portfolio(portfolio_wrapper.portfolio, initial_portfolio, orders, True)
            await fill_orders(orders, trader)
            # orders are impossible
            orders = await consumer.create_new_orders(min_trigger_market, evaluation, state)
            check_orders(orders, evaluation, state, 0, market_status)
            check_portfolio(portfolio_wrapper.portfolio, initial_portfolio, orders, True)
            await fill_orders(orders, trader)

    _reset_portfolio(exchange_manager)
    for state in _get_states_gradient_with_invald_states():
        for evaluation in _get_irrationnal_numbers():
            # orders are possible
            orders = await consumer.create_new_orders(symbol, evaluation, state)
            check_orders(orders, evaluation, state, nb_orders, market_status)
            check_portfolio(portfolio_wrapper.portfolio, initial_portfolio, orders, True)
            if any(order
                   for order in orders
                   if order.order_type not in (TraderOrderType.SELL_MARKET, TraderOrderType.BUY_MARKET)):
                # no need to fill market orders
                await fill_orders(orders, trader)
            # orders are impossible
            orders = await consumer.create_new_orders(min_trigger_market, evaluation, state)
            check_orders(orders, evaluation, state, 0, market_status)
            check_portfolio(portfolio_wrapper.portfolio, initial_portfolio, orders, True)
            if any(order
                   for order in orders
                   if order.order_type not in (TraderOrderType.SELL_MARKET, TraderOrderType.BUY_MARKET)):
                # no need to fill market orders
                await fill_orders(orders, trader)

    _reset_portfolio(exchange_manager)
    for state in _get_states_gradient_with_invald_states():
        # orders are possible
        orders = await consumer.create_new_orders(symbol, math.nan, state)
        check_orders(orders, math.nan, state, nb_orders, market_status)
        check_portfolio(portfolio_wrapper.portfolio, initial_portfolio, orders, True)
        await fill_orders(orders, trader)
        # orders are impossible
        orders = await consumer.create_new_orders(min_trigger_market, math.nan, state)
        check_orders(orders, math.nan, state, 0, market_status)
        check_portfolio(portfolio_wrapper.portfolio, initial_portfolio, orders, True)
        await fill_orders(orders, trader)
    await _stop(exchange_manager)


async def test_create_multiple_buy_orders_after_fill():
    exchange_manager, trader, symbol, consumer, last_btc_price = await _get_tools()

    # with BTC/USDT
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio_profitability.currencies_last_prices[symbol] = \
        last_btc_price
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio_profitability.portfolio_current_value = \
        10 + 1000/last_btc_price
    # force many traded asset not to create all in orders
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio_profitability.origin_crypto_currencies_values \
        = {
            "a": 0,
            "b": 0,
            "c": 0,
            "d": 0,
            "e": 0
        }
    await ensure_smaller_orders(consumer, symbol, trader)

    # with another symbol with 0 quantity when start
    force_set_mark_price(exchange_manager, "ADA/BTC", 0.0000001)
    await ensure_smaller_orders(consumer, "ADA/BTC", trader)
    await _stop(exchange_manager)


async def ensure_smaller_orders(consumer, symbol, trader):
    state = EvaluatorStates.VERY_LONG.value

    # first call: biggest order
    orders1 = (await consumer.create_new_orders(symbol, -1, state))
    if any(order
           for order in orders1
           if order.order_type not in (TraderOrderType.SELL_MARKET, TraderOrderType.BUY_MARKET)):
        # no need to fill market orders
        await fill_orders(orders1, trader)

    state = EvaluatorStates.LONG.value
    # second call: smaller order (same with very long as with long)
    orders2 = (await consumer.create_new_orders(symbol, -0.6, state))
    assert orders1[0].origin_quantity > orders2[0].origin_quantity
    if any(order
           for order in orders2
           if order.order_type not in (TraderOrderType.SELL_MARKET, TraderOrderType.BUY_MARKET)):
        # no need to fill market orders
        await fill_orders(orders2, trader)

    # third call: even smaller order
    orders3 = (await consumer.create_new_orders(symbol, -0.6, state))
    assert orders2[0].origin_quantity > orders3[0].origin_quantity
    if any(order
           for order in orders3
           if order.order_type not in (TraderOrderType.SELL_MARKET, TraderOrderType.BUY_MARKET)):
        # no need to fill market orders
        await fill_orders(orders3, trader)

    # third call: even-even smaller order
    orders4 = (await consumer.create_new_orders(symbol, -0.6, state))
    assert orders3[0].origin_quantity > orders4[0].origin_quantity
    if any(order
           for order in orders4
           if order.order_type not in (TraderOrderType.SELL_MARKET, TraderOrderType.BUY_MARKET)):
        # no need to fill market orders
        await fill_orders(orders4, trader)
