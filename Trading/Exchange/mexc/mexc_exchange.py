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
import octobot_commons.symbols as symbols_util


class MEXC(exchanges.RestExchange):
    REQUIRE_ORDER_FEES_FROM_TRADES = True  # set True when get_order is not giving fees on closed orders and fees

    @classmethod
    def get_name(cls):
        return 'mexc'

    def get_adapter_class(self):
        return MEXCCCXTAdapter

    def get_additional_connector_config(self):
        # tell ccxt to use amount as provided and not to compute it by multiplying it by price which is done here
        # (price should not be sent to market orders). Only used for buy market orders
        return {
            ccxt_constants.CCXT_OPTIONS: {
                "createMarketBuyOrderRequiresPrice": False  # disable quote conversion
            }
        }

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer,
                                            remove_price_limits=True)

    async def create_order(self, order_type: trading_enums.TraderOrderType, symbol: str, quantity: decimal.Decimal,
                           price: decimal.Decimal = None, stop_price: decimal.Decimal = None,
                           side: trading_enums.TradeOrderSide = None, current_price: decimal.Decimal = None,
                           reduce_only: bool = False, params: dict = None) -> typing.Optional[dict]:
        if order_type is trading_enums.TraderOrderType.BUY_MARKET:
            # on MEXC, market orders are in quote currency (YYY in XYZ/YYY)
            used_price = price or current_price
            if not used_price:
                raise octobot_trading.errors.NotSupported(f"{self.get_name()} requires a price parameter to create "
                                                          f"market orders as quantity is in quote currency")
            quantity = quantity * used_price
        return await super().create_order(order_type, symbol, quantity,
                                          price=price, stop_price=stop_price,
                                          side=side, current_price=current_price,
                                          reduce_only=reduce_only, params=params)


class MEXCCCXTAdapter(exchanges.CCXTAdapter):

    def fix_order(self, raw, **kwargs):
        fixed = super().fix_order(raw, **kwargs)
        try:
            if fixed[
                trading_enums.ExchangeConstantsOrderColumns.STATUS.value
            ] == trading_enums.OrderStatus.CANCELED.value \
                    and fixed[trading_enums.ExchangeConstantsOrderColumns.FEE.value] is None:
                symbol = fixed.get(trading_enums.ExchangeConstantsOrderColumns.SYMBOL.value, "")
                fixed[trading_enums.ExchangeConstantsOrderColumns.FEE.value] = {
                    trading_enums.FeePropertyColumns.CURRENCY.value:
                        symbols_util.parse_symbol(symbol).quote if symbol else "",
                    trading_enums.FeePropertyColumns.COST.value: 0.0,
                    trading_enums.FeePropertyColumns.IS_FROM_EXCHANGE.value: False,
                    trading_enums.FeePropertyColumns.EXCHANGE_ORIGINAL_COST.value: 0.0,
                }
        except KeyError as err:
            self.logger.debug(f"Failed to fix order fees: {err}")
        return fixed
