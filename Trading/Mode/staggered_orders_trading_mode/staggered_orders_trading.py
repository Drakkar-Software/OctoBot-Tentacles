# pylint: disable=E701
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
import enum
import dataclasses
import math
import asyncio
import decimal

import async_channel.constants as channel_constants
import octobot_commons.constants as commons_constants
import octobot_commons.enums as commons_enums
import octobot_commons.symbols.symbol_util as symbol_util
import octobot_commons.data_util as data_util
import octobot_trading.api as trading_api
import octobot_trading.modes as trading_modes
import octobot_trading.exchange_channel as exchanges_channel
import octobot_trading.constants as trading_constants
import octobot_trading.enums as trading_enums
import octobot_trading.personal_data as trading_personal_data
import octobot_trading.errors as trading_errors


class StrategyModes(enum.Enum):
    NEUTRAL = "neutral"
    MOUNTAIN = "mountain"
    VALLEY = "valley"
    SELL_SLOPE = "sell slope"
    BUY_SLOPE = "buy slope"
    FLAT = "flat"


INCREASING = "increasing_towards_current_price"
DECREASING = "decreasing_towards_current_price"
STABLE = "stable_towards_current_price"
MULTIPLIER = "multiplier"

ONE_PERCENT_DECIMAL = decimal.Decimal("1.01")

StrategyModeMultipliersDetails = {
    StrategyModes.FLAT: {
        MULTIPLIER: trading_constants.ZERO,
        trading_enums.TradeOrderSide.BUY: STABLE,
        trading_enums.TradeOrderSide.SELL: STABLE
    },
    StrategyModes.NEUTRAL: {
        MULTIPLIER: decimal.Decimal("0.3"),
        trading_enums.TradeOrderSide.BUY: INCREASING,
        trading_enums.TradeOrderSide.SELL: INCREASING
    },
    StrategyModes.MOUNTAIN: {
        MULTIPLIER: trading_constants.ONE,
        trading_enums.TradeOrderSide.BUY: INCREASING,
        trading_enums.TradeOrderSide.SELL: INCREASING
    },
    StrategyModes.VALLEY: {
        MULTIPLIER: trading_constants.ONE,
        trading_enums.TradeOrderSide.BUY: DECREASING,
        trading_enums.TradeOrderSide.SELL: DECREASING
    },
    StrategyModes.BUY_SLOPE: {
        MULTIPLIER: trading_constants.ONE,
        trading_enums.TradeOrderSide.BUY: DECREASING,
        trading_enums.TradeOrderSide.SELL: INCREASING
    },
    StrategyModes.SELL_SLOPE: {
        MULTIPLIER: trading_constants.ONE,
        trading_enums.TradeOrderSide.BUY: INCREASING,
        trading_enums.TradeOrderSide.SELL: DECREASING
    }
}


@dataclasses.dataclass
class OrderData:
    side: trading_enums.TradeOrderSide = None
    quantity: decimal.Decimal = trading_constants.ZERO
    price: decimal.Decimal = trading_constants.ZERO
    symbol: str = 0
    is_virtual: bool = True


class StaggeredOrdersTradingMode(trading_modes.AbstractTradingMode):
    CONFIG_PAIR_SETTINGS = "pair_settings"
    CONFIG_PAIR = "pair"
    CONFIG_MODE = "mode"
    CONFIG_SPREAD = "spread_percent"
    CONFIG_INCREMENT_PERCENT = "increment_percent"
    CONFIG_LOWER_BOUND = "lower_bound"
    CONFIG_UPPER_BOUND = "upper_bound"
    CONFIG_USE_EXISTING_ORDERS_ONLY = "use_existing_orders_only"
    CONFIG_ALLOW_INSTANT_FILL = "allow_instant_fill"
    CONFIG_OPERATIONAL_DEPTH = "operational_depth"
    CONFIG_MIRROR_ORDER_DELAY = "mirror_order_delay"
    CONFIG_STARTING_PRICE = "starting_price"
    CONFIG_BUY_FUNDS = "buy_funds"
    CONFIG_SELL_FUNDS = "sell_funds"
    CONFIG_SELL_VOLUME_PER_ORDER = "sell_volume_per_order"
    CONFIG_BUY_VOLUME_PER_ORDER = "buy_volume_per_order"
    CONFIG_REINVEST_PROFITS = "reinvest_profits"
    CONFIG_USE_FIXED_VOLUMES_FOR_MIRROR_ORDERS = "use_fixed_volume_for_mirror_orders"

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
            self.CONFIG_MODE, commons_enums.UserInputTypes.OPTIONS, StrategyModes.NEUTRAL.value, inputs,
            options=list(mode.value for mode in StrategyModes),
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Mode: way to allocate funds in created orders.",
        )
        self.UI.user_input(
            self.CONFIG_SPREAD, commons_enums.UserInputTypes.FLOAT, 0.005, inputs,
            min_val=0, other_schema_values={"exclusiveMinimum": True},
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Spread: price difference between buy and sell orders: percent of the current price to use as "
                  "spread (difference between highest buy and lowest sell).",
        )
        self.UI.user_input(
            self.CONFIG_INCREMENT_PERCENT, commons_enums.UserInputTypes.FLOAT, 0.005, inputs,
            min_val=0, other_schema_values={"exclusiveMinimum": True},
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Increment: price difference between grid orders: percent of the current price to use as increment "
                  "between orders. WARNING: this should be lower than the Spread value: profitability is close to "
                  "Spread-Increment.",
        )
        self.UI.user_input(
            self.CONFIG_LOWER_BOUND, commons_enums.UserInputTypes.FLOAT, 0.005, inputs,
            min_val=0, other_schema_values={"exclusiveMinimum": True},
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Lower bound: lower limit of the grid: minimum price to start placing buy orders from: lower "
                  "limit of the grid.",
        )
        self.UI.user_input(
            self.CONFIG_UPPER_BOUND, commons_enums.UserInputTypes.FLOAT, 0.005, inputs,
            min_val=0, other_schema_values={"exclusiveMinimum": True},
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Upper bound: upper limit of the grid: maximum price to stop placing sell orders from.",
        )
        self.UI.user_input(
            self.CONFIG_OPERATIONAL_DEPTH, commons_enums.UserInputTypes.INT, 50, inputs,
            min_val=1, other_schema_values={"exclusiveMinimum": True},
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Operational depth: maximum number of orders to be maintained on exchange.",
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
                  "size mirror orders. When unchecked, a part of the total volume will be reduced to take exchange "
                  "fees into account.",
        )
        self.UI.user_input(
            self.CONFIG_USE_EXISTING_ORDERS_ONLY, commons_enums.UserInputTypes.BOOLEAN, False, inputs,
            parent_input_name=self.CONFIG_PAIR_SETTINGS,
            title="Use existing orders only: when checked, new orders will only be created upon pre-existing orders "
                  "fill. OctoBot won't create orders at startup: it will use the ones already on exchange instead. "
                  "This mode allows staggered orders to operate on user created orders. "
                  "Can't work on trading simulator.",
        )

    def get_current_state(self) -> (str, float):
        order = self.exchange_manager.exchange_personal_data.orders_manager.get_open_orders(self.symbol)
        sell_count = len([o for o in order if o.side == trading_enums.TradeOrderSide.SELL])
        buy_count = len(order) - sell_count
        if buy_count > sell_count:
            state = trading_enums.EvaluatorStates.LONG
        elif buy_count < sell_count:
            state = trading_enums.EvaluatorStates.SHORT
        else:
            state = trading_enums.EvaluatorStates.NEUTRAL
        return state.name, f"{buy_count} buy {sell_count} sell"

    def get_mode_producer_classes(self) -> list:
        return [StaggeredOrdersTradingModeProducer]

    def get_mode_consumer_classes(self) -> list:
        return [StaggeredOrdersTradingModeConsumer]

    async def create_consumers(self) -> list:
        consumers = await super().create_consumers()
        # order consumer: filter by symbol not be triggered only on this symbol's orders
        order_consumer = await exchanges_channel.get_chan(trading_personal_data.OrdersChannel.get_name(),
                                                          self.exchange_manager.id).new_consumer(
            self._order_notification_callback,
            symbol=self.symbol if self.symbol else channel_constants.CHANNEL_WILDCARD
        )
        return consumers + [order_consumer]

    async def _order_notification_callback(self, exchange, exchange_id, cryptocurrency, symbol, order,
                                           is_new, is_from_bot):
        if order[
            trading_enums.ExchangeConstantsOrderColumns.STATUS.value] == trading_enums.OrderStatus.FILLED.value and is_from_bot:
            async with self.producers[0].get_lock():
                await self.producers[0].order_filled_callback(order)

    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        return False

    def set_default_config(self):
        raise RuntimeError(f"Impossible to start {self.get_name()} without a valid configuration file.")


class StaggeredOrdersTradingModeConsumer(trading_modes.AbstractTradingModeConsumer):
    ORDER_DATA_KEY = "order_data"
    CURRENT_PRICE_KEY = "current_price"
    SYMBOL_MARKET_KEY = "symbol_market"

    def __init__(self, trading_mode):
        super().__init__(trading_mode)
        self.skip_orders_creation = False

    async def cancel_orders_creation(self):
        self.logger.info(f"Cancelling all orders creation for {self.trading_mode.symbol}")
        self.skip_orders_creation = True
        try:
            while not self.queue.empty():
                await asyncio.sleep(0.1)
        finally:
            self.logger.info(f"Orders creation fully cancelled for {self.trading_mode.symbol}")
            self.skip_orders_creation = False

    async def create_new_orders(self, symbol, final_note, state, **kwargs):
        # use dict default getter: can't afford missing data
        data = kwargs["data"]
        if not self.skip_orders_creation:
            order_data = data[self.ORDER_DATA_KEY]
            current_price = data[self.CURRENT_PRICE_KEY]
            symbol_market = data[self.SYMBOL_MARKET_KEY]
            return await self.create_order(order_data, current_price, symbol_market)
        else:
            self.logger.info(f"Skipped {data.get(self.ORDER_DATA_KEY, '')}")

    async def create_order(self, order_data, current_price, symbol_market):
        created_order = None
        currency, market = symbol_util.parse_symbol(order_data.symbol).base_and_quote()
        try:
            for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                    order_data.quantity,
                    order_data.price,
                    symbol_market):
                selling = order_data.side == trading_enums.TradeOrderSide.SELL
                if selling:
                    if trading_api.get_portfolio_currency(self.exchange_manager, currency).available < order_quantity:
                        return []
                elif trading_api.get_portfolio_currency(self.exchange_manager, market).available < order_quantity * order_price:
                    return []
                order_type = trading_enums.TraderOrderType.SELL_LIMIT if selling else trading_enums.TraderOrderType.BUY_LIMIT
                current_order = trading_personal_data.create_order_instance(trader=self.exchange_manager.trader,
                                                                            order_type=order_type,
                                                                            symbol=order_data.symbol,
                                                                            current_price=current_price,
                                                                            quantity=order_quantity,
                                                                            price=order_price)
                # disable instant fill to avoid looping order fill in simulator
                current_order.allow_instant_fill = False
                created_order = await self.exchange_manager.trader.create_order(current_order)
        except trading_errors.MissingFunds as e:
            raise e
        except Exception as e:
            self.logger.error(f"Failed to create order : {e}. Order: {order_data}")
            self.logger.exception(e, False)
            return None
        return [] if created_order is None else [created_order]


class StaggeredOrdersTradingModeProducer(trading_modes.AbstractTradingModeProducer):
    FILL = 1
    ERROR = 2
    NEW = 3
    min_quantity = "min_quantity"
    max_quantity = "max_quantity"
    min_cost = "min_cost"
    max_cost = "max_cost"
    min_price = "min_price"
    max_price = "max_price"
    PRICE_FETCHING_TIMEOUT = 60
    # health check once every 3 days
    HEALTH_CHECK_INTERVAL_SECS = commons_constants.DAYS_TO_SECONDS * 3
    # recent filled allowed time delay to consider as pending order_filled callback
    RECENT_TRADES_ALLOWED_TIME = 10
    # when True, orders creation/health check will be performed on start()
    SCHEDULE_ORDERS_CREATION_ON_START = True
    ORDERS_DESC = "staggered"
    # keep track of available funds in order placement process to avoid spending multiple times
    # the same funds due to async between producers and consumers and the possibility to trade multiple pairs with
    # shared quote or base
    AVAILABLE_FUNDS = {}

    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)
        # no state for this evaluator: always neutral
        self.state = trading_enums.EvaluatorStates.NEUTRAL
        self.symbol = trading_mode.symbol
        self.symbol_market = None
        self.min_max_order_details = {}
        fees = trading_api.get_fees(exchange_manager, self.symbol)
        self.max_fees = decimal.Decimal(str(max(fees[trading_enums.ExchangeConstantsMarketPropertyColumns.TAKER.value],
                                                fees[trading_enums.ExchangeConstantsMarketPropertyColumns.MAKER.value]
                                                )))
        self.flat_increment = None
        self.flat_spread = None
        self.current_price = None
        self.scheduled_health_check = None
        self.sell_volume_per_order = self.buy_volume_per_order = self.starting_price = trading_constants.ZERO
        self.mirror_orders_tasks = []
        self.mirroring_pause_task = None

        self.healthy = False

        # used not to refresh orders when order_fill_callback is processing
        self.lock = asyncio.Lock()

        # staggered orders strategy parameters
        self.symbol_trading_config = None

        self.use_existing_orders_only = self.limit_orders_count_if_necessary = \
            self.reinvest_profits = self.use_fixed_volume_for_mirror_orders = False
        self.mode = self.spread \
            = self.increment = self.operational_depth \
            = self.lowest_buy = self.highest_sell \
            = None
        self.single_pair_setup = len(self.trading_mode.trading_config[self.trading_mode.CONFIG_PAIR_SETTINGS]) <= 1
        self.mirror_order_delay = self.buy_funds = self.sell_funds = 0
        self.allowed_mirror_orders = asyncio.Event()
        self.healthy = False

        try:
            self._load_symbol_trading_config()
        except KeyError as e:
            error_message = f"Impossible to start {self.ORDERS_DESC} orders for {self.symbol}: missing " \
                            f"configuration in trading mode config file. "
            self.logger.exception(e, True, error_message)
            return
        if self.symbol_trading_config is None:
            configured_pairs = \
                [c[self.trading_mode.CONFIG_PAIR]
                 for c in self.trading_mode.trading_config[self.trading_mode.CONFIG_PAIR_SETTINGS]]
            self.logger.error(f"No {self.ORDERS_DESC} orders configuration for trading pair: {self.symbol}. Add "
                              f"this pair's details into your {self.ORDERS_DESC} orders configuration or disable this "
                              f"trading pairs. Configured {self.ORDERS_DESC} orders pairs are"
                              f" {', '.join(configured_pairs)}")
            return
        self.already_errored_on_out_of_window_price = False

        self.allowed_mirror_orders.set()
        self.read_config()
        self._check_params()

        self.healthy = True

    def _load_symbol_trading_config(self):
        for config in self.trading_mode.trading_config[self.trading_mode.CONFIG_PAIR_SETTINGS]:
            if config[self.trading_mode.CONFIG_PAIR] == self.symbol:
                self.symbol_trading_config = config

    def read_config(self):
        mode = ""
        try:
            mode = self.symbol_trading_config[self.trading_mode.CONFIG_MODE]
            self.mode = StrategyModes(mode)
        except ValueError as e:
            self.logger.error(f"Invalid {self.ORDERS_DESC} orders strategy mode: {mode} for {self.symbol}"
                              f"supported modes are {[m.value for m in StrategyModes]}")
            raise e
        self.spread = decimal.Decimal(str(self.symbol_trading_config[self.trading_mode.CONFIG_SPREAD] / 100))
        self.increment = decimal.Decimal(str(self.symbol_trading_config[self.trading_mode.CONFIG_INCREMENT_PERCENT] / 100))
        self.operational_depth = self.symbol_trading_config[self.trading_mode.CONFIG_OPERATIONAL_DEPTH]
        self.lowest_buy = decimal.Decimal(str(self.symbol_trading_config[self.trading_mode.CONFIG_LOWER_BOUND]))
        self.highest_sell = decimal.Decimal(str(self.symbol_trading_config[self.trading_mode.CONFIG_UPPER_BOUND]))
        self.use_existing_orders_only = self.symbol_trading_config.get(
            self.trading_mode.CONFIG_USE_EXISTING_ORDERS_ONLY,
            self.use_existing_orders_only)
        self.mirror_order_delay = self.symbol_trading_config.get(self.trading_mode.CONFIG_MIRROR_ORDER_DELAY,
                                                                 self.mirror_order_delay)
        self.buy_funds = decimal.Decimal(str(self.symbol_trading_config.get(self.trading_mode.CONFIG_BUY_FUNDS,
                                                                            self.buy_funds)))
        self.sell_funds = decimal.Decimal(str(self.symbol_trading_config.get(self.trading_mode.CONFIG_SELL_FUNDS,
                                                                             self.sell_funds)))
        self.reinvest_profits = self.symbol_trading_config.get(self.trading_mode.CONFIG_REINVEST_PROFITS,
                                                               self.reinvest_profits)

    async def start(self) -> None:
        await super().start()
        if StaggeredOrdersTradingModeProducer.SCHEDULE_ORDERS_CREATION_ON_START and self.healthy:
            await self._ensure_staggered_orders_and_reschedule()

    async def stop(self):
        if self.trading_mode is not None:
            self.trading_mode.flush_trading_mode_consumers()
        if self.scheduled_health_check is not None:
            self.scheduled_health_check.cancel()
        if self.mirroring_pause_task is not None and not self.mirroring_pause_task.done():
            self.mirroring_pause_task.cancel()
        for task in self.mirror_orders_tasks:
            task.cancel()
        if self.exchange_manager and self.exchange_manager.id in StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS:
            # remove self.exchange_manager.id from available funds
            StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS.pop(self.exchange_manager.id, None)
        await super().stop()

    async def set_final_eval(self, matrix_id: str, cryptocurrency: str, symbol: str, time_frame):
        # nothing to do: this is not a strategy related trading mode
        pass

    def _schedule_order_refresh(self):
        # schedule order creation / health check
        asyncio.create_task(self._ensure_staggered_orders_and_reschedule())

    async def _ensure_staggered_orders_and_reschedule(self):
        can_create_orders = (not trading_api.get_is_backtesting(self.exchange_manager) \
                             or trading_api.is_mark_price_initialized(self.exchange_manager, symbol=self.symbol)) and \
            (trading_api.get_portfolio(self.exchange_manager) != {}
             or trading_api.is_trader_simulated(self.exchange_manager))
        if can_create_orders:
            await self._ensure_staggered_orders()
        if not self.should_stop:
            if can_create_orders:
                # a None self.HEALTH_CHECK_INTERVAL_SECS disables health check
                if self.HEALTH_CHECK_INTERVAL_SECS is not None:
                    self.scheduled_health_check = asyncio.get_event_loop().call_later(self.HEALTH_CHECK_INTERVAL_SECS,
                                                                                      self._schedule_order_refresh)
            else:
                self.scheduled_health_check = asyncio.get_event_loop().call_soon(self._schedule_order_refresh)

    async def trigger_staggered_orders_creation(self):
        if self.symbol_trading_config:
            await self._ensure_staggered_orders(ignore_mirror_orders_only=True)
        else:
            self.logger.error(f"No configuration for {self.symbol}")

    def start_mirroring_pause(self, delay):
        if self.allowed_mirror_orders.is_set():
            self.mirroring_pause_task = asyncio.create_task(self.stop_mirror_orders(delay))
        else:
            self.logger.info(f"Cancelling previous {self.symbol} mirror order delay")
            self.mirroring_pause_task.cancel()
            self.mirroring_pause_task = asyncio.create_task(self.stop_mirror_orders(delay))

    async def stop_mirror_orders(self, delay):
        self.logger.info(f"Pausing {self.symbol} mirror orders creation for the next {delay} seconds")
        self.allowed_mirror_orders.clear()
        await asyncio.sleep(delay)
        self.allowed_mirror_orders.set()
        self.logger.info(f"Resuming {self.symbol} mirror orders creation after a {delay} seconds pause")

    async def _ensure_staggered_orders(self, ignore_mirror_orders_only=False, ignore_available_funds=False):
        _, _, _, self.current_price, self.symbol_market = await trading_personal_data.get_pre_order_data(
            self.exchange_manager,
            symbol=self.symbol,
            timeout=self.PRICE_FETCHING_TIMEOUT)
        await self.create_state(self._get_new_state_price(), ignore_mirror_orders_only, ignore_available_funds)

    def _get_new_state_price(self):
        return decimal.Decimal(str(self.current_price if self.starting_price == 0 else self.starting_price))

    async def create_state(self, current_price, ignore_mirror_orders_only, ignore_available_funds):
        if current_price is not None:
            self._refresh_symbol_data(self.symbol_market)
            async with self.get_lock(), self.trading_mode_trigger():
                if self.exchange_manager.trader.is_enabled:
                    await self._handle_staggered_orders(current_price, ignore_mirror_orders_only, ignore_available_funds)

    async def order_filled_callback(self, filled_order):
        # create order on the order side
        now_selling = filled_order[
                          trading_enums.ExchangeConstantsOrderColumns.SIDE.value] == trading_enums.TradeOrderSide.BUY.value
        new_side = trading_enums.TradeOrderSide.SELL if now_selling else trading_enums.TradeOrderSide.BUY
        if self.flat_increment is None:
            self.logger.error(f"Impossible to create symmetrical order for {self.symbol}: "
                              f"self.flat_increment is unset.")
            return
        if self.flat_spread is None:
            self.flat_spread = trading_personal_data.decimal_adapt_price(
                self.symbol_market, self.spread * self.flat_increment / self.increment)
        price_increment = self.flat_spread - self.flat_increment
        filled_price = decimal.Decimal(str(filled_order[trading_enums.ExchangeConstantsOrderColumns.PRICE.value]))
        filled_volume = decimal.Decimal(str(filled_order[trading_enums.ExchangeConstantsOrderColumns.FILLED.value]))
        price = filled_price + price_increment if now_selling else filled_price - price_increment
        volume = self._compute_mirror_order_volume(now_selling, filled_price, price, filled_volume)
        new_order = OrderData(new_side, volume, price, self.symbol)
        if self.mirror_order_delay == 0 or trading_api.get_is_backtesting(self.exchange_manager):
            await self._lock_portfolio_and_create_order_when_possible(new_order, filled_price)
        else:
            # create order after waiting time
            self.mirror_orders_tasks.append(asyncio.get_event_loop().call_later(
                self.mirror_order_delay,
                asyncio.create_task,
                self._lock_portfolio_and_create_order_when_possible(new_order, filled_price)
            ))

    def _compute_mirror_order_volume(self, now_selling, filled_price, target_price, filled_volume):
        # use target volumes if set
        if self.sell_volume_per_order != trading_constants.ZERO and now_selling:
            return self.sell_volume_per_order
        if self.buy_volume_per_order != trading_constants.ZERO and not now_selling:
            return self.buy_volume_per_order
        # otherwise: compute mirror volume
        new_order_quantity = filled_volume
        if not now_selling:
            # buying => adapt order quantity
            new_order_quantity = filled_price / target_price * filled_volume
        # use max possible volume
        if self.reinvest_profits:
            return new_order_quantity
        # remove exchange fees
        quantity_change = self.max_fees
        quantity = new_order_quantity * (1 - quantity_change)
        return quantity

    async def _lock_portfolio_and_create_order_when_possible(self, new_order, filled_price):
        await asyncio.wait_for(self.allowed_mirror_orders.wait(), timeout=None)
        async with self.exchange_manager.exchange_personal_data.portfolio_manager.portfolio.lock:
            await self._create_order(new_order, filled_price)

    async def _handle_staggered_orders(self, current_price, ignore_mirror_orders_only, ignore_available_funds):
        self._ensure_current_price_in_limit_parameters(current_price)
        if not ignore_mirror_orders_only and self.use_existing_orders_only:
            # when using existing orders only, no need to check existing orders (they can't be wrong since they are
            # already on exchange): only initialize increment and order fill events will do the rest
            self._set_increment_and_spread(current_price)
        else:
            async with self.exchange_manager.exchange_personal_data.portfolio_manager.portfolio.lock:
                buy_orders, sell_orders = await self._generate_staggered_orders(current_price, ignore_available_funds)
                staggered_orders = self._merged_and_sort_not_virtual_orders(buy_orders, sell_orders)
                await self._create_not_virtual_orders(staggered_orders, current_price)

    def _ensure_current_price_in_limit_parameters(self, current_price):
        message = None
        if self.highest_sell < current_price:
            message = f"The current price is hover the {self.ORDERS_DESC} orders boundaries for {self.symbol}: upper " \
                      f"bound is {self.highest_sell} and price is {current_price}. OctoBot can't trade using " \
                      f"these settings at this current price. Adjust your {self.ORDERS_DESC} orders upper bound " \
                      f"settings to use this trading mode."
        if self.lowest_buy > current_price:
            message = f"The current price is bellow the {self.ORDERS_DESC} orders boundaries for {self.symbol}: " \
                      f"lower bound is {self.lowest_buy} and price is {current_price}. OctoBot can't trade using " \
                      f"these settings at this current price. Adjust your {self.ORDERS_DESC} orders " \
                      f"lower bound settings to use this trading mode."
        if message is not None:
            # Only log once in error, use warning of later messages.
            self._log_window_error_or_warning(message, not self.already_errored_on_out_of_window_price)
            self.already_errored_on_out_of_window_price = True
        else:
            self.already_errored_on_out_of_window_price = False

    def _log_window_error_or_warning(self, message, using_error):
        log_func = self.logger.error if using_error else self.logger.warning
        log_func(message)

    async def _generate_staggered_orders(self, current_price, ignore_available_funds):
        order_manager = self.exchange_manager.exchange_personal_data.orders_manager
        interfering_orders_pairs = self._get_interfering_orders_pairs(order_manager.get_open_orders())
        if interfering_orders_pairs:
            self.logger.error(f"Impossible to create {self.ORDERS_DESC} orders for {self.symbol} with "
                              f"interfering orders using pair(s): {interfering_orders_pairs}. "
                              f"{self.ORDERS_DESC.capitalize()} orders require no other orders in both quote and base.")
            return [], []
        existing_orders = order_manager.get_open_orders(self.symbol)

        sorted_orders = sorted(existing_orders, key=lambda order: order.origin_price)

        recent_trades_time = trading_api.get_exchange_current_time(
            self.exchange_manager) - self.RECENT_TRADES_ALLOWED_TIME
        recently_closed_trades = trading_api.get_trade_history(self.exchange_manager, symbol=self.symbol,
                                                               since=recent_trades_time)
        recently_closed_trades = sorted(recently_closed_trades, key=lambda trade: trade.origin_price)

        missing_orders, state, candidate_flat_increment = self._analyse_current_orders_situation(sorted_orders,
                                                                                                 recently_closed_trades)
        self._set_increment_and_spread(current_price, candidate_flat_increment)

        highest_buy = min(current_price, self.highest_sell)
        lowest_sell = max(current_price, self.lowest_buy)
        buy_orders = self._create_orders(self.lowest_buy, highest_buy, trading_enums.TradeOrderSide.BUY, sorted_orders,
                                         current_price, missing_orders, state, self.buy_funds, ignore_available_funds)
        sell_orders = self._create_orders(lowest_sell, self.highest_sell, trading_enums.TradeOrderSide.SELL, sorted_orders,
                                          current_price, missing_orders, state, self.sell_funds, ignore_available_funds)

        if state == self.NEW:
            self._set_virtual_orders(buy_orders, sell_orders, self.operational_depth)

        return buy_orders, sell_orders

    def _set_increment_and_spread(self, current_price, candidate_flat_increment=None):
        if self.flat_increment is None and candidate_flat_increment is not None:
            self.flat_increment = decimal.Decimal(str(candidate_flat_increment))
        elif self.flat_increment is None:
            self.flat_increment = trading_personal_data.decimal_adapt_price(self.symbol_market,
                                                                            current_price * self.increment)
        if self.flat_spread is None and self.flat_increment is not None:
            self.flat_spread = trading_personal_data.decimal_adapt_price(self.symbol_market,
                                                                         self.spread * self.flat_increment / self.increment)

        self.flat_increment = trading_personal_data.decimal_adapt_price(self.symbol_market, self.flat_increment)

    def _get_interfering_orders_pairs(self, orders):
        # Not a problem if allowed funds are set
        if (self.buy_funds > 0 and self.sell_funds > 0) \
                or (self.buy_volume_per_order > 0 and self.sell_volume_per_order > 0):
            return []
        else:
            current_base, current_quote = symbol_util.parse_symbol(self.symbol).base_and_quote()
            interfering_pairs = set()
            for order in orders:
                order_symbol = order.symbol
                if order_symbol != self.symbol:
                    base, quote = symbol_util.parse_symbol(order_symbol).base_and_quote()
                    if current_base == base or current_base == quote or current_quote == base or current_quote == quote:
                        interfering_pairs.add(order_symbol)
            return interfering_pairs

    def _check_params(self):
        if self.increment >= self.spread:
            self.logger.error(f"Your spread_percent parameter should always be higher than your increment_percent"
                              f" parameter: average profit is spread-increment. ({self.symbol})")
        if self.lowest_buy >= self.highest_sell:
            self.logger.error(f"Your lower_bound should always be lower than your upper_bound ({self.symbol})")

    def _analyse_current_orders_situation(self, sorted_orders, recently_closed_trades):
        if not sorted_orders:
            return None, self.NEW, None
        # check if orders are staggered orders
        return self._bootstrap_parameters(sorted_orders, recently_closed_trades)

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
            # create staggered orders
            funds_to_use = self._get_maximum_traded_funds(allowed_funds,
                                                          order_limiting_currency_amount,
                                                          order_limiting_currency,
                                                          selling,
                                                          ignore_available_funds)
            if funds_to_use == 0:
                return []
            starting_bound = lower_bound * (1 + self.spread / 2) if selling else upper_bound * (1 - self.spread / 2)
            self.flat_spread = trading_personal_data.decimal_adapt_price(self.symbol_market,
                                                                         current_price * self.spread)
            self._create_new_orders(orders, current_price, selling, lower_bound, upper_bound,
                                    funds_to_use, order_limiting_currency, starting_bound, side,
                                    True, self.mode, order_limiting_currency_amount)

        if state == self.FILL:
            # complete missing orders
            if missing_orders and [o for o in missing_orders if o[1] is side]:
                max_quant_per_order = order_limiting_currency_amount / len([o for o in missing_orders if o[1] is side])
                missing_orders_around_spread = []
                for missing_order_price, missing_order_side in missing_orders:
                    if missing_order_side == side:
                        previous_o = None
                        following_o = None
                        for o in sorted_orders:
                            if previous_o is None:
                                previous_o = o
                            elif o.origin_price > missing_order_price:
                                following_o = o
                                break
                            else:
                                previous_o = o
                        if previous_o.side == following_o.side:
                            decimal_missing_order_price = decimal.Decimal(str(missing_order_price))
                            # missing order between similar orders
                            quantity = min(data_util.mean([previous_o.origin_quantity, following_o.origin_quantity]),
                                           max_quant_per_order / decimal_missing_order_price)
                            orders.append(OrderData(missing_order_side, decimal.Decimal(str(quantity)),
                                                    decimal_missing_order_price, self.symbol, False))
                            self.logger.debug(f"Creating missing orders not around spread: {orders[-1]} "
                                              f"for {self.symbol}")
                        else:
                            missing_orders_around_spread.append((missing_order_price, missing_order_side))

                if missing_orders_around_spread:
                    # missing order next to spread
                    starting_bound = upper_bound if selling else lower_bound
                    increment_window = self.flat_increment / 2
                    order_limiting_currency_available_amount = trading_api.get_portfolio_currency(self.exchange_manager, order_limiting_currency).available
                    portfolio_total = trading_api.get_portfolio_currency(self.exchange_manager, order_limiting_currency).total
                    order_limiting_currency_amount = portfolio_total
                    if order_limiting_currency_available_amount:
                        orders_count, average_order_quantity = \
                            self._get_order_count_and_average_quantity(current_price, selling, lower_bound,
                                                                       upper_bound, portfolio_total,
                                                                       currency, self.mode)

                        for missing_order_price, missing_order_side in missing_orders_around_spread:
                            limiting_amount_from_this_order = order_limiting_currency_amount
                            price = starting_bound
                            found_order = False
                            i = 0
                            while not found_order and i < orders_count:
                                quantity = self._get_quantity_from_iteration(average_order_quantity, self.mode,
                                                                             side, i, orders_count,
                                                                             price, price)
                                limiting_currency_quantity = quantity if selling else quantity / price
                                if price is not None and limiting_amount_from_this_order > 0 and \
                                        price - increment_window <= missing_order_price <= price + increment_window:
                                    decimal_order_limiting_currency_available_amount = \
                                        decimal.Decimal(str(order_limiting_currency_available_amount))
                                    if limiting_currency_quantity > limiting_amount_from_this_order or \
                                            limiting_currency_quantity > decimal_order_limiting_currency_available_amount:
                                        limiting_currency_quantity = min(limiting_amount_from_this_order,
                                                                         decimal_order_limiting_currency_available_amount)
                                    found_order = True
                                    if limiting_currency_quantity is not None:
                                        orders.append(OrderData(side, decimal.Decimal(str(limiting_currency_quantity)),
                                                                decimal.Decimal(str(price)), self.symbol, False))
                                        self.logger.debug(f"Creating missing order around spread {orders[-1]} "
                                                          f"for {self.symbol}")
                                price = price - self.flat_increment if selling else price + self.flat_increment
                                limiting_amount_from_this_order -= limiting_currency_quantity
                                i += 1

        elif state == self.ERROR:
            self.logger.error(f"Impossible to create {self.ORDERS_DESC} orders for {self.symbol} when incompatible "
                              f"order are already in place. Cancel these orders of you want to use this trading mode.")
        return orders

    def _get_maximum_traded_funds(self, allowed_funds, total_available_funds, currency, selling, ignore_available_funds):
        to_trade_funds = total_available_funds
        if allowed_funds > 0:
            if total_available_funds < allowed_funds:
                self.logger.warning(
                    f"Impossible to create every {self.ORDERS_DESC} orders for {self.symbol} using the total "
                    f"{'sell' if selling else 'buy'} funds configuration ({allowed_funds}): not enough "
                    f"available {currency} funds ({total_available_funds}). Trying to use available funds only.")
                to_trade_funds = total_available_funds
            else:
                to_trade_funds = allowed_funds
        if not ignore_available_funds and self._is_initially_available_funds_set(currency):
            # check if enough funds are available
            unlocked_funds = self._get_available_funds(currency)
            if to_trade_funds > unlocked_funds:
                if unlocked_funds <= 0:
                    self.logger.error(f"Impossible to create {self.ORDERS_DESC} orders for {self.symbol}: {currency} "
                                      f"funds are already locked for other trading pairs.")
                    return 0
                self.logger.warning(f"Impossible to create {self.ORDERS_DESC} orders for {self.symbol} using the "
                                    f"total funds ({allowed_funds}): {currency} funds are already locked for other "
                                    f"trading pairs. Trying to use remaining funds only.")
                to_trade_funds = unlocked_funds
        return to_trade_funds

    def _create_new_orders(self, orders, current_price, selling, lower_bound, upper_bound,
                           order_limiting_currency_amount, order_limiting_currency, starting_bound, side,
                           virtual_orders, mode, total_available_funds):
        orders_count, average_order_quantity = \
            self._get_order_count_and_average_quantity(current_price, selling, lower_bound,
                                                       upper_bound, order_limiting_currency_amount,
                                                       order_limiting_currency, mode)
        # orders closest to the current price are added first
        for i in range(orders_count):
            price = self._get_price_from_iteration(starting_bound, selling, i)
            if price is not None:
                quantity = self._get_quantity_from_iteration(average_order_quantity, mode,
                                                             side, i, orders_count, price, starting_bound)
                if quantity is not None:
                    orders.append(OrderData(side, quantity, price, self.symbol, virtual_orders))
        if not orders:
            advise = "change change the strategy settings to make less but bigger orders." \
                if self._use_variable_orders_volume(side) else \
                f"reduce {'buy' if side is trading_enums.TradeOrderSide.BUY else 'sell'} the orders volume."
            self.logger.error(f"Not enough {order_limiting_currency} to create {side.name} orders. "
                              f"For the strategy to work better, add {order_limiting_currency} funds or "
                              f"{advise}")
        else:
            # register the locked orders funds
            if not self._is_initially_available_funds_set(order_limiting_currency):
                self._set_initially_available_funds(order_limiting_currency, total_available_funds)

    def _bootstrap_parameters(self, sorted_orders, recently_closed_trades):
        # no decimal.Decimal computation here
        mode = None
        spread = None
        increment = None
        bigger_buys_closer_to_center = None
        first_sell = None
        ratio = None
        state = self.FILL

        missing_orders = []

        previous_order = None

        only_sell = False
        only_buy = False
        if sorted_orders:
            if sorted_orders[0].side == trading_enums.TradeOrderSide.SELL:
                # only sell orders
                self.logger.warning(f"Only sell orders are online for {self.symbol}, now waiting for the price to "
                                    f"go up to create new buy orders.")
                first_sell = sorted_orders[0]
                only_sell = True
            if sorted_orders[-1].side == trading_enums.TradeOrderSide.BUY:
                # only buy orders
                self.logger.warning(f"Only buy orders are online for {self.symbol}, now waiting for the price to "
                                    f"go down to create new sell orders.")
                only_buy = True
            for order in sorted_orders:
                if order.symbol != self.symbol:
                    self.logger.warning(f"Error when analyzing orders for {self.symbol}: order.symbol != self.symbol.")
                    return None, self.ERROR, None
                spread_point = False
                if previous_order is None:
                    previous_order = order
                else:
                    if previous_order.side != order.side:
                        if spread is None:
                            if self.lowest_buy < self.current_price < self.highest_sell:
                                spread_point = True
                                delta_spread = order.origin_price - previous_order.origin_price

                                if increment is None:
                                    self.logger.warning(f"Error when analyzing orders for {self.symbol}: increment "
                                                        f"is None.")
                                    return None, self.ERROR, None
                                else:
                                    inferred_spread = self.flat_spread or self.spread * increment / self.increment
                                    missing_orders_count = (delta_spread - inferred_spread) / increment
                                    if missing_orders_count > 1 * 1.2:
                                        # missing orders around spread point: symmetrical orders were not created when
                                        # orders were filled => re-create them
                                        next_missing_order_price = previous_order.origin_price + increment
                                        half_spread = inferred_spread / 2
                                        spread_lower_boundary = self.current_price - half_spread
                                        spread_higher_boundary = self.current_price + half_spread

                                        # re-create buy orders starting from the closest buy up to spread
                                        while next_missing_order_price <= spread_lower_boundary:
                                            # missing buy order
                                            if not self._is_just_closed_order(next_missing_order_price,
                                                                              recently_closed_trades):
                                                missing_orders.append(
                                                    (next_missing_order_price, trading_enums.TradeOrderSide.BUY))
                                            next_missing_order_price += increment

                                        next_missing_order_price = order.origin_price - increment
                                        # re-create sell orders starting from the closest sell down to spread
                                        while next_missing_order_price >= spread_higher_boundary:
                                            # missing sell order
                                            if not self._is_just_closed_order(next_missing_order_price,
                                                                              recently_closed_trades):
                                                missing_orders.append(
                                                    (next_missing_order_price, trading_enums.TradeOrderSide.SELL))
                                            next_missing_order_price -= increment

                                        spread = inferred_spread
                                    else:
                                        spread = delta_spread

                                # calculations to infer ratio
                                last_buy_cost = previous_order.origin_price * previous_order.origin_quantity
                                first_buy_cost = sorted_orders[0].origin_price * sorted_orders[0].origin_quantity
                                bigger_buys_closer_to_center = last_buy_cost - first_buy_cost > 0
                                first_sell = order
                                ratio = last_buy_cost / first_buy_cost if bigger_buys_closer_to_center \
                                    else first_buy_cost / last_buy_cost
                            else:
                                self.logger.info(f"Current price ({self.current_price}) for {self.symbol} "
                                                 f"is out of range.")
                                return None, self.ERROR, None
                    if increment is None:
                        increment = self.flat_increment or order.origin_price - previous_order.origin_price
                        if increment <= 0:
                            self.logger.warning(f"Error when analyzing orders for {self.symbol}: increment <= 0.")
                            return None, self.ERROR, None
                    elif not spread_point:
                        delta_increment = order.origin_price - previous_order.origin_price
                        # skip not-yet-updated orders
                        if previous_order.side == order.side:
                            missing_orders_count = delta_increment / increment
                            if missing_orders_count > 2.5:
                                self.logger.warning(f"Error when analyzing orders for {self.symbol}: "
                                                    f"missing_orders_count > 2.5.")
                                if not self._is_just_closed_order(previous_order.origin_price + increment,
                                                                  recently_closed_trades):
                                    return None, self.ERROR, None
                            elif missing_orders_count > 1.5:
                                order_price = previous_order.origin_price + increment
                                if not self._is_just_closed_order(order_price, recently_closed_trades):
                                    if len(sorted_orders) < self.operational_depth and not recently_closed_trades:
                                        missing_orders.append((order_price, order.side))
                    previous_order = order

            if ratio is not None:
                first_sell_cost = first_sell.origin_price * first_sell.origin_quantity
                last_sell_cost = sorted_orders[-1].origin_price * sorted_orders[-1].origin_quantity
                bigger_sells_closer_to_center = first_sell_cost - last_sell_cost > 0

                if bigger_buys_closer_to_center is not None and bigger_sells_closer_to_center is not None:
                    if bigger_buys_closer_to_center:
                        if bigger_sells_closer_to_center:
                            mode = StrategyModes.NEUTRAL if 0.1 < ratio - 1 < 0.5 else StrategyModes.MOUNTAIN
                        else:
                            mode = StrategyModes.SELL_SLOPE
                    else:
                        if bigger_sells_closer_to_center:
                            mode = StrategyModes.BUY_SLOPE
                        else:
                            mode = StrategyModes.VALLEY

                if mode is None or increment is None or spread is None:
                    self.logger.warning(f"Error when analyzing orders for {self.symbol}: mode is None or increment "
                                        f"is None or spread is None.")
                    return None, self.ERROR, None
            if increment is None or (not (only_sell or only_buy) and spread is None):
                self.logger.warning(f"Error when analyzing orders for {self.symbol}: increment is None or "
                                    f"(not(only_sell or only_buy) and spread is None).")
                return None, self.ERROR, None
            return missing_orders, state, increment
        else:
            # no orders
            return None, self.ERROR, None

    def _is_just_closed_order(self, price, recently_closed_trades):
        if self.flat_increment is None:
            return len(recently_closed_trades)
        else:
            inc = self.flat_spread * decimal.Decimal("1.5")
            for trade in recently_closed_trades:
                if trade.origin_price - inc <= price <= trade.origin_price + inc:
                    return True
        return False

    @staticmethod
    def _spread_in_recently_closed_order(min_amount, max_amount, sorted_closed_orders):
        for order in sorted_closed_orders:
            if min_amount <= order.get_origin_price() <= max_amount:
                return True
        return False

    @staticmethod
    def _merged_and_sort_not_virtual_orders(buy_orders, sell_orders):
        # create sell orders first follows by buy orders
        return StaggeredOrdersTradingModeProducer._filter_virtual_order(sell_orders) + \
               StaggeredOrdersTradingModeProducer._filter_virtual_order(buy_orders)

    @staticmethod
    def _filter_virtual_order(orders):
        return [order for order in orders if not order.is_virtual]

    @staticmethod
    def _set_virtual_orders(buy_orders, sell_orders, operational_depth):
        # all orders that are further than self.operational_depth are virtual
        orders_count = 0
        buy_index = 0
        sell_index = 0
        at_least_one_added = True
        while orders_count < operational_depth and at_least_one_added:
            # priority to orders closer to current price
            at_least_one_added = False
            if len(buy_orders) > buy_index:
                buy_orders[buy_index].is_virtual = False
                buy_index += 1
                orders_count += 1
                at_least_one_added = True
            if len(sell_orders) > sell_index and orders_count < operational_depth:
                sell_orders[sell_index].is_virtual = False
                sell_index += 1
                orders_count += 1
                at_least_one_added = True

    def _get_order_count_and_average_quantity(self, current_price, selling, lower_bound, upper_bound, holdings,
                                              currency, mode):
        if lower_bound >= upper_bound:
            self.logger.error(f"Invalid bounds for {self.symbol}: too close to the current price")
            return 0, 0
        if selling:
            order_distance = upper_bound - (lower_bound + self.flat_spread / 2)
        else:
            order_distance = (upper_bound - self.flat_spread / 2) - lower_bound
        order_count_divisor = self.flat_increment
        orders_count = math.floor(order_distance / order_count_divisor + 1)
        if orders_count < 1:
            self.logger.warning(f"Impossible to create {'sell' if selling else 'buy'} orders for {currency}: "
                                f"not enough funds.")
            return 0, 0
        if self._use_variable_orders_volume(trading_enums.TradeOrderSide.SELL if selling
            else trading_enums.TradeOrderSide.BUY):
            return self._ensure_average_order_quantity(orders_count, current_price, selling, holdings,
                                                       currency, mode)
        else:
            return self._get_orders_count_from_fixed_volume(selling, current_price, holdings, orders_count)

    def _use_variable_orders_volume(self, side):
        return (self.sell_volume_per_order == decimal.Decimal(0) and side is trading_enums.TradeOrderSide.SELL) \
               or self.buy_volume_per_order == decimal.Decimal(0)

    def _get_orders_count_from_fixed_volume(self, selling, current_price, holdings, orders_count):
        volume_in_currency = self.sell_volume_per_order if selling else current_price * self.buy_volume_per_order
        orders_count = min(math.floor(holdings / volume_in_currency), orders_count)
        return orders_count, self.sell_volume_per_order if selling else self.buy_volume_per_order

    def _ensure_average_order_quantity(self, orders_count, current_price, selling,
                                       holdings, currency, mode):
        holdings_in_quote = holdings if selling else holdings / current_price
        average_order_quantity = holdings_in_quote / orders_count
        min_order_quantity, max_order_quantity = self._get_min_max_quantity(average_order_quantity, self.mode)
        if self.min_max_order_details[self.min_quantity] is not None \
                and self.min_max_order_details[self.min_cost] is not None:
            min_quantity = max(self.min_max_order_details[self.min_quantity],
                               self.min_max_order_details[self.min_cost] / current_price)
            if min_order_quantity < min_quantity:
                # 1.01 to account for order creation rounding
                if holdings_in_quote < average_order_quantity * ONE_PERCENT_DECIMAL:
                    return 0, 0
                elif self.limit_orders_count_if_necessary:
                    self.logger.warning(f"Not enough funds to create every {self.symbol} {self.ORDERS_DESC} "
                                        f"{trading_enums.TradeOrderSide.SELL.name if selling else trading_enums.TradeOrderSide.BUY.name} "
                                        f"orders according to exchange's rules. Creating the maximum possible number "
                                        f"of valid orders instead.")
                    return self._adapt_orders_count_and_quantity(holdings_in_quote, min_quantity, mode)
                else:
                    min_funds = self._get_min_funds(orders_count, min_quantity, self.mode, current_price)
                    self.logger.error(f"Impossible to create {self.symbol} {self.ORDERS_DESC} "
                                      f"{trading_enums.TradeOrderSide.SELL.name if selling else trading_enums.TradeOrderSide.BUY.name} "
                                      f"orders: minimum quantity for {self.mode.value} mode is lower than the minimum "
                                      f"allowed for this trading pair on this exchange: requested minimum: "
                                      f"{min_order_quantity} and exchange minimum is {min_quantity}. "
                                      f"Minimum required funds are {min_funds}{f' {currency}' if currency else ''}.")
                return 0, 0
        return orders_count, average_order_quantity

    def _adapt_orders_count_and_quantity(self, holdings, min_quantity, mode):
        # called when there are enough funds for at least one order but too many orders are requested
        min_average_quantity = self._get_average_quantity_from_exchange_minimal_requirements(min_quantity, mode)
        max_orders_count = math.floor(holdings / min_average_quantity)
        if max_orders_count > 0:
            # count remaining holdings if any
            average_quantity = min_average_quantity + \
                               (holdings - min_average_quantity * max_orders_count) / max_orders_count
            return max_orders_count, average_quantity
        return 0, 0

    def _get_price_from_iteration(self, starting_bound, is_selling, iteration):
        price_step = self.flat_increment * iteration
        price = starting_bound + price_step if is_selling else starting_bound - price_step
        if self.min_max_order_details[self.min_price] and price < self.min_max_order_details[self.min_price]:
            return None
        return price

    def _get_quantity_from_iteration(self, average_order_quantity, mode, side,
                                     iteration, max_iteration, price, starting_bound):
        multiplier_price_ratio = 1
        min_quantity, max_quantity = self._get_min_max_quantity(average_order_quantity, mode)
        delta = max_quantity - min_quantity
        if max_iteration == 1:
            quantity = average_order_quantity
        else:
            iterations_progress = iteration / (max_iteration - 1)
            if StrategyModeMultipliersDetails[mode][side] == INCREASING:
                multiplier_price_ratio = 1 - iterations_progress
            elif StrategyModeMultipliersDetails[mode][side] == DECREASING:
                multiplier_price_ratio = iterations_progress
            elif StrategyModeMultipliersDetails[mode][side] == STABLE:
                multiplier_price_ratio = 0
            if price <= 0:
                return None
            quantity_with_delta = (min_quantity +
                                   (decimal.Decimal(str(delta)) * decimal.Decimal(str(multiplier_price_ratio))))
            # when self.quote_volume_per_order is set, keep the same volume everywhere
            quantity = quantity_with_delta * (starting_bound / price if self._use_variable_orders_volume(side)
                                              else trading_constants.ONE)

        # reduce last order quantity to avoid python float representation issues
        if iteration == max_iteration - 1 and self._use_variable_orders_volume(side):
            quantity = quantity * decimal.Decimal("0.999")

        if self.min_max_order_details[self.min_quantity] and quantity < self.min_max_order_details[self.min_quantity]:
            return None
        cost = quantity * price
        if self.min_max_order_details[self.min_cost] and cost < self.min_max_order_details[self.min_cost]:
            return None
        return quantity

    def _get_min_funds(self, orders_count, min_order_quantity, mode, current_price):
        mode_multiplier = StrategyModeMultipliersDetails[mode][MULTIPLIER]
        required_average_quantity = min_order_quantity / (1 - mode_multiplier / 2)

        if self.min_cost in self.min_max_order_details:
            average_cost = current_price * required_average_quantity
            if self.min_max_order_details[self.min_cost]:
                min_cost = self.min_max_order_details[self.min_cost]
                if average_cost < min_cost:
                    required_average_quantity = min_cost / current_price

        return orders_count * required_average_quantity

    @staticmethod
    def _get_average_quantity_from_exchange_minimal_requirements(exchange_min, mode):
        mode_multiplier = StrategyModeMultipliersDetails[mode][MULTIPLIER]
        # add 1% to prevent rounding issues
        return exchange_min / (1 - mode_multiplier / 2) * ONE_PERCENT_DECIMAL

    @staticmethod
    def _get_min_max_quantity(average_order_quantity, mode):
        if mode is None:
            fdsf=1
        mode_multiplier = StrategyModeMultipliersDetails[mode][MULTIPLIER]
        min_quantity = average_order_quantity * (1 - mode_multiplier / 2)
        max_quantity = average_order_quantity * (1 + mode_multiplier / 2)
        return min_quantity, max_quantity

    async def _create_order(self, order, current_price):
        data = {
            StaggeredOrdersTradingModeConsumer.ORDER_DATA_KEY: order,
            StaggeredOrdersTradingModeConsumer.CURRENT_PRICE_KEY: current_price,
            StaggeredOrdersTradingModeConsumer.SYMBOL_MARKET_KEY: self.symbol_market,
        }
        state = trading_enums.EvaluatorStates.LONG if order.side is trading_enums.TradeOrderSide.BUY else trading_enums.EvaluatorStates.SHORT
        await self.submit_trading_evaluation(cryptocurrency=self.trading_mode.cryptocurrency,
                                             symbol=self.trading_mode.symbol,
                                             time_frame=None,
                                             state=state,
                                             data=data)

    async def _create_not_virtual_orders(self, orders_to_create, current_price):
        for order in orders_to_create:
            await self._create_order(order, current_price)
            base, quote = symbol_util.parse_symbol(order.symbol).base_and_quote()
            # keep track of the required funds
            volume = order.quantity if order.side is trading_enums.TradeOrderSide.SELL \
                else order.price * order.quantity
            self._remove_from_available_funds(base if order.side is trading_enums.TradeOrderSide.SELL else quote,
                                              volume)

    def _refresh_symbol_data(self, symbol_market):
        min_quantity, max_quantity, min_cost, max_cost, min_price, max_price = \
            trading_personal_data.get_min_max_amounts(symbol_market)
        self.min_max_order_details[self.min_quantity] = None if min_quantity is None \
            else decimal.Decimal(str(min_quantity))
        self.min_max_order_details[self.max_quantity] = None if max_quantity is None \
            else decimal.Decimal(str(max_quantity))
        self.min_max_order_details[self.min_cost] = None if min_cost is None \
            else decimal.Decimal(str(min_cost))
        self.min_max_order_details[self.max_cost] = None if max_cost is None \
            else decimal.Decimal(str(max_cost))
        self.min_max_order_details[self.min_price] = None if min_price is None \
            else decimal.Decimal(str(min_price))
        self.min_max_order_details[self.max_price] = None if max_price is None \
            else decimal.Decimal(str(max_price))

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return False

    def _remove_from_available_funds(self, currency, amount) -> None:
        StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS[self.exchange_manager.id][currency] = \
            StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS[self.exchange_manager.id][currency] - amount

    def _set_initially_available_funds(self, currency, amount) -> None:
        if self.exchange_manager.id not in StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS:
            StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS[self.exchange_manager.id] = {}
        StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS[self.exchange_manager.id][currency] = amount

    def _is_initially_available_funds_set(self, currency) -> bool:
        try:
            return currency in StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS[self.exchange_manager.id]
        except KeyError:
            return False

    def _get_available_funds(self, currency) -> float:
        try:
            return StaggeredOrdersTradingModeProducer.AVAILABLE_FUNDS[self.exchange_manager.id][currency]
        except KeyError:
            return 0

    # syntax: "async with xxx.get_lock():"
    def get_lock(self):
        return self.lock
