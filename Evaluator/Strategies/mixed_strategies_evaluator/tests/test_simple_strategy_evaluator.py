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
        # market: -16.49081672528331
        await strategy_tester.run_test_default_run(-9.226)

    @staticmethod
    async def test_slow_downtrend(strategy_tester):
        # market: -16.49081672528331
        # market: -41.233602421796164
        # market: -35.744804567363204
        # market: -45.18518518518518
        await strategy_tester.run_test_slow_downtrend(-9.226, -23.416, -18.1, -17.823)

    @staticmethod
    async def test_sharp_downtrend(strategy_tester):
        # market: -26.70135121806885
        # market: -31.0071854828888
        await strategy_tester.run_test_sharp_downtrend(-12.874, -24.607)

    @staticmethod
    async def test_flat_markets(strategy_tester):
        # market: -2.3786121486140956
        # market: -0.7446808510638192
        # market: -16.381236038719294
        # market: -37.886792452830186
        await strategy_tester.run_test_flat_markets(-3.149, 2.805, -3.878, -28.663)

    @staticmethod
    async def test_slow_uptrend(strategy_tester):
        # market: 31.954350927246793
        # market: 1.947463768115938
        await strategy_tester.run_test_slow_uptrend(4.33, 7.041)

    @staticmethod
    async def test_sharp_uptrend(strategy_tester):
        # market: 27.478937135450423
        # market: 9.919390953873702
        await strategy_tester.run_test_sharp_uptrend(10.929, 7.398)

    @staticmethod
    async def test_up_then_down(strategy_tester):
        # market: -3.124408623542479
        await strategy_tester.run_test_up_then_down(2.314)
