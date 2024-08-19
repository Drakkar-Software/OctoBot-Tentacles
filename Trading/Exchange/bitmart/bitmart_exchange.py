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


class BitMartConnector(exchanges.CCXTConnector):

    def _client_factory(self, force_unauth, keys_adapter=None) -> tuple:
        return super()._client_factory(force_unauth, keys_adapter=self._keys_adapter)

    def _keys_adapter(self, key, secret, password, uid):
        # use password as uid
        return key, secret, "", password


class BitMart(exchanges.RestExchange):
    FIX_MARKET_STATUS = True
    DEFAULT_CONNECTOR_CLASS = BitMartConnector

    @classmethod
    def get_name(cls):
        return 'bitmart'

    def get_adapter_class(self):
        return BitMartCCXTAdapter


class BitMartCCXTAdapter(exchanges.CCXTAdapter):
    pass
