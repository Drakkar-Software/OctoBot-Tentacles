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

from octobot_services.channel.abstract_service_feed import AbstractServiceFeedChannel
from octobot_services.constants import CONFIG_TELEGRAM_CHANNEL, CONFIG_GROUP_MESSAGE, CONFIG_GROUP_MESSAGE_DESCRIPTION, \
    CONFIG_TELEGRAM_ALL_CHANNEL, FEED_METADATA
from octobot_services.service_feeds.abstract_service_feed import AbstractServiceFeed
from tentacles.Services.Services_bases import TelegramService


class TelegramServiceFeedChannel(AbstractServiceFeedChannel):
    pass


class TelegramServiceFeed(AbstractServiceFeed):
    FEED_CHANNEL = TelegramServiceFeedChannel
    REQUIRED_SERVICES = [TelegramService]

    HANDLED_CHATS = ["group", "channel"]

    def __init__(self, config, main_async_loop, bot_id):
        super().__init__(config, main_async_loop, bot_id)
        self.feed_config = {
            CONFIG_TELEGRAM_ALL_CHANNEL: False,
            CONFIG_TELEGRAM_CHANNEL: []
        }

    # configure the whitelist of Telegram groups/channels to listen to
    # merge new config into existing config
    def update_feed_config(self, config):
        self.feed_config[CONFIG_TELEGRAM_CHANNEL].extend(channel for channel in config[CONFIG_TELEGRAM_CHANNEL]
                                                         if channel not in
                                                         self.feed_config[CONFIG_TELEGRAM_CHANNEL])

    # if True, disable channel whitelist and listen to every group/channel it is invited to
    def set_listen_to_all_groups_and_channels(self, activate=True):
        self.feed_config[CONFIG_TELEGRAM_ALL_CHANNEL] = activate

    def _register_to_service(self):
        if not self.services[0].is_registered(self.get_name()):
            self.services[0].register_user(self.get_name())
            self.services[0].register_text_polling_handler(self.HANDLED_CHATS, self._feed_callback)

    def _feed_callback(self, _, update):
        if self.feed_config[CONFIG_TELEGRAM_ALL_CHANNEL] or \
                update.effective_chat["title"] in self.feed_config[CONFIG_TELEGRAM_CHANNEL]:
            message = update.effective_message.text
            message_desc = str(update)
            self._notify_consumers(
                {
                    FEED_METADATA: message_desc,
                    CONFIG_GROUP_MESSAGE: update,
                    CONFIG_GROUP_MESSAGE_DESCRIPTION: message.lower()
                }
            )

    def _something_to_watch(self):
        return self.feed_config[CONFIG_TELEGRAM_ALL_CHANNEL] or self.feed_config[CONFIG_TELEGRAM_CHANNEL]

    @staticmethod
    def _get_service_layer_service_feed():
        return TelegramService

    def _initialize(self):
        self._register_to_service()

    async def _start_service_feed(self):
        return True
