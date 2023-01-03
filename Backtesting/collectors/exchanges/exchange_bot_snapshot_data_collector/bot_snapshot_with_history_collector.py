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
import json
import time
import shutil

import octobot_backtesting.collectors as collector
import octobot_backtesting.importers as importers
import octobot_backtesting.enums as backtesting_enums
import octobot_backtesting.constants as backtesting_constants
import octobot_backtesting.errors as backtesting_errors
import octobot_commons.errors as commons_errors
import octobot_commons.constants as commons_constants
import octobot_commons.enums as commons_enums
import octobot_commons.symbols.symbol_util as symbol_util
import octobot_commons.databases as databases
import octobot_backtesting.data as data
import tentacles.Backtesting.importers.exchanges.generic_exchange_importer as generic_exchange_importer

try:
    import octobot_trading.api as trading_api
    import octobot_trading.errors as trading_errors
except ImportError:
    logging.error("ExchangeHistoryDataCollector requires OctoBot-Trading package installed")


class ExchangeBotSnapshotWithHistoryCollector(collector.AbstractExchangeBotSnapshotCollector):
    IMPORTER = generic_exchange_importer.GenericExchangeDataImporter

    def __init__(self, config, exchange_name, exchange_type, tentacles_setup_config, symbols, time_frames,
                 use_all_available_timeframes=False,
                 data_format=backtesting_enums.DataFormats.REGULAR_COLLECTOR_DATA,
                 start_timestamp=None,
                 end_timestamp=None):
        super().__init__(config, exchange_name, exchange_type, tentacles_setup_config, symbols, time_frames,
                         use_all_available_timeframes, data_format=data_format,
                         start_timestamp=start_timestamp, end_timestamp=end_timestamp)
        self.exchange_type = None
        self.exchange_manager = None
        self.file_name = data.get_backtesting_file_name(self.__class__,
                                                        self.get_permanent_file_identifier,
                                                        data_format=data_format)
        self.is_creating_database = False
        self.description = None
        self.set_file_path()

    def get_permanent_file_identifier(self):
        symbols = "-".join(symbol_util.merge_symbol(symbol.symbol_str) for symbol in self.symbols)
        time_frames = "-".join(tf.value for tf in self.time_frames)
        return f"{self.exchange_name}{backtesting_constants.BACKTESTING_DATA_FILE_SEPARATOR}" \
               f"{symbols}{backtesting_constants.BACKTESTING_DATA_FILE_SEPARATOR}{time_frames}"

    async def initialize(self):
        self.create_database()
        await self.database.initialize()
        await self._check_database_content()

    def set_file_path(self) -> None:
        super().set_file_path()
        if os.path.isfile(self.file_path):
            shutil.copy(self.file_path, self.temp_file_path)

    def finalize_database(self):
        if os.path.isfile(self.file_path):
            os.remove(self.file_path)
        os.rename(self.temp_file_path, self.file_path)

    async def _check_database_content(self):
        # load description
        try:
            self.description = await data.get_database_description(self.database)
            found_exchange_name = self.description[backtesting_enums.DataFormatKeys.EXCHANGE.value]
            found_symbols = [symbol_util.parse_symbol(symbol)
                             for symbol in self.description[backtesting_enums.DataFormatKeys.SYMBOLS.value]]
            found_time_frames = self.description[backtesting_enums.DataFormatKeys.TIME_FRAMES.value]
            if found_exchange_name != self.exchange_name:
                raise backtesting_errors.IncompatibleDatafileError(f"Exchange name in database: {found_exchange_name}, "
                                                                   f"requested exchange: {self.exchange_name}")
            if found_symbols != self.symbols:
                raise backtesting_errors.IncompatibleDatafileError(f"Pairs in database: {found_symbols}, "
                                                                   f"requested exchange: {self.symbols}")
            if found_time_frames != self.time_frames:
                raise backtesting_errors.IncompatibleDatafileError(f"Time frames name in database: {found_time_frames}, "
                                                                   f"requested exchange: {self.time_frames}")
        except commons_errors.DatabaseNotFoundError:
            # newly created datafile
            self.is_creating_database = True

    async def start(self):
        self.should_stop = False
        should_stop_database = True
        self.current_step_percent = 0
        self.total_steps = len(self.time_frames) * len(self.symbols)
        try:
            self.exchange_manager = trading_api.get_exchange_manager_from_exchange_id(self.exchange_id)

            await self.adapt_timestamps()

            # create/update description
            if self.is_creating_database:
                await self._create_description()
            else:
                await self._update_description()

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
                                                 f"{', '.join([symbol.symbol_str for symbol in self.symbols])}: {err}")
                raise backtesting_errors.DataCollectorError(err) from err
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

    async def _update_description(self):
        updated_values = {}
        if self.end_timestamp and int(self.description[backtesting_enums.DataFormatKeys.END_TIMESTAMP.value]) * 1000 < self.end_timestamp:
            updated_values["end_timestamp"] = int(self.end_timestamp/1000)
        if self.start_timestamp and int(self.description[backtesting_enums.DataFormatKeys.START_TIMESTAMP.value]) * 1000 > self.start_timestamp:
            updated_values["start_timestamp"] = int(self.start_timestamp/1000)
        if updated_values:
            updated_values["timestamp"] = time.time()
            await self.database.update(backtesting_enums.DataTables.DESCRIPTION,
                                       updated_value_by_column=updated_values,
                                       version=self.VERSION,
                                       exchange=self.exchange_name,
                                       symbols=json.dumps([symbol.symbol_str for symbol in self.symbols]),
                                       time_frames=json.dumps([tf.value for tf in self.time_frames]))

    async def get_ticker_history(self, exchange, symbol):
        pass

    async def get_order_book_history(self, exchange, symbol):
        pass

    async def get_recent_trades_history(self, exchange, symbol):
        pass

    def get_ohlcv_snapshot(self, symbol, time_frame):
        symbol_data = trading_api.get_symbol_data(self.exchange_manager, str(symbol), allow_creation=False)
        candles = trading_api.get_symbol_historical_candles(symbol_data, time_frame)
        return [
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

    async def collect_historical_ohlcv(self, exchange, symbol, time_frame, time_frame_sec,
                                       start_time, end_time, update_progress=True):
        last_progress = 0
        symbol_id = str(symbol)
        async for candles in trading_api.get_historical_ohlcv(self.exchange_manager, symbol_id, time_frame,
                                                              start_time, end_time):
            await self.save_ohlcv(
                    exchange=exchange,
                    cryptocurrency=self.exchange_manager.exchange.get_pair_cryptocurrency(symbol_id),
                    symbol=symbol.symbol_str, time_frame=time_frame, candle=candles,
                    timestamp=[candle[commons_enums.PriceIndexes.IND_PRICE_TIME.value] + time_frame_sec
                               for candle in candles],
                    multiple=True
            )
            progress = (candles[-1][commons_enums.PriceIndexes.IND_PRICE_TIME.value] - start_time / 1000) / \
                                        ((end_time - start_time) / 1000) * 100
            if update_progress:
                progress_over_all_steps = progress / self.total_steps
                self.current_step_percent += progress_over_all_steps - last_progress
                self.logger.debug(f"progress: {self.current_step_percent}%")
                last_progress = progress_over_all_steps
        return last_progress

    def find_candle(self, candles, timestamp):
        for candle in candles:
            if candle[-1][commons_enums.PriceIndexes.IND_PRICE_TIME.value] == timestamp:
                return candle[-1], candle[0]
        return None, None

    async def update_ohlcv(self, exchange, symbol, time_frame, time_frame_sec,
                           database_candles, current_bot_candles):
        to_add_candles = []
        symbol_id = str(symbol)
        for up_to_date_candle in current_bot_candles:
            current_candle_time = up_to_date_candle[commons_enums.PriceIndexes.IND_PRICE_TIME.value]
            equivalent_db_candle, candle_timestamp = self.find_candle(database_candles, current_candle_time)
            if equivalent_db_candle is None:
                to_add_candles.append(up_to_date_candle)
            elif equivalent_db_candle != up_to_date_candle:
                updated_value_by_column = {
                    "candle": json.dumps(up_to_date_candle)
                }
                await self.database.update(backtesting_enums.ExchangeDataTables.OHLCV,
                                           updated_value_by_column=updated_value_by_column,
                                           exchange_name=exchange,
                                           cryptocurrency=
                                           self.exchange_manager.exchange.get_pair_cryptocurrency(symbol_id),
                                           symbol=symbol.symbol_str,
                                           time_frame=time_frame.value,
                                           timestamp=candle_timestamp)
        if to_add_candles:
            await self.save_ohlcv(
                exchange=exchange,
                cryptocurrency=self.exchange_manager.exchange.get_pair_cryptocurrency(symbol_id),
                symbol=symbol, time_frame=time_frame, candle=to_add_candles,
                timestamp=[candle[commons_enums.PriceIndexes.IND_PRICE_TIME.value] + time_frame_sec
                           for candle in to_add_candles],
                multiple=True
            )

    async def _check_ohlcv_integrity(self, exchange, symbol, time_frame):
        database_candles = await self._import_candles_from_datafile(exchange, symbol, time_frame)
        # ensure no timestamp is here twice
        timestamps = set(candle[0] for candle in database_candles)
        if len(timestamps) != len(database_candles):
            self.logger.warning(f"Duplicate candles in {exchange} data file for {symbol.symbol_str} on {time_frame}: "
                                f"{len(timestamps)} different timestamps for {len(database_candles)} "
                                f"different candles.")
            return False
        return True

    async def get_ohlcv_history(self, exchange, symbol, time_frame):
        try:
            last_progress = 0
            time_frame_sec = commons_enums.TimeFramesMinutes[time_frame] * commons_constants.MINUTE_TO_SECONDS
            # use current data from current bot
            bot_first_data_timestamp = await self.get_first_candle_timestamp(symbol, time_frame)
            current_bot_candles = self.get_ohlcv_snapshot(symbol, time_frame)
            if self.is_creating_database:
                if self.start_timestamp and self.start_timestamp < bot_first_data_timestamp:
                    # fetch missing data
                    last_progress = await self.collect_historical_ohlcv(
                        exchange, symbol, time_frame, time_frame_sec, self.start_timestamp, bot_first_data_timestamp)
                await self.save_ohlcv(
                        exchange=exchange,
                        cryptocurrency=self.exchange_manager.exchange.get_pair_cryptocurrency(str(symbol)),
                        symbol=symbol.symbol_str, time_frame=time_frame, candle=current_bot_candles,
                        timestamp=[candle[commons_enums.PriceIndexes.IND_PRICE_TIME.value] + time_frame_sec
                                   for candle in current_bot_candles],
                        multiple=True
                )
            else:
                database_candles = await self._import_candles_from_datafile(exchange, symbol, time_frame)
                first_candle_data_time = min(candle[-1][commons_enums.PriceIndexes.IND_PRICE_TIME.value]
                                             for candle in database_candles) * 1000
                last_candle_data_time = max(candle[-1][commons_enums.PriceIndexes.IND_PRICE_TIME.value]
                                            for candle in database_candles) * 1000
                if self.start_timestamp and self.start_timestamp + time_frame_sec * 1000 < first_candle_data_time:
                    # fetch missing data between required start time and actual start time in data file
                    last_progress = await self.collect_historical_ohlcv(
                        exchange, symbol, time_frame, time_frame_sec, self.start_timestamp, first_candle_data_time)
                if last_candle_data_time + 1 < bot_first_data_timestamp:
                    # fetch missing data between end time in data file and available data
                    # last_candle_data_time + 1 not to fetch the first candle twice
                    # do not add (time_frame_sec * 1000) to bot_first_data_timestamp to avoid double adding
                    await self.collect_historical_ohlcv(
                        exchange, symbol, time_frame, time_frame_sec, last_candle_data_time + 1,
                        bot_first_data_timestamp, update_progress=False)
                # finally, apply current candles
                await self.update_ohlcv(exchange, symbol, time_frame, time_frame_sec,
                                        database_candles, current_bot_candles)
            if not await self._check_ohlcv_integrity(exchange, symbol, time_frame):
                self.logger.error(f"Error when checking database integrity. "
                                  f"Delete this data file: {self.file_name} to reset it.")
            self.current_step_percent += 100 / self.total_steps - last_progress
        except trading_errors.FailedRequest as err:
            self.logger.exception(err, False)
            self.logger.warning(f"Ignored {symbol} {time_frame} candles on {exchange} ({err})")
        except Exception:
            raise

    async def _import_candles_from_datafile(self, exchange, symbol, time_frame):
        return importers.import_ohlcvs(
            await self.database.select(backtesting_enums.ExchangeDataTables.OHLCV,
                                       size=databases.SQLiteDatabase.DEFAULT_SIZE,
                                       exchange_name=exchange, symbol=symbol.symbol_str,
                                       time_frame=time_frame.value)
        )

    async def get_kline_history(self, exchange, symbol, time_frame):
        pass

    async def adapt_timestamps(self):
        lowest_timestamp = min([await self.get_first_candle_timestamp(symbol, tf)
                                for tf in self.time_frames
                                for symbol in self.symbols])
        if self.start_timestamp is None or lowest_timestamp < self.start_timestamp:
            self.start_timestamp = lowest_timestamp
        self.end_timestamp = self.end_timestamp or time.time() * 1000
        if self.start_timestamp > self.end_timestamp:
            raise backtesting_errors.DataCollectorError("start_timestamp is higher than end_timestamp")

    async def get_first_candle_timestamp(self, symbol, time_frame):
        symbol_data = trading_api.get_symbol_data(self.exchange_manager, str(symbol), allow_creation=False)
        candles = trading_api.get_symbol_historical_candles(symbol_data, time_frame)
        return candles[commons_enums.PriceIndexes.IND_PRICE_TIME.value][0] * 1000
