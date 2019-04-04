"""
OctoBot Tentacle

$tentacle_description: {
    "package_name": "OctoBot-Tentacles",
    "name": "crossing_analysis",
    "type": "Evaluator",
    "subtype": "Util",
    "version": "1.1.0",
    "requirements": []
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
from enum import Enum

import pandas as pd
import numpy as np

from evaluator.Util import AbstractUtil


class CrossingType(Enum):
    ABOVE = "above"
    BELOW = "below"


class CrossingAnalysis(AbstractUtil):
    @staticmethod
    def crossed(series1, series2, direction=None) -> pd.Series:
        below = None
        above = None

        if isinstance(series1, np.ndarray):
            series1 = pd.Series(series1)

        if isinstance(series2, (float, int, np.ndarray)):
            series2 = pd.Series(index=series1.index, data=series2)

        if direction is None or direction == CrossingType.ABOVE:
            above = pd.Series((series1 > series2) & (
                    series1.shift() <= series2.shift()))

        if direction is None or direction == CrossingType.BELOW:
            below = pd.Series((series1 < series2) & (
                    series1.shift() >= series2.shift()))

        if direction is None:
            return above or below

        return above if direction == CrossingType.ABOVE else below

    @staticmethod
    def crossed_above(series1, series2):
        return CrossingAnalysis.crossed(series1, series2, CrossingType.ABOVE)

    @staticmethod
    def crossed_below(series1, series2):
        return CrossingAnalysis.crossed(series1, series2, CrossingType.BELOW)
