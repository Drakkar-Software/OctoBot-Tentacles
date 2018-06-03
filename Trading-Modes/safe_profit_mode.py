"""
OctoBot Tentacle

$tentacle_description: {
    "name": "safe_profit_mode",
    "type": "Trading-Modes",
    "subtype": "",
    "version": "1.0.0",
    "requirements": []
}
"""
from trading.trader.modes.abstract_mode_creator import AbstractTradingModeCreator
from trading.trader.modes.abstract_mode_decider import AbstractTradingModeDecider
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode


class SafeProfitMode(AbstractTradingMode):
    def __init__(self, config, symbol_evaluator, exchange, symbol):
        super().__init__(config)

        self.set_creator(SafeProfitModeCreator(self))
        self.set_decider(SafeProfitModeDecider(self, symbol_evaluator, exchange, symbol))


class SafeProfitModeCreator(AbstractTradingModeCreator):
    def __init__(self, trading_mode):
        super().__init__(trading_mode)


class SafeProfitModeDecider(AbstractTradingModeDecider):
    def __init__(self, trading_mode, symbol_evaluator, exchange, symbol):
        super().__init__(trading_mode, symbol_evaluator, exchange, symbol)