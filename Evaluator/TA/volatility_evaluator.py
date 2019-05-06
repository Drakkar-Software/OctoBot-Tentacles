"""
OctoBot Tentacle

$tentacle_description: {
    "name": "volatility_evaluator",
    "type": "Evaluator",
    "subtype": "TA",
    "version": "1.1.1",
    "config_files": ["StochasticRSIVolatilityEvaluator.json"],
    "config_schema_files": ["StochasticRSIVolatilityEvaluator_schema.json"],
    "requirements": []
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
import tulipy

from config import PriceIndexes, START_PENDING_EVAL_NOTE
from evaluator.TA.TA_evaluator import VolatilityEvaluator


class StochasticRSIVolatilityEvaluator(VolatilityEvaluator):
    DESCRIPTION = "Uses the Stochastic RSI as a volatilty evaluator to help identify trends. " \
                  "When found, evaluates -1 to 1 according to the strength of the trend."
    
    STOCHRSI_PERIOD = "period"
    HIGH_LEVEL = "high_level"
    LOW_LEVEL = "low_level"
    TULIPY_INDICATOR_MULTIPLICATOR = 100

    def __init__(self):
        super().__init__()
        self.evaluator_config = self.get_specific_config()

    async def eval_impl(self):
        stochrsi_value = tulipy.stochrsi(self.data[PriceIndexes.IND_PRICE_CLOSE.value],
                                         self.evaluator_config[self.STOCHRSI_PERIOD])[-1]

        if stochrsi_value * self.TULIPY_INDICATOR_MULTIPLICATOR >= self.evaluator_config[self.HIGH_LEVEL]:
            self.eval_note = 1
        elif stochrsi_value * self.TULIPY_INDICATOR_MULTIPLICATOR <= self.evaluator_config[self.LOW_LEVEL]:
            self.eval_note = -1
        else:
            self.eval_note = stochrsi_value - 0.5
