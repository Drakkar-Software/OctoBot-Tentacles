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


class HuobiConnectorSettings(ccxt_exchange_settings.CCXTExchangeConfig):
    USE_FIXED_MARKET_STATUS = True
    MARKET_STATUS_FIXER_REMOVE_PRICE_LIMITS = True
    

class Huobi(exchanges.SpotCCXTExchange):
    CONNECTOR_SETTINGS = HuobiConnectorSettings

    @classmethod
    def get_name(cls):
        return 'huobi'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return exchange_candidate_name == cls.get_name()
