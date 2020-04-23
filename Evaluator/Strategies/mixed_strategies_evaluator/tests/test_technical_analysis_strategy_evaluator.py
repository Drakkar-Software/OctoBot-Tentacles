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

from tests.functional_tests.strategy_evaluators_tests.abstract_strategy_test import AbstractStrategyTest
from tentacles.Evaluator.Strategies import TechnicalAnalysisStrategyEvaluator
from tentacles.Trading.Mode import DailyTradingMode


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


@pytest.fixture()
def strategy_tester():
    strategy_tester_instance = _TestTechnicalAnalysisStrategyEvaluator()
    strategy_tester_instance.initialize(TechnicalAnalysisStrategyEvaluator, DailyTradingMode)
    return strategy_tester_instance


# TODO rename this test into TestTechnicalAnalysisStrategyEvaluator to include it in pytest tests list when
# backtesting randomness is fixed (will require tested values fixes)
class _TestTechnicalAnalysisStrategyEvaluator(AbstractStrategyTest):

    @staticmethod
    async def test_default_run(strategy_tester):
        # market: -13.325377883850436
        await strategy_tester.run_test_default_run(-6)

    @staticmethod
    async def test_slow_downtrend(strategy_tester):
        # market: -13.325377883850436
        # market: -13.737528779739065
        # market: -29.04611614724287
        # market: -28.89908256880733
        await strategy_tester.run_test_slow_downtrend(-6, -4.6, -18, -11.5)

    @staticmethod
    async def test_sharp_downtrend(strategy_tester):
        # market: -20.281292481438868
        # market: -31.28953771289538
        await strategy_tester.run_test_sharp_downtrend(-12.9, -21.7)

    @staticmethod
    async def test_flat_markets(strategy_tester):
        # market: -11.246861924686186
        # market: -5.834160873882809
        # market: -9.92366412213741
        # market: -4.723991507431009
        await strategy_tester.run_test_flat_markets(-1, 0.4, -9, 26.1)

    @staticmethod
    async def test_slow_uptrend(strategy_tester):
        # market: 14.688152888099395
        # market: 10.797424467558201
        await strategy_tester.run_test_slow_uptrend(7.5, -1.4)

    @staticmethod
    async def test_sharp_uptrend(strategy_tester):
        # market: 35.989104528430374
        # market: 16.12679315131882
        await strategy_tester.run_test_sharp_uptrend(3.7, 0.9)

    @staticmethod
    async def test_up_then_down(strategy_tester):
        # market: -9.085623368955268
        await strategy_tester.run_test_up_then_down(-8.5)
