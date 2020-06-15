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
from contextlib import asynccontextmanager
from os.path import join

from octobot_backtesting.api.backtesting import initialize_backtesting, get_importers
from octobot_backtesting.api.importer import stop_importer
from octobot_channels.util.channel_creator import create_all_subclasses_channel
from octobot_commons.tests.test_config import load_test_config, TEST_CONFIG_FOLDER
from octobot_trading.api.symbol_data import force_set_mark_price
from octobot_trading.channels.exchange_channel import ExchangeChannel, TimeFrameExchangeChannel, set_chan
from octobot_trading.constants import CONFIG_SIMULATOR, CONFIG_STARTING_PORTFOLIO
from octobot_trading.exchanges.exchange_manager import ExchangeManager
from octobot_trading.exchanges.exchange_simulator import ExchangeSimulator
from octobot_trading.exchanges.rest_exchange import RestExchange
from octobot_trading.traders.trader_simulator import TraderSimulator
from tentacles.Trading.Mode import ArbitrageTradingMode


@asynccontextmanager
async def exchange(exchange_name, backtesting=None, symbol="BTC/USDT"):
    exchange_manager = None
    try:
        config = load_test_config()
        config[CONFIG_SIMULATOR][CONFIG_STARTING_PORTFOLIO]["USDT"] = 2000
        exchange_manager = ExchangeManager(config, exchange_name)

        # use backtesting not to spam exchanges apis
        exchange_manager.is_simulated = True
        exchange_manager.is_backtesting = True
        backtesting = backtesting or await initialize_backtesting(
            config,
            exchange_ids=[exchange_manager.id],
            matrix_id=None,
            data_files=[join(TEST_CONFIG_FOLDER, "AbstractExchangeHistoryCollector_1586017993.616272.data")])
        exchange_manager.exchange_type = RestExchange.create_exchange_type(exchange_manager.exchange_class_string)
        exchange_manager.exchange = ExchangeSimulator(exchange_manager.config,
                                                      exchange_manager.exchange_type,
                                                      exchange_manager,
                                                      backtesting)
        await exchange_manager.exchange.initialize()
        for exchange_channel_class_type in [ExchangeChannel, TimeFrameExchangeChannel]:
            await create_all_subclasses_channel(exchange_channel_class_type, set_chan, exchange_manager=exchange_manager)

        trader = TraderSimulator(config, exchange_manager)
        await trader.initialize()

        mode = ArbitrageTradingMode(config, exchange_manager)
        mode.symbol = None if mode.get_is_symbol_wildcard() else symbol
        await mode.initialize()
        # add mode to exchange manager so that it can be stopped and freed from memory
        exchange_manager.trading_modes.append(mode)

        # set BTC/USDT price at 1000 USDT
        force_set_mark_price(exchange_manager, symbol, 1000)
        # force triggering_price_delta_ratio equivalent to a 0.2% setting in minimal_price_delta_percent
        mode.producers[0].triggering_price_delta_ratio = 1 - 0.002
        yield mode.producers[0], mode.consumers[0], exchange_manager
    finally:
        if exchange_manager is not None:
            for importer in get_importers(exchange_manager.exchange.backtesting):
                await stop_importer(importer)
            if exchange_manager.exchange.backtesting.time_updater is not None:
                await exchange_manager.exchange.backtesting.stop()
            await exchange_manager.stop()
