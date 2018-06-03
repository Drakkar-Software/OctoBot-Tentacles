"""
OctoBot Tentacle

$tentacle_description: {
    "name": "opportunity_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.0.0",
    "requirements": []
}
"""
from trading.trader.modes.abstract_mode_creator import AbstractTradingModeCreator
from trading.trader.modes.abstract_mode_decider import AbstractTradingModeDecider
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode


class OpportunityMode(AbstractTradingMode):
    def __init__(self, config, symbol_evaluator, exchange, symbol):
        super().__init__(config)

        self.set_creator(OpportunityModeCreator(self))
        self.set_decider(OpportunityModeDecider(self, symbol_evaluator, exchange, symbol))


class OpportunityModeCreator(AbstractTradingModeCreator):
    def __init__(self, trading_mode):
        super().__init__(trading_mode)


class OpportunityModeDecider(AbstractTradingModeDecider):
    def __init__(self, trading_mode, symbol_evaluator, exchange, symbol):
        super().__init__(trading_mode, symbol_evaluator, exchange, symbol)