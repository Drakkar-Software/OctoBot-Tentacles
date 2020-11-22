#  Drakkar-Software OctoBot
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
import os
import contextlib

import octobot_backtesting.data as backtesting_data
import octobot_backtesting.enums as enums
import octobot_backtesting.errors as errors
import tests.test_utils.config as test_utils_config
import tentacles.Backtesting.collectors.exchanges as collector_exchanges
import tentacles.Trading.Exchange as tentacles_exchanges

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


@contextlib.asynccontextmanager
async def data_collector(exchange_name, tentacles_setup_config, symbols, time_frames, use_all_available_timeframes):
    collector_instance = collector_exchanges.ExchangeHistoryDataCollector(
        {}, exchange_name, tentacles_setup_config, symbols, time_frames,
        use_all_available_timeframes=use_all_available_timeframes
    )
    try:
        await collector_instance.initialize()
        yield collector_instance
    finally:
        if collector_instance.file_path and os.path.isfile(collector_instance.file_path):
            os.remove(collector_instance.file_path)


@contextlib.asynccontextmanager
async def collector_database(collector):
    database = backtesting_data.DataBase(collector.file_path)
    try:
        await database.initialize()
        yield database
    finally:
        await database.stop()


async def test_collect_valid_data():
    exchange_name = "binance"
    tentacles_setup_config = test_utils_config.load_test_tentacles_config()
    symbols = ["ETH/BTC"]
    async with data_collector(exchange_name, tentacles_setup_config, symbols, None, True) as collector:
        assert collector.time_frames == []
        assert collector.symbols == symbols
        assert collector.exchange_name == exchange_name
        assert collector.tentacles_setup_config == tentacles_setup_config
        await collector.start()
        assert collector.time_frames != []
        assert collector.exchange_manager is None
        assert isinstance(collector.exchange, tentacles_exchanges.Binance)
        assert collector.file_path is not None
        async with collector_database(collector) as database:
            ohlcv = await database.select(enums.ExchangeDataTables.OHLCV)
            assert len(ohlcv) > 6000
            h_ohlcv = await database.select(enums.ExchangeDataTables.OHLCV, time_frame="1h")
            assert len(h_ohlcv) == 500
            eth_btc_ohlcv = await database.select(enums.ExchangeDataTables.OHLCV, symbol="ETH/BTC")
            assert len(eth_btc_ohlcv) == len(ohlcv)


async def test_collect_invalid_data():
    exchange_name = "binance"
    tentacles_setup_config = test_utils_config.load_test_tentacles_config()
    symbols = ["___ETH/BTC"]
    async with data_collector(exchange_name, tentacles_setup_config, symbols, None, True) as collector:
        with pytest.raises(errors.DataCollectorError):
            await collector.start()
        assert collector.time_frames != []
        assert collector.exchange_manager is None
        assert collector.exchange is not None
        assert collector.file_path is not None
        assert not os.path.isfile(collector.file_path)
