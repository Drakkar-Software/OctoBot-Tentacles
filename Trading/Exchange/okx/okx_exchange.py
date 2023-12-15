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

import octobot_commons.constants as commons_constants
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges
import octobot_trading.constants as constants
import octobot_trading.errors as trading_errors
import octobot_trading.exchanges.connectors.ccxt.enums as ccxt_enums
import octobot_trading.exchanges.connectors.ccxt.constants as ccxt_constants
import octobot_trading.exchanges.connectors.ccxt.ccxt_connector as ccxt_connector
import octobot_trading.personal_data as trading_personal_data


def _disabled_okx_algo_order_creation(f):
    async def wrapper(*args, **kwargs):
        # Algo order prevent bundled orders from working as they require to use the regular order api
        # Since the regular order api works for limit and market orders as well, us it all the time
        # Algo api is used for stop losses.
        # This ccxt issue will remain as long as privatePostTradeOrderAlgo will be used for each order with a
        # stopLossPrice or takeProfitPrice even when both are set (which make it an invalid okx algo order)
        connector = args[0]
        client = connector.client
        client.privatePostTradeOrderAlgo = client.privatePostTradeOrder
        try:
            return await f(*args, **kwargs)
        finally:
            client.privatePostTradeOrderAlgo = connector.get_saved_data(connector.PRIVATE_POST_TRADE_ORDER_ALGO)
    return wrapper


def _enabled_okx_algo_order_creation(f):
    async def wrapper(*args, **kwargs):
        # Used to force algo orders availability and avoid concurrency issues due to _disabled_algo_order_creation
        connector = args[0]
        connector.client.privatePostTradeOrderAlgo = connector.get_saved_data(connector.PRIVATE_POST_TRADE_ORDER_ALGO)
        return await f(*args, **kwargs)
    return wrapper


class OkxConnector(ccxt_connector.CCXTConnector):
    PRIVATE_POST_TRADE_ORDER_ALGO = "privatePostTradeOrderAlgo"

    def _create_client(self):
        super()._create_client()
        # save client.privatePostTradeOrderAlgo ref to prevent concurrent _disabled_algo_order_creation issues
        self.set_saved_data(self.PRIVATE_POST_TRADE_ORDER_ALGO, self.client.privatePostTradeOrderAlgo)

    @_disabled_okx_algo_order_creation
    async def create_market_buy_order(self, symbol, quantity, price=None, params=None) -> dict:
        return await super().create_market_buy_order(symbol, quantity, price=price, params=params)

    @_disabled_okx_algo_order_creation
    async def create_limit_buy_order(self, symbol, quantity, price=None, params=None) -> dict:
        return await super().create_limit_buy_order(symbol, quantity, price=price, params=params)

    @_disabled_okx_algo_order_creation
    async def create_market_sell_order(self, symbol, quantity, price=None, params=None) -> dict:
        return await super().create_market_sell_order(symbol, quantity, price=price, params=params)

    @_disabled_okx_algo_order_creation
    async def create_limit_sell_order(self, symbol, quantity, price=None, params=None) -> dict:
        return await super().create_limit_sell_order(symbol, quantity, price=price, params=params)

    @_enabled_okx_algo_order_creation
    async def create_market_stop_loss_order(self, symbol, quantity, price, side, current_price, params=None) -> dict:
        return self.adapter.adapt_order(
            await self.client.create_order(
                symbol, trading_enums.TradeOrderType.MARKET.value, side, quantity, params=params
            ),
            symbol=symbol, quantity=quantity
        )


class Okx(exchanges.RestExchange):
    DESCRIPTION = ""

    FIX_MARKET_STATUS = True
    ADAPT_MARKET_STATUS_FOR_CONTRACT_SIZE = True

    DEFAULT_CONNECTOR_CLASS = OkxConnector
    MAX_PAGINATION_LIMIT: int = 100  # value from https://www.okex.com/docs/en/#spot-orders_pending

    # Okx default take profits are market orders
    # note: use BUY_MARKET and SELL_MARKET since in reality those are conditional market orders, which behave the same
    # way as limit order but with higher fees
    _OKX_BUNDLED_ORDERS = [trading_enums.TraderOrderType.STOP_LOSS, trading_enums.TraderOrderType.TAKE_PROFIT,
                           trading_enums.TraderOrderType.BUY_MARKET, trading_enums.TraderOrderType.SELL_MARKET]

    # should be overridden locally to match exchange support
    SUPPORTED_ELEMENTS = {
        trading_enums.ExchangeTypes.FUTURE.value: {
            # order that should be self-managed by OctoBot
            trading_enums.ExchangeSupportedElements.UNSUPPORTED_ORDERS.value: [
                # trading_enums.TraderOrderType.STOP_LOSS,    # supported on futures
                trading_enums.TraderOrderType.STOP_LOSS_LIMIT,
                trading_enums.TraderOrderType.TAKE_PROFIT,
                trading_enums.TraderOrderType.TAKE_PROFIT_LIMIT,
                trading_enums.TraderOrderType.TRAILING_STOP,
                trading_enums.TraderOrderType.TRAILING_STOP_LIMIT
            ],
            # order that can be bundled together to create them all in one request
            trading_enums.ExchangeSupportedElements.SUPPORTED_BUNDLED_ORDERS.value: {
                trading_enums.TraderOrderType.BUY_MARKET: _OKX_BUNDLED_ORDERS,
                trading_enums.TraderOrderType.SELL_MARKET: _OKX_BUNDLED_ORDERS,
                trading_enums.TraderOrderType.BUY_LIMIT: _OKX_BUNDLED_ORDERS,
                trading_enums.TraderOrderType.SELL_LIMIT: _OKX_BUNDLED_ORDERS,
            },
        },
        trading_enums.ExchangeTypes.SPOT.value: {
            # order that should be self-managed by OctoBot
            trading_enums.ExchangeSupportedElements.UNSUPPORTED_ORDERS.value: [
                trading_enums.TraderOrderType.STOP_LOSS,
                trading_enums.TraderOrderType.STOP_LOSS_LIMIT,
                trading_enums.TraderOrderType.TAKE_PROFIT,
                trading_enums.TraderOrderType.TAKE_PROFIT_LIMIT,
                trading_enums.TraderOrderType.TRAILING_STOP,
                trading_enums.TraderOrderType.TRAILING_STOP_LIMIT
            ],
            # order that can be bundled together to create them all in one request
            trading_enums.ExchangeSupportedElements.SUPPORTED_BUNDLED_ORDERS.value: {},
        }
    }

    # Set True when exchange is not returning empty position details when fetching a position with a specified symbol
    # Exchange will then fallback to self.get_mocked_empty_position when having get_position returning None
    REQUIRES_MOCKED_EMPTY_POSITION = True   # https://www.okx.com/learn/complete-guide-to-okex-api-v5-upgrade#h-rest-2

    # set True when get_positions() is not returning empty positions and should use get_position() instead
    REQUIRES_SYMBOL_FOR_EMPTY_POSITION = True

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

    def _fix_limit(self, limit: int) -> int:
        return min(self.MAX_PAGINATION_LIMIT, limit) if limit else limit

    async def get_account_id(self, **kwargs: dict) -> str:
        accounts = await self.connector.client.fetch_accounts()
        try:
            return accounts[0]["id"]
        except IndexError:
            # should never happen as at least one account should be available
            return None

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

    def get_order_additional_params(self, order) -> dict:
        params = {}
        if self.exchange_manager.is_future:
            params["reduceOnly"] = order.reduce_only
            params[ccxt_enums.ExchangeOrderCCXTColumns.MARGIN_MODE.value] = self._get_ccxt_margin_type(order.symbol)
        return params

    def get_bundled_order_parameters(self, order, stop_loss_price=None, take_profit_price=None) -> dict:
        """
        Returns the updated params when this exchange supports orders created upon other orders fill
        (ex: a stop loss created at the same time as a buy order)
        :param order: the initial order
        :param stop_loss_price: the bundled order stopLoss price
        :param take_profit_price: the bundled order takeProfit price
        :return: A dict with the necessary parameters to create the bundled order on exchange alongside the
        base order in one request
        """
        params = {}
        if not (
            trading_personal_data.is_stop_order(order.order_type) or
            trading_personal_data.is_take_profit_order(order.order_type)
        ):
            # force non algo order "order type"
            if isinstance(order, trading_personal_data.MarketOrder):
                params["ordType"] = "market"
            elif isinstance(order, trading_personal_data.LimitOrder):
                params["px"] = str(order.origin_price)
                params["ordType"] = "limit"
        if stop_loss_price is not None:
            params[self.connector.adapter.OKX_STOP_LOSS_PRICE] = float(stop_loss_price)
            params["slOrdPx"] = -1  # execute as market order
        if take_profit_price is not None:
            params[self.connector.adapter.OKX_TAKE_PROFIT_PRICE] = float(take_profit_price)
            params["tpOrdPx"] = -1  # execute as market order
        return params

    async def _create_market_stop_loss_order(self, symbol, quantity, price, side, current_price, params=None) -> dict:
        params = params or {}
        params[self.connector.adapter.OKX_STOP_LOSS_PRICE] = price  # make ccxt understand that it's a stop loss
        return await self.connector.create_market_stop_loss_order(symbol, quantity, price, side, current_price, params=params)

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
        if self.exchange_manager.is_future:
            # stop orders are futures only for now
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

    async def get_order(self, exchange_order_id: str, symbol: str = None, **kwargs: dict) -> dict:
        try:
            kwargs = self._get_okx_order_params(exchange_order_id, **kwargs)
            order = await super().get_order(exchange_order_id, symbol=symbol, **kwargs)
            return order
        except trading_errors.NotSupported:
            if kwargs.get("stop", False):
                # from ccxt 2.8.4
                # fetchOrder() does not support stop orders, use fetchOpenOrders() fetchCanceledOrders() or fetchClosedOrders
                return await self.get_order_from_open_and_closed_orders(exchange_order_id, symbol=symbol, **kwargs)
            raise

    async def cancel_order(
        self, exchange_order_id: str, symbol: str, order_type: trading_enums.TraderOrderType, **kwargs: dict
    ) -> trading_enums.OrderStatus:
        return await super().cancel_order(
            exchange_order_id, symbol, order_type, **self._get_okx_order_params(exchange_order_id, order_type, **kwargs)
        )

    def _get_okx_order_params(self, exchange_order_id, order_type=None, **kwargs):
        params = kwargs or {}
        try:
            if "stop" not in params:
                order_type = order_type or \
                             self.exchange_manager.exchange_personal_data.orders_manager.get_order(
                                 None, exchange_order_id=exchange_order_id
                             ).order_type
                params["stop"] = trading_personal_data.is_stop_order(order_type) \
                    or trading_personal_data.is_take_profit_order(order_type)
        except KeyError:
            pass
        return params

    async def _verify_order(self, created_order, order_type, symbol, price, side, get_order_params=None):

        if trading_personal_data.is_stop_order(order_type) or trading_personal_data.is_take_profit_order(order_type):
            get_order_params = get_order_params or {}
            get_order_params["stop"] = True
        return await super()._verify_order(created_order, order_type, symbol, price, side,
                                           get_order_params=get_order_params)

    def _is_oco_order(self, params):
        return all(
            oco_order_param in (params or {})
            for oco_order_param in (
                self.connector.adapter.OKX_STOP_LOSS_PRICE,
                self.connector.adapter.OKX_TAKE_PROFIT_PRICE
            )
        )

    async def create_order(self, order_type: trading_enums.TraderOrderType, symbol: str, quantity: decimal.Decimal,
                           price: decimal.Decimal = None, stop_price: decimal.Decimal = None,
                           side: trading_enums.TradeOrderSide = None, current_price: decimal.Decimal = None,
                           reduce_only: bool = False, params: dict = None) -> typing.Optional[dict]:
        if self.exchange_manager.is_future:
            # on futures exchange expects, quantity in contracts: convert quantity into contracts
            quantity = quantity / self.get_contract_size(symbol)
        if self._is_oco_order(params):
            raise trading_errors.NotSupported(
                f"OCO bundled orders (orders including both a stop loss and take profit price) "
                f"are not yet supported on {self.get_name()}"
            )
        return await super().create_order(order_type, symbol, quantity,
                                          price=price, stop_price=stop_price,
                                          side=side, current_price=current_price,
                                          reduce_only=reduce_only, params=params)

    def _get_ccxt_margin_type(self, symbol, contract=None):
        if not self.exchange_manager.exchange.has_pair_future_contract(symbol):
            raise KeyError(f"{symbol} contract unavailable")
        contract = contract or self.exchange_manager.exchange.get_pair_future_contract(symbol)
        return ccxt_enums.ExchangeMarginTypes.ISOLATED.value if contract.is_isolated() \
            else ccxt_enums.ExchangeMarginTypes.CROSS.value

    def _get_margin_query_params(self, symbol, **kwargs):
        pos_side = self.connector.adapter.OKX_ONE_WAY_MODE
        if not self.exchange_manager.exchange.has_pair_future_contract(symbol):
            raise KeyError(f"{symbol} contract unavailable")
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
        kwargs = kwargs or {}
        if ccxt_enums.ExchangePositionCCXTColumns.MARGIN_MODE.value not in kwargs:
            margin_type = ccxt_enums.ExchangeMarginTypes.ISOLATED.value
            try:
                margin_type = self._get_ccxt_margin_type(symbol)
            except KeyError:
                pass
            kwargs[ccxt_enums.ExchangePositionCCXTColumns.MARGIN_MODE.value] = margin_type
        return await self.connector.get_symbol_leverage(symbol=symbol, **kwargs)

    async def set_symbol_leverage(self, symbol: str, leverage: float, **kwargs):
        """
        Set the symbol leverage
        :param symbol: the symbol
        :param leverage: the leverage
        :return: the update result
        """
        kwargs = self._get_margin_query_params(symbol, **kwargs)
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
            adapter.parse_margin_type(raw_data[adapter.OKX_MARGIN_MODE])
        position[trading_enums.ExchangeConstantsPositionColumns.LEVERAGE.value] = \
            leverage_data[trading_enums.ExchangeConstantsLeveragePropertyColumns.LEVERAGE.value]

    async def set_symbol_partial_take_profit_stop_loss(self, symbol: str, inverse: bool,
                                                       tp_sl_mode: trading_enums.TakeProfitStopLossMode):
        """
        take profit / stop loss mode does not exist on okx futures
        """

    def _get_used_order_types(self):
        return [
            # stop orders
            self.connector.adapter.OKX_CONDITIONAL_ORDER_TYPE,
            # created with bundled orders including stop loss & take profit: unsupported for now
            # self.connector.adapter.OKX_OCO_ORDER_TYPE,
        ]


class OKXCCXTAdapter(exchanges.CCXTAdapter):
    # ORDERS
    OKX_ORDER_TYPE = "ordType"
    OKX_TRIGGER_ORDER_TYPE = "trigger"
    OKX_OCO_ORDER_TYPE = "oco"
    OKX_CONDITIONAL_ORDER_TYPE = "conditional"
    OKX_BASIC_ORDER_TYPES = ["market", "limit"]
    OKX_LAST_PRICE = "last"
    OKX_STOP_LOSS_PRICE = "stopLossPrice"
    OKX_TAKE_PROFIT_PRICE = "takeProfitPrice"
    OKX_STOP_LOSS_TRIGGER_PRICE = "slTriggerPx"
    OKX_TAKE_PROFIT_TRIGGER_PRICE = "tpTriggerPx"

    # POSITIONS
    OKX_MARGIN_MODE = "mgnMode"
    OKX_POS_SIDE = "posSide"
    OKX_ONE_WAY_MODE = "net"

    # LEVERAGE
    OKX_LEVER = "lever"
    DATA = "data"

    # Funding
    OKX_DEFAULT_FUNDING_TIME = 8 * commons_constants.HOURS_TO_SECONDS

    def fix_order(self, raw, symbol=None, **kwargs):
        fixed = super().fix_order(raw, **kwargs)
        self._adapt_order_type(fixed)
        return fixed

    def _adapt_order_type(self, fixed):
        order_info = fixed[trading_enums.ExchangeConstantsOrderColumns.INFO.value]
        if fixed.get(ccxt_enums.ExchangeOrderCCXTColumns.TYPE.value, None) not in self.OKX_BASIC_ORDER_TYPES:
            trigger_price = fixed.get(ccxt_enums.ExchangeOrderCCXTColumns.TRIGGER_PRICE.value, None)
            last_price = order_info.get(self.OKX_LAST_PRICE, None)
            stop_loss_trigger_price = order_info.get(self.OKX_STOP_LOSS_TRIGGER_PRICE, None)
            take_profit_trigger_price = order_info.get(self.OKX_TAKE_PROFIT_TRIGGER_PRICE, None)
            updated_type = trading_enums.TradeOrderType.UNKNOWN.value
            if stop_loss_trigger_price and take_profit_trigger_price:
                # OCO order, unsupported yet
                self.logger.debug(f"Unsupported OKX OCO (stop loss & take profit in a single order): {fixed}")
                updated_type = trading_enums.TradeOrderType.UNSUPPORTED.value
            elif stop_loss_trigger_price is not None:
                updated_type = trading_enums.TradeOrderType.STOP_LOSS.value
            elif take_profit_trigger_price is not None:
                updated_type = trading_enums.TradeOrderType.TAKE_PROFIT.value
            elif last_price is not None:
                last_price = float(last_price)
                side = fixed[trading_enums.ExchangeConstantsOrderColumns.SIDE.value]
                if side == trading_enums.TradeOrderSide.BUY.value:
                    # trigger stop loss buy when price goes bellow stop_price, untriggered when last price is above
                    if last_price > trigger_price:
                        updated_type = trading_enums.TradeOrderType.STOP_LOSS.value
                    else:
                        updated_type = trading_enums.TradeOrderType.TAKE_PROFIT.value
                else:
                    # trigger take profit sell when price goes above stop_price, untriggered when last price is bellow
                    if last_price < trigger_price:
                        updated_type = trading_enums.TradeOrderType.TAKE_PROFIT.value
                    else:
                        updated_type = trading_enums.TradeOrderType.STOP_LOSS.value
            else:
                self.logger.error(f"Unknown order type, order: {fixed}")
            # stop loss and take profits are not tagged as such by ccxt, force it
            fixed[trading_enums.ExchangeConstantsOrderColumns.TYPE.value] = updated_type
        return fixed

    def parse_position(self, fixed, force_empty=False, **kwargs):
        parsed = super().parse_position(fixed, force_empty=force_empty, **kwargs)
        # use isolated by default. Set in set_leverage
        parsed[trading_enums.ExchangeConstantsPositionColumns.MARGIN_TYPE.value] = \
            trading_enums.MarginType(
                fixed.get(ccxt_enums.ExchangePositionCCXTColumns.MARGIN_MODE.value)
                or trading_enums.MarginType.ISOLATED.value
            )
        # use one way by default. Set in set_leverage
        if parsed[trading_enums.ExchangeConstantsPositionColumns.SIZE.value] == constants.ZERO:
            parsed[trading_enums.ExchangeConstantsPositionColumns.POSITION_MODE.value] = \
                trading_enums.PositionMode.ONE_WAY
        return parsed

    def parse_margin_type(self, margin_mode):
        if margin_mode == ccxt_enums.ExchangeMarginTypes.ISOLATED.value:
            return trading_enums.MarginType.ISOLATED
        elif margin_mode == ccxt_enums.ExchangeMarginTypes.CROSS.value:
            return trading_enums.MarginType.CROSS
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
        next_funding_timestamp = fixed[trading_enums.ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value]
        fixed.update({
            # patch LAST_FUNDING_TIME in tentacle
            trading_enums.ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value:
                max(next_funding_timestamp - self.OKX_DEFAULT_FUNDING_TIME, 0)
        })
        return fixed
