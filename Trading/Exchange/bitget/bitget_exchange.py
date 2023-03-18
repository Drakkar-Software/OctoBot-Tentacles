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
import time

import octobot_trading.exchanges as exchanges
import octobot_trading.enums as trading_enums
import octobot_trading.errors


class Bitget(exchanges.RestExchange):
    DESCRIPTION = ""
    REQUIRE_ORDER_FEES_FROM_TRADES = True  # set True when get_order is not giving fees on closed orders and fees

    @classmethod
    def get_name(cls):
        return 'bitget'

    def get_adapter_class(self):
        return BitgetCCXTAdapter

    async def get_symbol_prices(self, symbol, time_frame, limit: int = None, **kwargs: dict):
        if "since" in kwargs:
            # prevent ccxt from fillings the end param (not working when trying to get the 1st candle times)
            kwargs["until"] = int(time.time() * 1000)
        return await super().get_symbol_prices(symbol=symbol, time_frame=time_frame, limit=limit, **kwargs)

    async def create_order(self, order_type: trading_enums.TraderOrderType, symbol: str, quantity: decimal.Decimal,
                           price: decimal.Decimal = None, stop_price: decimal.Decimal = None,
                           side: trading_enums.TradeOrderSide = None, current_price: decimal.Decimal = None,
                           reduce_only: bool = False, params: dict = None) -> typing.Optional[dict]:
        # tell ccxt to use amount as provided and not to compute it by multiplying it by price which is done here
        # (price should not be sent to market orders). Only used for buy market orders
        self.connector.add_options({"createMarketBuyOrderRequiresPrice": False})
        if order_type is trading_enums.TraderOrderType.BUY_MARKET:
            # on Bitget, market orders are in quote currency (YYY in XYZ/YYY)
            used_price = price or current_price
            if not used_price:
                raise octobot_trading.errors.NotSupported(f"{self.get_name()} requires a price parameter to create "
                                                          f"market orders as quantity is in quote currency")
            quantity = quantity * used_price
        return await super().create_order(order_type, symbol, quantity,
                                          price=price, stop_price=stop_price,
                                          side=side, current_price=current_price,
                                          reduce_only=reduce_only, params=params)

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer,
                                            remove_price_limits=True)


class BitgetCCXTAdapter(exchanges.CCXTAdapter):

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

    def fix_trades(self, raw, **kwargs):
        raw = super().fix_trades(raw, **kwargs)
        for trade in raw:
            # fees example for paid fees in USDT:
            # {'code': 'USDT', 'cost': -0.015922}
            fee = trade[trading_enums.ExchangeConstantsOrderColumns.FEE.value]
            if trading_enums.FeePropertyColumns.CURRENCY.value not in fee:
                fee[trading_enums.FeePropertyColumns.CURRENCY.value] = fee.get("code")
            if fee[trading_enums.FeePropertyColumns.COST.value]:
                fee[trading_enums.FeePropertyColumns.COST.value] *= -1
        return raw
