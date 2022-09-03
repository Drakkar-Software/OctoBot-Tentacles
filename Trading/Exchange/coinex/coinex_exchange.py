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
import ccxt.async_support as ccxt
import copy
import math

import ccxt

import octobot_trading.errors
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges

import octobot_commons.logging as logging

import octobot_trading.api as trading_api

import octobot_services.interfaces as interfaces

class Coinex(exchanges.SpotCCXTExchange):
    DESCRIPTION = ""
    MAX_PAGINATION_LIMIT: int = 100

    @classmethod
    def get_name(cls):
        return 'coinex'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name


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

    def _fix_limit(self, limit: int) -> int:
        return min(self.MAX_PAGINATION_LIMIT, limit)

    def get_trades_history(bot_api=None, symbol=None, independent_backtesting=None, since=None, as_dict=False):
        simulated_trades_history = []
        real_trades_history = []

        for exchange_manager in interfaces.get_exchange_managers(bot_api=bot_api,
                                                             independent_backtesting=independent_backtesting):
           if trading_api.is_trader_existing_and_enabled(exchange_manager):
               if trading_api.is_trader_simulated(exchange_manager):
                simulated_trades_history += trading_api.get_trade_history(exchange_manager, symbol, since, as_dict)
               else:
                real_trades_history += trading_api.get_trade_history(exchange_manager, symbol, since, as_dict)
        return real_trades_history, simulated_trades_history