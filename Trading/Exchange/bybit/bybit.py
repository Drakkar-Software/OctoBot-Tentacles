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
import time

from octobot_commons.constants import HOURS_TO_SECONDS
from octobot_trading.constants import CCXT_INFO
from octobot_trading.enums import ExchangeConstantsPositionColumns, \
    ExchangeConstantsFundingColumns, PositionSide, PositionStatus, ExchangeConstantsMarkPriceColumns
from octobot_trading.exchanges.types.future_exchange import FutureExchange


class Bybit(FutureExchange):
    DESCRIPTION = ""

    BUY_STR = "Buy"
    SELL_STR = "Sell"

    MARK_PRICE_IN_TICKER = True
    FUNDING_IN_TICKER = True

    # Position
    BYBIT_SIZE = "size"
    BYBIT_VALUE = "position_value"
    BYBIT_MARGIN = "position_margin"
    BYBIT_STATUS = "position_status"
    BYBIT_LIQUIDATION_PRICE = "liq_price"
    BYBIT_TIMESTAMP = "created_at"

    # Funding
    BYBIT_FUNDING_TIMESTAMP = "funding_rate_timestamp"
    BYBIT_DEFAULT_FUNDING_TIME = 8 * HOURS_TO_SECONDS

    @classmethod
    def get_name(cls):
        return 'bybit'

    # override to add url
    def set_sandbox_mode(self, is_sandboxed):
        if is_sandboxed:
            self.client.urls['api'] = 'https://testnet.bybit.com'
        self.client.setSandboxMode(is_sandboxed)

    async def get_symbol_open_positions(self, symbol: str) -> list:
        return [self.parse_position((await self.client.private_get_position_list(
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
        return self.parse_funding((await self.client.openapi_get_funding_prev_funding_rate(
            {"symbol": self.get_exchange_pair(symbol)}))["result"])

    # async def get_kline_price(self, symbol, time_frame):
    #     try:
    #         await self.client.public_get_kline_list(
    #             {
    #                 "symbol": self.get_exchange_pair(symbol),
    #                 "interval": "",
    #                 "from": "",
    #                 "limit": 1
    #              })
    #     except BaseError as e:
    #         self.logger.error(f"Failed to get_kline_price {e}")
    #         return None

    def parse_position(self, position_dict) -> dict:
        try:
            position_dict.update({
                ExchangeConstantsPositionColumns.ID.value:
                    self.client.safe_string(position_dict,
                                            ExchangeConstantsPositionColumns.ID.value,
                                            position_dict[ExchangeConstantsPositionColumns.SYMBOL.value]),
                ExchangeConstantsPositionColumns.QUANTITY.value:
                    self.client.safe_float(position_dict, self.BYBIT_SIZE, 0),
                ExchangeConstantsPositionColumns.VALUE.value:
                    self.client.safe_float(position_dict, self.BYBIT_VALUE, 0),
                ExchangeConstantsPositionColumns.MARGIN.value:
                    self.client.safe_float(position_dict, self.BYBIT_MARGIN, 0),
                ExchangeConstantsPositionColumns.UNREALISED_PNL.value:
                # TODO currently resets the unrealised PNL on position update with WS
                    self.client.safe_float(position_dict, ExchangeConstantsPositionColumns.UNREALISED_PNL.value, 0),
                ExchangeConstantsPositionColumns.LIQUIDATION_PRICE.value:
                    self.client.safe_float(position_dict, self.BYBIT_LIQUIDATION_PRICE, 0),
                ExchangeConstantsPositionColumns.TIMESTAMP.value:
                    self.parse_timestamp(position_dict, self.BYBIT_TIMESTAMP),
                ExchangeConstantsPositionColumns.STATUS.value:
                    self.parse_position_status(self.client.safe_string(position_dict,
                                                                       ExchangeConstantsPositionColumns.STATUS.value,
                                                                       default_value=PositionStatus.OPEN.value)),
                ExchangeConstantsPositionColumns.SIDE.value:
                    self.parse_position_side(self.client.safe_string(position_dict,
                                                                     ExchangeConstantsPositionColumns.SIDE.value,
                                                                     default_value=PositionSide.UNKNOWN.value)),
                ExchangeConstantsPositionColumns.MARK_PRICE.value:
                    self.client.safe_float(position_dict, ExchangeConstantsPositionColumns.MARK_PRICE.value, 0)
            })
        except KeyError as e:
            self.logger.error(f"Fail to parse position dict ({e})")
        return position_dict if position_dict[self.BYBIT_SIZE] != 0 else None

    def parse_funding(self, funding_dict, from_ticker=False):
        if from_ticker and CCXT_INFO in funding_dict:
            funding_dict, old_funding_dict = funding_dict[CCXT_INFO], funding_dict

        try:
            """
            Bybit last funding time is not provided
            To obtain the last_funding_time : 
            => timestamp(next_funding_time) - timestamp(BYBIT_DEFAULT_FUNDING_TIME)
            """
            funding_next_timestamp = self.parse_timestamp(funding_dict,
                                                          ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value)
            funding_dict.update({
                ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value:
                    funding_next_timestamp - self.BYBIT_DEFAULT_FUNDING_TIME,
                ExchangeConstantsFundingColumns.FUNDING_RATE.value:
                    self.client.safe_float(funding_dict, ExchangeConstantsFundingColumns.FUNDING_RATE.value),
                ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value: funding_next_timestamp
            })
        except KeyError as e:
            self.logger.error(f"Fail to parse funding dict ({e})")
        return funding_dict

    def parse_mark_price(self, mark_price_dict, from_ticker=False) -> dict:
        if from_ticker and CCXT_INFO in mark_price_dict:
            mark_price_dict = mark_price_dict[CCXT_INFO]

        try:
            mark_price_dict = {
                ExchangeConstantsMarkPriceColumns.MARK_PRICE.value:
                    self.client.safe_float(mark_price_dict, ExchangeConstantsMarkPriceColumns.MARK_PRICE.value, 0)
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
        return PositionStatus(self.client.safe_string(statuses, status, status))
