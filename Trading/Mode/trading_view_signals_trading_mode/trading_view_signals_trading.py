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
import math

import async_channel.channels as channels
import octobot_commons.symbols.symbol_util as symbol_util
import octobot_commons.enums as commons_enums
import octobot_services.api as services_api
import tentacles.Services.Services_feeds.trading_view_service_feed as trading_view_service_feed
import tentacles.Trading.Mode.daily_trading_mode.daily_trading as daily_trading_mode
import octobot_trading.constants as trading_constants
import octobot_trading.enums as trading_enums
import octobot_trading.modes as trading_modes
import octobot_trading.modes.script_keywords as script_keywords


class TradingViewSignalsTradingMode(trading_modes.AbstractTradingMode):
    SERVICE_FEED_CLASS = trading_view_service_feed.TradingViewServiceFeed
    EXCHANGE_KEY = "EXCHANGE"
    SYMBOL_KEY = "SYMBOL"
    SIGNAL_KEY = "SIGNAL"
    PRICE_KEY = "PRICE"
    VOLUME_KEY = "VOLUME"
    REDUCE_ONLY_KEY = "REDUCE_ONLY"
    ORDER_TYPE_SIGNAL = "ORDER_TYPE"
    STOP_PRICE_KEY = "STOP_PRICE"
    TAG_KEY = "TAG"
    TAKE_PROFIT_PRICE_KEY = "TAKE_PROFIT_PRICE"
    PARAM_PREFIX_KEY = "PARAM_"
    BUY_SIGNAL = "buy"
    SELL_SIGNAL = "sell"
    MARKET_SIGNAL = "market"
    LIMIT_SIGNAL = "limit"
    STOP_SIGNAL = "stop"
    CANCEL_SIGNAL = "cancel"
    SIDE_PARAM_KEY = "SIDE"

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.USE_MARKET_ORDERS = True
        self.CANCEL_PREVIOUS_ORDERS = True
        self.merged_simple_symbol = None
        self.str_symbol = None

    def init_user_inputs(self, inputs: dict) -> None:
        """
        Called right before starting the tentacle, should define all the tentacle's user inputs unless
        those are defined somewhere else.
        """
        trading_modes.should_emit_trading_signals_user_input(self, inputs)
        self.UI.user_input(
            "use_maximum_size_orders", commons_enums.UserInputTypes.BOOLEAN, False, inputs,
            title="All in trades: Trade with all available funds at each order.",
        )
        self.USE_MARKET_ORDERS = self.UI.user_input(
            "use_market_orders", commons_enums.UserInputTypes.BOOLEAN, True, inputs,
            title="Use market orders: If enabled, placed orders will be market orders only. Otherwise order prices "
                  "are set using the Fixed limit prices difference value.",
        )
        self.UI.user_input(
            "close_to_current_price_difference", commons_enums.UserInputTypes.FLOAT, 0.005, inputs,
            min_val=0,
            title="Fixed limit prices difference: Difference to take into account when placing a limit order "
                  "(used if fixed limit prices is enabled). For a 200 USD price and 0.005 in difference: "
                  "buy price would be 199 and sell price 201.",
        )
        self.CANCEL_PREVIOUS_ORDERS = self.UI.user_input(
            "cancel_previous_orders", commons_enums.UserInputTypes.BOOLEAN, True, inputs,
            title="Cancel previous orders: If enabled, cancel other orders associated to the same symbol when "
                  "receiving a signal. This way, only the latest signal will be taken into account.",
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
        return [TradingViewSignalsModeProducer]

    def get_mode_consumer_classes(self) -> list:
        return [TradingViewSignalsModeConsumer]

    async def _get_feed_consumers(self):
        parsed_symbol = symbol_util.parse_symbol(self.symbol)
        self.str_symbol = str(parsed_symbol)
        self.merged_simple_symbol = parsed_symbol.merged_str_base_and_quote_only_symbol(market_separator="")
        service_feed = services_api.get_service_feed(self.SERVICE_FEED_CLASS, self.bot_id)
        feed_consumer = []
        if service_feed is not None:
            feed_consumer = [await channels.get_chan(service_feed.FEED_CHANNEL.get_name()).new_consumer(
                self._trading_view_signal_callback
            )]
        else:
            self.logger.error("Impossible to find the Trading view service feed, this trading mode can't work.")
        return feed_consumer

    async def create_consumers(self) -> list:
        consumers = await super().create_consumers()
        return consumers + await self._get_feed_consumers()

    async def _trading_view_signal_callback(self, data):
        parsed_data = {}
        signal_data = data.get("metadata", "")
        for line in signal_data.split("\n"):
            if not line.strip():
                # ignore empty lines
                continue
            values = line.split("=")
            try:
                value = values[1].strip()
                # restore booleans
                lower_val = value.lower()
                if lower_val in ("true", "false"):
                    value = lower_val == "true"
                parsed_data[values[0].strip()] = value
            except IndexError:
                self.logger.error(f"Invalid signal line in trading view signal, ignoring it. Line: \"{line}\"")

        try:
            if parsed_data[self.EXCHANGE_KEY].lower() in self.exchange_manager.exchange_name and \
                    (parsed_data[self.SYMBOL_KEY] == self.merged_simple_symbol or
                     parsed_data[self.SYMBOL_KEY] == self.str_symbol):
                await self.producers[0].signal_callback(parsed_data, script_keywords.get_base_context(self))
        except KeyError as e:
            self.logger.error(f"Error when handling trading view signal: missing {e} required value. "
                              f"Signal: \"{signal_data}\"")

    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        return False

    @staticmethod
    def is_backtestable():
        return False


class TradingViewSignalsModeConsumer(daily_trading_mode.DailyTradingModeConsumer):
    def __init__(self, trading_mode):
        super().__init__(trading_mode)
        self.QUANTITY_MIN_PERCENT = decimal.Decimal(str(0.1))
        self.QUANTITY_MAX_PERCENT = decimal.Decimal(str(0.9))

        self.QUANTITY_MARKET_MIN_PERCENT = decimal.Decimal(str(0.5))
        self.QUANTITY_MARKET_MAX_PERCENT = trading_constants.ONE
        self.QUANTITY_BUY_MARKET_ATTENUATION = decimal.Decimal(str(0.2))

        self.BUY_LIMIT_ORDER_MAX_PERCENT = decimal.Decimal(str(0.995))
        self.BUY_LIMIT_ORDER_MIN_PERCENT = decimal.Decimal(str(0.99))

        self.USE_CLOSE_TO_CURRENT_PRICE = True
        self.CLOSE_TO_CURRENT_PRICE_DEFAULT_RATIO = decimal.Decimal(str(trading_mode.trading_config.get("close_to_current_price_difference",
                                                                                    0.02)))
        self.BUY_WITH_MAXIMUM_SIZE_ORDERS = trading_mode.trading_config.get("use_maximum_size_orders", False)
        self.SELL_WITH_MAXIMUM_SIZE_ORDERS = trading_mode.trading_config.get("use_maximum_size_orders", False)
        self.USE_STOP_ORDERS = False


class TradingViewSignalsModeProducer(daily_trading_mode.DailyTradingModeProducer):
    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)
        self.EVAL_BY_STATES = {
            trading_enums.EvaluatorStates.LONG: -0.6,
            trading_enums.EvaluatorStates.SHORT: 0.6,
            trading_enums.EvaluatorStates.VERY_LONG: -1,
            trading_enums.EvaluatorStates.VERY_SHORT: 1,
            trading_enums.EvaluatorStates.NEUTRAL: 0,
        }

    def get_channels_registration(self):
        # do not register on matrix or candles channels
        return []

    async def set_final_eval(self, matrix_id: str, cryptocurrency: str, symbol: str, time_frame, trigger_source: str):
        # Ignore matrix calls
        pass

    async def _parse_order_details(self, ctx, parsed_data):
        side = parsed_data[TradingViewSignalsTradingMode.SIGNAL_KEY].casefold()
        order_type = parsed_data.get(TradingViewSignalsTradingMode.ORDER_TYPE_SIGNAL, "").casefold()
        order_exchange_creation_params = {
            param_name.split(TradingViewSignalsTradingMode.PARAM_PREFIX_KEY)[1]: param_value
            for param_name, param_value in parsed_data.items()
            if param_name.startswith(TradingViewSignalsTradingMode.PARAM_PREFIX_KEY)
        }
        parsed_side = None
        if side == TradingViewSignalsTradingMode.SELL_SIGNAL:
            parsed_side = trading_enums.TradeOrderSide.SELL.value
            if order_type == TradingViewSignalsTradingMode.MARKET_SIGNAL:
                state = trading_enums.EvaluatorStates.VERY_SHORT
            elif order_type in (TradingViewSignalsTradingMode.LIMIT_SIGNAL, TradingViewSignalsTradingMode.STOP_SIGNAL):
                state = trading_enums.EvaluatorStates.SHORT
            else:
                state = trading_enums.EvaluatorStates.VERY_SHORT if self.trading_mode.USE_MARKET_ORDERS \
                    else trading_enums.EvaluatorStates.SHORT
        elif side == TradingViewSignalsTradingMode.BUY_SIGNAL:
            parsed_side = trading_enums.TradeOrderSide.BUY.value
            if order_type == TradingViewSignalsTradingMode.MARKET_SIGNAL:
                state = trading_enums.EvaluatorStates.VERY_LONG
            elif order_type in (TradingViewSignalsTradingMode.LIMIT_SIGNAL, TradingViewSignalsTradingMode.STOP_SIGNAL):
                state = trading_enums.EvaluatorStates.LONG
            else:
                state = trading_enums.EvaluatorStates.VERY_LONG if self.trading_mode.USE_MARKET_ORDERS \
                    else trading_enums.EvaluatorStates.LONG
        elif side == TradingViewSignalsTradingMode.CANCEL_SIGNAL:
            state = trading_enums.EvaluatorStates.NEUTRAL
        else:
            self.logger.error(f"Unknown signal: {parsed_data[TradingViewSignalsTradingMode.SIGNAL_KEY]}, "
                              f"full data= {parsed_data}")
            state = trading_enums.EvaluatorStates.NEUTRAL
        target_price = decimal.Decimal(str(parsed_data.get(TradingViewSignalsTradingMode.PRICE_KEY, 0)))
        order_data = {
            TradingViewSignalsModeConsumer.PRICE_KEY: target_price,
            TradingViewSignalsModeConsumer.VOLUME_KEY: await self._parse_volume(ctx, parsed_data, parsed_side,
                                                                                target_price),
            TradingViewSignalsModeConsumer.STOP_PRICE_KEY:
                decimal.Decimal(str(parsed_data.get(TradingViewSignalsTradingMode.STOP_PRICE_KEY, math.nan))),
            TradingViewSignalsModeConsumer.STOP_ONLY: order_type == TradingViewSignalsTradingMode.STOP_SIGNAL,
            TradingViewSignalsModeConsumer.TAKE_PROFIT_PRICE_KEY:
                decimal.Decimal(str(parsed_data.get(TradingViewSignalsTradingMode.TAKE_PROFIT_PRICE_KEY, math.nan))),
            TradingViewSignalsModeConsumer.REDUCE_ONLY_KEY:
                parsed_data.get(TradingViewSignalsTradingMode.REDUCE_ONLY_KEY, False),
            TradingViewSignalsModeConsumer.TAG_KEY:
                parsed_data.get(TradingViewSignalsTradingMode.TAG_KEY, None),
            TradingViewSignalsModeConsumer.ORDER_EXCHANGE_CREATION_PARAMS: order_exchange_creation_params,
        }
        return state, order_data

    async def _parse_volume(self, ctx, parsed_data, side, target_price):
        user_volume = str(parsed_data.get(TradingViewSignalsTradingMode.VOLUME_KEY, 0))
        if user_volume == "0":
            return trading_constants.ZERO
        return await script_keywords.get_amount_from_input_amount(
            context=ctx,
            input_amount=user_volume,
            side=side,
            reduce_only=False,
            is_stop_order=False,
            use_total_holding=False,
            target_price=target_price,
        )

    async def signal_callback(self, parsed_data: dict, ctx):
        if self.trading_mode.CANCEL_PREVIOUS_ORDERS:
            # cancel open orders
            await self.cancel_symbol_open_orders(self.trading_mode.symbol)
        state, order_data = await self._parse_order_details(ctx, parsed_data)
        self.final_eval = self.EVAL_BY_STATES[state]
        # Use daily trading mode state system
        await self._set_state(self.trading_mode.cryptocurrency, ctx.symbol, state, order_data)

    async def _set_state(self, cryptocurrency: str, symbol: str, new_state, order_data):
        async with self.trading_mode_trigger():
            self.state = new_state
            self.logger.info(f"[{symbol}] new state: {self.state.name}")

            # if new state is not neutral --> cancel orders and create new else keep orders
            if new_state is not trading_enums.EvaluatorStates.NEUTRAL:
                # call orders creation from consumers
                await self.submit_trading_evaluation(cryptocurrency=cryptocurrency,
                                                     symbol=symbol,
                                                     time_frame=None,
                                                     final_note=self.final_eval,
                                                     state=self.state,
                                                     data=order_data)

                # send_notification
                if not self.exchange_manager.is_backtesting:
                    await self._send_alert_notification(symbol, new_state)
            else:
                await self.cancel_orders_from_order_data(symbol, order_data)

    async def cancel_orders_from_order_data(self, symbol: str, order_data) -> bool:
        if not self.trading_mode.consumers:
            return False

        cancel_order_raw_side = order_data.get(
            TradingViewSignalsModeConsumer.ORDER_EXCHANGE_CREATION_PARAMS, {}).get(
                TradingViewSignalsTradingMode.SIDE_PARAM_KEY, None)
        cancel_order_side = trading_enums.TradeOrderSide.BUY if cancel_order_raw_side == trading_enums.TradeOrderSide.BUY.value \
            else trading_enums.TradeOrderSide.SELL if cancel_order_raw_side == trading_enums.TradeOrderSide.SELL.value else None
        cancel_order_tag = order_data.get(TradingViewSignalsModeConsumer.TAG_KEY, None)

        # cancel open orders
        return await self.cancel_symbol_open_orders(symbol, side=cancel_order_side, tag=cancel_order_tag)
