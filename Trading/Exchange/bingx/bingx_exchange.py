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
import octobot_trading.exchanges.connectors.ccxt.constants as ccxt_constants
import octobot_trading.enums as trading_enums


class Bingx(exchanges.RestExchange):
    FIX_MARKET_STATUS = True

    def get_adapter_class(self):
        return BingxCCXTAdapter

    @classmethod
    def get_name(cls) -> str:
        return 'bingx'

    async def get_account_id(self, **kwargs: dict) -> str:
        resp = await self.connector.client.accountV1PrivateGetUid()
        return resp["data"]["uid"]

    async def get_my_recent_trades(self, symbol=None, since=None, limit=None, **kwargs):
        # On SPOT Bingx, account recent trades is available under fetch_closed_orders
        if self.exchange_manager.is_future:
            return await super().get_my_recent_trades(symbol=symbol, since=since, limit=limit, **kwargs)
        return await super().get_closed_orders(symbol=symbol, since=since, limit=limit, **kwargs)


class BingxCCXTAdapter(exchanges.CCXTAdapter):

    def fix_order(self, raw, **kwargs):
        fixed = super().fix_order(raw, **kwargs)
        try:
            info = fixed[ccxt_constants.CCXT_INFO]
            fixed[trading_enums.ExchangeConstantsOrderColumns.EXCHANGE_ID.value] = info["orderId"]
        except KeyError:
            pass
        return fixed

    def fix_market_status(self, raw, remove_price_limits=False, **kwargs):
        # on bingx, amounts are precisions in the right unit, do not patch precision
        market_status = raw
        if remove_price_limits:
            market_status[trading_enums.ExchangeConstantsMarketStatusColumns.LIMITS.value][
                trading_enums.ExchangeConstantsMarketStatusColumns.LIMITS_PRICE.value][
                trading_enums.ExchangeConstantsMarketStatusColumns.LIMITS_PRICE_MIN.value] = None
            market_status[trading_enums.ExchangeConstantsMarketStatusColumns.LIMITS.value][
                trading_enums.ExchangeConstantsMarketStatusColumns.LIMITS_PRICE.value][
                trading_enums.ExchangeConstantsMarketStatusColumns.LIMITS_PRICE_MAX.value] = None

        return market_status
