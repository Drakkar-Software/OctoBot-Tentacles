"""
OctoBot Tentacle

$tentacle_description: {
    "name": "news_evaluator",
    "type": "Evaluator",
    "subtype": "Social",
    "version": "1.1.1",
    "requirements": [],
    "config_files": ["TwitterNewsEvaluator.json"],
    "config_schema_files": ["TwitterNewsEvaluator_schema.json"]
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

from config import CONFIG_CRYPTO_CURRENCIES, CONFIG_CRYPTO_CURRENCY, MINUTE_TO_SECONDS, CONFIG_CATEGORY_SERVICES, \
CONFIG_TWITTER, CONFIG_SERVICE_INSTANCE, CONFIG_TWEET, CONFIG_TWEET_DESCRIPTION, START_PENDING_EVAL_NOTE, \
    CONFIG_TWITTERS_ACCOUNTS, CONFIG_TWITTERS_HASHTAGS
from evaluator.Social.social_evaluator import NewsSocialEvaluator
from evaluator.Util import TextAnalysis
from evaluator.Util.advanced_manager import AdvancedManager
from services.Dispatchers.twitter_dispatcher import TwitterDispatcher
from services.Dispatchers.abstract_dispatcher import DispatcherAbstractClient
from tools.decoding_encoding import DecoderEncoder


class TwitterNewsEvaluator(NewsSocialEvaluator, DispatcherAbstractClient):
    DESCRIPTION = "Triggers when a new tweet appears from the Twitter accounts in TwitterNewsEvaluator.json. " \
                  "If the evaluation a new tweet is significant enough, triggers strategies re-evaluation. Otherwise " \
                  "acts as a background evaluator."

    # max time to live for a pulse is 10min
    _EVAL_MAX_TIME_TO_LIVE = 10 * MINUTE_TO_SECONDS
    # absolute value above which a notification is triggered
    _EVAL_NOTIFICATION_THRESHOLD = 0.6

    def __init__(self):
        NewsSocialEvaluator.__init__(self)
        DispatcherAbstractClient.__init__(self)
        self.count = 0
        self.symbol = ""
        self.sentiment_analyser = None
        self.is_self_refreshing = True

    def set_dispatcher(self, dispatcher):
        super().set_dispatcher(dispatcher)
        self.dispatcher.update_social_config(self.social_config)

    @staticmethod
    def get_dispatcher_class():
        return TwitterDispatcher

    def get_twitter_service(self):
        return self.config[CONFIG_CATEGORY_SERVICES][CONFIG_TWITTER][CONFIG_SERVICE_INSTANCE]

    def _print_tweet(self, tweet_text, tweet_url, note, count=""):
        self.logger.debug(f"Current note : {note} | {count} : {self.symbol} : Link: {tweet_url} Text : "
                          f"{DecoderEncoder.encode_into_bytes(tweet_text)}")

    async def receive_notification_data(self, data):
        self.count += 1
        note = self.get_tweet_sentiment(data[CONFIG_TWEET], data[CONFIG_TWEET_DESCRIPTION])
        tweet_url = f"https://twitter.com/ProducToken/status/{data['tweet']['id']}"
        if note != START_PENDING_EVAL_NOTE:
            self._print_tweet(data[CONFIG_TWEET_DESCRIPTION], tweet_url, note, str(self.count))
        await self._check_eval_note(note)

    # only set eval note when something is happening
    async def _check_eval_note(self, note):
        if note != START_PENDING_EVAL_NOTE:
            if abs(note) > self._EVAL_NOTIFICATION_THRESHOLD:
                self.eval_note = note
                self.save_evaluation_expiration_time(self._compute_notification_time_to_live(self.eval_note))
                await self.notify_evaluator_task_managers(self.get_name())

    @staticmethod
    def _compute_notification_time_to_live(evaluation):
        return TwitterNewsEvaluator._EVAL_MAX_TIME_TO_LIVE * abs(evaluation)

    def get_tweet_sentiment(self, tweet, tweet_text, is_a_quote=False):
        try:
            if is_a_quote:
                return -1 * self.sentiment_analyser.analyse(tweet_text)
            else:
                stupid_useless_name = "########"
                author_screen_name = tweet['user']['screen_name'] if "screen_name" in tweet['user'] \
                    else stupid_useless_name
                author_name = tweet['user']['name'] if "name" in tweet['user'] else stupid_useless_name
                if self.social_config[CONFIG_TWITTERS_ACCOUNTS]:
                    if author_screen_name in self.social_config[CONFIG_TWITTERS_ACCOUNTS][self.symbol] \
                       or author_name in self.social_config[CONFIG_TWITTERS_ACCOUNTS][self.symbol]:
                        return -1 * self.sentiment_analyser.analyse(tweet_text)
        except KeyError:
            pass

        # ignore # for the moment (too much of bullshit)
        return START_PENDING_EVAL_NOTE

    def is_interested_by_this_notification(self, notification_description):
        # true if in twitter accounts
        if self.social_config[CONFIG_TWITTERS_ACCOUNTS]:
            for account in self.social_config[CONFIG_TWITTERS_ACCOUNTS][self.symbol]:
                if account.lower() in notification_description:
                    return True

        # false if it's a RT of an unfollowed account
        if notification_description.startswith("rt"):
            return False

        # true if contains symbol
        if self.symbol.lower() in notification_description:
            return True

        # true if in hashtags
        if self.social_config[CONFIG_TWITTERS_HASHTAGS]:
            for hashtags in self.social_config[CONFIG_TWITTERS_HASHTAGS][self.symbol]:
                if hashtags.lower() in notification_description:
                    return True
            return False

    def _get_config_elements(self, key):
        if CONFIG_CRYPTO_CURRENCIES in self.social_config and self.social_config[CONFIG_CRYPTO_CURRENCIES]:
            return {cc[CONFIG_CRYPTO_CURRENCY]: cc[key] for cc in self.social_config[CONFIG_CRYPTO_CURRENCIES]
                    if cc[CONFIG_CRYPTO_CURRENCY] == self.symbol}
        return {}

    def _format_config(self):
        # remove other symbols data to avoid unnecessary tweets
        self.social_config[CONFIG_TWITTERS_ACCOUNTS] = self._get_config_elements(CONFIG_TWITTERS_ACCOUNTS)
        self.social_config[CONFIG_TWITTERS_HASHTAGS] = self._get_config_elements(CONFIG_TWITTERS_HASHTAGS)

    def prepare(self):
        self._format_config()
        self.sentiment_analyser = AdvancedManager.get_util_instance(self.config, TextAnalysis)

    def get_data(self):
        pass

    async def eval_impl(self):
        pass

    # not standalone task
    async def start_task(self):
        pass
