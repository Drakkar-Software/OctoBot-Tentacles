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
import octobot_trading.exchanges as exchanges
import octobot_trading.exchanges.connectors.ccxt.constants as ccxt_constants
import octobot_trading.enums as trading_enums
import octobot_trading.constants as trading_constants


class BitMartConnector(exchanges.CCXTConnector):

    def _client_factory(
        self,
        force_unauth,
        keys_adapter: typing.Callable[[exchanges.ExchangeCredentialsData], exchanges.ExchangeCredentialsData]=None
    ) -> tuple:
        return super()._client_factory(force_unauth, keys_adapter=self._keys_adapter)

    def _keys_adapter(self, creds: exchanges.ExchangeCredentialsData) -> exchanges.ExchangeCredentialsData:
        # use password as uid
        creds.uid = creds.password
        creds.password = None
        return creds


class BitMart(exchanges.RestExchange):
    FIX_MARKET_STATUS = True
    DEFAULT_CONNECTOR_CLASS = BitMartConnector
    REQUIRE_ORDER_FEES_FROM_TRADES = True  # set True when get_order is not giving fees on closed orders and fees
    # set True when create_market_buy_order_with_cost should be used to create buy market orders
    # (useful to predict the exact spent amount)
    ENABLE_SPOT_BUY_MARKET_WITH_COST = True
    # broken: need v4 endpoint required, 10/10/25 ccxt still doesn't have it
    # bitmart {"msg":"This endpoint has been deprecated. Please refer to the document:
    # https://developer-pro.bitmart.com/en/spot/#update-plan","code":30031}
    SUPPORT_FETCHING_CANCELLED_ORDERS = False

    @classmethod
    def get_name(cls):
        return 'bitmart'

    def get_adapter_class(self):
        return BitMartCCXTAdapter

    def get_additional_connector_config(self):
        # tell ccxt to use amount as provided and not to compute it by multiplying it by price which is done here
        # (price should not be sent to market orders). Only used for buy market orders
        return {
            ccxt_constants.CCXT_OPTIONS: {
                "createMarketBuyOrderRequiresPrice": False  # disable quote conversion
            }
        }

    async def get_account_id(self, **kwargs: dict) -> str:
        # not available on bitmart
        return trading_constants.DEFAULT_ACCOUNT_ID


class BitMartCCXTAdapter(exchanges.CCXTAdapter):
    def fix_order(self, raw, **kwargs):
        fixed = super().fix_order(raw, **kwargs)
        self.adapt_amount_from_filled_or_cost(fixed)
        if (
            fixed[trading_enums.ExchangeConstantsOrderColumns.TYPE.value] == trading_enums.TradeOrderType.MARKET.value
            and fixed[trading_enums.ExchangeConstantsOrderColumns.STATUS.value]
                == trading_enums.OrderStatus.CANCELED.value
            and fixed[trading_enums.ExchangeConstantsOrderColumns.FILLED.value]
        ):
            # consider as filled & closed (Bitmart is sometimes tagging filled market orders as "canceled": ignore it)
            fixed[trading_enums.ExchangeConstantsOrderColumns.STATUS.value] = trading_enums.OrderStatus.CLOSED.value
        return fixed
