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

import octobot_trading.exchanges as exchanges
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
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer)

    async def get_price_ticker(self, symbol: str, **kwargs: dict):
        ticker = await super().get_price_ticker(symbol=symbol, **kwargs)
        ticker[trading_enums.ExchangeConstantsTickersColumns.TIMESTAMP.value] = self.connector.client.milliseconds()
        ticker[trading_enums.ExchangeConstantsTickersColumns.BASE_VOLUME.value] = \
            ticker[trading_enums.ExchangeConstantsTickersColumns.QUOTE_VOLUME.value] / \
            ticker[trading_enums.ExchangeConstantsTickersColumns.CLOSE.value]
        return ticker

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
