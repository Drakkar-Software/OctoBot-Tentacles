"""
OctoBot Tentacle

$tentacle_description: {
    "name": "hybrid_trading_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.0.0",
    "requirements": ["daily_trading_mode", "high_frequency_mode", "market_stability_strategy_evaluator"],
    "developing": true
}
"""
from tentacles.Evaluator.Strategies import MarketStabilityStrategiesEvaluator
from trading.trader.modes.abstract_mode_decider import AbstractTradingModeDecider
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode


class HybridTradingMode(AbstractTradingMode):
    def __init__(self, config, symbol_evaluator, exchange):
        super().__init__(config, symbol_evaluator, exchange)

        self.set_decider(HybridTradingModeDecider(self, symbol_evaluator, exchange))

    @staticmethod
    def get_required_strategies():
        return [MarketStabilityStrategiesEvaluator]


class HybridTradingModeDecider(AbstractTradingModeDecider):
    def __init__(self, trading_mode, symbol_evaluator, exchange):
        super().__init__(trading_mode, symbol_evaluator, exchange)

    def set_final_eval(self):
        pass

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True

    def create_state(self):
        pass
