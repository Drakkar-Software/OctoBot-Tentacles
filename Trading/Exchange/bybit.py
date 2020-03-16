"""
OctoBot Tentacle

$tentacle_description: {
    "package_name": "OctoBot-Tentacles",
    "name": "bybit",
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
from octobot_trading.constants import CCXT_INFO

from octobot_trading.enums import ExchangeConstantsOrderColumns, ExchangeConstantsPositionColumns, \
    ExchangeConstantsFundingColumns
from octobot_trading.exchanges.types.future_exchange import FutureExchange


class Bybit(FutureExchange):
    DESCRIPTION = ""

    MARK_PRICE_IN_TICKER = True
    FUNDING_IN_TICKER = True

    BYBIT_SIZE = "size"
    BYBIT_QUANTITY = "position_value"
    BYBIT_ENTRY_PRICE = "entry_price"
    BYBIT_LIQUIDATION_PRICE = "liq_price"
    BYBIT_TIMESTAMP = "created_at"
    BYBIT_MARK_PRICE = ""
    BYBIT_UNREALISED_PNL = "unrealised_pnl"

    BYBIT_FUNDING_TIMESTAMP = "funding_rate_timestamp"
    BYBIT_DEFAULT_FUNDING_TIME = 8 * HOURS_TO_SECONDS

    BYBIT_TIME = "time_now"

    @classmethod
    def get_name(cls):
        return 'bybit'

    # override to add url
    def set_sandbox_mode(self, is_sandboxed):
        if is_sandboxed:
            self.client.urls['api'] = 'https://testnet.bybit.com'
        self.client.setSandboxMode(is_sandboxed)

    async def get_symbol_open_positions(self, symbol: str) -> list:
        return [self.cleanup_position_dict((await self.client.private_get_position_list(
            {"symbol": self.get_exchange_pair(symbol)}))['result'])]

    async def set_symbol_leverage(self, symbol: str, leverage: int):
        # TODO returned error during implementation tests
        await self.client.user_post_leverage_save(
            {"symbol": self.get_exchange_pair(symbol),
             "leverage": leverage})

    async def get_symbol_leverage(self, symbol: str):
        # TODO returned error during implementation tests
        user_leverage = await self.client.user_get_leverage()
        return user_leverage["result"][symbol] if symbol in user_leverage["result"] else None

    async def set_symbol_margin_type(self, symbol: str, isolated: bool):
        # TODO add check if leverage is > 0 when isolated = True
        if not isolated:
            await self.set_symbol_leverage(symbol, 0)

    async def get_funding_rate(self, symbol: str):
        return self.cleanup_funding_dict((await self.client.openapi_get_funding_prev_funding_rate(
            {"symbol": self.get_exchange_pair(symbol)}))["result"])

    def cleanup_position_dict(self, position_dict) -> dict:
        try:
            # If exchange has not position id -> global position foreach symbol
            if ExchangeConstantsPositionColumns.ID.value not in position_dict:
                position_dict[ExchangeConstantsOrderColumns.ID.value] = position_dict[
                    ExchangeConstantsOrderColumns.SYMBOL.value]
            if ExchangeConstantsPositionColumns.ENTRY_PRICE.value not in position_dict \
                    and self.BYBIT_ENTRY_PRICE in position_dict:
                position_dict[ExchangeConstantsPositionColumns.ENTRY_PRICE.value] = position_dict[
                    self.BYBIT_ENTRY_PRICE]
            if ExchangeConstantsPositionColumns.QUANTITY.value not in position_dict \
                    and self.BYBIT_QUANTITY in position_dict:
                position_dict[ExchangeConstantsPositionColumns.QUANTITY.value] = position_dict[self.BYBIT_QUANTITY]
            if ExchangeConstantsPositionColumns.LIQUIDATION_PRICE.value not in position_dict \
                    and self.BYBIT_LIQUIDATION_PRICE in position_dict:
                position_dict[ExchangeConstantsPositionColumns.LIQUIDATION_PRICE.value] = position_dict[
                    self.BYBIT_LIQUIDATION_PRICE]
            if ExchangeConstantsPositionColumns.TIMESTAMP.value not in position_dict \
                    and self.BYBIT_TIMESTAMP in position_dict:
                position_dict[ExchangeConstantsPositionColumns.TIMESTAMP.value] = position_dict[self.BYBIT_TIMESTAMP]
            if ExchangeConstantsPositionColumns.MARK_PRICE.value not in position_dict:
                position_dict[ExchangeConstantsPositionColumns.MARK_PRICE.value] = None  # TODO
            if ExchangeConstantsPositionColumns.UNREALISED_PNL.value not in position_dict \
                    and self.BYBIT_UNREALISED_PNL in position_dict:
                position_dict[ExchangeConstantsPositionColumns.UNREALISED_PNL.value] = position_dict[
                    self.BYBIT_UNREALISED_PNL]
        except KeyError as e:
            self.logger.error(f"Fail to cleanup position dict ({e})")
        return position_dict if position_dict[self.BYBIT_SIZE] != 0 else None

    def cleanup_funding_dict(self, funding_dict, from_ticker=False):
        old_funding_dict = {}
        if from_ticker and CCXT_INFO in funding_dict:
            funding_dict, old_funding_dict = funding_dict[CCXT_INFO], funding_dict

        try:
            if ExchangeConstantsFundingColumns.TIMESTAMP.value not in funding_dict \
                    and self.BYBIT_FUNDING_TIMESTAMP in funding_dict:
                funding_dict[ExchangeConstantsFundingColumns.TIMESTAMP.value] = funding_dict[
                    self.BYBIT_FUNDING_TIMESTAMP]

            # if still empty use old_funding_dict if available
            if old_funding_dict and ExchangeConstantsFundingColumns.TIMESTAMP.value not in funding_dict \
                    and CCXT_INFO in old_funding_dict:
                funding_dict[ExchangeConstantsFundingColumns.TIMESTAMP.value] = old_funding_dict[CCXT_INFO]

            if ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value not in funding_dict:
                funding_dict[ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value] = \
                    funding_dict[
                        ExchangeConstantsFundingColumns.TIMESTAMP.value] + self.BYBIT_DEFAULT_FUNDING_TIME  # TODO manage timezone

        except KeyError as e:
            self.logger.error(f"Fail to cleanup funding dict ({e})")
        return funding_dict

    def cleanup_mark_price_dict(self, mark_price_dict, from_ticker=False) -> dict:
        if from_ticker and CCXT_INFO in mark_price_dict:
            mark_price_dict = mark_price_dict[CCXT_INFO]
        return mark_price_dict
