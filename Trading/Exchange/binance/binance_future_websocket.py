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

from .binance_websocket import Binance
from octobot_trading.enums import WebsocketFeeds as Feeds


class BinanceFuture(Binance):
    EXCHANGE_FEEDS = Binance.EXCHANGE_FEEDS.update({
        Feeds.MARK_PRICE: 'markPrice@1s',
        Feeds.FUNDING: 'markPrice@1s',  # provided with mark price
        Feeds.LIQUIDATIONS: 'forceOrder'
    })

    @classmethod
    def get_endpoint(cls):
        return 'https://fapi.binance.com/fapi'

    @classmethod
    def get_testnet_endpoint(cls):
        return 'https://testnet.binancefuture.com'

    @classmethod
    def get_ws_endpoint(cls):
        return 'wss://stream.binancefuture.com'  # or maybe wss://fstream.binance.com/ws

    @classmethod
    def get_ws_testnet_endpoint(cls):
        return 'wss://testnet.bitmex.com/realtime'
