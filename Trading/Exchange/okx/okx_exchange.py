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

import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges


class Okx(exchanges.SpotCCXTExchange):
    MAX_PAGINATION_LIMIT: int = 100  # value from https://www.okex.com/docs/en/#spot-orders_pending
    DESCRIPTION = ""

    # FROM https://www.okex.com/docs-v5/en/#overview-demo-trading-services
    SANDBOX_MODE_HEADERS = {"x-simulated-trading": "1"}

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)

        if self.exchange_manager.is_sandboxed:
            self.connector.add_headers(self.SANDBOX_MODE_HEADERS)

    @classmethod
    def get_name(cls):
        return 'okx'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    @classmethod
    def is_supporting_sandbox(cls) -> bool:
        return False

    async def get_open_orders(self, symbol=None, since=None, limit=None, **kwargs) -> list:
        return await super().get_open_orders(symbol=symbol,
                                             since=since,
                                             limit=self._fix_limit(limit),
                                             **kwargs)

    async def get_closed_orders(self, symbol=None, since=None, limit=None, **kwargs) -> list:
        return await super().get_closed_orders(symbol=symbol,
                                               since=since,
                                               limit=self._fix_limit(limit),
                                               **kwargs)

    async def _create_market_buy_order(self, symbol, quantity, price=None, params=None) -> dict:
        """
        Add price to default connector call for market orders https://github.com/ccxt/ccxt/issues/9523
        """
        return await self.connector.client.create_market_order(symbol=symbol, side='buy', amount=quantity,
                                                               price=price, params=params)

    async def _create_market_sell_order(self, symbol, quantity, price=None, params=None) -> dict:
        """
        Add price to default connector call for market orders https://github.com/ccxt/ccxt/issues/9523
        """
        return await self.connector.client.create_market_order(symbol=symbol, side='sell', amount=quantity,
                                                               price=price, params=params)

    def _fix_limit(self, limit: int) -> int:
        return min(self.MAX_PAGINATION_LIMIT, limit) if limit else limit

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer)

    async def get_sub_account_list(self):
        sub_account_list = (await self.connector.client.privateGetUsersSubaccountList()).get("data", [])
        if not sub_account_list:
            return []
        return [
            {
                trading_enums.SubAccountColumns.ID.value: sub_account.get("subAcct", ""),
                trading_enums.SubAccountColumns.NAME.value: sub_account.get("label", "")
            }
            for sub_account in sub_account_list
            if sub_account.get("enable", False)
        ]
