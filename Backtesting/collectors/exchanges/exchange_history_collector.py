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
import logging

from octobot_backtesting.collectors.exchanges.exchange_collector import ExchangeDataCollector
from tentacles.Backtesting.importers.exchanges.generic_exchange_importer import GenericExchangeDataImporter

try:
    from octobot_trading.api.exchange import create_new_exchange
except ImportError:
    logging.error("ExchangeHistoryDataCollector requires OctoBot-Trading package installed")


class ExchangeHistoryDataCollector(ExchangeDataCollector):
    IMPORTER = GenericExchangeDataImporter

    def __init__(self, config, exchange_name, symbols, time_frames):
        super().__init__(config, exchange_name, symbols, time_frames)
        self.exchange = None
        self.exchange_manager = None

    async def start(self):
        exchange_factory = create_new_exchange(self.config, self.exchange_name, is_simulated=True, is_rest_only=True,
                                               is_collecting=True, exchange_only=True)
        await exchange_factory.create_basic()
        self.exchange_manager = exchange_factory.exchange_manager
        self.exchange = self.exchange_manager.exchange

        self.logger.info("Start collecting history")
        for symbol in self.symbols:
            self.logger.info(f"Collecting history for {symbol}...")
            await self.get_ticker_history(self.exchange_name, symbol)
            await self.get_order_book_history(self.exchange_name, symbol)
            await self.get_recent_trades_history(self.exchange_name, symbol)

            for time_frame in self.time_frames:
                self.logger.info(f"Collecting history on {time_frame}...")
                await self.get_ohlcv_history(self.exchange_name, symbol, time_frame)
                await self.get_kline_history(self.exchange_name, symbol, time_frame)

        await self.stop()

    async def stop(self):
        await self.exchange_manager.stop()

    async def get_ticker_history(self, exchange, symbol):
        pass

    async def get_order_book_history(self, exchange, symbol):
        pass

    async def get_recent_trades_history(self, exchange, symbol):
        pass

    async def get_ohlcv_history(self, exchange, symbol, time_frame):
        candles: list = await self.exchange.get_symbol_prices(symbol, time_frame)
        await self.save_ohlcv(exchange=exchange, symbol=symbol, time_frame=time_frame, candle=candles,
                              timestamp=[candle[0] for candle in candles], multiple=True)

    async def get_kline_history(self, exchange, symbol, time_frame):
        pass
