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
from octobot_trading.exchanges.config import ccxt_exchange_settings
from octobot_trading.exchanges.util import parser


class BybitPositionsParser(parser.PositionsParser):
    def __init__(self, exchange):
        super().__init__(exchange=exchange)
        self.MODE_KEY_NAMES = ["mode"]
        self.ONEWAY_VALUES = ("MergedSingle", "0")
        self.HEDGE_VALUES = ("BothSide", "1", "2")


class BybitConnectorSettings(ccxt_exchange_settings.CCXTExchangeConfig):
    POSITIONS_PARSER_CLASS = BybitPositionsParser
    USE_FIXED_MARKET_STATUS = True
    CANDLE_LOADING_LIMIT = 200
    

class Bybit(exchanges.SpotCCXTExchange, exchanges.FutureCCXTExchange):
    
    CONNECTOR_SETTINGS = BybitConnectorSettings
    
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

    MARK_PRICE_IN_TICKER = True
    FUNDING_IN_TICKER = True

    BUY_STR = "Buy"
    SELL_STR = "Sell"

    LONG_STR = BUY_STR
    SHORT_STR = SELL_STR

    # Funding
    BYBIT_FUNDING_TIMESTAMP = "funding_rate_timestamp"
    BYBIT_DEFAULT_FUNDING_TIME = 8 * commons_constants.HOURS_TO_SECONDS

    @classmethod
    def get_name(cls) -> str:
        return 'bybit'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    def get_default_type(self):
        if self.exchange_manager.is_future:
            return 'linear'
        return 'spot'

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
