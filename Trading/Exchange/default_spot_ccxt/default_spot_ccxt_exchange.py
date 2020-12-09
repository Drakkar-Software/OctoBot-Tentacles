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


class DefaultCCXTSpotExchange(exchanges.SpotCCXTExchange):
    @classmethod
    def get_name(cls) -> str:
        return cls.__name__

    @classmethod
    def is_default_exchange(cls) -> bool:
        return True

    async def switch_to_account(self, account_type: trading_enums.AccountTypes):
        # Currently not supported
        pass
