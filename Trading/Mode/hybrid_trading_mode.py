"""
OctoBot Tentacle

$tentacle_description: {
    "name": "hybrid_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.0.0",
    "requirements": ["market_stability_strategy_evaluator"]
}
"""
from tentacles.Evaluator.Strategies import MarketStabilityStrategiesEvaluator
from trading.trader.modes.abstract_mode_decider import AbstractTradingModeDecider
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode


class HybridMode(AbstractTradingMode):
    def __init__(self, config, symbol_evaluator, exchange):
        super().__init__(config, symbol_evaluator, exchange)

        self.set_decider(HybridModeDecider(self, symbol_evaluator, exchange))

    @staticmethod
    def get_required_strategies():
        return [MarketStabilityStrategiesEvaluator]


class HybridModeDecider(AbstractTradingModeDecider):
    def __init__(self, trading_mode, symbol_evaluator, exchange):
        super().__init__(trading_mode, symbol_evaluator, exchange)

    def set_final_eval(self):
        pass

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True

    def create_state(self):
        pass
