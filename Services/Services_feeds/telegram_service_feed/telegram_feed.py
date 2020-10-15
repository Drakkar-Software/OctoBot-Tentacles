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

import octobot_services.channel as services_channel
import octobot_services.constants as services_constants
import octobot_services.service_feeds as service_feeds
import tentacles.Services.Services_bases as Services_bases


class TelegramServiceFeedChannel(services_channel.AbstractServiceFeedChannel):
    pass


class TelegramServiceFeed(service_feeds.AbstractServiceFeed):
    FEED_CHANNEL = TelegramServiceFeedChannel
    REQUIRED_SERVICES = [Services_bases.TelegramService]

    HANDLED_CHATS = ["group", "channel"]

    def __init__(self, config, main_async_loop, bot_id):
        super().__init__(config, main_async_loop, bot_id)
        self.feed_config = {
            services_constants.CONFIG_TELEGRAM_ALL_CHANNEL: False,
            services_constants.CONFIG_TELEGRAM_CHANNEL: []
        }

    # configure the whitelist of Telegram groups/channels to listen to
    # merge new config into existing config
    def update_feed_config(self, config):
        self.feed_config[services_constants.CONFIG_TELEGRAM_CHANNEL].extend(
            channel for channel in config[services_constants.CONFIG_TELEGRAM_CHANNEL]
            if channel not in
            self.feed_config[services_constants.CONFIG_TELEGRAM_CHANNEL])

    # if True, disable channel whitelist and listen to every group/channel it is invited to
    def set_listen_to_all_groups_and_channels(self, activate=True):
        self.feed_config[services_constants.CONFIG_TELEGRAM_ALL_CHANNEL] = activate

    def _register_to_service(self):
        if not self.services[0].is_registered(self.get_name()):
            self.services[0].register_user(self.get_name())
            self.services[0].register_text_polling_handler(self.HANDLED_CHATS, self._feed_callback)

    def _feed_callback(self, _, update):
        message = update.effective_message.text
        chat = update.effective_chat["title"]
        if self.feed_config[services_constants.CONFIG_TELEGRAM_ALL_CHANNEL] or chat in self.feed_config[
            services_constants.CONFIG_TELEGRAM_CHANNEL]:
            message_desc = str(update)
            self._notify_consumers(
                {
                    services_constants.FEED_METADATA: message_desc,
                    services_constants.CONFIG_GROUP_MESSAGE: update,
                    services_constants.CONFIG_GROUP_MESSAGE_DESCRIPTION: message.lower()
                }
            )
        else:
            self.logger.debug(f"Ignored message from {chat} chat: not in followed telegram chats (message: {message})")

    def _something_to_watch(self):
        return self.feed_config[services_constants.CONFIG_TELEGRAM_ALL_CHANNEL] or self.feed_config[
            services_constants.CONFIG_TELEGRAM_CHANNEL]

    @staticmethod
    def _get_service_layer_service_feed():
        return Services_bases.TelegramService

    def _initialize(self):
        self._register_to_service()

    async def _start_service_feed(self):
        return True
