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
import asyncio
from contextlib import asynccontextmanager

from octobot_services.interfaces.bots.abstract_bot_interface import AbstractBotInterface
from octobot_services.interfaces.abstract_interface import AbstractInterface


# All test coroutines will be treated as marked.

pytestmark = pytest.mark.asyncio


async def create_minimalist_unconnected_octobot():
    # import here to prevent later web interface import issues
    from octobot.octobot import OctoBot
    from octobot.constants import TENTACLES_SETUP_CONFIG_KEY
    from octobot.producers.evaluator_producer import EvaluatorProducer
    from octobot.producers.exchange_producer import ExchangeProducer
    from octobot_commons.tests.test_config import load_test_config
    from octobot_tentacles_manager.loaders.tentacle_loading import reload_tentacle_by_tentacle_class
    from octobot_trading.api.modes import init_trading_mode_config
    from octobot_evaluators.api.evaluators import initialize_evaluators
    from tests.test_utils.config import load_test_tentacles_config
    octobot = OctoBot(load_test_config())
    octobot.initialized = True
    tentacles_config = load_test_tentacles_config()
    reload_tentacle_by_tentacle_class()
    init_trading_mode_config(octobot.config)
    init_trading_mode_config(octobot.config)
    octobot.task_manager.async_loop = asyncio.get_event_loop()
    octobot.task_manager.create_pool_executor()
    octobot.tentacles_setup_config = tentacles_config
    octobot.configuration_manager.add_element(TENTACLES_SETUP_CONFIG_KEY, tentacles_config)
    octobot.exchange_producer = ExchangeProducer(None, octobot, None, False)
    octobot.evaluator_producer = EvaluatorProducer(None, octobot)
    octobot.evaluator_producer.matrix_id = await initialize_evaluators(octobot.config, tentacles_config)
    return octobot


# use context manager instead of fixture to prevent pytest threads issues
@asynccontextmanager
async def get_bot_interface():
    bot_interface = AbstractBotInterface({})
    AbstractInterface.initialize_global_project_data((await create_minimalist_unconnected_octobot()).octobot_api,
                                                     "octobot",
                                                     "x.y.z-alpha42")
    yield bot_interface


async def test_all_commands():
    """
    Test basing commands interactions, for most of them a default message will be saying that the bot is not ready.
    :return: None
    """
    async with get_bot_interface() as bot_interface:
        assert len(bot_interface.get_command_configuration()) > 50
        assert len(bot_interface.get_command_market_status()) > 50
        assert len(bot_interface.get_command_trades_history()) > 50
        assert len(bot_interface.get_command_open_orders()) > 50
        assert len(bot_interface.get_command_fees()) > 50
        assert "Nothing to sell" in bot_interface.get_command_sell_all_currencies()
        assert "Nothing to sell for BTC" in bot_interface.get_command_sell_all("BTC")
        assert len(bot_interface.get_command_portfolio()) > 50
        assert len(bot_interface.get_command_profitability()) > 50
        assert "I'm alive since" in bot_interface.get_command_ping()
        assert all(elem in bot_interface.get_command_version()
                   for elem in [AbstractInterface.project_name, AbstractInterface.project_version])
        assert "Hello, I'm OctoBot" in bot_interface.get_command_start()
