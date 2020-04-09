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
from octobot_commons.constants import START_PENDING_EVAL_NOTE
from octobot_services.constants import CONFIG_GROUP_MESSAGE_DESCRIPTION
from octobot_evaluators.evaluator.social_evaluator import SocialEvaluator
from tentacles.Services_feeds import TelegramServiceFeed


class TelegramSignalEvaluator(SocialEvaluator):

    SERVICE_FEED_CLASS = TelegramServiceFeed

    async def _feed_callback(self, data):
        if self._is_interested_by_this_notification(data[CONFIG_GROUP_MESSAGE_DESCRIPTION]):
            await self.analyse_notification(data)
            await self.evaluation_completed(self.cryptocurrency, self.symbol)

    # return true if the given notification is relevant for this client
    def _is_interested_by_this_notification(self, notification_description):
        if self.symbol:
            return self.symbol.lower() in notification_description.lower()
        else:
            return True

    async def analyse_notification(self, notification):
        notification_test = notification[CONFIG_GROUP_MESSAGE_DESCRIPTION]
        self.eval_note = START_PENDING_EVAL_NOTE
        start_eval_chars = "["
        end_eval_chars = "]"
        if start_eval_chars in notification_test and end_eval_chars in notification_test:
            try:
                split_test = notification_test.split(start_eval_chars)
                notification_eval = split_test[1].split(end_eval_chars)[0]
                potential_note = float(notification_eval)
                if -1 <= potential_note <= 1:
                    self.eval_note = potential_note
                else:
                    self.logger.error(f"Impossible to use notification evaluation: {notification_eval}: "
                                      f"evaluation should be between -1 and 1.")
            except Exception as e:
                self.logger.error(f"Impossible to parse notification {notification}: {e}")
        else:
            self.logger.error(f"Impossible to parse notification {notification}")

    @classmethod
    def get_is_cryptocurrencies_wildcard(cls) -> bool:
        """
        :return: True if the evaluator is not cryptocurrency dependant else False
        """
        return False

    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        """
        :return: True if the evaluator is not symbol dependant else False
        """
        return False
