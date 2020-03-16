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
    ExchangeConstantsMarkPriceColumns
from octobot_trading.exchanges.types.future_exchange import FutureExchange
from octobot_trading.exchanges.types.margin_exchange import MarginExchange
from octobot_trading.exchanges.types.spot_exchange import SpotExchange


class Binance(SpotExchange, MarginExchange, FutureExchange):
    DESCRIPTION = ""

    FUNDING_WITH_MARK_PRICE = True

    BINANCE_FUTURE_QUANTITY = "positionAmt"
    BINANCE_FUTURE_UNREALIZED_PNL = "unRealizedProfit"

    BINANCE_MARGIN_TYPE_ISOLATED = "ISOLATED"
    BINANCE_MARGIN_TYPE_CROSSED = "CROSSED"

    BINANCE_FUNDING_RATE = "lastFundingRate"
    BINANCE_NEXT_FUNDING_TIME = "nextFundingTime"
    BINANCE_TIME = "time"
    BINANCE_MARK_PRICE = "markPrice"

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
                self.cleanup_position_dict(position)
            for position in await self.client.fapiPrivate_get_positionrisk()
        }

    async def get_mark_price(self, symbol: str) -> dict:
        return (await self.get_mark_price_and_funding(symbol))[0]

    async def get_funding_rate(self, symbol: str):
        return (await self.get_mark_price_and_funding(symbol))[1]

    async def get_mark_price_and_funding(self, symbol: str) -> tuple:
        return self._cleanup_mark_price_and_funding_dict(await self.client.fapiPublic_get_premiumindex(
            {"symbol": self.get_exchange_pair(symbol)}))

    async def get_funding_rate_history(self, symbol: str, limit: int = 1) -> list:
        return [
            self.cleanup_funding_dict(funding_rate_dict)
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

    def cleanup_position_dict(self, position_dict):
        try:
            # If exchange has not position id -> global position foreach symbol
            if ExchangeConstantsOrderColumns.ID.value not in position_dict:
                position_dict[ExchangeConstantsOrderColumns.ID.value] = position_dict[
                    ExchangeConstantsOrderColumns.SYMBOL.value]
            if ExchangeConstantsPositionColumns.QUANTITY.value not in position_dict \
                    and self.BINANCE_FUTURE_QUANTITY in position_dict:
                position_dict[ExchangeConstantsPositionColumns.QUANTITY.value] = position_dict[self.BINANCE_FUTURE_QUANTITY]
            if ExchangeConstantsPositionColumns.TIMESTAMP.value not in position_dict:
                position_dict[ExchangeConstantsPositionColumns.TIMESTAMP.value] = time.time()  # TODO
            if ExchangeConstantsPositionColumns.UNREALISED_PNL.value not in position_dict \
                    and self.BINANCE_FUTURE_UNREALIZED_PNL in position_dict:
                position_dict[ExchangeConstantsPositionColumns.UNREALISED_PNL.value] = position_dict[
                    self.BINANCE_FUTURE_UNREALIZED_PNL]
        except KeyError as e:
            self.logger.error(f"Fail to cleanup position dict ({e})")
        return position_dict

    def cleanup_funding_dict(self, funding_dict, from_ticker=False):
        try:
            if ExchangeConstantsFundingColumns.FUNDING_RATE.value not in funding_dict \
                    and self.BINANCE_FUNDING_RATE in funding_dict:
                funding_dict[ExchangeConstantsFundingColumns.FUNDING_RATE.value] = funding_dict[
                    self.BINANCE_FUNDING_RATE]

            if ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value not in funding_dict \
                    and self.BINANCE_NEXT_FUNDING_TIME in funding_dict:
                funding_dict[ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value] = funding_dict[
                    self.BINANCE_NEXT_FUNDING_TIME]

            if ExchangeConstantsFundingColumns.TIMESTAMP.value not in funding_dict \
                    and self.BINANCE_TIME in funding_dict:
                funding_dict[ExchangeConstantsFundingColumns.TIMESTAMP.value] = funding_dict[
                    self.BINANCE_TIME]
        except KeyError as e:
            self.logger.error(f"Fail to cleanup funding dict ({e})")
        return funding_dict

    def cleanup_mark_price_dict(self, mark_price_dict, from_ticker=False):
        try:
            if ExchangeConstantsMarkPriceColumns.TIMESTAMP.value not in mark_price_dict \
                    and self.BINANCE_TIME in mark_price_dict:
                mark_price_dict[ExchangeConstantsMarkPriceColumns.TIMESTAMP.value] = mark_price_dict[
                    self.BINANCE_TIME]

            if ExchangeConstantsMarkPriceColumns.MARK_PRICE.value not in mark_price_dict \
                    and self.BINANCE_MARK_PRICE in mark_price_dict:
                mark_price_dict[ExchangeConstantsMarkPriceColumns.MARK_PRICE.value] = mark_price_dict[
                    self.BINANCE_MARK_PRICE]
        except KeyError as e:
            self.logger.error(f"Fail to cleanup mark_price dict ({e})")
        return mark_price_dict

    def _cleanup_mark_price_and_funding_dict(self, mark_price_and_funding_dict):
        return self.cleanup_mark_price_dict(mark_price_and_funding_dict), \
               self.cleanup_funding_dict(mark_price_and_funding_dict)
