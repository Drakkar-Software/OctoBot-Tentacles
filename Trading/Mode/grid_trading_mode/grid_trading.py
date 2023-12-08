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

import octobot_commons.constants as commons_constants
import octobot_commons.enums as commons_enums
import octobot_trading.api as trading_api
import octobot_trading.enums as trading_enums
import octobot_trading.constants as trading_constants
import octobot_trading.errors as trading_errors
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
    SUPPORTS_HEALTH_CHECK = False   # WIP   # set True when self.health_check is implemented

    def init_user_inputs(self, inputs: dict) -> None:
        """
        Called right before starting the tentacle, should define all the tentacle's user inputs unless
        those are defined somewhere else.
        """
        default_config = self.get_default_pair_config("BTC/USDT", 0.05, 0.005)
        self.UI.user_input(self.CONFIG_PAIR_SETTINGS, commons_enums.UserInputTypes.OBJECT_ARRAY,
                           self.trading_config.get(self.CONFIG_PAIR_SETTINGS, None), inputs,
                           item_title="Pair configuration",
                           other_schema_values={"minItems": 1, "uniqueItems": True},
                           title="Configuration for each traded pairs.")
        self.UI.user_input(self.CONFIG_PAIR, commons_enums.UserInputTypes.TEXT,
                           default_config[self.CONFIG_PAIR], inputs,
                           other_schema_values={"minLength": 3, "pattern": "([a-zA-Z]|\\d){2,}\\/([a-zA-Z]|\\d){2,}"},
                           parent_input_name=self.CONFIG_PAIR_SETTINGS,
                           title="Name of the traded pair."),
        self.UI.user_input(
            self.CONFIG_FLAT_SPREAD, commons_enums.UserInputTypes.FLOAT,
            default_config[self.CONFIG_FLAT_SPREAD], inputs,
            min_val=0, other_schema_values={"exclusiveMinimum": True},
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Spread: price difference between the closest buy and sell orders in the quote currency "
                  "(USDT for BTC/USDT).",
        )
        self.UI.user_input(
            self.CONFIG_FLAT_INCREMENT, commons_enums.UserInputTypes.FLOAT,
            default_config[self.CONFIG_FLAT_INCREMENT], inputs,
            min_val=0, other_schema_values={"exclusiveMinimum": True},
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Increment: price difference between two orders of the same side in the quote currency (USDT for "
                  "BTC/USDT). WARNING: this should be lower than the Spread value: profitability is close to "
                  "Spread-Increment.",
        )
        self.UI.user_input(
            self.CONFIG_BUY_ORDERS_COUNT, commons_enums.UserInputTypes.INT,
            default_config[self.CONFIG_BUY_ORDERS_COUNT], inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Buy orders count: number of initial buy orders to create. Make sure to have enough funds "
                  "to create that many orders.",
        )
        self.UI.user_input(
            self.CONFIG_SELL_ORDERS_COUNT, commons_enums.UserInputTypes.INT,
            default_config[self.CONFIG_SELL_ORDERS_COUNT], inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Sell orders count: Number of initial sell orders to create. Make sure to have enough funds "
                  "to create that many orders.",
        )
        self.UI.user_input(
            self.CONFIG_BUY_FUNDS, commons_enums.UserInputTypes.FLOAT,
            default_config[self.CONFIG_BUY_FUNDS], inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="[Optional] Total buy funds: total funds to use for buy orders creation (in quote currency: USDT "
                  "for BTC/USDT). Set 0 to use all available funds in portfolio. Allows to use the same currency "
                  "simultaneously in multiple traded pairs.",
        )
        self.UI.user_input(
            self.CONFIG_SELL_FUNDS, commons_enums.UserInputTypes.FLOAT,
            default_config[self.CONFIG_SELL_FUNDS], inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="[Optional] Total sell funds: total funds to use for sell orders creation (in base currency: "
                  "BTC for BTC/USDT). Set 0 to use all available funds in portfolio. Allows to use the same "
                  "currency simultaneously in multiple traded pairs.",
        )
        self.UI.user_input(
            self.CONFIG_STARTING_PRICE, commons_enums.UserInputTypes.FLOAT,
            default_config[self.CONFIG_STARTING_PRICE], inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="[Optional] Starting price: price to compute initial orders from. Set 0 to use current "
                  "exchange price during initial grid orders creation.",
        )
        self.UI.user_input(
            self.CONFIG_BUY_VOLUME_PER_ORDER, commons_enums.UserInputTypes.FLOAT,
            default_config[self.CONFIG_BUY_VOLUME_PER_ORDER], inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="[Optional] Buy orders volume: volume of each buy order in quote currency. Set 0 to use all "
                  "available funds in portfolio (or total buy funds if set) to create orders with constant "
                  "total order cost (price * volume).",
        )
        self.UI.user_input(
            self.CONFIG_SELL_VOLUME_PER_ORDER, commons_enums.UserInputTypes.FLOAT,
            default_config[self.CONFIG_SELL_VOLUME_PER_ORDER], inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="[Optional] Sell orders volume: volume of each sell order in quote currency. Set 0 to use all "
                  "available funds in portfolio (or total sell funds if set) to create orders with constant "
                  "total order cost (price * volume).",
        )
        self.UI.user_input(
            self.CONFIG_IGNORE_EXCHANGE_FEES, commons_enums.UserInputTypes.BOOLEAN,
            default_config[self.CONFIG_IGNORE_EXCHANGE_FEES], inputs,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Ignore exchange fees: when checked, exchange fees won't be considered when creating mirror orders. "
                  "When unchecked, a part of the total volume will be reduced to take exchange "
                  "fees into account.",
        )
        self.UI.user_input(
            self.CONFIG_MIRROR_ORDER_DELAY, commons_enums.UserInputTypes.FLOAT,
            default_config[self.CONFIG_MIRROR_ORDER_DELAY], inputs,
            min_val=0,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="[Optional] Mirror order delay: Seconds to wait for before creating a mirror order when an order "
                  "is filled. This can generate extra profits on quick market moves.",
        )
        self.UI.user_input(
            self.CONFIG_USE_FIXED_VOLUMES_FOR_MIRROR_ORDERS, commons_enums.UserInputTypes.BOOLEAN,
            default_config[self.CONFIG_USE_FIXED_VOLUMES_FOR_MIRROR_ORDERS], inputs,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Fixed volume on mirror orders: when checked, sell and buy orders volume settings will be used for "
                  "mirror orders. WARNING: incompatible with 'Ignore exchange fees'.",
        )
        self.UI.user_input(
            self.CONFIG_USE_EXISTING_ORDERS_ONLY, commons_enums.UserInputTypes.BOOLEAN,
            default_config[self.CONFIG_USE_EXISTING_ORDERS_ONLY], inputs,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Use existing orders only: when checked, new orders will only be created upon pre-existing orders "
                  "fill. OctoBot won't create orders at startup: it will use the ones already on exchange instead. "
                  "This mode allows grid orders to operate on user created orders. Can't work on trading simulator.",
        )
        self.UI.user_input( 
            self.CONFIG_ALLOW_FUNDS_REDISPATCH, commons_enums.UserInputTypes.BOOLEAN,
            default_config[self.CONFIG_ALLOW_FUNDS_REDISPATCH], inputs,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Auto-dispatch new funds: when checked, new available funds will be dispatched into existing "
                  "orders when additional funds become available. Funds redispatch check happens once a day "
                  "around your OctoBot start time.",
        )

    def get_default_pair_config(self, symbol, flat_spread, flat_increment) -> dict:
        return {
          self.CONFIG_PAIR: symbol,
          self.CONFIG_FLAT_SPREAD: flat_spread,
          self.CONFIG_FLAT_INCREMENT: flat_increment,
          self.CONFIG_BUY_ORDERS_COUNT: 20,
          self.CONFIG_SELL_ORDERS_COUNT: 20,
          self.CONFIG_SELL_FUNDS: 0,
          self.CONFIG_BUY_FUNDS: 0,
          self.CONFIG_STARTING_PRICE: 0,
          self.CONFIG_BUY_VOLUME_PER_ORDER: 0,
          self.CONFIG_SELL_VOLUME_PER_ORDER: 0,
          self.CONFIG_IGNORE_EXCHANGE_FEES: False,
          self.CONFIG_MIRROR_ORDER_DELAY: 0,
          self.CONFIG_USE_FIXED_VOLUMES_FOR_MIRROR_ORDERS: False,
          self.CONFIG_USE_EXISTING_ORDERS_ONLY: False,
          self.CONFIG_ALLOW_FUNDS_REDISPATCH: False,
        }

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
            **super().get_user_commands(),
            **{
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
        }


class GridTradingModeConsumer(staggered_orders_trading.StaggeredOrdersTradingModeConsumer):
    pass


class GridTradingModeProducer(staggered_orders_trading.StaggeredOrdersTradingModeProducer):
    # Disable health check
    HEALTH_CHECK_INTERVAL_SECS = None
    ORDERS_DESC = "grid"
    RECENT_TRADES_ALLOWED_TIME = 2 * commons_constants.DAYS_TO_SECONDS

    def __init__(self, channel, config, trading_mode, exchange_manager):
        self.buy_orders_count = self.sell_orders_count = None
        self.sell_price_range = AllowedPriceRange()
        self.buy_price_range = AllowedPriceRange()
        super().__init__(channel, config, trading_mode, exchange_manager)
        self._expect_missing_orders = True
        self._skip_order_restore_on_recently_closed_orders = False
        self._use_recent_trades_for_order_restore = True

    def read_config(self):
        self.mode = staggered_orders_trading.StrategyModes.FLAT
        # init decimals from str to remove native float rounding
        self.flat_spread = None if self.symbol_trading_config[self.trading_mode.CONFIG_FLAT_SPREAD] is None \
            else decimal.Decimal(str(self.symbol_trading_config[self.trading_mode.CONFIG_FLAT_SPREAD]))
        self.flat_increment = None if self.symbol_trading_config[self.trading_mode.CONFIG_FLAT_INCREMENT] is None \
            else decimal.Decimal(str(self.symbol_trading_config[self.trading_mode.CONFIG_FLAT_INCREMENT]))
        # decimal.Decimal operations are supporting int values, no need to convert these into decimal.Decimal
        self.buy_orders_count = self.symbol_trading_config[self.trading_mode.CONFIG_BUY_ORDERS_COUNT]
        self.sell_orders_count = self.symbol_trading_config[self.trading_mode.CONFIG_SELL_ORDERS_COUNT]
        self.operational_depth = self.buy_orders_count + self.sell_orders_count
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
        # tmp: ensure "reinvest_profits" legacy param still works
        self.ignore_exchange_fees = self.symbol_trading_config.get("reinvest_profits", self.ignore_exchange_fees)
        # end tmp
        self.ignore_exchange_fees = self.symbol_trading_config.get(self.trading_mode.CONFIG_IGNORE_EXCHANGE_FEES,
                                                                   self.ignore_exchange_fees)
        self.use_fixed_volume_for_mirror_orders = self.symbol_trading_config.get(
            self.trading_mode.CONFIG_USE_FIXED_VOLUMES_FOR_MIRROR_ORDERS,
            self.use_fixed_volume_for_mirror_orders
        )
        self.use_existing_orders_only = self.symbol_trading_config.get(self.trading_mode.CONFIG_USE_EXISTING_ORDERS_ONLY,
                                                                       self.use_existing_orders_only)
        self.mirror_order_delay = self.symbol_trading_config.get(self.trading_mode.CONFIG_MIRROR_ORDER_DELAY,
                                                                 self.mirror_order_delay)
        self.allow_order_funds_redispatch = self.symbol_trading_config.get(
            self.trading_mode.CONFIG_ALLOW_FUNDS_REDISPATCH, self.allow_order_funds_redispatch
        )
        if self.allow_order_funds_redispatch:
            # check every day that funds should not be redispatched and of orders are missing
            self.health_check_interval_secs = commons_constants.DAYS_TO_SECONDS
        self.compensate_for_missed_mirror_order = self.symbol_trading_config.get(
            self.trading_mode.COMPENSATE_FOR_MISSED_MIRROR_ORDER, self.compensate_for_missed_mirror_order
        )

    async def _handle_staggered_orders(self, current_price, ignore_mirror_orders_only, ignore_available_funds):
        self._init_allowed_price_ranges(current_price)
        if ignore_mirror_orders_only or not self.use_existing_orders_only:
            async with self.producer_exchange_wide_lock(self.exchange_manager):
                # use exchange level lock to prevent funds double spend
                buy_orders, sell_orders = await self._generate_staggered_orders(current_price, ignore_available_funds)
                grid_orders = self._merged_and_sort_not_virtual_orders(buy_orders, sell_orders)
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

    def _load_symbol_trading_config(self) -> bool:
        if not super()._load_symbol_trading_config():
            return self._apply_default_symbol_config()
        return True

    def _apply_default_symbol_config(self) -> bool:
        if not self.trading_mode.trading_config.get(commons_constants.ALLOW_DEFAULT_CONFIG, True):
            raise trading_errors.TradingModeIncompatibility(
                f"{self.trading_mode.get_name()} default configuration is not allowed. "
                f"Please configure the {self.symbol} settings."
            )
        self.logger.info(f"Using default configuration for {self.symbol} as no configuration "
                         f"is specified for this pair.")
        # set spread and increment as multipliers of the current price
        self.spread = decimal.Decimal(str(self.trading_mode.CONFIG_DEFAULT_SPREAD_PERCENT / 100))
        self.increment = decimal.Decimal(str(self.trading_mode.CONFIG_DEFAULT_INCREMENT_PERCENT / 100))
        self.symbol_trading_config = self.trading_mode.get_default_pair_config(
            self.symbol,
            None,   # will compute flat_spread from self.spread
            None,   # will compute flat_increment from self.increment
        )
        return True

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

        sorted_orders = self._get_grid_trades_or_orders(existing_orders)
        oldest_existing_order_creation_time = min(
            order.creation_time for order in sorted_orders
        ) if sorted_orders else 0
        recent_trades_time = max(
            trading_api.get_exchange_current_time(
                self.exchange_manager
            ) - self.RECENT_TRADES_ALLOWED_TIME,
            oldest_existing_order_creation_time
        )
        # list of trades orders from the most recent one to the oldest one
        recently_closed_trades = sorted([
            trade
            for trade in trading_api.get_trade_history(
                self.exchange_manager, symbol=self.symbol, since=recent_trades_time
            )
            # non limit orders are not to be taken into account
            if trade.trade_type in (trading_enums.TraderOrderType.BUY_LIMIT, trading_enums.TraderOrderType.SELL_LIMIT)
        ], key=lambda t: -t.executed_time)

        lowest_buy = max(trading_constants.ZERO, self.buy_price_range.lower_bound)
        highest_buy = self.buy_price_range.higher_bound
        lowest_sell = self.sell_price_range.lower_bound
        highest_sell = self.sell_price_range.higher_bound
        if sorted_orders:
            buy_orders = [order for order in sorted_orders if order.side == trading_enums.TradeOrderSide.BUY]
            highest_buy = current_price
            sell_orders = [order for order in sorted_orders if order.side == trading_enums.TradeOrderSide.SELL]
            lowest_sell = current_price
            origin_created_buy_orders_count, origin_created_sell_orders_count = self._get_origin_orders_count(
                sorted_orders, recently_closed_trades
            )

            min_max_total_order_price_delta = (
                self.flat_increment * (origin_created_buy_orders_count - 1 + origin_created_sell_orders_count - 1)
                + self.flat_increment
            )
            if buy_orders:
                lowest_buy = buy_orders[0].origin_price
                if not sell_orders:
                    highest_buy = min(current_price, lowest_buy + min_max_total_order_price_delta)
                    # buy orders only
                    lowest_sell = highest_buy + self.flat_spread - self.flat_increment
                    highest_sell = lowest_buy + min_max_total_order_price_delta + self.flat_spread - self.flat_increment
                else:
                    # use only open order prices when possible
                    _highest_sell = sell_orders[-1].origin_price
                    highest_buy = min(current_price, _highest_sell - self.flat_spread + self.flat_increment)
            if sell_orders:
                highest_sell = sell_orders[-1].origin_price
                if not buy_orders:
                    lowest_sell = max(current_price, highest_sell - min_max_total_order_price_delta)
                    # sell orders only
                    lowest_buy = max(
                        0, highest_sell - min_max_total_order_price_delta - self.flat_spread + self.flat_increment
                    )
                    highest_buy = lowest_sell - self.flat_spread + self.flat_increment
                else:
                    # use only open order prices when possible
                    _lowest_buy = buy_orders[0].origin_price
                    lowest_sell = max(current_price, _lowest_buy - self.flat_spread + self.flat_increment)

        missing_orders, state, _ = self._analyse_current_orders_situation(
            sorted_orders, recently_closed_trades, lowest_buy, highest_sell, current_price
        )
        if missing_orders:
            self.logger.info(
                f"{len(missing_orders)} missing {self.symbol} orders on {self.exchange_name}: {missing_orders}"
            )
        await self._handle_missed_mirror_orders_fills(recently_closed_trades, missing_orders, current_price)
        try:
            buy_orders = self._create_orders(lowest_buy, highest_buy,
                                             trading_enums.TradeOrderSide.BUY, sorted_orders,
                                             current_price, missing_orders, state, self.buy_funds, ignore_available_funds,
                                             recently_closed_trades)
            sell_orders = self._create_orders(lowest_sell, highest_sell,
                                              trading_enums.TradeOrderSide.SELL, sorted_orders,
                                              current_price, missing_orders, state, self.sell_funds, ignore_available_funds,
                                              recently_closed_trades)

            if state is self.FILL:
                self._ensure_used_funds(buy_orders, sell_orders, sorted_orders, recently_closed_trades)
        except staggered_orders_trading.ForceResetOrdersException:
            lowest_buy = max(trading_constants.ZERO, self.buy_price_range.lower_bound)
            highest_buy = self.buy_price_range.higher_bound
            lowest_sell = self.sell_price_range.lower_bound
            highest_sell = self.sell_price_range.higher_bound
            buy_orders, sell_orders, state = await self._reset_orders(
                sorted_orders, lowest_buy, highest_buy, lowest_sell, highest_sell, current_price, ignore_available_funds
            )

        return buy_orders, sell_orders

    def _get_origin_orders_count(self, recent_trades, open_orders):
        origin_created_buy_orders_count = self.buy_orders_count
        origin_created_sell_orders_count = self.sell_orders_count
        if recent_trades:
            buy_orders_count = len([order for order in open_orders if order.side is trading_enums.TradeOrderSide.BUY])
            buy_trades_count = len([trade for trade in recent_trades if trade.side is trading_enums.TradeOrderSide.BUY])
            origin_created_buy_orders_count = buy_orders_count + buy_trades_count
            origin_created_sell_orders_count = len(open_orders) + len(recent_trades) - origin_created_buy_orders_count
        return origin_created_buy_orders_count, origin_created_sell_orders_count

    def _get_grid_trades_or_orders(self, trades_or_orders):
        if not trades_or_orders:
            return trades_or_orders
        sorted_elements = sorted(trades_or_orders, key=lambda t: self.get_trade_or_order_price(t))
        four = decimal.Decimal("4")
        increment_lower_bound = - self.flat_increment / four
        increment_higher_bound = self.flat_increment / four
        for first_element_index in range(len(sorted_elements)):
            grid_trades_or_orders = []
            previous_element = None
            first_sided_element_price = None
            for trade_or_order in sorted_elements[first_element_index:]:
                if first_sided_element_price is None:
                    first_sided_element_price = self.get_trade_or_order_price(trade_or_order)
                if previous_element is None:
                    grid_trades_or_orders.append(trade_or_order)
                else:
                    if trade_or_order.side != previous_element.side:
                        # reached other side: take spread into account
                        first_sided_element_price += self.flat_spread
                    delta_increment = (self.get_trade_or_order_price(trade_or_order) - first_sided_element_price) \
                        % self.flat_increment
                    if increment_lower_bound < delta_increment < increment_higher_bound:
                        grid_trades_or_orders.append(trade_or_order)
                previous_element = trade_or_order
            if len(grid_trades_or_orders) / len(sorted_elements) > 0.5:
                # make sure that we did not miss every grid trade by basing computations on a non grid trade
                # more than 50% match of grid trades: grid trades are found
                return grid_trades_or_orders
        # grid trades are not found, use every trade
        return sorted_elements

    def _init_allowed_price_ranges(self, current_price):
        self._set_increment_and_spread(current_price)
        first_sell_price = current_price + (self.flat_spread / 2)
        self.sell_price_range.higher_bound = first_sell_price + (self.flat_increment * (self.sell_orders_count - 1))
        self.sell_price_range.lower_bound = max(current_price, first_sell_price)
        first_buy_price = current_price - (self.flat_spread / 2)
        self.buy_price_range.higher_bound = min(current_price, first_buy_price)
        self.buy_price_range.lower_bound = first_buy_price - (self.flat_increment * (self.buy_orders_count - 1))

    def _check_params(self):
        if None not in (self.flat_increment, self.flat_spread) and self.flat_increment >= self.flat_spread:
            self.logger.error(f"Your flat_spread parameter should always be higher than your flat_increment"
                              f" parameter: average profit is spread-increment. ({self.symbol})")

    def _create_new_orders_bundle(
        self, lower_bound, upper_bound, side, current_price, allowed_funds, ignore_available_funds, selling,
        order_limiting_currency, order_limiting_currency_amount
    ):
        orders = []
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
            return self._ensure_average_order_quantity(orders_count, current_price, selling, holdings, currency, mode)
        else:
            return self._get_orders_count_from_fixed_volume(selling, current_price, holdings, orders_count)

    def _get_max_theoretical_orders_count(self):
        return self.buy_orders_count + self.sell_orders_count
