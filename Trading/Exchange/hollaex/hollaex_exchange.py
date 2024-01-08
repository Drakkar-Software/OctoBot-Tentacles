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
import ccxt

import octobot_commons.enums as commons_enums
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges
import octobot_trading.exchanges.connectors.ccxt.enums as ccxt_enums


class hollaex(exchanges.RestExchange):
    DESCRIPTION = ""

    FIX_MARKET_STATUS = True

    BASE_REST_API = "api.hollaex.com"
    REST_KEY = "rest"
    HAS_WEBSOCKETS_KEY = "has_websockets"
    REQUIRE_ORDER_FEES_FROM_TRADES = True  # set True when get_order is not giving fees on closed orders and fees

    DEFAULT_MAX_LIMIT = 500

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.exchange_manager.rest_only = self.exchange_manager.rest_only \
            or not self.tentacle_config.get(
                self.HAS_WEBSOCKETS_KEY, not self.exchange_manager.rest_only
            )

    def get_adapter_class(self):
        return HollaexCCXTAdapter

    @classmethod
    def init_user_inputs_from_class(cls, inputs: dict) -> None:
        """
        Called at constructor, should define all the exchange's user inputs.
        """
        cls.CLASS_UI.user_input(
            cls.REST_KEY, commons_enums.UserInputTypes.TEXT, f"https://{cls.BASE_REST_API}", inputs,
            title=f"Address of the Hollaex based exchange API (similar to https://{cls.BASE_REST_API})"
        )
        cls.CLASS_UI.user_input(
            cls.HAS_WEBSOCKETS_KEY, commons_enums.UserInputTypes.BOOLEAN, True, inputs,
            title=f"Use websockets feed. To enable only when websockets are supported by the exchange."
        )

    def get_additional_connector_config(self):
        return {
            ccxt_enums.ExchangeColumns.URLS.value: self._get_urls()
        }

    def _get_urls(self):
        urls = ccxt.hollaex().urls
        custom_urls = {
            ccxt_enums.ExchangeColumns.API.value: {
                self.REST_KEY: self.tentacle_config[self.REST_KEY]
            }
        }
        urls.update(custom_urls)
        return urls

    @classmethod
    def get_name(cls):
        return 'hollaex'

    @classmethod
    def is_configurable(cls):
        return True

    async def get_symbol_prices(self, symbol, time_frame, limit: int = None, **kwargs: dict):
        # ohlcv without limit is not supported, replaced by a default max limit
        if limit is None:
            limit = self.DEFAULT_MAX_LIMIT
        return await super().get_symbol_prices(symbol=symbol, time_frame=time_frame, limit=limit, **kwargs)

    async def get_closed_orders(self, symbol: str = None, since: int = None,
                                limit: int = None, **kwargs: dict) -> list:
        # get_closed_orders sometimes does not return orders use _get_closed_orders_from_my_recent_trades in this case
        return (
            await super().get_closed_orders(symbol=symbol, since=since, limit=limit, **kwargs) or
            await self._get_closed_orders_from_my_recent_trades(
                symbol=symbol, since=since, limit=limit, **kwargs
            )
        )


class HollaexCCXTAdapter(exchanges.CCXTAdapter):

    def fix_order(self, raw, symbol=None, **kwargs):
        raw_order_info = raw[ccxt_enums.ExchangePositionCCXTColumns.INFO.value]
        # average is not supported by ccxt
        fixed = super().fix_order(raw, **kwargs)
        if not fixed[trading_enums.ExchangeConstantsOrderColumns.PRICE.value] and "average" in raw_order_info:
            fixed[trading_enums.ExchangeConstantsOrderColumns.PRICE.value] = raw_order_info.get("average", 0)
        return fixed