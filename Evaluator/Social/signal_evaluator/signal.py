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
import octobot_services.constants as services_constants
import octobot_evaluators.evaluators as evaluators
import tentacles.Services.Services_feeds as Services_feeds


class TelegramSignalEvaluator(evaluators.SocialEvaluator):
    SERVICE_FEED_CLASS = Services_feeds.TelegramServiceFeed

    async def _feed_callback(self, data):
        if self._is_interested_by_this_notification(data[services_constants.CONFIG_GROUP_MESSAGE_DESCRIPTION]):
            await self.analyse_notification(data)
            await self.evaluation_completed(self.cryptocurrency, self.symbol,
                                            eval_time=self.get_current_exchange_time())
        else:
            self.logger.debug(f"Ignored telegram feed: \"{self.symbol.lower()}\" pattern not found in "
                              f"\"{data[services_constants.CONFIG_GROUP_MESSAGE_DESCRIPTION].lower()}\"")

    # return true if the given notification is relevant for this client
    def _is_interested_by_this_notification(self, notification_description):
        if self.symbol:
            return self.symbol.lower() in notification_description.lower()
        else:
            return True

    async def analyse_notification(self, notification):
        notification_test = notification[services_constants.CONFIG_GROUP_MESSAGE_DESCRIPTION]
        self.eval_note = commons_constants.START_PENDING_EVAL_NOTE
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
                self.logger.error(f"Impossible to parse notification {notification_test}: {e}. Please refer to this "
                                  f"evaluator documentation to check the notification pattern.")
        else:
            self.logger.error(f"Impossible to parse notification {notification_test}. Please refer to this evaluator "
                              f"documentation to check the notification pattern.")

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

    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        """
        :return: True if the evaluator is not symbol dependant else False
        """
        return False

    def _get_tentacle_registration_topic(self, all_symbols_by_crypto_currencies, time_frames, real_time_time_frames):
        currencies = [self.cryptocurrency]
        symbols = [self.symbol]
        to_handle_time_frames = [self.time_frame]
        if self.get_is_cryptocurrencies_wildcard():
            currencies = all_symbols_by_crypto_currencies.keys()
        if self.get_is_symbol_wildcard():
            symbols = []
            for currency_symbols in all_symbols_by_crypto_currencies.values():
                symbols += currency_symbols
        # by default no time frame registration for social evaluators
        return currencies, symbols, to_handle_time_frames
