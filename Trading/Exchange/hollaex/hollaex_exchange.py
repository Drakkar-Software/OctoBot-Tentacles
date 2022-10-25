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
import octobot_trading.exchanges as exchanges


class hollaex(exchanges.SpotCCXTExchange):
    DESCRIPTION = ""

    DEFAULT_MAX_LIMIT = 500

    @classmethod
    def init_user_inputs(cls, inputs: dict) -> None:
        """
        Called at constructor, should define all the exchange's user inputs.
        """
        cls.UI.user_input(
            "rest", commons_enums.UserInputTypes.TEXT, "https://api.hollaex.com", inputs,
            title="Address of the Hollaex based exchange API (similar to https://api.hollaex.com)"
        )

    def get_additional_connector_config(self):
        urls = ccxt.hollaex().urls
        custom_urls = {
            "api": self.tentacle_config
        }
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
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer)
