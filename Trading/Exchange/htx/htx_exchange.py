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
import octobot_trading.exchanges.connectors.ccxt.constants as ccxt_constants
import octobot_trading.enums as trading_enums
import octobot_trading.errors


class Htx(exchanges.RestExchange):
    FIX_MARKET_STATUS = True
    REMOVE_MARKET_STATUS_PRICE_LIMITS = True

    @classmethod
    def get_name(cls):
        return 'htx'

    def get_adapter_class(self):
        return HtxCCXTAdapter

    def get_additional_connector_config(self):
        # tell ccxt to use amount as provided and not to compute it by multiplying it by price which is done here
        # (price should not be sent to market orders). Only used for buy market orders
        return {
            ccxt_constants.CCXT_OPTIONS: {
                "createMarketBuyOrderRequiresPrice": False  # disable quote conversion
            }
        }

    async def create_order(self, order_type: trading_enums.TraderOrderType, symbol: str, quantity: decimal.Decimal,
                           price: decimal.Decimal = None, stop_price: decimal.Decimal = None,
                           side: trading_enums.TradeOrderSide = None, current_price: decimal.Decimal = None,
                           reduce_only: bool = False, params: dict = None) -> typing.Optional[dict]:
        if order_type is trading_enums.TraderOrderType.BUY_MARKET:
            # on HTX, market orders are in quote currency (YYY in XYZ/YYY)
            used_price = price or current_price
            if not used_price:
                raise octobot_trading.errors.NotSupported(f"{self.get_name()} requires a price parameter to create "
                                                          f"market orders as quantity is in quote currency")
            quantity = quantity * used_price
        return await super().create_order(order_type, symbol, quantity,
                                          price=price, stop_price=stop_price,
                                          side=side, current_price=current_price,
                                          reduce_only=reduce_only, params=params)


class HtxCCXTAdapter(exchanges.CCXTAdapter):

    def fix_order(self, raw, **kwargs):
        fixed = super().fix_order(raw, **kwargs)
        try:
            if fixed[trading_enums.ExchangeConstantsOrderColumns.TYPE.value] \
                    == trading_enums.TradeOrderType.MARKET.value and \
                    fixed[trading_enums.ExchangeConstantsOrderColumns.SIDE.value] \
                    == trading_enums.TradeOrderSide.BUY.value:
                # convert amount to have the same units as evert other exchange: use FILLED for accuracy
                fixed[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] = \
                    fixed[trading_enums.ExchangeConstantsOrderColumns.FILLED.value]
        except KeyError:
            pass
        return fixed
