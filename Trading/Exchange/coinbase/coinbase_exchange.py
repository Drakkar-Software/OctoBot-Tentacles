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
import decimal

import octobot_trading.errors
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges
import octobot_commons.enums as commons_enums
import octobot_commons.constants as commons_constants
import octobot_commons.symbols as commons_symbols


class Coinbase(exchanges.RestExchange):
    MAX_PAGINATION_LIMIT: int = 300
    REQUIRES_AUTHENTICATION = True

    FIX_MARKET_STATUS = True

    @classmethod
    def get_name(cls):
        return 'coinbase'

    def get_adapter_class(self):
        return CoinbaseCCXTAdapter

    async def get_symbol_prices(self, symbol: str, time_frame: commons_enums.TimeFrames, limit: int = None,
                                **kwargs: dict) -> typing.Optional[list]:
        return await super().get_symbol_prices(
            symbol=symbol, time_frame=time_frame, **self._get_ohlcv_params(time_frame, limit, **kwargs)
        )

    async def create_order(self, order_type: trading_enums.TraderOrderType, symbol: str, quantity: decimal.Decimal,
                           price: decimal.Decimal = None, stop_price: decimal.Decimal = None,
                           side: trading_enums.TradeOrderSide = None, current_price: decimal.Decimal = None,
                           reduce_only: bool = False, params: dict = None) -> typing.Optional[dict]:
        # ccxt is converting quantity using price, make sure it's available
        if order_type is trading_enums.TraderOrderType.BUY_MARKET and not current_price:
            raise octobot_trading.errors.NotSupported(f"current_price is required for {order_type} orders")
        return await super().create_order(order_type, symbol, quantity,
                                          price=price, stop_price=stop_price,
                                          side=side, current_price=current_price,
                                          reduce_only=reduce_only, params=params)

    def _get_ohlcv_params(self, time_frame, limit, **kwargs):
        # to be added in tentacle
        limit = min(self.MAX_PAGINATION_LIMIT, limit) if limit else self.MAX_PAGINATION_LIMIT
        time_frame_sec = commons_enums.TimeFramesMinutes[time_frame] * commons_constants.MSECONDS_TO_MINUTE
        to_time = self.connector.client.milliseconds()
        kwargs.update({
            "since": to_time - (time_frame_sec * limit),
            "limit": limit,
        })
        return kwargs


class CoinbaseCCXTAdapter(exchanges.CCXTAdapter):

    def _register_exchange_fees(self, order_or_trade):
        super()._register_exchange_fees(order_or_trade)
        try:
            fees = order_or_trade[trading_enums.ExchangeConstantsOrderColumns.FEE.value]
            if not fees[trading_enums.FeePropertyColumns.CURRENCY.value]:
                # fees currency are not provided, they are always in quote on Coinbase
                fees[trading_enums.FeePropertyColumns.CURRENCY.value] = commons_symbols.parse_symbol(
                    order_or_trade[trading_enums.ExchangeConstantsOrderColumns.SYMBOL.value]
                ).quote
        except (KeyError, TypeError):
            pass

    def fix_trades(self, raw, **kwargs):
        raw = super().fix_trades(raw, **kwargs)
        for trade in raw:
            trade[trading_enums.ExchangeConstantsOrderColumns.STATUS.value] = trading_enums.OrderStatus.CLOSED.value
            try:
                if trade[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] is None and \
                        trade[trading_enums.ExchangeConstantsOrderColumns.COST.value] and \
                        trade[trading_enums.ExchangeConstantsOrderColumns.PRICE.value]:
                    # convert amount to have the same units as evert other exchange: use FILLED for accuracy
                    trade[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] = \
                        trade[trading_enums.ExchangeConstantsOrderColumns.COST.value] / \
                        trade[trading_enums.ExchangeConstantsOrderColumns.PRICE.value]
            except KeyError:
                pass
        return raw
