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
import octobot_commons.enums as commons_enums
import octobot_commons.constants as commons_constants
import octobot_trading.exchanges as exchanges
from octobot_trading.enums import WebsocketFeeds as Feeds
import tentacles.Trading.Exchange.bybit.bybit_exchange as bybit_exchange


class BybitCCXTWebsocketConnector(exchanges.CCXTWebsocketConnector):
    EXCHANGE_FEEDS = {
        Feeds.TRADES: True,
        Feeds.KLINE: True,
        Feeds.TICKER: True,
        Feeds.CANDLE: True,
    }

    @classmethod
    def get_name(cls):
        return bybit_exchange.Bybit.get_name()

    def get_adapter_class(self, adapter_class):
        return BybitCCXTWebsocketAdapter


class BybitCCXTWebsocketAdapter(bybit_exchange.BybitCCXTAdapter):

    def fix_ohlcv(self, raw, **kwargs):
        try:
            # candle open time is in the "start" value of info unlike what parsed by ccxt_pro
            # time_frame kwarg has to be passed to parse bybit candle time
            candles_ms = commons_enums.TimeFramesMinutes[commons_enums.TimeFrames(kwargs["time_frame"])] * \
                commons_constants.MSECONDS_TO_MINUTE
            for ohlcv in raw:
                ohlcv[commons_enums.PriceIndexes.IND_PRICE_TIME.value] -= \
                    ohlcv[commons_enums.PriceIndexes.IND_PRICE_TIME.value] % candles_ms
        except KeyError as e:
            self.logger.error(f"Fail to fix ohlcv ({e})")
        return super().fix_ohlcv(raw, **kwargs)
