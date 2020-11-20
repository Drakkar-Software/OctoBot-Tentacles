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
import octobot_trading.exchange_channel as exchanges_channel
import octobot_trading.constants as trading_constants
import octobot_trading.modes as trading_modes
import tentacles.Trading.Mode.daily_trading_mode.daily_trading as daily_trading_mode


class SignalTradingMode(trading_modes.AbstractTradingMode):
    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.load_config()

    def get_current_state(self) -> (str, float):
        return super().get_current_state()[0] if self.producers[0].state is None else self.producers[0].state.name, \
            self.producers[0].final_eval

    async def create_producers(self) -> list:
        mode_producer = SignalTradingModeProducer(exchanges_channel.get_chan(trading_constants.MODE_CHANNEL, self.exchange_manager.id),
                                                  self.config, self, self.exchange_manager)
        await mode_producer.run()
        return [mode_producer]

    async def create_consumers(self) -> list:
        mode_consumer = SignalTradingModeConsumer(self)
        await exchanges_channel.get_chan(trading_constants.MODE_CHANNEL, self.exchange_manager.id).new_consumer(
            consumer_instance=mode_consumer,
            trading_mode_name=self.get_name(),
            cryptocurrency=self.cryptocurrency if self.cryptocurrency else channel_constants.CHANNEL_WILDCARD,
            symbol=self.symbol if self.symbol else channel_constants.CHANNEL_WILDCARD,
            time_frame=self.time_frame if self.time_frame else channel_constants.CHANNEL_WILDCARD)
        return [mode_consumer]

    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        return False


class SignalTradingModeConsumer(daily_trading_mode.DailyTradingModeConsumer):
    def __init__(self, trading_mode):
        super().__init__(trading_mode)

        self.STOP_LOSS_ORDER_MAX_PERCENT = 0.99
        self.STOP_LOSS_ORDER_MIN_PERCENT = 0.95

        self.QUANTITY_MIN_PERCENT = 0.1
        self.QUANTITY_MAX_PERCENT = 0.9

        self.QUANTITY_MARKET_MIN_PERCENT = 0.5
        self.QUANTITY_MARKET_MAX_PERCENT = 1
        self.QUANTITY_BUY_MARKET_ATTENUATION = 0.2

        self.BUY_LIMIT_ORDER_MAX_PERCENT = 0.995
        self.BUY_LIMIT_ORDER_MIN_PERCENT = 0.99


class SignalTradingModeProducer(daily_trading_mode.DailyTradingModeProducer):
    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)

        # If final_eval not is < X_THRESHOLD --> state = X
        self.VERY_LONG_THRESHOLD = -0.88
        self.LONG_THRESHOLD = -0.4
        self.NEUTRAL_THRESHOLD = 0.4
        self.SHORT_THRESHOLD = 0.88
        self.RISK_THRESHOLD = 0.15
