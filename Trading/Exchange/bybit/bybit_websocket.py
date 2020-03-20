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

import time
from ccxt.async_support import bybit

from octobot_commons.enums import TimeFramesMinutes, TimeFrames
from octobot_trading.constants import ORDER_BOOK_CHANNEL, TICKER_CHANNEL, MARK_PRICE_CHANNEL, \
    TRADES_CHANNEL, ORDERS_CHANNEL, RECENT_TRADES_CHANNEL, KLINE_CHANNEL, OHLCV_CHANNEL, FUNDING_CHANNEL, \
    POSITIONS_CHANNEL
from octobot_trading.data.book import Book
from octobot_trading.enums import ExchangeConstantsTickersColumns, ExchangeConstantsFundingColumns
from octobot_trading.enums import WebsocketFeeds as Feeds
from octobot_trading.exchanges.types.websocket_exchange import WebsocketExchange


class ByBit(WebsocketExchange):
    EXCHANGE_FEEDS = {
        Feeds.FUNDING: Feeds.UNSUPPORTED.value,  # in Ticker
        Feeds.MARK_PRICE: Feeds.UNSUPPORTED.value,  # in Ticker
        Feeds.L2_BOOK: 'orderBookL2_25',
        Feeds.TRADES: 'trade',
        Feeds.TICKER: 'instrument_info.100ms',
        Feeds.KLINE: 'klineV2',
        Feeds.POSITION: Feeds.POSITION.value,
        Feeds.ORDERS: 'order',
        Feeds.TRADE: 'execution',
    }

    PAIR_INDEPENDENT_CHANNELS = [EXCHANGE_FEEDS[Feeds.TRADES], EXCHANGE_FEEDS[Feeds.POSITION],
                                 EXCHANGE_FEEDS[Feeds.TRADE], EXCHANGE_FEEDS[Feeds.ORDERS]]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.books = {}
        self.tickers = {}
        self.funding = {}

    async def _trade(self, msg: dict, symbol: str):
        if msg['data']:
            await self.push_to_channel(RECENT_TRADES_CHANNEL,
                                       symbol=symbol,
                                       recent_trades=[self.exchange.parse_trade(trade) for trade in msg['data']])

    async def _order(self, msg: dict):
        if msg['data']:
            await self.push_to_channel(ORDERS_CHANNEL,
                                       orders=[self.exchange.parse_order(order) for order in msg['data']])

    async def _execution(self, msg: dict):
        if msg['data']:
            await self.push_to_channel(TRADES_CHANNEL,
                                       trades=[self.exchange.parse_trade(trade) for trade in msg['data']])

    async def _kline(self, msg: dict, symbol: str, time_frame):
        if msg['data']:
            klines: list = msg['data']
            if klines[0]['confirm']:
                await self.push_to_channel(OHLCV_CHANNEL, time_frame=time_frame, symbol=symbol,
                                           candle=self.exchange.parse_ohlcv(klines[0]))
                klines.pop(0)
            if klines:
                await self.push_to_channel(KLINE_CHANNEL, time_frame=time_frame, symbol=symbol,
                                           kline=self.exchange.parse_ohlcv(klines[0]))

    async def _l2_book(self, msg: dict, symbol: str):
        if msg['data'] and symbol:
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

            await self.push_to_channel(ORDER_BOOK_CHANNEL,
                                       symbol=symbol,
                                       asks=book.get_asks(side=self.exchange.SELL_STR),
                                       bids=book.get_bids(side=self.exchange.BUY_STR))

    async def _ticker(self, msg: dict, symbol: str):
        if msg['data'] and symbol:
            try:
                self.tickers[symbol]
            except KeyError:
                self.tickers[symbol] = {}

            # bybit instrument only use snapshot and update
            data = msg['data'] if msg['type'] == 'snapshot' else msg['data']['update'][0]
            has_new_ticker = False
            if 'last_price_e4' in data:
                has_new_ticker = True
                self.tickers[symbol].update({ExchangeConstantsTickersColumns.LAST.value:
                                                 self.fix_precision(data['last_price_e4'], 4)})
            if 'mark_price_e4' in data:
                await self.push_to_channel(MARK_PRICE_CHANNEL, symbol=symbol,
                                           mark_price=self.fix_precision(data['mark_price_e4'], 4))

            if 'funding_rate_e6' in data:
                await self._parse_funding(symbol, data)
            if 'volume_24h' in data:
                has_new_ticker = True
                self.tickers[symbol].update({
                    ExchangeConstantsTickersColumns.HIGH.value: self.fix_precision(
                        data.get('high_price_24h_e4'), 4),
                    ExchangeConstantsTickersColumns.LOW.value: self.fix_precision(
                        data.get('low_price_24h_e4'), 4),
                    ExchangeConstantsTickersColumns.OPEN.value: self.fix_precision(
                        data.get('prev_price_24h_e4'), 4),
                    ExchangeConstantsTickersColumns.QUOTE_VOLUME.value: data.get('volume_24h')})

            if has_new_ticker:
                await self.push_to_channel(TICKER_CHANNEL, symbol=symbol, ticker=self.tickers[symbol])

    async def _parse_funding(self, symbol: str, data: dict):
        try:
            self.funding[symbol]
        except KeyError:
            self.funding[symbol] = {}
        self.funding[symbol].update(self.exchange.parse_funding({
            ExchangeConstantsFundingColumns.FUNDING_RATE.value: self.fix_precision(data['funding_rate_e6'], 6),
            ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value: data['next_funding_time']
        }))
        await self.push_to_channel(FUNDING_CHANNEL,
                                   symbol=symbol,
                                   funding_rate=self.funding[symbol][ExchangeConstantsFundingColumns.FUNDING_RATE.value],
                                   next_funding_time=
                                   self.funding[symbol][ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value],
                                   timestamp=
                                   self.funding[symbol][ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value])

    async def _position(self, msg: dict):
        if msg['data']:
            await self.push_to_channel(POSITIONS_CHANNEL,
                                       positions=[self.exchange.parse_position(position) for position in
                                                  msg['data']])

    async def on_message(self, json_message: str):
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

                if topic.startswith(self.EXCHANGE_FEEDS[Feeds.L2_BOOK]):
                    await self._l2_book(parsed_message, symbol=self.get_topic_symbol(topic))

                elif topic.startswith(self.EXCHANGE_FEEDS[Feeds.TRADES]):
                    await self._trade(parsed_message, symbol=self.get_topic_symbol(topic))

                elif topic.startswith(self.EXCHANGE_FEEDS[Feeds.TICKER]):
                    await self._ticker(parsed_message, symbol=self.get_topic_symbol(topic))

                elif topic.startswith(self.EXCHANGE_FEEDS[Feeds.KLINE]):
                    await self._kline(parsed_message,
                                      symbol=self.get_topic_symbol(topic),
                                      time_frame=self.get_topic_time_frame(self.EXCHANGE_FEEDS[Feeds.KLINE], topic))

                elif topic.startswith(self.EXCHANGE_FEEDS[Feeds.POSITION]):
                    await self._position(parsed_message)

                elif topic.startswith(self.EXCHANGE_FEEDS[Feeds.ORDERS]):
                    await self._order(parsed_message)

                elif topic.startswith(self.EXCHANGE_FEEDS[Feeds.TRADE]):
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
                if channel == self.get_exchange_feed(Feeds.TICKER):
                    await self._send_command("subscribe", [
                        f"{self.get_exchange_feed(Feeds.TICKER)}.{pair}"
                        for pair in self.pairs
                    ])
                elif channel == self.get_exchange_feed(Feeds.L2_BOOK):
                    await self._send_command("subscribe", [
                        f"{self.get_exchange_feed(Feeds.L2_BOOK)}.{pair}"
                        for pair in self.pairs
                    ])
                elif channel == self.get_exchange_feed(Feeds.KLINE):
                    await self._send_command("subscribe", [
                        f"{self.get_exchange_feed(Feeds.KLINE)}.{self.time_frame_to_interval(time_frame)}.{pair}"
                        for pair in self.pairs
                        for time_frame in self.time_frames
                    ])

    def get_topic_symbol(self, message_topic):
        # +1 for the "."
        return self.get_pair_from_exchange(message_topic[message_topic.rfind(".") + 1:])

    def get_topic_time_frame(self, topic_name, message_topic):
        return self.interval_to_time_frame(re.search(f"{topic_name}\.(.+?)\.", message_topic).group(1))

    def fix_precision(self, price, exp):
        return price * 10 ** -exp if price else None

    async def _send_command(self, command, args=None):
        await self.websocket.send(json.dumps({"op": command, "args": args or []}))

    async def ping(self):
        await super().ping()
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
    def is_handling_future(cls):
        return True

    """
    Authentication
    from https://github.com/bybit-exchange/api-connectors/blob/master/official-ws/python/BybitWebsocket.py
    """

    def generate_nonce(self):
        return str(int(round(time.time()) + 1) * 1000)

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
