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
from evaluator.Strategies import DipAnalyserStrategyEvaluator
from trading.trader.modes import DipAnalyserTradingMode


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
        # test_full_mixed_strategies_evaluator results: (-29.71931742129057, -48.381914161120044)
        await strategy_tester.run_test_default_run(-23)

    @staticmethod
    async def test_slow_downtrend(strategy_tester):
        # test_full_mixed_strategies_evaluator results: (-29.71931742129057, -48.381914161120044)
        # test_full_mixed_strategies_evaluator results: (-31.021874686419068, -38.2185273159145)
        await strategy_tester.run_test_slow_downtrend(-23, -24.5, None, None, skip_bittrex=True)

    @staticmethod
    async def test_sharp_downtrend(strategy_tester):
        # test_full_mixed_strategies_evaluator results: (-24.474138353712334, -20.423625066407965)
        await strategy_tester.run_test_sharp_downtrend(-11, None, skip_bittrex=True)

    @staticmethod
    async def test_flat_markets(strategy_tester):
        # test_full_mixed_strategies_evaluator results: (-26.58458438192001, -40.023174971031295)
        # test_full_mixed_strategies_evaluator results: (-36.9401141612163, -55.80320094842916)
        await strategy_tester.run_test_flat_markets(-26.5, -33.5, None, None, skip_bittrex=True)

    @staticmethod
    async def test_slow_uptrend(strategy_tester):
        # test_full_mixed_strategies_evaluator results: (-13.004510641884735, 6.022425915029842)
        # test_full_mixed_strategies_evaluator results: (-27.863018080882938, -34.78260869565217)
        await strategy_tester.run_test_slow_uptrend(6.5, -15.5)

    @staticmethod
    async def test_sharp_uptrend(strategy_tester):
        # test_full_mixed_strategies_evaluator results: (-6.701884818605208, -17.004747518342683)
        # test_full_mixed_strategies_evaluator results: (-21.017400517651993, -3.9076974903149875)
        await strategy_tester.run_test_sharp_uptrend(4, 14.5)

    @staticmethod
    async def test_up_then_down(strategy_tester):
        await strategy_tester.run_test_up_then_down(None, skip_bittrex=True)
