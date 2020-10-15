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

import octobot_commons.constants as commons_constants

import octobot_commons.tentacles_management as tentacles_management
import octobot_services.constants as services_constants
import octobot_evaluators.evaluators as evaluators
from tentacles.Evaluator.Util.text_analysis import TextAnalysis
import tentacles.Services.Services_feeds as Services_feeds


class TwitterNewsEvaluator(evaluators.SocialEvaluator):
    SERVICE_FEED_CLASS = Services_feeds.TwitterServiceFeed

    # max time to live for a pulse is 10min
    _EVAL_MAX_TIME_TO_LIVE = 10 * commons_constants.MINUTE_TO_SECONDS
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

    @classmethod
    def get_is_cryptocurrency_name_wildcard(cls) -> bool:
        """
        :return: True if the evaluator is not cryptocurrency name dependant else False
        """
        return False

    def _print_tweet(self, tweet_text, tweet_url, note, count=""):
        self.logger.debug(f"Current note : {note} | {count} : {self.cryptocurrency_name} : Link: {tweet_url} Text : "
                          f"{tweet_text.encode('utf-8', 'ignore')}")

    async def _feed_callback(self, data):
        if self._is_interested_by_this_notification(data[services_constants.CONFIG_TWEET_DESCRIPTION]):
            self.count += 1
            note = self._get_tweet_sentiment(data[services_constants.CONFIG_TWEET],
                                             data[services_constants.CONFIG_TWEET_DESCRIPTION])
            tweet_url = f"https://twitter.com/ProducToken/status/{data['tweet']['id']}"
            if note != commons_constants.START_PENDING_EVAL_NOTE:
                self._print_tweet(data[services_constants.CONFIG_TWEET_DESCRIPTION], tweet_url, note, str(self.count))
            await self._check_eval_note(note)

    # only set eval note when something is happening
    async def _check_eval_note(self, note):
        if note != commons_constants.START_PENDING_EVAL_NOTE:
            if abs(note) > self._EVAL_NOTIFICATION_THRESHOLD:
                self.eval_note = note
                self.save_evaluation_expiration_time(self._compute_notification_time_to_live(self.eval_note))
                await self.evaluation_completed(self.cryptocurrency, eval_time=self.get_current_exchange_time())

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
                if self.specific_config[services_constants.CONFIG_TWITTERS_ACCOUNTS]:
                    if author_screen_name in self.specific_config[services_constants.CONFIG_TWITTERS_ACCOUNTS][
                        self.cryptocurrency_name] \
                            or author_name in self.specific_config[services_constants.CONFIG_TWITTERS_ACCOUNTS][
                        self.cryptocurrency_name]:
                        return -1 * self.sentiment_analyser.analyse(tweet_text)
        except KeyError:
            pass

        # ignore # for the moment (too much of bullshit)
        return commons_constants.START_PENDING_EVAL_NOTE

    def _is_interested_by_this_notification(self, notification_description):
        # true if in twitter accounts
        if self.specific_config[services_constants.CONFIG_TWITTERS_ACCOUNTS]:
            for account in self.specific_config[services_constants.CONFIG_TWITTERS_ACCOUNTS][self.cryptocurrency_name]:
                if account.lower() in notification_description:
                    return True

        # false if it's a RT of an unfollowed account
        if notification_description.startswith("rt"):
            return False

        # true if contains symbol
        if self.cryptocurrency_name.lower() in notification_description:
            return True

        # true if in hashtags
        if self.specific_config[services_constants.CONFIG_TWITTERS_HASHTAGS]:
            for hashtags in self.specific_config[services_constants.CONFIG_TWITTERS_HASHTAGS][self.cryptocurrency_name]:
                if hashtags.lower() in notification_description:
                    return True
            return False

    def _get_config_elements(self, key):
        if commons_constants.CONFIG_CRYPTO_CURRENCIES in self.specific_config and self.specific_config[
            commons_constants.CONFIG_CRYPTO_CURRENCIES]:
            return {cc[commons_constants.CONFIG_CRYPTO_CURRENCY]: cc[key] for cc in
                    self.specific_config[commons_constants.CONFIG_CRYPTO_CURRENCIES]
                    if cc[commons_constants.CONFIG_CRYPTO_CURRENCY] == self.cryptocurrency_name}
        return {}

    def _format_config(self):
        # remove other symbols data to avoid unnecessary tweets
        self.specific_config[services_constants.CONFIG_TWITTERS_ACCOUNTS] = self._get_config_elements(
            services_constants.CONFIG_TWITTERS_ACCOUNTS)
        self.specific_config[services_constants.CONFIG_TWITTERS_HASHTAGS] = self._get_config_elements(
            services_constants.CONFIG_TWITTERS_HASHTAGS)

    async def prepare(self):
        self._format_config()
        self.sentiment_analyser = tentacles_management.get_single_deepest_child_class(TextAnalysis)()
