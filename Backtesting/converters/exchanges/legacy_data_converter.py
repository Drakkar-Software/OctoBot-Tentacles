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
import gzip
import json
from enum import Enum
from os.path import basename, join
from datetime import datetime

from octobot_backtesting.collectors.exchanges.abstract_exchange_history_collector import \
    AbstractExchangeHistoryCollector
from octobot_backtesting.constants import BACKTESTING_FILE_PATH
from octobot_backtesting.converters.data_converter import DataConverter
from octobot_backtesting.data.data_file_manager import get_backtesting_file_name
from octobot_backtesting.data.database import DataBase
from octobot_backtesting.enums import DataTables, ExchangeDataTables
from octobot_commons.constants import MINUTE_TO_SECONDS
from octobot_commons.enums import TimeFrames, TimeFramesMinutes
from octobot_commons.symbol_util import merge_currencies


class LegacyDataConverter(DataConverter):
    """
    LegacyDataConverter can be used to convert OctoBot v0.3 data files into v0.4 data files.
    """
    DATA_FILE_EXT = ".data"
    VERSION = "1.0"
    DATA_FILE_TIME_DATE_FORMAT = '%Y%m%d%H%M%S'

    class PriceIndexes(Enum):
        IND_PRICE_TIME = 0
        IND_PRICE_OPEN = 1
        IND_PRICE_HIGH = 2
        IND_PRICE_LOW = 3
        IND_PRICE_CLOSE = 4
        IND_PRICE_VOL = 5

    def __init__(self, backtesting_file_to_convert):
        super().__init__(backtesting_file_to_convert)
        self.exchange_name = ""
        self.symbol = ""
        self.time_data = ""
        self.time_frames = []
        self.file_content = {}
        self.database = None
        self.converted_file = get_backtesting_file_name(AbstractExchangeHistoryCollector)

    async def can_convert(self,) -> bool:
        self.exchange_name, self.symbol, self.time_data = LegacyDataConverter._interpret_file_name(self.file_to_convert)
        if None in (self.exchange_name, self.symbol, self.time_data):
            return False
        self.file_content = self._read_data_file()
        if not self.file_content:
            return False
        for time_frame, candles_data in self.file_content.items():
            try:
                # check time frame validity
                time_frame = TimeFrames(time_frame)
                # check candle data validity
                if isinstance(candles_data, list) and len(candles_data) == 6:
                    # check candle data non-emptiness
                    if all(data for data in candles_data):
                        self.time_frames.append(time_frame)
            except ValueError:
                pass
        return bool(self.time_frames)

    async def convert(self) -> bool:
        try:
            self.database = DataBase(join(BACKTESTING_FILE_PATH, self.converted_file))
            await self.database.initialize()
            await self._create_description()
            for time_frame in self.time_frames:
                await self._convert_ohlcv(time_frame)
            return True
        except Exception as e:
            self.logger.error(f"Error while converting data file: {e}")
            self.logger.exception(e)
            return False
        finally:
            if self.database is not None:
                await self.database.stop()

    async def _create_description(self):
        time_object = datetime.strptime(self.time_data, self.DATA_FILE_TIME_DATE_FORMAT)
        await self.database.insert(DataTables.DESCRIPTION,
                                   timestamp=datetime.timestamp(time_object),
                                   version=self.VERSION,
                                   exchange=self.exchange_name,
                                   symbols=json.dumps([self.symbol]),
                                   time_frames=json.dumps([tf.value for tf in self.time_frames]))

    async def _convert_ohlcv(self, time_frame):
        # use time_frame_sec to add time to save the candle closing time
        time_frame_sec = TimeFramesMinutes[time_frame] * MINUTE_TO_SECONDS
        candles = self._get_formatted_candles(time_frame)
        await self.database.insert_all(ExchangeDataTables.OHLCV,
                                       timestamp=[candle[0] + time_frame_sec for candle in candles],
                                       exchange_name=self.exchange_name, symbol=self.symbol,
                                       time_frame=time_frame.value, candle=[json.dumps(c) for c in candles])

    def _get_formatted_candles(self, time_frame):
        data = self.file_content[time_frame.value]
        candles = []
        for i in range(len(data[LegacyDataConverter.PriceIndexes.IND_PRICE_TIME.value])):
            candles.insert(i, [None] * len(LegacyDataConverter.PriceIndexes))
            candles[i][LegacyDataConverter.PriceIndexes.IND_PRICE_CLOSE.value] = \
                data[LegacyDataConverter.PriceIndexes.IND_PRICE_CLOSE.value][i]
            candles[i][LegacyDataConverter.PriceIndexes.IND_PRICE_OPEN.value] = \
                data[LegacyDataConverter.PriceIndexes.IND_PRICE_OPEN.value][i]
            candles[i][LegacyDataConverter.PriceIndexes.IND_PRICE_HIGH.value] = \
                data[LegacyDataConverter.PriceIndexes.IND_PRICE_HIGH.value][i]
            candles[i][LegacyDataConverter.PriceIndexes.IND_PRICE_LOW.value] = \
                data[LegacyDataConverter.PriceIndexes.IND_PRICE_LOW.value][i]
            candles[i][LegacyDataConverter.PriceIndexes.IND_PRICE_TIME.value] = \
                data[LegacyDataConverter.PriceIndexes.IND_PRICE_TIME.value][i]
            candles[i][LegacyDataConverter.PriceIndexes.IND_PRICE_VOL.value] = \
                data[LegacyDataConverter.PriceIndexes.IND_PRICE_VOL.value][i]
        return candles

    def _read_data_file(self):
        try:
            # try zipfile
            with gzip.open(self.file_to_convert, 'r') as file_to_parse:
                file_content = json.loads(file_to_parse.read())
        except OSError:
            # try without unzip
            with open(self.file_to_convert) as file_to_parse:
                file_content = json.loads(file_to_parse.read())
        except Exception:
            return {}
        return file_content

    @staticmethod
    def _interpret_file_name(file_name):
        data = basename(file_name).split("_")
        try:
            exchange_name = data[0]
            symbol = merge_currencies(data[1], data[2])
            file_ext = LegacyDataConverter.DATA_FILE_EXT
            timestamp = data[3] + data[4].replace(file_ext, "")
        except KeyError:
            exchange_name = None
            symbol = None
            timestamp = None

        return exchange_name, symbol, timestamp
