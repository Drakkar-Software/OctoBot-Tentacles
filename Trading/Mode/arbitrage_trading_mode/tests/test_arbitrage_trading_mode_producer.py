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
from mock import patch, AsyncMock, Mock

from octobot_trading.enums import EvaluatorStates, ExchangeConstantsOrderColumns, OrderStatus, FeePropertyColumns, \
    TradeOrderType
from tentacles.Trading.Mode.arbitrage_trading_mode.arbitrage_container import ArbitrageContainer
from tentacles.Trading.Mode.arbitrage_trading_mode.tests import exchange

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def test_init():
    async with exchange("binance") as exchange_tuple:
        binance_producer, binance_consumer, _ = exchange_tuple

        # producer
        assert binance_producer.own_exchange_mark_price is None
        assert binance_producer.other_exchanges_mark_prices == {}
        assert binance_producer.triggering_price_delta_ratio < 1
        assert binance_producer.base
        assert binance_producer.quote
        assert binance_producer.lock


async def test_own_exchange_mark_price_callback():
    async with exchange("binance") as exchange_tuple:
        binance_producer, _, _ = exchange_tuple

        with patch.object(binance_producer, "_create_arbitrage_initial_order", new=AsyncMock()) as order_mock:
            # no other exchange mark price yet
            await binance_producer._own_exchange_mark_price_callback("", "", "", "", 11)
            assert binance_producer.own_exchange_mark_price == 11
            order_mock.assert_not_called()

            binance_producer.other_exchanges_mark_prices["kraken"] = 20
            binance_producer.other_exchanges_mark_prices["bitfinex"] = 22
            # other exchange mark price is set
            await binance_producer._own_exchange_mark_price_callback("", "", "", "", 11)
            order_mock.assert_called_once()


async def test_mark_price_callback():
    binance = "binance"
    kraken = "kraken"
    async with exchange(binance) as binance_tuple, \
            exchange(kraken, backtesting=binance_tuple[2].backtesting) as kraken_tuple:
        binance_producer, _, _ = binance_tuple
        kraken_producer, _, _ = kraken_tuple

        with patch.object(binance_producer, "_create_arbitrage_initial_order", new=AsyncMock()) as binance_order_mock, \
            patch.object(kraken_producer, "_create_arbitrage_initial_order", new=AsyncMock()) as kraken_order_mock:
            # no own exchange price yet
            await kraken_producer._mark_price_callback(binance, "", "", "", 1000)
            kraken_order_mock.assert_not_called()
            await binance_producer._mark_price_callback(kraken, "", "", "", 1000)
            binance_order_mock.assert_not_called()

            # set own exchange mark price on kraken
            kraken_producer.own_exchange_mark_price = 900
            # no effect on binance
            await binance_producer._mark_price_callback(kraken, "", "", "", 1000)
            binance_order_mock.assert_not_called()
            # create arbitrage on kraken
            await kraken_producer._mark_price_callback(binance, "", "", "", 1000)
            kraken_order_mock.assert_called_once()


async def test_order_filled_callback():
    async with exchange("binance") as exchange_tuple:
        binance_producer, binance_consumer, _ = exchange_tuple
        order_id = "1"
        price = 10
        quantity = 3
        fees = 0.1
        fees_currency = "BTC"
        symbol = "BTC/USD"
        order_dict = get_order_dict(order_id, symbol, price, quantity, OrderStatus.FILLED.value,
                                    TradeOrderType.LIMIT.value, fees, fees_currency)
        with patch.object(binance_producer, "_close_arbitrage", new=Mock()) as close_mock, \
            patch.object(binance_producer, "_trigger_arbitrage_secondary_order", new=AsyncMock()) as trigger_mock, \
            patch.object(binance_producer, "_log_results", new=Mock()) as result_mock:
            # nothing happens: order id not in open arbitrages
            await binance_producer.order_filled_callback(order_dict)
            close_mock.assert_not_called()
            trigger_mock.assert_not_called()

            # order id now in open arbitrages
            arbitrage = ArbitrageContainer(price, 15, EvaluatorStates.LONG)
            arbitrage.initial_limit_order_id = order_id
            binance_consumer.open_arbitrages.append(arbitrage)

            await binance_producer.order_filled_callback(order_dict)
            close_mock.assert_not_called()
            result_mock.assert_not_called()
            # call create secondary order
            trigger_mock.assert_called_once()
            trigger_mock.reset_mock()

            # last step case 1: close arbitrage: fill callback with secondary limit order
            limit_id = "2"
            arbitrage.passed_initial_order = True
            arbitrage.secondary_limit_order_id = limit_id
            arbitrage.initial_before_fee_filled_quantity = 29.9
            sec_limit_order_dict = get_order_dict(limit_id, symbol, price, quantity, OrderStatus.FILLED.value,
                                                  TradeOrderType.LIMIT.value, fees, fees_currency)
            await binance_producer.order_filled_callback(sec_limit_order_dict)
            # call close arbitrage
            close_mock.assert_called_once()
            trigger_mock.assert_not_called()
            result_mock.assert_called_once()
            _, arbitrage_success, filled_quantity = result_mock.mock_calls[0].args
            assert arbitrage_success
            assert filled_quantity == quantity * price
            close_mock.reset_mock()
            result_mock.reset_mock()

            # last step case 2: close arbitrage: fill callback with secondary stop order
            stop_id = "3"
            arbitrage.secondary_stop_order_id = stop_id
            sec_stop_order_dict = get_order_dict(stop_id, symbol, price, quantity, OrderStatus.FILLED.value,
                                                 TradeOrderType.STOP_LOSS.value, fees, fees_currency)
            await binance_producer.order_filled_callback(sec_stop_order_dict)
            # call close arbitrage
            close_mock.assert_called_once()
            result_mock.assert_called_once()
            _, arbitrage_success, filled_quantity = result_mock.mock_calls[0].args
            assert not arbitrage_success
            assert filled_quantity == quantity * price
            trigger_mock.assert_not_called()


async def test_order_cancelled_callback():
    async with exchange("binance") as exchange_tuple:
        binance_producer, binance_consumer, _ = exchange_tuple
        order_id = "1"
        price = 10
        quantity = 3
        fees = 0.1
        fees_currency = "BTC"
        symbol = "BTC/USD"
        order_dict = get_order_dict(order_id, symbol, price, quantity, OrderStatus.FILLED.value,
                                    TradeOrderType.LIMIT.value, fees, fees_currency)
        with patch.object(binance_producer, "_close_arbitrage", new=Mock()) as close_mock:
            # no open arbitrage
            await binance_producer.order_cancelled_callback(order_dict)
            close_mock.assert_not_called()

            # open arbitrage with different order id: nothing happens
            arbitrage = ArbitrageContainer(price, 15, EvaluatorStates.LONG)
            binance_consumer.open_arbitrages.append(arbitrage)
            await binance_producer.order_cancelled_callback(order_dict)
            close_mock.assert_not_called()

            # open arbitrage with this order id: arbitrage gets closed
            arbitrage.initial_limit_order_id = order_id
            await binance_producer.order_cancelled_callback(order_dict)
            close_mock.assert_called_once()


async def test_analyse_arbitrage_opportunities():
    async with exchange("binance") as exchange_tuple:
        binance_producer, _, _ = exchange_tuple

        with patch.object(binance_producer, "_ensure_no_expired_opportunities", new=AsyncMock()) as expiration_mock, \
            patch.object(binance_producer, "_trigger_arbitrage_opportunity", new=AsyncMock()) as trigger_mock:
            # long opportunity 1
            binance_producer.own_exchange_mark_price = 10
            binance_producer.other_exchanges_mark_prices = {"kraken": 100, "binanceje": 200, "bitfinex": 150}
            await binance_producer._analyse_arbitrage_opportunities()
            expiration_mock.assert_called_once_with(150, EvaluatorStates.LONG)
            trigger_mock.assert_called_once_with(150, EvaluatorStates.LONG)
            expiration_mock.reset_mock()
            trigger_mock.reset_mock()

            # short opportunity 1
            binance_producer.own_exchange_mark_price = 100
            binance_producer.other_exchanges_mark_prices = {"kraken": 70, "binanceje": 71, "bitfinex": 75}
            await binance_producer._analyse_arbitrage_opportunities()
            expiration_mock.assert_called_once_with(72, EvaluatorStates.SHORT)
            trigger_mock.assert_called_once_with(72, EvaluatorStates.SHORT)
            expiration_mock.reset_mock()
            trigger_mock.reset_mock()

            # long opportunity but price too close to current price
            binance_producer.own_exchange_mark_price = 71.99
            binance_producer.other_exchanges_mark_prices = {"kraken": 70, "binanceje": 71, "bitfinex": 75}
            await binance_producer._analyse_arbitrage_opportunities()
            expiration_mock.assert_not_called()
            trigger_mock.assert_not_called()

            # short opportunity but price too close to current price
            binance_producer.own_exchange_mark_price = 72.01
            binance_producer.other_exchanges_mark_prices = {"kraken": 70, "binanceje": 71, "bitfinex": 75}
            await binance_producer._analyse_arbitrage_opportunities()
            expiration_mock.assert_not_called()
            trigger_mock.assert_not_called()

            # with higher numbers
            # higher numbers long opportunity
            # min long exclusive trigger should be 9980
            binance_producer.own_exchange_mark_price = 9979.9999
            binance_producer.other_exchanges_mark_prices = {"kraken": 9000, "binanceje": 10000, "bitfinex": 11000}
            await binance_producer._analyse_arbitrage_opportunities()
            expiration_mock.assert_called_once_with(10000, EvaluatorStates.LONG)
            trigger_mock.assert_called_once_with(10000, EvaluatorStates.LONG)
            expiration_mock.reset_mock()
            trigger_mock.reset_mock()

            # higher numbers long opportunity: fail to pass threshold 1
            # min long exclusive trigger should be 9980
            binance_producer.own_exchange_mark_price = 9980
            binance_producer.other_exchanges_mark_prices = {"kraken": 9000, "binanceje": 10000, "bitfinex": 11000}
            await binance_producer._analyse_arbitrage_opportunities()
            expiration_mock.assert_not_called()
            trigger_mock.assert_not_called()
            expiration_mock.reset_mock()
            trigger_mock.reset_mock()

            # higher numbers long opportunity: fail to pass threshold 2
            # min long exclusive trigger should be 9980
            binance_producer.own_exchange_mark_price = 9980.0001
            binance_producer.other_exchanges_mark_prices = {"kraken": 9000, "binanceje": 10000, "bitfinex": 11000}
            await binance_producer._analyse_arbitrage_opportunities()
            expiration_mock.assert_not_called()
            trigger_mock.assert_not_called()
            expiration_mock.reset_mock()
            trigger_mock.reset_mock()

            # higher numbers short opportunity
            # min short exclusive trigger should be 9980
            binance_producer.own_exchange_mark_price = 10000
            binance_producer.other_exchanges_mark_prices = {"kraken": 9979.9999, "binanceje": 9970, "bitfinex": 9990}
            await binance_producer._analyse_arbitrage_opportunities()
            expiration_mock.assert_called_once_with(9979.999966666668, EvaluatorStates.SHORT)
            trigger_mock.assert_called_once_with(9979.999966666668, EvaluatorStates.SHORT)
            expiration_mock.reset_mock()
            trigger_mock.reset_mock()

            # higher numbers short opportunity: fail to pass threshold 1
            # min short exclusive trigger should be 9980
            binance_producer.own_exchange_mark_price = 10000
            binance_producer.other_exchanges_mark_prices = {"kraken": 9980, "binanceje": 9981, "bitfinex": 9979}
            await binance_producer._analyse_arbitrage_opportunities()
            expiration_mock.assert_not_called()
            trigger_mock.assert_not_called()
            expiration_mock.reset_mock()
            trigger_mock.reset_mock()

            # higher numbers short opportunity: fail to pass threshold 2
            # min short exclusive trigger should be 9980
            binance_producer.own_exchange_mark_price = 10000
            binance_producer.other_exchanges_mark_prices = {"kraken": 9980.0001, "binanceje": 9981, "bitfinex": 9979}
            await binance_producer._analyse_arbitrage_opportunities()
            expiration_mock.assert_not_called()
            trigger_mock.assert_not_called()
            expiration_mock.reset_mock()
            trigger_mock.reset_mock()


async def test_trigger_arbitrage_opportunity():
    async with exchange("binance") as exchange_tuple:
        binance_producer, _, _ = exchange_tuple

        with patch.object(binance_producer, "_create_arbitrage_initial_order", new=AsyncMock()) as order_mock, \
          patch.object(binance_producer, "_register_state", new=Mock()) as register_mock:
            binance_producer.own_exchange_mark_price = 10
            await binance_producer._trigger_arbitrage_opportunity(15, EvaluatorStates.LONG)
            order_mock.assert_called_once()
            register_mock.assert_called_once_with(EvaluatorStates.LONG, 5)


async def test_trigger_arbitrage_secondary_order():
    async with exchange("binance") as exchange_tuple:
        binance_producer, _, _ = exchange_tuple
        order_id = "1"
        price = 10
        quantity = 3
        fees = 0.1
        fees_currency = "BTC"
        symbol = "BTC/USDT"
        order_dict = get_order_dict(order_id, symbol, price, quantity, OrderStatus.FILLED.value,
                                    TradeOrderType.LIMIT.value, fees, fees_currency)
        with patch.object(binance_producer, "_create_arbitrage_secondary_order", new=AsyncMock()) as order_mock:
            # long: already bought, is now selling
            arbitrage = ArbitrageContainer(price, 15, EvaluatorStates.LONG)
            await binance_producer._trigger_arbitrage_secondary_order(arbitrage, order_dict, 3)
            updated_arbitrage, secondary_quantity = order_mock.mock_calls[0].args
            assert updated_arbitrage is arbitrage
            assert arbitrage.passed_initial_order
            assert arbitrage.initial_before_fee_filled_quantity == 30
            assert secondary_quantity == 2.9
            order_mock.reset_mock()

            # short: already sold, is now buying: no fee on base side
            arbitrage_2 = ArbitrageContainer(price, 7, EvaluatorStates.SHORT)
            await binance_producer._trigger_arbitrage_secondary_order(arbitrage_2, order_dict, 3)
            updated_arbitrage, secondary_quantity = order_mock.mock_calls[0].args
            assert updated_arbitrage is arbitrage_2
            assert arbitrage_2.passed_initial_order
            assert arbitrage_2.initial_before_fee_filled_quantity == 3
            assert round(secondary_quantity, 5) == 4.14282
            order_mock.reset_mock()

            # short: already sold, is now buying: fee on base side
            arbitrage_3 = ArbitrageContainer(price, 7, EvaluatorStates.SHORT)
            order_dict = get_order_dict(order_id, symbol, price, quantity, OrderStatus.FILLED.value,
                                        TradeOrderType.STOP_LOSS.value, fees, "USDT")
            await binance_producer._trigger_arbitrage_secondary_order(arbitrage_3, order_dict, 3)
            updated_arbitrage, secondary_quantity = order_mock.mock_calls[0].args
            assert updated_arbitrage is arbitrage_3
            assert arbitrage_3.passed_initial_order
            assert arbitrage_3.initial_before_fee_filled_quantity == 3
            assert round(secondary_quantity, 5) == 4.27139


async def test_ensure_no_existing_arbitrage_on_this_price():
    async with exchange("binance") as exchange_tuple:
        binance_producer, binance_consumer, _ = exchange_tuple
        arbitrage_1 = ArbitrageContainer(10, 15, EvaluatorStates.LONG)
        arbitrage_2 = ArbitrageContainer(20, 18, EvaluatorStates.SHORT)
        binance_consumer.open_arbitrages = [arbitrage_1, arbitrage_2]

        binance_producer.own_exchange_mark_price = 9
        assert binance_producer._ensure_no_existing_arbitrage_on_this_price(EvaluatorStates.LONG)
        assert binance_producer._ensure_no_existing_arbitrage_on_this_price(EvaluatorStates.SHORT)

        for price in (9.99, 10, 11, 15):
            binance_producer.own_exchange_mark_price = price
            assert not binance_producer._ensure_no_existing_arbitrage_on_this_price(EvaluatorStates.LONG)
            assert binance_producer._ensure_no_existing_arbitrage_on_this_price(EvaluatorStates.SHORT)

        for price in (18, 17.99, 20, 20.001):
            binance_producer.own_exchange_mark_price = price
            assert binance_producer._ensure_no_existing_arbitrage_on_this_price(EvaluatorStates.LONG)
            assert not binance_producer._ensure_no_existing_arbitrage_on_this_price(EvaluatorStates.SHORT)


async def test_get_arbitrage():
    async with exchange("binance") as exchange_tuple:
        binance_producer, binance_consumer, _ = exchange_tuple
        arbitrage_1 = ArbitrageContainer(10, 15, EvaluatorStates.LONG)
        arbitrage_2 = ArbitrageContainer(20, 18, EvaluatorStates.SHORT)
        binance_consumer.open_arbitrages = [arbitrage_1, arbitrage_2]
        arbitrage_1.initial_limit_order_id = "1"
        assert arbitrage_1 is binance_producer._get_arbitrage("1")
        assert None is binance_producer._get_arbitrage("2")


async def test_ensure_no_expired_opportunities():
    async with exchange("binance") as exchange_tuple:
        binance_producer, binance_consumer, exchange_manager = exchange_tuple
        arbitrage_1 = ArbitrageContainer(10, 15, EvaluatorStates.LONG)
        arbitrage_2 = ArbitrageContainer(20, 17, EvaluatorStates.SHORT)
        binance_consumer.open_arbitrages = [arbitrage_1, arbitrage_2]

        with patch.object(binance_producer, "_cancel_order", new=AsyncMock()) as cancel_order_mock:
            # average price is 18
            # long order is valid
            # short order is expired (price > 17)
            await binance_producer._ensure_no_expired_opportunities(18, EvaluatorStates.LONG)
            assert arbitrage_2 not in binance_consumer.open_arbitrages
            cancel_order_mock.assert_called_once()
            cancel_order_mock.reset_mock()

            await binance_producer._ensure_no_expired_opportunities(18, EvaluatorStates.SHORT)
            assert binance_consumer.open_arbitrages == [arbitrage_1]
            cancel_order_mock.assert_not_called()


async def test_close_arbitrage():
    async with exchange("binance") as exchange_tuple:
        binance_producer, binance_consumer, _ = exchange_tuple
        arbitrage_1 = ArbitrageContainer(10, 15, EvaluatorStates.LONG)
        arbitrage_2 = ArbitrageContainer(20, 17, EvaluatorStates.SHORT)
        binance_consumer.open_arbitrages = [arbitrage_1, arbitrage_2]
        binance_producer._close_arbitrage(arbitrage_1)
        assert arbitrage_1 not in binance_consumer.open_arbitrages
        assert binance_producer.state is EvaluatorStates.NEUTRAL
        assert binance_producer.final_eval == ""


async def test_get_open_arbitrages():
    binance = "binance"
    kraken = "kraken"
    async with exchange(binance) as binance_tuple, \
            exchange(kraken, backtesting=binance_tuple[2].backtesting) as kraken_tuple:
        binance_producer, binance_consumer, _ = binance_tuple
        kraken_producer, kraken_consumer, _ = kraken_tuple
        arbitrage_1 = ArbitrageContainer(10, 15, EvaluatorStates.LONG)
        arbitrage_2 = ArbitrageContainer(20, 17, EvaluatorStates.SHORT)
        binance_consumer.open_arbitrages = [arbitrage_1, arbitrage_2]
        assert kraken_consumer.open_arbitrages == []
        assert binance_producer._get_open_arbitrages() is binance_consumer.open_arbitrages
        assert kraken_producer._get_open_arbitrages() is kraken_consumer.open_arbitrages


async def test_register_state():
    async with exchange("binance") as exchange_tuple:
        binance_producer, binance_consumer, _ = exchange_tuple
        assert binance_producer.state is EvaluatorStates.NEUTRAL
        binance_producer._register_state(EvaluatorStates.LONG, 1)
        assert binance_producer.state is EvaluatorStates.LONG
        assert "1" in binance_producer.final_eval


def get_order_dict(order_id, symbol, price, quantity, status, order_type, fees_amount, fees_currency):
    return {
        ExchangeConstantsOrderColumns.ID.value: order_id,
        ExchangeConstantsOrderColumns.SYMBOL.value: symbol,
        ExchangeConstantsOrderColumns.PRICE.value: price,
        ExchangeConstantsOrderColumns.AMOUNT.value: quantity,
        ExchangeConstantsOrderColumns.FILLED.value: quantity,
        ExchangeConstantsOrderColumns.STATUS.value: status,
        ExchangeConstantsOrderColumns.TYPE.value: order_type,
        ExchangeConstantsOrderColumns.FEE.value: {
            FeePropertyColumns.CURRENCY.value: fees_currency,
            FeePropertyColumns.COST.value: fees_amount
        },
    }
