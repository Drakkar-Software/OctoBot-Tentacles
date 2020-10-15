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

import octobot_commons.constants as commons_constants
import octobot_commons.tentacles_management as tentacles_management
import octobot_evaluators.evaluators as evaluators
import octobot_services.constants as services_constants
import tentacles.Evaluator.Util as EvaluatorUtil
import tentacles.Services.Services_feeds as Services_feeds


class GoogleTrendsEvaluator(evaluators.SocialEvaluator):
    SERVICE_FEED_CLASS = Services_feeds.GoogleServiceFeed

    def __init__(self):
        evaluators.SocialEvaluator.__init__(self)
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
        if self._is_interested_by_this_notification(data[services_constants.FEED_METADATA]):
            trend = numpy.array([d["data"] for d in data[services_constants.CONFIG_TREND]])
            # compute bollinger bands
            self.eval_note = self.stats_analyser.analyse_recent_trend_changes(trend, numpy.sqrt)
            await self.evaluation_completed(self.cryptocurrency, eval_time=self.get_current_exchange_time())

    def _is_interested_by_this_notification(self, notification_description):
        return self.cryptocurrency_name in notification_description

    def _build_trend_topics(self):
        trend_time_frame = f"today {str(self.specific_config[services_constants.CONFIG_TREND_HISTORY_TIME])}-m"
        return [
            Services_feeds.TrendTopic(self.specific_config[commons_constants.CONFIG_REFRESH_RATE],
                                      [self.cryptocurrency_name],
                                      time_frame=trend_time_frame)
        ]

    async def prepare(self):
        self.specific_config[services_constants.CONFIG_TREND_TOPICS] = self._build_trend_topics()
        self.stats_analyser = tentacles_management.get_single_deepest_child_class(EvaluatorUtil.StatisticAnalysis)()
