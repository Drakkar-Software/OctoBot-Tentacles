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
import asyncio
import decimal
import enum

import octobot_commons.symbols.symbol_util as symbol_util
import octobot_commons.enums as commons_enums
import octobot_commons.constants as commons_constants
import octobot_commons.evaluators_util as evaluators_util

import octobot_evaluators.api as evaluators_api
import octobot_evaluators.constants as evaluators_constants
import octobot_evaluators.enums as evaluators_enums
import octobot_evaluators.matrix as matrix

import octobot_trading.modes as trading_modes
import octobot_trading.enums as trading_enums
import octobot_trading.constants as trading_constants
import octobot_trading.util as trading_util
import octobot_trading.errors as trading_errors
import octobot_trading.personal_data as trading_personal_data
import octobot_trading.modes.script_keywords as script_keywords


class TriggerMode(enum.Enum):
    TIME_BASED = "Time based"
    MAXIMUM_EVALUATORS_SIGNALS_BASED = "Maximum evaluators signals based"


class DCATradingModeConsumer(trading_modes.AbstractTradingModeConsumer):
    AMOUNT_TO_BUY_IN_REF_MARKET = "amount_to_buy_in_reference_market"
    ENTRY_LIMIT_ORDERS_PRICE_PERCENT = "entry_limit_orders_price_percent"
    USE_MARKET_ENTRY_ORDERS = "use_market_entry_orders"
    USE_SECONDARY_ENTRY_ORDERS = "use_secondary_entry_orders"
    SECONDARY_ENTRY_ORDERS_COUNT = "secondary_entry_orders_count"
    SECONDARY_ENTRY_ORDERS_AMOUNT = "secondary_entry_orders_amount"
    SECONDARY_ENTRY_ORDERS_PRICE_PERCENT = "secondary_entry_orders_price_percent"
    DEFAULT_ENTRY_LIMIT_PRICE_MULTIPLIER = decimal.Decimal("0.05")   # 5% by default
    DEFAULT_SECONDARY_ENTRY_ORDERS_COUNT = 0
    DEFAULT_SECONDARY_ENTRY_ORDERS_AMOUNT = ""
    DEFAULT_SECONDARY_ENTRY_ORDERS_PRICE_MULTIPLIER = DEFAULT_ENTRY_LIMIT_PRICE_MULTIPLIER

    EXIT_LIMIT_ORDERS_PRICE_PERCENT = "exit_limit_orders_price_percent"
    DEFAULT_EXIT_LIMIT_PRICE_MULTIPLIER = DEFAULT_ENTRY_LIMIT_PRICE_MULTIPLIER
    USE_SECONDARY_EXIT_ORDERS = "use_secondary_exit_orders"
    SECONDARY_EXIT_ORDERS_COUNT = "secondary_exit_orders_count"
    SECONDARY_EXIT_ORDERS_AMOUNT = "secondary_exit_orders_amount"
    SECONDARY_EXIT_ORDERS_PRICE_PERCENT = "secondary_exit_orders_price_percent"
    DEFAULT_SECONDARY_EXIT_ORDERS_COUNT = 0
    DEFAULT_SECONDARY_EXIT_ORDERS_AMOUNT = ""
    DEFAULT_SECONDARY_EXIT_ORDERS_PRICE_MULTIPLIER = DEFAULT_ENTRY_LIMIT_PRICE_MULTIPLIER

    USE_STOP_LOSSES = "use_stop_losses"
    STOP_LOSS_PRICE_PERCENT = "stop_loss_price_percent"
    DEFAULT_STOP_LOSS_ORDERS_PRICE_MULTIPLIER = 2 * DEFAULT_ENTRY_LIMIT_PRICE_MULTIPLIER

    async def create_new_orders(self, symbol, final_note, state, **kwargs):
        current_order = None
        try:
            current_symbol_holding, current_market_holding, market_quantity, price, symbol_market = \
                await trading_personal_data.get_pre_order_data(self.exchange_manager, symbol=symbol,
                                                               timeout=trading_constants.ORDER_DATA_FETCHING_TIMEOUT)

            created_orders = []
            orders_should_have_been_created = False
            ctx = script_keywords.get_base_context(self.trading_mode, symbol)
            if state is trading_enums.EvaluatorStates.NEUTRAL:
                raise trading_errors.NotSupported(state)
            side = trading_enums.TradeOrderSide.BUY if state in (
                trading_enums.EvaluatorStates.LONG.value, trading_enums.EvaluatorStates.VERY_LONG.value
            ) else trading_enums.TradeOrderSide.SELL

            secondary_quantity = None
            if user_amount := trading_modes.get_user_selected_order_amount(self.trading_mode,
                                                                           trading_enums.TradeOrderSide.BUY):
                quantity = await script_keywords.get_amount_from_input_amount(
                    context=ctx,
                    input_amount=user_amount,
                    side=side.value,
                    reduce_only=False,
                    is_stop_order=False,
                    use_total_holding=False,
                )

                if self.trading_mode.secondary_entry_orders_amount:
                    secondary_quantity = await script_keywords.get_amount_from_input_amount(
                        context=ctx,
                        input_amount=self.trading_mode.secondary_entry_orders_amount,
                        side=side.value,
                        reduce_only=False,
                        is_stop_order=False,
                        use_total_holding=False,
                    )
            else:
                self.logger.error(f"Missing {side.value} order quantity")
                return []
            initial_entry_price = price if self.trading_mode.use_market_entry_orders else \
                trading_personal_data.decimal_adapt_price(
                    symbol_market,
                    price * (
                        1 - self.trading_mode.entry_limit_orders_price_multiplier if side is trading_enums.TradeOrderSide.BUY
                        else 1 + self.trading_mode.entry_limit_orders_price_multiplier
                    )
                )
            if side is trading_enums.TradeOrderSide.BUY:
                initial_entry_order_type = trading_enums.TraderOrderType.BUY_MARKET \
                    if self.trading_mode.use_market_entry_orders else trading_enums.TraderOrderType.BUY_LIMIT
            else:
                initial_entry_order_type = trading_enums.TraderOrderType.SELL_MARKET \
                    if self.trading_mode.use_market_entry_orders else trading_enums.TraderOrderType.SELL_LIMIT
            # initial entry
            orders_should_have_been_created = await self._create_entry_order(
                initial_entry_order_type, quantity, initial_entry_price,
                symbol_market, symbol, created_orders
            )
            # secondary entries
            if self.trading_mode.secondary_entry_orders_count > 0:
                secondary_order_type = trading_enums.TraderOrderType.BUY_LIMIT \
                    if side is trading_enums.TradeOrderSide.BUY else trading_enums.TraderOrderType.SELL_LIMIT
                for i in range(self.trading_mode.secondary_entry_orders_count):
                    multiplier = (i + 1) * self.trading_mode.secondary_entry_orders_price_multiplier
                    secondary_target_price = initial_entry_price * (
                        (1 - multiplier) if side is trading_enums.TradeOrderSide.BUY else
                        (1 + multiplier)
                    )
                    await self._create_entry_order(
                        secondary_order_type, secondary_quantity, secondary_target_price,
                        symbol_market, symbol, created_orders
                    )
            if created_orders:
                return created_orders
            if orders_should_have_been_created:
                raise trading_errors.OrderCreationError()
            raise trading_errors.MissingMinimalExchangeTradeVolume()

        except (trading_errors.MissingFunds,
                trading_errors.MissingMinimalExchangeTradeVolume,
                trading_errors.OrderCreationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to create order : {e}. Order: "
                              f"{current_order if current_order else None}")
            self.logger.exception(e, False)
            return []

    async def _create_entry_order(self, order_type, quantity, price, symbol_market, symbol, created_orders):
        for order_quantity, order_price in \
                trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                    quantity,
                    price,
                    symbol_market
                ):
            current_order = trading_personal_data.create_order_instance(
                trader=self.exchange_manager.trader,
                order_type=order_type,
                symbol=symbol,
                current_price=price,
                quantity=order_quantity,
                price=order_price
            )
            if created_order := await self._create_with_exit_orders(current_order, price, symbol_market):
                created_orders.append(created_order)
                return True
        return False

    async def _create_with_exit_orders(self, current_order, entry_price, symbol_market):
        params = {}
        chained_orders = []
        exit_side = trading_enums.TradeOrderSide.SELL if current_order.side is trading_enums.TradeOrderSide.BUY \
            else trading_enums.TradeOrderSide.BUY
        exit_multiplier_side_flag = 1 if exit_side is trading_enums.TradeOrderSide.SELL else -1
        total_exists_count = 1 + self.trading_mode.secondary_exit_orders_count
        can_bundle_exit_orders = total_exists_count == 1
        stop_price = entry_price * (
            trading_constants.ONE - (
                self.trading_mode.stop_loss_price_multiplier * exit_multiplier_side_flag
            )
        )
        first_sell_price = entry_price * (
            trading_constants.ONE + (
                self.trading_mode.exit_limit_orders_price_multiplier * exit_multiplier_side_flag
            )
        )
        last_sell_price = entry_price * (
            trading_constants.ONE + (
                self.trading_mode.secondary_exit_orders_price_multiplier *
                (1 + self.trading_mode.secondary_exit_orders_count) * exit_multiplier_side_flag
            )
        )
        # split entry into multiple exits if necessary (and possible)
        for i, exit_quantity in self._split_entry_quantity(
            current_order, total_exists_count,
            min(stop_price, first_sell_price, last_sell_price),
            max(stop_price, first_sell_price, last_sell_price),
            symbol_market
        ):
            # stop loss
            if self.trading_mode.use_stop_loss:
                stop_price = trading_personal_data.decimal_adapt_price(symbol_market, stop_price)
                param_update, chained_order = await self.register_chained_order(
                    current_order, stop_price, trading_enums.TraderOrderType.STOP_LOSS, exit_side,
                    quantity=exit_quantity, allow_bundling=can_bundle_exit_orders
                )
                params.update(param_update)
                chained_orders.append(chained_order)

            # take profit
            take_profit_multiplier = self.trading_mode.exit_limit_orders_price_multiplier \
                if i == 1 else self.trading_mode.secondary_exit_orders_price_multiplier * i
            take_profit_price = trading_personal_data.decimal_adapt_price(
                symbol_market,
                entry_price * (
                    trading_constants.ONE + (take_profit_multiplier * exit_multiplier_side_flag)
                )
            )
            take_profit_order_type = trading_enums.TraderOrderType.BUY_LIMIT \
                if exit_side is trading_enums.TradeOrderSide.BUY else trading_enums.TraderOrderType.SELL_LIMIT
            param_update, chained_order = await self.register_chained_order(
                current_order, take_profit_price, take_profit_order_type, None,
                quantity=exit_quantity, allow_bundling=can_bundle_exit_orders
            )
            params.update(param_update)
            chained_orders.append(chained_order)
        if len(chained_orders) > 1:
            oco_group = self.exchange_manager.exchange_personal_data.orders_manager \
                .create_group(trading_personal_data.OneCancelsTheOtherOrderGroup)
            for order in chained_orders:
                order.add_to_order_group(oco_group)
        return await self.trading_mode.create_order(current_order, params=params or None)

    @staticmethod
    def _split_entry_quantity(entry_order, target_exits_count, lowest_price, highest_price, symbol_market):
        if target_exits_count == 1:
            return [(1, entry_order.origin_quantity)]
        adapted_sell_orders_count, increment = trading_personal_data.get_split_orders_count_and_increment(
            lowest_price, highest_price, entry_order.origin_quantity, target_exits_count, symbol_market
        )
        if adapted_sell_orders_count:
            return [
                (i + 1, entry_order.origin_quantity / adapted_sell_orders_count)
                for i in range(adapted_sell_orders_count)
            ]
        else:
            return []

    async def can_create_order(self, symbol, state):
        can_create_order_result = await super().can_create_order(symbol, state)
        if not can_create_order_result:
            market = symbol_util.parse_symbol(symbol).quote
            self.logger.error(f"Can't create order : not enough balance. Please get more {market}.")
        return can_create_order_result


class DCATradingModeProducer(trading_modes.AbstractTradingModeProducer):
    MINUTES_BEFORE_NEXT_BUY = "minutes_before_next_buy"
    TRIGGER_MODE = "trigger_mode"
    
    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)
        self.task = None
        self.state = trading_enums.EvaluatorStates.NEUTRAL

    async def stop(self):
        if self.trading_mode is not None:
            self.trading_mode.flush_trading_mode_consumers()
        if self.task is not None:
            self.task.cancel()
        await super().stop()

    async def set_final_eval(self, matrix_id: str, cryptocurrency: str, symbol: str, time_frame, trigger_source: str):
        evaluations = []
        # Strategies analysis
        for evaluated_strategy_node in matrix.get_tentacles_value_nodes(
                matrix_id,
                matrix.get_tentacle_nodes(matrix_id,
                                          exchange_name=self.exchange_name,
                                          tentacle_type=evaluators_enums.EvaluatorMatrixTypes.STRATEGIES.value),
                cryptocurrency=cryptocurrency,
                symbol=symbol):

            if evaluators_util.check_valid_eval_note(evaluators_api.get_value(evaluated_strategy_node),
                                                     evaluators_api.get_type(evaluated_strategy_node),
                                                     evaluators_constants.EVALUATOR_EVAL_DEFAULT_TYPE):
                evaluations.append(evaluators_api.get_value(evaluated_strategy_node))

        if evaluations:
            state = trading_enums.EvaluatorStates.NEUTRAL
            if all(
                evaluation == -1
                for evaluation in evaluations
            ):
                state = trading_enums.EvaluatorStates.VERY_LONG
            elif all(
                evaluation == 1
                for evaluation in evaluations
            ):
                state = trading_enums.EvaluatorStates.VERY_SHORT
            self.final_eval = evaluations
            await self.trigger_dca_for_symbol(cryptocurrency=cryptocurrency, symbol=symbol, state=state)

    @classmethod
    def get_should_cancel_loaded_orders(cls) -> bool:
        """
        Called by cancel_symbol_open_orders => return true if OctoBot should cancel all orders for a symbol including
        orders already existing when OctoBot started up
        """
        return True

    async def trigger_dca_for_symbol(self, cryptocurrency, symbol, state):
        self.state = state
        self.logger.debug(
            f"{symbol} DCA task triggered on {self.exchange_manager.exchange_name}, state: {self.state.value}"
        )
        if self.state is not trading_enums.EvaluatorStates.NEUTRAL:
            # cancel existing DCA orders from previous signals
            await self.cancel_symbol_open_orders(symbol)
            # call orders creation from consumers
            await self.submit_trading_evaluation(
                cryptocurrency=cryptocurrency,
                symbol=symbol,
                time_frame=None,
                final_note=None,
                state=state
            )

            # send_notification
            if not self.exchange_manager.is_backtesting:
                await self._send_alert_notification(symbol, state)

    async def dca_task(self):
        while not self.should_stop:
            try:
                for cryptocurrency, pairs in trading_util.get_traded_pairs_by_currency(
                        self.exchange_manager.config
                ).items():
                    if self.symbol in pairs:
                        await self.trigger_dca_for_symbol(
                            cryptocurrency=cryptocurrency,
                            symbol=self.symbol,
                            state=trading_enums.EvaluatorStates.VERY_LONG
                        )

                await asyncio.sleep(self.trading_mode.minutes_before_next_buy)
            except Exception as e:
                self.logger.error(f"An error happened during DCA task : {e}")

    async def inner_start(self) -> None:
        await super().inner_start()
        self.task = asyncio.create_task(self.delayed_start())

    def get_channels_registration(self):
        registration_channels = []
        if self.trading_mode.trigger_mode is TriggerMode.MAXIMUM_EVALUATORS_SIGNALS_BASED:
            topic = self.trading_mode.trading_config.get(commons_constants.CONFIG_ACTIVATION_TOPICS.replace(" ", "_"),
                                                         commons_enums.ActivationTopics.EVALUATION_CYCLE.value)
            try:
                registration_channels.append(self.TOPIC_TO_CHANNEL_NAME[topic])
            except KeyError:
                self.logger.error(f"Unknown registration topic: {topic}")
        return registration_channels

    async def delayed_start(self):
        await self._wait_for_bot_init(
            self.CONFIG_INIT_TIMEOUT, extra_topics=[commons_enums.InitializationEventExchangeTopics.PRICE.value]
        )
        await self.dca_task()

    async def _send_alert_notification(self, symbol, state):
        try:
            import octobot_services.api as services_api
            import octobot_services.enums as services_enum
            action = "unknown"
            if state in (trading_enums.EvaluatorStates.LONG, trading_enums.EvaluatorStates.VERY_LONG):
                action = "BUYING"
            elif state in (trading_enums.EvaluatorStates.SHORT, trading_enums.EvaluatorStates.VERY_SHORT):
                action = "SELLING"
            title = f"DCA trigger for : #{symbol}"
            alert = f"{action} on {self.exchange_manager.exchange_name}"
            await services_api.send_notification(services_api.create_notification(
                alert, title=title, markdown_text=alert,
                category=services_enum.NotificationCategory.PRICE_ALERTS
            ))
        except ImportError as e:
            self.logger.exception(e, True, f"Impossible to send notification: {e}")


class DCATradingMode(trading_modes.AbstractTradingMode):
    MODE_PRODUCER_CLASSES = [DCATradingModeProducer]
    MODE_CONSUMER_CLASSES = [DCATradingModeConsumer]

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.use_market_entry_orders = False
        self.trigger_mode = TriggerMode.TIME_BASED
        self.minutes_before_next_buy = None

        self.entry_limit_orders_price_multiplier = DCATradingModeConsumer.DEFAULT_ENTRY_LIMIT_PRICE_MULTIPLIER
        self.use_secondary_entry_orders = False
        self.secondary_entry_orders_count = DCATradingModeConsumer.DEFAULT_SECONDARY_ENTRY_ORDERS_COUNT
        self.secondary_entry_orders_amount = DCATradingModeConsumer.DEFAULT_SECONDARY_ENTRY_ORDERS_AMOUNT
        self.secondary_entry_orders_price_multiplier = DCATradingModeConsumer.DEFAULT_ENTRY_LIMIT_PRICE_MULTIPLIER

        self.exit_limit_orders_price_multiplier = DCATradingModeConsumer.DEFAULT_EXIT_LIMIT_PRICE_MULTIPLIER
        self.use_secondary_exit_orders = False
        self.secondary_exit_orders_count = DCATradingModeConsumer.DEFAULT_SECONDARY_EXIT_ORDERS_COUNT
        self.secondary_exit_orders_amount = DCATradingModeConsumer.DEFAULT_SECONDARY_EXIT_ORDERS_AMOUNT
        self.secondary_exit_orders_price_multiplier = DCATradingModeConsumer.DEFAULT_ENTRY_LIMIT_PRICE_MULTIPLIER

        self.use_stop_loss = False
        self.stop_loss_price_multiplier = DCATradingModeConsumer.DEFAULT_STOP_LOSS_ORDERS_PRICE_MULTIPLIER

    def init_user_inputs(self, inputs: dict) -> None:
        """
        Called right before starting the tentacle, should define all the tentacle's user inputs unless
        those are defined somewhere else.
        """
        self.trigger_mode = TriggerMode(
            self.UI.user_input(
                DCATradingModeProducer.TRIGGER_MODE, commons_enums.UserInputTypes.OPTIONS, self.trigger_mode.value,
                inputs, options=[mode.value for mode in TriggerMode],
                title="Trigger mode: When should DCA entry orders should be triggered."
            )
        )
        self.minutes_before_next_buy = int(self.UI.user_input(
            DCATradingModeProducer.MINUTES_BEFORE_NEXT_BUY, commons_enums.UserInputTypes.INT, 60, inputs,
            min_val=1,
            title="Tigger period: Minutes to wait between each transaction. Examples: 60 for 1 hour, 1440 for 1 day, "
                  "10080 for 1 week or 43200 for 1 month.",
            editor_options={
                commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                  DCATradingModeProducer.TRIGGER_MODE: TriggerMode.TIME_BASED.value
                }
            }
        ))
        trading_modes.user_select_order_amount(self, inputs, include_sell=False)
        self.use_market_entry_orders = self.UI.user_input(
            DCATradingModeConsumer.USE_MARKET_ENTRY_ORDERS, commons_enums.UserInputTypes.BOOLEAN, False, inputs,
            title="Use market orders instead of limit orders."
        )
        self.entry_limit_orders_price_multiplier = decimal.Decimal(str(
            self.UI.user_input(
                DCATradingModeConsumer.ENTRY_LIMIT_ORDERS_PRICE_PERCENT, commons_enums.UserInputTypes.FLOAT,
                float(self.entry_limit_orders_price_multiplier * trading_constants.ONE_HUNDRED), inputs,
                min_val=0,
                title="Limit entry percent difference: Price difference in percent to compute the entry price from "
                      "when using limit orders. "
                      "Example: 10 on a 2000 USDT price buy would create a buy limit price at 1800 USDT or "
                      "a sell limit price at 2200 USDT.",
                editor_options={
                    commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                        DCATradingModeConsumer.USE_MARKET_ENTRY_ORDERS: False
                    }
                }
            )
        )) / trading_constants.ONE_HUNDRED
        self.use_secondary_entry_orders = self.UI.user_input(
            DCATradingModeConsumer.USE_SECONDARY_ENTRY_ORDERS, commons_enums.UserInputTypes.BOOLEAN,
            self.use_secondary_entry_orders, inputs,
            title="Enable secondary entry orders: Split entry into multiple orders using different prices."
        )
        self.secondary_entry_orders_count = self.UI.user_input(
            DCATradingModeConsumer.SECONDARY_ENTRY_ORDERS_COUNT, commons_enums.UserInputTypes.INT,
            self.secondary_entry_orders_count, inputs,
            title="Secondary entry orders count: Number of secondary limit orders to create alongside the initial "
                  "entry order.",
            editor_options={
                commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                    DCATradingModeConsumer.USE_SECONDARY_ENTRY_ORDERS: True
                }
            }
        )
        self.secondary_entry_orders_price_multiplier = decimal.Decimal(str(
            self.UI.user_input(
                DCATradingModeConsumer.SECONDARY_ENTRY_ORDERS_PRICE_PERCENT, commons_enums.UserInputTypes.FLOAT,
                float(self.secondary_entry_orders_price_multiplier * trading_constants.ONE_HUNDRED), inputs,
                title="Secondary entry orders price interval percent: Price difference in percent to compute the "
                      "price of secondary entry orders compared to the price of the initial entry order. "
                      "Example: 10 on a 1800 USDT entry buy price would create secondary entry buy orders "
                      "at 1600 USDT, 1400 USDT and so on.",
                editor_options={
                    commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                        DCATradingModeConsumer.USE_SECONDARY_ENTRY_ORDERS: True
                    }
                }
            )
        )) / trading_constants.ONE_HUNDRED
        self.UI.user_input(
            DCATradingModeConsumer.SECONDARY_ENTRY_ORDERS_AMOUNT, commons_enums.UserInputTypes.TEXT, "", inputs,
            title=f"Secondary entry orders amount: {trading_modes.get_order_amount_value_desc()}",
            other_schema_values={"minLength": 0},
            editor_options={
                commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                    DCATradingModeConsumer.USE_SECONDARY_ENTRY_ORDERS: True
                }
            }
        )
        self.exit_limit_orders_price_multiplier = decimal.Decimal(str(
            self.UI.user_input(
                DCATradingModeConsumer.EXIT_LIMIT_ORDERS_PRICE_PERCENT, commons_enums.UserInputTypes.FLOAT,
                float(self.exit_limit_orders_price_multiplier * trading_constants.ONE_HUNDRED), inputs,
                min_val=0,
                title="Limit exit percent difference: Price difference in percent to compute the exit price from "
                      "after an entry is filled. "
                      "Example: 10 on a 2000 USDT filled price buy would create a sell limit price at 2200 USDT.",
            )
        )) / trading_constants.ONE_HUNDRED
        self.use_secondary_exit_orders = self.UI.user_input(
            DCATradingModeConsumer.USE_SECONDARY_EXIT_ORDERS, commons_enums.UserInputTypes.BOOLEAN,
            self.use_secondary_exit_orders, inputs,
            title="Enable secondary exit orders: Split each filled entry order into into multiple exit orders using "
                  "different prices."
        )
        self.secondary_entry_orders_count = self.UI.user_input(
            DCATradingModeConsumer.SECONDARY_EXIT_ORDERS_COUNT, commons_enums.UserInputTypes.INT,
            self.secondary_entry_orders_count, inputs,
            title="Secondary exit orders count: Number of secondary limit orders to create additionally to "
                  "the initial exit order. When enabled, the entry filled amount is split into each exit orders.",
            editor_options={
                commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                    DCATradingModeConsumer.USE_SECONDARY_EXIT_ORDERS: True
                }
            }
        )
        self.secondary_exit_orders_price_multiplier = decimal.Decimal(str(
            self.UI.user_input(
                DCATradingModeConsumer.SECONDARY_EXIT_ORDERS_PRICE_PERCENT, commons_enums.UserInputTypes.FLOAT,
                float(self.secondary_exit_orders_price_multiplier * trading_constants.ONE_HUNDRED), inputs,
                title="Secondary exit orders price interval percent: Price difference in percent to compute the "
                      "price of secondary exit orders compared to the price of the associated entry order. "
                      "Example: 10 on a 2000 USDT exit sell price would create secondary exit sell orders "
                      "at 2200 USDT, 2400 USDT and so on.",
                editor_options={
                    commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                        DCATradingModeConsumer.USE_SECONDARY_EXIT_ORDERS: True
                    }
                }
            )
        )) / trading_constants.ONE_HUNDRED
        self.use_stop_loss = self.UI.user_input(
            DCATradingModeConsumer.USE_STOP_LOSSES, commons_enums.UserInputTypes.BOOLEAN, self.use_stop_loss, inputs,
            title="Enable stop losses: Create a stop loss alongside exit orders.",
        )
        self.stop_loss_price_multiplier = decimal.Decimal(str(
            self.UI.user_input(
                DCATradingModeConsumer.STOP_LOSS_PRICE_PERCENT, commons_enums.UserInputTypes.FLOAT,
                float(self.stop_loss_price_multiplier * trading_constants.ONE_HUNDRED), inputs, min_val=0, max_val=100,
                title="Stop loss price percent: maximum percent losses to compute the stop loss price from. "
                      "Example: a buy entry filled at 2000 with a Stop loss percent at"
                      " 15 will create a stop order at 1700.",
                editor_options={
                    commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                      DCATradingModeConsumer.USE_STOP_LOSSES: True
                    }
                }
            )
        )) / trading_constants.ONE_HUNDRED

    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        return False

    def get_current_state(self) -> (str, float):
        return super().get_current_state()[0] if self.producers[0].state is None else self.producers[0].state.name, \
               ",".join([str(e) for e in self.producers[0].final_eval] if self.producers[0].final_eval else
                        self.producers[0].final_eval)
