"""
OctoBot Tentacle

$tentacle_description: {
    "name": "daily_trading_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.0.0",
    "requirements": ["mixed_strategies_evaluator"],
    "config_files": ["DailyTradingMode.json"],
    "tests":["test_daily_trading_mode_creator", "test_daily_trading_mode_decider"]
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

from ccxt import InsufficientFunds

from tools.logging.logging_util import get_logger

from config import EvaluatorStates, INIT_EVAL_NOTE, TraderOrderType
from tools.evaluators_util import check_valid_eval_note
from trading.trader.modes.abstract_mode_creator import AbstractTradingModeCreator
from trading.trader.modes.abstract_mode_decider import AbstractTradingModeDecider
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode


class DailyTradingMode(AbstractTradingMode):

    DESCRIPTION = "DailyTradingMode is a low risk trading mode adapted to flat markets."

    def __init__(self, config, exchange):
        super().__init__(config, exchange)

    def create_deciders(self, symbol, symbol_evaluator):
        self.add_decider(symbol, DailyTradingModeDecider(self, symbol_evaluator, self.exchange))

    def create_creators(self, symbol, symbol_evaluator):
        self.add_creator(symbol, DailyTradingModeCreator(self))


class DailyTradingModeCreator(AbstractTradingModeCreator):
    def __init__(self, trading_mode):
        super().__init__(trading_mode)
        self.MAX_SUM_RESULT = 2

        self.STOP_LOSS_ORDER_MAX_PERCENT = 0.99
        self.STOP_LOSS_ORDER_MIN_PERCENT = 0.95
        self.STOP_LOSS_ORDER_ATTENUATION = (self.STOP_LOSS_ORDER_MAX_PERCENT - self.STOP_LOSS_ORDER_MIN_PERCENT)

        self.QUANTITY_MIN_PERCENT = 0.1
        self.QUANTITY_MAX_PERCENT = 0.9
        self.QUANTITY_ATTENUATION = (self.QUANTITY_MAX_PERCENT - self.QUANTITY_MIN_PERCENT) / self.MAX_SUM_RESULT

        self.QUANTITY_MARKET_MIN_PERCENT = 0.5
        self.QUANTITY_MARKET_MAX_PERCENT = 1
        self.QUANTITY_BUY_MARKET_ATTENUATION = 0.2
        self.QUANTITY_MARKET_ATTENUATION = (self.QUANTITY_MARKET_MAX_PERCENT - self.QUANTITY_MARKET_MIN_PERCENT) \
                                           / self.MAX_SUM_RESULT

        self.BUY_LIMIT_ORDER_MAX_PERCENT = 0.995
        self.BUY_LIMIT_ORDER_MIN_PERCENT = 0.98
        self.SELL_LIMIT_ORDER_MIN_PERCENT = 1 + (1 - self.BUY_LIMIT_ORDER_MAX_PERCENT)
        self.SELL_LIMIT_ORDER_MAX_PERCENT = 1 + (1 - self.BUY_LIMIT_ORDER_MIN_PERCENT)
        self.LIMIT_ORDER_ATTENUATION = (self.BUY_LIMIT_ORDER_MAX_PERCENT - self.BUY_LIMIT_ORDER_MIN_PERCENT) \
                                       / self.MAX_SUM_RESULT

    """
    Starting point : self.SELL_LIMIT_ORDER_MIN_PERCENT or self.BUY_LIMIT_ORDER_MAX_PERCENT
    1 - abs(eval_note) --> confirmation level --> high : sell less expensive / buy more expensive
    1 - trader.get_risk() --> high risk : sell / buy closer to the current price
    1 - abs(eval_note) + 1 - trader.get_risk() --> result between 0 and 2 --> self.MAX_SUM_RESULT
    self.QUANTITY_ATTENUATION --> try to contains the result between self.XXX_MIN_PERCENT and self.XXX_MAX_PERCENT
    """

    def _get_limit_price_from_risk(self, eval_note, trader):
        if eval_note > 0:
            factor = self.SELL_LIMIT_ORDER_MIN_PERCENT + \
                     ((1 - abs(eval_note) + 1 - trader.get_risk()) * self.LIMIT_ORDER_ATTENUATION)
            return self.check_factor(self.SELL_LIMIT_ORDER_MIN_PERCENT,
                                     self.SELL_LIMIT_ORDER_MAX_PERCENT,
                                     factor)
        else:
            factor = self.BUY_LIMIT_ORDER_MAX_PERCENT - \
                     ((1 - abs(eval_note) + 1 - trader.get_risk()) * self.LIMIT_ORDER_ATTENUATION)
            return self.check_factor(self.BUY_LIMIT_ORDER_MIN_PERCENT,
                                     self.BUY_LIMIT_ORDER_MAX_PERCENT,
                                     factor)

    """
    Starting point : self.STOP_LOSS_ORDER_MAX_PERCENT
    trader.get_risk() --> low risk : stop level close to the current price
    self.STOP_LOSS_ORDER_ATTENUATION --> try to contains the result between self.STOP_LOSS_ORDER_MIN_PERCENT and self.STOP_LOSS_ORDER_MAX_PERCENT
    """

    def _get_stop_price_from_risk(self, trader):
        factor = self.STOP_LOSS_ORDER_MAX_PERCENT - (trader.get_risk() * self.STOP_LOSS_ORDER_ATTENUATION)
        return self.check_factor(self.STOP_LOSS_ORDER_MIN_PERCENT,
                                 self.STOP_LOSS_ORDER_MAX_PERCENT,
                                 factor)

    """
    Starting point : self.QUANTITY_MIN_PERCENT
    abs(eval_note) --> confirmation level --> high : sell/buy more quantity
    trader.get_risk() --> high risk : sell / buy more quantity
    abs(eval_note) + trader.get_risk() --> result between 0 and 2 --> self.MAX_SUM_RESULT
    self.QUANTITY_ATTENUATION --> try to contains the result between self.QUANTITY_MIN_PERCENT and self.QUANTITY_MAX_PERCENT
    """

    def _get_limit_quantity_from_risk(self, eval_note, trader, quantity):
        factor = self.QUANTITY_MIN_PERCENT + ((abs(eval_note) + trader.get_risk()) * self.QUANTITY_ATTENUATION)
        return self.check_factor(self.QUANTITY_MIN_PERCENT,
                                 self.QUANTITY_MAX_PERCENT,
                                 factor) * quantity

    """
    Starting point : self.QUANTITY_MARKET_MIN_PERCENT
    abs(eval_note) --> confirmation level --> high : sell/buy more quantity
    trader.get_risk() --> high risk : sell / buy more quantity
    abs(eval_note) + trader.get_risk() --> result between 0 and 2 --> self.MAX_SUM_RESULT
    self.QUANTITY_MARKET_ATTENUATION --> try to contains the result between self.QUANTITY_MARKET_MIN_PERCENT and self.QUANTITY_MARKET_MAX_PERCENT
    """

    def _get_market_quantity_from_risk(self, eval_note, trader, quantity, buy=False):
        factor = self.QUANTITY_MARKET_MIN_PERCENT + (
                (abs(eval_note) + trader.get_risk()) * self.QUANTITY_MARKET_ATTENUATION)

        # if buy market --> limit market usage
        if buy:
            factor *= self.QUANTITY_BUY_MARKET_ATTENUATION

        return self.check_factor(self.QUANTITY_MARKET_MIN_PERCENT, self.QUANTITY_MARKET_MAX_PERCENT, factor) * quantity

    # creates a new order (or multiple split orders), always check EvaluatorOrderCreator.can_create_order() first.
    async def create_new_order(self, eval_note, symbol, exchange, trader, portfolio, state):
        try:
            current_symbol_holding, current_market_quantity, market_quantity, price, symbol_market = \
                await self.get_pre_order_data(exchange, symbol, portfolio)

            created_orders = []

            if state == EvaluatorStates.VERY_SHORT:
                quantity = self._get_market_quantity_from_risk(eval_note,
                                                               trader,
                                                               current_symbol_holding)
                quantity += self.get_additional_dusts_to_quantity_if_necessary(quantity, price,
                                                                               symbol_market, current_symbol_holding)
                for order_quantity, order_price in self.check_and_adapt_order_details_if_necessary(quantity, price,
                                                                                                   symbol_market):
                    market = trader.create_order_instance(order_type=TraderOrderType.SELL_MARKET,
                                                          symbol=symbol,
                                                          current_price=order_price,
                                                          quantity=order_quantity,
                                                          price=order_price)
                    await trader.create_order(market, portfolio)
                    created_orders.append(market)
                return created_orders

            elif state == EvaluatorStates.SHORT:
                quantity = self._get_limit_quantity_from_risk(eval_note,
                                                              trader,
                                                              current_symbol_holding)
                limit_price = self.adapt_price(symbol_market,
                                               price * self._get_limit_price_from_risk(eval_note, trader))
                stop_price = self.adapt_price(symbol_market, price * self._get_stop_price_from_risk(trader))
                for order_quantity, order_price in self.check_and_adapt_order_details_if_necessary(quantity,
                                                                                                   limit_price,
                                                                                                   symbol_market):
                    limit = trader.create_order_instance(order_type=TraderOrderType.SELL_LIMIT,
                                                         symbol=symbol,
                                                         current_price=price,
                                                         quantity=order_quantity,
                                                         price=order_price)
                    updated_limit = await trader.create_order(limit, portfolio)
                    created_orders.append(updated_limit)

                    stop = trader.create_order_instance(order_type=TraderOrderType.STOP_LOSS,
                                                        symbol=symbol,
                                                        current_price=price,
                                                        quantity=order_quantity,
                                                        price=stop_price,
                                                        linked_to=updated_limit)
                    await trader.create_order(stop, portfolio)
                return created_orders

            elif state == EvaluatorStates.NEUTRAL:
                pass

            # TODO : stop loss
            elif state == EvaluatorStates.LONG:
                quantity = self._get_limit_quantity_from_risk(eval_note,
                                                              trader,
                                                              market_quantity)
                limit_price = self.adapt_price(symbol_market,
                                               price * self._get_limit_price_from_risk(eval_note, trader))
                for order_quantity, order_price in self.check_and_adapt_order_details_if_necessary(quantity,
                                                                                                   limit_price,
                                                                                                   symbol_market):
                    limit = trader.create_order_instance(order_type=TraderOrderType.BUY_LIMIT,
                                                         symbol=symbol,
                                                         current_price=price,
                                                         quantity=order_quantity,
                                                         price=order_price)
                    await trader.create_order(limit, portfolio)
                    created_orders.append(limit)
                return created_orders

            elif state == EvaluatorStates.VERY_LONG:
                quantity = self._get_market_quantity_from_risk(eval_note,
                                                               trader,
                                                               market_quantity,
                                                               True)
                for order_quantity, order_price in self.check_and_adapt_order_details_if_necessary(quantity, price,
                                                                                                   symbol_market):
                    market = trader.create_order_instance(order_type=TraderOrderType.BUY_MARKET,
                                                          symbol=symbol,
                                                          current_price=order_price,
                                                          quantity=order_quantity,
                                                          price=order_price)
                    await trader.create_order(market, portfolio)
                    created_orders.append(market)
                return created_orders

            # if nothing go returned, return None
            return None

        except InsufficientFunds as e:
            raise e

        except Exception as e:
            get_logger(self.__class__.__name__).error(f"Failed to create order : {e}")
            get_logger(self.__class__.__name__).exception(e)
            return None


class DailyTradingModeDecider(AbstractTradingModeDecider):
    def __init__(self, trading_mode, symbol_evaluator, exchange):
        super().__init__(trading_mode, symbol_evaluator, exchange)

        # If final_eval not is < X_THRESHOLD --> state = X
        self.VERY_LONG_THRESHOLD = -0.85
        self.LONG_THRESHOLD = -0.25
        self.NEUTRAL_THRESHOLD = 0.25
        self.SHORT_THRESHOLD = 0.85
        self.RISK_THRESHOLD = 0.2

    def set_final_eval(self):
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

    def _get_delta_risk(self):
        return self.RISK_THRESHOLD * self.symbol_evaluator.get_trader(self.exchange).get_risk()

    async def create_state(self):
        delta_risk = self._get_delta_risk()

        if self.final_eval < self.VERY_LONG_THRESHOLD + delta_risk:
            await self._set_state(EvaluatorStates.VERY_LONG)

        elif self.final_eval < self.LONG_THRESHOLD + delta_risk:
            await self._set_state(EvaluatorStates.LONG)

        elif self.final_eval < self.NEUTRAL_THRESHOLD - delta_risk:
            await self._set_state(EvaluatorStates.NEUTRAL)

        elif self.final_eval < self.SHORT_THRESHOLD - delta_risk:
            await self._set_state(EvaluatorStates.SHORT)

        else:
            await self._set_state(EvaluatorStates.VERY_SHORT)

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True

    async def _set_state(self, new_state):
        if new_state != self.state:
            # previous_state = self.state
            self.state = new_state
            self.logger.info("{0} ** NEW FINAL STATE ** : {1}".format(self.symbol, self.state))

            # if new state is not neutral --> cancel orders and create new else keep orders
            if new_state is not EvaluatorStates.NEUTRAL:

                # cancel open orders
                await self.cancel_symbol_open_orders()

                # create notification
                if self.symbol_evaluator.matrices:
                    await self.notifier.notify_alert(
                          self.final_eval,
                          self.symbol_evaluator.get_crypto_currency_evaluator(),
                          self.symbol_evaluator.get_symbol(),
                          self.symbol_evaluator.get_trader(self.exchange),
                          self.state,
                          self.symbol_evaluator.get_matrix(self.exchange).get_matrix())
                    
                # call orders creation method
                await self.create_final_state_orders(self.notifier, self.trading_mode.get_only_creator_key(self.symbol))
