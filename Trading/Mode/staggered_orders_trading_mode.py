"""
OctoBot Tentacle

$tentacle_description: {
    "name": "staggered_orders_trading_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.1.0",
    "requirements": ["staggered_orders_strategy_evaluator"],
    "config_files": ["StaggeredOrdersTradingMode.json"],
    "tests":["test_staggered_orders_trading_mode"],
    "developing": true
}
"""

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

from ccxt import InsufficientFunds
from enum import Enum
from dataclasses import dataclass
from math import floor
from copy import copy

from config import EvaluatorStates, TraderOrderType, ExchangeConstantsTickersInfoColumns, INIT_EVAL_NOTE, \
    START_PENDING_EVAL_NOTE, TradeOrderSide, ExchangeConstantsMarketPropertyColumns
from evaluator.Strategies import StaggeredStrategiesEvaluator
from trading.trader.modes.abstract_mode_creator import AbstractTradingModeCreator
from trading.trader.modes.abstract_mode_decider import AbstractTradingModeDecider
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode
from trading.trader.portfolio import Portfolio
from tools.symbol_util import split_symbol
from tools.data_util import DataUtil


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

    DESCRIPTION = 'Places a large amount of buy and sell orders at fixed intervals, covering the order book from ' \
                  'very low prices to very high prices. The range ' \
                  '(specified in tentacles/Trading/Mode/config/StaggeredOrdersTradingMode.json) is supposed to ' \
                  'cover all conceivable prices for as ' \
                  'long as the user intends to run the strategy. That could be from -100x to +100x ' \
                  '(-99% to +10000%). Profits will be made from price movements, and the strategy introduces ' \
                  'friction to such movements. It gives markets depth, and makes them look better. It never ' \
                  '"sells at a loss", but always at a profit. Description from ' \
                  'https://github.com/Codaone/DEXBot/wiki/The-Staggered-Orders-strategy. Full documentation ' \
                  'available there. In order to never sell at a loss, OctoBot never ' \
                  'cancels orders, in order to change the staggered orders mode, you will have to manually cancel ' \
                  'orders and restart the strategy. This trading mode instantly places opposite side orders when an ' \
                  'order is filled and checks the current orders every 6 hours to replace any missing one. Only ' \
                  'works on single currency and trading pair configuration. ' \
                  f'Modes are {", ".join([m.value for m in StrategyModes])}.'
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

    def create_deciders(self, symbol, symbol_evaluator):
        self.add_decider(symbol, StaggeredOrdersTradingModeDecider(self, symbol_evaluator, self.exchange))

    def create_creators(self, symbol, symbol_evaluator):
        self.add_creator(symbol, StaggeredOrdersTradingModeCreator(self))

    async def order_filled_callback(self, order):
        decider = self.get_only_decider_key(order.get_order_symbol())
        await decider.order_filled_callback(order)

    def set_default_config(self):
        raise RuntimeError(f"Impossible to start {self.get_name()} without {self.get_config_file_name()} "
                           f"configuration file.")


class StaggeredOrdersTradingModeCreator(AbstractTradingModeCreator):
    def __init__(self, trading_mode):
        super().__init__(trading_mode)

    # should never be called
    def create_new_order(self, eval_note, symbol, exchange, trader, portfolio, state):
        super().create_new_order(eval_note, symbol, exchange, trader, portfolio, state)

    # creates a new order
    async def create_order(self, order_data, current_price, symbol_market, trader, portfolio):
        created_order = None
        currency, market = split_symbol(order_data.symbol)
        try:
            for order_quantity, order_price in self.check_and_adapt_order_details_if_necessary(order_data.quantity,
                                                                                               order_data.price,
                                                                                               symbol_market):
                selling = order_data.side == TradeOrderSide.SELL
                if selling:
                    if portfolio.get_portfolio()[currency][Portfolio.AVAILABLE] < order_quantity:
                        return None
                elif portfolio.get_portfolio()[market][Portfolio.AVAILABLE] < order_quantity*order_price:
                        return None
                order_type = TraderOrderType.SELL_LIMIT if selling else TraderOrderType.BUY_LIMIT
                created_order = trader.create_order_instance(order_type=order_type,
                                                             symbol=order_data.symbol,
                                                             current_price=current_price,
                                                             quantity=order_quantity,
                                                             price=order_price)
                await trader.create_order(created_order, portfolio)
        except InsufficientFunds as e:
            raise e
        except Exception as e:
            self.logger.error(f"Failed to create order : {e}. "
                              f"Order: "
                              f"{created_order.get_string_info() if created_order else None}")
            self.logger.exception(e)
            return None
        return created_order


class StaggeredOrdersTradingModeDecider(AbstractTradingModeDecider):

    FILL = 1
    ERROR = 2
    NEW = 3
    min_quantity = "min_quantity"
    max_quantity = "max_quantity"
    min_cost = "min_cost"
    max_cost = "max_cost"
    min_price = "min_price"
    max_price = "max_price"

    def __init__(self, trading_mode, symbol_evaluator, exchange):
        super().__init__(trading_mode, symbol_evaluator, exchange)
        # no state for this evaluator: always neutral
        self.state = EvaluatorStates.NEUTRAL
        self.symbol_market = None
        self.min_max_order_details = {}
        fees = self.exchange.get_fees(self.symbol)
        self.max_fees = max(fees[ExchangeConstantsMarketPropertyColumns.TAKER.value],
                            fees[ExchangeConstantsMarketPropertyColumns.MAKER.value])

        # staggered orders strategy parameters
        mode = ""
        try:
            mode = self.trading_mode.get_trading_config_value(self.trading_mode.CONFIG_MODE)
            self.mode = StrategyModes(mode)
        except ValueError as e:
            self.logger.error(f"Invalid staggered orders strategy mode: {mode} "
                              f"supported modes are {[m.value for m in StrategyModes]}")
            raise e
        self.spread = self.trading_mode.get_trading_config_value(self.trading_mode.CONFIG_SPREAD) / 100
        self.increment = self.trading_mode.get_trading_config_value(self.trading_mode.CONFIG_INCREMENT_PERCENT) / 100
        self.operational_depth = self.trading_mode.get_trading_config_value(self.trading_mode.CONFIG_OPERATIONAL_DEPTH)
        self.lowest_buy = self.trading_mode.get_trading_config_value(self.trading_mode.CONFIG_LOWER_BOUND)
        self.highest_sell = self.trading_mode.get_trading_config_value(self.trading_mode.CONFIG_UPPER_BOUND)

    def set_final_eval(self):
        # Strategies analysis
        for evaluated_strategies in self.symbol_evaluator.get_strategies_eval_list(self.exchange):
            if isinstance(evaluated_strategies, StaggeredStrategiesEvaluator) or \
               evaluated_strategies.has_class_in_parents(StaggeredStrategiesEvaluator):
                evaluation = evaluated_strategies.get_eval_note()
                if evaluation != START_PENDING_EVAL_NOTE:
                    self.final_eval = evaluation[ExchangeConstantsTickersInfoColumns.LAST_PRICE.value]
                    return

    async def create_state(self):
        if self.final_eval != INIT_EVAL_NOTE:
            self._refresh_symbol_data()
            if self.symbol_evaluator.has_trader_simulator(self.exchange):
                trader_simulator = self.symbol_evaluator.get_trader_simulator(self.exchange)
                if trader_simulator.is_enabled():
                    await self._handle_staggered_orders(self.final_eval, trader_simulator)
            if self.symbol_evaluator.has_trader(self.exchange):
                real_trader = self.symbol_evaluator.get_trader(self.exchange)
                if real_trader.is_enabled():
                    await self._handle_staggered_orders(self.final_eval, real_trader)

    async def order_filled_callback(self, filled_order):
        # create order on the order side
        now_selling = filled_order.get_side() == TradeOrderSide.BUY
        new_side = TradeOrderSide.SELL if now_selling else TradeOrderSide.BUY
        trader = filled_order.trader
        closest_order_with_price = self._get_closest_price_order(trader, new_side)
        price_increment = self._get_prince_increment(trader)
        price = closest_order_with_price.origin_price - price_increment if now_selling \
            else closest_order_with_price.origin_price + price_increment
        new_order_quantity = filled_order.filled_quantity
        if not now_selling:
            # buying => adapt order quantity
            new_order_quantity = filled_order.filled_price / price * filled_order.filled_quantity
        quantity_change = self.max_fees
        quantity = new_order_quantity * (1 - quantity_change)
        new_order = OrderData(new_side, quantity, price, self.symbol)

        creator_key = self.trading_mode.get_only_creator_key(self.symbol)
        order_creator = self.trading_mode.get_creator(self.symbol, creator_key)
        new_orders = []
        async with trader.get_portfolio().get_lock():
            pf = trader.get_portfolio()
            await self._create_order(new_order, trader, order_creator, new_orders, pf)
        await self.push_order_notification_if_possible(new_orders, self.notifier)

    async def _handle_staggered_orders(self, final_eval, trader):
        buy_orders, sell_orders = await self._generate_staggered_orders(final_eval, trader)
        staggered_orders = self._alternate_not_virtual_orders(buy_orders, sell_orders)
        async with trader.get_portfolio().get_lock():
            await self._create_multiple_not_virtual_orders(staggered_orders, trader)

    async def _generate_staggered_orders(self, current_price, trader):
        existing_orders = trader.get_open_orders()
        portfolio = trader.get_portfolio().get_portfolio()

        sorted_orders = sorted(existing_orders, key=lambda order: order.origin_price)
        missing_orders, state, increment = self._analyse_current_orders_situation(sorted_orders)

        buy_orders = self._create_orders(self.lowest_buy, current_price, TradeOrderSide.BUY,sorted_orders,
                                         portfolio, current_price, missing_orders, state, increment)
        sell_orders = self._create_orders(current_price, self.highest_sell, TradeOrderSide.SELL,sorted_orders,
                                          portfolio, current_price, missing_orders, state, increment)

        if state == self.NEW:
            self._set_virtual_orders(buy_orders, sell_orders, self.operational_depth)

        return buy_orders, sell_orders

    def _analyse_current_orders_situation(self, sorted_orders):
        if not sorted_orders:
            return None, self.NEW, None
        # check if orders are staggered orders
        return self._bootstrap_parameters(sorted_orders)

    def _create_orders(self, lower_bound, upper_bound, side, sorted_orders,
                       portfolio, current_price, missing_orders, state, bootstrapped_increment):
        orders = []
        selling = side == TradeOrderSide.SELL
        self.total_orders_count = self.highest_sell - self.lowest_buy

        currency, market = split_symbol(self.symbol)
        order_limiting_currency = currency if selling else market

        starting_bound = upper_bound if selling else lower_bound
        order_limiting_currency_amount = portfolio[order_limiting_currency][Portfolio.AVAILABLE] \
            if order_limiting_currency in portfolio else 0
        if state == self.NEW:
            # create staggered orders

            orders_count, average_order_quantity = \
                self._get_order_count_and_average_quantity(current_price, selling, lower_bound,
                                                           upper_bound, order_limiting_currency_amount)
            for i in range(orders_count):
                price = self._get_price_from_iteration(current_price, starting_bound, selling, i, self.increment)
                if price is not None:
                    quantity = self._get_quantity_from_iteration(average_order_quantity, self.mode,
                                                                 side, i, orders_count, price)
                    if quantity is not None:
                        orders.append(OrderData(side, quantity, price, self.symbol))
            if not orders:
                self.logger.warning(f"Not enough {order_limiting_currency} to create {side.name} orders. "
                                    f"For the strategy to work better, add {order_limiting_currency} funds or "
                                    f"change change the strategy settings to make less but bigger orders.")

        if state == self.FILL:
            # complete missing orders
            if missing_orders:
                max_quant_per_order = order_limiting_currency_amount / len(missing_orders)
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
                            quantity = min(DataUtil.mean([previous_o.origin_quantity, following_o.origin_quantity]),
                                           max_quant_per_order / missing_order_price)
                            orders.append(OrderData(missing_order_side, quantity,
                                                    missing_order_price, self.symbol, False))
                        else:
                            missing_orders_around_spread.append((missing_order_price, missing_order_side))

                if missing_orders_around_spread:
                    # missing order next to spread
                    increment_window = bootstrapped_increment/2
                    order_limiting_currency_available_amount = \
                        portfolio[order_limiting_currency][Portfolio.AVAILABLE] \
                        if order_limiting_currency in portfolio else 0
                    portfolio_total = portfolio[order_limiting_currency][Portfolio.TOTAL] \
                        if order_limiting_currency in portfolio else 0
                    order_limiting_currency_amount = portfolio_total
                    if order_limiting_currency_available_amount:
                        orders_count, average_order_quantity = \
                            self._get_order_count_and_average_quantity(current_price, selling, lower_bound,
                                                                       upper_bound, portfolio_total,
                                                                       bootstrapped_increment)
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
                                price = price - bootstrapped_increment if selling else price + bootstrapped_increment
                                limiting_amount_from_this_order -= limiting_currency_quantity
                                i += 1

        elif state == self.ERROR:
            self.logger.error("Impossible to create staggered orders when incompatible order are already in place. "
                              "Cancel these orders of you want to use this trading mode.")
        return orders

    def _bootstrap_parameters(self, sorted_orders):
        mode = None
        spread = None
        increment = None
        bigger_buys_closer_to_center = None
        first_sell = None
        ratio = None
        state = self.FILL

        missing_orders = []

        previous_order = None
        for order in sorted_orders:
            if order.symbol != self.symbol:
                return None, self.ERROR, None
            spread_point = False
            if previous_order is None:
                previous_order = order
            else:
                if previous_order.side != order.side:
                    if spread is None:
                        spread_point = True
                        delta_spread = order.origin_price - previous_order.origin_price

                        if increment is None:
                            return None, self.ERROR, None
                        else:
                            inferred_spread = self.spread*increment/self.increment
                            missing_orders_count = (delta_spread-inferred_spread)/increment
                            if missing_orders_count > 1*0.8:
                                # missing orders around spread point: symmetrical orders were not created when orders
                                # were filled => re-create them
                                next_missing_order_price = previous_order.origin_price + increment
                                half_spread = inferred_spread/2
                                spread_lower_boundary = self.final_eval - half_spread
                                spread_higher_boundary = self.final_eval + half_spread

                                # re-create buy orders starting from the closest buy up to spread
                                while next_missing_order_price <= spread_lower_boundary:
                                    # missing buy order
                                    missing_orders.append((next_missing_order_price, TradeOrderSide.BUY))
                                    next_missing_order_price += increment

                                next_missing_order_price = order.origin_price - increment
                                # re-create sell orders starting from the closest sell down to spread
                                while next_missing_order_price >= spread_higher_boundary:
                                    # missing sell order
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
                        return None, self.ERROR, None
                if increment is None:
                    increment = order.origin_price - previous_order.origin_price
                    if increment == 0:
                        return None, self.ERROR, None
                elif not spread_point:
                    delta_increment = order.origin_price - previous_order.origin_price
                    missing_orders_count = delta_increment/increment
                    if missing_orders_count > 2.2:
                        return None, self.ERROR, None
                    elif missing_orders_count > 1.1:
                        missing_orders.append((previous_order.origin_price+increment, order.side))
                previous_order = order

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
            return None, self.ERROR, None

        return missing_orders, state, increment

    @staticmethod
    def _get_prince_increment(trader):
        order_list = [order for order in copy(trader.get_order_manager().get_open_orders())
                      if order.side == TradeOrderSide.SELL]
        sorted_orders = sorted(order_list, key=lambda order: order.origin_price)
        if len(sorted_orders) > 1:
            return sorted_orders[1].origin_price - sorted_orders[0].origin_price
        else:
            return None

    @staticmethod
    def _get_closest_price_order(trader, side):
        order_list = [order for order in copy(trader.get_order_manager().get_open_orders()) if order.side == side]
        invert_sorting = True if side == TradeOrderSide.BUY else False
        return sorted(order_list, key=lambda order: order.origin_price, reverse=invert_sorting)[0]

    @staticmethod
    def _alternate_not_virtual_orders(buy_orders, sell_orders):
        not_virtual_buy_orders = StaggeredOrdersTradingModeDecider._filter_virtual_order(buy_orders)
        not_virtual_sell_orders = StaggeredOrdersTradingModeDecider._filter_virtual_order(sell_orders)
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
                                              bootstrapped_increment=None):
        if lower_bound >= upper_bound:
            self.logger.error("Bounds invalid: too close to the current price")
            return 0, 0
        if selling:
            order_distance = upper_bound - lower_bound * (1 + self.spread / 2)
        else:
            order_distance = upper_bound * (1 - self.spread / 2) - lower_bound
        order_count_divisor = bootstrapped_increment if bootstrapped_increment else current_price * self.increment
        orders_count = order_distance / order_count_divisor + 1
        average_order_quantity = holdings / orders_count
        if self.min_max_order_details[self.min_quantity] and \
           average_order_quantity < self.min_max_order_details[self.min_quantity]:
            if holdings < average_order_quantity:
                return 0, 0
            else:
                order_count = holdings / self.min_max_order_details[self.min_quantity]
                return floor(order_count), self.min_max_order_details[self.min_quantity]
        return floor(orders_count), average_order_quantity

    def _get_price_from_iteration(self, current_price, starting_bound, is_selling, iteration, increment):
        price_step = current_price * increment * iteration
        price = starting_bound - price_step if is_selling else starting_bound + price_step
        if self.min_max_order_details[self.min_price] and price < self.min_max_order_details[self.min_price]:
            return None
        return price

    def _get_quantity_from_iteration(self, average_order_quantity, mode, side, iteration, max_iteration, price):
        multiplier_price_ratio = 1
        mode_multiplier = StrategyModeMultipliersDetails[mode][MULTIPLIER]
        min_quantity = average_order_quantity * (1 - mode_multiplier/2)
        max_quantity = average_order_quantity * (1 + mode_multiplier/2)
        delta = max_quantity - min_quantity

        if max_iteration == 1:
            max_iteration = 2
        if StrategyModeMultipliersDetails[mode][side] == INCREASING:
            multiplier_price_ratio = iteration/(max_iteration - 1)
        elif StrategyModeMultipliersDetails[mode][side] == DECREASING:
            multiplier_price_ratio = 1 - iteration/(max_iteration - 1)
        if price <= 0:
            return None
        quantity_with_delta = (min_quantity + (delta * multiplier_price_ratio))
        quantity = quantity_with_delta / price if side == TradeOrderSide.BUY else quantity_with_delta

        if self.min_max_order_details[self.min_quantity] and quantity < self.min_max_order_details[self.min_quantity]:
            return None
        cost = quantity * price
        if self.min_max_order_details[self.min_cost] and cost < self.min_max_order_details[self.min_cost]:
            return None
        return quantity

    async def _create_multiple_not_virtual_orders(self, orders_to_create, trader):
        creator_key = self.trading_mode.get_only_creator_key(self.symbol)
        await self._create_not_virtual_orders(self.notifier, trader, orders_to_create, creator_key)

    async def _create_order(self, order, trader, order_creator, new_orders, portfolio):
        try:
            created_order = await order_creator.create_order(order, self.final_eval, self.symbol_market,
                                                             trader, portfolio)
            if created_order is not None:
                new_orders.append(created_order)
        except InsufficientFunds:
            if not trader.get_simulate():
                try:
                    # second chance: force portfolio update and retry
                    await trader.force_refresh_orders_and_portfolio()
                    created_order = await order_creator.create_order(order, self.final_eval, self.symbol_market,
                                                                     trader, portfolio)
                    if created_order is not None:
                        new_orders.append(created_order)
                except InsufficientFunds as e:
                    self.logger.error(f"Failed to create order on second attempt : {e})")

    async def _create_not_virtual_orders(self, notifier, trader, orders_to_create, creator_key):
        order_creator = self.trading_mode.get_creator(self.symbol, creator_key)
        new_orders = []
        pf = trader.get_portfolio()
        for order in orders_to_create:
            await self._create_order(order, trader, order_creator, new_orders, pf)

        await self.push_order_notification_if_possible(new_orders, notifier)

    def _refresh_symbol_data(self):
        self.symbol_market = self.exchange.get_market_status(self.symbol, with_fixer=False)
        min_quantity, max_quantity, min_cost, max_cost, min_price, max_price = \
            AbstractTradingModeCreator.get_min_max_amounts(self.symbol_market)
        self.min_max_order_details[self.min_quantity] = min_quantity
        self.min_max_order_details[self.max_quantity] = max_quantity
        self.min_max_order_details[self.min_cost] = min_cost
        self.min_max_order_details[self.max_cost] = max_cost
        self.min_max_order_details[self.min_price] = min_price
        self.min_max_order_details[self.max_price] = max_price

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return False
