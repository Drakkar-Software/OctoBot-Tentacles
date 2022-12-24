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


class TradingViewServiceFeedChannel(services_channel.AbstractServiceFeedChannel):
    pass


class TradingViewServiceFeed(service_feeds.AbstractServiceFeed):
    FEED_CHANNEL = TradingViewServiceFeedChannel
    REQUIRED_SERVICES = [Services_bases.WebHookService, Services_bases.TradingViewService]

    def __init__(self, config, main_async_loop, bot_id):
        super().__init__(config, main_async_loop, bot_id)
        self.webhook_service_name = "trading_view"
        self.webhook_service_url = ""

    def _something_to_watch(self):
        return bool(self.channel.consumers)

    def ensure_callback_auth(self, data) -> bool:
        if self.services[1].requires_token:
            split_result = data.split("TOKEN=")
            if len(split_result) > 1:
                token = split_result[1].strip().split("\n")[0]
                return self.services[1].token == token
            return False
        # no token expected
        return True

    def webhook_callback(self, data):
        self.logger.debug(f"Received : {data}")
        self._notify_consumers(
            {
                services_constants.FEED_METADATA: data,
            }
        )

    def _register_to_service(self):
        if not self.services[0].is_subscribed(self.webhook_service_name):
            self.services[0].subscribe_feed(self.webhook_service_name, self.webhook_callback, self.ensure_callback_auth)

    def _initialize(self):
        self._register_to_service()

    async def _start_service_feed(self):
        success = await self.services[0].start_webhooks()
        self.webhook_service_url = self.services[0].get_subscribe_url(self.webhook_service_name)
        if success:
            self.services[1].register_webhook_url(self.webhook_service_url)
            self.logger.info(f"Your OctoBot's TradingView webhook url is: {self.webhook_service_url}    "
                             f"the pin code for this feed is: {self.services[1].token}")
        return success
