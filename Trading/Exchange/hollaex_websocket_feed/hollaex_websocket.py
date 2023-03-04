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
import ccxt.pro as ccxt_pro
import octobot_trading.exchanges as exchanges
from octobot_trading.enums import WebsocketFeeds as Feeds
import tentacles.Trading.Exchange.hollaex as hollaex_tentacle


class HollaexCCXTWebsocketConnector(exchanges.CCXTWebsocketConnector):
    BASE_WS_API = f"{hollaex_tentacle.BASE_REST_API}/stream"
    EXCHANGE_FEEDS = {
        Feeds.TRADES: True,
        Feeds.KLINE: Feeds.UNSUPPORTED.value,
        Feeds.TICKER: Feeds.UNSUPPORTED.value,
        Feeds.CANDLE: Feeds.UNSUPPORTED.value,
    }

    def _create_client(self):
        if not self.additional_config:
            rest_config = self.exchange_manager.exchange.get_additional_connector_config()
            try:
                rest_url = rest_config["urls"]["api"]["rest"]
                if hollaex_tentacle.BASE_REST_API not in rest_url:
                    current_ws_url = ccxt_pro.hollaex().describe()["urls"]["api"]["ws"]
                    custom_url = rest_url.split("https://")[1]
                    rest_config["urls"]["api"]["ws"] = current_ws_url.replace(hollaex_tentacle.BASE_REST_API, custom_url)
                # use rest exchange additional config if any
                self.additional_config = self.exchange_manager.exchange.get_additional_connector_config()
            except KeyError as err:
                self.logger.error(f"Error when updating exchange url: {err}")
        super()._create_client()

    @classmethod
    def get_name(cls):
        return hollaex_tentacle.get_name()
