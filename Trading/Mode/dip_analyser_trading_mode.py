"""
OctoBot Tentacle

$tentacle_description: {
    "name": "dip_analyser_trading_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.1.1",
    "requirements": ["dip_analyser_strategy_evaluator"],
    "config_files": ["DipAnalyserTradingMode.json"],
    "config_schema_files": ["DipAnalyserTradingMode_schema.json"],
    "tests":["test_dip_analyser_trading_mode"]
}
"""

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

from ccxt import InsufficientFunds

from config import START_PENDING_EVAL_NOTE, TraderOrderType, TradeOrderSide
from trading.trader.modes.abstract_mode_creator import AbstractTradingModeCreator
from trading.trader.modes.abstract_mode_decider import AbstractTradingModeDecider
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode
from evaluator.Strategies import DipAnalyserStrategyEvaluator
from tools.symbol_util import split_symbol


class DipAnalyserTradingMode(AbstractTradingMode):
    DESCRIPTION = "DipAnalyserTradingMode is a trading mode adapted to volatile markets.\nIt will look for local " \
                  "market bottoms, weight them and buy these bottoms. It never sells except after a buy order is " \
                  "filled.\nWhen a buy order is filled, sell orders will automatically be created at a higher price " \
                  "than this of the filled buy order. The number of sell orders created after each buy is specified " \
                  "in DipAnalyserTradingMode.json.\nA higher risk will make larger buy orders.\n Warning: Make sure " \
                  "to have the base of each traded pair to be traded otherwise the DipAnalyserTradingMode won't " \
                  "trade: it will never be able to place the initial buy orders.\nSell orders are never cancelled " \
                  "by the strategy, therefore it is not advised to use it on continued downtrends or funds might " \
                  "get stuck in unfilled sell orders."

    def __init__(self, config, exchange):
        super().__init__(config, exchange)
        self.load_config()

    def create_deciders(self, symbol, symbol_evaluator):
        self.add_decider(symbol, DipAnalyserTradingModeDecider(self, symbol_evaluator, self.exchange))

    def create_creators(self, symbol, symbol_evaluator):
        self.add_creator(symbol, DipAnalyserTradingModeCreator(self))

    async def order_filled_callback(self, order):
        decider = self.get_only_decider_key(order.get_order_symbol())
        await decider.order_filled_callback(order)


class DipAnalyserTradingModeCreator(AbstractTradingModeCreator):

    LIMIT_PRICE_MULTIPLIER = 0.995
    SOFT_MAX_CURRENCY_RATIO = 0.33
    DEFAULT_FULL_VOLUME = 0.5

    RISK_VOLUME_MULTIPLIER = 0.2

    DELTA_RATIO = 0.8

    LIGHT_VOLUME_WEIGHT = "light_weight_volume_multiplier"
    MEDIUM_VOLUME_WEIGHT = "medium_weight_volume_multiplier"
    HEAVY_VOLUME_WEIGHT = "heavy_weight_volume_multiplier"
    VOLUME_WEIGH_TO_VOLUME_PERCENT = {}

    LIGHT_PRICE_WEIGHT = "light_weight_price_multiplier"
    MEDIUM_PRICE_WEIGHT = "medium_weight_price_multiplier"
    HEAVY_PRICE_WEIGHT = "heavy_weight_price_multiplier"
    PRICE_WEIGH_TO_PRICE_PERCENT = {}

    def __init__(self, trading_mode):
        super().__init__(trading_mode)

        self.PRICE_WEIGH_TO_PRICE_PERCENT[1] = self.trading_mode.get_trading_config_value(self.LIGHT_PRICE_WEIGHT)
        self.PRICE_WEIGH_TO_PRICE_PERCENT[2] = self.trading_mode.get_trading_config_value(self.MEDIUM_PRICE_WEIGHT)
        self.PRICE_WEIGH_TO_PRICE_PERCENT[3] = self.trading_mode.get_trading_config_value(self.HEAVY_PRICE_WEIGHT)

        self.VOLUME_WEIGH_TO_VOLUME_PERCENT[1] = self.trading_mode.get_trading_config_value(self.LIGHT_VOLUME_WEIGHT)
        self.VOLUME_WEIGH_TO_VOLUME_PERCENT[2] = self.trading_mode.get_trading_config_value(self.MEDIUM_VOLUME_WEIGHT)
        self.VOLUME_WEIGH_TO_VOLUME_PERCENT[3] = self.trading_mode.get_trading_config_value(self.HEAVY_VOLUME_WEIGHT)

    async def create_buy_order(self, volume_weight, trader, portfolio, symbol, exchange):

        current_order = None
        try:
            current_symbol_holding, current_market_holding, market_quantity, price, symbol_market = \
                await self.get_pre_order_data(exchange, symbol, portfolio)

            quote, _ = split_symbol(symbol)
            created_orders = []
            quantity = await self._get_buy_quantity_from_weight(volume_weight, trader,
                                                                market_quantity, portfolio, quote)
            limit_price = self.adapt_price(symbol_market, self.get_limit_price(price))
            for order_quantity, order_price in self.check_and_adapt_order_details_if_necessary(quantity,
                                                                                               limit_price,
                                                                                               symbol_market):
                current_order = trader.create_order_instance(order_type=TraderOrderType.BUY_LIMIT,
                                                             symbol=symbol,
                                                             current_price=price,
                                                             quantity=order_quantity,
                                                             price=order_price)
                await trader.create_order(current_order, portfolio)
                created_orders.append(current_order)
            return created_orders

        except InsufficientFunds as e:
            raise e

        except Exception as e:
            self.logger.error(f"Failed to create order : {e}. Order: "
                              f"{current_order.get_string_info() if current_order else None}")
            self.logger.exception(e)
            return []

    async def create_sell_orders(self, sell_orders_count, trader, portfolio, symbol,
                                 exchange, quantity, sell_weight, sell_base):
        current_order = None
        try:
            current_symbol_holding, current_market_holding, market_quantity, price, symbol_market = \
                await self.get_pre_order_data(exchange, symbol, portfolio)

            quote, _ = split_symbol(symbol)
            created_orders = []
            sell_max_quantity = min(current_symbol_holding, quantity)
            to_create_orders = self._generate_sell_orders(sell_orders_count, sell_max_quantity, sell_weight,
                                                          sell_base, symbol_market)
            for order_quantity, order_price in to_create_orders:
                current_order = trader.create_order_instance(order_type=TraderOrderType.SELL_LIMIT,
                                                             symbol=symbol,
                                                             current_price=sell_base,
                                                             quantity=order_quantity,
                                                             price=order_price)
                await trader.create_order(current_order, portfolio)
                created_orders.append(current_order)
            return created_orders

        except InsufficientFunds as e:
            raise e

        except Exception as e:
            self.logger.error(f"Failed to create order : {e}. Order: "
                              f"{current_order.get_string_info() if current_order else None}")
            self.logger.exception(e)
            return []

    async def _get_buy_quantity_from_weight(self, volume_weight, trader, market_quantity, portfolio, currency):
        weighted_volume = self.VOLUME_WEIGH_TO_VOLUME_PERCENT[volume_weight]
        # high risk is making larger orders, low risk is making smaller ones
        risk_multiplier = 1 + ((trader.get_risk() - 0.5) * self.RISK_VOLUME_MULTIPLIER)
        weighted_volume = min(weighted_volume * risk_multiplier, 1)
        traded_assets_count = self.get_number_of_traded_assets(trader)
        if traded_assets_count == 1:
            return market_quantity * self.DEFAULT_FULL_VOLUME * weighted_volume
        elif traded_assets_count == 2:
            return market_quantity * self.SOFT_MAX_CURRENCY_RATIO * weighted_volume
        else:
            currency_ratio = 0
            if currency != trader.get_reference_market():
                # if currency (quote) is not ref market => need to check holdings ratio not to spend all ref market
                # into one currency (at least 3 traded assets are available here)
                currency_ratio = await self.get_holdings_ratio(trader, portfolio, currency)
            # linear function of % holding in this currency: volume_ratio is in [0, SOFT_MAX_CURRENCY_RATIO*0.8]
            volume_ratio = self.SOFT_MAX_CURRENCY_RATIO * (1 - min(currency_ratio * self.DELTA_RATIO, 1))
            return market_quantity * volume_ratio * weighted_volume

    @staticmethod
    def get_limit_price(price):
        # buy very close from current price
        return price * DipAnalyserTradingModeCreator.LIMIT_PRICE_MULTIPLIER

    def _generate_sell_orders(self, sell_orders_count, quantity, sell_weight, sell_base, symbol_market):
        volume_with_price = []
        sell_max = sell_base * self.PRICE_WEIGH_TO_PRICE_PERCENT[sell_weight]
        adapted_sell_orders_count, increment = \
            self._check_limits(sell_base, sell_max, quantity, sell_orders_count, symbol_market)
        order_volume = quantity / adapted_sell_orders_count

        for i in range(adapted_sell_orders_count):
            order_price = sell_base + (increment * (i + 1))
            for adapted_quantity, adapted_price in self.check_and_adapt_order_details_if_necessary(order_volume,
                                                                                                   order_price,
                                                                                                   symbol_market):
                volume_with_price.append((adapted_quantity, adapted_price))
        return volume_with_price

    def _check_limits(self, sell_base, sell_max, quantity, sell_orders_count, symbol_market):
        min_quantity, max_quantity, min_cost, max_cost, min_price, max_price = \
            AbstractTradingModeCreator.get_min_max_amounts(symbol_market)

        orders_count = sell_orders_count

        limit_check = DipAnalyserTradingModeCreator._ensure_orders_size(
            sell_base, sell_max, quantity, orders_count,
            min_quantity, min_cost, min_price,
            max_quantity, max_cost, max_price)

        while limit_check > 0:
            if limit_check == 1:
                if orders_count > 1:
                    orders_count -= 1
                else:
                    # not enough funds to create orders
                    self.logger.error(f"Not enough funds to create sell order.")
                    return 0, 0
            elif limit_check == 2:
                if orders_count < 40:
                    orders_count += 1
                else:
                    # too many orders to create, must be a problem
                    self.logger.error("Too many orders to create: error with _generate_sell_orders.")
                    return 0, 0
            limit_check = DipAnalyserTradingModeCreator._ensure_orders_size(
                sell_base, sell_max, quantity, orders_count,
                min_quantity, min_cost, min_price,
                max_quantity, max_cost, max_price)
        return orders_count, (sell_max - sell_base) / orders_count

    @staticmethod
    def _ensure_orders_size(sell_base, sell_max, quantity, sell_orders_count,
                            min_quantity, min_cost, min_price,
                            max_quantity, max_cost, max_price):
        increment = (sell_max - sell_base) / sell_orders_count
        first_sell = sell_base + increment
        last_sell = sell_base + (increment * sell_orders_count)
        order_vol = quantity / sell_orders_count

        if DipAnalyserTradingModeCreator.orders_too_small(min_quantity, min_cost, min_price, first_sell, order_vol):
            return 1
        elif DipAnalyserTradingModeCreator.orders_too_large(max_quantity, max_cost, max_price, last_sell, order_vol):
            return 2
        return 0

    @staticmethod
    def orders_too_small(min_quantity, min_cost, min_price, sell_price, sell_vol):
        return (min_price and sell_price < min_price) or \
            (min_quantity and sell_vol < min_quantity) or \
            (min_cost and sell_price*sell_vol < min_cost)

    @staticmethod
    def orders_too_large(max_quantity, max_cost, max_price, sell_price, sell_vol):
        return (max_price and sell_price > max_price) or \
            (max_quantity and sell_vol > max_quantity) or \
            (max_cost and sell_price*sell_vol > max_cost)

    # should never be called
    def create_new_order(self, eval_note, symbol, exchange, trader, portfolio, state):
        super().create_new_order(eval_note, symbol, exchange, trader, portfolio, state)


class DipAnalyserTradingModeDecider(AbstractTradingModeDecider):

    def __init__(self, trading_mode, symbol_evaluator, exchange):
        super().__init__(trading_mode, symbol_evaluator, exchange)
        self.volume_weight = self.price_weight = self.last_buy_candle = None
        self.first_trigger = True
        self.sell_targets_by_order = {}
        self.quote, _ = split_symbol(self.symbol)
        self.sell_orders_per_buy = self.trading_mode.get_trading_config_value("sell_orders_count")

    def set_final_eval(self):
        # Strategies analysis
        self.final_eval = self.get_strategy_evaluation(DipAnalyserStrategyEvaluator)

    async def create_state(self):
        if self.first_trigger:
            # can't rely on previous execution buy orders: need plans for sell orders
            await self._cancel_buy_orders()
            self.first_trigger = False
        if self.final_eval != START_PENDING_EVAL_NOTE:
            self.volume_weight = self.final_eval["volume_weight"]
            self.price_weight = self.final_eval["price_weight"]
            await self._create_bottom_order(self.final_eval["current_candle_time"])
        else:
            self.volume_weight = self.price_weight = None

    async def order_filled_callback(self, filled_order):
        if filled_order.get_side() == TradeOrderSide.BUY:
            order_identifier = self._get_order_identifier(filled_order)
            if order_identifier in self.sell_targets_by_order:
                sell_target = self.sell_targets_by_order[order_identifier]
                trader = filled_order.trader
                sell_quantity = filled_order.get_filled_quantity() - filled_order.get_total_fees(self.quote)
                buy_price = filled_order.get_origin_price()
                await self._create_order(trader, False, sell_quantity, sell_target, buy_price)
            else:
                self.logger.error(f"No sell target from order {filled_order}. Can't create sell orders.")

    async def _create_bottom_order(self, notification_candle_time):
        self.logger.info(f"** New buy order for ** : {self.symbol}")
        # call orders creation method
        if self.symbol_evaluator.has_trader_simulator(self.exchange):
            await self._create_order_if_enabled(self.symbol_evaluator.get_trader_simulator(self.exchange),
                                                notification_candle_time)

        if self.symbol_evaluator.has_trader(self.exchange):
            await self._create_order_if_enabled(self.symbol_evaluator.get_trader(self.exchange),
                                                notification_candle_time)

    async def _create_order_if_enabled(self, trader, notification_candle_time):

        if trader.is_enabled():
            # cancel previous by orders if any
            cancelled_orders = await self._cancel_buy_orders_for_trader(trader)
            if self.last_buy_candle == notification_candle_time and cancelled_orders or \
                    self.last_buy_candle != notification_candle_time:
                # if subsequent notification from the same candle: only create order if able to cancel the previous buy
                # to avoid multiple order on the same candle
                await self._create_order(trader)
                self.last_buy_candle = notification_candle_time
            else:
                self.logger.debug(f"Ignored buy signal for {self.symbol}: buy order already filled.")

    async def _create_order(self, trader, buy=True, total_sell=None, sell_target=None, buy_price=None):
        creator_key = self.trading_mode.get_only_creator_key(self.symbol)
        order_creator = self.trading_mode.get_creator(self.symbol, creator_key)

        try:
            portfolio = trader.get_portfolio()
            async with portfolio.get_lock():
                try:
                    if buy:
                        await self._create_buy_order(trader, portfolio, order_creator)
                    else:
                        await self._create_sell_orders(trader, portfolio, order_creator,
                                                       total_sell, sell_target, buy_price)
                except InsufficientFunds:
                    if not trader.get_simulate():
                        try:
                            # second chance: force portfolio update and retry
                            await trader.force_refresh_orders_and_portfolio()
                            if buy:
                                await self._create_buy_order(trader, portfolio, order_creator)
                            else:
                                await self._create_sell_orders(trader, portfolio, order_creator,
                                                               total_sell, sell_target, buy_price)
                        except InsufficientFunds as e:
                            self.logger.error(f"Failed to create order on second attempt : {e})")
        except Exception as e:
            self.logger.error(f"Error while creating order: {e}")
            self.logger.exception(e)

    async def _create_sell_orders(self, trader, portfolio, order_creator, total_sell, sell_target, buy_price):
        created_orders = await order_creator.create_sell_orders(self.sell_orders_per_buy, trader, portfolio,
                                                                self.symbol, self.exchange, total_sell, sell_target,
                                                                buy_price)
        await self.push_order_notification_if_possible(created_orders, self.notifier)

    async def _create_buy_order(self, trader, portfolio, order_creator):
        created_orders = await order_creator.create_buy_order(self.volume_weight, trader,
                                                              portfolio, self.symbol, self.exchange)
        for order in created_orders:
            self._register_buy_order(order)
        await self.push_order_notification_if_possible(created_orders, self.notifier)

    def _register_buy_order(self, order):
        self.sell_targets_by_order[self._get_order_identifier(order)] = self.price_weight

    def _unregister_buy_order(self, order):
        order_identifier = self._get_order_identifier(order)
        if order_identifier in self.sell_targets_by_order:
            self.sell_targets_by_order.pop(order_identifier)

    @staticmethod
    def _get_order_identifier(order):
        return f"{order.get_creation_time()}{order.get_origin_price()}{order.get_origin_quantity()}"

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True

    async def _cancel_buy_orders(self):
        if self.symbol_evaluator.has_trader_simulator(self.exchange):
            trader_simulator = self.symbol_evaluator.get_trader_simulator(self.exchange)
            if trader_simulator.is_enabled():
                await self._cancel_buy_orders_for_trader(trader_simulator)
        if self.symbol_evaluator.has_trader(self.exchange):
            real_trader = self.symbol_evaluator.get_trader(self.exchange)
            if real_trader.is_enabled():
                await self._cancel_buy_orders_for_trader(real_trader)

    def _get_current_buy_orders(self, trader):
        return [order for order in trader.get_open_orders(self.symbol) if order.get_side() == TradeOrderSide.BUY]

    async def _cancel_buy_orders_for_trader(self, trader):
        cancelled_orders = False
        for order in self._get_current_buy_orders(trader):
            await trader.cancel_order(order)
            self._unregister_buy_order(order)
            cancelled_orders = True
        return cancelled_orders
