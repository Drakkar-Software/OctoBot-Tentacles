"""
OctoBot Tentacle

$tentacle_description: {
    "name": "high_frequency_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.0.0",
    "requirements": [market_stability_strategy_evaluator]
}
"""
from config.cst import INIT_EVAL_NOTE, EvaluatorStates
from tentacles.Evaluator.Strategies import MarketStabilityStrategiesEvaluator
from tools.evaluators_util import check_valid_eval_note
from trading.trader.modes.abstract_mode_creator import AbstractTradingModeCreator
from trading.trader.modes.abstract_mode_decider import AbstractTradingModeDecider
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode
from trading.trader.sub_portfolio import SubPortfolio


class HighFrequencyMode(AbstractTradingMode):
    TEMP_CREATOR_TO_USE = 5  # TODO temp cst

    def __init__(self, config, symbol_evaluator, exchange):
        super().__init__(config, symbol_evaluator, exchange)

        self.set_decider(HighFrequencyModeDecider(self, symbol_evaluator, exchange))

        # create new creators
        for _ in range(0, self.TEMP_CREATOR_TO_USE):
            self.add_creator(HighFrequencyModeCreator(self))

    @staticmethod
    def get_required_strategies():
        return [MarketStabilityStrategiesEvaluator]


class HighFrequencyModeCreator(AbstractTradingModeCreator):
    def __init__(self, trading_mode):
        super().__init__(trading_mode)
        self.sub_portfolio = None

    def get_sub_portfolio(self, trader, portfolio):
        if not self.sub_portfolio:
            self.sub_portfolio = SubPortfolio(self.trading_mode.config,
                                              trader,
                                              portfolio,
                                              1 / self.trading_mode.TEMP_CREATOR_TO_USE,
                                              is_relative=True)
        return self.sub_portfolio

    def create_new_order(self, eval_note, symbol, exchange, trader, portfolio, state):
        self.get_sub_portfolio(trader, portfolio)

        return None


class HighFrequencyModeDecider(AbstractTradingModeDecider):
    def __init__(self, trading_mode, symbol_evaluator, exchange):
        super().__init__(trading_mode, symbol_evaluator, exchange)

    def set_final_eval(self):
        # TODO : check changing mode

        strategies_analysis_note_counter = 0
        # Strategies analysis
        for evaluated_strategies in self.symbol_evaluator.get_strategies_eval_list(self.exchange):
            strategy_eval = evaluated_strategies.get_eval_note()
            if check_valid_eval_note(strategy_eval):
                self.final_eval += strategy_eval * evaluated_strategies.get_pertinence()
                strategies_analysis_note_counter += evaluated_strategies.get_pertinence()

        if strategies_analysis_note_counter > 0:
            self.final_eval /= strategies_analysis_note_counter
        else:
            self.final_eval = INIT_EVAL_NOTE

        self.create_state()

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True

    def create_state(self):
        # TODO : temp
        for creator in self.trading_mode.get_creators().values():
            trader = self.symbol_evaluator.get_trader_simulator(self.exchange)
            with trader.get_portfolio() as pf:
                creator.create_new_order(self.final_eval,
                                         self.symbol,
                                         self.exchange,
                                         trader,
                                         pf,
                                         EvaluatorStates.SHORT)
