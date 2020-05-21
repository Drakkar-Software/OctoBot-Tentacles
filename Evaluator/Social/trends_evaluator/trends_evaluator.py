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

from octobot_commons.constants import CONFIG_REFRESH_RATE
from octobot_commons.tentacles_management.class_inspector import get_single_deepest_child_class
from octobot_evaluators.evaluator.social_evaluator import SocialEvaluator
from octobot_services.constants import FEED_METADATA, CONFIG_TREND_HISTORY_TIME, CONFIG_TREND_TOPICS, CONFIG_TREND
from tentacles.Evaluator.Util.statistics_analysis import StatisticAnalysis
from tentacles.Services.Services_feeds import GoogleServiceFeed
from tentacles.Services.Services_feeds.google_service_feed.google_service_feed import TrendTopic


class GoogleTrendsEvaluator(SocialEvaluator):

    SERVICE_FEED_CLASS = GoogleServiceFeed

    def __init__(self):
        SocialEvaluator.__init__(self)
        self.stats_analyser = None

    @classmethod
    def get_is_cryptocurrencies_wildcard(cls) -> bool:
        """
        :return: True if the evaluator is not cryptocurrency dependant else False
        """
        return False

    @classmethod
    def get_is_cryptocurrency_name_wildcard(cls) -> bool:
        """
        :return: True if the evaluator is not cryptocurrency name dependant else False
        """
        return False

    async def _feed_callback(self, data):
        if self._is_interested_by_this_notification(data[FEED_METADATA]):
            trend = numpy.array([d["data"] for d in data[CONFIG_TREND]])
            # compute bollinger bands
            self.eval_note = self.stats_analyser.analyse_recent_trend_changes(trend, numpy.sqrt)
            await self.evaluation_completed(self.cryptocurrency, eval_time=self.get_current_exchange_time())

    def _is_interested_by_this_notification(self, notification_description):
        return self.cryptocurrency_name in notification_description

    def _build_trend_topics(self):
        trend_time_frame = f"today {str(self.specific_config[CONFIG_TREND_HISTORY_TIME])}-m"
        return [
            TrendTopic(self.specific_config[CONFIG_REFRESH_RATE],
                       [self.cryptocurrency_name],
                       time_frame=trend_time_frame)
        ]

    async def prepare(self):
        self.specific_config[CONFIG_TREND_TOPICS] = self._build_trend_topics()
        self.stats_analyser = get_single_deepest_child_class(StatisticAnalysis)()
