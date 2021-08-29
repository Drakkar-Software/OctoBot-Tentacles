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


class FTXUS(exchanges.SpotCCXTExchange):
    DESCRIPTION = ""
    FTX_SUB_ACCOUNT_HEADER_KEY = "FTXUS-SUBACCOUNT"

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        sub_account_id = exchange_manager.get_exchange_sub_account_id(exchange_manager.exchange_name)
        if sub_account_id is not None:
            self.connector.add_headers({
                self.FTX_SUB_ACCOUNT_HEADER_KEY: sub_account_id
            })

    @classmethod
    def get_name(cls):
        return 'ftx'
