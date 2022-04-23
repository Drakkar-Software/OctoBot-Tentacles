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
import decimal

import async_channel.constants as channel_constants
import octobot_commons.channels_name as channels_name
import octobot_commons.constants as common_constants
import octobot_commons.tentacles_management as tentacles_management
import async_channel.channels as channels
import octobot_trading.constants as trading_constants
import octobot_trading.enums as trading_enums
import octobot_trading.modes as trading_modes
import octobot_trading.errors as errors
import octobot_trading.exchange_channel as exchanges_channel
import octobot_trading.signals as trading_signals
import octobot_trading.personal_data as personal_data
import octobot_trading.modes.script_keywords as script_keywords


class RemoteTradingSignalsTradingMode(trading_modes.AbstractTradingMode):

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.load_config()
        self.USE_MARKET_ORDERS = self.trading_config.get("use_market_orders", True)
        self.merged_symbol = None

    def get_current_state(self) -> (str, float):
        return super().get_current_state()[0] if self.producers[0].state is None else self.producers[0].state.name, \
               self.producers[0].final_eval

    async def create_producers(self) -> list:
        mode_producer = RemoteTradingSignalsModeProducer(
            exchanges_channel.get_chan(trading_constants.MODE_CHANNEL, self.exchange_manager.id),
            self.config, self, self.exchange_manager)
        await mode_producer.run()
        signal_producers = await self._subscribe_to_signal_feed()
        return [mode_producer] + signal_producers

    async def _subscribe_to_signal_feed(self):
        channel = await trading_signals.create_remote_trading_signal_channel_if_missing(
            self.exchange_manager
        )
        if self.exchange_manager.is_backtesting:
            # TODO: create and return producer simulator with this bot id
            raise NotImplementedError("signal producer simulator is not implemented")
            return []
        try:
            await channel.subscribe_to_product_feed(
                self.trading_config[common_constants.CONFIG_TRADING_SIGNALS_STRATEGY]
            )
        except Exception as e:
            self.logger.exception(e, True, f"Error while subscribing to signal feed: {e}. This trading mode won't "
                                           f"be operating")
        return []

    async def create_consumers(self) -> list:
        mode_consumer = RemoteTradingSignalsModeConsumer(self)
        await exchanges_channel.get_chan(trading_constants.MODE_CHANNEL, self.exchange_manager.id).new_consumer(
            consumer_instance=mode_consumer,
            trading_mode_name=self.get_name(),
            cryptocurrency=self.cryptocurrency if self.cryptocurrency else channel_constants.CHANNEL_WILDCARD,
            symbol=self.symbol if self.symbol else channel_constants.CHANNEL_WILDCARD,
            time_frame=self.time_frame if self.time_frame else channel_constants.CHANNEL_WILDCARD)
        signals_consumer = await channels.get_chan(
            channels_name.OctoBotCommunityChannelsName.REMOTE_TRADING_SIGNALS_CHANNEL.value)\
            .new_consumer(
                self._remote_trading_signal_callback,
                strategy=self.trading_config[common_constants.CONFIG_TRADING_SIGNALS_STRATEGY],
                exchange=self.exchange_manager.exchange_name,
                symbol=self.symbol,
                bot_id=self.bot_id
            )
        return [mode_consumer, signals_consumer]

    async def _remote_trading_signal_callback(self, strategy, exchange, symbol, version, bot_id, signal):
        self.logger.info(f"received signal: {signal}")
        await self.producers[0].signal_callback(signal)
        self.logger.info("done")

    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        return False

    @staticmethod
    def is_backtestable():
        return False


class RemoteTradingSignalsModeConsumer(trading_modes.AbstractTradingModeConsumer):
    def __init__(self, trading_mode):
        super().__init__(trading_mode)

    async def internal_callback(self, trading_mode_name, cryptocurrency, symbol, time_frame, final_note, state,
                                data):
        # creates a new order (or multiple split orders), always check self.can_create_order() first.
        try:
            await self._handle_signal_orders(data)
        except errors.MissingMinimalExchangeTradeVolume:
            self.logger.info(f"Not enough funds to create a new order: {self.exchange_manager.exchange_name} "
                             f"exchange minimal order volume has not been reached.")
        except Exception as e:
            self.logger.exception(e, True, f"Error when handling remote signal orders: {e}")

    async def _handle_signal_orders(self, signal):
        to_create_orders_descriptions, to_edit_orders_descriptions, \
            to_cancel_orders_descriptions, to_group_orders_descriptions = \
            self._parse_signal_orders(signal)
        await self._group_orders(to_group_orders_descriptions, signal.symbol)
        cancelled_count = await self._cancel_orders(to_cancel_orders_descriptions, signal.symbol)
        edited_count = await self._edit_orders(to_edit_orders_descriptions, signal.symbol)
        created_count = await self._create_orders(to_create_orders_descriptions, signal.symbol)

        # send_notification
        if not self.exchange_manager.is_backtesting:
            await self._send_alert_notification(signal.symbol, created_count, edited_count, cancelled_count)

    async def _group_orders(self, orders_descriptions, symbol):
        for order_description, order in self.get_open_order_from_description(orders_descriptions, symbol):
            order_group = self._get_or_create_order_group(
                order_description,
                order_description[trading_enums.TradingSignalOrdersAttrs.GROUP_ID.value])
            order.add_to_order_group(order_group)

    async def _cancel_orders(self, orders_descriptions, symbol):
        cancelled_count = 0
        for _, order in self.get_open_order_from_description(orders_descriptions, symbol):
            await self.exchange_manager.trader.cancel_order(order)
            cancelled_count += 1
        return cancelled_count

    async def _edit_orders(self, orders_descriptions, symbol):
        edited_count = 0
        for order_description, order in self.get_open_order_from_description(orders_descriptions, symbol):
            edited_price = order_description[trading_enums.TradingSignalOrdersAttrs.UPDATED_LIMIT_PRICE.value]
            edited_stop_price = order_description[trading_enums.TradingSignalOrdersAttrs.UPDATED_STOP_PRICE.value]
            edited_quantity, _ = await self._get_quantity_from_signal_percent(
                order_description, order.side, symbol, order.reduce_only, True
            )
            await self.exchange_manager.trader.edit_order(
                order,
                edited_quantity=decimal.Decimal(edited_quantity) if edited_quantity else None,
                edited_price=decimal.Decimal(edited_price) if edited_price else None,
                edited_stop_price=decimal.Decimal(edited_stop_price) if edited_stop_price else None
            )
            edited_count += 1
        return edited_count

    async def _get_quantity_from_signal_percent(self, order_description, side, symbol, reduce_only, update_amount):
        quantity_type, quantity = script_keywords.parse_quantity(
            order_description[
                trading_enums.TradingSignalOrdersAttrs.UPDATED_TARGET_AMOUNT.value
                if update_amount else trading_enums.TradingSignalOrdersAttrs.TARGET_AMOUNT.value
            ]
        )
        portfolio_type = common_constants.PORTFOLIO_TOTAL if quantity_type is script_keywords.QuantityType.PERCENT \
            else common_constants.PORTFOLIO_AVAILABLE
        current_symbol_holding, current_market_holding, market_quantity, current_price, symbol_market = \
            await personal_data.get_pre_order_data(self.exchange_manager, symbol=symbol,
                                                   timeout=trading_constants.ORDER_DATA_FETCHING_TIMEOUT,
                                                   portfolio_type=portfolio_type)
        if self.exchange_manager.is_future:
            position_percent = order_description[
                trading_enums.TradingSignalOrdersAttrs.UPDATED_TARGET_POSITION.value
                if update_amount else trading_enums.TradingSignalOrdersAttrs.TARGET_POSITION.value
            ]
            if position_percent is not None:
                quantity_type, quantity = script_keywords.parse_quantity(position_percent)
                if quantity_type is script_keywords.QuantityType.POSITION_PERCENT:
                    return self.exchange_manager.exchange_personal_data.positions_manager.get_symbol_position(
                        symbol,
                        trading_enums.PositionSide.BOTH
                    ) * quantity / trading_constants.ONE_HUNDRED, current_price
                raise errors.InvalidArgumentError(f"Unhandled position based quantity type: {position_percent}")
            max_order_size, _ = personal_data.get_futures_max_order_size(
                self.exchange_manager, symbol, side, current_price, reduce_only,
                current_symbol_holding, market_quantity
            )
        else:
            max_order_size = market_quantity if side is trading_enums.TradeOrderSide.BUY else current_symbol_holding
        return max_order_size * quantity / trading_constants.ONE_HUNDRED, current_price

    async def _bundle_order(self, order_description, to_create_orders, bundled_with, fees_currency_side,
                            created_groups, symbol):
        chained_order = await self._create_order(order_description, symbol, created_groups, fees_currency_side)
        main_order = to_create_orders[bundled_with][0]
        # always align bundled order quantity with the main order one
        chained_order.origin_quantity = main_order.origin_quantity
        params = await self.exchange_manager.trader.bundle_chained_order_with_uncreated_order(main_order, chained_order)
        to_create_orders[bundled_with][1].update(params)

    async def _chain_order(self, order_description, created_orders, chained_to, fees_currency_side,
                           created_groups, symbol, order_description_by_id):
        base_order = created_orders[chained_to]
        desc_base_order_quantity = \
            order_description_by_id[chained_to][trading_enums.TradingSignalOrdersAttrs.QUANTITY.value]
        desc_chained_order_quantity = order_description[trading_enums.TradingSignalOrdersAttrs.QUANTITY.value]
        # compute target quantity based on the base order's description quantity to keep accurate %
        target_quantity = decimal.Decimal(f"{desc_chained_order_quantity}") * base_order.origin_quantity / \
            decimal.Decimal(f"{desc_base_order_quantity}")
        chained_order = await self._create_order(
            order_description, symbol, created_groups, fees_currency_side, target_quantity=target_quantity
        )
        await chained_order.set_as_chained_order(base_order, False, {})
        base_order.add_chained_order(chained_order)
        if base_order.is_filled() and chained_order.should_be_created():
            await personal_data.create_as_chained_order(chained_order)
            return 1
        return 0

    async def _create_order(self, order_description, symbol, created_groups, fees_currency_side, target_quantity=None):
        group = None
        if group_id := order_description[trading_enums.TradingSignalOrdersAttrs.GROUP_ID.value]:
            group = created_groups[group_id]
        side = trading_enums.TradeOrderSide(order_description[trading_enums.TradingSignalOrdersAttrs.SIDE.value])
        reduce_only = order_description[trading_enums.TradingSignalOrdersAttrs.REDUCE_ONLY.value]
        quantity, current_price = await self._get_quantity_from_signal_percent(
            order_description, side, symbol, reduce_only, False
        )
        quantity = target_quantity or quantity
        symbol_market = self.exchange_manager.exchange.get_market_status(symbol, with_fixer=False)
        adapted_quantity = personal_data.decimal_adapt_quantity(symbol_market, quantity)
        price = order_description[trading_enums.TradingSignalOrdersAttrs.STOP_PRICE.value] \
            or order_description[trading_enums.TradingSignalOrdersAttrs.LIMIT_PRICE.value]
        adapted_price = personal_data.decimal_adapt_price(symbol_market, decimal.Decimal(f"{price}"))
        order_type = trading_enums.TraderOrderType(
                order_description[trading_enums.TradingSignalOrdersAttrs.TYPE.value]
            )
        if order_type in (trading_enums.TraderOrderType.BUY_MARKET, trading_enums.TraderOrderType.SELL_MARKET):
            # side param is not supported for these orders
            side = None
        order = personal_data.create_order_instance(
            trader=self.exchange_manager.trader,
            order_type=order_type,
            symbol=symbol,
            current_price=current_price,
            quantity=adapted_quantity,
            price=adapted_price,
            side=side,
            tag=order_description[trading_enums.TradingSignalOrdersAttrs.TAG.value],
            group=group,
            fees_currency_side=fees_currency_side,
            reduce_only=reduce_only
        )
        order.set_shared_signal_order_id(
            order_description[trading_enums.TradingSignalOrdersAttrs.SHARED_SIGNAL_ORDER_ID.value]
        )
        return order

    def _get_or_create_order_group(self, order_description, group_id):
        group_type = order_description[trading_enums.TradingSignalOrdersAttrs.GROUP_TYPE.value]
        group_class = tentacles_management.get_class_from_parent_subclasses(group_type, personal_data.OrderGroup)
        return self.exchange_manager.exchange_personal_data.orders_manager.get_or_create_group(group_class, group_id)

    async def _create_orders(self, orders_descriptions, symbol):
        to_create_orders = {}   # dict of (orders, orders_param)
        created_groups = {}
        created_orders = {}
        order_description_by_id = {
            orders_description[trading_enums.TradingSignalOrdersAttrs.SHARED_SIGNAL_ORDER_ID.value]: orders_description
            for orders_description in orders_descriptions
        }
        fees_currency_side = None
        if self.exchange_manager.is_future:
            fees_currency_side = self.exchange_manager.exchange.get_pair_future_contract(symbol)\
                .get_fees_currency_side()
        for order_description in orders_descriptions:
            if group_id := order_description[trading_enums.TradingSignalOrdersAttrs.GROUP_ID.value]:
                group = self._get_or_create_order_group(order_description, group_id)
                await group.enable(False)
                created_groups[group_id] = group
            if order_description[trading_enums.TradingSignalOrdersAttrs.BUNDLED_WITH.value] is not None:
                # bundled orders are created later on
                continue
            if order_description[trading_enums.TradingSignalOrdersAttrs.CHAINED_TO.value] is not None:
                # chained orders are created later on
                continue
            created_order = await self._create_order(order_description, symbol, created_groups, fees_currency_side)
            to_create_orders[order_description[trading_enums.TradingSignalOrdersAttrs.SHARED_SIGNAL_ORDER_ID.value]] = \
                (created_order, {})
        for order_description in orders_descriptions:
            if bundled_with := order_description[trading_enums.TradingSignalOrdersAttrs.BUNDLED_WITH.value]:
                await self._bundle_order(order_description, to_create_orders, bundled_with, fees_currency_side,
                                         created_groups, symbol)
        # create orders
        for shared_signal_order_id, order_with_param in to_create_orders.items():
            created_orders[shared_signal_order_id] = \
                await self.exchange_manager.trader.create_order(order_with_param[0], params=order_with_param[1])
        # handle chained orders
        created_chained_orders_count = 0
        for order_description in orders_descriptions:
            if (chained_to := order_description[trading_enums.TradingSignalOrdersAttrs.CHAINED_TO.value]) \
                    and order_description[trading_enums.TradingSignalOrdersAttrs.BUNDLED_WITH.value] is None:
                created_chained_orders_count += \
                    await self._chain_order(order_description, created_orders, chained_to, fees_currency_side,
                                            created_groups, symbol, order_description_by_id)

        for group in created_groups.values():
            await group.enable(True)
        return len(to_create_orders) + created_chained_orders_count

    def get_open_order_from_description(self, order_descriptions, symbol):
        found_orders = []
        for order_description in order_descriptions:
            # filter orders using shared_signal_order_id
            if accurate_orders := [
                (order_description, order)
                for order in self.exchange_manager.exchange_personal_data.orders_manager.get_open_orders(symbol=symbol)
                if order.shared_signal_order_id == order_description[
                    trading_enums.TradingSignalOrdersAttrs.SHARED_SIGNAL_ORDER_ID.value]
            ]:
                found_orders += accurate_orders
                continue
            # 2nd chance: use order type and price as these are kept between bot restarts (loaded from exchange)
            found_orders += [
                (order_description, order)
                for order in self.exchange_manager.exchange_personal_data.orders_manager.get_open_orders(symbol=symbol)
                if (order.price == order_description[trading_enums.TradingSignalOrdersAttrs.STOP_PRICE.value] or
                    order.price == order_description[trading_enums.TradingSignalOrdersAttrs.LIMIT_PRICE.value])
                    and self._is_compatible_order_type(order, order_description)
            ]
        return found_orders

    def _is_compatible_order_type(self, order, order_description):
        side = order_description[trading_enums.TradingSignalOrdersAttrs.SIDE.value]
        if not order.side.value == side:
            return False
        order_type = order_description[trading_enums.TradingSignalOrdersAttrs.TYPE.value]
        return personal_data.TraderOrderTypeClasses[order_type] == order.__class__

    def _parse_signal_orders(self, signal):
        to_create_orders = []
        to_edit_orders = []
        to_cancel_orders = []
        to_group_orders = []
        for order_description in signal.orders:
            action = order_description.get(trading_enums.TradingSignalOrdersAttrs.ACTION.value)
            if action == trading_enums.TradingSignalOrdersActions.CREATE.value:
                to_create_orders.append(order_description)
            elif action == trading_enums.TradingSignalOrdersActions.EDIT.value:
                to_edit_orders.append(order_description)
            elif action == trading_enums.TradingSignalOrdersActions.CANCEL.value:
                to_cancel_orders.append(order_description)
            elif action == trading_enums.TradingSignalOrdersActions.ADD_TO_GROUP.value:
                to_group_orders.append(order_description)
        return to_create_orders, to_edit_orders, to_cancel_orders, to_group_orders

    async def _send_alert_notification(self, symbol, created, edited, cancelled):
        try:
            import octobot_services.api as services_api
            import octobot_services.enums as services_enum
            title = f"New trading signal for {symbol}"
            messages = []
            if created:
                messages.append(f"- Created {created} order{'s' if created > 1 else ''}")
            if edited:
                messages.append(f"- Edited {edited} order{'s' if edited > 1 else ''}")
            if cancelled:
                messages.append(f"- Cancelled {cancelled} order{'s' if cancelled > 1 else ''}")
            content = "\n".join(messages)
            await services_api.send_notification(services_api.create_notification(
                content, title=title,
                category=services_enum.NotificationCategory.TRADING_SCRIPT_ALERTS
            ))
        except ImportError as e:
            self.logger.exception(e, True, f"Impossible to send notification: {e}")


class RemoteTradingSignalsModeProducer(trading_modes.AbstractTradingModeProducer):

    def get_channels_registration(self):
        # trading mode is waking up this producer directly from signal channel
        return []

    async def signal_callback(self, signal):
        exchange_type = signal.exchange_type
        if exchange_type == trading_signals.get_signal_exchange_type(self.exchange_manager).value:
            state = trading_enums.EvaluatorStates(signal.state)
            await self._set_state(self.trading_mode.cryptocurrency, signal.symbol, state, signal)
        else:
            self.logger.error(f"Incompatible signal exchange type: {exchange_type} "
                              f"with current exchange: {self.exchange_manager}")

    async def _set_state(self, cryptocurrency: str, symbol: str, new_state, signal):
        self.state = new_state
        self.logger.info(f"[{symbol}] update state: {self.state.name}")
        # call orders creation from consumers
        await self.submit_trading_evaluation(cryptocurrency=cryptocurrency,
                                             symbol=symbol,
                                             time_frame=None,
                                             final_note=self.final_eval,
                                             state=self.state,
                                             data=signal)