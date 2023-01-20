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
import octobot_trading.exchanges as exchanges
from octobot_trading.enums import WebsocketFeeds as Feeds
import tentacles.Trading.Exchange.kucoin.kucoin_exchange as kucoin_exchange


class KucoinCCXTWebsocketConnector(exchanges.CCXTWebsocketConnector):
    EXCHANGE_FEEDS = {
        Feeds.TRADES: True,
        Feeds.KLINE: True,
        Feeds.TICKER: True,
        Feeds.CANDLE: True,
    }
    FUTURES_EXCHANGE_FEEDS = {
        Feeds.TRADES: True,
        Feeds.KLINE: Feeds.UNSUPPORTED.value,  # not supported in futures
        Feeds.TICKER: True,
        Feeds.CANDLE: Feeds.UNSUPPORTED.value,  # not supported in futures
    }

    @classmethod
    def get_name(cls):
        return kucoin_exchange.Kucoin.get_name()

    def get_feed_name(self):
        if self.exchange_manager.is_future:
            return kucoin_exchange.Kucoin.FUTURES_CCXT_CLASS_NAME
        return super().get_feed_name()

    @classmethod
    def update_exchange_feeds(cls, exchange_manager):
        if exchange_manager.is_future:
            cls.EXCHANGE_FEEDS = cls.FUTURES_EXCHANGE_FEEDS

    def get_adapter_class(self, adapter_class):
        return kucoin_exchange.KucoinCCXTAdapter
