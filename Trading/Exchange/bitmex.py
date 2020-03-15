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
from octobot_commons.timestamp_util import datetime_to_timestamp, create_datetime_from_string

from octobot_trading.data.position import ExchangeConstantsPositionColumns

from octobot_trading.enums import ExchangeConstantsOrderColumns, ExchangeConstantsFundingColumns
from octobot_trading.exchanges.types.future_exchange import FutureExchange


class Bitmex(FutureExchange):
    DESCRIPTION = ""

    MARK_PRICE_IN_POSITION = True

    BITMEX_ENTRY_PRICE = "avgEntryPrice"
    BITMEX_QUANTITY = "currentQty"
    BITMEX_FUNDING_RATE = "fundingRate"
    BITMEX_FUNDING_INTERV = "fundingInterval"

    BITMEX_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

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

    async def get_symbol_open_positions(self, symbol: str) -> dict:
        return self._cleanup_position_dict(
            (await self.client.private_get_position(self.get_filter_from_dict(
                {"symbol": self.get_exchange_pair(symbol),
                 "isOpen": True})))[0])

    async def set_symbol_leverage(self, symbol: str, leverage: int):
        await self.client.private_post_position_leverage(
            {"symbol": self.get_exchange_pair(symbol),
             "leverage": leverage})

    async def set_symbol_margin_type(self, symbol: str, isolated: bool):
        await self.client.private_post_position_isolate(
            {"symbol": self.get_exchange_pair(symbol),
             "enabled": True if isolated else False})

    async def get_funding_rate(self, symbol: str, limit: int = 1):
        return self._cleanup_funding_dict((await self.client.public_get_funding(
            {"symbol": self.get_exchange_pair(symbol),
             "count": limit,
             "reverse": True}))[0])

    def _cleanup_position_dict(self, position) -> dict:
        try:
            # If exchange has not position id -> global position foreach symbol
            if ExchangeConstantsOrderColumns.ID.value not in position:
                position[ExchangeConstantsOrderColumns.ID.value] = position[
                    ExchangeConstantsOrderColumns.SYMBOL.value]
            if ExchangeConstantsPositionColumns.ENTRY_PRICE.value not in position \
                    and self.BITMEX_ENTRY_PRICE in position:
                position[ExchangeConstantsPositionColumns.ENTRY_PRICE.value] = position[self.BITMEX_ENTRY_PRICE]
            if ExchangeConstantsPositionColumns.QUANTITY.value not in position \
                    and self.BITMEX_QUANTITY in position:
                position[ExchangeConstantsPositionColumns.QUANTITY.value] = position[self.BITMEX_QUANTITY]
        except KeyError as e:
            self.logger.error(f"Fail to cleanup position dict ({e})")
        return position

    def _cleanup_funding_dict(self, funding_dict):
        try:
            if ExchangeConstantsFundingColumns.FUNDING_RATE.value not in funding_dict \
                    and self.BITMEX_FUNDING_RATE in funding_dict:
                funding_dict[ExchangeConstantsFundingColumns.FUNDING_RATE.value] = funding_dict[
                    self.BITMEX_FUNDING_RATE]

            if ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value not in funding_dict \
                    and self.BITMEX_FUNDING_INTERV in funding_dict:
                funding_dict[ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value] = \
                    datetime_to_timestamp(funding_dict[ExchangeConstantsFundingColumns.TIMESTAMP.value],
                                          date_time_format=self.BITMEX_DATETIME_FORMAT) + \
                    (create_datetime_from_string(funding_dict[self.BITMEX_FUNDING_INTERV],
                                                 date_time_format=self.BITMEX_DATETIME_FORMAT).hour + 1) * HOURS_TO_SECONDS  # TODO manage timezone
        except KeyError as e:
            self.logger.error(f"Fail to cleanup funding dict ({e})")
        return funding_dict
