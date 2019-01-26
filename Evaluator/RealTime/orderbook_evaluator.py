"""
OctoBot Tentacle

$tentacle_description: {
    "name": "orderbook_evaluator",
    "type": "Evaluator",
    "subtype": "RealTime",
    "version": "1.1.0",
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

from config import CONFIG_TIME_FRAME, TimeFrames, CONFIG_REFRESH_RATE
from evaluator.RealTime import RealTimeTAEvaluator


class WhalesOrderBookEvaluator(RealTimeTAEvaluator):
    def __init__(self, exchange_inst, symbol):
        super().__init__(exchange_inst, symbol)

    def _refresh_data(self):
        pass

    async def eval_impl(self):
        pass

    def set_default_config(self):
        self.specific_config = {
            CONFIG_REFRESH_RATE: 5,
            CONFIG_TIME_FRAME: TimeFrames.FIVE_MINUTES
        }

    def _should_eval(self):
        pass
