"""
OctoBot Tentacle

$tentacle_description: {
    "name": "high_frequency_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.0.0",
    "requirements": ["high_frequency_strategy_evaluator"]
}
"""
from config.cst import EvaluatorStates, TraderOrderType
from tentacles.Evaluator.Strategies.Default.high_frequency_strategy_evaluator import HighFrequencyStrategiesEvaluator
from tools.evaluators_util import check_valid_eval_note
from tools.symbol_util import split_symbol
from trading.trader.modes.abstract_mode_creator import AbstractTradingModeCreator
from trading.trader.modes.abstract_mode_decider import AbstractTradingModeDecider
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode
from trading.trader.sub_portfolio import SubPortfolio


class HighFrequencyMode(AbstractTradingMode):
    TEMP_CREATOR_TO_USE = 5  # TODO temp cst

    def __init__(self, config, symbol_evaluator, exchange):
        super().__init__(config, symbol_evaluator, exchange)

        trader_simulator = symbol_evaluator.get_trader_simulator(exchange)
        trader = symbol_evaluator.get_trader(exchange)

        if trader_simulator.is_enabled():
            simulated_creators = []
            # create new creators --> simulation
            for _ in range(0, self.TEMP_CREATOR_TO_USE):
                simulated_creators.append(self.add_creator(HighFrequencyModeCreator(self, trader_simulator)))

            self.add_decider(
                HighFrequencyModeDecider(self, symbol_evaluator, exchange, trader_simulator, simulated_creators))

        if trader.is_enabled():
            real_creators = []
            # create new creators --> real
            for _ in range(0, self.TEMP_CREATOR_TO_USE):
                real_creators.append(self.add_creator(HighFrequencyModeCreator(self, trader)))

            self.add_decider(HighFrequencyModeDecider(self, symbol_evaluator, exchange, trader, real_creators))

    @staticmethod
    def get_required_strategies():
        return [HighFrequencyStrategiesEvaluator]


class HighFrequencyModeCreator(AbstractTradingModeCreator):
    def __init__(self, trading_mode, trader):
        super().__init__(trading_mode)
        self.trader = trader
        self.parent_portfolio = self.trader.get_portfolio()
        self.sub_portfolio = SubPortfolio(self.trading_mode.config,
                                          self.trader,
                                          self.parent_portfolio,
                                          1 / self.trading_mode.TEMP_CREATOR_TO_USE,
                                          is_relative=True)

    def get_portfolio(self):
        # force portfolio update
        self.sub_portfolio.update_from_parent()
        return self.sub_portfolio

    def can_create_order(self, symbol, exchange, state, portfolio):
        return super().can_create_order(symbol, exchange, state, self.get_portfolio())

    def create_new_order(self, eval_note, symbol, exchange, trader, _, state):
        sub_portfolio = self.get_portfolio()

        current_symbol_holding, current_market_quantity, market_quantity, price, symbol_market = \
            self.get_pre_order_data(exchange, symbol, sub_portfolio)

        created_orders = []

        if state == EvaluatorStates.VERY_SHORT:
            for order_quantity, order_price in self.check_and_adapt_order_details_if_necessary(current_symbol_holding,
                                                                                               price,
                                                                                               symbol_market):
                market = trader.create_order_instance(order_type=TraderOrderType.SELL_MARKET,
                                                      symbol=symbol,
                                                      current_price=order_price,
                                                      quantity=order_quantity,
                                                      price=order_price)
                trader.create_order(market, sub_portfolio)
                created_orders.append(market)
            return created_orders

        elif state == EvaluatorStates.VERY_LONG:
            for order_quantity, order_price in self.check_and_adapt_order_details_if_necessary(market_quantity, price,
                                                                                               symbol_market):
                market = trader.create_order_instance(order_type=TraderOrderType.BUY_MARKET,
                                                      symbol=symbol,
                                                      current_price=order_price,
                                                      quantity=order_quantity,
                                                      price=order_price)
                trader.create_order(market, sub_portfolio)
                created_orders.append(market)
            return created_orders

        return None


class HighFrequencyModeDecider(AbstractTradingModeDecider):
    LONG_THRESHOLD = -1
    SHORT_THRESHOLD = 1

    def __init__(self, trading_mode, symbol_evaluator, exchange, trader, creators):
        super().__init__(trading_mode, symbol_evaluator, exchange)
        self.trader = trader
        self.creators = creators
        self.available_creators = []
        self.pending_creators = []

    def set_final_eval(self):
        evaluated_strategies = self.symbol_evaluator.get_strategies_eval_list(self.exchange)
        for strategy in evaluated_strategies:
            if strategy.get_name() == HighFrequencyStrategiesEvaluator.get_name():
                strategy_eval = strategy.get_eval_note()
                if check_valid_eval_note(strategy_eval):
                    self.final_eval = strategy_eval

                self._update_available_creators()
                self.create_state()
                break

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True

    # TODO add risk
    # TODO add available creator management
    def create_state(self):
        if self.final_eval <= self.LONG_THRESHOLD:
            self._set_state(EvaluatorStates.VERY_LONG)

        if self.final_eval >= self.SHORT_THRESHOLD:
            self._set_state(EvaluatorStates.VERY_SHORT)

    def _set_state(self, new_state):
        if new_state != self.state:
            # previous_state = self.state
            self.state = new_state
            self.logger.info("{0} ** NEW STATE ** : {1}".format(self.symbol, self.state))

            if self.state == EvaluatorStates.VERY_SHORT:
                for creator_key in self.pending_creators:
                    self.create_order_if_possible(None, self.trader, creator_key)

            elif self.state == EvaluatorStates.VERY_LONG:
                order_creator_key = next(iter(self.available_creators))
                self.create_order_if_possible(None, self.trader, order_creator_key)

    def _update_available_creators(self):
        for order_creator_key in self.creators:
            order_creator = self.trading_mode.get_creators()[order_creator_key]

            # force portfolio update
            order_creator_pf = order_creator.get_portfolio()
            currency, market = split_symbol(self.symbol)

            currency_pf = order_creator_pf.get_currency_portfolio(currency)
            market_pf = order_creator_pf.get_currency_portfolio(market)

            # TODO : more comparison ( >= 0)
            if market_pf > currency_pf:
                self.available_creators.append(order_creator_key)
            # market < currency
            else:
                self.pending_creators.append(order_creator_key)
