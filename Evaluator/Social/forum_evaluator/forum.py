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
import octobot_evaluators.evaluators as evaluators
import octobot_services.constants as services_constants
import tentacles.Services.Services_feeds as Services_feeds
import tentacles.Evaluator.Util as EvaluatorUtil

CONFIG_REDDIT = "reddit"
CONFIG_REDDIT_SUBREDDITS = "subreddits"
CONFIG_REDDIT_ENTRY = "entry"
CONFIG_REDDIT_ENTRY_WEIGHT = "entry_weight"


# RedditForumEvaluator is used to get an overall state of a market, it will not trigger a trade
# (notify its evaluators) but is used to measure hype and trend of a market.
class RedditForumEvaluator(evaluators.SocialEvaluator):

    SERVICE_FEED_CLASS = Services_feeds.RedditServiceFeed

    def __init__(self):
        evaluators.SocialEvaluator.__init__(self)
        self.overall_state_analyser = EvaluatorUtil.OverallStateAnalyser()
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

    def _print_entry(self, entry_text, entry_note, count=""):
        self.logger.debug(f"New reddit entry ! : {entry_note} | {count} : {self.cryptocurrency_name} : "
                          f"Link : {entry_text}")

    async def _feed_callback(self, data):
        if self._is_interested_by_this_notification(data[services_constants.FEED_METADATA]):
            self.count += 1
            entry_note = self._get_sentiment(data[CONFIG_REDDIT_ENTRY])
            if entry_note != commons_constants.START_PENDING_EVAL_NOTE:
                self.overall_state_analyser.add_evaluation(entry_note, data[CONFIG_REDDIT_ENTRY_WEIGHT], False)
                if data[CONFIG_REDDIT_ENTRY_WEIGHT] > 3:
                    link = f"https://www.reddit.com{data[CONFIG_REDDIT_ENTRY].permalink}"
                    self._print_entry(link, entry_note, str(self.count))
                self.eval_note = self.overall_state_analyser.get_overall_state_after_refresh()
                await self.evaluation_completed(self.cryptocurrency, eval_time=self.get_current_exchange_time())

    def _get_sentiment(self, entry):
        # analysis entry text and gives overall sentiment
        reddit_entry_min_length = 50
        # ignore usless (very short) entries
        if entry.selftext and len(entry.selftext) >= reddit_entry_min_length:
            return -1 * self.sentiment_analyser.analyse(entry.selftext)
        return commons_constants.START_PENDING_EVAL_NOTE

    def _is_interested_by_this_notification(self, notification_description):
        # true if the given subreddit is in this cryptocurrency's subreddits configuration
        if self.specific_config[CONFIG_REDDIT_SUBREDDITS]:
            for subreddit in self.specific_config[CONFIG_REDDIT_SUBREDDITS][self.cryptocurrency_name]:
                if subreddit.lower() == notification_description:
                    return True
        return False

    def _get_config_elements(self, key):
        if commons_constants.CONFIG_CRYPTO_CURRENCIES in self.specific_config and self.specific_config[commons_constants.CONFIG_CRYPTO_CURRENCIES]:
            return {cc[commons_constants.CONFIG_CRYPTO_CURRENCY]: cc[key] for cc in self.specific_config[commons_constants.CONFIG_CRYPTO_CURRENCIES]
                    if cc[commons_constants.CONFIG_CRYPTO_CURRENCY] == self.cryptocurrency_name}
        return {}

    def _format_config(self):
        # remove other symbols data to avoid unnecessary entries
        self.specific_config[CONFIG_REDDIT_SUBREDDITS] = self._get_config_elements(CONFIG_REDDIT_SUBREDDITS)

    async def prepare(self):
        self._format_config()
        self.sentiment_analyser = tentacles_management.get_single_deepest_child_class(EvaluatorUtil.TextAnalysis)()
