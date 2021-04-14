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

import octobot_trading.enums as trading_enums
import octobot_trading.constants as trading_constants
import octobot_trading.modes as trading_modes
import tentacles.Trading.Mode.daily_trading_mode.daily_trading as daily_trading_mode


class PriceSignalTradingModeConsumer(daily_trading_mode.DailyTradingModeConsumer):
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


class PriceSignalTradingModeProducer(daily_trading_mode.DailyTradingModeProducer):
    async def get_market_price(self, symbol):
        try:
            mark_price = await self.exchange_manager.exchange_symbols_data.get_exchange_symbol_data(symbol) \
                .prices_manager.get_mark_price(timeout=trading_constants.ORDER_DATA_FETCHING_TIMEOUT)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError("Mark price is not available")

    async def create_state(self, cryptocurrency: str, symbol: str):
        mark_price = await self.get_market_price(symbol)

        if self.final_eval > mark_price * 1.01:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.VERY_LONG)
        elif self.final_eval > mark_price * 1.005:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.LONG)
        elif mark_price * 1.005 >= self.final_eval >= mark_price * 0.995:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.NEUTRAL)
        elif self.final_eval < mark_price * 0.995:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.SHORT)
        else:
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.VERY_SHORT)


class PriceSignalTradingMode(trading_modes.AbstractTradingMode):
    MODE_PRODUCER_CLASSES = [PriceSignalTradingModeProducer]
    MODE_CONSUMER_CLASSES = [PriceSignalTradingModeConsumer]

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.load_config()
