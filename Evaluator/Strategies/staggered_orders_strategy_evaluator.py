"""
OctoBot Tentacle

$tentacle_description: {
    "name": "staggered_orders_strategy_evaluator",
    "type": "Evaluator",
    "subtype": "Strategies",
    "version": "1.1.0",
    "requirements": ["price_refresher_evaluator"],
    "config_files": ["StaggeredOrdersStrategiesEvaluator.json"]
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

from typing import Dict

from config import EvaluatorMatrixTypes

from evaluator.Strategies import StaggeredStrategiesEvaluator
from tentacles.Evaluator.RealTime import PeriodicPriceTickerEvaluator


class StaggeredOrdersStrategiesEvaluator(StaggeredStrategiesEvaluator):

    DESCRIPTION = "StaggeredOrdersStrategiesEvaluator is simply forwarding a price refresh to the associated " \
                  "trading mode. Configuration is made in trading mode configuration file."

    PRICE_REFRESHER_CLASS_NAME = PeriodicPriceTickerEvaluator.get_name()

    @staticmethod
    def get_eval_type():
        return Dict[str, float]

    async def eval_impl(self) -> None:
        self.eval_note = \
            self.matrix[EvaluatorMatrixTypes.REAL_TIME][StaggeredOrdersStrategiesEvaluator.PRICE_REFRESHER_CLASS_NAME]
