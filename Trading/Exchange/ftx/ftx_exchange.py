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
import copy
import math

import ccxt

import octobot_trading.exchanges as exchanges
import octobot_trading.errors
import octobot_trading.enums as trading_enums


class FTX(exchanges.SpotCCXTExchange):
    DESCRIPTION = ""
    FTX_SUB_ACCOUNT_HEADER_KEY = "FTX-SUBACCOUNT"

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        sub_account_id = exchange_manager.get_exchange_sub_account_id(exchange_manager.exchange_name)
        if sub_account_id is not None:
            self.connector.add_headers({
                self.FTX_SUB_ACCOUNT_HEADER_KEY: sub_account_id
            })

    @classmethod
    def get_name(cls):
        return 'ftx'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        try:
            market_status = self._fix_market_status(copy.deepcopy(self.connector.client.market(symbol)))
            if with_fixer:
                market_status = exchanges.ExchangeMarketStatusFixer(market_status, price_example).market_status
            return market_status
        except ccxt.NotSupported:
            raise octobot_trading.errors.NotSupported
        except Exception as e:
            self.logger.error(f"Fail to get market status of {symbol}: {e}")
        return {}

    def _fix_market_status(self, market_status):
        market_status[trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION.value][
            trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION_AMOUNT.value] = self._get_digits_count(
            market_status[trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION.value][
                trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION_AMOUNT.value])
        market_status[trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION.value][
            trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION_PRICE.value] = self._get_digits_count(
            market_status[trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION.value][
                trading_enums.ExchangeConstantsMarketStatusColumns.PRECISION_PRICE.value])
        return market_status

    def _get_digits_count(self, value):
        return round(abs(math.log(value, 10)))

    async def get_price_ticker(self, symbol: str, **kwargs: dict):
        try:
            ticker = await self.connector.client.fetch_ticker(symbol, params=kwargs)
            ticker[trading_enums.ExchangeConstantsTickersColumns.TIMESTAMP.value] = self.connector.client.milliseconds()
            ticker[trading_enums.ExchangeConstantsTickersColumns.BASE_VOLUME.value] = ticker[trading_enums.ExchangeConstantsTickersColumns.QUOTE_VOLUME.value] / ticker[trading_enums.ExchangeConstantsTickersColumns.CLOSE.value]
            return ticker
        except ccxt.BaseError as e:
            raise octobot_trading.errors.FailedRequest(f"Failed to get_price_ticker {e}")

    async def get_sub_account_list(self):
        sub_account_list = (await self.connector.client.privateGetSubaccounts()).get("result", [])
        if not sub_account_list:
            return []
        return [
            {
                trading_enums.SubAccountColumns.ID.value: sub_account.get("nickname", ""),
                trading_enums.SubAccountColumns.NAME.value: sub_account.get("nickname", "")
            }
            for sub_account in sub_account_list
        ]
