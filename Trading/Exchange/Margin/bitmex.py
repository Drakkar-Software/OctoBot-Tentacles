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
from ccxt.async_support import bitmex
from octobot_trading.data.position import ExchangeConstantsPositionColumns

from octobot_trading.enums import ExchangeConstantsOrderColumns
from octobot_trading.exchanges.margin.margin_exchange import MarginExchange


class Bitmex(MarginExchange):
    DESCRIPTION = ""

    BITMEX_ENTRY_PRICE = "avgEntryPrice"
    BITMEX_QUANTITY = "currentQty"

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
