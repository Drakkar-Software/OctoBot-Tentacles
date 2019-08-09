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
from evaluator.Strategies import SimpleMixedStrategiesEvaluator
from trading.trader.modes import DailyTradingMode


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


@pytest.fixture()
def strategy_tester():
    strategy_tester_instance = TestSimpleMixedStrategiesEvaluator()
    strategy_tester_instance.initialize(SimpleMixedStrategiesEvaluator, DailyTradingMode)
    return strategy_tester_instance


class TestSimpleMixedStrategiesEvaluator(AbstractStrategyTest):

    @staticmethod
    async def test_default_run(strategy_tester):
        # market: -16.49081672528331
        await strategy_tester.run_test_default_run(-5.6)

    @staticmethod
    async def test_slow_downtrend(strategy_tester):
        # market: -16.49081672528331
        # market: -41.233602421796164
        # market: -35.744804567363204
        # market: -45.18518518518518
        await strategy_tester.run_test_slow_downtrend(-5.6, -29.6, -29.1, -17.4)

    @staticmethod
    async def test_sharp_downtrend(strategy_tester):
        # market: -26.70135121806885
        # market: -31.0071854828888
        await strategy_tester.run_test_sharp_downtrend(-21.7, -23.1)

    @staticmethod
    async def test_flat_markets(strategy_tester):
        # market: -2.3786121486140956
        # market: -0.7446808510638192
        # market: -16.381236038719294
        # market: -37.886792452830186
        await strategy_tester.run_test_flat_markets(5.4, 2.4, -1.7, 3.2)

    @staticmethod
    async def test_slow_uptrend(strategy_tester):
        # market: 31.954350927246793
        # market: 1.947463768115938
        await strategy_tester.run_test_slow_uptrend(10.9, 1.3)

    @staticmethod
    async def test_sharp_uptrend(strategy_tester):
        # market: 27.478937135450423
        # market: 9.919390953873702
        await strategy_tester.run_test_sharp_uptrend(9.1, 12.8)

    @staticmethod
    async def test_up_then_down(strategy_tester):
        # market: -3.124408623542479
        await strategy_tester.run_test_up_then_down(2.5)
