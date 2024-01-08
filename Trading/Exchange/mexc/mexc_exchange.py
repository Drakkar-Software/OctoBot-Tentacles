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
import contextlib
import decimal
import time
import typing
import ccxt

import octobot_trading.exchanges as exchanges
import octobot_trading.exchanges.connectors.ccxt.constants as ccxt_constants
import octobot_trading.enums as trading_enums
import octobot_trading.errors
import octobot_commons.symbols as symbols_util
import octobot_commons.constants as commons_constants


class MEXC(exchanges.RestExchange):
    FIX_MARKET_STATUS = True
    REMOVE_MARKET_STATUS_PRICE_LIMITS = True

    REQUIRE_ORDER_FEES_FROM_TRADES = True  # set True when get_order is not giving fees on closed orders and fees

    def __init__(self, config, exchange_manager, connector_class=None):
        super().__init__(config, exchange_manager, connector_class=connector_class)
        self.api_handled_symbols = APIHandledSymbols(self, commons_constants.DAYS_TO_SECONDS)

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
                "createMarketBuyOrderRequiresPrice": False,  # disable quote conversion
                "recvWindow": 60000,  # default is 5000, avoid time related issues
            }
        }

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

    async def _create_specific_order(self, order_type, symbol, quantity: decimal.Decimal, price: decimal.Decimal = None,
                                     side: trading_enums.TradeOrderSide = None, current_price: decimal.Decimal = None,
                                     stop_price: decimal.Decimal = None, reduce_only: bool = False,
                                     params=None) -> dict:
        async with self._mexc_handled_symbols_filter(symbol):
            return await super()._create_specific_order(order_type, symbol, quantity,
                                                        price=price, stop_price=stop_price,
                                                        side=side, current_price=current_price,
                                                        reduce_only=reduce_only, params=params)

    @contextlib.asynccontextmanager
    async def _mexc_handled_symbols_filter(self, symbol):
        try:
            yield
        except (ccxt.BadSymbol, ccxt.BadRequest) as err:
            if self.api_handled_symbols.should_be_updated():
                await self.api_handled_symbols.update()
            if symbol not in self.api_handled_symbols.symbols:
                raise octobot_trading.errors.FailedRequest(
                    f"{self.get_name()} error: {symbol} trading pair is not available to the API at the moment, "
                    f"{symbol} is under maintenance ({err}). "
                    f"API available trading pairs are {self.api_handled_symbols.symbols}"
                )
            raise err

    async def get_open_orders(self, symbol: str = None, since: int = None, limit: int = None, **kwargs: dict) -> list:
        return self._filter_orders(
            await super().get_open_orders(symbol=symbol, since=since, limit=limit, **kwargs),
            True
        )

    async def get_closed_orders(self, symbol: str = None, since: int = None, limit: int = None, **kwargs: dict) -> list:
        return self._filter_orders(
            await super().get_closed_orders(symbol=symbol, since=since, limit=limit, **kwargs),
            False
        )

    async def get_order(self, exchange_order_id: str, symbol: str = None, **kwargs: dict) -> dict:
        try:
            return await super().get_order(
                exchange_order_id, symbol=symbol, **kwargs
            )
        except octobot_trading.errors.FailedRequest as err:
            if "Order does not exist" in str(err):
                return None
            raise

    def _filter_orders(self, orders: list, open_only: bool) -> list:
        return [
            order
            for order in orders
            if (
                open_only and order[trading_enums.ExchangeConstantsOrderColumns.STATUS.value]
                == trading_enums.OrderStatus.OPEN.value
            ) or (
                not open_only and order[trading_enums.ExchangeConstantsOrderColumns.STATUS.value]
                != trading_enums.OrderStatus.OPEN.value
            )
        ]


class APIHandledSymbols:
    """
    MEXC has pairs that are sometimes tradable from the exchange UI but not from the API. Get the list of
    currently api tradable symbols from the defaultSymbols endpoint.
    """

    def __init__(self, exchange, update_interval):
        self.symbols = set()
        self.last_update = 0
        self._exchange = exchange
        self._update_interval = update_interval

    def should_be_updated(self):
        return time.time() - self._update_interval >= self._update_interval

    async def update(self):
        try:
            result = await self._exchange.connector.client.spot2PublicGetMarketApiDefaultSymbols()
            self.symbols = set(result["data"]["symbol"])
            self.last_update = time.time()
            self._exchange.logger.info(f"Updated handled symbols, list: {self.symbols}")
        except Exception as err:
            self._exchange.logger.exception(err, True, f"Error when fetching api-tradable symbols: {err}")


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
