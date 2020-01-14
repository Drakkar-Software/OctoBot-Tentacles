"""
OctoBot Tentacle

$tentacle_description: {
    "package_name": "OctoBot-Tentacles",
    "name": "daily_trading_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.2.0",
    "requirements": ["mixed_strategies_evaluator"],
    "config_files": ["DailyTradingMode.json"],
    "tests":["test_daily_trading_mode_creator", "test_daily_trading_mode_decider"]
}
"""

#  Drakkar-Software OctoBot-Tentacles
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

from octobot_commons.constants import INIT_EVAL_NOTE
from octobot_commons.evaluators_util import check_valid_eval_note
from octobot_commons.symbol_util import split_symbol

from octobot_trading.constants import MODE_CHANNEL
from octobot_trading.channels.exchange_channel import get_chan
from octobot_trading.consumers.abstract_mode_consumer import AbstractTradingModeConsumer
from octobot_trading.enums import EvaluatorStates, TraderOrderType
from octobot_trading.modes.abstract_trading_mode import AbstractTradingMode
from octobot_trading.orders.order_adapter import add_dusts_to_quantity_if_necessary, \
    check_and_adapt_order_details_if_necessary, adapt_price
from octobot_trading.orders.order_factory import create_order_instance
from octobot_trading.orders.order_util import get_pre_order_data
from octobot_trading.producers.abstract_mode_producer import AbstractTradingModeProducer


class DailyTradingMode(AbstractTradingMode):
    DESCRIPTION = "DailyTradingMode is a low risk versatile trading mode that reacts only the its state changes to " \
                  "a state that is different from the previous one and that is not NEUTRAL.\n" \
                  "When triggered for a given symbol, it will cancel previously created (and unfilled) orders " \
                  "and create new ones according to its new state.\n" \
                  "DailyTradingMode will consider every compatible strategy and average their evaluation to create " \
                  "each state."

    async def create_producers(self):
        await DailyTradingModeProducer(get_chan(MODE_CHANNEL, self.exchange_manager.exchange.name),
                                       self.config, self, self.exchange_manager).run()

    async def create_consumers(self):
        await get_chan(MODE_CHANNEL, self.exchange_manager.exchange.name).new_consumer(
            consumer_instance=DailyTradingModeConsumer(self))


class DailyTradingModeConsumer(AbstractTradingModeConsumer):
    def __init__(self, trading_mode):
        super().__init__(trading_mode)
        self.trader = self.exchange_manager.trader

        self.MAX_SUM_RESULT = 2

        self.STOP_LOSS_ORDER_MAX_PERCENT = 0.99
        self.STOP_LOSS_ORDER_MIN_PERCENT = 0.95
        self.STOP_LOSS_ORDER_ATTENUATION = (self.STOP_LOSS_ORDER_MAX_PERCENT - self.STOP_LOSS_ORDER_MIN_PERCENT)

        self.QUANTITY_MIN_PERCENT = 0.1
        self.QUANTITY_MAX_PERCENT = 0.9
        self.QUANTITY_ATTENUATION = (self.QUANTITY_MAX_PERCENT - self.QUANTITY_MIN_PERCENT) / self.MAX_SUM_RESULT

        self.QUANTITY_MARKET_MIN_PERCENT = 0.3
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

        self.QUANTITY_RISK_WEIGHT = 0.2
        self.MAX_QUANTITY_RATIO = 1
        self.MIN_QUANTITY_RATIO = 0.2
        self.DELTA_RATIO = self.MAX_QUANTITY_RATIO - self.MIN_QUANTITY_RATIO

        self.SELL_MULTIPLIER = 5
        self.FULL_SELL_MIN_RATIO = 0.05

    """
    Starting point : self.SELL_LIMIT_ORDER_MIN_PERCENT or self.BUY_LIMIT_ORDER_MAX_PERCENT
    1 - abs(eval_note) --> confirmation level --> high : sell less expensive / buy more expensive
    1 - trader.risk --> high risk : sell / buy closer to the current price
    1 - abs(eval_note) + 1 - trader.risk --> result between 0 and 2 --> self.MAX_SUM_RESULT
    self.QUANTITY_ATTENUATION --> try to contains the result between self.XXX_MIN_PERCENT and self.XXX_MAX_PERCENT
    """

    def __get_limit_price_from_risk(self, eval_note):
        if eval_note > 0:
            factor = self.SELL_LIMIT_ORDER_MIN_PERCENT + \
                     ((1 - abs(eval_note) + 1 - self.trader.risk) * self.LIMIT_ORDER_ATTENUATION)
            return AbstractTradingModeConsumer.check_factor(self.SELL_LIMIT_ORDER_MIN_PERCENT,
                                                            self.SELL_LIMIT_ORDER_MAX_PERCENT,
                                                            factor)
        else:
            factor = self.BUY_LIMIT_ORDER_MAX_PERCENT - \
                     ((1 - abs(eval_note) + 1 - self.trader.risk) * self.LIMIT_ORDER_ATTENUATION)
            return AbstractTradingModeConsumer.check_factor(self.BUY_LIMIT_ORDER_MIN_PERCENT,
                                                            self.BUY_LIMIT_ORDER_MAX_PERCENT,
                                                            factor)

    """
    Starting point : self.STOP_LOSS_ORDER_MAX_PERCENT
    trader.risk --> low risk : stop level close to the current price
    self.STOP_LOSS_ORDER_ATTENUATION --> try to contains the result between self.STOP_LOSS_ORDER_MIN_PERCENT 
    and self.STOP_LOSS_ORDER_MAX_PERCENT
    """

    def __get_stop_price_from_risk(self):
        factor = self.STOP_LOSS_ORDER_MAX_PERCENT - (self.trader.risk * self.STOP_LOSS_ORDER_ATTENUATION)
        return AbstractTradingModeConsumer.check_factor(self.STOP_LOSS_ORDER_MIN_PERCENT,
                                                        self.STOP_LOSS_ORDER_MAX_PERCENT,
                                                        factor)

    """
    Starting point : self.QUANTITY_MIN_PERCENT
    abs(eval_note) --> confirmation level --> high : sell/buy more quantity
    trader.risk --> high risk : sell / buy more quantity
    abs(eval_note) + weighted_risk --> result between 0 and 1 + self.QUANTITY_RISK_WEIGHT --> self.MAX_SUM_RESULT
    self.QUANTITY_ATTENUATION --> try to contains the result between self.QUANTITY_MIN_PERCENT 
    and self.QUANTITY_MAX_PERCENT
    """

    def __get_buy_limit_quantity_from_risk(self, eval_note, quantity, quote):
        weighted_risk = self.trader.risk * self.QUANTITY_RISK_WEIGHT
        # consider buy quantity like a sell if quote is the reference market
        if quote == self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market:
            weighted_risk *= self.SELL_MULTIPLIER
        factor = self.QUANTITY_MIN_PERCENT + ((abs(eval_note) + weighted_risk) * self.QUANTITY_ATTENUATION)
        checked_factor = AbstractTradingModeConsumer.check_factor(self.QUANTITY_MIN_PERCENT, self.QUANTITY_MAX_PERCENT,
                                                                  factor)
        return checked_factor * quantity

    """
    Starting point : self.QUANTITY_MIN_PERCENT
    abs(eval_note) --> confirmation level --> high : sell/buy more quantity
    trader.risk --> high risk : sell / buy more quantity
    use SELL_MULTIPLIER to increase sell volume relatively to risk
    if currency holding < FULL_SELL_MIN_RATIO, sell everything to free up funds
    abs(eval_note) + weighted_risk --> result between 0 and 1 + self.QUANTITY_RISK_WEIGHT --> self.MAX_SUM_RESULT
    self.QUANTITY_ATTENUATION --> try to contains the result between self.QUANTITY_MIN_PERCENT 
    and self.QUANTITY_MAX_PERCENT
    """

    async def __get_sell_limit_quantity_from_risk(self, eval_note, quantity, quote):
        weighted_risk = self.trader.risk * self.QUANTITY_RISK_WEIGHT
        # consider sell quantity like a buy if base is the reference market
        if quote != self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market:
            weighted_risk *= self.SELL_MULTIPLIER
        if await self.get_holdings_ratio(quote) < self.FULL_SELL_MIN_RATIO:
            return quantity
        factor = self.QUANTITY_MIN_PERCENT + ((abs(eval_note) + weighted_risk) * self.QUANTITY_ATTENUATION)
        checked_factor = AbstractTradingModeConsumer.check_factor(self.QUANTITY_MIN_PERCENT,
                                                                  self.QUANTITY_MAX_PERCENT,
                                                                  factor)
        return checked_factor * quantity

    """
    Starting point : self.QUANTITY_MARKET_MIN_PERCENT
    abs(eval_note) --> confirmation level --> high : sell/buy more quantity
    trader.risk --> high risk : sell / buy more quantity
    use SELL_MULTIPLIER to increase sell volume relatively to risk
    abs(eval_note) + trader.risk --> result between 0 and 1 + self.QUANTITY_RISK_WEIGHT --> self.MAX_SUM_RESULT
    self.QUANTITY_MARKET_ATTENUATION --> try to contains the result between self.QUANTITY_MARKET_MIN_PERCENT 
    and self.QUANTITY_MARKET_MAX_PERCENT
    """

    def __get_market_quantity_from_risk(self, eval_note, quantity, quote, selling=False):
        weighted_risk = self.trader.risk * self.QUANTITY_RISK_WEIGHT
        if (selling and quote != self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market) \
                or (
                not selling and quote == self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market):
            weighted_risk *= self.SELL_MULTIPLIER
        factor = self.QUANTITY_MARKET_MIN_PERCENT + (
                (abs(eval_note) + weighted_risk) * self.QUANTITY_MARKET_ATTENUATION)

        checked_factor = AbstractTradingModeConsumer.check_factor(self.QUANTITY_MARKET_MIN_PERCENT,
                                                                  self.QUANTITY_MARKET_MAX_PERCENT,
                                                                  factor)
        return checked_factor * quantity

    async def __get_quantity_ratio(self, currency):
        if self.get_number_of_traded_assets() > 2:
            ratio = await self.get_holdings_ratio(currency)
            # returns a linear result between self.MIN_QUANTITY_RATIO and self.MAX_QUANTITY_RATIO: closer to
            # self.MAX_QUANTITY_RATIO when holdings are lower in % and to self.MIN_QUANTITY_RATIO when holdings
            # are higher in %
            return 1 - min(ratio * self.DELTA_RATIO, 1)
        else:
            return 1

    # creates a new order (or multiple split orders), always check EvaluatorOrderCreator.can_create_order() first.
    async def internal_callback(self, trading_mode_name, symbol, final_note, state):
        current_order = None
        try:
            current_symbol_holding, current_market_holding, market_quantity, price, symbol_market = \
                await get_pre_order_data(self.exchange_manager, symbol=symbol)

            quote, _ = split_symbol(symbol)
            created_orders = []

            if state == EvaluatorStates.VERY_SHORT:
                quantity = self.__get_market_quantity_from_risk(final_note, current_symbol_holding, quote, True)
                quantity = add_dusts_to_quantity_if_necessary(quantity, price, symbol_market, current_symbol_holding)
                for order_quantity, order_price in check_and_adapt_order_details_if_necessary(quantity, price,
                                                                                              symbol_market):
                    current_order = create_order_instance(trader=self.trader,
                                                          order_type=TraderOrderType.SELL_MARKET,
                                                          symbol=symbol,
                                                          current_price=order_price,
                                                          quantity=order_quantity,
                                                          price=order_price)
                    await self.trader.create_order(current_order)
                    created_orders.append(current_order)
                return created_orders

            elif state == EvaluatorStates.SHORT:
                quantity = await self.__get_sell_limit_quantity_from_risk(final_note, current_symbol_holding, quote)
                quantity = add_dusts_to_quantity_if_necessary(quantity, price, symbol_market, current_symbol_holding)
                limit_price = adapt_price(symbol_market, price * self.__get_limit_price_from_risk(final_note))
                stop_price = adapt_price(symbol_market, price * self.__get_stop_price_from_risk())
                for order_quantity, order_price in check_and_adapt_order_details_if_necessary(quantity,
                                                                                              limit_price,
                                                                                              symbol_market):
                    current_order = create_order_instance(trader=self.trader,
                                                          order_type=TraderOrderType.SELL_LIMIT,
                                                          symbol=symbol,
                                                          current_price=price,
                                                          quantity=order_quantity,
                                                          price=order_price)
                    updated_limit = await self.trader.create_order(current_order)
                    created_orders.append(updated_limit)

                    current_order = create_order_instance(trader=self.trader,
                                                          order_type=TraderOrderType.STOP_LOSS,
                                                          symbol=symbol,
                                                          current_price=price,
                                                          quantity=order_quantity,
                                                          price=stop_price,
                                                          linked_to=updated_limit)
                    await self.trader.create_order(current_order)
                return created_orders

            elif state == EvaluatorStates.NEUTRAL:
                pass

            # TODO : stop loss
            elif state == EvaluatorStates.LONG:
                quantity = self.__get_buy_limit_quantity_from_risk(final_note, market_quantity, quote)
                quantity = quantity * await self.__get_quantity_ratio(quote)
                limit_price = adapt_price(symbol_market, price * self.__get_limit_price_from_risk(final_note))
                for order_quantity, order_price in check_and_adapt_order_details_if_necessary(quantity,
                                                                                              limit_price,
                                                                                              symbol_market):
                    current_order = create_order_instance(trader=self.trader,
                                                          order_type=TraderOrderType.BUY_LIMIT,
                                                          symbol=symbol,
                                                          current_price=price,
                                                          quantity=order_quantity,
                                                          price=order_price)
                    await self.trader.create_order(current_order)
                    created_orders.append(current_order)
                return created_orders

            elif state == EvaluatorStates.VERY_LONG:
                quantity = self.__get_market_quantity_from_risk(final_note, market_quantity, quote)
                quantity = quantity * await self.__get_quantity_ratio(quote)
                for order_quantity, order_price in check_and_adapt_order_details_if_necessary(quantity, price,
                                                                                              symbol_market):
                    current_order = create_order_instance(trader=self.trader,
                                                          order_type=TraderOrderType.BUY_MARKET,
                                                          symbol=symbol,
                                                          current_price=order_price,
                                                          quantity=order_quantity,
                                                          price=order_price)
                    await self.trader.create_order(current_order)
                    created_orders.append(current_order)
                return created_orders

            # if nothing go returned, return None
            return None

        except InsufficientFunds as e:
            raise e

        except Exception as e:
            self._logger.error(f"Failed to create order : {e}.")
            self._logger.exception(e)
            return None


class DailyTradingModeProducer(AbstractTradingModeProducer):
    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)

        self.state = None

        # If final_eval not is < X_THRESHOLD --> state = X
        self.VERY_LONG_THRESHOLD = -0.85
        self.LONG_THRESHOLD = -0.25
        self.NEUTRAL_THRESHOLD = 0.25
        self.SHORT_THRESHOLD = 0.85
        self.RISK_THRESHOLD = 0.2

    async def set_final_eval(self, matrix_id: str, cryptocurrency: str, symbol: str, time_frame):
        if time_frame is None:
            # Do nothing, requires a time frame
            return

        strategies_analysis_note_counter = 0

        try:
            from octobot_evaluators.matrices.matrices import Matrices
            from octobot_evaluators.enums import EvaluatorMatrixTypes
        except ImportError:
            self.logger.error("octobot_evaluators.matrices.matrices.Matrices cannot be imported")
            return

        related_matrix = Matrices.instance().get_matrix(matrix_id)

        # Strategies analysis
        for evaluated_strategy_node in related_matrix.get_tentacles_value_nodes(related_matrix.get_tentacle_nodes(
                exchange_name=self.exchange_name,
                tentacle_type=EvaluatorMatrixTypes.STRATEGIES.value),
                symbol=symbol,
                time_frame=time_frame):

            if evaluated_strategy_node and check_valid_eval_note(evaluated_strategy_node.node_value):
                self.final_eval += evaluated_strategy_node.node_value  # TODO * evaluated_strategies.get_pertinence()
                strategies_analysis_note_counter += 1  # TODO evaluated_strategies.get_pertinence()

        if strategies_analysis_note_counter > 0:
            self.final_eval /= strategies_analysis_note_counter
        else:
            self.final_eval = INIT_EVAL_NOTE
        await self.create_state(symbol=symbol)

    async def submit_trading_evaluation(self, symbol, final_note=INIT_EVAL_NOTE, state=EvaluatorStates.NEUTRAL):
        await self.send(trading_mode_name=self.trading_mode.get_name(),
                        symbol=symbol,
                        final_note=final_note,
                        state=state)

    def __get_delta_risk(self):
        return self.RISK_THRESHOLD * self.exchange_manager.trader.risk

    async def create_state(self, symbol):
        delta_risk = self.__get_delta_risk()

        if self.final_eval < self.VERY_LONG_THRESHOLD + delta_risk:
            await self.__set_state(symbol, EvaluatorStates.VERY_LONG)
        elif self.final_eval < self.LONG_THRESHOLD + delta_risk:
            await self.__set_state(symbol, EvaluatorStates.LONG)
        elif self.final_eval < self.NEUTRAL_THRESHOLD - delta_risk:
            await self.__set_state(symbol, EvaluatorStates.NEUTRAL)
        elif self.final_eval < self.SHORT_THRESHOLD - delta_risk:
            await self.__set_state(symbol, EvaluatorStates.SHORT)
        else:
            await self.__set_state(symbol, EvaluatorStates.VERY_SHORT)

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True

    async def __set_state(self, symbol, new_state):
        if new_state != self.state:
            # previous_state = self.state
            self.state = new_state

            # if new state is not neutral --> cancel orders and create new else keep orders
            if new_state is not EvaluatorStates.NEUTRAL:
                # cancel open orders
                await self.cancel_symbol_open_orders(symbol)

                # call orders creation from consumers
                await self.submit_trading_evaluation(symbol=symbol, final_note=self.final_eval, state=self.state)
