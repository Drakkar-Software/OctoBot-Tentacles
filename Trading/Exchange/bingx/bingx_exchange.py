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
import typing

import octobot_commons.enums

import octobot_trading.exchanges as exchanges


class Bingx(exchanges.RestExchange):
    # ccxt 4.0.65: bingx websocket not yet supported
    FIX_MARKET_STATUS = True

    def get_adapter_class(self):
        return BingxCCXTAdapter

    @classmethod
    def get_name(cls) -> str:
        return 'bingx'


class BingxCCXTAdapter(exchanges.CCXTAdapter):
    pass
