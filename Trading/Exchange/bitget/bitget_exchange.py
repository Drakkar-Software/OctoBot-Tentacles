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
import decimal
import typing

import octobot_trading.exchanges as exchanges
import octobot_trading.enums as trading_enums
import octobot_trading.errors
from octobot_trading.exchanges.config import ccxt_exchange_settings


class BitgetConnectorSettings(ccxt_exchange_settings.CCXTExchangeConfig):
    MARKET_STATUS_FIX_PRECISION = True


class _BitgetCCXTExchange(exchanges.CCXTExchange):
    def get_client_time_frames(self):
        # on Bitget, it is necessary to specify the instrument type to get timeframes
        # use client.timeframes["spot"]
        return set(self.client.timeframes["spot"])


class Bitget(exchanges.SpotCCXTExchange):    
    CONNECTOR_SETTINGS = BitgetConnectorSettings
    CONNECTOR_CLASS = _BitgetCCXTExchange
    DESCRIPTION = ""

    @classmethod
    def get_name(cls):
        return 'bitget'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def create_order(self, order_type: trading_enums.TraderOrderType, symbol: str, quantity: decimal.Decimal,
                           price: decimal.Decimal = None, stop_price: decimal.Decimal = None,
                           side: trading_enums.TradeOrderSide = None, current_price: decimal.Decimal = None,
                           params: dict = None) -> typing.Optional[dict]:
        # tell ccxt to use amount as provided and not to compute it by multiplying it by price which is done here
        # (price should not be sent to market orders). Only used for buy market orders
        self.connector.add_options({"createMarketBuyOrderRequiresPrice": False})
        if order_type is trading_enums.TraderOrderType.BUY_MARKET:
            # on Bitget, market orders are in quote currency (YYY in XYZ/YYY)
            if price is None:
                raise octobot_trading.errors.NotSupported(f"{self.get_name()} requires a price parameter to create "
                                                          f"market orders as quantity is in quote currency")
            quantity = quantity * price
        return await super().create_order(order_type, symbol, quantity, price=price, stop_price=stop_price,
                                          side=side, current_price=current_price, params=params)
