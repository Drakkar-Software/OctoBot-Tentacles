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
import octobot_commons.constants as common_constants
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges

    
class Binance(exchanges.SpotCCXTExchange, exchanges.FutureCCXTExchange):  
    DESCRIPTION = ""

    BUY_STR = "BUY"
    SELL_STR = "SELL"

    ACCOUNTS = {
        trading_enums.AccountTypes.CASH: 'cash',
        trading_enums.AccountTypes.MARGIN: 'margin',
        trading_enums.AccountTypes.FUTURE: 'future'
    }

    MARK_PRICE_IN_POSITION = True

    BINANCE_SYMBOL = "symbol"

    BINANCE_FUTURE_UNREALIZED_PNL = "unRealizedProfit"
    BINANCE_FUTURE_LIQUIDATION_PRICE = "liquidationPrice"
    BINANCE_FUTURE_VALUE = "liquidationPrice"

    BINANCE_MARGIN_TYPE = "marginType"
    BINANCE_MARGIN_TYPE_ISOLATED = "ISOLATED"
    BINANCE_MARGIN_TYPE_CROSSED = "CROSSED"

    BINANCE_FUNDING_RATE = "fundingRate"
    BINANCE_LAST_FUNDING_TIME = "fundingTime"
    BINANCE_FUNDING_DURATION = 8 * common_constants.HOURS_TO_SECONDS

    BINANCE_TIME = "time"
    BINANCE_MARK_PRICE = "markPrice"
    BINANCE_ENTRY_PRICE = "entryPrice"


    @classmethod
    def get_name(cls):
        return 'binance'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    def _get_params(self, params):
        if params is None:
            params = {}
        params.update({'recvWindow': 60000})
        return params

    async def get_balance(self, **kwargs):
        return await exchanges.SpotCCXTExchange.get_balance(self, **self._get_params(kwargs))

    async def get_funding_rate_history(self, symbol: str, limit: int = 100, **kwargs: dict) -> list:
        return [
            self.parse_funding(funding_rate_dict)
            for funding_rate_dict in (await self.connector.client.fapiPublic_get_fundingrate(
                {self.BINANCE_SYMBOL: self.get_exchange_pair(symbol),
                 "limit": limit}))
        ]

    async def set_symbol_leverage(self, symbol: str, leverage: int, **kwargs: dict):
        await self.connector.client.fapiPrivate_post_leverage(
            {self.BINANCE_SYMBOL: self.get_exchange_pair(symbol),
             "leverage": leverage})

    async def set_symbol_margin_type(self, symbol: str, isolated: bool):
        await self.connector.client.fapiPrivate_post_marginType(
            {
                self.BINANCE_SYMBOL: self.get_exchange_pair(symbol),
                self.BINANCE_MARGIN_TYPE: self.BINANCE_MARGIN_TYPE_ISOLATED
                if isolated else self.BINANCE_MARGIN_TYPE_CROSSED
            })

    def parse_funding(self, funding_dict, from_ticker=False):
        try:
            last_funding_time = self.connector.get_uniform_timestamp(
                self.connector.client.safe_float(funding_dict, self.BINANCE_LAST_FUNDING_TIME))
            funding_dict = {
                trading_enums.ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value: last_funding_time,
                trading_enums.ExchangeConstantsFundingColumns.FUNDING_RATE.value:
                    self.connector.client.safe_float(funding_dict, self.BINANCE_FUNDING_RATE),
                trading_enums.ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value:
                    last_funding_time + self.BINANCE_FUNDING_DURATION
            }
        except KeyError as e:
            self.logger.error(f"Fail to parse funding dict ({e})")
        return funding_dict

    def parse_mark_price(self, mark_price_dict, from_ticker=False):
        try:
            mark_price_dict = {
                trading_enums.ExchangeConstantsMarkPriceColumns.MARK_PRICE.value:
                    self.connector.client.safe_float(mark_price_dict, self.BINANCE_MARK_PRICE, 0)
            }
        except KeyError as e:
            self.logger.error(f"Fail to parse mark_price dict ({e})")
        return mark_price_dict
