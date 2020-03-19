# cython: language_level=3
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
import hmac
import json
import re
from enum import Enum

import time
from ccxt.async_support import bybit
from octobot_websockets.data.ticker import Ticker

from octobot_commons.enums import TimeFramesMinutes, TimeFrames
from octobot_websockets.constants import BUY, SELL, Feeds
from octobot_websockets.data.book import Book
from octobot_websockets.feeds.feed import Feed


class BybitFeeds(Enum):
    TRADES = 'trade'
    TICKER = 'instrument_info.100ms'
    L2_BOOK = 'orderBookL2_25'
    KLINE = 'klineV2'
    TRADE = 'execution'
    ORDERS = 'order'


class BybitSide(Enum):
    BUY = "Buy"
    SELL = "Sell"


class ByBit(Feed):
    PAIR_INDEPENDENT_CHANNELS = [BybitFeeds.TRADES.value, Feeds.POSITION.value,
                                 BybitFeeds.TRADE.value, BybitFeeds.ORDERS.value]

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__(pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.books = {}
        self.tickers = {}

    async def _trade(self, msg: dict, symbol: str):
        if msg['data'] and symbol in self.callbacks[Feeds.TRADES]:
            await self.callbacks[Feeds.TRADES][symbol](recent_trades=self.ccxt_client.parse_trades(msg['data']))

    async def _order(self, msg: dict):
        if msg['data']:
            await self.callbacks[Feeds.ORDERS](orders=self.ccxt_client.parse_orders(msg['data']))

    async def _execution(self, msg: dict):
        if msg['data']:
            await self.callbacks[Feeds.TRADE](trades=self.ccxt_client.parse_trades(msg['data']))

    async def _kline(self,  msg: dict, symbol: str, time_frame):
        if msg['data'] and symbol in self.callbacks[Feeds.KLINE] and time_frame in self.callbacks[Feeds.KLINE][symbol]:
            klines: list = msg['data']
            if klines[0]['confirm']:
                await self.callbacks[Feeds.CANDLE][symbol][time_frame](candle=self.ccxt_client.parse_ohlcv(klines[0]))
                klines.pop(0)
            if klines:
                await self.callbacks[Feeds.KLINE][symbol][time_frame](kline=self.ccxt_client.parse_ohlcv(klines[0]))

    async def _l2_book(self, msg: dict, symbol: str):
        if symbol in self.callbacks[Feeds.L2_BOOK]:
            try:
                book = self.books[symbol]
            except KeyError:
                self.books[symbol] = Book()
                book = self.books[symbol]

            if msg['type'] == 'snapshot':
                book.reset()
                book.handle_book_update(msg['data'])
            else:
                if msg['data']['delete']:
                    book.handle_book_delta_delete(msg['data']['delete'])
                if msg['data']['insert']:
                    book.handle_book_delta_insert(msg['data']['insert'])
                if msg['data']['update']:
                    book.handle_book_delta_update(msg['data']['update'])

                await self.callbacks[Feeds.L2_BOOK][symbol](feed=self.get_name(),
                                                            asks=book.get_asks(side=BybitSide.SELL.value),
                                                            bids=book.get_bids(side=BybitSide.BUY.value),
                                                            timestamp=book.timestamp)

    async def _ticker(self, msg: dict, symbol: str):
        if symbol in self.callbacks[Feeds.TICKER]:
            try:
                ticker = self.tickers[symbol]
            except KeyError:
                self.tickers[symbol] = Ticker()
                ticker = self.tickers[symbol]

            # bybit instrument only use snapshot and update
            data = msg['data'] if msg['type'] == 'snapshot' else msg['data']['update'][0]
            has_new_ticker = False
            if 'last_price_e4' in data:
                if ticker.handle_last_price(self.fix_precision(data['last_price_e4'], 4)):
                    has_new_ticker = True
            if 'mark_price_e4' in data:
                if ticker.handle_mark_price(data['mark_price_e4']) and symbol in self.callbacks[Feeds.MARK_PRICE]:
                    await self.callbacks[Feeds.MARK_PRICE][symbol](mark_price=self.fix_precision(ticker.mark_price, 4))
            if 'funding_rate_e6' in data:
                if ticker.handle_funding(self.fix_precision(data['funding_rate_e6'], 6),
                                         data['next_funding_time']) and symbol in self.callbacks[Feeds.FUNDING]:
                    await self.callbacks[Feeds.FUNDING][symbol](funding_rate=ticker.funding_rate,
                                                                next_funding_time=ticker.next_funding_time,
                                                                timestamp=ticker.timestamp)
            if 'volume_24h' in data:
                if ticker.handle_24_ticker(high_24=self.fix_precision(data.get('high_price_24h_e4'), 4),
                                           low_24=self.fix_precision(data.get('low_price_24h_e4'), 4),
                                           open_24=self.fix_precision(data.get('prev_price_24h_e4'), 4),
                                           volume_24=data.get('volume_24h')):
                    has_new_ticker = True

            if has_new_ticker:
                await self.callbacks[Feeds.TICKER][symbol](ticker=ticker.to_dict())

    async def _position(self, msg: dict):
        if msg['data']:
            # TODO
            await self.callbacks[Feeds.POSITION](feed=self.get_name(), position={})

    async def on_message(self, json_message: str):
        """Handler for parsing WS messages."""
        parsed_message: dict = json.loads(json_message)
        try:
            if 'success' in parsed_message:
                if parsed_message["success"]:
                    if 'request' in parsed_message and parsed_message["request"]["op"] == 'auth':
                        self.on_auth(True)
                    if 'ret_msg' in parsed_message and parsed_message["ret_msg"] == 'pong':
                        self.on_pong()
                else:
                    if 'ret_msg' in parsed_message:
                        self.on_error(parsed_message["ret_msg"])

            if 'topic' in parsed_message:
                topic = parsed_message["topic"]

                if topic.startswith(self.get_L2_book_feed()):
                    await self._l2_book(parsed_message, symbol=self.get_topic_symbol(topic))

                elif topic.startswith(self.get_trades_feed()):
                    await self._trade(parsed_message, symbol=self.get_topic_symbol(topic))

                elif topic.startswith(self.get_ticker_feed()):
                    await self._ticker(parsed_message, symbol=self.get_topic_symbol(topic))

                elif topic.startswith(self.get_kline_feed()):
                    await self._kline(parsed_message,
                                      symbol=self.get_topic_symbol(topic),
                                      time_frame=self.get_topic_time_frame(self.get_kline_feed(), topic))

                elif topic.startswith(self.get_position_feed()):
                    await self._position(parsed_message)

                elif topic.startswith(self.get_orders_feed()):
                    await self._order(parsed_message)

                elif topic.startswith(self.get_execution_feed()):
                    await self._execution(parsed_message)
                else:
                    self.on_error(f"Unknown topic: {topic}")
        except Exception as e:
            self.on_error(f"Error when handling message {e}")
            self.logger.exception(e)

    async def subscribe(self):
        for channel in self.channels:
            if channel in self.PAIR_INDEPENDENT_CHANNELS:
                await self._send_command("subscribe", [channel])
            else:
                if channel == BybitFeeds.TICKER.value:
                    await self._send_command("subscribe", [
                        f"{BybitFeeds.TICKER.value}.{pair}"
                        for pair in self.pairs
                    ])
                elif channel == BybitFeeds.L2_BOOK.value:
                    await self._send_command("subscribe", [
                        f"{BybitFeeds.L2_BOOK.value}.{pair}"
                        for pair in self.pairs
                    ])
                elif channel == BybitFeeds.KLINE.value:
                    await self._send_command("subscribe", [
                        f"{BybitFeeds.KLINE.value}.{self.time_frame_to_interval(time_frame)}.{pair}"
                        for pair in self.pairs
                        for time_frame in self.time_frames
                    ])

    def get_topic_symbol(self, message_topic):
        # +1 for the "."
        return self.get_pair_from_exchange(message_topic[message_topic.rfind(".") + 1:])

    def get_topic_time_frame(self, topic_name, message_topic):
        return self.interval_to_time_frame(re.search(f"{topic_name}\.(.+?)\.", message_topic).group(1))

    def _parse_side(self, side):
        return BUY if side == BybitSide.BUY.value else SELL

    def fix_precision(self, price, exp):
        return price * 10 ** -exp if price else None

    async def _send_command(self, command, args=None):
        await self.websocket.send(json.dumps({"op": command, "args": args or []}))

    async def ping(self):
        await self._send_command(command="ping")

    async def do_auth(self):
        expires = self.generate_nonce()
        signature = self.generate_signature(expires)
        await self._send_command(command="auth", args=[self.api_key, expires, signature])

    @classmethod
    def get_name(cls):
        return 'bybit'

    @classmethod
    def get_ws_endpoint(cls):
        return 'wss://stream.bybit.com/realtime'

    @classmethod
    def get_ws_testnet_endpoint(cls):
        return 'wss://stream-testnet.bybit.com/realtime'

    @classmethod
    def get_endpoint(cls):
        return 'https://api.bybit.com'

    @classmethod
    def get_testnet_endpoint(cls):
        return 'https://api-testnet.bybit.com'

    @classmethod
    def get_ccxt_async_client(cls):
        return bybit

    @classmethod
    def get_L2_book_feed(cls):
        return BybitFeeds.L2_BOOK.value

    @classmethod
    def get_L3_book_feed(cls):
        return Feeds.UNSUPPORTED.value  #  'orderBookL2'

    @classmethod
    def get_trades_feed(cls):
        return BybitFeeds.TRADES.value

    @classmethod
    def get_ticker_feed(cls):
        return BybitFeeds.TICKER.value

    @classmethod
    def get_candle_feed(cls):
        return Feeds.KLINE.value

    @classmethod
    def get_kline_feed(cls):
        return BybitFeeds.KLINE.value

    @classmethod
    def get_funding_feed(cls):
        return Feeds.TICKER.value

    @classmethod
    def get_mark_price_feed(cls):
        return Feeds.TICKER.value

    @classmethod
    def get_margin_feed(cls):
        return Feeds.UNSUPPORTED.value

    @classmethod
    def get_position_feed(cls):
        return Feeds.POSITION.value

    @classmethod
    def get_portfolio_feed(cls):
        return Feeds.UNSUPPORTED.value

    @classmethod
    def get_orders_feed(cls):
        return BybitFeeds.ORDERS.value

    @classmethod
    def get_execution_feed(cls):
        return BybitFeeds.TRADE.value

    """
    Authentication
    from https://github.com/bybit-exchange/api-connectors/blob/master/official-ws/python/BybitWebsocket.py
    """

    def generate_nonce(self):
        return str(int(round(time.time()) + 1)) + "000"

    def generate_signature(self, expires):
        """Generate a request signature."""
        _val = 'GET/realtime' + expires
        return str(hmac.new(bytes(self.api_secret, "utf-8"), bytes(_val, "utf-8"), digestmod="sha256").hexdigest())

    def time_frame_to_interval(self, time_frame):
        tfm = TimeFramesMinutes[time_frame]
        if tfm > TimeFramesMinutes[TimeFrames.SIX_HOURS]:
            if time_frame == TimeFrames.ONE_DAY:
                return "D"
            if time_frame == TimeFrames.ONE_WEEK:
                return "W"
            if time_frame == TimeFrames.ONE_MONTH:
                return "M"
        return tfm

    def interval_to_time_frame(self, interval):
        try:
            time_frame_minute = int(interval)
            for time_frame, tfm in TimeFramesMinutes.items():
                if time_frame_minute == tfm:
                    return time_frame
        except ValueError:
            if interval == "D":
                return TimeFrames.ONE_DAY
            if interval == "W":
                return TimeFrames.ONE_WEEK
            if interval == "M":
                return TimeFrames.ONE_MONTH
        return None
