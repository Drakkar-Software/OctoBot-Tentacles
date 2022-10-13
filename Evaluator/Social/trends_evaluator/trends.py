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
import octobot_commons.enums as commons_enums
import octobot_commons.tentacles_management as tentacles_management
import octobot_evaluators.evaluators as evaluators
import octobot_services.constants as services_constants
import tentacles.Evaluator.Util as EvaluatorUtil
import tentacles.Services.Services_feeds as Services_feeds


class GoogleTrendsEvaluator(evaluators.SocialEvaluator):
    SERVICE_FEED_CLASS = Services_feeds.GoogleServiceFeed

    def __init__(self, tentacles_setup_config):
        evaluators.SocialEvaluator.__init__(self, tentacles_setup_config)
        self.stats_analyser = None
        self.refresh_rate_seconds = 86400
        self.relevant_history_months = 3

    def init_user_inputs(self, inputs: dict) -> None:
        self.refresh_rate_seconds = self.UI.user_input(commons_constants.CONFIG_REFRESH_RATE,
                                                    commons_enums.UserInputTypes.INT,
                                                    self.refresh_rate_seconds, inputs, min_val=1,
                                                    title="Seconds between each re-evaluation "
                                                          "(do not set too low because google has a low "
                                                          "monthly rate limit).")
        self.relevant_history_months = self.UI.user_input(services_constants.CONFIG_TREND_HISTORY_TIME,
                                                       commons_enums.UserInputTypes.INT,
                                                       self.relevant_history_months, inputs, min_val=3, max_val=3,
                                                       title="Number of months to look into to compute the trend "
                                                             "evaluation (for now works only with 3).")
        self.feed_config[services_constants.CONFIG_TREND_TOPICS] = self._build_trend_topics()

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
        trend_time_frame = f"today {self.relevant_history_months}-m"
        return [
            Services_feeds.TrendTopic(self.refresh_rate_seconds,
                                      [self.cryptocurrency_name],
                                      time_frame=trend_time_frame)
        ]

    async def prepare(self):
        self.stats_analyser = tentacles_management.get_single_deepest_child_class(EvaluatorUtil.StatisticAnalysis)()
