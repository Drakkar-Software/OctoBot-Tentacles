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
import aiohttp
import pytest
import threading
import asyncio

from mock import patch, AsyncMock
from contextlib import asynccontextmanager
from tentacles.Services.Interfaces.web_interface import WebInterface
from tentacles.Services.Interfaces.web_interface import server_instance
from octobot_services.interfaces.abstract_interface import AbstractInterface


# All test coroutines will be treated as marked.

pytestmark = pytest.mark.asyncio
PORT = 5555


async def _init_bot():
    # import here to prevent web interface import issues
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
async def get_web_interface():
    try:
        web_interface = WebInterface({})
        web_interface.port = PORT
        AbstractInterface.bot_api = (await _init_bot()).octobot_api
        with patch.object(web_interface, "_register_on_channels", new=AsyncMock()):
            threading.Thread(target=_start_web_interface, args=(web_interface,)).start()
            # ensure web interface had time to start or it can't be stopped at the moment
            await asyncio.sleep(1)
            yield web_interface
    finally:
        await web_interface.stop()


async def test_browse_all_pages():
    async with get_web_interface():
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(*[check_page(f"http://localhost:{PORT}{rule.replace('.', '/')}", session)
                                   for rule in _get_all_rules(server_instance)])


async def check_page(url, session):
    async with session.get(url) as resp:
        text = await resp.text()
        assert "We are sorry, but an unexpected error occurred" not in text
        assert "We are sorry, but this doesn't exist" not in text
        assert resp.status == 200


def _get_all_rules(app):
    return set(rule.rule
               for rule in app.url_map.iter_rules()
               if "GET" in rule.methods and has_no_empty_params(rule) and rule.rule not in URL_BLACK_LIST)


# backlist endpoints expecting additional data
URL_BLACK_LIST = ["/symbol_market_status", "/tentacle_media", "/watched_symbols"]


def _start_web_interface(interface):
    asyncio.run(interface.start())


def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)
