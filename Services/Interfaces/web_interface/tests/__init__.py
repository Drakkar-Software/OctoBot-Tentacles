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
import threading
import asyncio
import time
import mock
import contextlib

import octobot_commons.configuration as configuration
import tentacles.Services.Interfaces.web_interface.controllers as controllers
import tentacles.Services.Interfaces.web_interface as web_interface
import octobot_services.interfaces as interfaces
import octobot_commons.singleton as singleton
import octobot_commons.authentication as authentication
import octobot.community as community


PORT = 5555
PASSWORD = "123"
MAX_START_TIME = 5


async def _init_bot():
    # import here to prevent web interface import issues
    import octobot.octobot as octobot
    import octobot.constants as octobot_constants
    import octobot.producers as producers
    import octobot_commons.tests as test_config
    import octobot_tentacles_manager.loaders as loaders
    import octobot_evaluators.api as evaluators_api
    import tests.test_utils.config as config
    # force community CommunityAuthentication reset
    community.IdentifiersProvider.use_production()
    singleton.Singleton._instances.pop(authentication.Authenticator, None)
    singleton.Singleton._instances.pop(community.CommunityAuthentication, None)
    octobot = octobot.OctoBot(test_config.load_test_config(dict_only=False))
    octobot.initialized = True
    tentacles_config = config.load_test_tentacles_config()
    loaders.reload_tentacle_by_tentacle_class()
    octobot.task_manager.async_loop = asyncio.get_event_loop()
    octobot.task_manager.create_pool_executor()
    octobot.tentacles_setup_config = tentacles_config
    octobot.configuration_manager.add_element(octobot_constants.TENTACLES_SETUP_CONFIG_KEY, tentacles_config)
    octobot.exchange_producer = producers.ExchangeProducer(None, octobot, None, False)
    octobot.evaluator_producer = producers.EvaluatorProducer(None, octobot)
    await evaluators_api.initialize_evaluators(octobot.config, tentacles_config)
    octobot.evaluator_producer.matrix_id = evaluators_api.create_matrix()
    # Do not edit config file
    octobot.community_auth.edited_config = None
    return octobot


def _start_web_interface(interface):
    asyncio.run(interface.start())


# use context manager instead of fixture to prevent pytest threads issues
@contextlib.asynccontextmanager
async def get_web_interface(require_password):
    web_interface_instance = None
    try:
        web_interface_instance = web_interface.WebInterface({})
        web_interface_instance.port = PORT
        web_interface_instance.should_open_web_interface = False
        web_interface_instance.set_requires_password(require_password)
        web_interface_instance.password_hash = configuration.get_password_hash(PASSWORD)
        interfaces.AbstractInterface.bot_api = (await _init_bot()).octobot_api
        with mock.patch.object(web_interface_instance, "_register_on_channels", new=mock.AsyncMock()):
            threading.Thread(target=_start_web_interface, args=(web_interface_instance,)).start()
            # ensure web interface had time to start or it can't be stopped at the moment
            launch_time = time.time()
            while not web_interface_instance.started and time.time() - launch_time < MAX_START_TIME:
                await asyncio.sleep(0.3)
            if not web_interface_instance.started:
                raise RuntimeError("Web interface did not start in time")
            yield web_interface_instance
    finally:
        if web_interface_instance is not None:
            await web_interface_instance.stop()


async def check_page_no_login_redirect(url, session):
    async with session.get(url) as resp:
        text = await resp.text()
        assert "We are sorry, but an unexpected error occurred" not in text
        assert "We are sorry, but this doesn't exist" not in text
        if not (url.endswith("login") or url.endswith("logout")
                or url.endswith("/community") or url.endswith("/profiles_selector")):
            assert "input type=submit value=Login" not in text
            assert not resp.real_url.name == "login"
        if url.endswith("historical_portfolio_value"):
            assert resp.status == 404
        else:
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


def get_plugins_routes(web_interface_instance, app):
    all_rules = tuple(rule for rule in app.url_map.iter_rules())
    plugin_routes = []
    for plugin in web_interface_instance.registered_plugins:
        plugin_routes += [rule.rule for rule in get_plugin_routes(app, plugin, all_rules)]
    return plugin_routes


def get_plugin_routes(app, plugin, all_rules=None):
    all_rules = all_rules or [rule for rule in app.url_map.iter_rules()]
    return (
        route for route in all_rules
        if route.rule.startswith(f"{plugin.blueprint.url_prefix}/")
    )


def _force_validate_on_submit(*_):
    return True


async def login_user_on_session(session):
    login_data = {
        "password": PASSWORD,
        "remember_me": False
    }
    with mock.patch.object(controllers.LoginForm, "validate_on_submit", new=_force_validate_on_submit):
        async with session.post(f"http://localhost:{PORT}/login",
                                data=login_data) as resp:
            assert resp.status == 200


def get_all_plugin_rules(app, plugin_class, black_list):
    plugin_instance = plugin_class.factory()
    plugin_instance.blueprint_factory()
    return set(rule.rule
               for rule in get_plugin_routes(app, plugin_instance)
               if "GET" in rule.methods
               and _has_no_empty_params(rule)
               and rule.rule not in black_list)


def _has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)
