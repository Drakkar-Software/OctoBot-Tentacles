import pytest

from tests.functional_tests.strategy_evaluators_tests.abstract_strategy_test import AbstractStrategyTest
from evaluator.Strategies import MoveSignalsStrategyEvaluator
from trading.trader.modes import SignalTradingMode


@pytest.fixture()
def strategy_tester():
    strategy_tester_instance = TestMoveSignalsStrategyEvaluator()
    strategy_tester_instance.init(MoveSignalsStrategyEvaluator, SignalTradingMode)
    return strategy_tester_instance


class TestMoveSignalsStrategyEvaluator(AbstractStrategyTest):

    @staticmethod
    def test_default_run(strategy_tester):
        strategy_tester.run_test_default_run(-13)

    @staticmethod
    def test_slow_downtrend(strategy_tester):
        strategy_tester.run_test_slow_downtrend(-13, -5, -17.5, 0)

    @staticmethod
    def test_sharp_downtrend(strategy_tester):
        strategy_tester.run_test_sharp_downtrend(-12, -18)

    @staticmethod
    def test_flat_markets(strategy_tester):
        strategy_tester.run_test_flat_markets(-3, -0.5, -15, -6)

    @staticmethod
    def test_slow_uptrend(strategy_tester):
        strategy_tester.run_test_slow_uptrend(-4, 5)

    @staticmethod
    def test_sharp_uptrend(strategy_tester):
        strategy_tester.run_test_sharp_uptrend(20, 14)

    @staticmethod
    def test_up_then_down(strategy_tester):
        strategy_tester.run_test_up_then_down(-3.5)
