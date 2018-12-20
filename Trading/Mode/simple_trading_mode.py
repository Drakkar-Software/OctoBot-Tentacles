"""
OctoBot Tentacle

$tentacle_description: {
    "name": "simple_trading_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.0.0",
    "requirements": ["mixed_strategies_evaluator"],
    "config_files": ["SimpleTradingMode.json"],
    "tests":[],
    "developing": true
}
"""

#  Drakkar-Software OctoBot
#  Copyright (c) Drakkar-Software, All rights reserved.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.

from tools.logging.logging_util import get_logger

from config import EvaluatorStates, INIT_EVAL_NOTE, TraderOrderType
from tools.evaluators_util import check_valid_eval_note
from trading.trader.modes.abstract_mode_creator import AbstractTradingModeCreator
from trading.trader.modes.abstract_mode_decider import AbstractTradingModeDecider
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode


class SimpleTradingMode(AbstractTradingMode):
    DESCRIPTION = "SimpleTradingMode is basic trading mode, it can buy and sell with market orders."

    def __init__(self, config, exchange):
        super().__init__(config, exchange)

    def create_deciders(self, symbol, symbol_evaluator):
        self.add_decider(symbol, SimpleTradingModeDecider(self, symbol_evaluator, self.exchange))

    def create_creators(self, symbol, symbol_evaluator):
        self.add_creator(symbol, SimpleTradingModeCreator(self))


class SimpleTradingModeCreator(AbstractTradingModeCreator):
    def __init__(self, trading_mode):
        super().__init__(trading_mode)

    # creates a new order
    def create_new_order(self, eval_note, symbol, exchange, trader, portfolio, state):
        try:
            current_symbol_holding, current_market_quantity, market_quantity, price, symbol_market = \
                self.get_pre_order_data(exchange, symbol, portfolio)

            created_orders = []

            if state in [EvaluatorStates.SHORT, EvaluatorStates.VERY_SHORT]:
                # buy quantity from risk
                quantity = current_symbol_holding * trader.get_risk()

                quantity += self.get_additional_dusts_to_quantity_if_necessary(quantity, price,
                                                                               symbol_market, current_symbol_holding)
                for order_quantity, order_price in self.check_and_adapt_order_details_if_necessary(quantity, price,
                                                                                                   symbol_market):
                    market = trader.create_order_instance(order_type=TraderOrderType.SELL_MARKET,
                                                          symbol=symbol,
                                                          current_price=order_price,
                                                          quantity=order_quantity,
                                                          price=order_price)
                    trader.create_order(market, portfolio)
                    created_orders.append(market)
                return created_orders

            elif state in [EvaluatorStates.LONG, EvaluatorStates.VERY_LONG]:
                # buy quantity from risk
                quantity = current_market_quantity * trader.get_risk()

                for order_quantity, order_price in self.check_and_adapt_order_details_if_necessary(quantity, price,
                                                                                                   symbol_market):
                    market = trader.create_order_instance(order_type=TraderOrderType.BUY_MARKET,
                                                          symbol=symbol,
                                                          current_price=order_price,
                                                          quantity=order_quantity,
                                                          price=order_price)
                    trader.create_order(market, portfolio)
                    created_orders.append(market)
                return created_orders

            # if nothing go returned, return None
            return None

        except Exception as e:
            logger = get_logger(self.__class__.__name__)
            logger.error(f"Failed to create order : {e}")
            logger.exception(e)
            return None


class SimpleTradingModeDecider(AbstractTradingModeDecider):
    def __init__(self, trading_mode, symbol_evaluator, exchange):
        super().__init__(trading_mode, symbol_evaluator, exchange)

        # If final_eval not is < X_THRESHOLD --> state = X
        self.VERY_LONG_THRESHOLD = -0.85
        self.LONG_THRESHOLD = -0.25
        self.NEUTRAL_THRESHOLD = 0.25
        self.SHORT_THRESHOLD = 0.85

    def set_final_eval(self):
        strategies_counter = 0
        # Strategies analysis
        for evaluated_strategies in self.symbol_evaluator.get_strategies_eval_list(self.exchange):
            strategy_eval = evaluated_strategies.get_eval_note()
            if check_valid_eval_note(strategy_eval):
                self.final_eval += strategy_eval
                strategies_counter += 1

        if strategies_counter > 0:
            self.final_eval /= strategies_counter
        else:
            self.final_eval = INIT_EVAL_NOTE

    def create_state(self):
        if self.final_eval < self.VERY_LONG_THRESHOLD:
            self._set_state(EvaluatorStates.VERY_LONG)

        elif self.final_eval < self.LONG_THRESHOLD:
            self._set_state(EvaluatorStates.LONG)

        elif self.final_eval < self.NEUTRAL_THRESHOLD:
            self._set_state(EvaluatorStates.NEUTRAL)

        elif self.final_eval < self.SHORT_THRESHOLD:
            self._set_state(EvaluatorStates.SHORT)

        else:
            self._set_state(EvaluatorStates.VERY_SHORT)

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True

    def _set_state(self, new_state):
        if new_state != self.state:
            # previous_state = self.state
            self.state = new_state
            self.logger.info("{0} ** NEW FINAL STATE ** : {1}".format(self.symbol, self.state))

            # if new state is not neutral --> cancel orders and create new else keep orders
            if new_state is not EvaluatorStates.NEUTRAL:

                # cancel open orders
                self.cancel_symbol_open_orders()

                # create notification
                if self.symbol_evaluator.matrices:
                    self.notifier.notify_alert(
                        self.final_eval,
                        self.symbol_evaluator.get_crypto_currency_evaluator(),
                        self.symbol_evaluator.get_symbol(),
                        self.symbol_evaluator.get_trader(self.exchange),
                        self.state,
                        self.symbol_evaluator.get_matrix(self.exchange).get_matrix())

                # call orders creation method
                self.create_final_state_orders(self.notifier, self.trading_mode.get_only_creator_key(self.symbol))
