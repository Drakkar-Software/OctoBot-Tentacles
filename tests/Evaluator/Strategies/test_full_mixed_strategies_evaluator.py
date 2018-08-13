import pytest

from tests.functional_tests.strategy_evaluators_tests.abstract_strategy_test import AbstractStrategyTest
from evaluator.Strategies import FullMixedStrategiesEvaluator


@pytest.fixture()
def strategy_tester():
    strategy_tester_instance = TestFullMixedStrategiesEvaluator()
    strategy_tester_instance.init(FullMixedStrategiesEvaluator)
    return strategy_tester_instance


class TestFullMixedStrategiesEvaluator(AbstractStrategyTest):

    @staticmethod
    def test_default_run(strategy_tester):
        strategy_tester.run_test_default_run(-12)

    @staticmethod
    def test_slow_downtrend(strategy_tester):
        strategy_tester.run_test_slow_downtrend(-9.5, -10.5, -20.5, 0)

    @staticmethod
    def test_sharp_downtrend(strategy_tester):
        strategy_tester.run_test_sharp_downtrend(-14, -21.5)

    @staticmethod
    def test_flat_markets(strategy_tester):
        strategy_tester.run_test_flat_markets(-3.5, 0.5, 7, 26.5)

    @staticmethod
    def test_slow_uptrend(strategy_tester):
        strategy_tester.run_test_slow_uptrend(-5, -4)

    @staticmethod
    def test_sharp_uptrend(strategy_tester):
        strategy_tester.run_test_sharp_uptrend(10, 7.5)

    @staticmethod
    def test_up_then_down(strategy_tester):
        strategy_tester.run_test_up_then_down(-13)
