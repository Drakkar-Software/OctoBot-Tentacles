"""
OctoBot Tentacle

$tentacle_description: {
    "name": "market_making_startegy_evaluator",
    "type": "Evaluator",
    "subtype": "Strategies",
    "version": "1.1.0",
    "requirements": ["instant_fluctuations_evaluator"],
    "config_files": ["SimpleMarketMakingStrategiesEvaluator.json"],
    "tests":["test_market_making_strategies_evaluator"]
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

from config import EvaluatorMatrixTypes
from evaluator.Strategies import MarketMakingStrategiesEvaluator
from tentacles.Evaluator.RealTime import InstantMarketMakingEvaluator


class SimpleMarketMakingStrategiesEvaluator(MarketMakingStrategiesEvaluator):
    DESCRIPTION = "SimpleMarketMakingStrategiesEvaluator uses to pass up to date bid and ask price to MM TM"

    INSTANT_MM_CLASS_NAME = InstantMarketMakingEvaluator.get_name()

    async def eval_impl(self) -> None:
        self.finalize()

    def finalize(self):
        self.eval_note = self.matrix[EvaluatorMatrixTypes.REAL_TIME][
            SimpleMarketMakingStrategiesEvaluator.INSTANT_MM_CLASS_NAME]
