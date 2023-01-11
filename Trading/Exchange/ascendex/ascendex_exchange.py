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
import typing
import decimal

import octobot_commons.enums
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges


class AscendEx(exchanges.RestExchange):
    DESCRIPTION = ""

    BUY_STR = "Buy"
    SELL_STR = "Sell"

    ACCOUNTS = {
        trading_enums.AccountTypes.CASH: 'cash',
        trading_enums.AccountTypes.MARGIN: 'margin',
        trading_enums.AccountTypes.FUTURE: 'futures',  # currently in beta
    }

    @classmethod
    def get_name(cls):
        return 'ascendex'

    def get_adapter_class(self):
        return AscendexCCXTAdapter

    async def switch_to_account(self, account_type):
        # TODO
        pass

    def parse_account(self, account):
        return trading_enums.AccountTypes[account.lower()]

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer)

    async def get_my_recent_trades(self, symbol=None, since=None, limit=None, **kwargs):
        # On AscendEx, account recent trades is available under fetch_closed_orders
        return await super().get_closed_orders(symbol=symbol, since=since, limit=limit, **kwargs)

    async def get_symbol_prices(self,
                                symbol: str,
                                time_frame: octobot_commons.enums.TimeFrames,
                                limit: int = None,
                                **kwargs: dict) -> typing.Optional[list]:
        if limit is None:
            # force default limit on AscendEx since it's not used by default in fetch_ohlcv
            options = self.connector.client.safe_value(self.connector.client.options, 'fetchOHLCV', {})
            limit = self.connector.client.safe_integer(options, 'limit', 500)
        return await super().get_symbol_prices(symbol, time_frame, limit, **kwargs)


class AscendexCCXTAdapter(exchanges.CCXTAdapter):

    def fix_ticker(self, raw, **kwargs):
        fixed = super().fix_ticker(raw, **kwargs)
        fixed[trading_enums.ExchangeConstantsTickersColumns.TIMESTAMP.value] = self.connector.client.milliseconds()
        return fixed
