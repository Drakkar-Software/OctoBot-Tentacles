"""
OctoBot Tentacle

$tentacle_description: {
    "name": "stats_evaluator",
    "type": "Evaluator",
    "subtype": "Social",
    "version": "1.1.1",
    "requirements": [],
    "config_files": ["GoogleTrendStatsEvaluator.json"],
    "config_schema_files": ["GoogleTrendStatsEvaluator_schema.json"]

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

import numpy

from simplifiedpytrends.exceptions import ResponseError
from simplifiedpytrends.request import TrendReq

from config import *
from evaluator.Social.social_evaluator import StatsSocialEvaluator
from evaluator.Util import StatisticAnalysis
from evaluator.Util.advanced_manager import AdvancedManager


class GoogleTrendStatsEvaluator(StatsSocialEvaluator):
    DESCRIPTION = "Analyses the trend of the given currencies using their names to compute the evaluation. " \
                  "Never triggers strategies re-evaluations, acts as a background evaluator."

    def __init__(self):
        super().__init__()
        self.simplified_pytrends = None

    # Use simmplifiedpytrends lib (https://github.com/Drakkar-Software/simplifiedpytrends)
    # https://github.com/Drakkar-Software/simplifiedpytrends/blob/master/examples/example.py
    def get_data(self):
        self.simplified_pytrends = TrendReq(hl='en-US', tz=0)
        # self.simmplifiedpytrends.GENERAL_URL = "https://trends.google.com/trends/explore"
        # self.symbol
        key_words = [self.symbol]
        try:
            # looks like only 1 and 3 months are working ...
            time_frame = f"today {str(self.social_config[STATS_EVALUATOR_HISTORY_TIME])}-m"
            # Careful, apparently hourly rate limit is low
            self.simplified_pytrends.build_payload(kw_list=key_words, cat=0, timeframe=time_frame, geo='', gprop='')
        except ResponseError as e:
            self.logger.warn(str(e))

    async def eval_impl(self):
        interest_over_time = self.simplified_pytrends.interest_over_time()
        trend = numpy.array([d["data"] for d in interest_over_time])

        # compute bollinger bands
        self.eval_note = AdvancedManager.get_class(self.config, StatisticAnalysis).analyse_recent_trend_changes(
            trend, numpy.sqrt)

    # check if history is not too high
    def load_config(self):
        super(GoogleTrendStatsEvaluator, self).load_config()
        if self.social_config[STATS_EVALUATOR_HISTORY_TIME] > STATS_EVALUATOR_MAX_HISTORY_TIME:
            self.social_config[STATS_EVALUATOR_HISTORY_TIME] = STATS_EVALUATOR_MAX_HISTORY_TIME

    def set_default_config(self):
        self.social_config = {
            CONFIG_REFRESH_RATE: 3600,
            STATS_EVALUATOR_HISTORY_TIME: 3
        }

    # not standalone task
    async def start_task(self):
        pass
