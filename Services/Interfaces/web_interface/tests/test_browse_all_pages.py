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
import asyncio

import tentacles.Services.Interfaces.web_interface as web_interface
import tentacles.Services.Interfaces.web_interface.tests as web_interface_tests

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def test_browse_all_pages_no_required_password():
    async with web_interface_tests.get_web_interface(False) as web_interface_instance:
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(
                *[web_interface_tests.check_page_no_login_redirect(
                    f"http://localhost:{web_interface_tests.PORT}{rule.replace('.', '/')}",
                    session)
                  for rule in _get_all_native_rules(web_interface_instance, web_interface.server_instance,
                                                    black_list=["/advanced/tentacles",
                                                                "/advanced/tentacle_packages"]
                                                    )])


async def test_browse_all_pages_required_password_without_login():
    async with web_interface_tests.get_web_interface(True) as web_interface_instance:
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(
                *[web_interface_tests.check_page_login_redirect(
                    f"http://localhost:{web_interface_tests.PORT}{rule.replace('.', '/')}",
                    session)
                  for rule in _get_all_native_rules(web_interface_instance, web_interface.server_instance)])


async def test_browse_all_pages_required_password_with_login():
    async with web_interface_tests.get_web_interface(True) as web_interface_instance:
        async with aiohttp.ClientSession() as session:
            await web_interface_tests.login_user_on_session(session)
            # correctly display pages: session is logged in
            await asyncio.gather(
                *[web_interface_tests.check_page_no_login_redirect(
                    f"http://localhost:{web_interface_tests.PORT}{rule.replace('.', '/')}",
                    session)
                  for rule in _get_all_native_rules(web_interface_instance, web_interface.server_instance,
                                                    ["/logout"])])
        async with aiohttp.ClientSession() as unauthenticated_session:
            # redirect to login page: session is not logged in
            await asyncio.gather(
                *[web_interface_tests.check_page_login_redirect(
                    f"http://localhost:{web_interface_tests.PORT}{rule.replace('.', '/')}",
                    unauthenticated_session)
                  for rule in _get_all_native_rules(web_interface_instance, web_interface.server_instance)])


async def test_logout():
    async with web_interface_tests.get_web_interface(True):
        async with aiohttp.ClientSession() as session:
            await web_interface_tests.login_user_on_session(session)
            await web_interface_tests.check_page_no_login_redirect(f"http://localhost:{web_interface_tests.PORT}/",
                                                                   session)
            await web_interface_tests.check_page_login_redirect(f"http://localhost:{web_interface_tests.PORT}/logout",
                                                                session)
            await web_interface_tests.check_page_login_redirect(f"http://localhost:{web_interface_tests.PORT}/",
                                                                session)


def _get_all_native_rules(web_interface_instance, app, black_list=None):
    if black_list is None:
        black_list = []
    full_back_list = URL_BLACK_LIST + black_list + web_interface_tests.get_plugins_routes(web_interface_instance, app)
    return set(rule.rule
               for rule in app.url_map.iter_rules()
               if "GET" in rule.methods
               and _has_no_empty_params(rule)
               and rule.rule not in full_back_list)


# backlist endpoints expecting additional data
URL_BLACK_LIST = ["/symbol_market_status", "/tentacle_media", "/watched_symbols", "/export_logs",
                  "/api/first_exchange_details"]


def _has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)
