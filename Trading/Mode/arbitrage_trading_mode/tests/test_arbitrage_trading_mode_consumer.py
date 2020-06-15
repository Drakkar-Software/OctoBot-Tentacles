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
from mock import patch, AsyncMock

from octobot_trading.enums import EvaluatorStates, TradeOrderType, TraderOrderType, TradeOrderSide
from tentacles.Trading.Mode.arbitrage_trading_mode.arbitrage_container import ArbitrageContainer
from tentacles.Trading.Mode.arbitrage_trading_mode.arbitrage_trading_mode import ArbitrageModeConsumer
from tentacles.Trading.Mode.arbitrage_trading_mode.tests import exchange

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def test_init():
    async with exchange("binance") as exchange_tuple:
        binance_producer, binance_consumer, _ = exchange_tuple

        # trading mode
        assert len(binance_producer.trading_mode.consumers) == 2
        assert len(binance_producer.trading_mode.producers) == 1

        # consumer
        assert binance_consumer.PORTFOLIO_PERCENT_PER_TRADE != 0
        assert binance_consumer.STOP_LOSS_DELTA_FROM_OWN_PRICE != 0
        assert binance_consumer.open_arbitrages == []


async def test_create_new_orders():
    async with exchange("binance") as exchange_tuple:
        _, binance_consumer, _ = exchange_tuple

        symbol = "BTC/USDT"
        final_note = None
        state = EvaluatorStates.SHORT
        with patch.object(binance_consumer, "_create_initial_arbitrage_order", new=AsyncMock()) as initial_mock, \
            patch.object(binance_consumer, "_create_secondary_arbitrage_order", new=AsyncMock()) as secondary_mock:
            # no data in kwargs
            with pytest.raises(KeyError):
                await binance_consumer.create_new_orders(symbol, final_note, state)
            initial_mock.assert_not_called()
            secondary_mock.assert_not_called()

            data = {
                ArbitrageModeConsumer.ARBITRAGE_PHASE_KEY: ArbitrageModeConsumer.INITIAL_PHASE,
                ArbitrageModeConsumer.ARBITRAGE_CONTAINER_KEY: None
            }
            await binance_consumer.create_new_orders(symbol, final_note, state, data=data)
            initial_mock.assert_called_once()
            secondary_mock.assert_not_called()
            initial_mock.reset_mock()

            data = {
                ArbitrageModeConsumer.ARBITRAGE_PHASE_KEY: ArbitrageModeConsumer.SECONDARY_PHASE,
                ArbitrageModeConsumer.ARBITRAGE_CONTAINER_KEY: None,
                ArbitrageModeConsumer.QUANTITY_KEY: None
            }
            await binance_consumer.create_new_orders(symbol, final_note, state, data=data)
            initial_mock.assert_not_called()
            secondary_mock.assert_called_once()


async def test_create_initial_arbitrage_order():
    async with exchange("binance") as exchange_tuple:
        _, binance_consumer, _ = exchange_tuple
        price = 10
        # long
        arbitrage = ArbitrageContainer(price, 15, EvaluatorStates.LONG)
        orders = await binance_consumer._create_initial_arbitrage_order(arbitrage)
        assert orders
        order = orders[0]
        assert order.exchange_order_type is TradeOrderType.LIMIT
        assert order.order_type is TraderOrderType.BUY_LIMIT
        assert order.side is TradeOrderSide.BUY
        assert order.symbol == binance_consumer.trading_mode.symbol
        assert order.order_id == arbitrage.initial_limit_order_id
        assert arbitrage in binance_consumer.open_arbitrages

        # short
        arbitrage = ArbitrageContainer(price, 15, EvaluatorStates.SHORT)
        orders = await binance_consumer._create_initial_arbitrage_order(arbitrage)
        assert orders
        order = orders[0]
        assert order.exchange_order_type is TradeOrderType.LIMIT
        assert order.order_type is TraderOrderType.SELL_LIMIT
        assert order.side is TradeOrderSide.SELL
        assert order.symbol == binance_consumer.trading_mode.symbol
        assert order.order_id == arbitrage.initial_limit_order_id
        assert arbitrage in binance_consumer.open_arbitrages


async def test_create_secondary_arbitrage_order():
    async with exchange("binance") as exchange_tuple:
        _, binance_consumer, _ = exchange_tuple
        price = 10

        # long
        arbitrage = ArbitrageContainer(price, 15, EvaluatorStates.LONG)
        quantity = 5
        orders = await binance_consumer._create_secondary_arbitrage_order(arbitrage, quantity)
        assert orders

        limit_order = orders[0]
        assert limit_order.exchange_order_type is TradeOrderType.LIMIT
        assert limit_order.order_type is TraderOrderType.SELL_LIMIT
        assert limit_order.side is TradeOrderSide.SELL
        assert limit_order.symbol == binance_consumer.trading_mode.symbol
        assert limit_order.order_id == arbitrage.secondary_limit_order_id
        assert limit_order.origin_quantity == quantity

        stop_order = limit_order.linked_orders[0]
        assert stop_order.exchange_order_type is TradeOrderType.STOP_LOSS
        assert stop_order.order_type is TraderOrderType.STOP_LOSS
        assert stop_order.side is TradeOrderSide.SELL
        assert stop_order.symbol == binance_consumer.trading_mode.symbol
        assert stop_order.order_id == arbitrage.secondary_stop_order_id
        assert stop_order.origin_quantity == quantity

        # short
        arbitrage = ArbitrageContainer(price, 15, EvaluatorStates.SHORT)
        quantity = 5
        orders = await binance_consumer._create_secondary_arbitrage_order(arbitrage, quantity)
        assert orders

        limit_order = orders[0]
        assert limit_order.exchange_order_type is TradeOrderType.LIMIT
        assert limit_order.order_type is TraderOrderType.BUY_LIMIT
        assert limit_order.side is TradeOrderSide.BUY
        assert limit_order.symbol == binance_consumer.trading_mode.symbol
        assert limit_order.order_id == arbitrage.secondary_limit_order_id
        assert limit_order.origin_quantity == quantity

        stop_order = limit_order.linked_orders[0]
        assert stop_order.exchange_order_type is TradeOrderType.STOP_LOSS
        assert stop_order.order_type is TraderOrderType.STOP_LOSS
        assert stop_order.side is TradeOrderSide.BUY
        assert stop_order.symbol == binance_consumer.trading_mode.symbol
        assert stop_order.order_id == arbitrage.secondary_stop_order_id
        assert stop_order.origin_quantity == quantity


async def test_get_quantity_from_holdings():
    async with exchange("binance") as exchange_tuple:
        _, binance_consumer, _ = exchange_tuple
        binance_consumer.PORTFOLIO_PERCENT_PER_TRADE = 0.5
        assert binance_consumer._get_quantity_from_holdings(10, 100, EvaluatorStates.SHORT) == 5
        assert binance_consumer._get_quantity_from_holdings(10, 100, EvaluatorStates.LONG) == 50


async def test_get_stop_loss_price():
    async with exchange("binance") as exchange_tuple:
        _, binance_consumer, exchange_manager = exchange_tuple
        binance_consumer.STOP_LOSS_DELTA_FROM_OWN_PRICE = 0.01
        symbol_market = exchange_manager.exchange.get_market_status("BTC/USDT", with_fixer=False)
        assert binance_consumer._get_stop_loss_price(symbol_market, 100, True) == 99
        assert binance_consumer._get_stop_loss_price(symbol_market, 100, False) == 101
