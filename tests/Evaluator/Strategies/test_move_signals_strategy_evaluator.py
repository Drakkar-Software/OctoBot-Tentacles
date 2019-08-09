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
from evaluator.Strategies import MoveSignalsStrategyEvaluator
from trading.trader.modes import SignalTradingMode


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


@pytest.fixture()
def strategy_tester():
    strategy_tester_instance = TestMoveSignalsStrategyEvaluator()
    strategy_tester_instance.initialize(MoveSignalsStrategyEvaluator, SignalTradingMode)
    return strategy_tester_instance


# can compare to test_full_mixed_strategies_evaluator: using same timeframes
# test_full_mixed_strategies_evaluator results: (full_mixed_strategies_evaluator profitability, market profitability)
class TestMoveSignalsStrategyEvaluator(AbstractStrategyTest):

    @staticmethod
    async def test_default_run(strategy_tester):
        # test_full_mixed_strategies_evaluator results: (-5.852441652658413, -13.325377883850436)
        await strategy_tester.run_test_default_run(-2.1)

    @staticmethod
    async def test_slow_downtrend(strategy_tester):
        # test_full_mixed_strategies_evaluator results: (-5.852441652658413, -13.325377883850436)
        # test_full_mixed_strategies_evaluator results: (-4.520148471540537, -13.737528779739065)
        # test_full_mixed_strategies_evaluator results: (-17.964934829680857, -29.04611614724287)
        # test_full_mixed_strategies_evaluator results: (-11.422677230943492, -28.89908256880733)
        await strategy_tester.run_test_slow_downtrend(-2.1, -3.8, -15.8, -7.7)

    @staticmethod
    async def test_sharp_downtrend(strategy_tester):
        # test_full_mixed_strategies_evaluator results: (-12.780472907249703, -20.281292481438868)
        # test_full_mixed_strategies_evaluator results: (-21.571523686884376, -31.28953771289538)
        await strategy_tester.run_test_sharp_downtrend(-7.8, -19)

    @staticmethod
    async def test_flat_markets(strategy_tester):
        # test_full_mixed_strategies_evaluator results: (-0.9097753768806598, -11.246861924686186)
        # test_full_mixed_strategies_evaluator results: (0.4784409359433255, -5.834160873882809)
        # test_full_mixed_strategies_evaluator results: (-8.888333459616902, -9.92366412213741)
        # test_full_mixed_strategies_evaluator results: (26.253241969042733, -4.723991507431009)
        await strategy_tester.run_test_flat_markets(-0.2, 1.9, -12.7, -2.9)

    @staticmethod
    async def test_slow_uptrend(strategy_tester):
        # test_full_mixed_strategies_evaluator results: (7.589434201486512, 14.688152888099395)
        # test_full_mixed_strategies_evaluator results: (-1.2987367913981132, 10.797424467558201)
        await strategy_tester.run_test_slow_uptrend(7.1, 6)

    @staticmethod
    async def test_sharp_uptrend(strategy_tester):
        # test_full_mixed_strategies_evaluator results: (3.808722550442397, 35.989104528430374)
        # test_full_mixed_strategies_evaluator results: (1.0465276590314687, 16.12679315131882)
        await strategy_tester.run_test_sharp_uptrend(15.8, 4.7)

    @staticmethod
    async def test_up_then_down(strategy_tester):
        # test_full_mixed_strategies_evaluator results: (-8.400359202205237, -9.085623368955268)
        await strategy_tester.run_test_up_then_down(-10.7)
