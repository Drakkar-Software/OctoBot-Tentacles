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
import uuid
from enum import Enum

import time
from ccxt.async_support import bitmax
from octobot_commons.enums import TimeFramesMinutes

from octobot_trading.constants import RECENT_TRADES_CHANNEL, ORDER_BOOK_CHANNEL, KLINE_CHANNEL, \
    ORDERS_CHANNEL
from octobot_trading.data.book import Book
from octobot_trading.enums import WebsocketFeeds as Feeds
from octobot_trading.exchanges.types.websocket_exchange import WebsocketExchange


class Bitmax(WebsocketExchange):
    EXCHANGE_FEEDS = {
        Feeds.L2_BOOK: 'depth',
        Feeds.KLINE: 'bar',
        Feeds.TRADES: 'trades',
        Feeds.ORDERS: 'order',
    }

    ACCOUNT_DEPENDENT_CHANNELS = [EXCHANGE_FEEDS[Feeds.ORDERS]]
    TIME_FRAME_DEPENDENT_CHANNELS = [EXCHANGE_FEEDS[Feeds.KLINE]]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ws_id = None
        self.books = {}

    async def _kline(self, msg: dict):
        if msg['data'] and msg['s']:
            symbol = self.get_pair_from_exchange(msg['s'])
            time_frame = self.interval_to_time_frame(msg['data'].get('i', ''))
            if msg['data']:
                await self.push_to_channel(KLINE_CHANNEL, time_frame=time_frame, symbol=symbol,
                                           kline=self.exchange.parse_ohlcv(msg['data']))

    async def _trade(self, msg: dict):
        if msg['data'] and msg['symbol']:
            symbol = self.get_pair_from_exchange(msg['symbol'])
            await self.push_to_channel(RECENT_TRADES_CHANNEL,
                                       symbol=symbol,
                                       recent_trades=[self.exchange.parse_trade(trade) for trade in msg['data']])

    async def _l2_book(self, msg: dict):
        if msg['data'] and msg['symbol']:
            symbol = self.get_pair_from_exchange(msg['symbol'])
            order_book = self.exchange.parse_order_book(msg['data'])

            def format_order_book(side_orders: list, side: str):
                return [{"id": order[0],
                         "price": order[0],
                         "size": order[1],
                         "side": side}
                        for order in side_orders]

            orders = format_order_book(order_book.get('asks', []), self.exchange.SELL_STR) + \
                     format_order_book(order_book.get('bids', []), self.exchange.BUY_STR)
            if msg.get('m', '').endswith('snapshot'):
                self.books[symbol] = Book()
                self.books[symbol].handle_book_update(orders)
            elif symbol in self.books:
                book = self.books[symbol]
                updated_orders = [order for order in orders if order["size"] > 0]
                removed_orders = [order for order in orders if order["size"] == 0]

                # if size is zero, you should delete the level at price.
                # id inserted_orders:
                #   book.handle_book_delta_insert([])
                if updated_orders:
                    book.handle_book_delta_update(updated_orders)
                if removed_orders:
                    book.handle_book_delta_delete(removed_orders)

            if symbol in self.books:
                await self.push_to_channel(ORDER_BOOK_CHANNEL,
                                           symbol=symbol,
                                           asks=self.books[symbol].get_asks(side=self.exchange.SELL_STR),
                                           bids=self.books[symbol].get_bids(side=self.exchange.BUY_STR))

    async def _order(self, msg: dict):
        if msg['data']:
            # TODO parsing not fully handled by ccxt_client.parse_order
            await self.push_to_channel(ORDERS_CHANNEL,
                                       orders=self.exchange.parse_order(msg['data']))

    async def on_message(self, json_message: str):
        parsed_message: dict = json.loads(json_message)
        try:
            if 'm' in parsed_message or 'message' in parsed_message:
                topic = parsed_message["m"] if 'm' in parsed_message else parsed_message["message"]

                if topic.startswith("error"):
                    self.on_error(f"{topic}, reason : {parsed_message.get('reason', '')}")

                elif topic.startswith('pong'):
                    self.on_pong()

                elif topic.startswith('ping'):
                    await self.on_ping()

                elif topic.startswith('connected'):
                    self.on_auth(parsed_message.get('type', 'unauth') == 'auth')

                elif topic.startswith('auth'):
                    self.on_auth(parsed_message.get('code', -1) == 0)

                elif topic.startswith(self.EXCHANGE_FEEDS[Feeds.L2_BOOK]) or topic.startswith('depth-snapshot'):
                    await self._l2_book(parsed_message)

                elif topic.startswith(self.EXCHANGE_FEEDS[Feeds.TRADES]):
                    await self._trade(parsed_message)

                elif topic.startswith(self.EXCHANGE_FEEDS[Feeds.KLINE]):
                    await self._kline(parsed_message)

                elif topic.startswith(self.EXCHANGE_FEEDS[Feeds.ORDERS]):
                    await self._order(parsed_message)

                elif topic.startswith('sub'):
                    if parsed_message.get('code', -1) == 0:
                        self.logger.debug(f"Subscription succeed to : {parsed_message.get('ch', '')}")
                    else:
                        self.on_error(f"Subscription failed to : {parsed_message.get('ch', '')}")
                else:
                    self.on_error(f"Unknown topic: {topic}")
        except Exception as e:
            self.on_error(f"Error when handling message {e}")
            self.logger.exception(e)

    async def request_order_book_snapshot(self):
        for pair in self.pairs:
            await self.send_request(action='depth-snapshot', args={'symbol': pair})

    async def send_request(self, action: str, **kwargs: dict):
        await self._send_command(command='req', action=action, **kwargs)

    async def prepare(self):
        await self.request_order_book_snapshot()

    async def subscribe(self, unsubscribe=False, account='cash'):
        for channel in self.channels:
            subscribing_channels = f"{channel}:"
            if channel in self.ACCOUNT_DEPENDENT_CHANNELS:
                for account in self.exchange.ACCOUNTS:
                    subscribing_channels += account.value
            else:
                if channel in self.TIME_FRAME_DEPENDENT_CHANNELS:
                    subscribing_channels += ','.join([str(TimeFramesMinutes[time_frame])
                                                      for time_frame in self.time_frames])
                    subscribing_channels += ":"
                subscribing_channels += ','.join(self.pairs)
            await self._send_command("sub" if not unsubscribe else 'unsub', ch=subscribing_channels)

    async def _send_command(self, command, **kwargs: dict):
        args = {
            "op": command,
            "id": self.generate_nonce()
        }
        args.update(kwargs)
        await self.websocket.send(json.dumps(args))

    async def ping(self):
        await super().ping()
        await self._send_command(command="ping")

    async def do_auth(self):
        nonce = self.generate_nonce()
        auth_ts = self.get_timestamp()
        await self._send_command(command="auth", id=nonce, ts=auth_ts,
                                 key=self.api_key, sig=self.generate_signature(auth_ts))

    @classmethod
    def get_name(cls):
        return 'bitmax'

    @classmethod
    def get_ws_endpoint(cls, group=0, route_prefix='api/pro/v1'):
        return f'wss://bitmax.io:443/{group}/{route_prefix}/stream'

    @classmethod
    def get_ws_testnet_endpoint(cls, group=0, route_prefix='api/pro/v1'):
        return f'wss://bitmax-test.io:443/{group}/{route_prefix}/stream'

    @classmethod
    def get_endpoint(cls):
        return 'https://bitmax.io'

    @classmethod
    def get_testnet_endpoint(cls):
        return 'https://bitmax-test.io'

    @classmethod
    def get_ccxt_async_client(cls):
        return bitmax

    """
    Authentication
    from https://github.com/bitmax-exchange/bitmax-pro-api-demo/blob/master/python/client.py
    """

    def generate_nonce(self):
        if not self.ws_id:
            self.ws_id = uuid.uuid4().hex
        return self.ws_id

    def get_timestamp(self):
        return int(time.time() * 1e3)

    def generate_signature(self, timestamp, api_path='stream'):
        return hmac.new(key=self.api_secret.encode('utf-8'),
                        msg=f"{timestamp}{api_path}".encode('utf-8'),
                        digestmod=hashlib.sha256).hexdigest()

    def interval_to_time_frame(self, interval):
        try:
            time_frame_minute = int(interval)
            for time_frame, tfm in TimeFramesMinutes.items():
                if time_frame_minute == tfm:
                    return time_frame
        except ValueError:
            pass
        return None
