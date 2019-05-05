"""
OctoBot Tentacle

$tentacle_description: {
    "name": "forum_evaluator",
    "type": "Evaluator",
    "subtype": "Social",
    "version": "1.1.1",
    "requirements": [],
    "config_files": ["RedditForumEvaluator.json"],
    "config_schema_files": ["RedditForumEvaluator_schema.json"]
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

from config import *
from evaluator.Social.social_evaluator import ForumSocialEvaluator
from evaluator.Util.advanced_manager import AdvancedManager
from evaluator.Util import TextAnalysis
from evaluator.Util import OverallStateAnalyser
from services.Dispatchers.reddit_dispatcher import RedditDispatcher
from services.Dispatchers.abstract_dispatcher import DispatcherAbstractClient


# RedditForumEvaluator is used to get an overall state of a market, it will not trigger a trade
# (notify its evaluators) but is used to measure hype and trend of a market.
class RedditForumEvaluator(ForumSocialEvaluator, DispatcherAbstractClient):
    DESCRIPTION = "First initialises using the recent history of the subreddits in RedditForumEvaluator.json then " \
                  "watches for new posts to update its evaluation. Never triggers strategies re-evaluations, " \
                  "acts as a background evaluator."

    def __init__(self):
        ForumSocialEvaluator.__init__(self)
        DispatcherAbstractClient.__init__(self)
        self.overall_state_analyser = OverallStateAnalyser()
        self.count = 0
        self.symbol = ""
        self.sentiment_analyser = None
        self.is_self_refreshing = True

    def set_dispatcher(self, dispatcher):
        super().set_dispatcher(dispatcher)
        self.dispatcher.update_social_config(self.social_config)

    @staticmethod
    def get_dispatcher_class():
        return RedditDispatcher

    def _print_entry(self, entry_text, entry_note, count=""):
        self.logger.debug(f"New reddit entry ! : {entry_note} | {count} : {self.symbol} : Link : {entry_text}")

    async def receive_notification_data(self, data):
        self.count += 1
        entry_note = self._get_sentiment(data[CONFIG_REDDIT_ENTRY])
        if entry_note != START_PENDING_EVAL_NOTE:
            self.overall_state_analyser.add_evaluation(entry_note, data[CONFIG_REDDIT_ENTRY_WEIGHT], False)
            if data[CONFIG_REDDIT_ENTRY_WEIGHT] > 4:
                link = f"https://www.reddit.com{data[CONFIG_REDDIT_ENTRY].permalink}"
                self._print_entry(link, entry_note, str(self.count))

    # overwrite get_eval_note from abstract evaluator to recompute OverallStateAnalyser evaluation
    def get_eval_note(self):
        self.eval_note = self.overall_state_analyser.get_overall_state_after_refresh()
        return self.eval_note

    def _get_sentiment(self, entry):
        # analysis entry text and gives overall sentiment
        reddit_entry_min_length = 50
        # ignore usless (very short) entries
        if entry.selftext and len(entry.selftext) >= reddit_entry_min_length:
            return -1 * self.sentiment_analyser.analyse(entry.selftext)
        return START_PENDING_EVAL_NOTE

    def is_interested_by_this_notification(self, notification_description):
        # true if in this symbol's subreddits configuration
        if self.social_config[CONFIG_REDDIT_SUBREDDITS]:
            for subreddit in self.social_config[CONFIG_REDDIT_SUBREDDITS][self.symbol]:
                if subreddit.lower() == notification_description:
                    return True
        return False

    def _get_config_elements(self, key):
        if CONFIG_CRYPTO_CURRENCIES in self.social_config and self.social_config[CONFIG_CRYPTO_CURRENCIES]:
            return {cc[CONFIG_CRYPTO_CURRENCY]: cc[key] for cc in self.social_config[CONFIG_CRYPTO_CURRENCIES]
                    if cc[CONFIG_CRYPTO_CURRENCY] == self.symbol}
        return {}

    def _format_config(self):
        # remove other symbols data to avoid unnecessary entries
        self.social_config[CONFIG_REDDIT_SUBREDDITS] = self._get_config_elements(CONFIG_REDDIT_SUBREDDITS)

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
