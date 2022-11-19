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
from octobot_trading.exchanges.config import ccxt_exchange_settings


class GateIOConnectorSettings(ccxt_exchange_settings.CCXTExchangeConfig):
    MAX_RECENT_TRADES_PAGINATION_LIMIT = 100
    MAX_ORDERS_PAGINATION_LIMIT = 100
    MARKET_STATUS_FIX_PRECISION = True
    MARKET_STATUS_REMOVE_INVALID_PRICE_LIMITS = True


class GateIO(exchanges.SpotCCXTExchange):
    CONNECTOR_SETTINGS = GateIOConnectorSettings

    @classmethod
    def get_name(cls):
        return "gateio"

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return exchange_candidate_name == cls.get_name()
