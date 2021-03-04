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
import asyncio
import csv
import datetime
import json
import math
import os.path as path

from octobot_commons import symbol_util

import octobot_backtesting.collectors.exchanges as exchanges
import octobot_backtesting.constants as backtesting_constants
import octobot_backtesting.converters as converters
import octobot_backtesting.data as backtesting_data
import octobot_backtesting.enums as backtesting_enums
import octobot_commons.constants as commons_constants
import octobot_commons.enums as commons_enums


class CSVDataConverter(converters.DataConverter):
    """
    CSVDataConverter can be used to convert a csv data file into OctoBot data file.
    """
    DATA_FILE_EXT = ".csv"
    VERSION = "1.0"
    DATA_FILE_TIME_DATE_FORMAT = '%Y%m%d%H%M%S'

    def __init__(self, backtesting_file_to_convert):
        super().__init__(backtesting_file_to_convert)
        self.exchange_name = ""
        self.symbol = ""
        self.time_data = -1
        self.time_frames = []
        self.file_content = {}
        self.file_headers = []
        self.database = None
        self.converted_file = backtesting_data.get_backtesting_file_name(exchanges.AbstractExchangeHistoryCollector)

    async def can_convert(self, ) -> bool:
        with open(self.file_to_convert, "r") as csv_file:
            self.file_content = csv.DictReader(csv_file, delimiter=',')
            self.file_headers = self.file_content.fieldnames

        self.exchange_name, self.symbol, time_frame = CSVDataConverter._interpret_file_name(self.file_to_convert)
        self.time_frames = [commons_enums.TimeFrames(time_frame)]
        if not all([
            commons_enums.PriceStrings.STR_PRICE_TIME.value in self.file_headers,
            commons_enums.PriceStrings.STR_PRICE_OPEN.value in self.file_headers,
            commons_enums.PriceStrings.STR_PRICE_HIGH.value in self.file_headers,
            commons_enums.PriceStrings.STR_PRICE_LOW.value in self.file_headers,
            commons_enums.PriceStrings.STR_PRICE_CLOSE.value in self.file_headers,
            commons_enums.PriceStrings.STR_PRICE_VOL.value in self.file_headers,
        ]):
            return False
        return True

    async def convert(self) -> bool:
        try:
            self.database = backtesting_data.DataBase(
                path.join(backtesting_constants.BACKTESTING_FILE_PATH, self.converted_file))
            await self.database.initialize()
            await self._create_description()
            with open(self.file_to_convert, "r") as csv_file:
                self.file_content = csv.DictReader(csv_file, delimiter=',')
                for time_frame in self.time_frames:
                    await self._convert_ohlcv(time_frame)
            return True
        except Exception as e:
            self.logger.exception(e, True, f"Error while converting data file: {e}")
            return False
        finally:
            if self.database is not None:
                await self.database.stop()

    async def _create_description(self):
        time_object = datetime.datetime.fromtimestamp(self.time_data)
        await self.database.insert(backtesting_enums.DataTables.DESCRIPTION,
                                   timestamp=datetime.datetime.timestamp(time_object),
                                   version=self.VERSION,
                                   exchange=self.exchange_name,
                                   symbols=json.dumps([self.symbol]),
                                   time_frames=json.dumps([tf.value for tf in self.time_frames]))

    async def _convert_ohlcv(self, time_frame):
        # use time_frame_sec to add time to save the candle closing time
        time_frame_sec = commons_enums.TimeFramesMinutes[time_frame] * commons_constants.MINUTE_TO_SECONDS
        candles = self._get_formatted_candles()
        await self.database.insert_all(backtesting_enums.ExchangeDataTables.OHLCV,
                                       timestamp=[candle[0] + time_frame_sec for candle in candles],
                                       exchange_name=self.exchange_name, symbol=self.symbol,
                                       time_frame=time_frame.value, candle=[json.dumps(c) for c in candles])

    def _get_formatted_candles(self):
        candles = []
        candle_index = 0
        for row in self.file_content:
            candle_data = [None] * len(commons_enums.PriceIndexes)
            if self.time_data == -1:
                self.time_data = int(row[commons_enums.PriceStrings.STR_PRICE_TIME.value])
            candle_data[commons_enums.PriceIndexes.IND_PRICE_CLOSE.value] = \
                float(row[commons_enums.PriceStrings.STR_PRICE_CLOSE.value])
            candle_data[commons_enums.PriceIndexes.IND_PRICE_OPEN.value] = \
                float(row[commons_enums.PriceStrings.STR_PRICE_OPEN.value])
            candle_data[commons_enums.PriceIndexes.IND_PRICE_HIGH.value] = \
                float(row[commons_enums.PriceStrings.STR_PRICE_HIGH.value])
            candle_data[commons_enums.PriceIndexes.IND_PRICE_LOW.value] = \
                float(row[commons_enums.PriceStrings.STR_PRICE_LOW.value])
            candle_data[commons_enums.PriceIndexes.IND_PRICE_TIME.value] = \
                int(row[commons_enums.PriceStrings.STR_PRICE_TIME.value])
            candle_data[commons_enums.PriceIndexes.IND_PRICE_VOL.value] = \
                float(row[commons_enums.PriceStrings.STR_PRICE_VOL.value])
            if all(not math.isnan(v) for v in candle_data):
                candles.insert(candle_index, candle_data)
                candle_index += 1
        return candles

    @staticmethod
    def _interpret_file_name(file_name):
        """
        Should be named like exchange_symbol_timeframe.csv (bitstamp_BTC_USD_1m.csv)
        """
        data = path.basename(file_name).split("_")
        try:
            exchange_name = data[0]
            symbol = symbol_util.merge_currencies(data[1], data[2])
            file_ext = CSVDataConverter.DATA_FILE_EXT
            time_frame = data[3].replace(file_ext, "")
        except KeyError:
            exchange_name = None
            symbol = None
            time_frame = None

        return exchange_name, symbol, time_frame
