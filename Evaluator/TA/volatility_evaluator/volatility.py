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

    def __init__(self):
        super().__init__()
        self.evaluator_config = tentacles_manager_api.get_tentacle_config(self.__class__)
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
