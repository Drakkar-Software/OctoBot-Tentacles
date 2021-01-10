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
import async_channel.constants as channel_constants
import async_channel.channels as channels
import octobot_commons.symbol_util as symbol_util
import octobot_services.api as services_api
import tentacles.Services.Services_feeds.trading_view_service_feed as trading_view_service_feed
import tentacles.Trading.Mode.daily_trading_mode.daily_trading as daily_trading_mode
import octobot_trading.constants as trading_constants
import octobot_trading.enums as trading_enums
import octobot_trading.modes as trading_modes
import octobot_trading.exchange_channel as exchanges_channel


class TradingViewSignalsTradingMode(trading_modes.AbstractTradingMode):
    SERVICE_FEED_CLASS = trading_view_service_feed.TradingViewServiceFeed
    EXCHANGE_KEY = "EXCHANGE"
    SYMBOL_KEY = "SYMBOL"
    SIGNAL_KEY = "SIGNAL"
    SELL_SIGNAL = "SELL"
    BUY_SIGNAL = "BUY"

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.load_config()
        self.USE_MARKET_ORDERS = self.trading_config.get("use_market_orders", True)
        self.merged_symbol = None

    def get_current_state(self) -> (str, float):
        return super().get_current_state()[0] if self.producers[0].state is None else self.producers[0].state.name, \
               self.producers[0].final_eval

    async def create_producers(self) -> list:
        mode_producer = TradingViewSignalsModeProducer(
            exchanges_channel.get_chan(trading_constants.MODE_CHANNEL, self.exchange_manager.id),
            self.config, self, self.exchange_manager)
        await mode_producer.run()
        return [mode_producer]

    async def create_consumers(self) -> list:
        mode_consumer = TradingViewSignalsModeConsumer(self)
        await exchanges_channel.get_chan(trading_constants.MODE_CHANNEL, self.exchange_manager.id).new_consumer(
            consumer_instance=mode_consumer,
            trading_mode_name=self.get_name(),
            cryptocurrency=self.cryptocurrency if self.cryptocurrency else channel_constants.CHANNEL_WILDCARD,
            symbol=self.symbol if self.symbol else channel_constants.CHANNEL_WILDCARD,
            time_frame=self.time_frame if self.time_frame else channel_constants.CHANNEL_WILDCARD)
        self.merged_symbol = symbol_util.merge_symbol(self.symbol)
        service_feed = services_api.get_service_feed(self.SERVICE_FEED_CLASS, self.bot_id)
        feed_consumer = None
        if service_feed is not None:
            feed_consumer = await channels.get_chan(service_feed.FEED_CHANNEL.get_name()).new_consumer(
                self._trading_view_signal_callback
            )
        else:
            self.logger.error("Impossible to find the Trading view service feed, this trading mode can't work.")
        return [mode_consumer, feed_consumer]

    async def _trading_view_signal_callback(self, data):
        parsed_data = {}
        for line in data['metadata'].split("\n"):
            values = line.split("=")
            parsed_data[values[0]] = values[1]

        if parsed_data[self.EXCHANGE_KEY].lower() in self.exchange_manager.exchange_name and \
                parsed_data[self.SYMBOL_KEY] == self.merged_symbol:
            await self.producers[0].signal_callback(parsed_data)

    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        return False

    @staticmethod
    def is_backtestable():
        return False


class TradingViewSignalsModeConsumer(daily_trading_mode.DailyTradingModeConsumer):
    def __init__(self, trading_mode):
        super().__init__(trading_mode)
        self.QUANTITY_MIN_PERCENT = 0.1
        self.QUANTITY_MAX_PERCENT = 0.9

        self.QUANTITY_MARKET_MIN_PERCENT = 0.5
        self.QUANTITY_MARKET_MAX_PERCENT = 1
        self.QUANTITY_BUY_MARKET_ATTENUATION = 0.2

        self.BUY_LIMIT_ORDER_MAX_PERCENT = 0.995
        self.BUY_LIMIT_ORDER_MIN_PERCENT = 0.99

        self.USE_CLOSE_TO_CURRENT_PRICE = True
        self.CLOSE_TO_CURRENT_PRICE_DEFAULT_RATIO = trading_mode.trading_config.get("close_to_current_price_difference",
                                                                                    0.02)
        self.USE_MAXIMUM_SIZE_ORDERS = trading_mode.trading_config.get("use_maximum_size_orders", False)
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

    async def set_final_eval(self, matrix_id: str, cryptocurrency: str, symbol: str, time_frame):
        # Ignore matrix calls
        pass

    async def signal_callback(self, parsed_data):
        if parsed_data[TradingViewSignalsTradingMode.SIGNAL_KEY] == TradingViewSignalsTradingMode.SELL_SIGNAL:
            state = trading_enums.EvaluatorStates.VERY_SHORT if self.trading_mode.USE_MARKET_ORDERS else trading_enums.EvaluatorStates.SHORT
        elif parsed_data[TradingViewSignalsTradingMode.SIGNAL_KEY] == TradingViewSignalsTradingMode.BUY_SIGNAL:
            state = trading_enums.EvaluatorStates.VERY_LONG if self.trading_mode.USE_MARKET_ORDERS else trading_enums.EvaluatorStates.LONG
        else:
            self.logger.error(f"Unknown signal: {parsed_data[TradingViewSignalsTradingMode.SIGNAL_KEY]}, "
                              f"full data= {parsed_data}")
            state = trading_enums.EvaluatorStates.NEUTRAL
        self.final_eval = self.EVAL_BY_STATES[state]
        # Force temporary neutral state to allow multiple buy or sell signals
        self.state = trading_enums.EvaluatorStates.NEUTRAL
        # Use daily trading mode state system
        await self._set_state(self.trading_mode.cryptocurrency, self.trading_mode.symbol, state)
