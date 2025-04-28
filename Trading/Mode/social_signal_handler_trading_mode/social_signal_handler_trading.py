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

import octobot_commons.pretty_printer as pretty_printer
import async_channel.constants as channel_constants

import octobot_trading.personal_data as trading_personal_data
import octobot_trading.enums as trading_enums
import octobot_trading.modes as trading_modes
import octobot_trading.constants as trading_constants
import octobot_trading.exchange_channel as exchanges_channel


class SocialSignalHandlerTradingModeConsumer(trading_modes.AbstractTradingModeConsumer):

    def __init__(self, trading_mode):
        super().__init__(trading_mode)
        trading_config = self.trading_mode.trading_config if self.trading_mode else {}

        self.BUY_WITH_MAXIMUM_SIZE_ORDERS = trading_config.get("buy_with_maximum_size_orders", False)
        self.SELL_WITH_MAXIMUM_SIZE_ORDERS = trading_config.get("sell_with_maximum_size_orders", False)

    async def create_new_orders(self, symbol, final_note, state, **kwargs):
        timeout = kwargs.pop("timeout", trading_constants.ORDER_DATA_FETCHING_TIMEOUT)
        try:
            current_symbol_holding, current_market_holding, market_quantity, price, symbol_market = \
                await trading_personal_data.get_pre_order_data(self.exchange_manager, symbol=symbol, timeout=timeout)
            created_orders = []

            market_quantity *= 0.99
            if state == trading_enums.EvaluatorStates.VERY_LONG.value:
                for order_quantity, order_price in trading_personal_data.check_and_adapt_order_details_if_necessary(
                        market_quantity, price,
                        symbol_market):
                    current_order = trading_personal_data.create_order_instance(trader=self.exchange_manager.trader,
                                                                                order_type=trading_enums.TraderOrderType.BUY_MARKET,
                                                                                symbol=symbol,
                                                                                current_price=order_price,
                                                                                quantity=order_quantity,
                                                                                price=order_price)
                    await self.exchange_manager.trader.create_order(current_order)
                    created_orders.append(current_order)
            return created_orders
        except Exception as e:
            self.logger.exception(e, True, f"Failed to create order : {e}.")
            return []


class SocialSignalHandlerTradingModeProducer(trading_modes.AbstractTradingModeProducer):
    TAKE_PROFITS_INCREMENTS = [1.2, 1.5, 2.0, 2.5, 3.0]

    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)
        self.state = None

    def is_cryptocurrency_wildcard(self):
        return True

    def is_symbol_wildcard(self):
        return True

    async def set_final_eval(self, matrix_id: str, cryptocurrency: str, symbol: str, time_frame):
        self.state = trading_enums.EvaluatorStates.VERY_LONG
        self.logger.info(f"[{symbol}] new state: {self.state.name}")

        # call orders creation from consumers
        await self.submit_trading_evaluation(cryptocurrency=cryptocurrency,
                                             symbol=symbol,
                                             time_frame=None,
                                             final_note=self.final_eval,
                                             state=self.state)

        # send_notification
        if not self.exchange_manager.is_backtesting:
            await self._send_alert_notification(symbol, self.state)

    async def order_callback(self, order):
        # Ensure order market has not expired
        if order[trading_enums.ExchangeConstantsOrderColumns.STATUS.value] == trading_enums.OrderStatus.EXPIRED.value:
            current_order = trading_personal_data.create_order_instance(
                trader=self.exchange_manager.trader,
                order_type=trading_enums.TraderOrderType.BUY_MARKET,
                symbol=order[trading_enums.ExchangeConstantsOrderColumns.SYMBOL.value],
                current_price=decimal.Decimal(str(order[trading_enums.ExchangeConstantsOrderColumns.PRICE.value])),
                quantity=decimal.Decimal(str(order[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value])),
                price=decimal.Decimal(str(order[trading_enums.ExchangeConstantsOrderColumns.PRICE.value])))
            await self.exchange_manager.trader.create_order(current_order)

        # When buy market order is filled
        if order[trading_enums.ExchangeConstantsOrderColumns.STATUS.value] == trading_enums.OrderStatus.FILLED.value:
            # create order on the order side
            symbol = order[trading_enums.ExchangeConstantsOrderColumns.SYMBOL.value]
            filled_price = decimal.Decimal(str(order[trading_enums.ExchangeConstantsOrderColumns.PRICE.value]))
            filled_volume = decimal.Decimal(str(order[trading_enums.ExchangeConstantsOrderColumns.FILLED.value]))
            symbol_market_status = self.exchange_manager.exchange.get_market_status(symbol, with_fixer=False)
            created_orders = []
            for increment in self.TAKE_PROFITS_INCREMENTS:
                created_orders.append(await self.create_take_profit_order(
                    filled_volume, filled_price, increment, symbol_market_status))

    async def create_take_profit_order(self, filled_quantity, filled_price, increment, symbol, symbol_market_status):
        quantity_to_sell = filled_quantity / len(self.TAKE_PROFITS_INCREMENTS)
        price_to_sell = filled_price * decimal.Decimal(str(increment))
        created_orders = []
        for order_quantity, order_price in trading_personal_data.check_and_adapt_order_details_if_necessary(
                quantity_to_sell, price_to_sell, symbol_market_status):
            current_order = trading_personal_data.create_order_instance(trader=self.exchange_manager.trader,
                                                                        order_type=trading_enums.TraderOrderType.SELL_LIMIT,
                                                                        symbol=symbol,
                                                                        current_price=order_price,
                                                                        quantity=order_quantity,
                                                                        price=order_price)
            await self.exchange_manager.trader.create_order(current_order)
            created_orders.append(current_order)
        return created_orders

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return False

    async def _send_alert_notification(self, symbol, new_state):
        try:
            import octobot_services.api as services_api
            import octobot_services.enums as services_enum
            title = f"Social signal received on #{symbol}"
            alert_content, alert_content_markdown = pretty_printer.cryptocurrency_alert(
                new_state,
                self.final_eval)
            await services_api.send_notification(services_api.create_notification(
                alert_content, title=title, markdown_text=alert_content_markdown,
                category=services_enum.NotificationCategory.PRICE_ALERTS))
        except ImportError as e:
            self.logger.exception(e, True, f"Impossible to send notification: {e}")


class SocialSignalHandlerTradingMode(trading_modes.AbstractTradingMode):
    MODE_PRODUCER_CLASSES = [SocialSignalHandlerTradingModeProducer]
    MODE_CONSUMER_CLASSES = [SocialSignalHandlerTradingModeConsumer]

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.load_config()

    async def create_consumers(self) -> list:
        consumers = await super().create_consumers()

        # order consumer: filter by symbol not be triggered only on this symbol's orders
        order_consumer = await exchanges_channel.get_chan(trading_personal_data.OrdersChannel.get_name(),
                                                          self.exchange_manager.id).new_consumer(
            self._order_notification_callback,
            symbol=self.symbol if self.symbol else channel_constants.CHANNEL_WILDCARD
        )
        consumers.append(order_consumer)
        return consumers

    async def _order_notification_callback(self, exchange, exchange_id,
                                           cryptocurrency, symbol, order, is_new, is_from_bot):
        await self.producers[0].order_callback(order)
