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

from octobot_commons.config_manager import get_password_hash
from tentacles.Services.Interfaces.web_interface import WebInterface
from tentacles.Services.Interfaces.web_interface import server_instance
from tentacles.Services.Interfaces.web_interface.controllers.authentication import LoginForm
from octobot_services.interfaces.abstract_interface import AbstractInterface


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio
PORT = 5555
PASSWORD = "123"


async def _init_bot():
    # import here to prevent web interface import issues
    from octobot.octobot import OctoBot
    from octobot.constants import TENTACLES_SETUP_CONFIG_KEY
    from octobot.producers.evaluator_producer import EvaluatorProducer
    from octobot.producers.exchange_producer import ExchangeProducer
    from octobot_commons.tests.test_config import load_test_config
    from octobot_tentacles_manager.loaders.tentacle_loading import reload_tentacle_by_tentacle_class
    from octobot_evaluators.api.evaluators import initialize_evaluators
    from tests.test_utils.config import load_test_tentacles_config
    octobot = OctoBot(load_test_config())
    octobot.initialized = True
    tentacles_config = load_test_tentacles_config()
    reload_tentacle_by_tentacle_class()
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
async def get_web_interface(require_password):
    try:
        web_interface = WebInterface({})
        web_interface.port = PORT
        web_interface.should_open_web_interface = False
        web_interface.requires_password = require_password
        web_interface.password_hash = get_password_hash(PASSWORD)
        AbstractInterface.bot_api = (await _init_bot()).octobot_api
        with patch.object(web_interface, "_register_on_channels", new=AsyncMock()):
            threading.Thread(target=_start_web_interface, args=(web_interface,)).start()
            # ensure web interface had time to start or it can't be stopped at the moment
            await asyncio.sleep(1)
            yield web_interface
    finally:
        await web_interface.stop()


async def test_browse_all_pages_no_required_password():
    async with get_web_interface(False):
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(*[_check_page_no_login_redirect(f"http://localhost:{PORT}{rule.replace('.', '/')}",
                                                                 session)
                                   for rule in _get_all_rules(server_instance)])


async def test_browse_all_pages_required_password_without_login():
    async with get_web_interface(True):
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(*[check_page_login_redirect(f"http://localhost:{PORT}{rule.replace('.', '/')}",
                                                             session)
                                   for rule in _get_all_rules(server_instance)])


async def test_browse_all_pages_required_password_with_login():
    async with get_web_interface(True):
        async with aiohttp.ClientSession() as session:
            await _login_user_on_session(session)
            # correctly display pages: session is logged in
            await asyncio.gather(*[_check_page_no_login_redirect(f"http://localhost:{PORT}{rule.replace('.', '/')}",
                                                                 session)
                                   for rule in _get_all_rules(server_instance, ["/logout"])])
        async with aiohttp.ClientSession() as unauthenticated_session:
            # redirect to login page: session is not logged in
            await asyncio.gather(*[check_page_login_redirect(f"http://localhost:{PORT}{rule.replace('.', '/')}",
                                                             unauthenticated_session)
                                   for rule in _get_all_rules(server_instance)])


async def test_logout():
    async with get_web_interface(True):
        async with aiohttp.ClientSession() as session:
            await _login_user_on_session(session)
            await _check_page_no_login_redirect(f"http://localhost:{PORT}/", session)
            await check_page_login_redirect(f"http://localhost:{PORT}/logout", session)
            await check_page_login_redirect(f"http://localhost:{PORT}/", session)


async def _check_page_no_login_redirect(url, session):
    async with session.get(url) as resp:
        text = await resp.text()
        assert "We are sorry, but an unexpected error occurred" not in text
        assert "We are sorry, but this doesn't exist" not in text
        if not (url.endswith("/login") or url.endswith("/logout")):
            assert "input type=submit value=Login" not in text
            assert not resp.real_url.name == "login"
        assert resp.status == 200


async def check_page_login_redirect(url, session):
    async with session.get(url) as resp:
        text = await resp.text()
        assert "We are sorry, but an unexpected error occurred" not in text
        assert "We are sorry, but this doesn't exist" not in text
        if "/api/" not in url:
            assert "input type=submit value=Login" in text
            assert resp.real_url.name == "login"
        assert resp.status == 200


async def _login_user_on_session(session):
    login_data = {
        "password": PASSWORD,
        "remember_me": False
    }
    with patch.object(LoginForm, "validate_on_submit", new=_force_validate_on_submit):
        async with session.post(f"http://localhost:{PORT}/login",
                                data=login_data) as resp:
            assert resp.status == 200


def _get_all_rules(app, black_list=None):
    if black_list is None:
        black_list = []
    return set(rule.rule
               for rule in app.url_map.iter_rules()
               if "GET" in rule.methods and _has_no_empty_params(rule) and rule.rule not in URL_BLACK_LIST + black_list)


# backlist endpoints expecting additional data
URL_BLACK_LIST = ["/symbol_market_status", "/tentacle_media", "/watched_symbols"]


def _start_web_interface(interface):
    asyncio.run(interface.start())


def _has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)


def _force_validate_on_submit(*_):
    return True
