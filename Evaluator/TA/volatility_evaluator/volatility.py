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
import tulipy

import octobot_commons.constants as commons_constants
import octobot_commons.data_util as data_util
import octobot_evaluators.evaluators as evaluators
import octobot_evaluators.util as evaluators_util
import octobot_tentacles_manager.api as tentacles_manager_api
import octobot_trading.api as trading_api


class StochasticRSIVolatilityEvaluator(evaluators.TAEvaluator):
    STOCHRSI_PERIOD = "period"
    HIGH_LEVEL = "high_level"
    LOW_LEVEL = "low_level"
    TULIPY_INDICATOR_MULTIPLICATOR = 100

    def __init__(self, tentacles_setup_config):
        super().__init__(tentacles_setup_config)
        self.evaluator_config = tentacles_manager_api.get_tentacle_config(self.tentacles_setup_config, self.__class__)
        self.period = self.evaluator_config[self.STOCHRSI_PERIOD]

    async def ohlcv_callback(self, exchange: str, exchange_id: str,
                             cryptocurrency: str, symbol: str, time_frame, candle, inc_in_construction_data):
        candle_data = trading_api.get_symbol_close_candles(self.get_exchange_symbol_data(exchange, exchange_id, symbol),
                                                           time_frame,
                                                           include_in_construction=inc_in_construction_data)
        await self.evaluate(cryptocurrency, symbol, time_frame, candle_data, candle)

    async def evaluate(self, cryptocurrency, symbol, time_frame, candle_data, candle):
        try:
            if len(candle_data) >= self.period * 2:
                stochrsi_value = tulipy.stochrsi(data_util.drop_nan(candle_data), self.period)[-1]

                if stochrsi_value * self.TULIPY_INDICATOR_MULTIPLICATOR >= self.evaluator_config[self.HIGH_LEVEL]:
                    self.eval_note = 1
                elif stochrsi_value * self.TULIPY_INDICATOR_MULTIPLICATOR <= self.evaluator_config[self.LOW_LEVEL]:
                    self.eval_note = -1
                else:
                    self.eval_note = stochrsi_value - 0.5
        except tulipy.lib.InvalidOptionError as e:
            self.logger.debug(f"Error when computing StochRSI: {e}")
            self.logger.exception(e, False)
            self.eval_note = commons_constants.START_PENDING_EVAL_NOTE
        await self.evaluation_completed(cryptocurrency, symbol, time_frame,
                                        eval_time=evaluators_util.get_eval_time(full_candle=candle,
                                                                                time_frame=time_frame))

class CHOPVolatilityEvaluator(evaluators.TAEvaluator):
    CHOP_PERIOD = 14
    CHOP_THRESHOLD = 45
    RSI_UP_THRESHOLD = 70
    RSI_DOWN_THRESHOLD = 45
    RSI_PERIOD = 14

    def __init__(self, tentacles_setup_config):
        super().__init__(tentacles_setup_config)
        self.period = self.CHOP_PERIOD
        self.evaluator_config = tentacles_manager_api.get_tentacle_config(self.tentacles_setup_config, self.__class__)

    async def ohlcv_callback(self, exchange: str, exchange_id: str,
                             cryptocurrency: str, symbol: str, time_frame, candle, inc_in_construction_data):
        close_candle_data = trading_api.get_symbol_close_candles(
            self.get_exchange_symbol_data(exchange, exchange_id, symbol), time_frame)
        high_candle_data = trading_api.get_symbol_high_candles(
            self.get_exchange_symbol_data(exchange, exchange_id, symbol), time_frame)
        low_candle_data = trading_api.get_symbol_low_candles(
            self.get_exchange_symbol_data(exchange, exchange_id, symbol), time_frame)
        await self.evaluate(cryptocurrency, symbol, time_frame,
                            candle_data=(close_candle_data, high_candle_data, low_candle_data),
                            candle=candle)

    def _get_chop_index(self, atr_values, close_candle_data, high_candle_data, low_candle_data):
        chop_values = []
        for i in range(len(close_candle_data)):
            if i > self.period * 2:
                nmrt = np.log10(np.sum(atr_values[i - self.period:i]) /
                                (max(high_candle_data[i - self.period:i]) - min(low_candle_data[i - self.period:i])))
                dnmnt = np.log10(self.period)
                chop_values.append(round(100 * nmrt / dnmnt))
        return chop_values

    async def evaluate(self, cryptocurrency, symbol, time_frame, candle_data, candle):
        try:
            close_candle_data, high_candle_data, low_candle_data = candle_data
            if len(close_candle_data) >= self.period * 2:
                atr_values = tulipy.atr(high_candle_data, low_candle_data, close_candle_data, self.period)
                chop_values = self._get_chop_index(atr_values, close_candle_data, high_candle_data, low_candle_data)
                if chop_values:
                    rsi_values = tulipy.rsi(close_candle_data, period=self.RSI_PERIOD)
                    last_chop_value = chop_values[-1]
                    last_rsi_value = rsi_values[-1]
                    if last_chop_value < self.CHOP_THRESHOLD:
                        if last_rsi_value > self.RSI_UP_THRESHOLD:
                            self.eval_note = 1
                        elif last_rsi_value < self.RSI_DOWN_THRESHOLD:
                            self.eval_note = -1
        except tulipy.lib.InvalidOptionError as e:
            self.logger.debug(f"Error when computing Chop: {e}")
            self.eval_note = commons_constants.START_PENDING_EVAL_NOTE
        await self.evaluation_completed(cryptocurrency, symbol, time_frame,
                                        eval_time=evaluators_util.get_eval_time(full_candle=candle,
                                                                                time_frame=time_frame))

