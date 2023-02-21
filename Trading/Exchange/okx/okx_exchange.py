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

import octobot_commons.constants as commons_constants
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges
import octobot_trading.constants as constants
import octobot_trading.errors as trading_errors
import octobot_trading.exchanges.connectors.ccxt.enums as ccxt_enums
import octobot_trading.personal_data as trading_personal_data


class Okx(exchanges.RestExchange):
    MAX_PAGINATION_LIMIT: int = 100  # value from https://www.okex.com/docs/en/#spot-orders_pending
    DESCRIPTION = ""
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
            params["marginMode"] = self._get_ccxt_margin_type(order.symbol)
        return params

    # todo check
    async def _create_market_stop_loss_order(self, symbol, quantity, price, side, current_price, params=None) -> dict:
        params = params or {}
        params["stopLossPrice"] = price  # make ccxt understand that it's a stop loss
        order = await self.connector.client.create_order(symbol, "market", side, quantity, params=params)
        return order

    async def _get_all_typed_orders(self, method, symbol=None, since=None, limit=None, **kwargs) -> list:
        limit = self._fix_limit(limit)
        is_stop_order = kwargs.get("stop", False)
        if is_stop_order and self.connector.adapter.OKX_ORDER_TYPE not in kwargs:
            kwargs[self.connector.adapter.OKX_ORDER_TYPE] = self.connector.adapter.OKX_CONDITIONAL_ORDER_TYPE
        regular_orders = await method(symbol=symbol, since=since, limit=limit, **kwargs)
        if is_stop_order:
            # only require stop orders
            return regular_orders
        # add order types of order (different param in api endpoint)
        other_orders = []
        for order_type in self._get_used_order_types():
            kwargs["ordType"] = order_type
            other_orders += await method(symbol=symbol, since=since, limit=limit, **kwargs)
        return regular_orders + other_orders

    async def get_open_orders(self, symbol=None, since=None, limit=None, **kwargs) -> list:
        return await self._get_all_typed_orders(
            super().get_open_orders, symbol=symbol, since=since, limit=limit, **kwargs
        )

    async def get_closed_orders(self, symbol=None, since=None, limit=None, **kwargs) -> list:
        return await self._get_all_typed_orders(
            super().get_closed_orders, symbol=symbol, since=since, limit=limit, **kwargs
        )

    async def get_order(self, order_id: str, symbol: str = None, **kwargs: dict) -> dict:
        try:
            kwargs = self._get_okx_order_params(order_id, **kwargs)
            return await super().get_order(order_id, symbol=symbol, **kwargs)
        except trading_errors.NotSupported:
            if kwargs.get("stop", False):
                # from ccxt 2.8.4
                # fetchOrder() does not support stop orders, use fetchOpenOrders() fetchCanceledOrders() or fetchClosedOrders
                return await self.get_order_from_open_and_closed_orders(order_id, symbol=symbol, **kwargs)
            raise

    async def cancel_order(self, order_id: str, symbol: str = None, **kwargs: dict) -> trading_enums.OrderStatus:
        return await super().cancel_order(order_id, symbol=symbol, **self._get_okx_order_params(order_id, **kwargs))

    def _get_okx_order_params(self, order_id, **kwargs):
        params = kwargs or {}
        try:
            if "stop" not in params:
                order = self.exchange_manager.exchange_personal_data.orders_manager.get_order(order_id)
                params["stop"] = trading_personal_data.is_stop_order(order.order_type) \
                    or trading_personal_data.is_take_profit_order(order.order_type)
        except KeyError:
            pass
        return params

    async def _verify_order(self, created_order, order_type, symbol, price, side, get_order_params=None):

        if trading_personal_data.is_stop_order(order_type) or trading_personal_data.is_take_profit_order(order_type):
            get_order_params = get_order_params or {}
            get_order_params["stop"] = True
        return await super()._verify_order(created_order, order_type, symbol, price, side,
                                           get_order_params=get_order_params)

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

    def _get_ccxt_margin_type(self, symbol, contract=None):
        if not self.exchange_manager.exchange.has_pair_future_contract(symbol):
            raise KeyError(f"{symbol} contract unavailable")
        contract = contract or self.exchange_manager.exchange.get_pair_future_contract(symbol)
        return self.connector.adapter.OKX_ISOLATED_MARGIN_MODE if contract.is_isolated() \
            else self.connector.adapter.OKX_CROSS_MARGIN_MODE

    def _get_margin_query_params(self, symbol, allow_missing_contract=False, **kwargs):
        pos_side = self.connector.adapter.OKX_ONE_WAY_MODE
        if not self.exchange_manager.exchange.has_pair_future_contract(symbol):
            if not allow_missing_contract:
                raise KeyError(f"{symbol} contract unavailable")
            kwargs.update({
                self.connector.adapter.OKX_POS_SIDE: pos_side,
            })
        else:
            contract = self.exchange_manager.exchange.get_pair_future_contract(symbol)
            if not contract.is_one_way_position_mode():
                self.logger.debug(f"Switching {symbol} position mode to one way")
                contract.set_position_mode(is_one_way=True, is_hedge=False)
                # todo: handle other position sides when cross is supported
            kwargs = kwargs or {}
            kwargs.update({
                self.connector.adapter.OKX_LEVER: float(contract.current_leverage),
                self.connector.adapter.OKX_MARGIN_MODE: self._get_ccxt_margin_type(symbol, contract=contract),
                self.connector.adapter.OKX_POS_SIDE: pos_side,
            })
        return kwargs

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
        kwargs = self._get_margin_query_params(symbol, allow_missing_contract=True, **kwargs)
        kwargs.pop(self.connector.adapter.OKX_LEVER, None)
        return await self.connector.set_symbol_leverage(leverage=leverage, symbol=symbol, **kwargs)

    async def set_symbol_margin_type(self, symbol: str, isolated: bool, **kwargs: dict):
        kwargs = self._get_margin_query_params(symbol, **kwargs)
        kwargs.pop(self.connector.adapter.OKX_MARGIN_MODE)
        await super().set_symbol_margin_type(symbol, isolated, **kwargs)

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

    async def set_symbol_partial_take_profit_stop_loss(self, symbol: str, inverse: bool,
                                                       tp_sl_mode: trading_enums.TakeProfitStopLossMode):
        """
        take profit / stop loss mode does not exist on okx futures
        """

    def _get_used_order_types(self):
        # todo fill in with used order type (used to get open and closed orders)
        return [
            self.connector.adapter.OKX_CONDITIONAL_ORDER_TYPE,
        ]


class OKXCCXTAdapter(exchanges.CCXTAdapter):
    # ORDERS
    OKX_ORDER_TYPE = "ordType"
    OKX_TRIGGER_ORDER_TYPE = "trigger"
    OKX_CONDITIONAL_ORDER_TYPE = "conditional"
    OKX_LAST_PRICE = "last"

    # POSITIONS
    OKX_MARGIN_MODE = "mgnMode"
    OKX_ISOLATED_MARGIN_MODE = "isolated"
    OKX_CROSS_MARGIN_MODE = "cross"

    OKX_POS_SIDE = "posSide"
    OKX_ONE_WAY_MODE = "net"

    # LEVERAGE
    OKX_LEVER = "lever"
    DATA = "data"

    # Funding
    OKX_DEFAULT_FUNDING_TIME = 8 * commons_constants.HOURS_TO_SECONDS

    def fix_order(self, raw, symbol=None, **kwargs):
        fixed = super().fix_order(raw, **kwargs)
        if self.connector.exchange_manager.is_future \
                and fixed[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] is not None:
            # amount is in contact, multiply by contract value to get the currency amount (displayed to the user)
            contract_size = self.connector.get_contract_size(symbol)
            fixed[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] = \
                fixed[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] * float(contract_size)
        if fixed[trading_enums.ExchangeConstantsOrderColumns.COST.value] is not None:
            fixed[trading_enums.ExchangeConstantsOrderColumns.COST.value] = \
                fixed[trading_enums.ExchangeConstantsOrderColumns.COST.value]
        self._adapt_order_type(fixed)
        return fixed

    def _adapt_order_type(self, fixed):
        order_info = fixed[trading_enums.ExchangeConstantsOrderColumns.INFO.value]
        if stop_price := fixed.get(ccxt_enums.ExchangeOrderCCXTColumns.STOP_PRICE.value, None):
            last_price = order_info.get(self.OKX_LAST_PRICE, None)
            if last_price is None:
                self.logger.error(f"Unhandled stop order: last price is None")
            else:
                last_price = float(last_price)
                side = fixed[trading_enums.ExchangeConstantsOrderColumns.SIDE.value]
                if side == trading_enums.TradeOrderSide.BUY.value:
                    # trigger stop loss buy when price goes bellow stop_price, untriggered when last price is above
                    if last_price > stop_price:
                        updated_type = trading_enums.TradeOrderType.STOP_LOSS.value
                    else:
                        updated_type = trading_enums.TradeOrderType.TAKE_PROFIT.value
                else:
                    # trigger take profit sell when price goes above stop_price, untriggered when last price is bellow
                    if last_price < stop_price:
                        updated_type = trading_enums.TradeOrderType.TAKE_PROFIT.value
                    else:
                        updated_type = trading_enums.TradeOrderType.STOP_LOSS.value
                # stop loss are not tagged as such by ccxt, force it
                fixed[trading_enums.ExchangeConstantsOrderColumns.TYPE.value] = updated_type
        return fixed

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

    def parse_funding_rate(self, fixed, from_ticker=False, **kwargs):
        if from_ticker:
            # no funding info in ticker
            return {}
        fixed = super().parse_funding_rate(fixed, from_ticker=from_ticker, **kwargs)
        # no previous funding time of rate on okx
        next_funding_timestamp = fixed[trading_enums.ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value]
        # only the next scheduled funding rate is available: use it for last value
        next_funding_rate = fixed[trading_enums.ExchangeConstantsFundingColumns.PREDICTED_FUNDING_RATE.value]
        fixed.update({
            trading_enums.ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value:
                next_funding_timestamp - self.OKX_DEFAULT_FUNDING_TIME,
            trading_enums.ExchangeConstantsFundingColumns.FUNDING_RATE.value: next_funding_rate,
            trading_enums.ExchangeConstantsFundingColumns.PREDICTED_FUNDING_RATE.value: next_funding_rate,
        })
        return fixed
