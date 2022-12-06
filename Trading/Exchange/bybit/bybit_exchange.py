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
    _BYBIT_BUNDLED_ORDERS = [trading_enums.TraderOrderType.STOP_LOSS, trading_enums.TraderOrderType.TAKE_PROFIT,
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
    BYBIT_BANKRUPTCY_PRICE = "bustPrice"
    BYBIT_CLOSING_FEE = "occClosingFee"
    BYBIT_MODE = "positionIdx"
    BYBIT_REALIZED_PNL = "RealisedPnl"
    BYBIT_ONE_WAY = "MergedSingle"
    BYBIT_ONE_WAY_DIGIT = "0"
    BYBIT_HEDGE = "BothSide"
    BYBIT_HEDGE_DIGITS = ["1", "2"]

    # Funding
    BYBIT_DEFAULT_FUNDING_TIME = 8 * commons_constants.HOURS_TO_SECONDS

    # Orders
    BYBIT_REDUCE_ONLY = "reduceOnly"
    BYBIT_TRIGGER_ABOVE_KEY = "triggerDirection"
    BYBIT_TRIGGER_ABOVE_VALUE = "1"

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

    async def get_positions(self, symbols=None, **kwargs: dict) -> list:
        params = {}
        raw_positions = []
        for settleCoin in ("USDT", "BTC"):
            params["settleCoin"] = settleCoin
            params["dataFilter"] = "full"
            raw_positions += await super().get_positions(symbols=symbols, **params)
        return self.parse_positions(raw_positions)

    async def get_position(self, symbol: str, **kwargs: dict) -> dict:
        raw_positions = await super().get_position(symbol, **kwargs)
        return self.parse_position(raw_positions)

    def clean_order(self, order):
        return super().clean_order(self._update_order_and_trade_data(order))

    def clean_trade(self, trade):
        return super().clean_trade(self._update_order_and_trade_data(trade))

    async def _create_market_stop_loss_order(self, symbol, quantity, price, side, current_price, params=None) -> dict:
        # /contract/v3/private/position/trading-stop ?
        params = params or {}
        params["triggerPrice"] = price
        # Trigger the order when market price rises to triggerPrice or falls to triggerPrice. 1: rise; 2: fall
        params["triggerDirection"] = 1 if price > current_price else 2
        order = await self.connector.client.create_order(symbol, "market", side, quantity, params=params)
        return order

    async def _edit_order(self, order_id: str, order_type: trading_enums.TraderOrderType, symbol: str,
                          quantity: float, price: float, stop_price: float = None, side: str = None,
                          current_price: float = None, params: dict = None):
        params = params or {}
        if order_type in (trading_enums.TraderOrderType.STOP_LOSS, trading_enums.TraderOrderType.STOP_LOSS_LIMIT):
            params["stop_order_id"] = order_id
        if stop_price is not None:
            # params["stop_px"] = stop_price
            # params["stop_loss"] = stop_price
            params["triggerPrice"] = str(stop_price)
        return await super()._edit_order(order_id, order_type, symbol, quantity=quantity,
                                         price=price, stop_price=stop_price, side=side,
                                         current_price=current_price, params=params)

    async def _verify_order(self, created_order, order_type, symbol, price, params=None):
        if order_type in (trading_enums.TraderOrderType.STOP_LOSS, trading_enums.TraderOrderType.STOP_LOSS_LIMIT):
            params = params or {}
            params["stop"] = True
        return await super()._verify_order(created_order, order_type, symbol, price, params=params)

    def _update_order_and_trade_data(self, order):
        order_info = order[trading_enums.ExchangeConstantsOrderColumns.INFO.value]
        # parse reduce_only if present
        order[trading_enums.ExchangeConstantsOrderColumns.REDUCE_ONLY.value] = \
            order_info.get(self.BYBIT_REDUCE_ONLY, False)

        # market orders with stop price are stop loss
        if order.get(trading_enums.ExchangeConstantsOrderColumns.STOP_PRICE.value, None) is not None and \
                order[
                    trading_enums.ExchangeConstantsOrderColumns.TYPE.value] == trading_enums.TradeOrderType.MARKET.value:
            order[trading_enums.ExchangeConstantsOrderColumns.TYPE.value] = trading_enums.TradeOrderType.STOP_LOSS.value
            order[trading_enums.ExchangeConstantsOrderColumns.TRIGGER_ABOVE.value] = \
                order_info[self.BYBIT_TRIGGER_ABOVE_KEY] == self.BYBIT_TRIGGER_ABOVE_VALUE

        return order

    async def cancel_order(self, order_id: str, symbol: str = None, **kwargs: dict) -> trading_enums.OrderStatus:
        return await super().cancel_order(order_id, symbol=symbol, **kwargs)

    async def set_symbol_leverage(self, symbol: str, leverage: int, **kwargs: dict):
        # buy_leverage and sell_leverage are required on Bybit
        kwargs["buy_leverage"] = kwargs.get("buy_leverage", float(leverage))
        kwargs["sell_leverage"] = kwargs.get("sell_leverage", float(leverage))
        return await self.connector.set_symbol_leverage(leverage=leverage, symbol=symbol, **kwargs)

    async def set_symbol_partial_take_profit_stop_loss(self, symbol: str, inverse: bool,
                                                       tp_sl_mode: trading_enums.TakeProfitStopLossMode):
        # /contract/v3/private/position/switch-tpsl-mode
        # from https://bybit-exchange.github.io/docs/derivativesV3/contract/#t-dv_switchpositionmode
        params = {
            "symbol": self.connector.client.market(symbol)['id'],
            "tpSlMode": tp_sl_mode.value
        }
        try:
            await self.connector.client.privatePostContractV3PrivatePositionSwitchTpslMode(params)
        except ccxt.ExchangeError as e:
            if "same tp sl mode1" in str(e):
                # can't fetch the tp sl mode1 value
                return
            raise

    def get_order_additional_params(self, order) -> dict:
        params = {}
        if self.exchange_manager.is_future:
            contract = self.exchange_manager.exchange.get_pair_future_contract(order.symbol)
            params["positionIdx"] = self._get_position_idx(contract)
            params["reduceOnly"] = order.reduce_only
        return params

    async def get_order(self, order_id: str, symbol: str = None, **kwargs: dict) -> dict:
        order = await super().get_order(order_id, symbol=symbol, **kwargs)
        if order is None or order[trading_enums.ExchangeConstantsOrderColumns.SYMBOL.value] is None:
            # order might just have been created / cancelled
            orders = await self.get_open_orders(symbol, orderId=order_id)
            if orders:

                return self._adapt_order_type(orders[0])
        return self._adapt_order_type(order)

    async def get_open_orders(self, symbol: str = None, since: int = None, limit: int = None,
                              **kwargs: dict) -> list:
        orders = await self.connector.get_open_orders(symbol=symbol, since=since, limit=limit, **kwargs)
        for order in orders:
            self._adapt_order_type(order)
        return orders

    def _adapt_order_type(self, order):
        order_info = order[trading_enums.ExchangeConstantsOrderColumns.INFO.value]
        if "StopLoss" in order_info["stopOrderType"] or "Stop" in order_info["stopOrderType"]:
            # stop loss are not tagged as such by ccxt, force it
            order[trading_enums.ExchangeConstantsOrderColumns.TYPE.value] = \
                trading_enums.TradeOrderType.STOP_LOSS.value
        elif "TakeProfit" in order_info["stopOrderType"]:
            # take profit are not tagged as such by ccxt, force it
            order[trading_enums.ExchangeConstantsOrderColumns.TYPE.value] = \
                trading_enums.TradeOrderType.TAKE_PROFIT.value
        return order


    def get_bundled_order_parameters(self, stop_loss_price=None, take_profit_price=None) -> dict:
        """
        Returns True when this exchange supports orders created upon other orders fill (ex: a stop loss created at
        the same time as a buy order)
        :param stop_loss_price: the bundled order stopLoss price
        :param take_profit_price: the bundled order takeProfit price
        :return: A dict with the necessary parameters to create the bundled order on exchange alongside the
        base order in one request
        """
        params = {}
        if stop_loss_price is not None:
            params["stopLoss"] = str(stop_loss_price)
        if take_profit_price is not None:
            params["takeProfit"] = str(take_profit_price)
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
            size = decimal.Decimal(str(position_dict.get(trading_enums.ExchangePositionCCXTColumns.CONTRACTS.value, 0)))
            # if size == constants.ZERO:
            #     return {}  # Don't parse empty position

            symbol = self.get_pair_from_exchange(
                position_dict[trading_enums.ExchangePositionCCXTColumns.SYMBOL.value])
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
                    self.connector.client.safe_value(position_dict, trading_enums.ExchangePositionCCXTColumns.TIMESTAMP.value, 0),
                trading_enums.ExchangeConstantsPositionColumns.SIDE.value: side,
                trading_enums.ExchangeConstantsPositionColumns.MARGIN_TYPE.value:
                    trading_enums.TraderPositionType(
                        position_dict.get(trading_enums.ExchangePositionCCXTColumns.MARGIN_MODE.value)
                    ),
                trading_enums.ExchangeConstantsPositionColumns.SIZE.value:
                    size if original_side == trading_enums.PositionSide.LONG.value else -size,
                trading_enums.ExchangeConstantsPositionColumns.INITIAL_MARGIN.value:
                    self._safe_decimal(
                        position_dict, trading_enums.ExchangePositionCCXTColumns.INITIAL_MARGIN.value, constants.ZERO
                    ),
                trading_enums.ExchangeConstantsPositionColumns.NOTIONAL.value:
                    self._safe_decimal(
                        position_dict, trading_enums.ExchangePositionCCXTColumns.NOTIONAL.value, constants.ZERO
                    ),
                trading_enums.ExchangeConstantsPositionColumns.LEVERAGE.value:
                    self._safe_decimal(
                        position_dict, trading_enums.ExchangePositionCCXTColumns.LEVERAGE.value, constants.ONE
                    ),
                trading_enums.ExchangeConstantsPositionColumns.UNREALIZED_PNL.value: unrealized_pnl,
                trading_enums.ExchangeConstantsPositionColumns.REALISED_PNL.value:
                    self._safe_decimal(
                        position_dict, self.BYBIT_REALIZED_PNL, constants.ZERO
                    ),
                trading_enums.ExchangeConstantsPositionColumns.LIQUIDATION_PRICE.value: liquidation_price,
                trading_enums.ExchangeConstantsPositionColumns.CLOSING_FEE.value:
                    self._safe_decimal(
                        position_dict, self.BYBIT_CLOSING_FEE, constants.ZERO
                    ),
                trading_enums.ExchangeConstantsPositionColumns.BANKRUPTCY_PRICE.value:
                    self._safe_decimal(
                        position_dict, self.BYBIT_BANKRUPTCY_PRICE, constants.ZERO
                    ),
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
            return decimal.Decimal(str(val))
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
            funding_next_timestamp = float(
                funding_dict[trading_enums.ExchangeFundingCCXTColumns.NEXT_FUNDING_TIME.value]
            )
            funding_dict.update({
                trading_enums.ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value:
                    funding_next_timestamp - self.BYBIT_DEFAULT_FUNDING_TIME,
                trading_enums.ExchangeConstantsFundingColumns.FUNDING_RATE.value: decimal.Decimal(
                    funding_dict.get(trading_enums.ExchangeFundingCCXTColumns.FUNDING_RATE.value, 0)),
                trading_enums.ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value: funding_next_timestamp,
                trading_enums.ExchangeConstantsFundingColumns.PREDICTED_FUNDING_RATE.value: constants.NaN
            })
        except KeyError as e:
            self.logger.error(f"Fail to parse funding dict ({e})")
        return funding_dict

    def parse_mark_price(self, mark_price_dict, from_ticker=False) -> dict:
        if from_ticker and constants.CCXT_INFO in mark_price_dict:
            try:
                return {
                    trading_enums.ExchangeConstantsMarkPriceColumns.MARK_PRICE.value:
                        mark_price_dict[constants.CCXT_INFO][trading_enums.ExchangeConstantsMarkPriceColumns.MARK_PRICE.value]
                }
            except KeyError:
                pass
        try:
            mark_price_dict = {
                trading_enums.ExchangeConstantsMarkPriceColumns.MARK_PRICE.value:
                    decimal.Decimal(mark_price_dict[
                        trading_enums.ExchangeConstantsTickersColumns.CLOSE.value])
            }
        except KeyError as e:
            # do not fill mark price with 0 when missing as might liquidate positions
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
