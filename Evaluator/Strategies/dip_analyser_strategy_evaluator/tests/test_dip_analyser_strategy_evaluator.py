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
import pytest

from tests.functional_tests.strategy_evaluators_tests.abstract_strategy_test import AbstractStrategyTest
from tentacles.Evaluator.Strategies import DipAnalyserStrategyEvaluator
from tentacles.Trading.Mode import DipAnalyserTradingMode


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


@pytest.fixture()
def strategy_tester():
    strategy_tester_instance = TestDipAnalyserStrategiesEvaluator()
    strategy_tester_instance.initialize(DipAnalyserStrategyEvaluator, DipAnalyserTradingMode)
    return strategy_tester_instance


class TestDipAnalyserStrategiesEvaluator(AbstractStrategyTest):

    # Careful with results here, unlike other strategy tests, this one uses only the 4h timeframe, therefore results
    # are not comparable with regular 1h timeframes strategy tests

    # Cannot use bittrex data since they are not providing 4h timeframe data

    # test_full_mixed_strategies_evaluator.py with only 4h timeframe results are provided for comparison:
    # format: results: (bot profitability, market average profitability)

    @staticmethod
    async def test_default_run(strategy_tester):
        # market: -49.25407390406244
        await strategy_tester.run_test_default_run(-25.441)

    @staticmethod
    async def test_slow_downtrend(strategy_tester):
        # market: -49.25407390406244
        # market: -47.50593824228029
        await strategy_tester.run_test_slow_downtrend(-25.441, -30.202, None, None, skip_extended=True)

    @staticmethod
    async def test_sharp_downtrend(strategy_tester):
        # market: -34.67997135795625
        await strategy_tester.run_test_sharp_downtrend(-23.61, None, skip_extended=True)

    @staticmethod
    async def test_flat_markets(strategy_tester):
        # market: -38.07647740440325
        # market: -53.87077652637819
        await strategy_tester.run_test_flat_markets(-20.69, -30.363, None, None, skip_extended=True)

    @staticmethod
    async def test_slow_uptrend(strategy_tester):
        # market: 11.32644122514472
        # market: -36.64596273291926
        await strategy_tester.run_test_slow_uptrend(6.673, -12.312)

    @staticmethod
    async def test_sharp_uptrend(strategy_tester):
        # market: -17.004747518342683
        # market: -18.25837965302341
        await strategy_tester.run_test_sharp_uptrend(3.83, 11.743)

    @staticmethod
    async def test_up_then_down(strategy_tester):
        await strategy_tester.run_test_up_then_down(None, skip_extended=True)
