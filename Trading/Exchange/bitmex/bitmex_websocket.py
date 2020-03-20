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
import urllib

import time
from ccxt.async_support import bitmex

from octobot_trading.constants import RECENT_TRADES_CHANNEL, ORDERS_CHANNEL, BALANCE_CHANNEL, \
    ORDER_BOOK_CHANNEL, TICKER_CHANNEL, MARK_PRICE_CHANNEL, FUNDING_CHANNEL, POSITIONS_CHANNEL
from octobot_trading.data.book import Book
from octobot_trading.enums import WebsocketFeeds as Feeds, ExchangeConstantsFundingColumns
from octobot_trading.exchanges.data.exchange_personal_data import TRADES_CHANNEL
from octobot_trading.exchanges.types.websocket_exchange import WebsocketExchange


class Bitmex(WebsocketExchange):
    EXCHANGE_FEEDS = {
        Feeds.FUNDING: Feeds.FUNDING.value,
        Feeds.MARK_PRICE: 'instrument',
        Feeds.L2_BOOK: 'orderBookL2_25',
        Feeds.BOOK_TICKER: 'quote',
        Feeds.TRADES: 'trade',
        Feeds.TICKER: 'instrument',
        Feeds.LIQUIDATIONS: 'liquidation',
        Feeds.POSITION: Feeds.POSITION.value,
        Feeds.ORDERS: 'order',
        Feeds.TRADE: 'execution',
        Feeds.PORTFOLIO: 'margin'
    }

    PAIR_INDEPENDENT_CHANNELS = [EXCHANGE_FEEDS[Feeds.TRADE], EXCHANGE_FEEDS[Feeds.POSITION],
                                 EXCHANGE_FEEDS[Feeds.ORDERS], EXCHANGE_FEEDS[Feeds.PORTFOLIO]]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.books = {}
        self.tickers = {}
        self.balance = {}

    async def _trade(self, msg: dict):
        if msg['data']:
            symbol = self.get_pair_from_exchange(msg['data'][0]['symbol'])
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

    async def _balance(self, msg: dict):
        if msg['data'] and msg['data'][0]:
            balance = msg['data'][0]
            currency = self.exchange.parse_currency(balance.get('currency'))

            try:
                self.balance[currency]
            except KeyError:
                self.balance[currency] = self.exchange.get_default_balance()

            account_balance = {'free': balance.get('availableMargin'), 'total': balance.get('marginBalance')}
            if currency == 'BTC':
                if account_balance['free']:
                    account_balance['free'] = account_balance['free'] * 0.00000001
                else:
                    account_balance.pop('free', None)
                if account_balance['total']:
                    account_balance['total'] = account_balance['total'] * 0.00000001
                else:
                    account_balance.pop('total', None)
            self.balance.update({currency: account_balance})
            await self.push_to_channel(BALANCE_CHANNEL, balance=self.balance)

    async def _l2_book(self, msg: dict, action: str):
        if msg['data']:
            symbol: str = self.get_pair_from_exchange(msg['data'][0]['symbol'])
            try:
                book = self.books[symbol]
            except KeyError:
                self.books[symbol] = Book()
                book = self.books[symbol]

            if action == 'partial':
                book.reset()
                book.handle_book_update(msg['data'])
            else:
                if action == 'delete':
                    book.handle_book_delta_delete(msg['data'])
                if action == 'insert':
                    book.handle_book_delta_insert(msg['data'])
                if action == 'update':
                    book.handle_book_delta_update(msg['data'])

            await self.push_to_channel(ORDER_BOOK_CHANNEL,
                                       symbol=symbol,
                                       asks=book.get_asks(side=self.exchange.SELL_STR),
                                       bids=book.get_bids(side=self.exchange.BUY_STR))

    async def _ticker(self, msg: dict, action: str):
        if msg['data'] and msg['data'][0]:
            symbol: str = self.get_pair_from_exchange(msg['data'][0]['symbol'])

            # ticker
            if action == 'insert':
                self.tickers[symbol] = self.exchange.parse_ticker(msg['data'][0])
            else:
                try:
                    self.tickers[symbol].update(msg['data'][0])
                except KeyError:
                    self.tickers[symbol] = self.exchange.parse_ticker(msg['data'][0])

            await self.push_to_channel(TICKER_CHANNEL,
                                       symbol=symbol,
                                       ticker=self.tickers[symbol])

            # mark_price
            if 'markPrice' in self.tickers[symbol]['info']:
                await self.push_to_channel(MARK_PRICE_CHANNEL,
                                           symbol=symbol,
                                           mark_price=self.tickers[symbol]['info']['markPrice'])

    async def _position(self, msg: dict):
        if msg['data']:
            await self.push_to_channel(POSITIONS_CHANNEL,
                                       positions=[self.exchange.parse_position(position) for position in msg['data']])

    async def _funding(self, msg: dict):
        if msg['data'] and msg['data'][0]:
            data = msg['data'][0]
            funding = self.exchange.parse_funding(data)
            await self.push_to_channel(FUNDING_CHANNEL,
                                       symbol=self.get_pair_from_exchange(data['symbol']),
                                       timestamp=funding[ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value],
                                       next_funding_time=funding[ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value],
                                       funding_rate=funding[ExchangeConstantsFundingColumns.FUNDING_RATE.value])

    async def on_message(self, json_message: str):
        parsed_message: dict = json.loads(json_message)
        table: str = parsed_message.get("table")
        action: str = parsed_message.get("action")

        try:
            if 'info' in parsed_message:
                self.logger.info(f"{self.get_name()}: info message : {parsed_message}")
            elif 'subscribe' in parsed_message:
                if not parsed_message['success']:
                    self.logger.error(f"{self.get_name()}: subscribed failed : {parsed_message}")
            elif 'status' in parsed_message:
                if parsed_message['status'] == 400:
                    self.logger.error(parsed_message['error'])
                if parsed_message['status'] == 401:
                    self.logger.error("API Key incorrect, please check and restart.")
            elif 'error' in parsed_message:
                self.logger.error(f"{self.get_name()}: Error message from exchange: {parsed_message}")
            elif action:
                await self._handle_action(action, table, parsed_message)

        except Exception as e:
            self.logger.error(f"Error when handling message {e}")
            raise e

    async def _handle_action(self, action: str, table: str, parsed_message: dict):
        if table == self.EXCHANGE_FEEDS[Feeds.TRADES]:
            await self._trade(parsed_message)

        elif table == self.EXCHANGE_FEEDS[Feeds.FUNDING]:
            await self._funding(parsed_message)

        elif table == self.EXCHANGE_FEEDS[Feeds.TICKER]:
            await self._ticker(parsed_message, action)

        elif table == self.EXCHANGE_FEEDS[Feeds.POSITION]:
            # await self._position(parsed_message)
            pass

        elif table == self.EXCHANGE_FEEDS[Feeds.ORDERS]:
            await self._order(parsed_message)

        elif table == self.EXCHANGE_FEEDS[Feeds.TRADE]:
            await self._execution(parsed_message)

        elif table == self.EXCHANGE_FEEDS[Feeds.L2_BOOK]:
            await self._l2_book(parsed_message, action)

        elif table == self.EXCHANGE_FEEDS[Feeds.PORTFOLIO]:
            await self._balance(parsed_message)
        else:
            print(parsed_message)
            self.on_error(f"Unknown action: {action} for table : {table}")

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

    async def ping(self):
        await super().ping()

    @classmethod
    def get_name(cls):
        return 'bitmex'

    @classmethod
    def get_ws_endpoint(cls):
        return 'wss://www.bitmex.com/realtime'

    @classmethod
    def get_ws_testnet_endpoint(cls):
        return 'wss://testnet.bitmex.com/realtime'

    @classmethod
    def get_endpoint(cls):
        return 'https://www.bitmex.com/api/v1'

    @classmethod
    def get_testnet_endpoint(cls):
        return 'https://testnet.bitmex.com/api/v1'

    @classmethod
    def get_ccxt_async_client(cls):
        return bitmex

    @classmethod
    def is_handling_future(cls):
        return True

    """
    Authentication
    from https://github.com/BitMEX/api-connectors/blob/master/official-ws/python/util/api_key.py
    """

    def generate_nonce(self):
        return int(round(time.time() + 3600))

    def generate_signature(self, verb, url, nonce, post_dict=None):
        data = ''
        if post_dict:
            data = json.dumps(post_dict, separators=(',', ':'))
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        if parsed_url.query:
            path = path + '?' + parsed_url.query
        message = (verb + path + str(nonce) + data).encode('utf-8')
        return hmac.new(self.api_secret.encode('utf-8'), message, digestmod=hashlib.sha256).hexdigest()
