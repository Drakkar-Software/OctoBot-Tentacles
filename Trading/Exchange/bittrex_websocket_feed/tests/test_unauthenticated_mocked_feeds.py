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

import pytest

import octobot_commons.channels_name as channels_name
import octobot_commons.enums as commons_enums
import octobot_commons.tests as commons_tests
import octobot_trading.exchanges as exchanges
import octobot_trading.util.test_tools.exchanges_test_tools as exchanges_test_tools
import octobot_trading.util.test_tools.websocket_test_tools as websocket_test_tools
from ...bittrex_websocket_feed import BittrexCryptofeedWebsocketConnector

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def test_start_spot_websocket():
    config = commons_tests.load_test_config()
    exchange_manager_instance = await exchanges_test_tools.create_test_exchange_manager(
        config=config, exchange_name=BittrexCryptofeedWebsocketConnector.get_name())

    await websocket_test_tools.test_unauthenticated_push_to_channel_coverage_websocket(
        websocket_exchange_class=exchanges.CryptofeedWebSocketExchange,
        websocket_connector_class=BittrexCryptofeedWebsocketConnector,
        exchange_manager=exchange_manager_instance,
        config=config,
        symbols=["BTC/USDT", "ETH/USDT"],
        time_frames=[commons_enums.TimeFrames.ONE_MINUTE, commons_enums.TimeFrames.ONE_HOUR],
        expected_pushed_channels={
            channels_name.OctoBotTradingChannelsName.RECENT_TRADES_CHANNEL.value,
            channels_name.OctoBotTradingChannelsName.TICKER_CHANNEL.value,
            channels_name.OctoBotTradingChannelsName.KLINE_CHANNEL.value,
            channels_name.OctoBotTradingChannelsName.OHLCV_CHANNEL.value,
        },
        time_before_assert=20
    )
    await exchanges_test_tools.stop_test_exchange_manager(exchange_manager_instance)
