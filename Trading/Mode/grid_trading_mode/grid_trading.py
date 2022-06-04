# Drakkar-Software OctoBot-Tentacles
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
import dataclasses
import decimal

import async_channel.constants as channel_constants
import async_channel.channels as channels
import octobot_commons.symbols.symbol_util as symbol_util
import octobot_services.channel as services_channels
import octobot_trading.api as trading_api
import octobot_trading.enums as trading_enums
import octobot_trading.exchange_channel as exchanges_channel
import octobot_trading.constants as trading_constants
import octobot_trading.personal_data as trading_personal_data
import tentacles.Trading.Mode.staggered_orders_trading_mode.staggered_orders_trading as staggered_orders_trading


@dataclasses.dataclass
class AllowedPriceRange:
    lower_bound: decimal.Decimal = trading_constants.ZERO
    higher_bound: decimal.Decimal = trading_constants.ZERO


class GridTradingMode(staggered_orders_trading.StaggeredOrdersTradingMode):
    CONFIG_FLAT_SPREAD = "flat_spread"
    CONFIG_FLAT_INCREMENT = "flat_increment"
    CONFIG_BUY_ORDERS_COUNT = "buy_orders_count"
    CONFIG_SELL_ORDERS_COUNT = "sell_orders_count"
    LIMIT_ORDERS_IF_NECESSARY = "limit_orders_if_necessary"
    USER_COMMAND_CREATE_ORDERS = "create initial orders"
    USER_COMMAND_STOP_ORDERS_CREATION = "stop initial orders creation"
    USER_COMMAND_PAUSE_ORDER_MIRRORING = "pause orders mirroring"
    USER_COMMAND_TRADING_PAIR = "trading pair"
    USER_COMMAND_PAUSE_TIME = "pause length in seconds"

    async def create_producers(self) -> list:
        mode_producer = GridTradingModeProducer(
            exchanges_channel.get_chan(trading_constants.MODE_CHANNEL, self.exchange_manager.id),
            self.config, self, self.exchange_manager)
        await mode_producer.run()
        return [mode_producer]

    async def create_consumers(self) -> list:
        # trading mode consumer
        mode_consumer = GridTradingModeConsumer(self)
        await exchanges_channel.get_chan(trading_constants.MODE_CHANNEL, self.exchange_manager.id).new_consumer(
            consumer_instance=mode_consumer,
            trading_mode_name=self.get_name(),
            cryptocurrency=self.cryptocurrency if self.cryptocurrency else channel_constants.CHANNEL_WILDCARD,
            symbol=self.symbol if self.symbol else channel_constants.CHANNEL_WILDCARD,
            time_frame=self.time_frame if self.time_frame else channel_constants.CHANNEL_WILDCARD)

        # order consumer: filter by symbol not be triggered only on this symbol's orders
        order_consumer = await exchanges_channel.get_chan(trading_personal_data.OrdersChannel.get_name(),
                                                          self.exchange_manager.id).new_consumer(
            self._order_notification_callback,
            symbol=self.symbol if self.symbol else channel_constants.CHANNEL_WILDCARD
        )
        try:
            user_commands_consumer = \
                await channels.get_chan(services_channels.UserCommandsChannel.get_name()).new_consumer(
                    self._user_commands_callback,
                    {"bot_id": self.bot_id, "subject": self.get_name()}
                )
        except KeyError:
            return [mode_consumer, order_consumer]
        return [mode_consumer, order_consumer, user_commands_consumer]

    async def _user_commands_callback(self, bot_id, subject, action, data) -> None:
        if data.get(GridTradingMode.USER_COMMAND_TRADING_PAIR, "").upper() == self.symbol:
            self.logger.info(f"Received {action} command for {self.symbol}.")
            if action == GridTradingMode.USER_COMMAND_CREATE_ORDERS:
                await self.producers[0].trigger_staggered_orders_creation()
            elif action == GridTradingMode.USER_COMMAND_STOP_ORDERS_CREATION:
                await self.consumers[0].cancel_orders_creation()
            elif action == GridTradingMode.USER_COMMAND_PAUSE_ORDER_MIRRORING:
                delay = float(data.get(GridTradingMode.USER_COMMAND_PAUSE_TIME, 0))
                self.producers[0].start_mirroring_pause(delay)

    @classmethod
    def get_user_commands(cls) -> dict:
        """
        Return the dict of user commands for this tentacle
        :return: the commands dict
        """
        return {
            GridTradingMode.USER_COMMAND_CREATE_ORDERS: {
                GridTradingMode.USER_COMMAND_TRADING_PAIR: "text"
            },
            GridTradingMode.USER_COMMAND_STOP_ORDERS_CREATION: {
                GridTradingMode.USER_COMMAND_TRADING_PAIR: "text"
            },
            GridTradingMode.USER_COMMAND_PAUSE_ORDER_MIRRORING: {
                GridTradingMode.USER_COMMAND_TRADING_PAIR: "text",
                GridTradingMode.USER_COMMAND_PAUSE_TIME: "number"
            }
        }


class GridTradingModeConsumer(staggered_orders_trading.StaggeredOrdersTradingModeConsumer):
    pass


class GridTradingModeProducer(staggered_orders_trading.StaggeredOrdersTradingModeProducer):
    # Disable health check
    HEALTH_CHECK_INTERVAL_SECS = None
    ORDERS_DESC = "grid"

    def __init__(self, channel, config, trading_mode, exchange_manager):
        self.buy_orders_count = self.sell_orders_count = None
        self.sell_price_range = AllowedPriceRange()
        self.buy_price_range = AllowedPriceRange()
        super().__init__(channel, config, trading_mode, exchange_manager)

    def read_config(self):
        self.mode = staggered_orders_trading.StrategyModes.FLAT
        # init decimals from str to remove native float rounding
        self.flat_spread = decimal.Decimal(str(self.symbol_trading_config[self.trading_mode.CONFIG_FLAT_SPREAD]))
        self.flat_increment = decimal.Decimal(str(self.symbol_trading_config[self.trading_mode.CONFIG_FLAT_INCREMENT]))
        # decimal.Decimal operations are supporting int values, no need to convert these into decimal.Decimal
        self.buy_orders_count = self.symbol_trading_config[self.trading_mode.CONFIG_BUY_ORDERS_COUNT]
        self.sell_orders_count = self.symbol_trading_config[self.trading_mode.CONFIG_SELL_ORDERS_COUNT]
        self.buy_funds = decimal.Decimal(str(self.symbol_trading_config.get(self.trading_mode.CONFIG_BUY_FUNDS,
                                                                            self.buy_funds)))
        self.sell_funds = decimal.Decimal(str(self.symbol_trading_config.get(self.trading_mode.CONFIG_SELL_FUNDS,
                                                                             self.sell_funds)))
        self.starting_price = decimal.Decimal(str(self.symbol_trading_config.get(self.trading_mode.CONFIG_STARTING_PRICE,
                                                                                 self.starting_price)))
        self.sell_volume_per_order = decimal.Decimal(str(self.symbol_trading_config.get(self.trading_mode.CONFIG_SELL_VOLUME_PER_ORDER,
                                                                                        self.sell_volume_per_order)))
        self.buy_volume_per_order = decimal.Decimal(str(self.symbol_trading_config.get(self.trading_mode.CONFIG_BUY_VOLUME_PER_ORDER,
                                                                                       self.buy_volume_per_order)))
        self.limit_orders_count_if_necessary = \
            self.symbol_trading_config.get(self.trading_mode.LIMIT_ORDERS_IF_NECESSARY, True)
        self.reinvest_profits = self.symbol_trading_config.get(self.trading_mode.CONFIG_REINVEST_PROFITS,
                                                               self.reinvest_profits)
        self.use_fixed_volume_for_mirror_orders = self.symbol_trading_config.get(
            self.trading_mode.CONFIG_USE_FIXED_VOLUMES_FOR_MIRROR_ORDERS,
            self.use_fixed_volume_for_mirror_orders
        )
        self.use_existing_orders_only = self.symbol_trading_config.get(self.trading_mode.CONFIG_USE_EXISTING_ORDERS_ONLY,
                                                                       self.use_existing_orders_only)
        self.mirror_order_delay = self.symbol_trading_config.get(self.trading_mode.CONFIG_MIRROR_ORDER_DELAY,
                                                                 self.mirror_order_delay)

    async def _handle_staggered_orders(self, current_price, ignore_mirror_orders_only, ignore_available_funds):
        self._init_allowed_price_ranges(current_price)
        if ignore_mirror_orders_only or not self.use_existing_orders_only:
            buy_orders, sell_orders = await self._generate_staggered_orders(current_price, ignore_available_funds)
            grid_orders = self._merged_and_sort_not_virtual_orders(buy_orders, sell_orders)
            async with self.exchange_manager.exchange_personal_data.portfolio_manager.portfolio.lock:
                await self._create_not_virtual_orders(grid_orders, current_price)

    async def trigger_staggered_orders_creation(self):
        # reload configuration
        self.trading_mode.load_config()
        self._load_symbol_trading_config()
        self.read_config()
        if self.symbol_trading_config:
            await self._ensure_staggered_orders(ignore_mirror_orders_only=True, ignore_available_funds=True)
        else:
            self.logger.error(f"No configuration for {self.symbol}")

    async def _generate_staggered_orders(self, current_price, ignore_available_funds):
        order_manager = self.exchange_manager.exchange_personal_data.orders_manager
        if not self.single_pair_setup:
            interfering_orders_pairs = self._get_interfering_orders_pairs(order_manager.get_open_orders())
            if interfering_orders_pairs:
                self.logger.error(f"Impossible to create grid orders for {self.symbol} with interfering orders "
                                  f"using pair(s): {interfering_orders_pairs}. Configure funds to use for each pairs "
                                  f"to be able to use interfering pairs.")
                return [], []
        existing_orders = order_manager.get_open_orders(self.symbol)

        sorted_orders = sorted(existing_orders, key=lambda order: order.origin_price)

        state = self.NEW
        missing_orders = []

        buy_orders = self._create_orders(self.buy_price_range.lower_bound, self.buy_price_range.higher_bound,
                                         trading_enums.TradeOrderSide.BUY, sorted_orders,
                                         current_price, missing_orders, state, self.buy_funds, ignore_available_funds)
        sell_orders = self._create_orders(self.sell_price_range.lower_bound, self.sell_price_range.higher_bound,
                                          trading_enums.TradeOrderSide.SELL, sorted_orders,
                                          current_price, missing_orders, state, self.sell_funds, ignore_available_funds)

        return buy_orders, sell_orders

    def _init_allowed_price_ranges(self, current_price):
        first_sell_price = current_price + (self.flat_spread / 2)
        self.sell_price_range.higher_bound = first_sell_price + (self.flat_increment * (self.sell_orders_count - 1))
        self.sell_price_range.lower_bound = max(current_price, first_sell_price)
        first_buy_price = current_price - (self.flat_spread / 2)
        self.buy_price_range.higher_bound = min(current_price, first_buy_price)
        self.buy_price_range.lower_bound = first_buy_price - (self.flat_increment * (self.buy_orders_count - 1))

    def _check_params(self):
        if self.flat_increment >= self.flat_spread:
            self.logger.error(f"Your flat_spread parameter should always be higher than your flat_increment"
                              f" parameter: average profit is spread-increment. ({self.symbol})")

    def _create_orders(self, lower_bound, upper_bound, side, sorted_orders,
                       current_price, missing_orders, state, allowed_funds, ignore_available_funds):

        if lower_bound >= upper_bound:
            self.logger.warning(f"No {side} orders for {self.symbol} possible: current price beyond boundaries.")
            return []

        orders = []
        selling = side == trading_enums.TradeOrderSide.SELL

        currency, market = symbol_util.parse_symbol(self.symbol).base_and_quote()
        order_limiting_currency = currency if selling else market

        order_limiting_currency_amount = trading_api.get_portfolio_currency(self.exchange_manager, order_limiting_currency).available
        if state == self.NEW:
            # create grid orders
            funds_to_use = self._get_maximum_traded_funds(allowed_funds,
                                                          order_limiting_currency_amount,
                                                          order_limiting_currency,
                                                          selling,
                                                          ignore_available_funds)
            if funds_to_use == 0:
                return []
            starting_bound = lower_bound if selling else upper_bound
            self._create_new_orders(orders, current_price, selling, lower_bound, upper_bound,
                                    funds_to_use, order_limiting_currency, starting_bound, side, False,
                                    self.mode, order_limiting_currency_amount)
        return orders

    def _get_order_count_and_average_quantity(self, current_price, selling, lower_bound, upper_bound, holdings,
                                              currency, mode):
        if lower_bound >= upper_bound:
            self.logger.error(f"Invalid bounds for {self.symbol}: too close to the current price")
            return 0, 0
        orders_count = self.sell_orders_count if selling else self.buy_orders_count
        if self._use_variable_orders_volume(trading_enums.TradeOrderSide.SELL if selling
           else trading_enums.TradeOrderSide.BUY):
            return self._ensure_average_order_quantity(orders_count, current_price, selling, holdings,
                                                       currency, mode)
        else:
            return self._get_orders_count_from_fixed_volume(selling, current_price, holdings, orders_count)
