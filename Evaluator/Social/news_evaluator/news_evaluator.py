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

from octobot_commons.constants import CONFIG_CRYPTO_CURRENCIES, CONFIG_CRYPTO_CURRENCY, MINUTE_TO_SECONDS, \
    START_PENDING_EVAL_NOTE
from octobot_commons.tentacles_management.advanced_manager import get_single_deepest_child_class
from octobot_services.constants import CONFIG_TWITTERS_ACCOUNTS, CONFIG_TWITTERS_HASHTAGS, CONFIG_TWEET, \
    CONFIG_TWEET_DESCRIPTION
from octobot_evaluators.evaluator.social_evaluator import SocialEvaluator
from tentacles.Evaluator.Util.text_analysis import TextAnalysis
from tentacles.Services.Services_feeds import TwitterServiceFeed


class TwitterNewsEvaluator(SocialEvaluator):

    SERVICE_FEED_CLASS = TwitterServiceFeed

    # max time to live for a pulse is 10min
    _EVAL_MAX_TIME_TO_LIVE = 10 * MINUTE_TO_SECONDS
    # absolute value above which a notification is triggered
    _EVAL_NOTIFICATION_THRESHOLD = 0.6

    def __init__(self):
        super().__init__()
        self.count = 0
        self.sentiment_analyser = None
        self.is_self_refreshing = True

    @classmethod
    def get_is_cryptocurrencies_wildcard(cls) -> bool:
        """
        :return: True if the evaluator is not cryptocurrency dependant else False
        """
        return False

    def _print_tweet(self, tweet_text, tweet_url, note, count=""):
        self.logger.debug(f"Current note : {note} | {count} : {self.cryptocurrency} : Link: {tweet_url} Text : "
                          f"{tweet_text.encode('utf-8', 'ignore')}")

    async def _feed_callback(self, data):
        if self._is_interested_by_this_notification(data[CONFIG_TWEET_DESCRIPTION]):
            self.count += 1
            note = self._get_tweet_sentiment(data[CONFIG_TWEET], data[CONFIG_TWEET_DESCRIPTION])
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
                await self.evaluation_completed(self.cryptocurrency)

    @staticmethod
    def _compute_notification_time_to_live(evaluation):
        return TwitterNewsEvaluator._EVAL_MAX_TIME_TO_LIVE * abs(evaluation)

    def _get_tweet_sentiment(self, tweet, tweet_text, is_a_quote=False):
        try:
            if is_a_quote:
                return -1 * self.sentiment_analyser.analyse(tweet_text)
            else:
                padding_name = "########"
                author_screen_name = tweet['user']['screen_name'] if "screen_name" in tweet['user'] \
                    else padding_name
                author_name = tweet['user']['name'] if "name" in tweet['user'] else padding_name
                if self.specific_config[CONFIG_TWITTERS_ACCOUNTS]:
                    if author_screen_name in self.specific_config[CONFIG_TWITTERS_ACCOUNTS][self.cryptocurrency] \
                       or author_name in self.specific_config[CONFIG_TWITTERS_ACCOUNTS][self.cryptocurrency]:
                        return -1 * self.sentiment_analyser.analyse(tweet_text)
        except KeyError:
            pass

        # ignore # for the moment (too much of bullshit)
        return START_PENDING_EVAL_NOTE

    def _is_interested_by_this_notification(self, notification_description):
        # true if in twitter accounts
        if self.specific_config[CONFIG_TWITTERS_ACCOUNTS]:
            for account in self.specific_config[CONFIG_TWITTERS_ACCOUNTS][self.cryptocurrency]:
                if account.lower() in notification_description:
                    return True

        # false if it's a RT of an unfollowed account
        if notification_description.startswith("rt"):
            return False

        # true if contains symbol
        if self.cryptocurrency.lower() in notification_description:
            return True

        # true if in hashtags
        if self.specific_config[CONFIG_TWITTERS_HASHTAGS]:
            for hashtags in self.specific_config[CONFIG_TWITTERS_HASHTAGS][self.cryptocurrency]:
                if hashtags.lower() in notification_description:
                    return True
            return False

    def _get_config_elements(self, key):
        if CONFIG_CRYPTO_CURRENCIES in self.specific_config and self.specific_config[CONFIG_CRYPTO_CURRENCIES]:
            return {cc[CONFIG_CRYPTO_CURRENCY]: cc[key] for cc in self.specific_config[CONFIG_CRYPTO_CURRENCIES]
                    if cc[CONFIG_CRYPTO_CURRENCY] == self.cryptocurrency}
        return {}

    def _format_config(self):
        # remove other symbols data to avoid unnecessary tweets
        self.specific_config[CONFIG_TWITTERS_ACCOUNTS] = self._get_config_elements(CONFIG_TWITTERS_ACCOUNTS)
        self.specific_config[CONFIG_TWITTERS_HASHTAGS] = self._get_config_elements(CONFIG_TWITTERS_HASHTAGS)

    async def prepare(self):
        self._format_config()
        self.sentiment_analyser = get_single_deepest_child_class(TextAnalysis)()
