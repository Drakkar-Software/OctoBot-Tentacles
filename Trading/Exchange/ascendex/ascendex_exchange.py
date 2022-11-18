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
import octobot_trading.exchanges.config.ccxt_exchange_settings as ccxt_exchange_settings


class AscendExConnectorSettings(ccxt_exchange_settings.CCXTExchangeConfig):
    USE_FIXED_MARKET_STATUS = True
    CANDLE_LOADING_LIMIT = 500
    GET_MY_RECENT_TRADES_METHODS = [
        trading_enums.CCXTExchangeConfigMethods.GET_MY_RECENT_TRADES_USING_CLOSED_ORDERS.value,
    ]


class AscendEx(exchanges.SpotCCXTExchange):
    CONNECTOR_SETTINGS = AscendExConnectorSettings

    DESCRIPTION = ""

    BUY_STR = "Buy"
    SELL_STR = "Sell"

    ACCOUNTS = {
        trading_enums.AccountTypes.CASH: "cash",
        trading_enums.AccountTypes.MARGIN: "margin",
        trading_enums.AccountTypes.FUTURE: "futures",  # currently in beta
    }

    @classmethod
    def get_name(cls):
        return "ascendex"

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def switch_to_account(self, account_type):
        # TODO
        pass
