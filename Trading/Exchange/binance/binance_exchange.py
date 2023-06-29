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

import ccxt

import octobot_trading.enums as trading_enums
import octobot_trading.constants as constants
import octobot_trading.exchanges as exchanges
import octobot_trading.errors as errors
import octobot_trading.exchanges.connectors.ccxt.constants as ccxt_constants


class Binance(exchanges.RestExchange):
    DESCRIPTION = ""
    REQUIRE_ORDER_FEES_FROM_TRADES = True  # set True when get_order is not giving fees on closed orders and fees
    # should be fetched using recent trades.
    SUPPORTS_SET_MARGIN_TYPE_ON_OPEN_POSITIONS = False  # set False when the exchange refuses to change margin type
    # when an associated position is open
    # binance {"code":-4048,"msg":"Margin type cannot be changed if there exists position."}

    BUY_STR = "BUY"
    SELL_STR = "SELL"
    INVERSE_TYPE = "inverse"
    LINEAR_TYPE = "linear"

    @classmethod
    def get_name(cls):
        return 'binance'

    def get_adapter_class(self):
        return BinanceCCXTAdapter

    @classmethod
    def get_supported_exchange_types(cls) -> list:
        """
        :return: The list of supported exchange types
        """
        return [
            trading_enums.ExchangeTypes.SPOT,
            trading_enums.ExchangeTypes.FUTURE,
        ]

    def _get_future_account_types(self):
        return [
            self.LINEAR_TYPE,   # allows to fetch linear markets
            self.INVERSE_TYPE   # allows to fetch inverse markets
        ]

    def get_additional_connector_config(self):
        config = {
            ccxt_constants.CCXT_OPTIONS: {
                "quoteOrderQty": False,  # disable quote conversion
                "recvWindow": 60000,    # default is 10000, avoid time related issues
            }
        }
        if self.exchange_manager.is_future:
            config[ccxt_constants.CCXT_OPTIONS]['fetchMarkets'] = self._get_future_account_types()
        return config

    async def get_balance(self, **kwargs: dict):    #todo handle in different portfolio
        if self.exchange_manager.is_future:
            balance = []
            for account_type in self._get_future_account_types():
                balance.append(await self.connector.get_balance(**kwargs, subType=account_type))
            # pb: meme asset mais pas meme balance
            return balance[0]   # only returning linear portfolio
        return await self.connector.get_balance(**kwargs)

    async def create_order(self, order_type: trading_enums.TraderOrderType, symbol: str, quantity: decimal.Decimal,
                           price: decimal.Decimal = None, stop_price: decimal.Decimal = None,
                           side: trading_enums.TradeOrderSide = None, current_price: decimal.Decimal = None,
                           reduce_only: bool = False, params: dict = None) -> typing.Optional[dict]:
        if self.exchange_manager.is_future:
            # on futures exchange expects, quantity in contracts: convert quantity into contracts
            quantity = quantity / self.get_contract_size(symbol)
        return await super().create_order(order_type, symbol, quantity,
                                          price=price, stop_price=stop_price,
                                          side=side, current_price=current_price,
                                          reduce_only=reduce_only, params=params)

    async def get_positions(self, symbols=None, **kwargs: dict) -> list:
        positions = []
        if "subType" in kwargs:
            return _filter_positions(await super().get_positions(symbols=symbols, **kwargs))
        for account_type in self._get_future_account_types():
            kwargs["subType"] = account_type
            positions += await super().get_positions(symbols=symbols, **kwargs)
        return _filter_positions(positions)

    async def get_position(self, symbol: str, **kwargs: dict) -> dict:
        # fetchPosition() supports option markets only
        # => use get_positions
        return (await self.get_positions(symbols=[symbol], **kwargs))[0]

    async def get_symbol_leverage(self, symbol: str, **kwargs: dict):
        """
        :param symbol: the symbol
        :return: the current symbol leverage multiplier
        """
        # leverage is in position
        return self.connector.adapter.adapt_leverage(await self.get_position(symbol))

    async def set_symbol_margin_type(self, symbol: str, isolated: bool, **kwargs: dict):
        """
        Set the symbol margin type
        :param symbol: the symbol
        :param isolated: when False, margin type is cross, else it's isolated
        :return: the update result
        """
        try:
            return await super(). set_symbol_margin_type(symbol, isolated, **kwargs)
        except ccxt.ExchangeError as err:
            raise errors.NotSupported() from err


class BinanceCCXTAdapter(exchanges.CCXTAdapter):

    def fix_order(self, raw, symbol=None, **kwargs):
        fixed = super().fix_order(raw, **kwargs)
        if self.connector.exchange_manager.is_future \
                and fixed[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] is not None:
            # amount is in contact, multiply by contract value to get the currency amount (displayed to the user)
            contract_size = self.connector.get_contract_size(symbol)
            fixed[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] = \
                fixed[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] * float(contract_size)
        return fixed

    def fix_trades(self, raw, **kwargs):
        raw = super().fix_trades(raw, **kwargs)
        for trade in raw:
            trade[trading_enums.ExchangeConstantsOrderColumns.STATUS.value] = trading_enums.OrderStatus.CLOSED.value
            trade[trading_enums.ExchangeConstantsOrderColumns.EXCHANGE_ID.value] = trade[
                trading_enums.ExchangeConstantsOrderColumns.ORDER.value
            ]
        return raw

    def parse_position(self, fixed, force_empty=False, **kwargs):
        try:
            parsed = super().parse_position(fixed, force_empty=force_empty, **kwargs)
            # use one way by default.
            if parsed[trading_enums.ExchangeConstantsPositionColumns.SIZE.value] == constants.ZERO:
                parsed[trading_enums.ExchangeConstantsPositionColumns.POSITION_MODE.value] = \
                    trading_enums.PositionMode.ONE_WAY
            return parsed
        except decimal.InvalidOperation:
            # on binance, positions might be invalid (ex: LUNAUSD_PERP as None contact size)
            return None

    def parse_leverage(self, fixed, **kwargs):
        # WARNING no CCXT standard leverage parsing logic
        # HAS TO BE IMPLEMENTED IN EACH EXCHANGE IMPLEMENTATION
        parsed = super().parse_leverage(fixed, **kwargs)
        # on binance fixed is a parsed position
        parsed[trading_enums.ExchangeConstantsLeveragePropertyColumns.LEVERAGE.value] = \
            fixed[trading_enums.ExchangeConstantsPositionColumns.LEVERAGE.value]
        return parsed


def _filter_positions(positions):
    return [
        position
        for position in positions
        if position is not None
    ]
