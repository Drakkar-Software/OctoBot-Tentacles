"""
OctoBot Tentacle

$tentacle_description: {
    "package_name": "OctoBot-Tentacles",
    "name": "bitmex",
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
from octobot_commons.constants import HOURS_TO_SECONDS

from octobot_commons.timestamp_util import datetime_to_timestamp
from octobot_trading.constants import CCXT_INFO

from octobot_trading.data.position import ExchangeConstantsPositionColumns

from octobot_trading.enums import ExchangeConstantsFundingColumns, \
    ExchangeConstantsMarkPriceColumns, PositionStatus, PositionSide
from octobot_trading.exchanges.types.future_exchange import FutureExchange


class Bitmex(FutureExchange):
    DESCRIPTION = ""

    BUY_STR = "Buy"
    SELL_STR = "Sell"

    MARK_PRICE_IN_TICKER = True
    FUNDING_IN_TICKER = True

    # MARK_PRICE_IN_POSITION = True

    BITMEX_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    # Position
    BITMEX_ENTRY_PRICE = "avgEntryPrice"
    BITMEX_QUANTITY = "currentQty"
    BITMEX_VALUE = "markValue"
    BITMEX_MARGIN = "posMargin"
    BITMEX_LIQUIDATION_PRICE = "liquidationPrice"
    BITMEX_UNREALISED_PNL = "unrealisedPnl"
    BITMEX_REALISED_PNL = "realisedPnl"

    # Funding
    BITMEX_LAST_FUNDING_TIME = "timestamp"
    BITMEX_FUNDING_TIMESTAMP = "fundingTimestamp"
    BITMEX_FUNDING_RATE = "fundingRate"
    BITMEX_FUNDING_INTERV = "fundingInterval"
    BITMEX_FUNDING_INTERVAL_REF = "2000-01-01T00:00:00.000Z"
    BITMEX_FUNDING_INTERVAL_REF_TS = datetime_to_timestamp(BITMEX_FUNDING_INTERVAL_REF,
                                                           date_time_format=BITMEX_DATETIME_FORMAT)
    BITMEX_DEFAULT_FUNDING_TIME = 8 * HOURS_TO_SECONDS

    # Mark price
    BITMEX_MARK_PRICE = "markPrice"

    @classmethod
    def get_name(cls):
        return 'bitmex'

    # override to add url
    def set_sandbox_mode(self, is_sandboxed):
        if is_sandboxed:
            self.client.urls['api'] = 'https://testnet.bitmex.com'
        self.client.setSandboxMode(is_sandboxed)

    def get_filter_from_dict(self, kwargs) -> dict:
        return {"filter": self.client.json(kwargs)}

    async def get_symbol_open_positions(self, symbol: str) -> list:
        positions: list = await self.client.private_get_position(self.get_filter_from_dict(
            {"symbol": self.get_exchange_pair(symbol), "isOpen": True}))
        if positions:
            return [self.parse_position(position) for position in positions]
        return []

    async def set_symbol_leverage(self, symbol: str, leverage: int):
        await self.client.private_post_position_leverage(
            {"symbol": self.get_exchange_pair(symbol),
             "leverage": leverage})

    async def set_symbol_margin_type(self, symbol: str, isolated: bool):
        await self.client.private_post_position_isolate(
            {"symbol": self.get_exchange_pair(symbol),
             "enabled": True if isolated else False})

    async def get_funding_rate(self, symbol: str):
        return (await self.get_funding_rate_history(symbol, limit=1))[0]

    async def get_funding_rate_history(self, symbol: str, limit: int = 1) -> list:
        return [
            self.parse_funding(funding_rate_dict)
            for funding_rate_dict in (await self.client.public_get_funding(
                {"symbol": self.get_exchange_pair(symbol),
                 "count": limit,
                 "reverse": True}))
        ]

    def parse_position(self, position_dict) -> dict:
        try:
            position_dict.update({
                ExchangeConstantsPositionColumns.ID.value:
                    self.client.safe_string(position_dict,
                                            ExchangeConstantsPositionColumns.ID.value,
                                            position_dict[ExchangeConstantsPositionColumns.SYMBOL.value]),
                ExchangeConstantsPositionColumns.QUANTITY.value:
                    self.client.safe_float(position_dict, self.BITMEX_QUANTITY, 0),
                ExchangeConstantsPositionColumns.VALUE.value:
                    self.client.safe_float(position_dict, self.BITMEX_VALUE, 0),
                ExchangeConstantsPositionColumns.MARGIN.value:
                    self.client.safe_float(position_dict, self.BITMEX_MARGIN, 0),
                ExchangeConstantsPositionColumns.UNREALISED_PNL.value:
                    self.client.safe_float(position_dict, self.BITMEX_UNREALISED_PNL, 0),
                ExchangeConstantsPositionColumns.REALISED_PNL.value:
                    self.client.safe_float(position_dict, self.BITMEX_REALISED_PNL, 0),
                ExchangeConstantsPositionColumns.LIQUIDATION_PRICE.value:
                    self.client.safe_float(position_dict, self.BITMEX_LIQUIDATION_PRICE, 0),
                ExchangeConstantsPositionColumns.MARK_PRICE.value:
                    self.client.safe_float(position_dict, self.BITMEX_MARK_PRICE, 0),
                ExchangeConstantsPositionColumns.ENTRY_PRICE.value:
                    self.client.safe_float(position_dict, self.BITMEX_ENTRY_PRICE, 0),
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
        if from_ticker and CCXT_INFO in funding_dict:
            funding_dict = funding_dict[CCXT_INFO]
        try:
            if from_ticker:
                """
                Bitmex last funding time is not provided
                To obtain the last_funding_time : 
                => timestamp(next_funding_time) - timestamp(BITMEX_DEFAULT_FUNDING_TIME)
                """
                next_funding_ts = self.parse_timestamp(funding_dict, self.BITMEX_FUNDING_TIMESTAMP)
                funding_dict = {
                    ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value:
                        next_funding_ts - self.BITMEX_DEFAULT_FUNDING_TIME,
                    ExchangeConstantsFundingColumns.FUNDING_RATE.value:
                        self.client.safe_float(funding_dict, self.BITMEX_FUNDING_RATE),
                    ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value: next_funding_ts
                }
            else:
                """
                Bitmex funding interval is '2000-01-01T08:00:00.000Z'
                To obtain the next_funding_time : 
                => timestamp(funding_interval) - timestamp('2000-01-01T00:00:00.000Z') + timestamp(last_funding_time)
                """
                funding_ts = self.parse_timestamp(funding_dict, self.BITMEX_LAST_FUNDING_TIME)
                funding_dict = {
                    ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value: funding_ts,
                    ExchangeConstantsFundingColumns.FUNDING_RATE.value:
                        self.client.safe_float(funding_dict, self.BITMEX_FUNDING_RATE),
                    ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value:
                        datetime_to_timestamp(funding_dict.get(self.BITMEX_FUNDING_INTERV),
                                              date_time_format=self.BITMEX_DATETIME_FORMAT) -
                        self.BITMEX_FUNDING_INTERVAL_REF_TS + funding_ts
                }
        except KeyError as e:
            self.logger.error(f"Fail to parse funding dict ({e})")
        return funding_dict

    def parse_mark_price(self, mark_price_dict, from_ticker=False) -> dict:
        if from_ticker and CCXT_INFO in mark_price_dict:
            mark_price_dict = mark_price_dict[CCXT_INFO]

        try:
            mark_price_dict = {
                ExchangeConstantsMarkPriceColumns.MARK_PRICE.value:
                    self.client.safe_float(mark_price_dict, self.BITMEX_MARK_PRICE, 0)
            }
        except KeyError as e:
            self.logger.error(f"Fail to parse mark price dict ({e})")

        return mark_price_dict
