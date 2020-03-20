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
import hashlib
import hmac
import json

import time
from ccxt.async_support import binance

from octobot_trading.exchanges.types.websocket_exchange import WebsocketExchange
from octobot_trading.enums import WebsocketFeeds as Feeds


class Binance(WebsocketExchange):
    EXCHANGE_FEEDS = {
        Feeds.TRADES: 'aggTrade',
        Feeds.KLINE: 'kline',
        Feeds.TICKER: 'ticker',
        Feeds.MINI_TICKER: 'miniTicker',
        Feeds.BOOK_TICKER: 'bookTicker',
        Feeds.L2_BOOK: 'depth20@100ms'  # TODO only updates with depth@100ms ?
    }

    TIME_FRAME_DEPENDENT_CHANNELS = [EXCHANGE_FEEDS[Feeds.KLINE]]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.books = {}
        self.tickers = {}

    async def on_message(self, json_message: str):
        parsed_message: dict = json.loads(json_message)
        try:
            pass
        except Exception as e:
            self.logger.error(f"Error when handling message {e}")
            raise e

    async def subscribe(self):
        to_subscribe = set()
        for channel in self.channels:
            if channel in self.PAIR_INDEPENDENT_CHANNELS:
                to_subscribe.add(channel)
            else:
                to_subscribe |= set("{}:{}".format(channel, pair) for pair in self.pairs)
        if to_subscribe:
            await self._send_command("subscribe", list(to_subscribe))

    async def _send_command(self, command, args=None):
        await self.websocket.send(json.dumps({"op": command, "args": args or []}))

    async def do_auth(self):
        expires = self.generate_nonce()
        await self._send_command(command="authKeyExpires", args=[
            self.api_key,
            expires,
            self.generate_signature('GET', '/realtime', expires),
        ])

    @classmethod
    def get_name(cls):
        return 'binance'

    @classmethod
    def get_ccxt_async_client(cls):
        return binance

    """
    Authentication
    from https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md
    """

    def generate_nonce(self):
        return int(round(time.time() + 3600))

    def generate_signature(self, data):
        return hmac.new(self.api_secret.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest()
