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
import uuid

from flask import request, abort

from octobot_services.channel.abstract_service_feed import AbstractServiceFeedChannel
from octobot_services.constants import FEED_METADATA
from octobot_services.service_feeds.abstract_service_feed import AbstractServiceFeed
from tentacles.Services.Services_bases import WebHookService, TradingViewService


class TradingViewServiceFeedChannel(AbstractServiceFeedChannel):
    pass


class TradingViewServiceFeed(AbstractServiceFeed):
    FEED_CHANNEL = TradingViewServiceFeedChannel
    REQUIRED_SERVICES = [WebHookService, TradingViewService]

    def __init__(self, config, main_async_loop, bot_id):
        super().__init__(config, main_async_loop, bot_id)
        self.pin_code = uuid.uuid4().hex
        self.webhook_service_name = "trading_view"
        self.webhook_service_url = ""

    def _something_to_watch(self):
        return True

    def _load_webhook_routes(self) -> None:
        @self.webhook_app.route('/')
        def index():
            """
            Route to check if webhook server is online
            """
            return ''

        @self.webhook_app.route('/webhook', methods=['POST'])
        def webhook():
            """
            Route to handle webhook requests
            """
            if request.method == 'POST':
                data = request.get_data(as_text=True)
                # Check that the key is correct
                # if self.service.get_security_token(self.pin_code) == data['key']:
                self.logger.debug(f"WebHook received : {data}")
                self._notify_consumers(
                    {
                        FEED_METADATA: data,
                    }
                )
                return '', 200
                # else:
                #     abort(403)
            else:
                abort(400)

    def webhook_callback(self, data):
        self.logger.debug(f"Received : {data}")
        self._notify_consumers(
            {
                FEED_METADATA: data,
            }
        )

    def _initialize(self):
        pass

    async def _start_service_feed(self):
        try:
            self.webhook_service_url = self.services[0].subscribe_feed(self.webhook_service_name, self.webhook_callback)
            self.logger.info(f"TradingView webhook url = {self.webhook_service_url}")
            return True
        except Exception as e:
            self.logger.exception(e, True, f"Error when starting TradingView feed: ({e})")
            self.should_stop = True
        finally:
            return False
