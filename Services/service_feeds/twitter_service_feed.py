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
import threading
import twitter

from octobot_services.channel.abstract_service_feed import AbstractServiceFeedChannel
from octobot_services.constants import CONFIG_TWITTERS_ACCOUNTS, CONFIG_TWITTERS_HASHTAGS, CONFIG_TWEET, \
    CONFIG_TWEET_DESCRIPTION, FEED_METADATA
from octobot_services.service_feeds.abstract_service_feed import AbstractServiceFeed
from tentacles.Services import TwitterService


class TwitterServiceFeedChannel(AbstractServiceFeedChannel):
    pass


class TwitterServiceFeed(AbstractServiceFeed, threading.Thread):
    FEED_CHANNEL = TwitterServiceFeedChannel
    REQUIRED_SERVICE = TwitterService

    def __init__(self, config, main_async_loop):
        super().__init__(config, main_async_loop)
        threading.Thread.__init__(self)
        self.user_ids = []
        self.hashtags = []
        self.counter = 0

    def start(self) -> None:
        threading.Thread.start(self)

    # merge new config into existing config
    def update_social_config(self, config):
        if CONFIG_TWITTERS_ACCOUNTS in self.feed_config:
            self.feed_config[CONFIG_TWITTERS_ACCOUNTS] = {**self.feed_config[CONFIG_TWITTERS_ACCOUNTS],
                                                          **config[CONFIG_TWITTERS_ACCOUNTS]}
        else:
            self.feed_config[CONFIG_TWITTERS_ACCOUNTS] = config[CONFIG_TWITTERS_ACCOUNTS]

        if CONFIG_TWITTERS_HASHTAGS in self.feed_config:
            self.feed_config[CONFIG_TWITTERS_HASHTAGS] = {**self.feed_config[CONFIG_TWITTERS_HASHTAGS],
                                                          **config[CONFIG_TWITTERS_HASHTAGS]}
        else:
            self.feed_config[CONFIG_TWITTERS_HASHTAGS] = config[CONFIG_TWITTERS_HASHTAGS]

    def _init_users_accounts(self):
        tempo_added_accounts = []
        for symbol in self.feed_config[CONFIG_TWITTERS_ACCOUNTS]:
            for account in self.feed_config[CONFIG_TWITTERS_ACCOUNTS][symbol]:
                if account not in tempo_added_accounts:
                    tempo_added_accounts.append(account)
                    try:
                        self.user_ids.append(str(self.service.get_user_id(account)))
                    except twitter.TwitterError as e:
                        self.logger.error(account + " : " + str(e))

    def _init_hashtags(self):
        for symbol in self.feed_config[CONFIG_TWITTERS_HASHTAGS]:
            for hashtag in self.feed_config[CONFIG_TWITTERS_HASHTAGS][symbol]:
                if hashtag not in self.hashtags:
                    self.hashtags.append(hashtag)

    def _initialize(self):
        if not self.user_ids:
            self._init_users_accounts()
        if not self.hashtags:
            self._init_hashtags()

    def _something_to_watch(self):
        return (CONFIG_TWITTERS_HASHTAGS in self.feed_config
                and self.feed_config[CONFIG_TWITTERS_HASHTAGS]) \
               or (CONFIG_TWITTERS_ACCOUNTS in self.feed_config
                   and self.feed_config[CONFIG_TWITTERS_ACCOUNTS])

    def _start_listener(self):
        for tweet in self.service.get_endpoint().GetStreamFilter(follow=self.user_ids,
                                                                 track=self.hashtags,
                                                                 stall_warnings=True):
            self.counter += 1
            string_tweet = self.service.get_tweet_text(tweet)
            if string_tweet:
                tweet_desc = str(tweet).lower()
                self._notify_consumers(
                    {
                         FEED_METADATA: tweet_desc,
                         CONFIG_TWEET: tweet,
                         CONFIG_TWEET_DESCRIPTION: string_tweet.lower()
                    }
                )

    def _start_service_feed(self):
        while not self.should_stop:
            try:
                self._start_listener()
            except twitter.error.TwitterError as e:
                self.logger.error(f"Error when receiving Twitter feed: {e.message} ({e})")
                self.logger.exception(e)
                self.keep_running = False
            except Exception as e:
                self.logger.error(f"Error when receiving Twitter feed ({e}) ")
                self.logger.exception(e)
                self.keep_running = False
        return False
