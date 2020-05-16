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
    strategy_tester_instance = TechnicalAnalysisStrategyEvaluatorTest()
    strategy_tester_instance.initialize(TechnicalAnalysisStrategyEvaluator, DailyTradingMode)
    return strategy_tester_instance


class TechnicalAnalysisStrategyEvaluatorTest(AbstractStrategyTest):
    """
    About using this test framework:
    To be called by pytest, tests have to be called manually since the cythonized version of AbstractStrategyTest
    creates an __init__() which prevents the default pytest tests collect process
    """

    async def test_default_run(self):
        # market: -12.643224022125636
        await self.run_test_default_run(-5.988)

    async def test_slow_downtrend(self):
        # market: -12.643224022125636
        # market: -16.39871382636656
        # market: -28.59375
        # market: -31.162790697674424
        await self.run_test_slow_downtrend(-5.988, -4.464, -10.424, -8.468)

    async def test_sharp_downtrend(self):
        # market: -26.019620667102686
        # market: -31.958511287370357
        await self.run_test_sharp_downtrend(-15.781, -20.087)

    async def test_flat_markets(self):
        # market: -10.814419225634182
        # market: -3.2570860268523063
        # market: -5.367231638418076
        # market: -7.921318447634235
        await self.run_test_flat_markets(-2.022, 1.591, -6.829, -0.749)

    async def test_slow_uptrend(self):
        # market: 16.65469559146318
        # market: 16.31135349529005
        await self.run_test_slow_uptrend(4.128, 12.568)

    async def test_sharp_uptrend(self):
        # market: 30.659415363698173
        # market: 11.435132032146939
        await self.run_test_sharp_uptrend(11.552, 10.307)

    async def test_up_then_down(self):
        # market: -6.684034772021235
        await self.run_test_up_then_down(-2.285)


async def test_default_run(strategy_tester):
    await strategy_tester.test_default_run()


async def test_slow_downtrend(strategy_tester):
    await strategy_tester.test_slow_downtrend()


async def test_sharp_downtrend(strategy_tester):
    await strategy_tester.test_sharp_downtrend()


async def test_flat_markets(strategy_tester):
    await strategy_tester.test_flat_markets()


async def test_slow_uptrend(strategy_tester):
    await strategy_tester.test_slow_uptrend()


async def test_sharp_uptrend(strategy_tester):
    await strategy_tester.test_sharp_uptrend()


async def test_up_then_down(strategy_tester):
    await strategy_tester.test_up_then_down()
