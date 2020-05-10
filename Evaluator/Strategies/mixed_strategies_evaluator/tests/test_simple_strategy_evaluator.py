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
from tentacles.Evaluator.Strategies import SimpleStrategyEvaluator
from tentacles.Trading.Mode import DailyTradingMode


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


@pytest.fixture()
def strategy_tester():
    strategy_tester_instance = TestSimpleStrategyEvaluator()
    strategy_tester_instance.initialize(SimpleStrategyEvaluator, DailyTradingMode)
    return strategy_tester_instance


class TestSimpleStrategyEvaluator(AbstractStrategyTest):

    @staticmethod
    async def test_default_run(strategy_tester):
        # market: -13.599062133645944
        await strategy_tester.run_test_default_run(-7.466)

    @staticmethod
    async def test_slow_downtrend(strategy_tester):
        # market: -13.599062133645944
        # market: -44.248234106962656
        # market: -34.87003936300901
        # market: -45.18518518518518
        await strategy_tester.run_test_slow_downtrend(-7.466, -10.961, -21.457, -12.624)

    @staticmethod
    async def test_sharp_downtrend(strategy_tester):
        # market: -30.271723049610415
        # market: -32.091097308488614
        await strategy_tester.run_test_sharp_downtrend(-12.345, -20.457)

    @staticmethod
    async def test_flat_markets(strategy_tester):
        # market: 5.052093571849795
        # market: 3.4840425531915002
        # market: -12.732688011913623
        # market: -34.64150943396227
        await strategy_tester.run_test_flat_markets(-0.457, 8.824, -12.844, -17.463)

    @staticmethod
    async def test_slow_uptrend(strategy_tester):
        # market: 32.524679029957184
        # market: 6.25
        await strategy_tester.run_test_slow_uptrend(16.046, 5.561)

    @staticmethod
    async def test_sharp_uptrend(strategy_tester):
        # market: 24.56254050550875
        # market: 8.665472458575891
        await strategy_tester.run_test_sharp_uptrend(10.506, 1.895)

    @staticmethod
    async def test_up_then_down(strategy_tester):
        # market: 1.1543668450702853
        await strategy_tester.run_test_up_then_down(11.513)
