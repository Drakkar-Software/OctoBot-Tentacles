"""
OctoBot Tentacle

$tentacle_description: {
    "package_name": "OctoBot-Tentacles",
    "name": "binance",
    "type": "Trading",
    "subtype": "Exchange",
    "version": "1.0.0",
}
"""

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

from octobot_trading.data.position import ExchangeConstantsPositionColumns
from octobot_trading.enums import ExchangeConstantsOrderColumns, ExchangeConstantsFundingColumns, \
    ExchangeConstantsMarkPriceColumns, PositionStatus, PositionSide
from octobot_trading.exchanges.types.future_exchange import FutureExchange
from octobot_trading.exchanges.types.margin_exchange import MarginExchange
from octobot_trading.exchanges.types.spot_exchange import SpotExchange


class Binance(SpotExchange, MarginExchange, FutureExchange):
    DESCRIPTION = ""

    BUY_STR = "BUY"
    SELL_STR = "SELL"

    FUNDING_WITH_MARK_PRICE = True

    BINANCE_FUTURE_QUANTITY = "positionAmt"
    BINANCE_FUTURE_UNREALIZED_PNL = "unRealizedProfit"
    BINANCE_FUTURE_LIQUIDATION_PRICE = "liquidationPrice"
    BINANCE_FUTURE_VALUE = "liquidationPrice"

    BINANCE_MARGIN_TYPE_ISOLATED = "ISOLATED"
    BINANCE_MARGIN_TYPE_CROSSED = "CROSSED"

    BINANCE_FUNDING_RATE = "lastFundingRate"
    BINANCE_NEXT_FUNDING_TIME = "nextFundingTime"
    BINANCE_TIME = "time"
    BINANCE_MARK_PRICE = "markPrice"
    BINANCE_ENTRY_PRICE = "entryPrice"

    CCXT_CLIENT_LOGIN_OPTIONS = {'defaultMarket': 'future'}

    @classmethod
    def get_name(cls):
        return 'binance'

    # override to add url
    def set_sandbox_mode(self, is_sandboxed):
        if is_sandboxed:
            self.client.urls['test'] = {
                'public': 'https://testnet.binancefuture.com/fapi/v1',
                'private': 'https://testnet.binancefuture.com/fapi/v1',
                'fapiPublic': 'https://testnet.binancefuture.com/fapi/v1',
                'fapiPrivate': 'https://testnet.binancefuture.com/fapi/v1'
            }

        self.client.setSandboxMode(is_sandboxed)

    async def get_open_positions(self) -> dict:
        return {
            self.get_pair_from_exchange(position[ExchangeConstantsOrderColumns.SYMBOL.value]):
                self.parse_position(position)
            for position in await self.client.fapiPrivate_get_positionrisk()
        }

    async def get_mark_price(self, symbol: str) -> dict:
        return (await self.get_mark_price_and_funding(symbol))[0]

    async def get_funding_rate(self, symbol: str):
        return (await self.get_mark_price_and_funding(symbol))[1]

    async def get_mark_price_and_funding(self, symbol: str) -> tuple:
        return self._parse_mark_price_and_funding_dict(await self.client.fapiPublic_get_premiumindex(
            {"symbol": self.get_exchange_pair(symbol)}))

    async def get_funding_rate_history(self, symbol: str, limit: int = 1) -> list:
        return [
            self.parse_funding(funding_rate_dict)
            for funding_rate_dict in (await self.client.fapiPublic_get_funding_rate(
                {"symbol": self.get_exchange_pair(symbol),
                 "limit": limit}))
        ]

    async def set_symbol_leverage(self, symbol: str, leverage: int):
        await self.client.fapiPrivate_post_leverage(
            {"symbol": self.get_exchange_pair(symbol),
             "leverage": leverage})

    async def set_symbol_margin_type(self, symbol: str, isolated: bool):
        await self.client.fapiPrivate_post_marginType(
            {"symbol": self.get_exchange_pair(symbol),
             "marginType": self.BINANCE_MARGIN_TYPE_ISOLATED if isolated else self.BINANCE_MARGIN_TYPE_CROSSED})

    def parse_position(self, position_dict):
        try:
            position_dict.update({
                ExchangeConstantsPositionColumns.ID.value:
                    self.client.safe_string(position_dict,
                                            ExchangeConstantsPositionColumns.ID.value,
                                            position_dict[ExchangeConstantsPositionColumns.SYMBOL.value]),
                ExchangeConstantsPositionColumns.QUANTITY.value:
                    self.client.safe_float(position_dict, self.BINANCE_FUTURE_QUANTITY, 0),
                ExchangeConstantsPositionColumns.VALUE.value:
                    self.calculate_position_value(
                        self.client.safe_float(position_dict, [ExchangeConstantsPositionColumns.QUANTITY.value], 0),
                        self.client.safe_float(position_dict, [ExchangeConstantsPositionColumns.MARK_PRICE.value], 1)),
                ExchangeConstantsPositionColumns.MARGIN.value:
                # TODO
                    self.client.safe_float(position_dict, ExchangeConstantsPositionColumns.MARGIN.value, 0),
                ExchangeConstantsPositionColumns.UNREALISED_PNL.value:
                    self.client.safe_float(position_dict, self.BINANCE_FUTURE_UNREALIZED_PNL, 0),
                ExchangeConstantsPositionColumns.REALISED_PNL.value:
                # TODO
                    self.client.safe_float(position_dict, ExchangeConstantsPositionColumns.REALISED_PNL.value, 0),
                ExchangeConstantsPositionColumns.LIQUIDATION_PRICE.value:
                    self.client.safe_float(position_dict, self.BINANCE_FUTURE_LIQUIDATION_PRICE, 0),
                ExchangeConstantsPositionColumns.MARK_PRICE.value:
                    self.client.safe_float(position_dict, self.BINANCE_MARK_PRICE, 0),
                ExchangeConstantsPositionColumns.ENTRY_PRICE.value:
                    self.client.safe_float(position_dict, self.BINANCE_ENTRY_PRICE, 0),
                ExchangeConstantsPositionColumns.TIMESTAMP.value:
                # TODO
                    self.client.safe_float(position_dict, ExchangeConstantsPositionColumns.TIMESTAMP.value,
                                           time.time()),
                ExchangeConstantsPositionColumns.STATUS.value:
                    self.parse_position_status(self.client.safe_string(position_dict,
                                                                       ExchangeConstantsPositionColumns.STATUS.value,
                                                                       default_value=PositionStatus.OPEN.value)),
                ExchangeConstantsPositionColumns.SIDE.value:
                    self.parse_position_side(self.client.safe_string(position_dict,
                                                            ExchangeConstantsPositionColumns.SIDE.value,
                                                            default_value=PositionSide.UNKNOWN.value)),
            })
        except KeyError as e:
            self.logger.error(f"Fail to parse position dict ({e})")
        return position_dict

    def parse_funding(self, funding_dict, from_ticker=False):
        try:
            funding_dict = {
                ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value:
                    self.parse_timestamp(funding_dict, self.BINANCE_TIME),
                ExchangeConstantsFundingColumns.FUNDING_RATE.value:
                    self.client.safe_float(funding_dict, self.BINANCE_FUNDING_RATE),
                ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value:
                    self.parse_timestamp(funding_dict, self.BINANCE_NEXT_FUNDING_TIME)
            }
        except KeyError as e:
            self.logger.error(f"Fail to parse funding dict ({e})")
        return funding_dict

    def parse_mark_price(self, mark_price_dict, from_ticker=False):
        try:
            mark_price_dict = {
                ExchangeConstantsMarkPriceColumns.MARK_PRICE.value:
                    self.client.safe_float(mark_price_dict, self.BINANCE_MARK_PRICE, 0)
            }
        except KeyError as e:
            self.logger.error(f"Fail to parse mark_price dict ({e})")
        return mark_price_dict

    def _parse_mark_price_and_funding_dict(self, mark_price_and_funding_dict):
        return self.parse_mark_price(mark_price_and_funding_dict), \
               self.parse_funding(mark_price_and_funding_dict)
