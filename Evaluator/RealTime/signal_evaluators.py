"""
OctoBot Tentacle

$tentacle_description: {
    "name": "signal_evaluators",
    "type": "Evaluator",
    "subtype": "RealTime",
    "version": "1.1.1",
    "requirements": [],
    "config_files": ["TelegramSignalEvaluator.json"],
    "config_schema_files": ["TelegramSignalEvaluator_schema.json"]
}
"""
#  Drakkar-Software OctoBot
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


from abc import abstractmethod
from typing import Dict, Any

from config import START_PENDING_EVAL_NOTE, CONFIG_GROUP_MESSAGE_DESCRIPTION
from services.Dispatchers.telegram_dispatcher import TelegramDispatcher
from evaluator.RealTime.realtime_evaluator import RealTimeSignalEvaluator


class TelegramSignalEvaluator(RealTimeSignalEvaluator):
    DESCRIPTION = "Very simple evaluator designed to be an example for an evaluator using Telegram signals. " \
                  "Triggers on a Telegram signal from any group or channel listed in TelegramSignalEvaluator.json " \
                  "in which your Telegram bot is invited and analyses it to make a move. " \
                  "Signal format for this implementation is: SYMBOL[evaluation]. Example: BTC/USDT[-0.45] " \
                  "SYMBOL has to be in current watched symbols (in configuration) " \
                  "and evaluation must be between -1 and 1. Remember that OctoBot can only see messages from a " \
                  "chat/group where its Telegram bot (in configuration) has been invited. Keep also in mind that you " \
                  "need to disable the privacy mode of your Telegram bot to allow it to see group messages. " \
                  "See OctoBot wiki about Telegram interface for more information."

    def set_dispatcher(self, dispatcher):
        super().set_dispatcher(dispatcher)
        self.dispatcher.update_channel_config(self.specific_config)

    async def receive_notification_data(self, data) -> None:
        await self.analyse_notification(data)

    @staticmethod
    def get_dispatcher_class():
        return TelegramDispatcher

    # return true if the given notification is relevant for this client
    def is_interested_by_this_notification(self, notification_description):
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
                notification_eval = notification_test.split(start_eval_chars)[1].split(end_eval_chars)[0]
                potential_note = float(notification_eval)
                if -1 <= potential_note <= 1:
                    self.eval_note = potential_note
                    await self.notify_evaluator_task_managers(self.get_name())
                else:
                    self.logger.error(f"Impossible to use notification evaluation: {notification_eval}: "
                                      f"evaluation should be between -1 and 1.")
            except Exception as e:
                self.logger.error(f"Impossible to parse notification {notification}: {e}")
        else:
            self.logger.error(f"Impossible to parse notification {notification}")

    async def eval_impl(self):
        pass
