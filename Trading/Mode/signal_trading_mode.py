"""
OctoBot Tentacle

$tentacle_description: {
    "name": "signal_trading_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.0.0",
    "requirements": ["move_signals_strategy_evaluator", "daily_trading_mode"],
    "config_files": ["SignalTradingMode.json"]
}
"""
from tentacles.Trading.Mode.Default.daily_trading_mode import DailyTradingModeCreator
from tentacles.Trading.Mode.Default.daily_trading_mode import DailyTradingModeDecider
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode


class SignalTradingMode(AbstractTradingMode):
    DESCRIPTION = "SignalTradingMode is a low risk trading mode adapted to relatively flat markets. " \
                  "SignalTradingMode is using the daily trading mode orders system with adapted parameters. " \
                  "Warning: Works only on liquid markets."

    def __init__(self, config, exchange):
        super().__init__(config, exchange)

    def create_deciders(self, symbol, symbol_evaluator):
        self.add_decider(symbol, SignalTradingModeDecider(self, symbol_evaluator, self.exchange))

    def create_creators(self, symbol, symbol_evaluator):
        self.add_creator(symbol, SignalTradingModeCreator(self))


class SignalTradingModeCreator(DailyTradingModeCreator):
    def __init__(self, trading_mode):
        super().__init__(trading_mode)

        self.STOP_LOSS_ORDER_MAX_PERCENT = 0.99
        self.STOP_LOSS_ORDER_MIN_PERCENT = 0.95

        self.QUANTITY_MIN_PERCENT = 0.1
        self.QUANTITY_MAX_PERCENT = 0.9

        self.QUANTITY_MARKET_MIN_PERCENT = 0.5
        self.QUANTITY_MARKET_MAX_PERCENT = 1
        self.QUANTITY_BUY_MARKET_ATTENUATION = 0.2

        self.BUY_LIMIT_ORDER_MAX_PERCENT = 0.995
        self.BUY_LIMIT_ORDER_MIN_PERCENT = 0.99


class SignalTradingModeDecider(DailyTradingModeDecider):
    def __init__(self, trading_mode, symbol_evaluator, exchange):
        super().__init__(trading_mode, symbol_evaluator, exchange)

        # If final_eval not is < X_THRESHOLD --> state = X
        self.VERY_LONG_THRESHOLD = -0.88
        self.LONG_THRESHOLD = -0.4
        self.NEUTRAL_THRESHOLD = 0.4
        self.SHORT_THRESHOLD = 0.88
        self.RISK_THRESHOLD = 0.15
