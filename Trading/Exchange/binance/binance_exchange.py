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
import decimal

import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges


class Binance(exchanges.RestExchange):
    DESCRIPTION = ""
    REQUIRE_ORDER_FEES_FROM_TRADES = True  # set True when get_order is not giving fees on closed orders and fees
    # should be fetched using recent trades.

    BUY_STR = "BUY"
    SELL_STR = "SELL"

    ACCOUNTS = {    # useless ?
        trading_enums.AccountTypes.CASH: 'cash'
    }

    @classmethod
    def get_name(cls):
        return 'binance'

    def get_adapter_class(self):
        return BinanceCCXTAdapter

    async def get_balance(self, **kwargs):
        return await exchanges.RestExchange.get_balance(self, **self._get_params(kwargs))

    def _get_params(self, params):
        if params is None:
            params = {}
        params.update({'recvWindow': 60000})
        return params


class BinanceCCXTAdapter(exchanges.CCXTAdapter):

    def fix_trades(self, raw, **kwargs):
        raw = super().fix_trades(raw, **kwargs)
        for trade in raw:
            trade[trading_enums.ExchangeConstantsOrderColumns.STATUS.value] = trading_enums.OrderStatus.CLOSED.value
            trade[trading_enums.ExchangeConstantsOrderColumns.ID.value] = trade[
                trading_enums.ExchangeConstantsOrderColumns.ORDER.value]
        return raw
