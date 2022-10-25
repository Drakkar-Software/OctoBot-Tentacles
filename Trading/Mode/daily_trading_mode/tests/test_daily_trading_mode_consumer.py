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
import decimal
import math
import pytest
import os.path
import copy
import pytest_asyncio

import async_channel.util as channel_util
import octobot_backtesting.api as backtesting_api
import octobot_commons.asyncio_tools as asyncio_tools
import octobot_commons.constants as commons_constants
import octobot_commons.tests.test_config as test_config
import octobot_trading.constants as trading_constants
import octobot_trading.api as trading_api
import octobot_trading.exchange_channel as exchanges_channel
import octobot_trading.enums as trading_enums
import octobot_trading.errors as trading_errors
import octobot_trading.exchanges as exchanges
import octobot_trading.personal_data as trading_personal_data
import tentacles.Trading.Mode as Mode
import tests.unit_tests.trading_modes_tests.trading_mode_test_toolkit as trading_mode_test_toolkit
import tests.test_utils.config as test_utils_config
import tests.test_utils.test_exchanges as test_exchanges
import octobot_tentacles_manager.api as tentacles_manager_api


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def tools():
    tentacles_manager_api.reload_tentacle_info()
    exchange_manager = None
    try:
        symbol = "BTC/USDT"
        config = test_config.load_test_config()
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO][
            "SUB"] = 0.000000000000000000005
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO][
            "BNB"] = 0.000000000000000000005
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO]["USDT"] = 2000
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

        mode = Mode.DailyTradingMode(config, exchange_manager)
        await mode.initialize()
        # add mode to exchange manager so that it can be stopped and freed from memory
        exchange_manager.trading_modes.append(mode)
        consumer = mode.get_trading_mode_consumers()[0]
        consumer.MAX_CURRENCY_RATIO = 1

        # set BTC/USDT price at 7009.194999999998 USDT
        last_btc_price = 7009.194999999998
        trading_api.force_set_mark_price(exchange_manager, symbol, last_btc_price)

        yield exchange_manager, trader, symbol, consumer, decimal.Decimal(str(last_btc_price))
    finally:
        if exchange_manager:
            try:
                await _stop(exchange_manager)
            except Exception as err:
                print(f"error when stopping exchange manager: {err}")


async def _stop(exchange_manager):
    for importer in backtesting_api.get_importers(exchange_manager.exchange.backtesting):
        await backtesting_api.stop_importer(importer)
    await exchange_manager.exchange.backtesting.stop()
    await exchange_manager.stop()
    # let updaters gracefully shutdown
    await asyncio_tools.wait_asyncio_next_cycle()


async def test_valid_create_new_orders_no_ref_market_as_quote(tools):
    exchange_manager, trader, symbol, consumer, last_btc_price = tools

    # change reference market to USDT
    exchange_manager.exchange_personal_data.portfolio_manager.reference_market = "USDT"
    exchange_manager.exchange_personal_data.portfolio_manager.reference_market = "USDT"
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder.last_prices_by_trading_pair[
        symbol] = last_btc_price
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder.portfolio_current_value = \
        decimal.Decimal(str(last_btc_price * 10 + 1000))

    market_status = exchange_manager.exchange.get_market_status(symbol, with_fixer=False)

    # portfolio: "BTC": 10 "USD": 1000
    # order from neutral state
    assert await consumer.create_new_orders(symbol, decimal.Decimal(str(-1)), trading_enums.EvaluatorStates.NEUTRAL.value) == []
    assert await consumer.create_new_orders(symbol, decimal.Decimal(str(0.5)), trading_enums.EvaluatorStates.NEUTRAL.value) == []
    assert await consumer.create_new_orders(symbol, trading_constants.ZERO, trading_enums.EvaluatorStates.NEUTRAL.value) == []
    assert await consumer.create_new_orders(symbol, decimal.Decimal(str(-0.5)), trading_enums.EvaluatorStates.NEUTRAL.value) == []
    assert await consumer.create_new_orders(symbol, decimal.Decimal(str(-1)), trading_enums.EvaluatorStates.NEUTRAL.value) == []

    # valid sell limit order (price adapted)
    orders = await consumer.create_new_orders(symbol, decimal.Decimal(str(0.65)), trading_enums.EvaluatorStates.SHORT.value)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, trading_personal_data.SellLimitOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == decimal.Decimal(str(7062.64011187))
    assert order.created_last_price == last_btc_price
    assert order.order_type == trading_enums.TraderOrderType.SELL_LIMIT
    assert order.side == trading_enums.TradeOrderSide.SELL
    assert order.status == trading_enums.OrderStatus.OPEN
    assert order.exchange_manager == exchange_manager
    assert order.trader == trader
    assert order.fee is None
    assert order.filled_price == trading_constants.ZERO
    assert order.origin_quantity == decimal.Decimal(str(7.6))
    assert order.filled_quantity == order.origin_quantity
    assert order.simulated is True
    assert isinstance(order.order_group, trading_personal_data.OneCancelsTheOtherOrderGroup)

    trading_mode_test_toolkit.check_order_limits(order, market_status)

    trading_mode_test_toolkit.check_oco_order_group(order,
                                                    trading_enums.TraderOrderType.STOP_LOSS, decimal.Decimal(str(6658.73524999)),
                                                    market_status)

    # valid buy limit order with (price and quantity adapted)
    orders = await consumer.create_new_orders(symbol, decimal.Decimal(str(-0.65)), trading_enums.EvaluatorStates.LONG.value)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, trading_personal_data.BuyLimitOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == decimal.Decimal(str(6955.74988812))
    assert order.created_last_price == last_btc_price
    assert order.order_type == trading_enums.TraderOrderType.BUY_LIMIT
    assert order.side == trading_enums.TradeOrderSide.BUY
    assert order.status == trading_enums.OrderStatus.OPEN
    assert order.exchange_manager == exchange_manager
    assert order.trader == trader
    assert order.fee is None
    assert order.filled_price == trading_constants.ZERO
    assert order.origin_quantity == decimal.Decimal(str(0.12554936))
    assert order.filled_quantity == order.origin_quantity
    assert order.simulated is True
    assert order.order_group is None

    trading_mode_test_toolkit.check_order_limits(order, market_status)

    truncated_last_price = trading_personal_data.decimal_trunc_with_n_decimal_digits(last_btc_price, 8)

    # valid buy market order with (price and quantity adapted)
    orders = await consumer.create_new_orders(symbol, decimal.Decimal(str(-1)), trading_enums.EvaluatorStates.VERY_LONG.value)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, trading_personal_data.BuyMarketOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == truncated_last_price
    assert order.created_last_price == truncated_last_price
    assert order.order_type == trading_enums.TraderOrderType.BUY_MARKET
    assert order.side == trading_enums.TradeOrderSide.BUY
    assert order.status == trading_enums.OrderStatus.FILLED
    # order has been cleared
    assert order.exchange_manager is None
    assert order.trader is None
    assert order.fee
    assert order.filled_price == decimal.Decimal(str(7009.19499999))
    assert order.origin_quantity == decimal.Decimal(str(0.11573814))
    assert order.filled_quantity == order.origin_quantity
    assert order.simulated is True
    assert order.order_group is None

    trading_mode_test_toolkit.check_order_limits(order, market_status)

    # valid buy market order with (price and quantity adapted)
    orders = await consumer.create_new_orders(symbol, trading_constants.ONE,
                                              trading_enums.EvaluatorStates.VERY_SHORT.value)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, trading_personal_data.SellMarketOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == truncated_last_price
    assert order.created_last_price == truncated_last_price
    assert order.order_type == trading_enums.TraderOrderType.SELL_MARKET
    assert order.side == trading_enums.TradeOrderSide.SELL
    assert order.status == trading_enums.OrderStatus.FILLED
    assert order.exchange_manager is None
    assert order.trader is None
    assert order.fee
    assert order.filled_price == decimal.Decimal(str(7009.19499999))
    assert order.origin_quantity == decimal.Decimal(str(2.5156224))
    assert order.filled_quantity == order.origin_quantity
    assert order.simulated is True
    assert order.order_group is None

    trading_mode_test_toolkit.check_order_limits(order, market_status)


async def test_valid_create_new_orders_ref_market_as_quote(tools):
    exchange_manager, trader, symbol, consumer, last_btc_price = tools

    exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder.last_prices_by_trading_pair[
        symbol] = last_btc_price
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder.portfolio_current_value = \
        decimal.Decimal(str(10 + 1000 / last_btc_price))

    # portfolio: "BTC": 10 "USD": 1000
    # order from neutral state
    assert await consumer.create_new_orders(symbol, decimal.Decimal(str(-1)), trading_enums.EvaluatorStates.NEUTRAL.value) == []
    assert await consumer.create_new_orders(symbol, decimal.Decimal(str(0.5)), trading_enums.EvaluatorStates.NEUTRAL.value) == []
    assert await consumer.create_new_orders(symbol, decimal.Decimal(str(0)), trading_enums.EvaluatorStates.NEUTRAL.value) == []
    assert await consumer.create_new_orders(symbol, decimal.Decimal(str(-0.5)), trading_enums.EvaluatorStates.NEUTRAL.value) == []
    assert await consumer.create_new_orders(symbol, decimal.Decimal(str(-1)), trading_enums.EvaluatorStates.NEUTRAL.value) == []

    # valid sell limit order (price adapted)
    orders = await consumer.create_new_orders(symbol, decimal.Decimal(str(0.65)), trading_enums.EvaluatorStates.SHORT.value)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, trading_personal_data.SellLimitOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == decimal.Decimal(str(7062.64011187))
    assert order.created_last_price == last_btc_price
    assert order.order_type == trading_enums.TraderOrderType.SELL_LIMIT
    assert order.side == trading_enums.TradeOrderSide.SELL
    assert order.status == trading_enums.OrderStatus.OPEN
    assert order.exchange_manager == exchange_manager
    assert order.trader == trader
    assert order.fee is None
    assert order.filled_price == trading_constants.ZERO
    assert order.origin_quantity == decimal.Decimal(str(4.4))
    assert order.filled_quantity == order.origin_quantity
    assert order.simulated is True
    assert isinstance(order.order_group, trading_personal_data.OneCancelsTheOtherOrderGroup)

    market_status = exchange_manager.exchange.get_market_status(symbol, with_fixer=False)
    trading_mode_test_toolkit.check_order_limits(order, market_status)

    trading_mode_test_toolkit.check_oco_order_group(order,
                                                    trading_enums.TraderOrderType.STOP_LOSS, decimal.Decimal(str(6658.73524999)),
                                                    market_status)

    # valid buy limit order with (price and quantity adapted)
    orders = await consumer.create_new_orders(symbol, decimal.Decimal(str(-0.65)), trading_enums.EvaluatorStates.LONG.value)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, trading_personal_data.BuyLimitOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == decimal.Decimal(str(6955.74988812))
    assert order.created_last_price == last_btc_price
    assert order.order_type == trading_enums.TraderOrderType.BUY_LIMIT
    assert order.side == trading_enums.TradeOrderSide.BUY
    assert order.status == trading_enums.OrderStatus.OPEN
    assert order.exchange_manager == exchange_manager
    assert order.trader == trader
    assert order.fee is None
    assert order.filled_price == trading_constants.ZERO
    assert order.origin_quantity == decimal.Decimal(str(0.21685799))
    assert order.filled_quantity == order.origin_quantity
    assert order.simulated is True
    assert order.order_group is None

    trading_mode_test_toolkit.check_order_limits(order, market_status)

    truncated_last_price = trading_personal_data.decimal_trunc_with_n_decimal_digits(last_btc_price, 8)

    # valid buy market order with (price and quantity adapted)
    orders = await consumer.create_new_orders(symbol, decimal.Decimal(str(-1)), trading_enums.EvaluatorStates.VERY_LONG.value)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, trading_personal_data.BuyMarketOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == truncated_last_price
    assert order.created_last_price == truncated_last_price
    assert order.order_type == trading_enums.TraderOrderType.BUY_MARKET
    assert order.side == trading_enums.TradeOrderSide.BUY
    assert order.status == trading_enums.OrderStatus.FILLED
    assert order.filled_price == decimal.Decimal(str(7009.19499999))
    assert order.origin_quantity == decimal.Decimal(str(0.07013502))
    assert order.filled_quantity == order.origin_quantity
    assert order.simulated is True
    assert order.order_group is None

    trading_mode_test_toolkit.check_order_limits(order, market_status)

    # valid buy market order with (price and quantity adapted)
    orders = await consumer.create_new_orders(symbol, trading_constants.ONE, trading_enums.EvaluatorStates.VERY_SHORT.value)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, trading_personal_data.SellMarketOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == truncated_last_price
    assert order.created_last_price == truncated_last_price
    assert order.order_type == trading_enums.TraderOrderType.SELL_MARKET
    assert order.side == trading_enums.TradeOrderSide.SELL
    assert order.status == trading_enums.OrderStatus.FILLED
    assert order.fee
    assert order.filled_price == decimal.Decimal(str(7009.19499999))
    assert order.origin_quantity == decimal.Decimal(str(4.08244671))
    assert order.filled_quantity == order.origin_quantity
    assert order.simulated is True
    assert order.order_group is None

    trading_mode_test_toolkit.check_order_limits(order, market_status)


async def test_invalid_create_new_orders(tools):
    exchange_manager, trader, symbol, consumer, last_btc_price = tools

    # portfolio: "BTC": 10 "USD": 1000
    min_trigger_market = "ADA/BNB"

    # invalid sell order with not trade data
    import octobot_trading.constants
    trading_constants.ORDER_DATA_FETCHING_TIMEOUT = 0.1
    assert await consumer.create_new_orders(min_trigger_market, decimal.Decimal(str(0.6)), trading_enums.EvaluatorStates.SHORT.value,
                                            timeout=1) == []

    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("BTC").available = decimal.Decimal(str(0.000000000000000000005))
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("BTC").total = decimal.Decimal(str(2000))

    # invalid sell order with not enough currency to sell
    with pytest.raises(trading_errors.MissingMinimalExchangeTradeVolume):
        await consumer.create_new_orders(symbol, decimal.Decimal(str(0.6)), trading_enums.EvaluatorStates.SHORT.value)

    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("USDT").available = decimal.Decimal(str(0.000000000000000000005))
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("USDT").total = decimal.Decimal(str(2000))

    # invalid buy order with not enough currency to buy
    with pytest.raises(trading_errors.MissingMinimalExchangeTradeVolume):
        orders = await consumer.create_new_orders(symbol, decimal.Decimal(str(-0.6)), trading_enums.EvaluatorStates.LONG.value)


async def test_create_new_orders_with_dusts_included(tools):
    exchange_manager, trader, symbol, consumer, last_btc_price = tools

    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("BTC").available = decimal.Decimal(str(0.000015))
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("BTC").total = decimal.Decimal(str(0.000015))

    # trigger order that should not sell everything but does sell everything because remaining amount
    # is not sellable
    orders = await consumer.create_new_orders(symbol, decimal.Decimal(str(0.6)), trading_enums.EvaluatorStates.VERY_SHORT.value)
    assert len(orders) == 1

    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("BTC").available = trading_constants.ZERO
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("BTC").total = trading_constants.ZERO

    test_currency = "NEO"
    test_pair = f"{test_currency}/BTC"
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio(test_currency).available = decimal.Decimal(str(0.44))
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio(test_currency).total = decimal.Decimal(str(0.44))

    trading_api.force_set_mark_price(exchange_manager, test_pair, 0.005318)
    # trigger order that should not sell everything but does sell everything because remaining amount
    # is not sellable
    orders = await consumer.create_new_orders(test_pair, decimal.Decimal(str(0.75445456165478)),
                                              trading_enums.EvaluatorStates.SHORT.value)
    assert len(orders) == 1
    assert exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio(test_currency).available == trading_constants.ZERO
    assert exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio(test_currency).total == orders[0].origin_quantity


async def test_split_create_new_orders(tools):
    exchange_manager, trader, symbol, consumer, last_btc_price = tools

    # change reference market to get more orders
    exchange_manager.exchange_personal_data.portfolio_manager.reference_market = "USDT"
    exchange_manager.exchange_personal_data.portfolio_manager.reference_market = "USDT"
    market_status = exchange_manager.exchange.get_market_status(symbol, with_fixer=False)
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("BTC").available = decimal.Decimal(str(2000000001))
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("BTC").total = decimal.Decimal(str(2000000001))

    exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder.last_prices_by_trading_pair[
        symbol] = last_btc_price
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder.portfolio_current_value = \
        decimal.Decimal(str(last_btc_price * 2000000001 + 1000))

    # split orders because order too big and coin price too high
    orders = await consumer.create_new_orders(symbol, decimal.Decimal(str(0.6)), trading_enums.EvaluatorStates.SHORT.value)
    assert len(orders) == 11
    adapted_order = orders[0]
    identical_orders = orders[1:]

    assert isinstance(adapted_order, trading_personal_data.SellLimitOrder)
    assert adapted_order.currency == "BTC"
    assert adapted_order.symbol == "BTC/USDT"
    assert adapted_order.origin_price == decimal.Decimal(str(7065.26855999))
    assert adapted_order.created_last_price == last_btc_price
    assert adapted_order.order_type == trading_enums.TraderOrderType.SELL_LIMIT
    assert adapted_order.side == trading_enums.TradeOrderSide.SELL
    assert adapted_order.status == trading_enums.OrderStatus.OPEN
    assert adapted_order.exchange_manager == exchange_manager
    assert adapted_order.trader == trader
    assert adapted_order.fee is None
    assert adapted_order.filled_price == trading_constants.ZERO
    assert adapted_order.origin_quantity == decimal.Decimal(str(64625635.97358073))
    assert adapted_order.filled_quantity == adapted_order.origin_quantity
    assert adapted_order.simulated is True
    assert isinstance(adapted_order.order_group, trading_personal_data.OneCancelsTheOtherOrderGroup)

    trading_mode_test_toolkit.check_order_limits(adapted_order, market_status)

    trading_mode_test_toolkit.check_oco_order_group(adapted_order,
                                                    trading_enums.TraderOrderType.STOP_LOSS, decimal.Decimal(str(6658.73524999)),
                                                    market_status)

    for order in identical_orders:
        assert isinstance(order, trading_personal_data.SellLimitOrder)
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
        assert order.origin_quantity == decimal.Decimal(str(141537436.47664192))
        assert order.origin_quantity > adapted_order.origin_quantity
        assert order.filled_quantity > adapted_order.filled_quantity
        assert order.simulated == adapted_order.simulated
        assert isinstance(order.order_group, trading_personal_data.OneCancelsTheOtherOrderGroup)

        trading_mode_test_toolkit.check_order_limits(order, market_status)
        trading_mode_test_toolkit.check_oco_order_group(order,
                                                        trading_enums.TraderOrderType.STOP_LOSS, decimal.Decimal(str(6658.73524999)),
                                                        market_status)

    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("USDT").available = decimal.Decimal(str(40000000000))
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("USDT").total = decimal.Decimal(str(40000000000))

    # set btc last price to 6998.55407999 * 0.000001 = 0.00699855408
    trading_api.force_set_mark_price(exchange_manager, symbol, float(last_btc_price * decimal.Decimal(str(0.000001))))
    # split orders because order too big and too many coins
    orders = await consumer.create_new_orders(symbol, decimal.Decimal(str(-0.6)), trading_enums.EvaluatorStates.LONG.value)
    assert len(orders) == 3
    adapted_order = orders[0]
    identical_orders = orders[1:]

    assert isinstance(adapted_order, trading_personal_data.BuyLimitOrder)
    assert adapted_order.currency == "BTC"
    assert adapted_order.symbol == "BTC/USDT"
    assert adapted_order.origin_price == decimal.Decimal(str(0.00695312))
    assert adapted_order.created_last_price == decimal.Decimal(str(0.007009194999999998))
    assert adapted_order.order_type == trading_enums.TraderOrderType.BUY_LIMIT
    assert adapted_order.side == trading_enums.TradeOrderSide.BUY
    assert adapted_order.status == trading_enums.OrderStatus.OPEN
    assert adapted_order.exchange_manager == exchange_manager
    assert adapted_order.trader == trader
    assert adapted_order.fee is None
    assert adapted_order.filled_price == trading_constants.ZERO
    assert adapted_order.origin_quantity == decimal.Decimal("396851564266.65327383")
    assert adapted_order.filled_quantity == adapted_order.origin_quantity
    assert adapted_order.simulated is True

    trading_mode_test_toolkit.check_order_limits(adapted_order, market_status)

    for order in identical_orders:
        assert isinstance(order, trading_personal_data.BuyLimitOrder)
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
        assert order.origin_quantity == decimal.Decimal(str(1000000000000.0))
        assert order.origin_quantity > adapted_order.origin_quantity
        assert order.filled_quantity > adapted_order.filled_quantity
        assert order.simulated == adapted_order.simulated

        trading_mode_test_toolkit.check_order_limits(order, market_status)


async def test_valid_create_new_orders_without_stop_order(tools):
    exchange_manager, trader, symbol, consumer, last_btc_price = tools

    # change reference market to get more orders
    exchange_manager.exchange_personal_data.portfolio_manager.reference_market = "USDT"
    exchange_manager.exchange_personal_data.portfolio_manager.reference_market = "USDT"
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder.last_prices_by_trading_pair[
        symbol] = last_btc_price
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder.portfolio_current_value = \
        decimal.Decimal(str(last_btc_price * 10 + 1000))
    market_status = exchange_manager.exchange.get_market_status(symbol, with_fixer=False)

    # force no stop orders
    consumer.USE_STOP_ORDERS = False

    # valid sell limit order (price adapted)
    orders = await consumer.create_new_orders(symbol, decimal.Decimal(str(0.65)), trading_enums.EvaluatorStates.SHORT.value)
    assert len(orders) == 1
    order = orders[0]
    assert isinstance(order, trading_personal_data.SellLimitOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == decimal.Decimal(str(7062.64011187))
    assert order.created_last_price == last_btc_price
    assert order.order_type == trading_enums.TraderOrderType.SELL_LIMIT
    assert order.side == trading_enums.TradeOrderSide.SELL
    assert order.status == trading_enums.OrderStatus.OPEN
    assert order.exchange_manager == exchange_manager
    assert order.trader == trader
    assert order.fee is None
    assert order.filled_price == trading_constants.ZERO
    assert order.origin_quantity == decimal.Decimal(str(7.6))
    assert order.filled_quantity == order.origin_quantity
    assert order.simulated is True
    assert order.order_group is None

    trading_mode_test_toolkit.check_order_limits(order, market_status)


def _get_evaluations_gradient(step):
    nb_steps = 1 / step
    return [decimal.Decimal(str(i / nb_steps)) for i in range(int(-nb_steps), int(nb_steps + 1), 1)]


def _get_states_gradient_with_invald_states():
    states = [state.value for state in trading_enums.EvaluatorStates]
    states += [None, 1, {'toto': 1}, math.nan]
    return states


def _get_irrationnal_numbers():
    irrationals = [math.pi, math.sqrt(2), math.sqrt(3), math.sqrt(5), math.sqrt(7), math.sqrt(11), math.sqrt(73),
                   10 / 3]
    return [decimal.Decimal(str(1 / i)) for i in irrationals]


def _reset_portfolio(exchange_manager):
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("BTC").available = decimal.Decimal(str(10))
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("BTC").total = decimal.Decimal(str(10))
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("USDT").available = decimal.Decimal(str(2000))
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio("USDT").total = decimal.Decimal(str(2000))


async def test_create_orders_using_a_lot_of_different_inputs_with_portfolio_reset(tools):
    exchange_manager, trader, symbol, consumer, last_btc_price = tools
    gradient_step = 0.005
    nb_orders = 1
    initial_portfolio = copy.copy(exchange_manager.exchange_personal_data.portfolio_manager.portfolio)
    portfolio_wrapper = exchange_manager.exchange_personal_data.portfolio_manager.portfolio
    market_status = exchange_manager.exchange.get_market_status(symbol, with_fixer=False)
    min_trigger_market = "ADA/BNB"
    trading_api.force_set_mark_price(exchange_manager, min_trigger_market, 0.001)

    for state in _get_states_gradient_with_invald_states():
        for evaluation in _get_evaluations_gradient(gradient_step):
            _reset_portfolio(exchange_manager)
            # orders are possible
            try:
                orders = await consumer.create_new_orders(symbol, evaluation, state)
                trading_mode_test_toolkit.check_orders(orders, evaluation, state, nb_orders, market_status)
                trading_mode_test_toolkit.check_portfolio(portfolio_wrapper, initial_portfolio, orders)
            except trading_errors.MissingMinimalExchangeTradeVolume:
                pass
            # orders are impossible
            try:
                orders = []
                orders = await consumer.create_new_orders(min_trigger_market, evaluation, state)
                trading_mode_test_toolkit.check_orders(orders, evaluation, state, 0, market_status)
                trading_mode_test_toolkit.check_portfolio(portfolio_wrapper, initial_portfolio, orders)
            except trading_errors.MissingMinimalExchangeTradeVolume:
                pass

        for evaluation in _get_irrationnal_numbers():
            # orders are possible
            _reset_portfolio(exchange_manager)
            try:
                orders = await consumer.create_new_orders(symbol, evaluation, state)
                trading_mode_test_toolkit.check_orders(orders, evaluation, state, nb_orders, market_status)
                trading_mode_test_toolkit.check_portfolio(portfolio_wrapper, initial_portfolio, orders)
            except trading_errors.MissingMinimalExchangeTradeVolume:
                pass
            # orders are impossible
            try:
                orders = []
                orders = await consumer.create_new_orders(min_trigger_market, evaluation, state)
                trading_mode_test_toolkit.check_orders(orders, evaluation, state, 0, market_status)
                trading_mode_test_toolkit.check_portfolio(portfolio_wrapper, initial_portfolio, orders)
            except trading_errors.MissingMinimalExchangeTradeVolume:
                pass

        _reset_portfolio(exchange_manager)
        # orders are possible
        try:
            orders = await consumer.create_new_orders(symbol, decimal.Decimal("nan"), state)
            trading_mode_test_toolkit.check_orders(orders, decimal.Decimal("nan"), state, nb_orders, market_status)
            trading_mode_test_toolkit.check_portfolio(portfolio_wrapper, initial_portfolio, orders)
        except trading_errors.MissingMinimalExchangeTradeVolume:
            pass
        # orders are impossible
        try:
            orders = []
            orders = await consumer.create_new_orders(min_trigger_market, decimal.Decimal("nan"), state)
            trading_mode_test_toolkit.check_orders(orders, decimal.Decimal("nan"), state, 0, market_status)
            trading_mode_test_toolkit.check_portfolio(portfolio_wrapper, initial_portfolio, orders)
        except trading_errors.MissingMinimalExchangeTradeVolume:
            pass
        try:
            orders = []
            # float evaluation
            orders = await consumer.create_new_orders(min_trigger_market, math.nan, state)
            trading_mode_test_toolkit.check_orders(orders, math.nan, state, 0, market_status)
            trading_mode_test_toolkit.check_portfolio(portfolio_wrapper, initial_portfolio, orders)
        except trading_errors.MissingMinimalExchangeTradeVolume:
            pass


async def test_create_order_using_a_lot_of_different_inputs_without_portfolio_reset(tools):
    exchange_manager, trader, symbol, consumer, last_btc_price = tools

    gradient_step = 0.001
    nb_orders = "unknown"
    initial_portfolio = copy.copy(exchange_manager.exchange_personal_data.portfolio_manager.portfolio)
    portfolio_wrapper = exchange_manager.exchange_personal_data.portfolio_manager.portfolio
    market_status = exchange_manager.exchange.get_market_status(symbol, with_fixer=False)
    min_trigger_market = "ADA/BNB"
    trading_api.force_set_mark_price(exchange_manager, min_trigger_market, 0.001)

    _reset_portfolio(exchange_manager)
    for state in _get_states_gradient_with_invald_states():
        for evaluation in _get_evaluations_gradient(gradient_step):
            # orders are possible
            try:
                orders = await consumer.create_new_orders(symbol, evaluation, state)
                trading_mode_test_toolkit.check_orders(orders, evaluation, state, nb_orders, market_status)
                trading_mode_test_toolkit.check_portfolio(portfolio_wrapper, initial_portfolio, orders, True)
                await trading_mode_test_toolkit.fill_orders(orders, trader)
            except trading_errors.MissingMinimalExchangeTradeVolume:
                pass
            # orders are impossible
            try:
                orders = []
                orders = await consumer.create_new_orders(min_trigger_market, evaluation, state)
                trading_mode_test_toolkit.check_orders(orders, evaluation, state, 0, market_status)
                trading_mode_test_toolkit.check_portfolio(portfolio_wrapper, initial_portfolio, orders, True)
                await trading_mode_test_toolkit.fill_orders(orders, trader)
            except trading_errors.MissingMinimalExchangeTradeVolume:
                pass

    _reset_portfolio(exchange_manager)
    for state in _get_states_gradient_with_invald_states():
        for evaluation in _get_irrationnal_numbers():
            # orders are possible
            try:
                orders = await consumer.create_new_orders(symbol, evaluation, state)
                trading_mode_test_toolkit.check_orders(orders, evaluation, state, nb_orders, market_status)
                trading_mode_test_toolkit.check_portfolio(portfolio_wrapper, initial_portfolio, orders, True)
                if any(order
                       for order in orders
                       if order.order_type not in (
                trading_enums.TraderOrderType.SELL_MARKET, trading_enums.TraderOrderType.BUY_MARKET)):
                    # no need to fill market orders
                    await trading_mode_test_toolkit.fill_orders(orders, trader)
            except trading_errors.MissingMinimalExchangeTradeVolume:
                pass
            # orders are impossible
            try:
                orders = []
                orders = await consumer.create_new_orders(min_trigger_market, evaluation, state)
                trading_mode_test_toolkit.check_orders(orders, evaluation, state, 0, market_status)
                trading_mode_test_toolkit.check_portfolio(portfolio_wrapper, initial_portfolio, orders, True)
                if any(order
                       for order in orders
                       if order.order_type not in (
                trading_enums.TraderOrderType.SELL_MARKET, trading_enums.TraderOrderType.BUY_MARKET)):
                    # no need to fill market orders
                    await trading_mode_test_toolkit.fill_orders(orders, trader)
            except trading_errors.MissingMinimalExchangeTradeVolume:
                pass

    _reset_portfolio(exchange_manager)
    for state in _get_states_gradient_with_invald_states():
        # orders are possible
        try:
            orders = await consumer.create_new_orders(symbol, decimal.Decimal("nan"), state)
            trading_mode_test_toolkit.check_orders(orders, math.nan, state, nb_orders, market_status)
            trading_mode_test_toolkit.check_portfolio(portfolio_wrapper, initial_portfolio, orders, True)
            await trading_mode_test_toolkit.fill_orders(orders, trader)
        except trading_errors.MissingMinimalExchangeTradeVolume:
            pass
        # orders are impossible
        try:
            orders = []
            orders = await consumer.create_new_orders(min_trigger_market, decimal.Decimal("nan"), state)
            trading_mode_test_toolkit.check_orders(orders, math.nan, state, 0, market_status)
            trading_mode_test_toolkit.check_portfolio(portfolio_wrapper, initial_portfolio, orders, True)
            await trading_mode_test_toolkit.fill_orders(orders, trader)
        except trading_errors.MissingMinimalExchangeTradeVolume:
            pass


async def test_create_multiple_buy_orders_after_fill(tools):
    exchange_manager, trader, symbol, consumer, last_btc_price = tools

    # with BTC/USDT
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder.last_prices_by_trading_pair[symbol] = \
        last_btc_price
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder.portfolio_current_value = \
        decimal.Decimal(str(10 + 1000 / last_btc_price))
    # force many traded asset not to create all in orders
    exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder.origin_crypto_currencies_values \
        = {
        "a": trading_constants.ZERO,
        "b": trading_constants.ZERO,
        "c": trading_constants.ZERO,
        "d": trading_constants.ZERO,
        "e": trading_constants.ZERO
    }
    await ensure_smaller_orders(consumer, symbol, trader)

    # with another symbol with 0 quantity when start
    trading_api.force_set_mark_price(exchange_manager, "ADA/BTC", 0.0000001)
    await ensure_smaller_orders(consumer, "ADA/BTC", trader)


async def ensure_smaller_orders(consumer, symbol, trader):
    state = trading_enums.EvaluatorStates.VERY_LONG.value

    # first call: biggest order
    orders1 = (await consumer.create_new_orders(symbol, decimal.Decimal(str(-1)), state))
    if any(order
           for order in orders1
           if order.order_type not in (
    trading_enums.TraderOrderType.SELL_MARKET, trading_enums.TraderOrderType.BUY_MARKET)):
        # no need to fill market orders
        await trading_mode_test_toolkit.fill_orders(orders1, trader)

    state = trading_enums.EvaluatorStates.LONG.value
    # second call: smaller order (same with very long as with long)
    orders2 = (await consumer.create_new_orders(symbol, decimal.Decimal(str(-0.6)), state))
    assert orders1[0].origin_quantity > orders2[0].origin_quantity
    if any(order
           for order in orders2
           if order.order_type not in (
    trading_enums.TraderOrderType.SELL_MARKET, trading_enums.TraderOrderType.BUY_MARKET)):
        # no need to fill market orders
        await trading_mode_test_toolkit.fill_orders(orders2, trader)

    # third call: even smaller order
    orders3 = (await consumer.create_new_orders(symbol, decimal.Decimal(str(-0.6)), state))
    assert orders2[0].origin_quantity > orders3[0].origin_quantity
    if any(order
           for order in orders3
           if order.order_type not in (
    trading_enums.TraderOrderType.SELL_MARKET, trading_enums.TraderOrderType.BUY_MARKET)):
        # no need to fill market orders
        await trading_mode_test_toolkit.fill_orders(orders3, trader)

    # third call: even-even smaller order
    orders4 = (await consumer.create_new_orders(symbol, decimal.Decimal(str(-0.6)), state))
    assert orders3[0].origin_quantity > orders4[0].origin_quantity
    if any(order
           for order in orders4
           if order.order_type not in (
    trading_enums.TraderOrderType.SELL_MARKET, trading_enums.TraderOrderType.BUY_MARKET)):
        # no need to fill market orders
        await trading_mode_test_toolkit.fill_orders(orders4, trader)
