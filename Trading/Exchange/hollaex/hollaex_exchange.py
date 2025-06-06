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
import typing
import decimal

import octobot_commons.enums as commons_enums
import octobot_commons.constants as commons_constants
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges
import octobot_trading.exchanges.connectors.ccxt.enums as ccxt_enums



class hollaexConnector(exchanges.CCXTConnector):

    def _create_client(self, force_unauth=False):
        super()._create_client(force_unauth=force_unauth)
        self._register_patched_sign()

    def _register_patched_sign(self):
        # hollaex sign() creates invalid signatures when floats are represented in scientific notation
        # use strings instead
        # Note: stop param should not be converted to string as it will then be ignored: leave it as float
        origin_sign = self.client.sign

        def _patched_sign(path, api='public', method='GET', params={}, headers=None, body=None):
            if self.client.omit(params, self.client.extract_params(path)):
                # only fix params when there is a query to generate a signature for
                # => meaning when self.client.omit leaves something to put in request body
                fixed_params = {
                    k: format(decimal.Decimal(str(v)), "f") if (isinstance(v, float) and k != "stop") else v
                    for k, v in params.items()
                }
            else:
                fixed_params = params
            return origin_sign(path, api=api, method=method, params=fixed_params, headers=headers, body=body)

        self.client.sign = _patched_sign


class hollaex(exchanges.RestExchange):
    DESCRIPTION = ""
    DEFAULT_CONNECTOR_CLASS = hollaexConnector

    FIX_MARKET_STATUS = True

    BASE_REST_API = "api.hollaex.com"
    REST_KEY = "rest"
    HAS_WEBSOCKETS_KEY = "has_websockets"
    REQUIRE_ORDER_FEES_FROM_TRADES = True  # set True when get_order is not giving fees on closed orders and fees
    SUPPORT_FETCHING_CANCELLED_ORDERS = False

    # STOP_PRICE is used in ccxt/hollaex instead of default STOP_LOSS_PRICE
    STOP_LOSS_CREATE_PRICE_PARAM = ccxt_enums.ExchangeOrderCCXTUnifiedParams.STOP_PRICE.value
    STOP_LOSS_EDIT_PRICE_PARAM = STOP_LOSS_CREATE_PRICE_PARAM

    # should be overridden locally to match exchange support
    SUPPORTED_ELEMENTS = {
        trading_enums.ExchangeTypes.FUTURE.value: {
            # order that should be self-managed by OctoBot
            trading_enums.ExchangeSupportedElements.UNSUPPORTED_ORDERS.value: [
                trading_enums.TraderOrderType.STOP_LOSS,
                trading_enums.TraderOrderType.STOP_LOSS_LIMIT,
                trading_enums.TraderOrderType.TAKE_PROFIT,
                trading_enums.TraderOrderType.TAKE_PROFIT_LIMIT,
                trading_enums.TraderOrderType.TRAILING_STOP,
                trading_enums.TraderOrderType.TRAILING_STOP_LIMIT
            ],
            # order that can be bundled together to create them all in one request
            # not supported or need custom mechanics with batch orders
            trading_enums.ExchangeSupportedElements.SUPPORTED_BUNDLED_ORDERS.value: {},
        },
        trading_enums.ExchangeTypes.SPOT.value: {
            # order that should be self-managed by OctoBot
            trading_enums.ExchangeSupportedElements.UNSUPPORTED_ORDERS.value: [
                # trading_enums.TraderOrderType.STOP_LOSS,
                trading_enums.TraderOrderType.STOP_LOSS_LIMIT,
                trading_enums.TraderOrderType.TAKE_PROFIT,
                trading_enums.TraderOrderType.TAKE_PROFIT_LIMIT,
                trading_enums.TraderOrderType.TRAILING_STOP,
                trading_enums.TraderOrderType.TRAILING_STOP_LIMIT
            ],
            # order that can be bundled together to create them all in one request
            trading_enums.ExchangeSupportedElements.SUPPORTED_BUNDLED_ORDERS.value: {},
        }
    }

    DEFAULT_MAX_LIMIT = 500
    EXCHANGE_PERMISSION_ERRORS: typing.List[typing.Iterable[str]] = [
        # '"message":"Access denied: Unauthorized Access. This key does not have the right permissions to access this endpoint"'
        ("permissions to access",),
    ]

    def __init__(
        self, config, exchange_manager, exchange_config_by_exchange: typing.Optional[dict[str, dict]],
        connector_class=None
    ):
        super().__init__(config, exchange_manager, exchange_config_by_exchange, connector_class=connector_class)
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
            ccxt_enums.ExchangeColumns.URLS.value: self.get_patched_urls(self.tentacle_config[self.REST_KEY])
        }

    @classmethod
    def get_custom_url_config(cls, tentacle_config: dict, exchange_name: str) -> dict:
        if details := cls.get_exchange_details(tentacle_config, exchange_name):
            return {
                ccxt_enums.ExchangeColumns.URLS.value: cls.get_patched_urls(details.api)
            }
        return {}

    @classmethod
    def get_exchange_details(cls, tentacle_config, exchange_name) -> typing.Optional[exchanges.ExchangeDetails]:
        return None

    @classmethod
    def get_patched_urls(cls, api_url: str):
        urls = ccxt.hollaex().urls
        custom_urls = {
            ccxt_enums.ExchangeColumns.API.value: {
                cls.REST_KEY: api_url
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

    def is_authenticated_request(self, url: str, method: str, headers: dict, body) -> bool:
        signature_identifier = "api-signature"
        return bool(
            headers
            and signature_identifier in headers
        )

    def get_max_orders_count(self, symbol: str, order_type: trading_enums.TraderOrderType) -> int:
        #  (05/06/2025)
        # hollaex {"message":"Error 1010 - You are only allowed to have maximum 25 active orders per market."}
        return 25

    async def get_account_id(self, **kwargs: dict) -> str:
        with self.connector.error_describer():
            user_info = await self.connector.client.private_get_user()
            return user_info["id"]

    async def get_symbol_prices(self, symbol, time_frame, limit: int = None, **kwargs: dict):
        # ohlcv without limit is not supported, replaced by a default max limit
        if limit is None:
            limit = self.DEFAULT_MAX_LIMIT
        if "since" not in kwargs:
            # temporary fix to prevent hollaex from fetching outdates candles
            # remove once hollaex ccxt fetch_ohlcv stop hard coding defaultSpan = 2592000  # 30 days
            tf_seconds = commons_enums.TimeFramesMinutes[time_frame] * commons_constants.MINUTE_TO_SECONDS
            kwargs["since"] = (self.get_exchange_current_time() - tf_seconds * limit) \
                * commons_constants.MSECONDS_TO_SECONDS
        return await super().get_symbol_prices(symbol, time_frame, limit=limit, **kwargs)

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
        fixed = super().fix_order(raw, symbol=symbol, **kwargs)
        if not fixed[trading_enums.ExchangeConstantsOrderColumns.PRICE.value] and "average" in raw_order_info:
            fixed[trading_enums.ExchangeConstantsOrderColumns.PRICE.value] = raw_order_info.get("average", 0)

        if fixed[ccxt_enums.ExchangeOrderCCXTColumns.TRIGGER_PRICE.value]:
            order_type = trading_enums.TradeOrderType.STOP_LOSS.value
            # todo uncomment when stop loss limit are supported
            # if fixed[ccxt_enums.ExchangeOrderCCXTColumns.PRICE.value] is None:
            #     order_type = trading_enums.TradeOrderType.STOP_LOSS.value
            fixed[trading_enums.ExchangeConstantsOrderColumns.TYPE.value] = order_type

        return fixed

    def fix_ticker(self, raw, **kwargs):
        fixed = super().fix_ticker(raw, **kwargs)
        fixed[trading_enums.ExchangeConstantsTickersColumns.TIMESTAMP.value] = \
            fixed.get(trading_enums.ExchangeConstantsTickersColumns.TIMESTAMP.value) or self.connector.client.seconds()
        return fixed
