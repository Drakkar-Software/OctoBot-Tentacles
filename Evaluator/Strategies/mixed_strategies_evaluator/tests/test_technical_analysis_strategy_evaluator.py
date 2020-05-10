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
    strategy_tester_instance = TestTechnicalAnalysisStrategyEvaluator()
    strategy_tester_instance.initialize(TechnicalAnalysisStrategyEvaluator, DailyTradingMode)
    return strategy_tester_instance



class TestTechnicalAnalysisStrategyEvaluator(AbstractStrategyTest):

    @staticmethod
    async def test_default_run(strategy_tester):
        # market: -12.052505966587105
        await strategy_tester.run_test_default_run(-6.213)

    @staticmethod
    async def test_slow_downtrend(strategy_tester):
        # market: -12.052505966587105
        # market: -15.195702225633141
        # market: -29.12366137549725
        # market: -32.110091743119256
        await strategy_tester.run_test_slow_downtrend(-6.213, -4.773, -10.92, -5.737)

    @staticmethod
    async def test_sharp_downtrend(strategy_tester):
        # market: -26.07183938094741
        # market: -32.1654501216545
        await strategy_tester.run_test_sharp_downtrend(-15.471, -19.481)

    @staticmethod
    async def test_flat_markets(strategy_tester):
        # market: -10.560669456066947
        # market: -3.401191658391241
        # market: -5.7854560064282765
        # market: -8.067940552016978
        await strategy_tester.run_test_flat_markets(-1.538, 1.939, -7.731, 5.081)

    @staticmethod
    async def test_slow_uptrend(strategy_tester):
        # market: 17.203948364436457
        # market: 16.19613670133728
        await strategy_tester.run_test_slow_uptrend(4.707, 13.005)

    @staticmethod
    async def test_sharp_uptrend(strategy_tester):
        # market: 30.881852230166828
        # market: 12.28597871355852
        await strategy_tester.run_test_sharp_uptrend(13.97, 10.842)

    @staticmethod
    async def test_up_then_down(strategy_tester):
        # market: -6.040105108015155
        await strategy_tester.run_test_up_then_down(-3.998)
