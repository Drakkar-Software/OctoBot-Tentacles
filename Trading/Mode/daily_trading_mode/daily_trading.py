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
import asyncio
import decimal
import math

import octobot_commons.constants as commons_constants
import octobot_commons.enums as commons_enums
import octobot_commons.evaluators_util as evaluators_util
import octobot_commons.pretty_printer as pretty_printer
import octobot_commons.symbols.symbol_util as symbol_util
import octobot_evaluators.api as evaluators_api
import octobot_evaluators.constants as evaluators_constants
import octobot_evaluators.enums as evaluators_enums
import octobot_evaluators.matrix as matrix
import octobot_trading.personal_data as trading_personal_data
import octobot_trading.constants as trading_constants
import octobot_trading.errors as trading_errors
import octobot_trading.modes as trading_modes
import octobot_trading.modes.script_keywords as script_keywords
import octobot_trading.enums as trading_enums
import octobot_trading.api as trading_api


class DailyTradingMode(trading_modes.AbstractTradingMode):

    def init_user_inputs(self, inputs: dict) -> None:
        """
        Called right before starting the tentacle, should define all the tentacle's user inputs unless
        those are defined somewhere else.
        """
        trading_modes.should_emit_trading_signals_user_input(self, inputs)
        self.UI.user_input(
            "target_profits_mode", commons_enums.UserInputTypes.BOOLEAN, False, inputs,
            title="Target profits mode: Enable target profits mode. In this mode, only entry "
                  "signals are taken into account (usually LONG signals). When an entry is filled, "
                  "a take profit will instantly be created using the '[Target profits mode] Take profit' setting. "
                  "A stop loss can also be created using the '[Target profits mode] Stop loss' setting if "
                  "'Stop orders' are enabled.",
        )

        self.UI.user_input(
            "use_prices_close_to_current_price", commons_enums.UserInputTypes.BOOLEAN, False, inputs,
            title="Fixed limit prices: Use a fixed ratio to compute prices in sell / buy orders.",
        )
        self.UI.user_input(
            "close_to_current_price_difference", commons_enums.UserInputTypes.FLOAT, 0.005, inputs,
            min_val=0,
            title="Fixed limit prices difference: Multiplier to take into account when placing a limit order "
                  "(used if fixed limit prices is enabled). For a 200 USD price and 0.005 in difference: "
                  "buy price would be 199 and sell price 201.",
            editor_options={
                commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                  "use_prices_close_to_current_price": True
                }
            }
        )
        self.UI.user_input(
            "target_profits_mode_take_profit", commons_enums.UserInputTypes.FLOAT, 5, inputs,
            min_val=0,
            title="[Target profits mode] Take profit: percent profits to compute the take profit order price from. "
                  "Only used in 'Target profits mode'. "
                  "Example: a buy entry at 300 with a 'Take profit' at 10 will create a sell order at 330.",
            editor_options={
                commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                  "target_profits_mode": True
                }
            }
        )
        self.UI.user_input(
            "use_stop_orders", commons_enums.UserInputTypes.BOOLEAN, True, inputs,
            title="Stop orders: Create a stop loss alongside sell orders.",
        )
        self.UI.user_input(
            "target_profits_mode_stop_loss", commons_enums.UserInputTypes.FLOAT, 2.5, inputs,
            min_val=0, max_val=100,
            title="[Target profits mode] Stop loss: maximum percent losses to compute the stop loss price from. "
                  "Only used in 'Target profits mode'. "
                  "Example: a buy entry at 300 with a 'Stop loss' at 10 will create a stop order at 270.",
            editor_options={
                commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                  "target_profits_mode": True,
                  "use_stop_orders": True,
                }
            }
        )
        self.UI.user_input(
            "target_profits_mode_enable_position_increase", commons_enums.UserInputTypes.BOOLEAN, False, inputs,
            title="[Target profits mode] Enable futures position increase: Allow to increase a previously open "
                  "position when receiving a new signal. "
                  "Only used in 'Target profits mode' when trading futures. "
                  "Example: increase a $100 LONG position to $150 by adding $50 more when a new LONG signal is "
                  "received. WARNING: enabling this option can lead to liquidation price changes as positions "
                  "build up and end up liquidating a position before initial stop loss prices are reached.",
            editor_options={
                commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                  "target_profits_mode": True
                }
            }
        )
        self.UI.user_input(
            "buy_with_maximum_size_orders", commons_enums.UserInputTypes.BOOLEAN, False, inputs,
            title="All in buy trades: Trade with all available funds at each buy order.",
        )
        self.UI.user_input(
            "sell_with_maximum_size_orders", commons_enums.UserInputTypes.BOOLEAN, False, inputs,
            title="All in sell trades: Trade with all available funds at each sell order.",
            editor_options={
                commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                  "target_profits_mode": False
                }
            }
        )
        trading_modes.user_select_order_amount(
            self, inputs,
            buy_dependencies={"buy_with_maximum_size_orders": False},
            sell_dependencies={"target_profits_mode": False, "sell_with_maximum_size_orders": False}
        )
        self.UI.user_input(
            "disable_sell_orders", commons_enums.UserInputTypes.BOOLEAN, False, inputs,
            title="Disable sell orders (sell market and sell limit).",
            editor_options={
                commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                  "target_profits_mode": False
                }
            }
        )
        self.UI.user_input(
            "disable_buy_orders", commons_enums.UserInputTypes.BOOLEAN, False, inputs,
            title="Disable buy orders (buy market and buy limit).",
            editor_options={
                commons_enums.UserInputOtherSchemaValuesTypes.DEPENDENCIES.value: {
                  "target_profits_mode": False
                }
            }
        )
        self.UI.user_input(
            "max_currency_percent", commons_enums.UserInputTypes.FLOAT, 100, inputs,
            min_val=0, max_val=100,
            title="Maximum currency percent: Maximum portfolio % to allocate on a given currency. "
                  "Used to compute buy order amounts. Ignored when 'Amount per buy/entry order' is set.",
        )

    @classmethod
    def get_supported_exchange_types(cls) -> list:
        """
        :return: The list of supported exchange types
        """
        return [
            trading_enums.ExchangeTypes.SPOT,
            trading_enums.ExchangeTypes.FUTURE,
        ]

    def get_current_state(self) -> (str, float):
        return super().get_current_state()[0] if self.producers[0].state is None else self.producers[0].state.name, \
               self.producers[0].final_eval

    def get_mode_producer_classes(self) -> list:
        return [DailyTradingModeProducer]

    def get_mode_consumer_classes(self) -> list:
        return [DailyTradingModeConsumer]

    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        return False


class DailyTradingModeConsumer(trading_modes.AbstractTradingModeConsumer):
    PRICE_KEY = "PRICE"
    VOLUME_KEY = "VOLUME"
    STOP_PRICE_KEY = "STOP_PRICE"
    TAKE_PROFIT_PRICE_KEY = "TAKE_PROFIT_PRICE"
    STOP_ONLY = "STOP_ONLY"
    REDUCE_ONLY_KEY = "REDUCE_ONLY"
    TAG_KEY = "TAG"
    ORDER_EXCHANGE_CREATION_PARAMS = "ORDER_EXCHANGE_CREATION_PARAMS"
    CREATE_ORDER_DATA_PARAM = "data"
    TARGET_PROFIT_MODE_ENTRY_QUANTITY_SIDE = trading_enums.TradeOrderSide.BUY

    def __init__(self, trading_mode):
        super().__init__(trading_mode)
        self.trader = self.exchange_manager.trader

        self.MAX_SUM_RESULT = decimal.Decimal(2)

        self.STOP_LOSS_ORDER_MAX_PERCENT = decimal.Decimal(str(0.99))
        self.STOP_LOSS_ORDER_MIN_PERCENT = decimal.Decimal(str(0.95))
        self.STOP_LOSS_ORDER_ATTENUATION = (self.STOP_LOSS_ORDER_MAX_PERCENT - self.STOP_LOSS_ORDER_MIN_PERCENT)

        self.QUANTITY_MIN_PERCENT = decimal.Decimal(str(0.1))
        self.QUANTITY_MAX_PERCENT = decimal.Decimal(str(0.9))
        self.QUANTITY_ATTENUATION = (self.QUANTITY_MAX_PERCENT - self.QUANTITY_MIN_PERCENT) / self.MAX_SUM_RESULT

        self.QUANTITY_MARKET_MIN_PERCENT = decimal.Decimal(str(0.3))
        self.QUANTITY_MARKET_MAX_PERCENT = decimal.Decimal(str(1))
        self.QUANTITY_BUY_MARKET_ATTENUATION = decimal.Decimal(str(0.2))
        self.QUANTITY_MARKET_ATTENUATION = (self.QUANTITY_MARKET_MAX_PERCENT - self.QUANTITY_MARKET_MIN_PERCENT) \
                                           / self.MAX_SUM_RESULT

        self.BUY_LIMIT_ORDER_MAX_PERCENT = decimal.Decimal(str(0.995))
        self.BUY_LIMIT_ORDER_MIN_PERCENT = decimal.Decimal(str(0.98))
        self.SELL_LIMIT_ORDER_MIN_PERCENT = 1 + (1 - self.BUY_LIMIT_ORDER_MAX_PERCENT)
        self.SELL_LIMIT_ORDER_MAX_PERCENT = 1 + (1 - self.BUY_LIMIT_ORDER_MIN_PERCENT)
        self.LIMIT_ORDER_ATTENUATION = (self.BUY_LIMIT_ORDER_MAX_PERCENT - self.BUY_LIMIT_ORDER_MIN_PERCENT) \
                                       / self.MAX_SUM_RESULT

        self.QUANTITY_RISK_WEIGHT = decimal.Decimal(str(0.2))
        self.MAX_QUANTITY_RATIO = decimal.Decimal(str(1))
        self.MIN_QUANTITY_RATIO = decimal.Decimal(str(0.2))
        self.DELTA_RATIO = self.MAX_QUANTITY_RATIO - self.MIN_QUANTITY_RATIO
        # consider a high ratio not to take too much risk and not to prevent order creation either
        self.DEFAULT_HOLDING_RATIO = decimal.Decimal(str(0.35))

        self.SELL_MULTIPLIER = decimal.Decimal(str(5))
        self.FULL_SELL_MIN_RATIO = decimal.Decimal(str(0.05))

        trading_config = self.trading_mode.trading_config if self.trading_mode else {}

        self.USE_TARGET_PROFIT_MODE = trading_config.get("target_profits_mode", False)
        self.USE_CLOSE_TO_CURRENT_PRICE = trading_config.get("use_prices_close_to_current_price", False)
        self.CLOSE_TO_CURRENT_PRICE_DEFAULT_RATIO = decimal.Decimal(str(
            trading_config.get("close_to_current_price_difference") or 0.02
        ))
        self.TARGET_PROFIT_TAKE_PROFIT = decimal.Decimal(str(
            trading_config.get("target_profits_mode_take_profit") or 5
        )) / trading_constants.ONE_HUNDRED
        self.USE_STOP_ORDERS = trading_config.get("use_stop_orders", True)
        self.TARGET_PROFIT_STOP_LOSS = decimal.Decimal(str(
            trading_config.get("target_profits_mode_stop_loss") or 2.5
        )) / trading_constants.ONE_HUNDRED
        self.TARGET_PROFIT_ENABLE_POSITION_INCREASE = trading_config.get(
            "target_profits_mode_enable_position_increase", False
        )
        self.BUY_WITH_MAXIMUM_SIZE_ORDERS = trading_config.get("buy_with_maximum_size_orders", False)
        self.SELL_WITH_MAXIMUM_SIZE_ORDERS = trading_config.get("sell_with_maximum_size_orders", False)
        self.DISABLE_SELL_ORDERS = trading_config.get("disable_sell_orders", False)
        self.DISABLE_BUY_ORDERS = trading_config.get("disable_buy_orders", False)
        self.MAX_CURRENCY_RATIO = trading_config.get("max_currency_percent", None) or None
        if self.MAX_CURRENCY_RATIO is not None:
            try:
                self.MAX_CURRENCY_RATIO = decimal.Decimal(str(self.MAX_CURRENCY_RATIO)) / trading_constants.ONE_HUNDRED
            except decimal.InvalidOperation:
                self.MAX_CURRENCY_RATIO = None

    def flush(self):
        super().flush()
        self.trader = None

    """
    Starting point : self.SELL_LIMIT_ORDER_MIN_PERCENT or self.BUY_LIMIT_ORDER_MAX_PERCENT
    1 - abs(eval_note) --> confirmation level --> high : sell less expensive / buy more expensive
    1 - trader.risk --> high risk : sell / buy closer to the current price
    1 - abs(eval_note) + 1 - trader.risk --> result between 0 and 2 --> self.MAX_SUM_RESULT
    self.QUANTITY_ATTENUATION --> try to contains the result between self.XXX_MIN_PERCENT and self.XXX_MAX_PERCENT
    """

    def _get_limit_price_from_risk(self, eval_note):
        if eval_note > 0:
            if self.USE_CLOSE_TO_CURRENT_PRICE:
                return 1 + self.CLOSE_TO_CURRENT_PRICE_DEFAULT_RATIO
            factor = self.SELL_LIMIT_ORDER_MIN_PERCENT + \
                     ((1 - abs(eval_note) + 1 - self.trader.risk) * self.LIMIT_ORDER_ATTENUATION)
            return trading_modes.check_factor(self.SELL_LIMIT_ORDER_MIN_PERCENT,
                                              self.SELL_LIMIT_ORDER_MAX_PERCENT, factor)
        else:
            if self.USE_CLOSE_TO_CURRENT_PRICE:
                return 1 - self.CLOSE_TO_CURRENT_PRICE_DEFAULT_RATIO
            factor = self.BUY_LIMIT_ORDER_MAX_PERCENT - \
                     ((1 - abs(eval_note) + 1 - self.trader.risk) * self.LIMIT_ORDER_ATTENUATION)
            return trading_modes.check_factor(self.BUY_LIMIT_ORDER_MIN_PERCENT,
                                              self.BUY_LIMIT_ORDER_MAX_PERCENT, factor)

    """
    Starting point : self.STOP_LOSS_ORDER_MAX_PERCENT
    trader.risk --> low risk : stop level close to the current price
    self.STOP_LOSS_ORDER_ATTENUATION --> try to contains the result between self.STOP_LOSS_ORDER_MIN_PERCENT
    and self.STOP_LOSS_ORDER_MAX_PERCENT
    """

    def _get_stop_price_from_risk(self, is_long):
        max_percent = self.STOP_LOSS_ORDER_MAX_PERCENT if is_long \
            else 2 * trading_constants.ONE - self.STOP_LOSS_ORDER_MIN_PERCENT
        min_percent = self.STOP_LOSS_ORDER_MIN_PERCENT if is_long \
            else 2 * trading_constants.ONE - self.STOP_LOSS_ORDER_MAX_PERCENT
        risk_difference = self.trader.risk * self.STOP_LOSS_ORDER_ATTENUATION
        factor = max_percent - risk_difference if is_long else min_percent + risk_difference
        return trading_modes.check_factor(min_percent, max_percent, factor)

    """
    Starting point : self.QUANTITY_MIN_PERCENT
    abs(eval_note) --> confirmation level --> high : sell/buy more quantity
    trader.risk --> high risk : sell / buy more quantity
    abs(eval_note) + weighted_risk --> result between 0 and 1 + self.QUANTITY_RISK_WEIGHT --> self.MAX_SUM_RESULT
    self.QUANTITY_ATTENUATION --> try to contains the result between self.QUANTITY_MIN_PERCENT
    and self.QUANTITY_MAX_PERCENT
    """

    async def _get_buy_limit_quantity_from_risk(self, ctx, eval_note, quantity, quote, increasing_position):
        # check all in orders
        if increasing_position and self.BUY_WITH_MAXIMUM_SIZE_ORDERS:
            return quantity
        # check configured quantity
        if user_amount := trading_modes.get_user_selected_order_amount(
            self.trading_mode,
            self.TARGET_PROFIT_MODE_ENTRY_QUANTITY_SIDE
            if self.USE_TARGET_PROFIT_MODE else trading_enums.TradeOrderSide.BUY
        ):
            return await script_keywords.get_amount_from_input_amount(
                context=ctx,
                input_amount=user_amount,
                side=trading_enums.TradeOrderSide.BUY.value,
                reduce_only=False,
                is_stop_order=False,
                use_total_holding=False,
            )
        # get quantity from risk
        max_amount = self._get_max_amount_from_max_ratio(
            self.MAX_CURRENCY_RATIO, quantity, quote, self.QUANTITY_MAX_PERCENT
        ) if increasing_position else quantity
        weighted_risk = self.trader.risk * self.QUANTITY_RISK_WEIGHT
        # consider buy quantity like a sell if quote is the reference market
        if quote == self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market \
                and increasing_position:
            weighted_risk *= self.SELL_MULTIPLIER
        if not increasing_position and self._get_ratio(quote) < self.FULL_SELL_MIN_RATIO:
            return quantity
        factor = self.QUANTITY_MIN_PERCENT + ((abs(eval_note) + weighted_risk) * self.QUANTITY_ATTENUATION)
        checked_factor = trading_modes.check_factor(self.QUANTITY_MIN_PERCENT, self.QUANTITY_MAX_PERCENT,
                                                    factor)
        holding_ratio = self._get_quantity_ratio(quote) if increasing_position else trading_constants.ONE
        return min(checked_factor * quantity * holding_ratio, max_amount)

    """
    Starting point : self.QUANTITY_MIN_PERCENT
    abs(eval_note) --> confirmation level --> high : sell/buy more quantity
    trader.risk --> high risk : sell / buy more quantity
    use SELL_MULTIPLIER to increase sell volume relatively to risk
    if currency holding < FULL_SELL_MIN_RATIO, sell everything to free up funds
    abs(eval_note) + weighted_risk --> result between 0 and 1 + self.QUANTITY_RISK_WEIGHT --> self.MAX_SUM_RESULT
    self.QUANTITY_ATTENUATION --> try to contains the result between self.QUANTITY_MIN_PERCENT
    and self.QUANTITY_MAX_PERCENT
    """

    async def _get_sell_limit_quantity_from_risk(self, ctx, eval_note, quantity, quote, increasing_position):
        # check all in orders
        if not increasing_position and self.SELL_WITH_MAXIMUM_SIZE_ORDERS:
            return quantity
        if user_amount := trading_modes.get_user_selected_order_amount(
            self.trading_mode,
            self.TARGET_PROFIT_MODE_ENTRY_QUANTITY_SIDE
            if self.USE_TARGET_PROFIT_MODE else trading_enums.TradeOrderSide.SELL
        ):
            return await script_keywords.get_amount_from_input_amount(
                context=ctx,
                input_amount=user_amount,
                side=trading_enums.TradeOrderSide.SELL.value,
                reduce_only=False,
                is_stop_order=False,
                use_total_holding=False,
            )
        # check configured quantity
        # get quantity from risk
        max_amount = self._get_max_amount_from_max_ratio(
            self.MAX_CURRENCY_RATIO, quantity, quote, self.QUANTITY_MAX_PERCENT
        ) if increasing_position else quantity
        weighted_risk = self.trader.risk * self.QUANTITY_RISK_WEIGHT
        # consider sell quantity like a buy if base is the reference market
        if quote != self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market \
                and not increasing_position:
            weighted_risk *= self.SELL_MULTIPLIER
        if not increasing_position and self._get_ratio(quote) < self.FULL_SELL_MIN_RATIO:
            return quantity
        factor = self.QUANTITY_MIN_PERCENT + ((abs(eval_note) + weighted_risk) * self.QUANTITY_ATTENUATION)
        checked_factor = trading_modes.check_factor(self.QUANTITY_MIN_PERCENT, self.QUANTITY_MAX_PERCENT,
                                                    factor)
        holding_ratio = self._get_quantity_ratio(quote) if increasing_position else trading_constants.ONE
        return min(checked_factor * quantity * holding_ratio, max_amount)

    """
    Starting point : self.QUANTITY_MARKET_MIN_PERCENT
    abs(eval_note) --> confirmation level --> high : sell/buy more quantity
    trader.risk --> high risk : sell / buy more quantity
    use SELL_MULTIPLIER to increase sell volume relatively to risk
    abs(eval_note) + trader.risk --> result between 0 and 1 + self.QUANTITY_RISK_WEIGHT --> self.MAX_SUM_RESULT
    self.QUANTITY_MARKET_ATTENUATION --> try to contains the result between self.QUANTITY_MARKET_MIN_PERCENT
    and self.QUANTITY_MARKET_MAX_PERCENT
    """

    async def _get_market_quantity_from_risk(self, ctx, eval_note, quantity, quote, selling, increasing_position):
        # check configured quantity
        side = self.TARGET_PROFIT_MODE_ENTRY_QUANTITY_SIDE if self.USE_TARGET_PROFIT_MODE else (
            trading_enums.TradeOrderSide.SELL if selling else trading_enums.TradeOrderSide.BUY
        )
        if user_amount := trading_modes.get_user_selected_order_amount(self.trading_mode, side):
            return await script_keywords.get_amount_from_input_amount(
                context=ctx,
                input_amount=user_amount,
                side=side.value,
                reduce_only=False,
                is_stop_order=False,
                use_total_holding=False,
            )
        # get quantity from risk
        max_amount = quantity * self.QUANTITY_MARKET_MAX_PERCENT if increasing_position \
            else self._get_max_amount_from_max_ratio(self.MAX_CURRENCY_RATIO, quantity,
                                                     quote, self.QUANTITY_MARKET_MAX_PERCENT)
        weighted_risk = self.trader.risk * self.QUANTITY_RISK_WEIGHT
        ref_market = self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
        if (not increasing_position and quote != ref_market) or (increasing_position and quote == ref_market):
            weighted_risk *= self.SELL_MULTIPLIER
        factor = self.QUANTITY_MARKET_MIN_PERCENT + (
                (abs(eval_note) + weighted_risk) * self.QUANTITY_MARKET_ATTENUATION)

        checked_factor = trading_modes.check_factor(self.QUANTITY_MARKET_MIN_PERCENT,
                                                    self.QUANTITY_MARKET_MAX_PERCENT, factor)
        holding_ratio = 1 if not increasing_position else self._get_quantity_ratio(quote)
        return min(checked_factor * holding_ratio * quantity, max_amount)

    def _get_ratio(self, currency):
        try:
            return self.get_holdings_ratio(currency)
        except trading_errors.MissingPriceDataError:
            # Can happen when ref market is not in the pair, data will be available later (ticker is now registered)
            return self.DEFAULT_HOLDING_RATIO

    def _get_quantity_ratio(self, currency):
        if self.get_number_of_traded_assets() > 2:
            ratio = self._get_ratio(currency)
            # returns a linear result between self.MIN_QUANTITY_RATIO and self.MAX_QUANTITY_RATIO: closer to
            # self.MAX_QUANTITY_RATIO when holdings are lower in % and to self.MIN_QUANTITY_RATIO when holdings
            # are higher in %
            return 1 - min(ratio * self.DELTA_RATIO, 1)
        else:
            return 1

    def _get_max_amount_from_max_ratio(self, max_ratio, quantity, quote, default_ratio):
        # TODO ratios in futures trading
        # reduce max amount when self.MAX_CURRENCY_RATIO is defined
        if self.MAX_CURRENCY_RATIO is None or max_ratio == trading_constants.ONE or self.exchange_manager.is_future:
            return quantity * default_ratio
        max_amount_ratio = max_ratio - self._get_ratio(quote)
        if max_amount_ratio > 0:
            max_amount_in_ref_market = trading_api.get_current_portfolio_value(self.exchange_manager) * \
                                       max_amount_ratio
            try:
                max_theoretical_amount = max_amount_in_ref_market / trading_api.get_current_crypto_currency_value(
                    self.exchange_manager, quote)
                return min(max_theoretical_amount, quantity)
            except KeyError:
                self.logger.error(f"Missing price information in reference market for {quote}. Skipping buy order "
                                  f"as is it required to ensure the maximum currency percent parameter. "
                                  f"Set it to 100 to buy anyway.")
        return trading_constants.ZERO

    async def _create_order(
        self, current_order,
        use_take_profit_orders, take_profit_price,
        use_stop_loss_orders, stop_price,
        symbol_market, tag
    ):
        params = {}
        chained_orders = []
        is_long = current_order.side is trading_enums.TradeOrderSide.BUY
        exit_side = trading_enums.TradeOrderSide.SELL if is_long else trading_enums.TradeOrderSide.BUY
        if use_stop_loss_orders:
            stop_price = trading_personal_data.decimal_adapt_price(
                symbol_market,
                current_order.origin_price * (
                    trading_constants.ONE + (self.TARGET_PROFIT_STOP_LOSS * (-1 if is_long else 1))
                )
            ) if stop_price.is_nan() else stop_price
            param_update, chained_order = await self.register_chained_order(
                current_order, stop_price, trading_enums.TraderOrderType.STOP_LOSS, exit_side, tag=tag
            )
            params.update(param_update)
            chained_orders.append(chained_order)
        if use_take_profit_orders:
            take_profit_price = trading_personal_data.decimal_adapt_price(
                symbol_market,
                current_order.origin_price * (
                    trading_constants.ONE + (self.TARGET_PROFIT_TAKE_PROFIT * (1 if is_long else -1))
                )
            ) if take_profit_price.is_nan() else take_profit_price
            order_type = self.exchange_manager.trader.get_take_profit_order_type(
                current_order,
                trading_enums.TraderOrderType.SELL_LIMIT if exit_side is trading_enums.TradeOrderSide.SELL
                else trading_enums.TraderOrderType.BUY_LIMIT
            )
            param_update, chained_order = await self.register_chained_order(
                current_order, take_profit_price, order_type, exit_side, tag=tag
            )
            params.update(param_update)
            chained_orders.append(chained_order)
        if len(chained_orders) > 1:
            oco_group = self.exchange_manager.exchange_personal_data.orders_manager \
                .create_group(trading_personal_data.OneCancelsTheOtherOrderGroup)
            for order in chained_orders:
                order.add_to_order_group(oco_group)
        return await self.trading_mode.create_order(current_order, params=params or None)

    async def create_new_orders(self, symbol, final_note, state, **kwargs):
        try:
            if final_note.is_nan():
                return []
        except AttributeError:
            final_note = decimal.Decimal(str(final_note))
            if final_note.is_nan():
                return []
        data = kwargs.get(self.CREATE_ORDER_DATA_PARAM, {})
        user_price = data.get(self.PRICE_KEY, trading_constants.ZERO)
        user_volume = data.get(self.VOLUME_KEY, trading_constants.ZERO)
        user_reduce_only = data.get(self.REDUCE_ONLY_KEY, False) if self.exchange_manager.is_future else None
        tag = data.get(self.TAG_KEY, None)
        exchange_creation_params = data.get(self.ORDER_EXCHANGE_CREATION_PARAMS, {})
        current_order = None
        orders_should_have_been_created = False
        timeout = kwargs.pop("timeout", trading_constants.ORDER_DATA_FETCHING_TIMEOUT)
        ctx = script_keywords.get_base_context(self.trading_mode, symbol)
        try:
            current_symbol_holding, current_market_holding, market_quantity, price, symbol_market = \
                await trading_personal_data.get_pre_order_data(self.exchange_manager, symbol=symbol, timeout=timeout)
            self.logger.debug(
                f"Order creation inputs: "
                f"current_symbol_holding: {current_symbol_holding}, "
                f"current_market_holding: {current_market_holding}, "
                f"market_quantity: {market_quantity}, "
                f"price: {price}."
            )
            max_buy_size = market_quantity
            max_sell_size = current_symbol_holding
            spot_increasing_position = state in (trading_enums.EvaluatorStates.VERY_LONG.value,
                                                 trading_enums.EvaluatorStates.LONG.value)
            if self.exchange_manager.is_future:
                # on futures, current_symbol_holding = current_market_holding = market_quantity
                max_buy_size, buy_increasing_position = trading_personal_data.get_futures_max_order_size(
                    self.exchange_manager, symbol, trading_enums.TradeOrderSide.BUY,
                    price, False, current_symbol_holding, market_quantity
                )
                max_sell_size, sell_increasing_position = trading_personal_data.get_futures_max_order_size(
                    self.exchange_manager, symbol, trading_enums.TradeOrderSide.SELL,
                    price, False, current_symbol_holding, market_quantity
                )
                # take the right value depending on if we are in a buy or sell condition
                increasing_position = buy_increasing_position if spot_increasing_position else sell_increasing_position
            else:
                increasing_position = spot_increasing_position

            base = symbol_util.parse_symbol(symbol).base
            created_orders = []
            # use stop loss when reducing the position and stop are enabled or when the user explicitly asks for one
            user_take_profit_price = trading_personal_data.decimal_adapt_price(
                symbol_market,
                data.get(self.TAKE_PROFIT_PRICE_KEY, decimal.Decimal(math.nan))
            )
            user_stop_price = trading_personal_data.decimal_adapt_price(
                symbol_market,
                data.get(self.STOP_PRICE_KEY, decimal.Decimal(math.nan))
            )
            create_stop_only = data.get(self.STOP_ONLY, False)
            if create_stop_only and (not user_stop_price or user_stop_price.is_nan()):
                self.logger.error("Stop price is required to create a stop order")
                return []
            is_reducing_position = not increasing_position
            if self.USE_TARGET_PROFIT_MODE:
                if is_reducing_position:
                    self.logger.debug("Ignored reducing position signal as Target Profit Mode is enabled. "
                                      "Positions are reduced from chained orders that are created at entry time.")
                    return []
                elif not self.TARGET_PROFIT_ENABLE_POSITION_INCREASE:
                    if self.exchange_manager.is_future:
                        current_position = self.exchange_manager.exchange_personal_data.positions_manager\
                            .get_symbol_position(
                                symbol,
                                trading_enums.PositionSide.BOTH
                            )
                        if not current_position.is_idle():
                            self.logger.debug(
                                f"Ignored increasing position signal on {symbol} as Mode 'Enable futures "
                                f"position increase' is disabled."
                            )
                            return []

            use_stop_orders = is_reducing_position and (self.USE_STOP_ORDERS or not user_stop_price.is_nan())
            # use stop loss when increasing the position and the user explicitly asks for one
            use_chained_take_profit_orders = increasing_position and (
                not user_take_profit_price.is_nan() or self.USE_TARGET_PROFIT_MODE
            )
            use_chained_stop_loss_orders = increasing_position and (
                not user_stop_price.is_nan() or (self.USE_TARGET_PROFIT_MODE and self.USE_STOP_ORDERS)
            )
            if state == trading_enums.EvaluatorStates.VERY_SHORT.value and not self.DISABLE_SELL_ORDERS:
                quantity = user_volume \
                           or await self._get_market_quantity_from_risk(
                    ctx, final_note, max_sell_size, base, True, increasing_position
                )
                quantity = trading_personal_data.decimal_add_dusts_to_quantity_if_necessary(quantity, price,
                                                                                            symbol_market,
                                                                                            max_sell_size)

                for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                        quantity,
                        price,
                        symbol_market):
                    orders_should_have_been_created = True
                    current_order = trading_personal_data.create_order_instance(
                        trader=self.trader,
                        order_type=trading_enums.TraderOrderType.SELL_MARKET,
                        symbol=symbol,
                        current_price=order_price,
                        quantity=order_quantity,
                        price=order_price,
                        reduce_only=user_reduce_only,
                        exchange_creation_params=exchange_creation_params,
                        tag=tag,
                    )
                    if current_order := await self._create_order(
                        current_order,
                        use_chained_take_profit_orders, user_take_profit_price,
                        use_chained_stop_loss_orders, user_stop_price,
                        symbol_market, tag
                    ):
                        created_orders.append(current_order)

            elif state == trading_enums.EvaluatorStates.SHORT.value and not self.DISABLE_SELL_ORDERS:
                quantity = user_volume or \
                           await self._get_sell_limit_quantity_from_risk(
                               ctx, final_note, max_sell_size, base, increasing_position
                           )
                quantity = trading_personal_data.decimal_add_dusts_to_quantity_if_necessary(quantity, price,
                                                                                            symbol_market,
                                                                                            max_sell_size)
                limit_price = user_stop_price if create_stop_only else trading_personal_data.decimal_adapt_price(
                    symbol_market, user_price or (price * self._get_limit_price_from_risk(final_note))
                )
                for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                        quantity,
                        limit_price,
                        symbol_market):
                    orders_should_have_been_created = True
                    current_order = trading_personal_data.create_order_instance(
                        trader=self.trader,
                        order_type=trading_enums.TraderOrderType.SELL_LIMIT,
                        symbol=symbol,
                        current_price=price,
                        quantity=order_quantity,
                        price=order_price,
                        reduce_only=user_reduce_only,
                        exchange_creation_params=exchange_creation_params,
                        tag=tag,
                    )
                    updated_limit = None
                    if create_stop_only or (updated_limit := await self._create_order(
                        current_order,
                        use_chained_take_profit_orders, user_take_profit_price,
                        use_chained_stop_loss_orders, user_stop_price,
                        symbol_market, tag
                    )):
                        if updated_limit:
                            created_orders.append(updated_limit)
                        # ensure limit order was not instantly filled
                        if create_stop_only or (use_stop_orders and updated_limit and updated_limit.is_open()):
                            oco_group = None
                            if updated_limit:
                                oco_group = self.exchange_manager.exchange_personal_data.orders_manager \
                                    .create_group(trading_personal_data.OneCancelsTheOtherOrderGroup)
                                updated_limit.add_to_order_group(oco_group)
                            stop_price = trading_personal_data.decimal_adapt_price(
                                symbol_market, price * self._get_stop_price_from_risk(True)
                            ) if user_stop_price.is_nan() else user_stop_price
                            current_order = trading_personal_data.create_order_instance(
                                trader=self.trader,
                                order_type=trading_enums.TraderOrderType.STOP_LOSS,
                                symbol=symbol,
                                current_price=price,
                                quantity=order_quantity,
                                price=stop_price,
                                side=trading_enums.TradeOrderSide.SELL,
                                reduce_only=True,
                                group=oco_group,
                                exchange_creation_params=exchange_creation_params,
                                tag=tag,
                            )
                            created_stop = await self.trading_mode.create_order(current_order)
                            if create_stop_only:
                                created_orders.append(created_stop)

            elif state == trading_enums.EvaluatorStates.NEUTRAL.value:
                return []

            elif state == trading_enums.EvaluatorStates.LONG.value and not self.DISABLE_BUY_ORDERS:
                quantity = await self._get_buy_limit_quantity_from_risk(
                    ctx, final_note, max_buy_size, base, increasing_position
                ) \
                    if user_volume == 0 else user_volume
                limit_price = user_stop_price if create_stop_only else trading_personal_data.decimal_adapt_price(
                    symbol_market, user_price or (price * self._get_limit_price_from_risk(final_note))
                )
                quantity = trading_personal_data.decimal_adapt_order_quantity_because_fees(
                    self.exchange_manager, symbol, trading_enums.TraderOrderType.BUY_LIMIT, quantity,
                    limit_price, trading_enums.ExchangeConstantsMarketPropertyColumns.TAKER,
                    trading_enums.TradeOrderSide.BUY, current_market_holding
                )
                for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                        quantity,
                        limit_price,
                        symbol_market):
                    orders_should_have_been_created = True
                    current_order = trading_personal_data.create_order_instance(
                        trader=self.trader,
                        order_type=trading_enums.TraderOrderType.BUY_LIMIT,
                        symbol=symbol,
                        current_price=price,
                        quantity=order_quantity,
                        price=order_price,
                        reduce_only=user_reduce_only,
                        exchange_creation_params=exchange_creation_params,
                        tag=tag,
                    )
                    updated_limit = None
                    if create_stop_only or (updated_limit := await self._create_order(
                        current_order,
                        use_chained_take_profit_orders, user_take_profit_price,
                        use_chained_stop_loss_orders, user_stop_price,
                        symbol_market, tag
                    )):
                        if updated_limit:
                            created_orders.append(updated_limit)
                        # ensure limit order was not instantly filled
                        if create_stop_only or (use_stop_orders and updated_limit and updated_limit.is_open()):
                            oco_group = None
                            if updated_limit:
                                oco_group = self.exchange_manager.exchange_personal_data.orders_manager \
                                    .create_group(trading_personal_data.OneCancelsTheOtherOrderGroup)
                                updated_limit.add_to_order_group(oco_group)
                            stop_price = trading_personal_data.decimal_adapt_price(
                                symbol_market, price * self._get_stop_price_from_risk(False)
                            ) if user_stop_price.is_nan() else user_stop_price
                            current_order = trading_personal_data.create_order_instance(
                                trader=self.trader,
                                order_type=trading_enums.TraderOrderType.STOP_LOSS,
                                symbol=symbol,
                                current_price=price,
                                quantity=order_quantity,
                                price=stop_price,
                                side=trading_enums.TradeOrderSide.BUY,
                                reduce_only=True,
                                group=oco_group,
                                exchange_creation_params=exchange_creation_params,
                                tag=tag,
                            )
                            await self.trading_mode.create_order(current_order)
                            created_stop = await self.trading_mode.create_order(current_order)
                            if create_stop_only:
                                created_orders.append(created_stop)

            elif state == trading_enums.EvaluatorStates.VERY_LONG.value and not self.DISABLE_BUY_ORDERS:
                quantity = await self._get_market_quantity_from_risk(
                    ctx, final_note, max_buy_size, base, False, increasing_position
                ) \
                    if user_volume == 0 else user_volume
                quantity = trading_personal_data.decimal_adapt_order_quantity_because_fees(
                    self.exchange_manager, symbol, trading_enums.TraderOrderType.BUY_MARKET, quantity,
                    price, trading_enums.ExchangeConstantsMarketPropertyColumns.TAKER,
                    trading_enums.TradeOrderSide.BUY, current_market_holding
                )
                for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                        quantity,
                        price,
                        symbol_market):
                    orders_should_have_been_created = True
                    current_order = trading_personal_data.create_order_instance(
                        trader=self.trader,
                        order_type=trading_enums.TraderOrderType.BUY_MARKET,
                        symbol=symbol,
                        current_price=order_price,
                        quantity=order_quantity,
                        price=order_price,
                        reduce_only=user_reduce_only,
                        exchange_creation_params=exchange_creation_params,
                        tag=tag,
                    )
                    if current_order := await self._create_order(
                        current_order,
                        use_chained_take_profit_orders, user_take_profit_price,
                        use_chained_stop_loss_orders, user_stop_price,
                        symbol_market, tag
                    ):
                        created_orders.append(current_order)
            if created_orders:
                return created_orders
            if orders_should_have_been_created:
                raise trading_errors.OrderCreationError()
            raise trading_errors.MissingMinimalExchangeTradeVolume()

        except (trading_errors.MissingFunds,
                trading_errors.MissingMinimalExchangeTradeVolume,
                trading_errors.OrderCreationError):
            raise
        except asyncio.TimeoutError as e:
            self.logger.error(f"Impossible to create order for {symbol} on {self.exchange_manager.exchange_name}: {e} "
                              f"and is necessary to compute the order details.")
            return []
        except Exception as e:
            self.logger.exception(e, True, f"Failed to create order : {e}.")
            return []


class DailyTradingModeProducer(trading_modes.AbstractTradingModeProducer):

    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)

        self.state = None

        # If final_eval not is < X_THRESHOLD --> state = X
        self.VERY_LONG_THRESHOLD = decimal.Decimal("-0.85")
        self.LONG_THRESHOLD = decimal.Decimal("-0.25")
        self.NEUTRAL_THRESHOLD = decimal.Decimal("0.25")
        self.SHORT_THRESHOLD = decimal.Decimal("0.85")
        self.RISK_THRESHOLD = decimal.Decimal("0.2")

    async def stop(self):
        if self.trading_mode is not None:
            self.trading_mode.flush_trading_mode_consumers()
        await super().stop()

    async def set_final_eval(self, matrix_id: str, cryptocurrency: str, symbol: str, time_frame, trigger_source: str):
        strategies_analysis_note_counter = 0
        evaluation = commons_constants.INIT_EVAL_NOTE
        # Strategies analysis
        for evaluated_strategy_node in matrix.get_tentacles_value_nodes(
                matrix_id,
                matrix.get_tentacle_nodes(matrix_id,
                                          exchange_name=self.exchange_name,
                                          tentacle_type=evaluators_enums.EvaluatorMatrixTypes.STRATEGIES.value),
                cryptocurrency=cryptocurrency,
                symbol=symbol):

            if evaluators_util.check_valid_eval_note(evaluators_api.get_value(evaluated_strategy_node),
                                                     evaluators_api.get_type(evaluated_strategy_node),
                                                     evaluators_constants.EVALUATOR_EVAL_DEFAULT_TYPE):
                evaluation += evaluators_api.get_value(
                    evaluated_strategy_node
                )
                strategies_analysis_note_counter += 1

        if strategies_analysis_note_counter > 0:
            self.final_eval = decimal.Decimal(str(evaluation / strategies_analysis_note_counter))
            await self.create_state(cryptocurrency=cryptocurrency, symbol=symbol)

    def _get_delta_risk(self):
        return self.RISK_THRESHOLD * self.exchange_manager.trader.risk

    async def create_state(self, cryptocurrency: str, symbol: str):
        if self.final_eval.is_nan():
            # discard NaN case as it is not usable
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.NEUTRAL)
            return
        delta_risk = self._get_delta_risk()
        if self.final_eval < self.VERY_LONG_THRESHOLD + delta_risk:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.VERY_LONG)
        elif self.final_eval < self.LONG_THRESHOLD + delta_risk:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.LONG)
        elif self.final_eval < self.NEUTRAL_THRESHOLD - delta_risk:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.NEUTRAL)
        elif self.final_eval < self.SHORT_THRESHOLD - delta_risk:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.SHORT)
        else:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.VERY_SHORT)

    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True

    async def _set_state(self, cryptocurrency: str, symbol: str, new_state):
        if new_state != self.state:
            self.state = new_state
            self.logger.info(f"[{symbol}] new state: {self.state.name}")

            # if new state is not neutral --> cancel orders and create new else keep orders
            if new_state is not trading_enums.EvaluatorStates.NEUTRAL:
                if self.trading_mode.consumers:
                    if self.trading_mode.consumers[0].USE_TARGET_PROFIT_MODE:
                        await self._cancel_position_opening_orders(symbol)
                    else:
                        # cancel open orders when not on target profit mode
                        await self.cancel_symbol_open_orders(symbol)

                # call orders creation from consumers
                await self.submit_trading_evaluation(cryptocurrency=cryptocurrency,
                                                     symbol=symbol,
                                                     time_frame=None,
                                                     final_note=self.final_eval,
                                                     state=self.state)

                # send_notification
                if not self.exchange_manager.is_backtesting:
                    await self._send_alert_notification(symbol, new_state)

    async def _cancel_position_opening_orders(self, symbol):
        if self.exchange_manager.trader.is_enabled:
            for order in self.exchange_manager.exchange_personal_data.orders_manager.get_open_orders(symbol=symbol):
                if (
                    not (order.is_cancelled() or order.is_closed())
                    # orders with chained orders and no "triggered by" are "position opening"
                    and order.chained_orders and order.triggered_by is None
                ):
                    await self.trading_mode.cancel_order(order)

    async def _send_alert_notification(self, symbol, new_state):
        try:
            import octobot_services.api as services_api
            import octobot_services.enums as services_enum
            title = f"OCTOBOT ALERT : #{symbol}"
            alert_content, alert_content_markdown = pretty_printer.cryptocurrency_alert(
                new_state,
                self.final_eval)
            await services_api.send_notification(services_api.create_notification(alert_content, title=title,
                                                                                  markdown_text=alert_content_markdown,
                                                                                  category=services_enum.NotificationCategory.PRICE_ALERTS))
        except ImportError as e:
            self.logger.exception(e, True, f"Impossible to send notification: {e}")
