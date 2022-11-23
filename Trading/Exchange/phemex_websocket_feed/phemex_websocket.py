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
import cryptofeed.defines as cryptofeed_constants
from octobot_trading.enums import WebsocketFeeds as Feeds


class PhemexCryptofeedWebsocketConnector(exchanges.CryptofeedWebsocketConnector):
    REQUIRED_ACTIVATED_TENTACLES = []
    EXCHANGE_FEEDS = {
        Feeds.TRADES: cryptofeed_constants.TRADES,
        Feeds.KLINE: cryptofeed_constants.CANDLES,
        Feeds.CANDLE: cryptofeed_constants.CANDLES,
    }

    # todo remove this on cryptofeed 2.3.2
    # monkey patch cryptofeed phemex _parse_symbol_data not to crash
    def __init__(self, config: object, exchange_manager: object):
        import cryptofeed.exchanges as cryptofeed_exchanges
        from cryptofeed.symbols import Symbol
        from collections import defaultdict

        def patched_parse_symbol_data(data: dict):
            ret = {}
            info = defaultdict(dict)

            for entry in data['data']['products']:
                if entry['status'] != 'Listed':
                    continue
                stype = entry['type'].lower()
                if "perpetual" in stype:    # can be "perpetualv2"
                    stype = cryptofeed_constants.PERPETUAL
                base, quote = entry['displaySymbol'].split("/")
                s = Symbol(base.strip(), quote.strip(), type=stype)
                ret[s.normalized] = entry['symbol']
                info['tick_size'][s.normalized] = entry['tickSize'] if 'tickSize' in entry else entry['quoteTickSize']
                info['instrument_type'][s.normalized] = stype
                # the price scale for spot symbols is not reported via the API but it is documented
                # here in the API docs: https://github.com/phemex/phemex-api-docs/blob/master/Public-Spot-API-en.md#spot-currency-and-symbols
                # the default value for spot is 10^8
                cryptofeed_exchanges.EXCHANGE_MAP[self.get_feed_name()].price_scale[s.normalized] = \
                    10 ** entry.get('priceScale', 8)
            return ret, info
        cryptofeed_exchanges.EXCHANGE_MAP[self.get_feed_name()]._parse_symbol_data = patched_parse_symbol_data
        super().__init__(config, exchange_manager)

    @classmethod
    def get_name(cls):
        return 'phemex'

    @classmethod
    def get_feed_name(cls):
        return cryptofeed_constants.PHEMEX

    @classmethod
    def is_handling_spot(cls) -> bool:
        return True
