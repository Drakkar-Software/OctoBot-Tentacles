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

import octobot_trading.exchanges as exchanges
import octobot_trading.exchanges.connectors.ccxt.constants as ccxt_constants


class PolymarketConnector(exchanges.CCXTConnector):

    def _client_factory(
        self,
        force_unauth,
        keys_adapter: typing.Callable[[exchanges.ExchangeCredentialsData], exchanges.ExchangeCredentialsData]=None
    ) -> tuple:
        return super()._client_factory(force_unauth, keys_adapter=self._keys_adapter)

    def _keys_adapter(self, creds: exchanges.ExchangeCredentialsData) -> exchanges.ExchangeCredentialsData:
        # if api key and secret are provided, use them as wallet address and private key
        creds.wallet_address = creds.api_key
        creds.uid = creds.password
        creds.private_key = creds.secret
        creds.api_key = creds.secret = creds.password = None
        return creds

class Polymarket(exchanges.RestExchange):
    DESCRIPTION = ""
    DEFAULT_CONNECTOR_CLASS = PolymarketConnector

    SUPPORT_FETCHING_CANCELLED_ORDERS = False

    @classmethod
    def get_name(cls):
        return 'polymarket'

    def get_additional_connector_config(self):
        return {
            ccxt_constants.CCXT_OPTIONS: {
                "fetchMarkets": {
                    "types": ["option"],  # only polymarket option markets are supported
                }
            }
        }
