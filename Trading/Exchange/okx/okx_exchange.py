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
import time
import decimal
import typing

import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges
import octobot_trading.constants as constants
import octobot_trading.exchanges.connectors.ccxt.enums as ccxt_enums


class Okx(exchanges.RestExchange):
    MAX_PAGINATION_LIMIT: int = 100  # value from https://www.okex.com/docs/en/#spot-orders_pending
    DESCRIPTION = ""
    USED_ORDER_TYPES = []   # todo fill in with used order type (used to get open orders)
    REQUIRES_MOCKED_EMPTY_POSITION = True   # https://www.okx.com/learn/complete-guide-to-okex-api-v5-upgrade#h-rest-2

    @classmethod
    def get_name(cls):
        return 'okx'

    def get_adapter_class(self):
        return OKXCCXTAdapter

    @classmethod
    def is_supporting_sandbox(cls) -> bool:
        return False

    @classmethod
    def get_supported_exchange_types(cls) -> list:
        """
        :return: The list of supported exchange types
        """
        return [
            trading_enums.ExchangeTypes.SPOT,
            trading_enums.ExchangeTypes.FUTURE,
        ]

    async def get_symbol_prices(self, symbol, time_frame, limit: int = None, **kwargs: dict):
        if "since" in kwargs:
            # prevent ccxt from fillings the end param (not working when trying to get the 1st candle times)
            kwargs["until"] = int(time.time() * 1000)
        return await super().get_symbol_prices(symbol=symbol, time_frame=time_frame, limit=limit, **kwargs)

    async def get_open_orders(self, symbol=None, since=None, limit=None, **kwargs) -> list:
        return await super().get_open_orders(symbol=symbol,
                                             since=since,
                                             limit=self._fix_limit(limit),
                                             **kwargs)

    async def get_closed_orders(self, symbol=None, since=None, limit=None, **kwargs) -> list:
        return await super().get_closed_orders(symbol=symbol,
                                               since=since,
                                               limit=self._fix_limit(limit),
                                               **kwargs)

    async def _create_market_buy_order(self, symbol, quantity, price=None, params=None) -> dict:
        """
        Add price to default connector call for market orders https://github.com/ccxt/ccxt/issues/9523
        """
        return await self.connector.client.create_market_order(symbol=symbol, side='buy', amount=quantity,
                                                               price=price, params=params)

    async def _create_market_sell_order(self, symbol, quantity, price=None, params=None) -> dict:
        """
        Add price to default connector call for market orders https://github.com/ccxt/ccxt/issues/9523
        """
        return await self.connector.client.create_market_order(symbol=symbol, side='sell', amount=quantity,
                                                               price=price, params=params)

    def _fix_limit(self, limit: int) -> int:
        return min(self.MAX_PAGINATION_LIMIT, limit) if limit else limit

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer,
                                            adapt_for_contract_size=True)   # todo check

    async def get_sub_account_list(self):
        sub_account_list = (await self.connector.client.privateGetUsersSubaccountList()).get("data", [])
        if not sub_account_list:
            return []
        return [
            {
                trading_enums.SubAccountColumns.ID.value: sub_account.get("subAcct", ""),
                trading_enums.SubAccountColumns.NAME.value: sub_account.get("label", "")
            }
            for sub_account in sub_account_list
            if sub_account.get("enable", False)
        ]

    # todo check
    def get_order_additional_params(self, order) -> dict:
        params = {}
        if self.exchange_manager.is_future:
            params["reduceOnly"] = order.reduce_only
        return params

    # todo check
    async def _create_market_stop_loss_order(self, symbol, quantity, price, side, current_price, params=None) -> dict:
        params = params or {}
        params["stopLossPrice"] = price  # make ccxt understand that it's a stop loss
        order = await self.connector.client.create_order(symbol, "market", side, quantity, params=params)
        return order

    # todo check
    async def get_open_orders(self, symbol=None, since=None, limit=None, **kwargs) -> list:
        regular_orders = await super().get_open_orders(symbol=symbol, since=since, limit=limit, **kwargs)
        # add order types of order (different api endpoint)
        other_orders = []
        for order_type in self.USED_ORDER_TYPES:
            kwargs["ordType"] = order_type
            other_orders += await super().get_open_orders(symbol=symbol, since=since, limit=limit, **kwargs)
        return regular_orders + other_orders

    # todo check
    async def create_order(self, order_type: trading_enums.TraderOrderType, symbol: str, quantity: decimal.Decimal,
                           price: decimal.Decimal = None, stop_price: decimal.Decimal = None,
                           side: trading_enums.TradeOrderSide = None, current_price: decimal.Decimal = None,
                           params: dict = None) -> typing.Optional[dict]:
        if self.exchange_manager.is_future:
            # on futures exchange expects, quantity in contracts: convert quantity into contracts
            quantity = quantity / self.get_contract_size(symbol)
        return await super().create_order(order_type, symbol, quantity,
                                          price=price, stop_price=stop_price,
                                          side=side, current_price=current_price,
                                          params=params)

    async def get_symbol_leverage(self, symbol: str, **kwargs: dict):
        """
        :param symbol: the symbol
        :return: the current symbol leverage multiplier
        """
        return await self.connector.get_symbol_leverage(symbol=symbol, **kwargs)

    async def set_symbol_leverage(self, symbol: str, leverage: float, **kwargs):
        """
        Set the symbol leverage
        :param symbol: the symbol
        :param leverage: the leverage
        :return: the update result
        """
        # TODO also set position mode and margin type
        return await self.connector.set_symbol_leverage(leverage=leverage, symbol=symbol, **kwargs)

    async def get_position(self, symbol: str, **kwargs: dict) -> dict:
        """
        Get the current user symbol position
        :param symbol: the position symbol
        :return: the user symbol position
        """
        position = await super().get_position(symbol=symbol, **kwargs)
        if position[trading_enums.ExchangeConstantsPositionColumns.SIZE.value] == constants.ZERO:
            await self._update_position_with_leverage_data(symbol, position)

        if position[trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value] != symbol:
            # happened in previous ccxt version, todo remove if no seen again
            raise ValueError(
                f"Invalid position symbol: "
                f"{position[trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value]}, "
                f"expected {symbol}"
            )
        return position

    async def _update_position_with_leverage_data(self, symbol, position):
        leverage_data = await self.get_symbol_leverage(symbol)
        raw_data = leverage_data[trading_enums.ExchangeConstantsLeveragePropertyColumns.RAW.value]
        adapter = self.connector.adapter
        position[trading_enums.ExchangeConstantsPositionColumns.POSITION_MODE.value] = \
            adapter.parse_position_mode(raw_data[adapter.OKX_POS_SIDE])
        position[trading_enums.ExchangeConstantsPositionColumns.MARGIN_TYPE.value] = \
            adapter.parse_position_type(raw_data[adapter.OKX_MARGIN_MODE])
        position[trading_enums.ExchangeConstantsPositionColumns.LEVERAGE.value] = \
            leverage_data[trading_enums.ExchangeConstantsLeveragePropertyColumns.LEVERAGE.value]

    # todo check set_symbol_partial_take_profit_stop_loss


class OKXCCXTAdapter(exchanges.CCXTAdapter):
    # POSITIONS
    OKX_MARGIN_MODE = "mgnMode"
    OKX_ISOLATED_MARGIN_MODE = "isolated"
    OKX_CROSS_MARGIN_MODE = "cross"

    OKX_POS_SIDE = "posSide"
    OKX_ONE_WAY_MODE = "net"

    # LEVERAGE
    OKX_LEVER = "lever"
    DATA = "data"

    def parse_position(self, fixed, force_empty=False, **kwargs):
        parsed = super().parse_position(fixed, force_empty=force_empty, **kwargs)
        # use isolated by default. Set in set_leverage
        parsed[trading_enums.ExchangeConstantsPositionColumns.MARGIN_TYPE.value] = \
            trading_enums.TraderPositionType(
                fixed.get(ccxt_enums.ExchangePositionCCXTColumns.MARGIN_MODE.value)
                or trading_enums.TraderPositionType.ISOLATED.value
            )
        # use one way by default. Set in set_leverage
        if parsed[trading_enums.ExchangeConstantsPositionColumns.SIZE.value] == constants.ZERO:
            parsed[trading_enums.ExchangeConstantsPositionColumns.POSITION_MODE.value] = \
                trading_enums.PositionMode.ONE_WAY
        return parsed

    def parse_position_type(self, margin_mode):
        if margin_mode == self.OKX_ISOLATED_MARGIN_MODE:
            return trading_enums.TraderPositionType.ISOLATED
        elif margin_mode == self.OKX_CROSS_MARGIN_MODE:
            return trading_enums.TraderPositionType.CROSS
        raise ValueError(margin_mode)

    def parse_position_mode(self, position_mode):
        if position_mode == self.OKX_ONE_WAY_MODE:
            return trading_enums.PositionMode.ONE_WAY
        return trading_enums.PositionMode.HEDGE

    def parse_leverage(self, fixed, **kwargs):
        # WARNING no CCXT standard leverage parsing logic
        # HAS TO BE IMPLEMENTED IN EACH EXCHANGE IMPLEMENTATION
        fixed = fixed[self.DATA][0]    # okx is returning a list, use the 1 element only
        fixed = super().parse_leverage(fixed, **kwargs)
        fixed[trading_enums.ExchangeConstantsLeveragePropertyColumns.LEVERAGE.value] = \
            self.safe_decimal(
                fixed[trading_enums.ExchangeConstantsLeveragePropertyColumns.RAW.value],
                self.OKX_LEVER,
                constants.DEFAULT_SYMBOL_LEVERAGE,
            )
        return fixed
