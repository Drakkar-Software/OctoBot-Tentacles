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

from config import EvaluatorStates, INIT_EVAL_NOTE
from tentacles_management.advanced_manager import AdvancedManager
from evaluator.cryptocurrency_evaluator import CryptocurrencyEvaluator
from evaluator.evaluator_creator import EvaluatorCreator
from evaluator.symbol_evaluator import SymbolEvaluator
from tests.test_utils.config import load_test_config
from trading.exchanges.exchange_manager import ExchangeManager
from trading.trader.modes import DailyTradingMode
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
    trader_inst = TraderSimulator(config, exchange_inst, 0.3)
    await trader_inst.initialize()
    trader_inst.stop_order_manager()
    trader_inst2 = TraderSimulator(config, exchange_inst, 0.3)
    await trader_inst2.initialize()
    trader_inst2.stop_order_manager()
    crypto_currency_evaluator = CryptocurrencyEvaluator(config, "Bitcoin", [])
    symbol_evaluator = SymbolEvaluator(config, symbol, crypto_currency_evaluator)
    exchange_traders[exchange_inst.get_name()] = trader_inst
    exchange_traders2[exchange_inst.get_name()] = trader_inst2
    symbol_evaluator.set_trader_simulators(exchange_traders)
    symbol_evaluator.set_traders(exchange_traders2)
    symbol_evaluator.strategies_eval_lists[exchange_inst.get_name()] = \
        EvaluatorCreator.create_strategies_eval_list(config)

    trading_mode = DailyTradingMode(config, exchange_inst)
    trading_mode.add_symbol_evaluator(symbol_evaluator)
    final_evaluator = trading_mode.get_only_decider_key(symbol)

    trader_inst.portfolio.portfolio["USDT"] = {
        Portfolio.TOTAL: 2000,
        Portfolio.AVAILABLE: 2000
    }
    return final_evaluator, trader_inst


async def test_default_values():
    final_evaluator, trader_inst = await _get_tools()
    assert final_evaluator.state is None
    final_evaluator.final_eval = 1211161
    assert final_evaluator.get_final_eval() == 1211161
    final_evaluator.state = "plop"
    assert final_evaluator.get_state() == "plop"


async def test_set_state():
    final_evaluator, trader_inst = await _get_tools()
    await final_evaluator._set_state(EvaluatorStates.NEUTRAL)
    assert final_evaluator.state == EvaluatorStates.NEUTRAL
    await final_evaluator._set_state(EvaluatorStates.VERY_LONG)
    assert final_evaluator.state == EvaluatorStates.VERY_LONG
    assert len(trader_inst.order_manager.order_list) == 1
    await final_evaluator._set_state(EvaluatorStates.NEUTRAL)
    await final_evaluator._set_state(EvaluatorStates.VERY_SHORT)
    assert final_evaluator.state == EvaluatorStates.VERY_SHORT
    assert len(trader_inst.order_manager.order_list) == 1
    await final_evaluator._set_state(EvaluatorStates.NEUTRAL)
    await final_evaluator._set_state(EvaluatorStates.LONG)
    assert final_evaluator.state == EvaluatorStates.LONG
    assert len(trader_inst.order_manager.order_list) == 1
    await final_evaluator._set_state(EvaluatorStates.NEUTRAL)
    await final_evaluator._set_state(EvaluatorStates.SHORT)
    assert final_evaluator.state == EvaluatorStates.SHORT
    assert len(trader_inst.order_manager.order_list) == 2  # has stop loss
    await final_evaluator._set_state(EvaluatorStates.NEUTRAL)
    assert final_evaluator.state == EvaluatorStates.NEUTRAL
    assert len(trader_inst.order_manager.order_list) == 2  # has not reset


async def test_get_delta_risk():
    final_evaluator, trader_inst = await _get_tools()
    for i in range(0, 100, 1):
        final_evaluator.symbol_evaluator.get_trader(final_evaluator.exchange).risk = i/100
        assert round(final_evaluator._get_delta_risk(), 6) == round(final_evaluator.RISK_THRESHOLD*i/100, 6)


async def test_create_state():
    final_evaluator, trader_inst = await _get_tools()
    delta_risk = final_evaluator._get_delta_risk()
    for i in range(-100, 100, 1):
        final_evaluator.final_eval = i/100
        await final_evaluator.create_state()
        if final_evaluator.final_eval < final_evaluator.VERY_LONG_THRESHOLD + delta_risk:
            assert final_evaluator.state == EvaluatorStates.VERY_LONG
        elif final_evaluator.final_eval < final_evaluator.LONG_THRESHOLD + delta_risk:
            assert final_evaluator.state == EvaluatorStates.LONG
        elif final_evaluator.final_eval < final_evaluator.NEUTRAL_THRESHOLD - delta_risk:
            assert final_evaluator.state == EvaluatorStates.NEUTRAL
        elif final_evaluator.final_eval < final_evaluator.SHORT_THRESHOLD - delta_risk:
            assert final_evaluator.state == EvaluatorStates.SHORT
        else:
            assert final_evaluator.state == EvaluatorStates.VERY_SHORT


async def test_prepare():
    final_evaluator, trader_inst = await _get_tools()
    await final_evaluator._set_state(EvaluatorStates.SHORT)
    assert final_evaluator.state == EvaluatorStates.SHORT
    assert len(trader_inst.order_manager.order_list) == 2  # has stop loss
    final_evaluator.final_eval = None
    final_evaluator.set_final_eval()
    assert final_evaluator.state == EvaluatorStates.SHORT  # ensure did not change EvaluatorStates
    assert len(trader_inst.order_manager.order_list) == 2  # ensure did not change orders
    assert final_evaluator.final_eval == INIT_EVAL_NOTE


async def test_finalize():
    final_evaluator, trader_inst = await _get_tools()
    final_evaluator.final_eval = None
    await final_evaluator.finalize()
    assert final_evaluator.final_eval == INIT_EVAL_NOTE

    await final_evaluator._set_state(EvaluatorStates.SHORT)
    assert final_evaluator.state == EvaluatorStates.SHORT
    assert len(trader_inst.order_manager.order_list) == 2  # has stop loss

    await final_evaluator.finalize()
    assert final_evaluator.final_eval == INIT_EVAL_NOTE
    assert final_evaluator.state == EvaluatorStates.NEUTRAL  # ensure changed EvaluatorStates
    assert len(trader_inst.order_manager.order_list) == 2  # ensure did not change orders because neutral state
