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
import octobot_tentacles_manager.api as tentacles_manager_api


class hollaex(exchanges.SpotCCXTExchange):
    DESCRIPTION = ""

    DEFAULT_MAX_LIMIT = 500

    def get_additional_connector_config(self):
        urls = ccxt.hollaex().urls
        custom_urls = tentacles_manager_api.get_tentacle_config(self.exchange_manager.tentacles_setup_config,
                                                                self.__class__)
        urls.update(custom_urls)
        return {
            'urls': urls
        }

    @classmethod
    def get_name(cls):
        return 'hollaex'

    @classmethod
    def is_configurable(cls):
        return True

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def get_symbol_prices(self, symbol, time_frame, limit: int = None, **kwargs: dict):
        # ohlcv without limit is not supported, replaced by a default max limit
        if limit is None:
            limit = self.DEFAULT_MAX_LIMIT
        return await super().get_symbol_prices(symbol=symbol, time_frame=time_frame, limit=limit, **kwargs)

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
