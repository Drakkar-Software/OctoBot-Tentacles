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
import asyncio
from ccxt import InsufficientFunds

from octobot_channels.channels.channel import CHANNEL_WILDCARD
from octobot_commons.constants import INIT_EVAL_NOTE
from octobot_commons.evaluators_util import check_valid_eval_note
from octobot_commons.pretty_printer import cryptocurrency_alert
from octobot_commons.symbol_util import split_symbol
from octobot_evaluators.api.matrix import get_value, get_type
from octobot_evaluators.constants import EVALUATOR_EVAL_DEFAULT_TYPE
from octobot_evaluators.data_manager.matrix_manager import get_tentacles_value_nodes, get_tentacle_nodes
from octobot_evaluators.enums import EvaluatorMatrixTypes
from octobot_trading.constants import MODE_CHANNEL, ORDER_DATA_FETCHING_TIMEOUT
from octobot_trading.channels.exchange_channel import get_chan
from octobot_trading.modes.abstract_trading_mode import AbstractTradingMode
from octobot_trading.consumers.abstract_mode_consumer import AbstractTradingModeConsumer, check_factor
from octobot_trading.producers.abstract_mode_producer import AbstractTradingModeProducer
from octobot_trading.enums import EvaluatorStates, TraderOrderType
from octobot_trading.orders.order_adapter import add_dusts_to_quantity_if_necessary, \
    check_and_adapt_order_details_if_necessary, adapt_price
from octobot_trading.orders.order_factory import create_order_instance
from octobot_trading.orders.order_util import get_pre_order_data


class DailyTradingMode(AbstractTradingMode):

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.load_config()

    def get_current_state(self) -> (str, float):
        return super().get_current_state()[0] if self.producers[0].state is None else self.producers[0].state.name, \
            self.producers[0].final_eval

    async def create_producers(self) -> list:
        mode_producer = DailyTradingModeProducer(get_chan(MODE_CHANNEL, self.exchange_manager.id),
                                                 self.config, self, self.exchange_manager)
        await mode_producer.run()
        return [mode_producer]

    async def create_consumers(self) -> list:
        mode_consumer = DailyTradingModeConsumer(self)
        await get_chan(MODE_CHANNEL, self.exchange_manager.id).new_consumer(
            consumer_instance=mode_consumer,
            trading_mode_name=self.get_name(),
            cryptocurrency=self.cryptocurrency if self.cryptocurrency else CHANNEL_WILDCARD,
            symbol=self.symbol if self.symbol else CHANNEL_WILDCARD,
            time_frame=self.time_frame if self.time_frame else CHANNEL_WILDCARD)
        return [mode_consumer]

    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        return False


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
        # consider a high ratio not to take too much risk and not to prevent order creation either
        self.DEFAULT_HOLDING_RATIO = 0.35

        self.SELL_MULTIPLIER = 5
        self.FULL_SELL_MIN_RATIO = 0.05

        trading_config = self.trading_mode.trading_config if self.trading_mode else {}

        self.USE_CLOSE_TO_CURRENT_PRICE = trading_config.get("use_prices_close_to_current_price", False)
        self.CLOSE_TO_CURRENT_PRICE_DEFAULT_RATIO = trading_config.get("close_to_current_price_difference", 0.02)
        self.USE_MAXIMUM_SIZE_ORDERS = trading_config.get("use_maximum_size_orders", False)
        self.USE_STOP_ORDERS = trading_config.get("use_stop_orders", True)

    def flush(self):
        super().flush()
        self.trader = None

    """
    Starting point : self.SELL_LIMIT_ORDER_MIN_PERCENT or self.BUY_LIMIT_ORDER_MAX_PERCENT
    1 - abs(eval_note) --> confirmation level --> high : sell less expensive / buy more expensive
    1 - trader.risk --> high risk : sell / buy closer to the current price
    1 - abs(eval_note) + 1 - trader.risk --> result between 0 and 2 --> self.MAX_SUM_RESULT
    self.QUANTITY_ATTENUATION --> try to contains the result between self.XXX_MIN_PERCENT and self.XXX_MAX_PERCENT
    """

    def _get_limit_price_from_risk(self, eval_note):
        if eval_note > 0:
            if self.USE_CLOSE_TO_CURRENT_PRICE:
                return 1 + self.CLOSE_TO_CURRENT_PRICE_DEFAULT_RATIO
            factor = self.SELL_LIMIT_ORDER_MIN_PERCENT + \
                ((1 - abs(eval_note) + 1 - self.trader.risk) * self.LIMIT_ORDER_ATTENUATION)
            return check_factor(self.SELL_LIMIT_ORDER_MIN_PERCENT, self.SELL_LIMIT_ORDER_MAX_PERCENT, factor)
        else:
            if self.USE_CLOSE_TO_CURRENT_PRICE:
                return 1 - self.CLOSE_TO_CURRENT_PRICE_DEFAULT_RATIO
            factor = self.BUY_LIMIT_ORDER_MAX_PERCENT - \
                ((1 - abs(eval_note) + 1 - self.trader.risk) * self.LIMIT_ORDER_ATTENUATION)
            return check_factor(self.BUY_LIMIT_ORDER_MIN_PERCENT, self.BUY_LIMIT_ORDER_MAX_PERCENT, factor)

    """
    Starting point : self.STOP_LOSS_ORDER_MAX_PERCENT
    trader.risk --> low risk : stop level close to the current price
    self.STOP_LOSS_ORDER_ATTENUATION --> try to contains the result between self.STOP_LOSS_ORDER_MIN_PERCENT
    and self.STOP_LOSS_ORDER_MAX_PERCENT
    """

    def _get_stop_price_from_risk(self):
        factor = self.STOP_LOSS_ORDER_MAX_PERCENT - (self.trader.risk * self.STOP_LOSS_ORDER_ATTENUATION)
        return check_factor(self.STOP_LOSS_ORDER_MIN_PERCENT, self.STOP_LOSS_ORDER_MAX_PERCENT, factor)

    """
    Starting point : self.QUANTITY_MIN_PERCENT
    abs(eval_note) --> confirmation level --> high : sell/buy more quantity
    trader.risk --> high risk : sell / buy more quantity
    abs(eval_note) + weighted_risk --> result between 0 and 1 + self.QUANTITY_RISK_WEIGHT --> self.MAX_SUM_RESULT
    self.QUANTITY_ATTENUATION --> try to contains the result between self.QUANTITY_MIN_PERCENT
    and self.QUANTITY_MAX_PERCENT
    """

    def _get_buy_limit_quantity_from_risk(self, eval_note, quantity, quote):
        if self.USE_MAXIMUM_SIZE_ORDERS:
            return quantity
        weighted_risk = self.trader.risk * self.QUANTITY_RISK_WEIGHT
        # consider buy quantity like a sell if quote is the reference market
        if quote == self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market:
            weighted_risk *= self.SELL_MULTIPLIER
        factor = self.QUANTITY_MIN_PERCENT + ((abs(eval_note) + weighted_risk) * self.QUANTITY_ATTENUATION)
        checked_factor = check_factor(self.QUANTITY_MIN_PERCENT, self.QUANTITY_MAX_PERCENT, factor)
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

    async def _get_sell_limit_quantity_from_risk(self, eval_note, quantity, quote):
        if self.USE_MAXIMUM_SIZE_ORDERS:
            return quantity
        weighted_risk = self.trader.risk * self.QUANTITY_RISK_WEIGHT
        # consider sell quantity like a buy if base is the reference market
        if quote != self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market:
            weighted_risk *= self.SELL_MULTIPLIER
        if await self._get_ratio(quote) < self.FULL_SELL_MIN_RATIO:
            return quantity
        factor = self.QUANTITY_MIN_PERCENT + ((abs(eval_note) + weighted_risk) * self.QUANTITY_ATTENUATION)
        checked_factor = check_factor(self.QUANTITY_MIN_PERCENT, self.QUANTITY_MAX_PERCENT, factor)
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

    def _get_market_quantity_from_risk(self, eval_note, quantity, quote, selling=False):
        weighted_risk = self.trader.risk * self.QUANTITY_RISK_WEIGHT
        ref_market = self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
        if (selling and quote != ref_market) or (not selling and quote == ref_market):
            weighted_risk *= self.SELL_MULTIPLIER
        factor = self.QUANTITY_MARKET_MIN_PERCENT + (
            (abs(eval_note) + weighted_risk) * self.QUANTITY_MARKET_ATTENUATION)

        checked_factor = check_factor(self.QUANTITY_MARKET_MIN_PERCENT, self.QUANTITY_MARKET_MAX_PERCENT, factor)
        return checked_factor * quantity

    async def _get_ratio(self, currency):
        try:
            return await self.get_holdings_ratio(currency)
        except KeyError:
            # Can happen when ref market is not in the pair, data will be available later (ticker is now registered)
            return self.DEFAULT_HOLDING_RATIO

    async def _get_quantity_ratio(self, currency):
        if self.get_number_of_traded_assets() > 2:
            ratio = await self._get_ratio(currency)
            # returns a linear result between self.MIN_QUANTITY_RATIO and self.MAX_QUANTITY_RATIO: closer to
            # self.MAX_QUANTITY_RATIO when holdings are lower in % and to self.MIN_QUANTITY_RATIO when holdings
            # are higher in %
            return 1 - min(ratio * self.DELTA_RATIO, 1)
        else:
            return 1

    async def create_new_orders(self, symbol, final_note, state, **kwargs):
        current_order = None
        timeout = kwargs.pop("timeout", ORDER_DATA_FETCHING_TIMEOUT)
        try:
            current_symbol_holding, current_market_holding, market_quantity, price, symbol_market = \
                await get_pre_order_data(self.exchange_manager, symbol=symbol, timeout=timeout)

            quote, _ = split_symbol(symbol)
            created_orders = []

            if state == EvaluatorStates.VERY_SHORT.value:
                quantity = self._get_market_quantity_from_risk(final_note, current_symbol_holding, quote, True)
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

            elif state == EvaluatorStates.SHORT.value:
                quantity = await self._get_sell_limit_quantity_from_risk(final_note, current_symbol_holding, quote)
                quantity = add_dusts_to_quantity_if_necessary(quantity, price, symbol_market, current_symbol_holding)
                limit_price = adapt_price(symbol_market, price * self._get_limit_price_from_risk(final_note))
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

                    if self.USE_STOP_ORDERS:
                        stop_price = adapt_price(symbol_market, price * self._get_stop_price_from_risk())
                        current_order = create_order_instance(trader=self.trader,
                                                              order_type=TraderOrderType.STOP_LOSS,
                                                              symbol=symbol,
                                                              current_price=price,
                                                              quantity=order_quantity,
                                                              price=stop_price,
                                                              linked_to=updated_limit)
                        await self.trader.create_order(current_order)
                return created_orders

            elif state == EvaluatorStates.NEUTRAL.value:
                pass

            # TODO : stop loss
            elif state == EvaluatorStates.LONG.value:
                quantity = self._get_buy_limit_quantity_from_risk(final_note, market_quantity, quote)
                quantity = quantity * await self._get_quantity_ratio(quote)
                limit_price = adapt_price(symbol_market, price * self._get_limit_price_from_risk(final_note))
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

            elif state == EvaluatorStates.VERY_LONG.value:
                quantity = self._get_market_quantity_from_risk(final_note, market_quantity, quote)
                quantity = quantity * await self._get_quantity_ratio(quote)
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

            # if nothing go returned, return empty list
            return []

        except InsufficientFunds as e:
            raise e
        except asyncio.TimeoutError as e:
            self.logger.error(f"Impossible to create order on {symbol}: {e} and is necessary to compute the "
                              f"order details.")
            return []
        except Exception as e:
            self.logger.exception(e, True, f"Failed to create order : {e}.")
            return []

    async def internal_callback(self, trading_mode_name, cryptocurrency, symbol, time_frame, final_note, state, data):
        # creates a new order (or multiple split orders), always check self.can_create_order() first.
        await self.create_order_if_possible(symbol, final_note, state)


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

    async def stop(self):
        if self.trading_mode is not None:
            self.trading_mode.consumers[0].flush()
        await super().stop()

    async def set_final_eval(self, matrix_id: str, cryptocurrency: str, symbol: str, time_frame):
        strategies_analysis_note_counter = 0
        evaluation = INIT_EVAL_NOTE
        # Strategies analysis
        for evaluated_strategy_node in get_tentacles_value_nodes(
                matrix_id,
                get_tentacle_nodes(matrix_id,
                                   exchange_name=self.exchange_name,
                                   tentacle_type=EvaluatorMatrixTypes.STRATEGIES.value),
                cryptocurrency=cryptocurrency,
                symbol=symbol):

            if check_valid_eval_note(get_value(evaluated_strategy_node),
                                     get_type(evaluated_strategy_node),
                                     EVALUATOR_EVAL_DEFAULT_TYPE):
                evaluation += get_value(evaluated_strategy_node)  # TODO * evaluated_strategies.get_pertinence()
                strategies_analysis_note_counter += 1  # TODO evaluated_strategies.get_pertinence()

        if strategies_analysis_note_counter > 0:
            self.final_eval = evaluation / strategies_analysis_note_counter
            await self.create_state(cryptocurrency=cryptocurrency, symbol=symbol)

    def _get_delta_risk(self):
        return self.RISK_THRESHOLD * self.exchange_manager.trader.risk

    async def create_state(self, cryptocurrency: str, symbol: str):
        delta_risk = self._get_delta_risk()

        if self.final_eval < self.VERY_LONG_THRESHOLD + delta_risk:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=EvaluatorStates.VERY_LONG)
        elif self.final_eval < self.LONG_THRESHOLD + delta_risk:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=EvaluatorStates.LONG)
        elif self.final_eval < self.NEUTRAL_THRESHOLD - delta_risk:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=EvaluatorStates.NEUTRAL)
        elif self.final_eval < self.SHORT_THRESHOLD - delta_risk:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=EvaluatorStates.SHORT)
        else:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=EvaluatorStates.VERY_SHORT)

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True

    async def _set_state(self, cryptocurrency: str, symbol: str, new_state):
        if new_state != self.state:
            # previous_state = self.state
            self.state = new_state
            self.logger.info(f"[{symbol}] new state: {self.state.name}")

            # if new state is not neutral --> cancel orders and create new else keep orders
            if new_state is not EvaluatorStates.NEUTRAL:
                # cancel open orders
                await self.cancel_symbol_open_orders(symbol)

                # call orders creation from consumers
                await self.submit_trading_evaluation(cryptocurrency=cryptocurrency,
                                                     symbol=symbol,
                                                     time_frame=None,
                                                     final_note=self.final_eval,
                                                     state=self.state)

                # send_notification
                if not self.exchange_manager.is_backtesting:
                    await self._send_alert_notification(symbol, new_state)

    async def _send_alert_notification(self, symbol, new_state):
        try:
            from octobot_services.api.notification import create_notification, send_notification
            from octobot_services.enums import NotificationCategory
            title = f"OCTOBOT ALERT : #{symbol}"
            alert_content, alert_content_markdown = cryptocurrency_alert(
                new_state,
                self.final_eval)
            await send_notification(create_notification(alert_content, title=title,
                                                        markdown_text=alert_content_markdown,
                                                        category=NotificationCategory.PRICE_ALERTS))
        except ImportError as e:
            self.logger.exception(e, True, f"Impossible to send notification: {e}")
