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
import math
import copy

import ccxt

import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges
import octobot_commons.constants as commons_constants
import octobot_trading.constants as constants
import octobot_trading.errors


class Bybit(exchanges.SpotCCXTExchange, exchanges.FutureCCXTExchange):
    DESCRIPTION = ""

    # Bybit default take profits are market orders
    # note: use BUY_MARKET and SELL_MARKET since in reality those are conditional market orders, which behave the same
    # way as limit order but with higher fees
    _BYBIT_BUNDLED_ORDERS = [trading_enums.TraderOrderType.STOP_LOSS,
                             trading_enums.TraderOrderType.BUY_MARKET, trading_enums.TraderOrderType.SELL_MARKET]
    SUPPORTED_BUNDLED_ORDERS = {
        trading_enums.TraderOrderType.BUY_MARKET: _BYBIT_BUNDLED_ORDERS,
        trading_enums.TraderOrderType.SELL_MARKET: _BYBIT_BUNDLED_ORDERS,
        trading_enums.TraderOrderType.BUY_LIMIT: _BYBIT_BUNDLED_ORDERS,
        trading_enums.TraderOrderType.SELL_LIMIT: _BYBIT_BUNDLED_ORDERS,
    }

    BUY_STR = "Buy"
    SELL_STR = "Sell"

    LONG_STR = BUY_STR
    SHORT_STR = SELL_STR

    MARK_PRICE_IN_TICKER = True
    FUNDING_IN_TICKER = True

    # Position
    BYBIT_BANKRUPTCY_PRICE = "bust_price"
    BYBIT_CLOSING_FEE = "occ_closing_fee"
    BYBIT_MODE = "mode"
    BYBIT_REALIZED_PNL = "cum_realised_pnl"
    BYBIT_ONE_WAY = "MergedSingle"
    BYBIT_ONE_WAY_DIGIT = "0"
    BYBIT_HEDGE = "BothSide"
    BYBIT_HEDGE_DIGITS = ["1", "2"]

    # Funding
    BYBIT_FUNDING_TIMESTAMP = "funding_rate_timestamp"
    BYBIT_DEFAULT_FUNDING_TIME = 8 * commons_constants.HOURS_TO_SECONDS

    @classmethod
    def get_name(cls) -> str:
        return 'bybit'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer)

    async def get_symbol_prices(self, symbol, time_frame, limit: int = 200, **kwargs: dict):
        # never fetch more than 200 candles or get candles from the past
        limit = min(limit, 200)
        return await super().get_symbol_prices(symbol=symbol, time_frame=time_frame, limit=limit, **kwargs)

    async def get_price_ticker(self, symbol: str, **kwargs: dict):
        ticker = await super().get_price_ticker(symbol=symbol, **kwargs)
        ticker[trading_enums.ExchangeConstantsTickersColumns.TIMESTAMP.value] = self.connector.client.milliseconds()
        return ticker

    def get_default_type(self):
        if self.exchange_manager.is_future:
            return 'linear'
        return 'spot'

    async def get_positions(self) -> list:
        params = {}
        raw_positions = []
        for position_type in ("linear", "inverse"):
            params["subType"] = position_type
            raw_positions += await super().get_positions(**params)
        return self.parse_positions(raw_positions)

    async def get_open_orders(self, symbol: str = None, since: int = None,
                              limit: int = None, **kwargs: dict) -> list:
        orders = []
        try:
            orders = await super().get_open_orders(symbol=symbol, since=since, limit=limit, **kwargs)
        except Exception as e:
            self.logger.exception(e, True, f"Fail to fetching orders : {e}")
        if "stop" not in kwargs:
            # only fetch untriggered stop orders
            kwargs["stop"] = True
            try:
                orders += await super().get_open_orders(symbol=symbol, since=since, limit=limit, **kwargs)
            except Exception as e:
                self.logger.exception(e, True, f"Fail to fetching stop orders : {e}")
        return orders

    async def get_closed_orders(self, symbol: str = None, since: int = None,
                                limit: int = None, **kwargs: dict) -> list:
        orders = []
        try:
            orders = await super().get_closed_orders(symbol=symbol, since=since, limit=limit, **kwargs)
        except ccxt.AuthenticationError as e:
            self.logger.debug(f"(known issue) Fail to fetching closed orders : {e}")
        if "stop" not in kwargs:
            # only fetch untriggered stop orders
            kwargs["stop"] = True
            try:
                orders += await super().get_closed_orders(symbol=symbol, since=since, limit=limit, **kwargs)
            except ccxt.AuthenticationError as e:
                self.logger.debug(f"(known issue) Fail to fetching closed stop orders : {e}")
        return orders

    def clean_order(self, order):
        return super().clean_order(self._update_order_and_trade_data(order))

    def clean_trade(self, trade):
        return super().clean_trade(self._update_order_and_trade_data(trade))

    async def _create_market_stop_loss_order(self, symbol, quantity, price, side, current_price, params=None) -> dict:
        params = params or {}
        params["stop_px"] = price
        params["base_price"] = current_price
        return await self.connector.client.create_order(symbol, "market", side, quantity, params=params)

    async def _edit_order(self, order_id: str, order_type: trading_enums.TraderOrderType, symbol: str,
                          quantity: float, price: float, stop_price: float = None, side: str = None,
                          current_price: float = None, params: dict = None):
        params = params or {}
        if order_type in (trading_enums.TraderOrderType.STOP_LOSS, trading_enums.TraderOrderType.STOP_LOSS_LIMIT):
            params["stop_order_id"] = order_id
        if stop_price is not None:
            # params["stop_px"] = stop_price
            # params["stop_loss"] = stop_price
            params["p_r_trigger_price"] = stop_price
        return await super()._edit_order(order_id, order_type, symbol, quantity=quantity,
                                         price=price, stop_price=stop_price, side=side,
                                         current_price=current_price, params=params)

    async def _verify_order(self, created_order, order_type, symbol, price, params=None):
        if order_type in (trading_enums.TraderOrderType.STOP_LOSS, trading_enums.TraderOrderType.STOP_LOSS_LIMIT):
            params = params or {}
            params["stop_order_id"] = created_order[trading_enums.ExchangeConstantsOrderColumns.ID.value]
        return await super()._verify_order(created_order, order_type, symbol, price, params=params)

    def _update_order_and_trade_data(self, order):
        # parse reduce_only if present
        order[trading_enums.ExchangeConstantsOrderColumns.REDUCE_ONLY.value] = \
            order[trading_enums.ExchangeConstantsOrderColumns.INFO.value].get("reduce_only", False)

        # market orders with stop price are stop loss
        if order.get(trading_enums.ExchangeConstantsOrderColumns.STOP_PRICE.value, None) is not None and \
                order[
                    trading_enums.ExchangeConstantsOrderColumns.TYPE.value] == trading_enums.TradeOrderType.MARKET.value:
            order[trading_enums.ExchangeConstantsOrderColumns.TYPE.value] = trading_enums.TradeOrderType.STOP_LOSS.value

        order[trading_enums.ExchangeConstantsOrderColumns.REDUCE_ONLY.value] = \
            order[trading_enums.ExchangeConstantsOrderColumns.INFO.value].get("reduce_only", False)
        return order

    async def cancel_order(self, order_id: str, symbol: str = None, **kwargs: dict) -> bool:
        if await super().cancel_order(order_id, symbol=symbol, **kwargs):
            return True
        else:
            # order might not have been triggered yet, try with stop order endpoint
            # from docs: You may cancel all untriggered conditional orders or take profit/stop loss order. Essentially,
            # after a conditional order is triggered, it will become an active order. So, when a conditional order
            # is triggered, cancellation has to be done through the active order endpoint for any unfilled or
            # partially filled active order
            kwargs["stop_order_id"] = order_id
            return await super().cancel_order(order_id, symbol=symbol, **kwargs)

    async def set_symbol_leverage(self, symbol: str, leverage: int, **kwargs: dict):
        # buy_leverage and sell_leverage are required on Bybit
        kwargs["buy_leverage"] = kwargs.get("buy_leverage", float(leverage))
        kwargs["sell_leverage"] = kwargs.get("sell_leverage", float(leverage))
        return await self.connector.set_symbol_leverage(leverage=leverage, symbol=symbol, **kwargs)

    async def set_symbol_partial_take_profit_stop_loss(self, symbol: str, inverse: bool,
                                                       tp_sl_mode: trading_enums.TakeProfitStopLossMode):
        # v2/private/tpsl/switch-mode
        # from https://bybit-exchange.github.io/docs/inverse/#t-switchmode
        params = {
            "symbol": self.connector.client.market(symbol)['id'],
            "tp_sl_mode": tp_sl_mode.value
        }
        try:
            if inverse:
                await self.connector.client.privatePostPrivateTpslSwitchMode(params)
            await self.connector.client.privatePostPrivateLinearTpslSwitchMode(params)
        except ccxt.ExchangeError as e:
            if "same tp sl mode1" in str(e):
                # can't fetch the tp sl mode1 value
                return
            raise

    def get_order_additional_params(self, order) -> dict:
        params = {}
        if self.exchange_manager.is_future:
            contract = self.exchange_manager.exchange.get_pair_future_contract(order.symbol)
            params["position_idx"] = self._get_position_idx(contract)
            params["reduce_only"] = order.reduce_only
        return params

    async def get_order(self, order_id: str, symbol: str = None, **kwargs: dict) -> dict:
        try:
            return await super().get_order(order_id, symbol=symbol, **kwargs)
        except octobot_trading.errors.NotSupported:
            # fetchOrder() supports spot markets and linear non-USDC perpetual swap markets only
            if order := await self._private_get_order(order_id, symbol, **kwargs):
                return order
            # try from open & closed orders
            if order := await self.get_order_from_open_and_closed_orders(order_id, symbol, **kwargs):
                return order
            # last chance: try from trades (return None if no order)
            return await self.get_order_from_trades(symbol, order_id)

    async def _private_get_order(self, order_id: str, symbol: str = None, **kwargs: dict) -> dict:
        # try to force fetch order with id even on USDC / non-linear markets
        # from ccxt/async_support/bybit/fetch_order
        # from ccxt/async_support/bybit/fetch_orders
        market = self.connector.client.market(symbol)
        isStop = self.connector.client.safe_value(kwargs, 'stop', False)
        stopOrderId = self.connector.client.safe_string(kwargs, 'stop_order_id')  # might want to filter by id
        orderType = self.connector.client.safe_string_lower(kwargs, 'orderType')
        isConditionalOrder = isStop or (stopOrderId is not None) or (orderType == 'stop' or orderType == 'conditional')
        params = self.connector.client.omit(kwargs, ['orderType', 'stop', 'orderType'])
        if stopOrderId is None:
            if isConditionalOrder:
                orderKey = 'stop_order_id'
            else:
                isUsdcSettled = (market['settle'] == 'USDC')
                orderKey = 'orderId' if isUsdcSettled else 'order_id'
            if order_id is not None:  # The user can also use argument params["order_link_id"] and leave self as None
                params[orderKey] = order_id
        if market['linear']:
            method = 'privateGetPrivateLinearStopOrderList' if isConditionalOrder else 'privateGetPrivateLinearOrderList'
        elif market['future']:
            method = 'privateGetFuturesPrivateStopOrderList' if isConditionalOrder else 'privateGetFuturesPrivateOrderList'
        else:
            # inverse swap
            method = 'privateGetV2PrivateStopOrderList' if isConditionalOrder else 'privateGetV2PrivateOrderList'
        request = {
            'symbol': market['id'],
            # 'order_id': 'string'
            # 'order_link_id': 'string',  # unique client order id, max 36 characters
            # 'symbol': market['id'],  # default BTCUSD
            # 'order': 'desc',  # asc
            # 'page': 1,
            # 'limit': 20,  # max 50
            # 'order_status': 'Created,New'
            # conditional orders ---------------------------------------------
            # 'stop_order_id': 'string',
            # 'stop_order_status': 'Untriggered',
        }
        response = await getattr(self.connector.client, method)(self.connector.client.extend(request, params))
        result = self.connector.client.safe_value(response, 'result', {})
        data = self.connector.client.safe_value(result, 'data', [])
        orders = self.connector.client.parse_orders(data, market)
        for order in orders:
            if order[trading_enums.ExchangeConstantsOrderColumns.ID.value] == order_id:
                return order
        return None



    def get_bundled_order_parameters(self, stop_loss_price=None, take_profit_price=None) -> dict:
        """
        Returns True when this exchange supports orders created upon other orders fill (ex: a stop loss created at
        the same time as a buy order)
        :param stop_loss_price: the bundled order stop_loss price
        :param take_profit_price: the bundled order take_profit price
        :return: A dict with the necessary parameters to create the bundled order on exchange alongside the
        base order in one request
        """
        params = {}
        if stop_loss_price is not None:
            params["stop_loss"] = float(stop_loss_price)
        if take_profit_price is not None:
            params["take_profit"] = float(take_profit_price)
        return params

    def _get_position_idx(self, contract):
        # "position_idx" has to be set when trading futures
        # from https://bybit-exchange.github.io/docs/inverse/#t-myposition
        # Position idx, used to identify positions in different position modes:
        # 0-One-Way Mode
        # 1-Buy side of both side mode
        # 2-Sell side of both side mode
        if contract.is_one_way_position_mode():
            return 0
        else:
            raise NotImplementedError(
                f"Hedge mode is not implemented yet. Please switch to One-Way position mode from the Bybit "
                f"trading interface preferences of {contract.pair}"
            )
            # TODO
            # if Buy side of both side mode:
            #     return 1
            # else Buy side of both side mode:
            #     return 2

    def parse_positions(self, positions) -> list:
        """
        CCXT is returning the position dict as {'data': {position data dict}}
        """
        try:
            return [self.parse_position(position) for position in positions] if positions else []
        except Exception as e:
            self.logger.exception(e, False)
            raise

    def parse_position(self, position_dict) -> dict:
        try:
            raw_position_info = position_dict.get(trading_enums.ExchangePositionCCXTColumns.INFO.value)
            size = decimal.Decimal(position_dict.get(trading_enums.ExchangePositionCCXTColumns.CONTRACTS.value, 0))
            # if size == constants.ZERO:
            #     return {}  # Don't parse empty position

            symbol = self.get_pair_from_exchange(
                position_dict[trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value])
            mode = self._parse_position_mode(raw_position_info.get(self.BYBIT_MODE))
            original_side = position_dict.get(trading_enums.ExchangePositionCCXTColumns.SIDE.value)
            side = self.parse_position_side(original_side, mode)
            unrealized_pnl = self._safe_decimal(position_dict,
                                                trading_enums.ExchangePositionCCXTColumns.UNREALISED_PNL.value,
                                                constants.ZERO)
            liquidation_price = self._safe_decimal(position_dict,
                                                   trading_enums.ExchangePositionCCXTColumns.LIQUIDATION_PRICE.value,
                                                   constants.ZERO)
            entry_price = self._safe_decimal(position_dict,
                                             trading_enums.ExchangePositionCCXTColumns.ENTRY_PRICE.value,
                                             constants.ZERO)
            return {
                trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value: symbol,
                trading_enums.ExchangeConstantsPositionColumns.TIMESTAMP.value:
                    self.parse_timestamp(position_dict,
                                         trading_enums.ExchangePositionCCXTColumns.TIMESTAMP.value, 0),
                trading_enums.ExchangeConstantsPositionColumns.SIDE.value: side,
                trading_enums.ExchangeConstantsPositionColumns.MARGIN_TYPE.value:
                    trading_enums.TraderPositionType(
                        position_dict.get(trading_enums.ExchangePositionCCXTColumns.MARGIN_MODE.value)
                    ),
                trading_enums.ExchangeConstantsPositionColumns.SIZE.value:
                    size if original_side == trading_enums.PositionSide.LONG.value else -size,
                trading_enums.ExchangeConstantsPositionColumns.INITIAL_MARGIN.value:
                    decimal.Decimal(position_dict.get(trading_enums.ExchangePositionCCXTColumns.COLLATERAL.value, 0)),
                trading_enums.ExchangeConstantsPositionColumns.NOTIONAL.value:
                    decimal.Decimal(position_dict.get(trading_enums.ExchangePositionCCXTColumns.NOTIONAL.value, 0)),
                trading_enums.ExchangeConstantsPositionColumns.LEVERAGE.value:
                    decimal.Decimal(position_dict.get(trading_enums.ExchangePositionCCXTColumns.LEVERAGE.value, 1)),
                trading_enums.ExchangeConstantsPositionColumns.UNREALIZED_PNL.value: unrealized_pnl,
                trading_enums.ExchangeConstantsPositionColumns.REALISED_PNL.value:
                    decimal.Decimal(raw_position_info.get(self.BYBIT_REALIZED_PNL, 0)),
                trading_enums.ExchangeConstantsPositionColumns.LIQUIDATION_PRICE.value: liquidation_price,
                trading_enums.ExchangeConstantsPositionColumns.CLOSING_FEE.value:
                    decimal.Decimal(raw_position_info.get(self.BYBIT_CLOSING_FEE, 0)),
                trading_enums.ExchangeConstantsPositionColumns.BANKRUPTCY_PRICE.value:
                    decimal.Decimal(raw_position_info.get(self.BYBIT_BANKRUPTCY_PRICE, 0)),
                trading_enums.ExchangeConstantsPositionColumns.ENTRY_PRICE.value: entry_price,
                trading_enums.ExchangeConstantsPositionColumns.CONTRACT_TYPE.value:
                    self._parse_position_contract_type(symbol),
                trading_enums.ExchangeConstantsPositionColumns.POSITION_MODE.value: mode,
            }
        except KeyError as e:
            self.logger.error(f"Fail to parse position dict ({e})")
        return position_dict

    def _safe_decimal(self, container, key, default):
        if (val := container.get(key, default)) is not None:
            return decimal.Decimal(val)
        return default

    def parse_funding(self, funding_dict, from_ticker=False):
        if from_ticker and constants.CCXT_INFO in funding_dict:
            funding_dict, old_funding_dict = funding_dict[constants.CCXT_INFO], funding_dict

        try:
            """
            Bybit last funding time is not provided
            To obtain the last_funding_time : 
            => timestamp(next_funding_time) - timestamp(BYBIT_DEFAULT_FUNDING_TIME)
            """
            funding_next_timestamp = self.parse_timestamp(
                funding_dict, trading_enums.ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value)
            funding_dict.update({
                trading_enums.ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value:
                    funding_next_timestamp - self.BYBIT_DEFAULT_FUNDING_TIME,
                trading_enums.ExchangeConstantsFundingColumns.FUNDING_RATE.value: decimal.Decimal(
                    funding_dict.get(trading_enums.ExchangeConstantsFundingColumns.FUNDING_RATE.value, 0)),
                trading_enums.ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value: funding_next_timestamp
            })
        except KeyError as e:
            self.logger.error(f"Fail to parse funding dict ({e})")
        return funding_dict

    def parse_mark_price(self, mark_price_dict, from_ticker=False) -> dict:
        if from_ticker and constants.CCXT_INFO in mark_price_dict:
            mark_price_dict = mark_price_dict[constants.CCXT_INFO]

        try:
            mark_price_dict = {
                trading_enums.ExchangeConstantsMarkPriceColumns.MARK_PRICE.value:
                    decimal.Decimal(mark_price_dict.get(
                        trading_enums.ExchangeConstantsMarkPriceColumns.MARK_PRICE.value, 0))
            }
        except KeyError as e:
            self.logger.error(f"Fail to parse mark price dict ({e})")

        return mark_price_dict

    def parse_position_status(self, status):
        statuses = {
            'Normal': 'open',
            'Liq': 'liquidating',
            'Adl': 'auto_deleveraging',
        }
        return trading_enums.PositionStatus(self.connector.client.safe_string(statuses, status, status))

    def _parse_position_contract_type(self, position_pair):
        return self.get_contract_type(position_pair)

    def _parse_position_mode(self, raw_mode):
        if raw_mode == self.BYBIT_ONE_WAY or raw_mode == self.BYBIT_ONE_WAY_DIGIT:
            return trading_enums.PositionMode.ONE_WAY
        if raw_mode == self.BYBIT_HEDGE or raw_mode in self.BYBIT_HEDGE_DIGITS:
            return trading_enums.PositionMode.HEDGE
        return None
