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

import octobot_commons.symbols.symbol_util as symbol_util
import octobot_commons.enums as commons_enums
import octobot_trading.api as trading_api
import octobot_trading.enums as trading_enums
import octobot_trading.constants as trading_constants
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

    def init_user_inputs(self, inputs: dict) -> None:
        """
        Called right before starting the tentacle, should define all the tentacle's user inputs unless
        those are defined somewhere else.
        """
        self.UI.user_input(self.CONFIG_PAIR_SETTINGS, commons_enums.UserInputTypes.OBJECT_ARRAY,
                           self.trading_config.get(self.CONFIG_PAIR_SETTINGS, None), inputs,
                           item_title="Pair configuration",
                           other_schema_values={"minItems": 1, "uniqueItems": True},
                           title="Configuration for each traded pairs.")
        self.UI.user_input(self.CONFIG_PAIR, commons_enums.UserInputTypes.TEXT, "BTC/USDT", inputs,
                           other_schema_values={"minLength": 3, "pattern": "([a-zA-Z]|\\d){2,}\\/([a-zA-Z]|\\d){2,}"},
                           parent_input_name=self.CONFIG_PAIR_SETTINGS,
                           title="Name of the traded pair."),
        self.UI.user_input(
            self.CONFIG_FLAT_SPREAD, commons_enums.UserInputTypes.FLOAT, 0.005, inputs,
            min_val=0, other_schema_values={"exclusiveMinimum": True},
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Spread: price difference between the closest buy and sell orders in the quote currency "
                  "(USDT for BTC/USDT).",
        )
        self.UI.user_input(
            self.CONFIG_FLAT_INCREMENT, commons_enums.UserInputTypes.FLOAT, 0.005, inputs,
            min_val=0, other_schema_values={"exclusiveMinimum": True},
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Increment: price difference between two orders of the same side in the base currency (USDT for "
                  "BTC/USDT). WARNING: this should be lower than the Spread value: profitability is close to "
                  "Spread-Increment.",
        )
        self.UI.user_input(
            self.CONFIG_BUY_ORDERS_COUNT, commons_enums.UserInputTypes.INT, 10, inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Buy orders count: number of initial buy orders to create. Make sure to have enough funds "
                  "to create that many orders.",
        )
        self.UI.user_input(
            self.CONFIG_SELL_ORDERS_COUNT, commons_enums.UserInputTypes.INT, 10, inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Sell orders count: Number of initial sell orders to create. Make sure to have enough funds "
                  "to create that many orders.",
        )
        self.UI.user_input(
            self.CONFIG_BUY_FUNDS, commons_enums.UserInputTypes.FLOAT, 0, inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="[Optional] Total buy funds: total funds to use for buy orders creation (in quote currency: USDT "
                  "for BTC/USDT). Set 0 to use all available funds in portfolio. Allows to use the same currency "
                  "simultaneously in multiple traded pairs.",
        )
        self.UI.user_input(
            self.CONFIG_SELL_FUNDS, commons_enums.UserInputTypes.FLOAT, 0, inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="[Optional] Total sell funds: total funds to use for sell orders creation (in base currency: "
                  "BTC for BTC/USDT). Set 0 to use all available funds in portfolio. Allows to use the same "
                  "currency simultaneously in multiple traded pairs.",
        )
        self.UI.user_input(
            self.CONFIG_STARTING_PRICE, commons_enums.UserInputTypes.FLOAT, 0, inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="[Optional] Starting price: price to compute initial orders from. Set 0 to use current "
                  "exchange price during initial grid orders creation.",
        )
        self.UI.user_input(
            self.CONFIG_BUY_VOLUME_PER_ORDER, commons_enums.UserInputTypes.FLOAT, 0, inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="[Optional] Buy orders volume: volume of each buy order in quote currency. Set 0 to use all "
                  "available base funds in portfolio (or total buy funds if set) to create orders with constant "
                  "total order cost (price * volume).",
        )
        self.UI.user_input(
            self.CONFIG_SELL_VOLUME_PER_ORDER, commons_enums.UserInputTypes.FLOAT, 0, inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="[Optional] Sell orders volume: volume of each sell order in quote currency. Set 0 to use all "
                  "available quote funds in portfolio (or total sell funds if set) to create orders with constant "
                  "total order cost (price * volume).",
        )
        self.UI.user_input(
            self.CONFIG_MIRROR_ORDER_DELAY, commons_enums.UserInputTypes.FLOAT, 0, inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="[Optional] Mirror order delay: Seconds to wait for before creating a mirror order when an order "
                  "is filled. This can generate extra profits on quick market moves.",
        )
        self.UI.user_input(
            self.CONFIG_REINVEST_PROFITS, commons_enums.UserInputTypes.BOOLEAN, False, inputs,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Reinvest profits: when checked, profits will be included in mirror orders resulting in maximum "
                  "size mirror orders. When unchecked, a part of the total volume will be reduced to take "
                  "exchange fees into account. WARNING: incompatible with fixed volume on mirror orders.",
        )
        self.UI.user_input(
            self.CONFIG_USE_FIXED_VOLUMES_FOR_MIRROR_ORDERS, commons_enums.UserInputTypes.BOOLEAN, False, inputs,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Fixed volume on mirror orders: when checked, sell and buy orders volume settings will be used for "
                  "mirror orders. WARNING: incompatible with profits reinvesting.",
        )
        self.UI.user_input(
            self.CONFIG_USE_EXISTING_ORDERS_ONLY, commons_enums.UserInputTypes.BOOLEAN, False, inputs,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Use existing orders only: when checked, new orders will only be created upon pre-existing orders "
                  "fill. OctoBot won't create orders at startup: it will use the ones already on exchange instead. "
                  "This mode allows grid orders to operate on user created orders. Can't work on trading simulator.",
        )

    def get_mode_producer_classes(self) -> list:
        return [GridTradingModeProducer]

    def get_mode_consumer_classes(self) -> list:
        return [GridTradingModeConsumer]

    async def user_commands_callback(self, bot_id, subject, action, data) -> None:
        await super().user_commands_callback(bot_id, subject, action, data)
        if data and data.get(GridTradingMode.USER_COMMAND_TRADING_PAIR, "").upper() == self.symbol:
            self.logger.info(f"Received {action} command for {self.symbol}.")
            if action == GridTradingMode.USER_COMMAND_CREATE_ORDERS:
                await self.producers[0].trigger_staggered_orders_creation()
            elif action == GridTradingMode.USER_COMMAND_STOP_ORDERS_CREATION:
                await self.get_trading_mode_consumers()[0].cancel_orders_creation()
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
        await self.trading_mode.reload_config(self.exchange_manager.bot_id)
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
