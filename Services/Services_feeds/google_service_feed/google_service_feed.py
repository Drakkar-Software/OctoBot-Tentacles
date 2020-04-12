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
import asyncio
from time import time

import aiohttp

from simplifiedpytrends.exceptions import ResponseError
from simplifiedpytrends.request import TrendReq

from octobot_services.channel.abstract_service_feed import AbstractServiceFeedChannel
from octobot_services.constants import FEED_METADATA, CONFIG_TREND_DESCRIPTION, CONFIG_TREND, CONFIG_TREND_TOPICS
from octobot_services.service_feeds.abstract_service_feed import AbstractServiceFeed
from tentacles.Services.Services_bases import GoogleService


class GoogleServiceFeedChannel(AbstractServiceFeedChannel):
    pass


class TrendTopic:
    def __init__(self, refresh_time, keywords, category=0, time_frame="today 5-y", geo="", grop=""):
        self.keywords = keywords
        self.category = category
        self.time_frame = time_frame
        self.geo = geo
        self.grop = grop
        self.refresh_time = refresh_time
        self.next_refresh = time()

    def __str__(self):
        return f"{self.keywords} {self.time_frame}"


class GoogleServiceFeed(AbstractServiceFeed):
    FEED_CHANNEL = GoogleServiceFeedChannel
    REQUIRED_SERVICE = GoogleService

    def __init__(self, config, main_async_loop, bot_id):
        super().__init__(config, main_async_loop, bot_id)
        self.trends_req_builder = None
        self.trends_topics = []

    def _initialize(self):
        # if the url changes (google sometimes changes it), use the following line:
        # trends_req.GENERAL_URL = "https://trends.google.com/trends/explore"
        self.trends_req_builder = TrendReq(hl='en-US', tz=0)

    # merge new config into existing config
    def update_feed_config(self, config):
        self.trends_topics.extend(topic
                                  for topic in config[CONFIG_TREND_TOPICS]
                                  if topic not in self.trends_topics)

    def _something_to_watch(self):
        return bool(self.trends_topics)

    def _get_sleep_time_before_next_wakeup(self):
        closest_wakeup = min(topic.next_refresh for topic in self.trends_topics)
        return max(0, closest_wakeup - time())

    async def _get_topic_trend(self, topic):
        await self.trends_req_builder.async_build_payload(kw_list=topic.keywords,
                                                          cat=topic.category,
                                                          timeframe=topic.time_frame,
                                                          geo=topic.geo,
                                                          gprop=topic.grop)
        topic.next_refresh = time() + topic.refresh_time
        return await self.trends_req_builder.async_interest_over_time()

    async def _push_update_and_wait(self):
        for topic in self.trends_topics:
            if time() >= topic.next_refresh:
                interest_over_time = await self._get_topic_trend(topic)
                if interest_over_time:
                    await self._async_notify_consumers(
                        {
                             FEED_METADATA: f"{topic};{interest_over_time}",
                             CONFIG_TREND: interest_over_time,
                             CONFIG_TREND_DESCRIPTION: topic
                        }
                    )
        await asyncio.sleep(self._get_sleep_time_before_next_wakeup())

    async def _update_loop(self):
        async with aiohttp.ClientSession() as session:
            self.trends_req_builder.aiohttp_session = session
            while not self.should_stop:
                try:
                    await self._push_update_and_wait()
                except ResponseError as e:
                    self.logger.exception(e, True, f"Error when fetching Google trends feed: {e}")
                    self.should_stop = True
                except Exception as e:
                    self.logger.exception(e, True, f"Error when receiving Google feed: ({e})")
                    self.should_stop = True
            return False

    async def _start_service_feed(self):
        try:
            asyncio.create_task(self._update_loop())
        except Exception as e:
            self.logger.exception(e, True, f"Error when initializing Google trends feed: {e}")
            return False
        return True
