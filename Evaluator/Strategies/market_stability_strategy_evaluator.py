"""
OctoBot Tentacle

$tentacle_description: {
    "name": "market_stability_strategy_evaluator",
    "type": "Evaluator",
    "subtype": "Strategies",
    "version": "1.1.0",
    "requirements": ["instant_fluctuations_evaluator"],
    "config_files": ["MarketStabilityStrategiesEvaluator.json"]
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

from config import EvaluatorMatrixTypes

from evaluator.Strategies import MixedStrategiesEvaluator
from tentacles.Evaluator.RealTime import InstantVolatilityEvaluator


# WARNING : THIS STRATEGY MUST BE USED WITH A WEBSOCKET
class MarketStabilityStrategiesEvaluator(MixedStrategiesEvaluator):
    def __init__(self):
        super().__init__()

    async def eval_impl(self) -> None:
        matrix_note = self.matrix[EvaluatorMatrixTypes.REAL_TIME][InstantVolatilityEvaluator.get_name()]
        self.eval_note = matrix_note
