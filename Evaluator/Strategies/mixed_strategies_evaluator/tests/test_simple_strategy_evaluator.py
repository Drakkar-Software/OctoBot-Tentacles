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
    strategy_tester_instance = SimpleStrategyEvaluatorTest()
    strategy_tester_instance.initialize(SimpleStrategyEvaluator, DailyTradingMode)
    return strategy_tester_instance


class SimpleStrategyEvaluatorTest(AbstractStrategyTest):
    """
    About using this test framework:
    To be called by pytest, tests have to be called manually since the cythonized version of AbstractStrategyTest
    creates an __init__() which prevents the default pytest tests collect process
    """

    async def test_default_run(self):
        # market: -13.565285379202493
        await self.run_test_default_run(-3.363)

    async def test_slow_downtrend(self):
        # market: -13.565285379202493
        # market: -44.67392664914257
        # market: -34.9002849002849
        # market: -45.18518518518518
        await self.run_test_slow_downtrend(-3.363, -10.95, -16.132, -13.422)

    async def test_sharp_downtrend(self):
        # market: -29.03994780688548
        # market: -32.616314199395774
        await self.run_test_sharp_downtrend(-11.44, -21.133)

    async def test_flat_markets(self):
        # market: 5.445935280189417
        # market: 2.9365079365079225
        # market: -13.088616981831663
        # market: -33.91835177413202
        await self.run_test_flat_markets(-0.817, 9.289, -11.406, -19.348)

    async def test_slow_uptrend(self):
        # market: 32.14765291607395
        # market: 6.394557823129247
        await self.run_test_slow_uptrend(17.186, 2.159)

    async def test_sharp_uptrend(self):
        # market: 23.920051579626048
        # market: 6.94138386954603
        await self.run_test_sharp_uptrend(10.608, 3.86)

    async def test_up_then_down(self):
        # market: 1.2482029762598756
        await self.run_test_up_then_down(8.503)


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
