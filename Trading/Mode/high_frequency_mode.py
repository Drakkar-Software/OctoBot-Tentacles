"""
OctoBot Tentacle

$tentacle_description: {
    "name": "high_frequency_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.0.0",
    "requirements": ["high_frequency_strategy_evaluator"],
    "config_files": ["HighFrequencyMode.json"],
    "developing": true
}
"""
from config import EvaluatorStates, TraderOrderType, CURRENCY_DEFAULT_MAX_PRICE_DIGITS, PriceIndexes
from config import ExchangeConstantsMarketStatusColumns as Ecmsc
from tentacles.Evaluator.Strategies import HighFrequencyStrategiesEvaluator
from tools.evaluators_util import check_valid_eval_note
from tools.symbol_util import split_symbol
from trading.trader.modes.abstract_mode_creator import AbstractTradingModeCreatorWithBot
from trading.trader.modes.abstract_mode_decider import AbstractTradingModeDeciderWithBot
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode


class HighFrequencyMode(AbstractTradingMode):

    def __init__(self, config, exchange):
        super().__init__(config, exchange)
        self.nb_creators = 0
        self.simulated_creators = {}
        self.real_creators = {}

    def create_deciders(self, symbol, symbol_evaluator):
        trader_simulator = symbol_evaluator.get_trader_simulator(self.exchange)
        trader = symbol_evaluator.get_trader(self.exchange)

        if trader_simulator.is_enabled():
            self.add_decider(symbol,
                             HighFrequencyModeDecider(self,
                                                      symbol_evaluator,
                                                      self.exchange,
                                                      trader_simulator,
                                                      self.simulated_creators[symbol]))
        if trader.is_enabled():
            self.add_decider(symbol, HighFrequencyModeDecider(self,
                                                              symbol_evaluator,
                                                              self.exchange,
                                                              trader,
                                                              self.real_creators[symbol]))

    def create_creators(self, symbol, symbol_evaluator):
        trader_simulator = symbol_evaluator.get_trader_simulator(self.exchange)
        trader = symbol_evaluator.get_trader(self.exchange)

        self.init_nb_creator_from_exchange(symbol, self.exchange)

        if trader_simulator.is_enabled():
            self.simulated_creators[symbol] = []
            # create new creators --> simulation
            for _ in range(0, self.nb_creators):
                self.simulated_creators[symbol].append(
                    self.add_creator(symbol, HighFrequencyModeCreator(self, trader_simulator)))

        if trader.is_enabled():
            self.real_creators[symbol] = []
            # create new creators --> real
            for _ in range(0, self.nb_creators):
                self.real_creators[symbol].append(self.add_creator(symbol, HighFrequencyModeCreator(self, trader)))

    def init_nb_creator_from_exchange(self, symbol, exchange):
        # low fees => can have a lot of creators (more trades)
        # high fees => less creators (decider will also need a bigger price move to trigger a trade)

        exchange_fees = max(exchange.get_fees(symbol))
        max_creators = (5, 0.001)  # fees <= 0.1% (0.001)
        min_creators = (2, 0.01)  # fees >= 1% (0.01)

        if exchange_fees <= max_creators[1]:
            self.nb_creators = max_creators[0]
        elif exchange_fees >= min_creators[1]:
            self.nb_creators = min_creators[0]
        else:
            if exchange_fees <= min_creators[1] / 2:
                self.nb_creators = 4
            else:
                self.nb_creators = 3


class HighFrequencyModeCreator(AbstractTradingModeCreatorWithBot):
    def __init__(self, trading_mode, trader):
        super().__init__(trading_mode, trader, 1 / trading_mode.nb_creators)
        self._market_value = None

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
                                                      price=order_price,
                                                      linked_portfolio=sub_portfolio)
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
                                                      price=order_price,
                                                      linked_portfolio=sub_portfolio)
                trader.create_order(market, sub_portfolio)
                created_orders.append(market)
            return created_orders

        return None

    def set_market_value(self, market_value):
        self._market_value = market_value

    def get_market_value(self):
        return self._market_value


class HighFrequencyModeDecider(AbstractTradingModeDeciderWithBot):

    def __init__(self, trading_mode, symbol_evaluator, exchange, trader, creators):
        super().__init__(trading_mode, symbol_evaluator, exchange, trader, creators)
        exchange_fees = max(exchange.get_fees(self.symbol))
        self.LONG_THRESHOLD = -2 * exchange_fees
        self.SHORT_THRESHOLD = 2 * exchange_fees
        self.filled_creators = []
        self.pending_creators = []
        self.blocked_creators = []

        self.currency, self.market = split_symbol(self.symbol)
        market_status = exchange.get_market_status(self.symbol)
        self.currency_max_digits = HighFrequencyModeCreator.get_value_or_default(market_status[Ecmsc.PRECISION.value],
                                                                                 Ecmsc.PRECISION_PRICE.value,
                                                                                 CURRENCY_DEFAULT_MAX_PRICE_DIGITS)
        limit_cost = market_status[Ecmsc.LIMITS.value][Ecmsc.LIMITS_COST.value]
        self.currency_min_cost = HighFrequencyModeCreator.get_value_or_default(limit_cost, Ecmsc.LIMITS_COST_MIN.value)
        self._update_available_creators()

    def set_final_eval(self):
        strategy = self.trading_mode.get_strategy_instances_by_classes(self.symbol)[HighFrequencyStrategiesEvaluator]
        strategy_eval = strategy.get_eval_note()

        if check_valid_eval_note(strategy_eval):
            self.final_eval = strategy_eval

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True

    def get_required_difference_from_risk(self):
        # low risk => harder trigger a new bot => need bigger change
        nb_blocked_creators = len(self.blocked_creators)
        # always the same for 0 blocked creator
        if nb_blocked_creators == 0:
            return 1
        else:
            # return between sqrt(x) (pow(0.5)) (for risk=1) and x*sqrt(x) (pow(1.5)) (for risk=0)
            # difference according to risk
            power = 1.5 - (self.trader.get_risk())
            return pow(nb_blocked_creators + 1, power)

    def create_state(self):
        if self.final_eval > self.SHORT_THRESHOLD:
            self._set_state(EvaluatorStates.VERY_SHORT)

        elif self.final_eval < self.LONG_THRESHOLD * self.get_required_difference_from_risk():
            self._set_state(EvaluatorStates.VERY_LONG)

        self._update_available_creators()

    def _creator_can_sell(self, creator_key, current_price):
        creator = self.trading_mode.get_creator(self.symbol, creator_key)
        current_sell_value = current_price * creator.get_portfolio().get_currency_portfolio(self.currency)
        value_when_bought = creator.get_market_value()
        if current_sell_value and value_when_bought:
            return current_sell_value / value_when_bought >= self.SHORT_THRESHOLD * 2
        else:
            return False

    def _register_creator_market_value(self, creator_key):
        creator = self.trading_mode.get_creator(self.symbol, creator_key)
        creator.set_market_value(creator.get_portfolio().get_currency_portfolio(self.market))

    def _set_state(self, new_state):
        self.state = new_state
        self.logger.info("{0} ** NEW STATE ** : {1}".format(self.symbol, self.state))
        current_price = self.exchange.get_symbol_prices(self.symbol, None, limit=None, return_list=True) \
            [PriceIndexes.IND_PRICE_CLOSE.value][-1]

        if self.state == EvaluatorStates.VERY_SHORT:
            for creator_key in self.filled_creators:
                if self._creator_can_sell(creator_key, current_price):
                    self.create_order_if_possible(None, self.get_trader(), creator_key)

        elif self.state == EvaluatorStates.VERY_LONG and len(self.pending_creators) > 0:
            order_creator_key = next(iter(self.pending_creators))
            self._register_creator_market_value(order_creator_key)
            self.create_order_if_possible(None, self.get_trader(), order_creator_key)

    def _update_available_creators(self):
        for order_creator_key in self.get_creators():
            order_creator = self.trading_mode.get_creators(self.symbol)[order_creator_key]

            # force portfolio update
            order_creator_pf = order_creator.get_portfolio()
            currency, market = split_symbol(self.symbol)

            currency_pf = order_creator_pf.get_currency_portfolio(currency)
            market_pf = order_creator_pf.get_currency_portfolio(market)

            if round(currency_pf, self.currency_max_digits) > self.currency_min_cost:
                if order_creator_key not in self.filled_creators:
                    self.filled_creators.append(order_creator_key)
            elif order_creator_key in self.filled_creators:
                self.filled_creators.remove(order_creator_key)

            if round(market_pf, self.currency_max_digits) >= self.currency_min_cost:
                if order_creator_key not in self.pending_creators:
                    self.pending_creators.append(order_creator_key)
            elif order_creator_key in self.pending_creators:
                self.pending_creators.remove(order_creator_key)

            if round(market_pf, self.currency_max_digits) < self.currency_min_cost and \
                    round(currency_pf, self.currency_max_digits) > 0:
                if order_creator_key not in self.blocked_creators:
                    self.blocked_creators.append(order_creator_key)
            elif order_creator_key in self.blocked_creators:
                self.blocked_creators.remove(order_creator_key)
