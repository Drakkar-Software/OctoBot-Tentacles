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

import octobot_commons.symbols.symbol_util as symbol_util
import octobot_commons.enums as commons_enums

import octobot_trading.modes as trading_modes
import octobot_trading.enums as trading_enums
import octobot_trading.constants as trading_constants
import octobot_trading.util as trading_util
import octobot_trading.errors as trading_errors
import octobot_trading.personal_data as trading_personal_data


class DCATradingModeConsumer(trading_modes.AbstractTradingModeConsumer):
    AMOUNT_TO_BUY_IN_REF_MARKET = "amount_to_buy_in_reference_market"
    ORDER_PRICE_DISTANCE = decimal.Decimal(str(0.001))

    async def create_new_orders(self, symbol, final_note, state, **kwargs):
        current_order = None
        try:
            base, market = symbol_util.parse_symbol(symbol).base_and_quote()
            if market != self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market:
                self.logger.warning(f"Ignored DCA order creation on {symbol} : it's not a reference market pair.")
                return []

            current_symbol_holding, current_market_holding, market_quantity, price, symbol_market = \
                await trading_personal_data.get_pre_order_data(self.exchange_manager, symbol=symbol,
                                                               timeout=trading_constants.ORDER_DATA_FETCHING_TIMEOUT)

            created_orders = []
            orders_should_have_been_created = False
            quantity = self.trading_mode.order_quantity_of_ref_market / price
            limit_price = trading_personal_data.decimal_adapt_price(symbol_market, price * (trading_constants.ONE -
                                                                                            self.ORDER_PRICE_DISTANCE))
            for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                    quantity,
                    limit_price,
                    symbol_market):
                orders_should_have_been_created = True
                current_order = trading_personal_data.create_order_instance(trader=self.exchange_manager.trader,
                                                                            order_type=trading_enums.TraderOrderType.BUY_LIMIT,
                                                                            symbol=symbol,
                                                                            current_price=price,
                                                                            quantity=order_quantity,
                                                                            price=order_price)
                created_order = await self.exchange_manager.trader.create_order(current_order)
                created_orders.append(created_order)
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

    async def can_create_order(self, symbol, state):
        can_create_order_result = await super().can_create_order(symbol, state)
        if not can_create_order_result:
            market = symbol_util.parse_symbol(symbol).quote
            self.logger.error(f"Can't create order : not enough balance. Please get more {market}.")
        return can_create_order_result


class DCATradingModeProducer(trading_modes.AbstractTradingModeProducer):
    MINUTES_BEFORE_NEXT_BUY = "minutes_before_next_buy"
    
    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)
        self.task = None
        self.state = trading_enums.EvaluatorStates.LONG

    async def stop(self):
        if self.trading_mode is not None:
            self.trading_mode.flush_trading_mode_consumers()
        if self.task is not None:
            self.task.cancel()
        await super().stop()

    async def trigger_dca_for_symbol(self, cryptocurrency, symbol):
        # call orders creation from consumers
        await self.submit_trading_evaluation(cryptocurrency=cryptocurrency,
                                             symbol=symbol,
                                             time_frame=None,
                                             final_note=None,
                                             state=self.state)

        # send_notification
        if not self.exchange_manager.is_backtesting:
            await self._send_alert_notification(symbol)

    async def dca_task(self):
        while not self.should_stop:
            try:
                self.logger.info("DCA task triggered")

                for cryptocurrency, pairs in trading_util.get_traded_pairs_by_currency(
                        self.exchange_manager.config).items():
                    for pair in pairs:
                        await self.trigger_dca_for_symbol(cryptocurrency=cryptocurrency, symbol=pair)

                await asyncio.sleep(self.trading_mode.minutes_before_next_buy)
            except Exception as e:
                self.logger.error(f"An error happened during DCA task : {e}")

    async def start(self) -> None:
        self.task = await asyncio.create_task(self.delayed_start())

    async def delayed_start(self):
        # wait for portfolio to be fetched
        await asyncio.sleep(3)
        await self.dca_task()

    async def _send_alert_notification(self, symbol):
        try:
            import octobot_services.api as services_api
            import octobot_services.enums as services_enum
            title = f"DCA trigger for : #{symbol}"
            alert = "BUYING event"
            await services_api.send_notification(services_api.create_notification(alert, title=title,
                                                                                  markdown_text=alert,
                                                                                  category=services_enum.NotificationCategory.PRICE_ALERTS))
        except ImportError as e:
            self.logger.exception(e, True, f"Impossible to send notification: {e}")


class DCATradingMode(trading_modes.AbstractTradingMode):
    MODE_PRODUCER_CLASSES = [DCATradingModeProducer]
    MODE_CONSUMER_CLASSES = [DCATradingModeConsumer]

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.order_quantity_of_ref_market = None
        self.minutes_before_next_buy = None

    def init_user_inputs(self, inputs: dict) -> None:
        """
        Called right before starting the tentacle, should define all the tentacle's user inputs unless
        those are defined somewhere else.
        """
        self.order_quantity_of_ref_market = decimal.Decimal(str(self.UI.user_input(
            DCATradingModeConsumer.AMOUNT_TO_BUY_IN_REF_MARKET, commons_enums.UserInputTypes.FLOAT, 1, inputs,
            min_val=1,
            title="The amount of dollars (or unit of reference market) to buy on each transaction.",
        )))
        self.minutes_before_next_buy = int(self.UI.user_input(
            DCATradingModeProducer.MINUTES_BEFORE_NEXT_BUY, commons_enums.UserInputTypes.INT, 60, inputs,
            min_val=1,
            title="The amount of minutes to wait between each transaction (60 for 1 hour, 1440 for 1 day, "
                  "10080 for 1 week and 43200 1 month).",
        ))

    @staticmethod
    def is_backtestable():
        return False
