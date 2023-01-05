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
import octobot_trading.enums as trading_enums


class WavesExchange(exchanges.RestExchange):
    DESCRIPTION = ""

    @classmethod
    def get_name(cls):
        return 'wavesexchange'

    def get_adapter_class(self):
        return WavesCCXTAdapter


class WavesCCXTAdapter(exchanges.CCXTAdapter):

    def fix_ticker(self, raw, **kwargs):
        fixed = super().fix_ticker(raw)
        fixed[trading_enums.ExchangeConstantsTickersColumns.TIMESTAMP.value] = self.connector.client.milliseconds()
        return fixed
