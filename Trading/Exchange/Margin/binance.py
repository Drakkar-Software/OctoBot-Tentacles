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

from octobot_trading.data.position import ExchangeConstantsPositionColumns

from octobot_trading.enums import ExchangeConstantsOrderColumns
from octobot_trading.exchanges.margin.margin_exchange import MarginExchange


class Binance(MarginExchange):
    DESCRIPTION = ""

    BINANCE_FUTURE_QUANTITY = "positionAmt"
    BINANCE_FUTURE_UNREALIZED_PNL = "unRealizedProfit"

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
                self._cleanup_position_dict(position)
            for position in await self.client.fapiPrivate_get_positionrisk()
        }

    async def set_symbol_leverage(self, symbol: str, leverage: int):
        await self.client.fapiPrivate_post_leverage(
            {"symbol": self.get_exchange_pair(symbol),
             "leverage": leverage})

    def _cleanup_position_dict(self, position):
        try:
            # If exchange has not position id -> global position foreach symbol
            if ExchangeConstantsOrderColumns.ID.value not in position:
                position[ExchangeConstantsOrderColumns.ID.value] = position[
                    ExchangeConstantsOrderColumns.SYMBOL.value]
            if ExchangeConstantsPositionColumns.QUANTITY.value not in position \
                    and self.BINANCE_FUTURE_QUANTITY in position:
                position[ExchangeConstantsPositionColumns.QUANTITY.value] = position[self.BINANCE_FUTURE_QUANTITY]
            if ExchangeConstantsPositionColumns.TIMESTAMP.value not in position:
                position[ExchangeConstantsPositionColumns.TIMESTAMP.value] = 0  # TODO
            if ExchangeConstantsPositionColumns.UNREALISED_PNL.value not in position \
                    and self.BINANCE_FUTURE_UNREALIZED_PNL in position:
                position[ExchangeConstantsPositionColumns.UNREALISED_PNL.value] = position[
                    self.BINANCE_FUTURE_UNREALIZED_PNL]
        except KeyError as e:
            self.logger.error(f"Fail to cleanup position dict ({e})")
        return position
