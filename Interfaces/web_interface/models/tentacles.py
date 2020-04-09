#  Drakkar-Software OctoBot-Interfaces
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
from octobot.constants import DEFAULT_TENTACLES_URL, DEFAULT_TENTACLES_PACKAGE_NAME
from octobot_commons.logging.logging_util import get_logger
from octobot_interfaces.util.bot import get_bot_api
from octobot_interfaces.util.util import run_in_bot_main_loop
from octobot_tentacles_manager.api.configurator import get_user_tentacles_packages
from octobot_tentacles_manager.api.inspector import get_installed_tentacles
from octobot_tentacles_manager.api.installer import install_all_tentacles
from octobot_tentacles_manager.api.uninstaller import uninstall_all_tentacles, uninstall_tentacles
from octobot_tentacles_manager.api.updater import update_all_tentacles, update_tentacles

logger = get_logger("TentaclesModel")


def get_tentacles_packages():
    packages = {
        DEFAULT_TENTACLES_URL: DEFAULT_TENTACLES_PACKAGE_NAME
    }
    for tentacle_package, package_name in get_user_tentacles_packages(get_bot_api().get_edited_tentacles_config()):
        packages[tentacle_package] = package_name
    return packages


def register_and_install(path_or_url):
    # TODO or remove if irrelevant in 0.4
    return False


def call_tentacle_manager(coro, *args, **kwargs):
    return run_in_bot_main_loop(coro(*args, **kwargs)) == 0


def install_packages():
    if call_tentacle_manager(install_all_tentacles,
                             DEFAULT_TENTACLES_URL,
                             aiohttp_session=get_bot_api().get_aiohttp_session()):
        return "Tentacles installed"
    else:
        return False


def update_packages():
    if call_tentacle_manager(update_all_tentacles,
                             DEFAULT_TENTACLES_URL,
                             aiohttp_session=get_bot_api().get_aiohttp_session()):
        return "Tentacles updated"
    else:
        return False


def reset_packages():
    if call_tentacle_manager(uninstall_all_tentacles,
                             use_confirm_prompt=False):
        return "Reset successful"
    else:
        return None


def update_modules(modules):
    if call_tentacle_manager(update_tentacles,
                             modules,
                             DEFAULT_TENTACLES_URL,
                             aiohttp_session=get_bot_api().get_aiohttp_session()):
        return f"{len(modules)} Tentacles updated"
    else:
        return None


def uninstall_modules(modules):
    if call_tentacle_manager(uninstall_tentacles,
                             modules):
        return f"{len(modules)} Tentacles uninstalled"
    else:
        return None


def get_tentacles():
    return get_installed_tentacles()
