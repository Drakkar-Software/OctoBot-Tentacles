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
import octobot_commons.constants as constants


# TODO later: find a way to store this in exchange tentacles instead and use exchange.get_default_reference_market
# Issue: hollaex based exchanages require an exchange configuration to be identified as such 
_SPECIFIC_REFERENCE_MARKET_PER_EXCHANGE = {
    "coinbase": "USDC",
    "binance": "USDC",
}

def get_default_reference_market_per_exchange(exchanges: list[str]) -> dict[str, str]:
    return {exchange: get_default_exchange_reference_market(exchange) for exchange in exchanges}

def get_default_exchange_reference_market(exchange: str) -> str:
    return _SPECIFIC_REFERENCE_MARKET_PER_EXCHANGE.get(exchange, constants.DEFAULT_REFERENCE_MARKET)
