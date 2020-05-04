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
from ccxt import InsufficientFunds
from enum import Enum
from dataclasses import dataclass
from math import floor
from asyncio import Lock, create_task, get_event_loop

from octobot_commons.constants import DAYS_TO_SECONDS, PORTFOLIO_TOTAL
from octobot_commons.symbol_util import split_symbol
from octobot_commons import data_util
from octobot_channels.constants import CHANNEL_WILDCARD
from octobot_trading.api.exchange import get_fees, get_exchange_current_time
from octobot_trading.api.portfolio import get_portfolio_currency
from octobot_trading.api.trades import get_trade_history
from octobot_trading.channels.exchange_channel import get_chan
from octobot_trading.channels.orders import OrdersChannel
from octobot_trading.constants import MODE_CHANNEL
from octobot_trading.enums import EvaluatorStates, TraderOrderType, TradeOrderSide, \
    ExchangeConstantsMarketPropertyColumns, ExchangeConstantsOrderColumns, OrderStatus
from octobot_trading.modes.abstract_trading_mode import AbstractTradingMode
from octobot_trading.consumers.abstract_mode_consumer import AbstractTradingModeConsumer
from octobot_trading.orders.order_adapter import adapt_price, check_and_adapt_order_details_if_necessary
from octobot_trading.orders.order_factory import create_order_instance
from octobot_trading.orders.order_util import get_pre_order_data, get_min_max_amounts
from octobot_trading.producers.abstract_mode_producer import AbstractTradingModeProducer


class StrategyModes(Enum):
    NEUTRAL = "neutral"
    MOUNTAIN = "mountain"
    VALLEY = "valley"
    SELL_SLOPE = "sell slope"
    BUY_SLOPE = "buy slope"


INCREASING = "increasing_towards_current_price"
DECREASING = "decreasing_towards_current_price"
MULTIPLIER = "multiplier"


StrategyModeMultipliersDetails = {
    StrategyModes.NEUTRAL: {
        MULTIPLIER: 0.3,
        TradeOrderSide.BUY: INCREASING,
        TradeOrderSide.SELL: INCREASING
    },
    StrategyModes.MOUNTAIN: {
        MULTIPLIER: 1,
        TradeOrderSide.BUY: INCREASING,
        TradeOrderSide.SELL: INCREASING
    },
    StrategyModes.VALLEY: {
        MULTIPLIER: 1,
        TradeOrderSide.BUY: DECREASING,
        TradeOrderSide.SELL: DECREASING
    },
    StrategyModes.BUY_SLOPE: {
        MULTIPLIER: 1,
        TradeOrderSide.BUY: DECREASING,
        TradeOrderSide.SELL: INCREASING
    },
    StrategyModes.SELL_SLOPE: {
        MULTIPLIER: 1,
        TradeOrderSide.BUY: INCREASING,
        TradeOrderSide.SELL: DECREASING
    }
}


@dataclass
class OrderData:
    side: TradeOrderSide = None
    quantity: float = 0
    price: float = 0
    symbol: str = 0
    is_virtual: bool = True


class StaggeredOrdersTradingMode(AbstractTradingMode):
    CONFIG_PAIR_SETTINGS = "pair_settings"
    CONFIG_PAIR = "pair"
    CONFIG_MODE = "mode"
    CONFIG_SPREAD = "spread_percent"
    CONFIG_INCREMENT_PERCENT = "increment_percent"
    CONFIG_LOWER_BOUND = "lower_bound"
    CONFIG_UPPER_BOUND = "upper_bound"
    CONFIG_ALLOW_INSTANT_FILL = "allow_instant_fill"
    CONFIG_OPERATIONAL_DEPTH = "operational_depth"

    def __init__(self, config, exchange):
        super().__init__(config, exchange)
        self.load_config()

    def get_current_state(self) -> (str, float):
        order = self.exchange_manager.exchange_personal_data.orders_manager.get_open_orders(self.symbol)
        sell_count = len([o for o in order if o.side == TradeOrderSide.SELL])
        buy_count = len(order) - sell_count
        if buy_count > sell_count:
            state = EvaluatorStates.LONG
        elif buy_count < sell_count:
            state = EvaluatorStates.SHORT
        else:
            state = EvaluatorStates.NEUTRAL
        return state.name, f"{buy_count} buy {sell_count} sell"

    @staticmethod
    def is_backtestable():
        return False

    async def create_producers(self) -> list:
        mode_producer = StaggeredOrdersTradingModeProducer(get_chan(MODE_CHANNEL, self.exchange_manager.id),
                                                           self.config, self, self.exchange_manager)
        await mode_producer.run()
        return [mode_producer]

    async def create_consumers(self) -> list:
        # trading mode consumer
        mode_consumer = StaggeredOrdersTradingModeConsumer(self)
        await get_chan(MODE_CHANNEL, self.exchange_manager.id).new_consumer(
            consumer_instance=mode_consumer,
            trading_mode_name=self.get_name(),
            cryptocurrency=self.cryptocurrency if self.cryptocurrency else CHANNEL_WILDCARD,
            symbol=self.symbol if self.symbol else CHANNEL_WILDCARD,
            time_frame=self.time_frame if self.time_frame else CHANNEL_WILDCARD)

        # order consumer: filter by symbol not be triggered only on this symbol's orders
        order_consumer = await get_chan(OrdersChannel.get_name(), self.exchange_manager.id).new_consumer(
            self._order_notification_callback,
            symbol=self.symbol if self.symbol else CHANNEL_WILDCARD
        )
        return [mode_consumer, order_consumer]

    async def _order_notification_callback(self, exchange, exchange_id, cryptocurrency, symbol, order,
                                           is_closed, is_updated, is_from_bot):
        if order[ExchangeConstantsOrderColumns.STATUS.value] == OrderStatus.FILLED.value and is_from_bot:
            async with self.producers[0].get_lock():
                await self.producers[0].order_filled_callback(order)

    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        return False

    def set_default_config(self):
        raise RuntimeError(f"Impossible to start {self.get_name()} without a valid configuration file.")


class StaggeredOrdersTradingModeConsumer(AbstractTradingModeConsumer):
    ORDER_DATA_KEY = "order_data"
    CURRENT_PRICE_KEY = "current_price"
    SYMBOL_MARKET_KEY = "symbol_market"

    # creates a new order
    async def internal_callback(self, trading_mode_name, cryptocurrency, symbol, time_frame, final_note, state, data):
        # creates a new order (or multiple split orders), always check self.can_create_order() first.
        await self.create_order_if_possible(symbol, final_note, state, data=data)

    async def create_new_orders(self, symbol, final_note, state, **kwargs):
        # use dict default getter: can't afford missing data
        data = kwargs["data"]
        order_data = data[self.ORDER_DATA_KEY]
        current_price = data[self.CURRENT_PRICE_KEY]
        symbol_market = data[self.SYMBOL_MARKET_KEY]
        return await self.create_order(order_data, current_price, symbol_market)

    async def create_order(self, order_data, current_price, symbol_market):
        created_order = None
        currency, market = split_symbol(order_data.symbol)
        try:
            for order_quantity, order_price in check_and_adapt_order_details_if_necessary(order_data.quantity,
                                                                                          order_data.price,
                                                                                          symbol_market):
                selling = order_data.side == TradeOrderSide.SELL
                if selling:
                    if get_portfolio_currency(self.exchange_manager, currency) < order_quantity:
                        return None
                elif get_portfolio_currency(self.exchange_manager, market) < order_quantity * order_price:
                    return None
                order_type = TraderOrderType.SELL_LIMIT if selling else TraderOrderType.BUY_LIMIT
                current_order = create_order_instance(trader=self.exchange_manager.trader,
                                                      order_type=order_type,
                                                      symbol=order_data.symbol,
                                                      current_price=current_price,
                                                      quantity=order_quantity,
                                                      price=order_price)
                created_order = await self.exchange_manager.trader.create_order(current_order)
        except InsufficientFunds as e:
            raise e
        except Exception as e:
            self.logger.error(f"Failed to create order : {e}. Order: {order_data}")
            self.logger.exception(e)
            return None
        return created_order


class StaggeredOrdersTradingModeProducer(AbstractTradingModeProducer):

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
    HEALTH_CHECK_INTERVAL_SECS = DAYS_TO_SECONDS * 3
    # recent filled allowed time delay to consider as pending order_filled callback
    RECENT_TRADES_ALLOWED_TIME = 10
    # when True, orders creation/health check will be performed on start()
    SCHEDULE_ORDERS_CREATION_ON_START = True

    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)
        # no state for this evaluator: always neutral
        self.state = EvaluatorStates.NEUTRAL
        self.symbol = trading_mode.symbol
        self.symbol_market = None
        self.min_max_order_details = {}
        fees = get_fees(exchange_manager, self.symbol)
        self.max_fees = max(fees[ExchangeConstantsMarketPropertyColumns.TAKER.value],
                            fees[ExchangeConstantsMarketPropertyColumns.MAKER.value])
        self.flat_increment = None
        self.flat_spread = None
        self.current_price = None
        self.scheduled_health_check = None

        self.healthy = False

        # used not to refresh orders when order_fill_callback is processing
        self.lock = Lock()

        # staggered orders strategy parameters
        self.symbol_trading_config = None
        try:
            for config in self.trading_mode.trading_config[self.trading_mode.CONFIG_PAIR_SETTINGS]:
                if config[self.trading_mode.CONFIG_PAIR] == self.symbol:
                    self.symbol_trading_config = config
        except KeyError as e:
            error_message = f"Impossible to start staggered orders for {self.symbol}: missing configuration in " \
                f"trading mode config file. See Default/StaggeredOrdersTradingMode.json for a config example."
            self.logger.exception(e, True, error_message)
            return
        if self.symbol_trading_config is None:
            configured_staggered_pairs = \
                [c[self.trading_mode.CONFIG_PAIR]
                 for c in self.trading_mode.trading_config[self.trading_mode.CONFIG_PAIR_SETTINGS]]
            self.logger.error(f"No staggered orders configuration for trading pair: {self.symbol}. Add this pair's "
                              f"details into your staggered orders configuration or remove it from current traded "
                              f"pairs. Configured staggered orders pairs are {', '.join(configured_staggered_pairs)}")
            return
        mode = ""
        try:
            mode = self.symbol_trading_config[self.trading_mode.CONFIG_MODE]
            self.mode = StrategyModes(mode)
        except ValueError as e:
            self.logger.error(f"Invalid staggered orders strategy mode: {mode} for {self.symbol}"
                              f"supported modes are {[m.value for m in StrategyModes]}")
            raise e
        self.spread = self.symbol_trading_config[self.trading_mode.CONFIG_SPREAD] / 100
        self.increment = self.symbol_trading_config[self.trading_mode.CONFIG_INCREMENT_PERCENT] / 100
        self.operational_depth = self.symbol_trading_config[self.trading_mode.CONFIG_OPERATIONAL_DEPTH]
        self.lowest_buy = self.symbol_trading_config[self.trading_mode.CONFIG_LOWER_BOUND]
        self.highest_sell = self.symbol_trading_config[self.trading_mode.CONFIG_UPPER_BOUND]

        self._check_params()
        self.healthy = True

    async def start(self) -> None:
        await super().start()
        if StaggeredOrdersTradingModeProducer.SCHEDULE_ORDERS_CREATION_ON_START and self.healthy:
            await self._ensure_staggered_orders_and_reschedule()

    async def stop(self):
        if self.trading_mode is not None:
            self.trading_mode.consumers[0].flush()
        if self.scheduled_health_check is not None:
            self.scheduled_health_check.cancel()
        await super().stop()

    async def set_final_eval(self, matrix_id: str, cryptocurrency: str, symbol: str, time_frame):
        # nothing to do: this is not a strategy related trading mode
        pass

    def _schedule_order_refresh(self):
        # schedule order creation / health check
        create_task(self._ensure_staggered_orders_and_reschedule())

    async def _ensure_staggered_orders_and_reschedule(self):
        await self._ensure_staggered_orders()
        if not self.should_stop:
            self.scheduled_health_check = get_event_loop().call_later(self.HEALTH_CHECK_INTERVAL_SECS,
                                                                      self._schedule_order_refresh)

    async def _ensure_staggered_orders(self):
        _, _, _, self.current_price, self.symbol_market = await get_pre_order_data(self.exchange_manager,
                                                                                   symbol=self.symbol,
                                                                                   timeout=self.PRICE_FETCHING_TIMEOUT)
        await self.create_state(self.current_price)

    async def create_state(self, current_price):
        if current_price is not None:
            self._refresh_symbol_data(self.symbol_market)
            async with self.get_lock():
                if self.exchange_manager.trader.is_enabled:
                    await self._handle_staggered_orders(current_price)

    async def order_filled_callback(self, filled_order):
        # create order on the order side
        now_selling = filled_order[ExchangeConstantsOrderColumns.SIDE.value] == TradeOrderSide.BUY.value
        new_side = TradeOrderSide.SELL if now_selling else TradeOrderSide.BUY
        if self.flat_increment is None:
            self.logger.error(f"Impossible to create symmetrical order for {self.symbol}: "
                              f"self.flat_increment is unset.")
            return
        if self.flat_spread is None:
            self.flat_spread = adapt_price(self.symbol_market, self.spread * self.flat_increment / self.increment)
        price_increment = self.flat_spread - self.flat_increment
        filled_price = filled_order[ExchangeConstantsOrderColumns.PRICE.value]
        filled_volume = filled_order[ExchangeConstantsOrderColumns.FILLED.value]
        price = filled_price + price_increment if now_selling else filled_price - price_increment
        new_order_quantity = filled_volume
        if not now_selling:
            # buying => adapt order quantity
            new_order_quantity = filled_price / price * filled_volume
        quantity_change = self.max_fees
        quantity = new_order_quantity * (1 - quantity_change)
        new_order = OrderData(new_side, quantity, price, self.symbol)

        async with self.exchange_manager.exchange_personal_data.portfolio_manager.portfolio.lock:
            await self._create_order(new_order, filled_price)

    async def _handle_staggered_orders(self, current_price):
        buy_orders, sell_orders = await self._generate_staggered_orders(current_price)
        staggered_orders = self._alternate_not_virtual_orders(buy_orders, sell_orders)
        async with self.exchange_manager.exchange_personal_data.portfolio_manager.portfolio.lock:
            await self._create_not_virtual_orders(staggered_orders, current_price)

    async def _generate_staggered_orders(self, current_price):
        order_manager = self.exchange_manager.exchange_personal_data.orders_manager
        interfering_orders_pairs = self._get_interfering_orders_pairs(order_manager.get_open_orders())
        if interfering_orders_pairs:
            self.logger.error(f"Impossible to create staggered orders for {self.symbol} with interfering orders "
                              f"using pair(s): {interfering_orders_pairs}. Staggered orders require no other orders "
                              f"in both quote and base.")
            return [], []
        existing_orders = order_manager.get_open_orders(self.symbol)

        sorted_orders = sorted(existing_orders, key=lambda order: order.origin_price)

        recent_trades_time = get_exchange_current_time(self.exchange_manager) - self.RECENT_TRADES_ALLOWED_TIME
        recently_closed_trades = get_trade_history(self.exchange_manager, symbol=self.symbol, since=recent_trades_time)
        recently_closed_trades = sorted(recently_closed_trades, key=lambda trade: trade.origin_price)

        missing_orders, state, candidate_flat_increment = self._analyse_current_orders_situation(sorted_orders,
                                                                                                 recently_closed_trades)
        if self.flat_increment is None and candidate_flat_increment is not None:
            self.flat_increment = candidate_flat_increment
        elif self.flat_increment is None:
            self.flat_increment = adapt_price(self.symbol_market, current_price * self.increment)
        if self.flat_spread is None and self.flat_increment is not None:
            self.flat_spread = adapt_price(self.symbol_market,  self.spread * self.flat_increment / self.increment)

        self.flat_increment = adapt_price(self.symbol_market, self.flat_increment)

        buy_high = min(current_price, self.highest_sell)
        sell_low = max(current_price, self.lowest_buy)
        buy_orders = self._create_orders(self.lowest_buy, buy_high, TradeOrderSide.BUY, sorted_orders,
                                         current_price, missing_orders, state)
        sell_orders = self._create_orders(sell_low, self.highest_sell, TradeOrderSide.SELL, sorted_orders,
                                          current_price, missing_orders, state)

        if state == self.NEW:
            self._set_virtual_orders(buy_orders, sell_orders, self.operational_depth)

        return buy_orders, sell_orders

    def _get_interfering_orders_pairs(self, orders):
        current_base, current_quote = split_symbol(self.symbol)
        interfering_pairs = set()
        for order in orders:
            order_symbol = order.symbol
            if order_symbol != self.symbol:
                base, quote = split_symbol(order_symbol)
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
                       current_price, missing_orders, state):

        if lower_bound >= upper_bound:
            self.logger.warning(f"No {side} orders for {self.symbol} possible: current price beyond boundaries.")
            return []

        orders = []
        selling = side == TradeOrderSide.SELL

        currency, market = split_symbol(self.symbol)
        order_limiting_currency = currency if selling else market

        order_limiting_currency_amount = get_portfolio_currency(self.exchange_manager, order_limiting_currency)
        if state == self.NEW:
            # create staggered orders

            starting_bound = lower_bound * (1 + self.spread / 2) if selling else upper_bound * (1 - self.spread / 2)
            self.flat_spread = adapt_price(self.symbol_market, current_price * self.spread)
            orders_count, average_order_quantity = \
                self._get_order_count_and_average_quantity(current_price, selling, lower_bound,
                                                           upper_bound, order_limiting_currency_amount,
                                                           currency=order_limiting_currency)
            for i in range(orders_count):
                price = self._get_price_from_iteration(starting_bound, selling, i)
                if price is not None:
                    quantity = self._get_quantity_from_iteration(average_order_quantity, self.mode,
                                                                 side, i, orders_count, price)
                    if quantity is not None:
                        orders.append(OrderData(side, quantity, price, self.symbol))
            if not orders:
                self.logger.error(f"Not enough {order_limiting_currency} to create {side.name} orders. "
                                  f"For the strategy to work better, add {order_limiting_currency} funds or "
                                  f"change change the strategy settings to make less but bigger orders.")
            else:
                orders.reverse()

        if state == self.FILL:
            # complete missing orders
            if missing_orders:
                max_quant_per_order = order_limiting_currency_amount / len([o for o in missing_orders if o[1] == side])
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
                            # missing order between similar orders
                            quantity = min(data_util.mean([previous_o.origin_quantity, following_o.origin_quantity]),
                                           max_quant_per_order / missing_order_price)
                            orders.append(OrderData(missing_order_side, quantity,
                                                    missing_order_price, self.symbol, False))
                            self.logger.debug(f"Creating missing orders not around spread: {orders[-1]} "
                                              f"for {self.symbol}")
                        else:
                            missing_orders_around_spread.append((missing_order_price, missing_order_side))

                if missing_orders_around_spread:
                    # missing order next to spread
                    starting_bound = upper_bound if selling else lower_bound
                    increment_window = self.flat_increment/2
                    order_limiting_currency_available_amount = get_portfolio_currency(self.exchange_manager,
                                                                                      order_limiting_currency)
                    portfolio_total = get_portfolio_currency(self.exchange_manager,
                                                             order_limiting_currency,
                                                             portfolio_type=PORTFOLIO_TOTAL)
                    order_limiting_currency_amount = portfolio_total
                    if order_limiting_currency_available_amount:
                        orders_count, average_order_quantity = \
                            self._get_order_count_and_average_quantity(current_price, selling, lower_bound,
                                                                       upper_bound, portfolio_total,
                                                                       currency=order_limiting_currency)
                        for missing_order_price, missing_order_side in missing_orders_around_spread:
                            limiting_amount_from_this_order = order_limiting_currency_amount
                            price = starting_bound
                            found_order = False
                            i = 0
                            while not found_order and i < orders_count:
                                quantity = self._get_quantity_from_iteration(average_order_quantity, self.mode,
                                                                             side, i, orders_count,
                                                                             price)
                                limiting_currency_quantity = quantity if selling else quantity / price
                                if price is not None and limiting_amount_from_this_order > 0 and \
                                        price-increment_window <= missing_order_price <= price+increment_window:

                                    if limiting_currency_quantity > limiting_amount_from_this_order or \
                                            limiting_currency_quantity > order_limiting_currency_available_amount:
                                        limiting_currency_quantity = min(limiting_amount_from_this_order,
                                                                         order_limiting_currency_available_amount)
                                    found_order = True
                                    if limiting_currency_quantity is not None:
                                        orders.append(OrderData(side, limiting_currency_quantity, price,
                                                                self.symbol, False))
                                        self.logger.debug(f"Creating missing order around spread {orders[-1]} "
                                                          f"for {self.symbol}")
                                price = price - self.flat_increment if selling else price + self.flat_increment
                                limiting_amount_from_this_order -= limiting_currency_quantity
                                i += 1

        elif state == self.ERROR:
            self.logger.error(f"Impossible to create staggered orders for {self.symbol} when incompatible order "
                              f"are already in place. Cancel these orders of you want to use this trading mode.")
        return orders

    def _bootstrap_parameters(self, sorted_orders, recently_closed_trades):
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
            if sorted_orders[0].side == TradeOrderSide.SELL:
                # only sell orders
                self.logger.warning(f"Only sell orders are online for {self.symbol}, now waiting for the price to "
                                    f"go up to create new buy orders.")
                first_sell = sorted_orders[0]
                only_sell = True
            if sorted_orders[-1].side == TradeOrderSide.BUY:
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
                                    inferred_spread = self.flat_spread or self.spread*increment/self.increment
                                    missing_orders_count = (delta_spread-inferred_spread)/increment
                                    if missing_orders_count > 1*1.2:
                                        # missing orders around spread point: symmetrical orders were not created when
                                        # orders were filled => re-create them
                                        next_missing_order_price = previous_order.origin_price + increment
                                        half_spread = inferred_spread/2
                                        spread_lower_boundary = self.current_price - half_spread
                                        spread_higher_boundary = self.current_price + half_spread

                                        # re-create buy orders starting from the closest buy up to spread
                                        while next_missing_order_price <= spread_lower_boundary:
                                            # missing buy order
                                            if not self._is_just_closed_order(next_missing_order_price,
                                                                              recently_closed_trades):
                                                missing_orders.append((next_missing_order_price, TradeOrderSide.BUY))
                                            next_missing_order_price += increment

                                        next_missing_order_price = order.origin_price - increment
                                        # re-create sell orders starting from the closest sell down to spread
                                        while next_missing_order_price >= spread_higher_boundary:
                                            # missing sell order
                                            if not self._is_just_closed_order(next_missing_order_price,
                                                                              recently_closed_trades):
                                                missing_orders.append((next_missing_order_price, TradeOrderSide.SELL))
                                            next_missing_order_price -= increment

                                        spread = inferred_spread
                                    else:
                                        spread = delta_spread

                                # calculations to infer ratio
                                last_buy_cost = previous_order.origin_price*previous_order.origin_quantity
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
                            missing_orders_count = delta_increment/increment
                            if missing_orders_count > 2.5:
                                self.logger.warning(f"Error when analyzing orders for {self.symbol}: "
                                                    f"missing_orders_count > 2.5.")
                                if not self._is_just_closed_order(previous_order.origin_price+increment,
                                                                  recently_closed_trades):
                                    return None, self.ERROR, None
                            elif missing_orders_count > 1.5:
                                order_price = previous_order.origin_price+increment
                                if not self._is_just_closed_order(order_price, recently_closed_trades):
                                    if len(sorted_orders) < self.operational_depth and not recently_closed_trades:
                                        missing_orders.append((order_price, order.side))
                    previous_order = order

            if ratio is not None:
                first_sell_cost = first_sell.origin_price*first_sell.origin_quantity
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
            if increment is None or (not(only_sell or only_buy) and spread is None):
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
            inc = self.flat_spread*1.5
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
    def _alternate_not_virtual_orders(buy_orders, sell_orders):
        not_virtual_buy_orders = StaggeredOrdersTradingModeProducer._filter_virtual_order(buy_orders)
        not_virtual_sell_orders = StaggeredOrdersTradingModeProducer._filter_virtual_order(sell_orders)
        alternated_orders_list = []
        for i in range(max(len(not_virtual_buy_orders), len(not_virtual_sell_orders))):
            if i < len(not_virtual_buy_orders):
                alternated_orders_list.append(not_virtual_buy_orders[i])
            if i < len(not_virtual_sell_orders):
                alternated_orders_list.append(not_virtual_sell_orders[i])
        return alternated_orders_list

    @staticmethod
    def _filter_virtual_order(orders):
        return [order for order in orders if not order.is_virtual]

    @staticmethod
    def _set_virtual_orders(buy_orders, sell_orders, operational_depth):
        # reverse orders to put orders closer to the current price first in order to set virtual orders
        buy_orders.reverse()
        sell_orders.reverse()

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

        # reverse back
        buy_orders.reverse()
        sell_orders.reverse()

    def _get_order_count_and_average_quantity(self, current_price, selling, lower_bound, upper_bound, holdings,
                                              currency=None):
        if lower_bound >= upper_bound:
            self.logger.error(f"Invalid bounds for {self.symbol}: too close to the current price")
            return 0, 0
        if selling:
            order_distance = upper_bound - (lower_bound + self.flat_spread/2)
        else:
            order_distance = (upper_bound - self.flat_spread/2) - lower_bound
        order_count_divisor = self.flat_increment
        orders_count = floor(order_distance / order_count_divisor + 1)
        if orders_count < 1:
            self.logger.warning(f"Impossible to create {'sell' if selling else 'buy'} orders for {currency}: "
                                f"not enough funds.")
            return 0, 0
        average_order_quantity = holdings / orders_count
        min_order_quantity, max_order_quantity = self._get_min_max_quantity(average_order_quantity, self.mode)
        if self.min_max_order_details[self.min_quantity] is not None \
                and self.min_max_order_details[self.min_cost] is not None:
            min_quantity = max(self.min_max_order_details[self.min_quantity],
                               self.min_max_order_details[self.min_cost]/current_price) if selling \
                else self.min_max_order_details[self.min_cost]
            if min_order_quantity < min_quantity:
                if holdings < average_order_quantity:
                    return 0, 0
                else:
                    min_funds = self._get_min_funds(orders_count, min_quantity, self.mode, current_price)
                    self.logger.error(f"Impossible to create {self.symbol} staggered "
                                      f"{TradeOrderSide.SELL.name if selling else TradeOrderSide.BUY.name} orders: "
                                      f"minimum quantity for {self.mode.value} mode is lower than the minimum allowed "
                                      f"for this trading pair on this exchange: requested minimum: {min_order_quantity}"
                                      f" and exchange minimum is {min_quantity}. "
                                      f"Minimum required funds are {min_funds}{f' {currency}' if currency else ''}.")
                return 0, 0
        return orders_count, average_order_quantity

    def _get_price_from_iteration(self, starting_bound, is_selling, iteration):
        price_step = self.flat_increment * iteration
        price = starting_bound + price_step if is_selling else starting_bound - price_step
        if self.min_max_order_details[self.min_price] and price < self.min_max_order_details[self.min_price]:
            return None
        return price

    def _get_quantity_from_iteration(self, average_order_quantity, mode, side, iteration, max_iteration, price):
        multiplier_price_ratio = 1
        min_quantity, max_quantity = self._get_min_max_quantity(average_order_quantity, mode)
        delta = max_quantity - min_quantity

        if max_iteration == 1:
            quantity = average_order_quantity
        else:
            if StrategyModeMultipliersDetails[mode][side] == INCREASING:
                multiplier_price_ratio = 1 - iteration/(max_iteration - 1)
            elif StrategyModeMultipliersDetails[mode][side] == DECREASING:
                multiplier_price_ratio = iteration/(max_iteration - 1)
            if price <= 0:
                return None
            quantity_with_delta = (min_quantity + (delta * multiplier_price_ratio))
            quantity = quantity_with_delta / price if side == TradeOrderSide.BUY else quantity_with_delta

        # reduce last order quantity to avoid python float representation issues
        if iteration == max_iteration - 1:
            quantity = quantity * 0.999

        if self.min_max_order_details[self.min_quantity] and quantity < self.min_max_order_details[self.min_quantity]:
            return None
        cost = quantity * price
        if self.min_max_order_details[self.min_cost] and cost < self.min_max_order_details[self.min_cost]:
            return None
        return quantity

    def _get_min_funds(self, orders_count, min_order_quantity, mode, current_price):
        mode_multiplier = StrategyModeMultipliersDetails[mode][MULTIPLIER]
        required_average_quantity = min_order_quantity / (1 - mode_multiplier/2)

        if self.min_cost in self.min_max_order_details:
            average_cost = current_price * required_average_quantity
            if self.min_max_order_details[self.min_cost]:
                min_cost = self.min_max_order_details[self.min_cost]
                if average_cost < min_cost:
                    required_average_quantity = min_cost/current_price

        return orders_count * required_average_quantity

    @staticmethod
    def _get_min_max_quantity(average_order_quantity, mode):
        mode_multiplier = StrategyModeMultipliersDetails[mode][MULTIPLIER]
        min_quantity = average_order_quantity * (1 - mode_multiplier/2)
        max_quantity = average_order_quantity * (1 + mode_multiplier/2)
        return min_quantity, max_quantity

    async def _create_order(self, order, current_price):
        data = {
            StaggeredOrdersTradingModeConsumer.ORDER_DATA_KEY: order,
            StaggeredOrdersTradingModeConsumer.CURRENT_PRICE_KEY: current_price,
            StaggeredOrdersTradingModeConsumer.SYMBOL_MARKET_KEY: self.symbol_market,
        }
        state = EvaluatorStates.LONG if order.side is TradeOrderSide.BUY else EvaluatorStates.SHORT
        await self.submit_trading_evaluation(cryptocurrency=self.trading_mode.cryptocurrency,
                                             symbol=self.trading_mode.symbol,
                                             time_frame=None,
                                             state=state,
                                             data=data)

    async def _create_not_virtual_orders(self, orders_to_create, current_price):
        for order in orders_to_create:
            await self._create_order(order, current_price)

    def _refresh_symbol_data(self, symbol_market):
        min_quantity, max_quantity, min_cost, max_cost, min_price, max_price = get_min_max_amounts(symbol_market)
        self.min_max_order_details[self.min_quantity] = min_quantity
        self.min_max_order_details[self.max_quantity] = max_quantity
        self.min_max_order_details[self.min_cost] = min_cost
        self.min_max_order_details[self.max_cost] = max_cost
        self.min_max_order_details[self.min_price] = min_price
        self.min_max_order_details[self.max_price] = max_price

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return False

    # syntax: "async with xxx.get_lock():"
    def get_lock(self):
        return self.lock
