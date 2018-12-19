"""
OctoBot Tentacle

$tentacle_description: {
    "name": "stats_evaluator",
    "type": "Evaluator",
    "subtype": "Social",
    "version": "1.0.0",
    "requirements": [],
    "config_files": ["GoogleTrendStatsEvaluator.json"]
}
"""

import numpy

from pytrends.exceptions import ResponseError
from pytrends.request import TrendReq

from config import *
from evaluator.Social.social_evaluator import StatsSocialEvaluator
from evaluator.Util import StatisticAnalysis
from evaluator.Util.advanced_manager import AdvancedManager


class GoogleTrendStatsEvaluator(StatsSocialEvaluator):
    def __init__(self):
        super().__init__()
        self.pytrends = None
        self.is_threaded = False

    # Use pytrends lib (https://github.com/GeneralMills/pytrends)
    # https://github.com/GeneralMills/pytrends/blob/master/examples/example.py
    def get_data(self):
        self.pytrends = TrendReq(hl='en-US', tz=0)
        # self.pytrends.GENERAL_URL = "https://trends.google.com/trends/explore"
        # self.symbol
        key_words = [self.symbol]
        try:
            # looks like only 1 and 3 months are working ...
            time_frame = f"today {str(self.social_config[STATS_EVALUATOR_HISTORY_TIME])}-m"
            # Careful, apparently hourly rate limit is low
            self.pytrends.build_payload(kw_list=key_words, cat=0, timeframe=time_frame, geo='', gprop='')
        except ResponseError as e:
            self.logger.warn(str(e))

    def eval_impl(self):
        interest_over_time_df = self.pytrends.interest_over_time()

        # compute bollinger bands
        self.eval_note = AdvancedManager.get_class(self.config, StatisticAnalysis).analyse_recent_trend_changes(
            interest_over_time_df[self.symbol].astype('float64').values, numpy.sqrt)

    def run(self):
        pass

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
