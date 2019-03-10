#  Drakkar-Software OctoBot
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

import ccxt
import pytest

from config import CONFIG_SIMULATOR, CONFIG_SIMULATOR_FEES, ExchangeConstantsOrderBookInfoColumns
from tentacles.Trading.Mode import MarketMakerTradingModeCreator, MarketMakerTradingMode
from tests.test_utils.config import load_test_config
from trading.exchanges.exchange_manager import ExchangeManager
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

    trading_mode = MarketMakerTradingMode(config, exchange_inst)

    return config, exchange_inst, trader_inst, symbol, trading_mode


async def test_verify_and_adapt_delta_with_fees():
    config, exchange, trader, symbol, trading_mode = await _get_tools()

    # with default exchange simulator fees {'taker': 0, 'maker': 0, 'fee': 0}
    order_creator = MarketMakerTradingModeCreator(trading_mode)

    # expect to use specified fees
    order_creator.config_delta_bid = 10
    order_creator.config_delta_ask = 15
    assert order_creator.verify_and_adapt_delta_with_fees(symbol) == (15, 10)

    # with modified simulator fees
    config[CONFIG_SIMULATOR][CONFIG_SIMULATOR_FEES] = {
        ExchangeConstantsMarketPropertyColumns.TAKER.value: 30,
        ExchangeConstantsMarketPropertyColumns.MAKER.value: 40,
        ExchangeConstantsMarketPropertyColumns.FEE.value: 50
    }
    order_creator = MarketMakerTradingModeCreator(trading_mode)

    # expect to use specified fees
    order_creator.config_delta_bid = 100
    order_creator.config_delta_ask = 200
    assert order_creator.verify_and_adapt_delta_with_fees(symbol) == (200, 100)

    # expect to use exchange fees
    order_creator = MarketMakerTradingModeCreator(trading_mode)
    order_creator.config_delta_bid = 1
    order_creator.config_delta_ask = 2
    assert order_creator.verify_and_adapt_delta_with_fees(symbol) == (40 / order_creator.FEES_ATTENUATION,
                                                                      40 / order_creator.FEES_ATTENUATION)


async def test_create_new_order():
    config, exchange, trader, symbol, trading_mode = await _get_tools()
    portfolio = trader.get_portfolio()
    order_creator = MarketMakerTradingModeCreator(trading_mode)

    # portfolio: "BTC": 10 "USD": 1000
    last_btc_price = 6943.01

    # With incorrect eval_note
    assert await order_creator.create_new_order(-1, symbol, exchange, trader, portfolio, None) is None

    # With correct eval_note
    last_bid_price = 190
    last_ask_price = 200
    eval_note = {
        ExchangeConstantsOrderBookInfoColumns.BIDS.value: [last_bid_price, 0.2],
        ExchangeConstantsOrderBookInfoColumns.ASKS.value: [last_ask_price, 0.2]
    }
    # with modified simulator fees
    config[CONFIG_SIMULATOR][CONFIG_SIMULATOR_FEES] = {
        ExchangeConstantsMarketPropertyColumns.TAKER.value: 0.02,
        ExchangeConstantsMarketPropertyColumns.MAKER.value: 0.02,
        ExchangeConstantsMarketPropertyColumns.FEE.value: 0.02
    }
    order_creator = MarketMakerTradingModeCreator(trading_mode)
    orders = await order_creator.create_new_order(eval_note, symbol, exchange, trader, portfolio, None)
    assert len(orders) == 2

    # ASK ORDER
    qty = 10 / order_creator.LIMIT_ORDER_ATTENUATION
    order = orders[0]
    assert isinstance(order, SellLimitOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert order.origin_price == 198.0
    assert order.created_last_price == last_btc_price
    assert order.order_type == TraderOrderType.SELL_LIMIT
    assert order.side == TradeOrderSide.SELL
    assert order.status == OrderStatus.OPEN
    assert order.exchange == exchange
    assert order.trader == trader
    assert order.fee is None
    assert order.market_total_fees == 0
    assert order.filled_price == 0
    assert order.origin_quantity == qty
    assert order.filled_quantity == order.origin_quantity
    assert order.is_simulated is True
    assert order.linked_to is None

    # BID ORDER
    qty = round((2000 / order_creator.LIMIT_ORDER_ATTENUATION) / last_btc_price, 8)
    order = orders[1]
    assert isinstance(order, BuyLimitOrder)
    assert order.currency == "BTC"
    assert order.symbol == "BTC/USDT"
    assert round(order.origin_price, 5) == 191.9
    # round((last_bid_price - (last_bid_price * qty / order_creator.FEES_ATTENUATION)), 5)
    assert order.created_last_price == last_btc_price
    assert order.order_type == TraderOrderType.BUY_LIMIT
    assert order.side == TradeOrderSide.BUY
    assert order.status == OrderStatus.OPEN
    assert order.exchange == exchange
    assert order.trader == trader
    assert order.fee is None
    assert order.market_total_fees == 0
    assert order.filled_price == 0
    assert order.origin_quantity == qty
    assert order.filled_quantity == order.origin_quantity
    assert order.is_simulated is True
    assert order.linked_to is None
