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


class BinanceSpotMarginLending(Binance):

    @classmethod
    def get_endpoint(cls):
        return 'https://api.binance.com/api'

    @classmethod
    def get_testnet_endpoint(cls):
        return 'https://testnet.bitmex.com/api/v1'

    @classmethod
    def get_ws_endpoint(cls):
        return 'wss://stream.binance.com:9443'

    @classmethod
    def get_ws_testnet_endpoint(cls):
        return 'wss://testnet.bitmex.com/realtime'
