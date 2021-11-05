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
import asyncio
import logging
import os
import time

import octobot_backtesting.collectors as collector
import octobot_backtesting.enums as backtesting_enums
import octobot_backtesting.errors as errors
import octobot_commons.constants as commons_constants
import octobot_commons.enums as commons_enums
import octobot_commons.time_frame_manager as time_frame_manager
import tentacles.Backtesting.importers.exchanges.generic_exchange_importer as generic_exchange_importer

try:
    import octobot_trading.api as trading_api
except ImportError:
    logging.error("ExchangeHistoryDataCollector requires OctoBot-Trading package installed")


class ExchangeBotSnapshotCollector(collector.AbstractExchangeBotSnapshotCollector):
    IMPORTER = generic_exchange_importer.GenericExchangeDataImporter

    def __init__(self, config, exchange_name, tentacles_setup_config, symbols, time_frames,
                 use_all_available_timeframes=False,
                 data_format=backtesting_enums.DataFormats.REGULAR_COLLECTOR_DATA,
                 start_timestamp=None,
                 end_timestamp=None):
        super().__init__(config, exchange_name, tentacles_setup_config, symbols, time_frames,
                         use_all_available_timeframes, data_format=data_format,
                         start_timestamp=start_timestamp, end_timestamp=end_timestamp)
        self.exchange_manager = None

    async def start(self):
        self.should_stop = False
        should_stop_database = True
        try:
            self.exchange_manager = trading_api.get_exchange_manager_from_exchange_id(self.exchange_id)

            await self.check_timestamps()

            # create description
            await self._create_description()

            self.total_steps = len(self.time_frames) * len(self.symbols)
            self.in_progress = True

            self.logger.info(f"Start collecting history on {self.exchange_name}")
            tasks = []
            for symbol_index, symbol in enumerate(self.symbols):
                self.logger.info(f"Collecting history for {symbol}...")
                tasks.append(asyncio.create_task(self.get_ticker_history(self.exchange_name, symbol)))
                tasks.append(asyncio.create_task(self.get_order_book_history(self.exchange_name, symbol)))
                tasks.append(asyncio.create_task(self.get_recent_trades_history(self.exchange_name, symbol)))

                for time_frame_index, time_frame in enumerate(self.time_frames):
                    tasks.append(asyncio.create_task(self.get_ohlcv_history(self.exchange_name, symbol, time_frame)))
                    tasks.append(asyncio.create_task(self.get_kline_history(self.exchange_name, symbol, time_frame)))
                    if symbol_index == time_frame_index == 0:
                        # let tables get created
                        await asyncio.gather(*tasks)
                        tasks = []
            if tasks:
                await asyncio.gather(*tasks)

        except Exception as err:
            await self.database.stop()
            should_stop_database = False
            # Do not keep errored data file
            if os.path.isfile(self.temp_file_path):
                os.remove(self.temp_file_path)
            if not self.should_stop:
                self.logger.exception(err, True, f"Error when collecting {self.exchange_name} history for "
                                                 f"{', '.join(self.symbols)}: {err}")
                raise errors.DataCollectorError(err)
        finally:
            await self.stop(should_stop_database=should_stop_database)

    async def stop(self, should_stop_database=True):
        self.should_stop = True
        if should_stop_database:
            await self.database.stop()
            self.finalize_database()
        self.exchange_manager = None
        self.in_progress = False
        self.finished = True
        return self.finished

    async def get_ticker_history(self, exchange, symbol):
        pass

    async def get_order_book_history(self, exchange, symbol):
        pass

    async def get_recent_trades_history(self, exchange, symbol):
        pass

    async def get_ohlcv_history(self, exchange, symbol, time_frame):
        time_frame_sec = commons_enums.TimeFramesMinutes[time_frame] * commons_constants.MINUTE_TO_SECONDS
        symbol_data = trading_api.get_symbol_data(self.exchange_manager, symbol)
        candles = trading_api.get_symbol_historical_candles(symbol_data, time_frame)
        merged_candles = [
            [
                time_val,
                candles[commons_enums.PriceIndexes.IND_PRICE_OPEN.value][index],
                candles[commons_enums.PriceIndexes.IND_PRICE_HIGH.value][index],
                candles[commons_enums.PriceIndexes.IND_PRICE_LOW.value][index],
                candles[commons_enums.PriceIndexes.IND_PRICE_CLOSE.value][index],
                candles[commons_enums.PriceIndexes.IND_PRICE_VOL.value][index],
            ]
            for index, time_val in enumerate(candles[commons_enums.PriceIndexes.IND_PRICE_TIME.value])
        ]
        await self.save_ohlcv(
                exchange=exchange,
                cryptocurrency=self.exchange_manager.exchange.get_pair_cryptocurrency(symbol),
                symbol=symbol, time_frame=time_frame, candle=merged_candles,
                timestamp=[candle[commons_enums.PriceIndexes.IND_PRICE_TIME.value] + time_frame_sec
                           for candle in merged_candles],
                multiple=True
        )
        self.current_step_index += 1

    async def get_kline_history(self, exchange, symbol, time_frame):
        pass
