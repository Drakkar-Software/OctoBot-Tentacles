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
from octobot.constants import DEFAULT_TENTACLES_URL, OCTOBOT_FOLDER
from octobot_commons.logging.logging_util import get_logger
from octobot_services.interfaces.util.bot import get_bot_api
from octobot_services.interfaces.util.util import run_in_bot_main_loop
from octobot_tentacles_manager.api.configurator import get_registered_tentacle_packages
from octobot_tentacles_manager.api.inspector import get_installed_tentacles_modules
from octobot_tentacles_manager.api.installer import install_all_tentacles
from octobot_tentacles_manager.api.uninstaller import uninstall_all_tentacles, uninstall_tentacles
from octobot_tentacles_manager.api.updater import update_all_tentacles, update_tentacles
from octobot_tentacles_manager.constants import UNKNOWN_TENTACLES_PACKAGE_LOCATION

logger = get_logger("TentaclesModel")


def get_tentacles_packages():
    return get_registered_tentacle_packages(get_bot_api().get_edited_tentacles_config())


def call_tentacle_manager(coro, *args, **kwargs):
    return run_in_bot_main_loop(coro(*args, **kwargs)) == 0


def install_packages(path_or_url=None):
    message = "Tentacles installed"
    for package_url in [path_or_url] if path_or_url else \
            get_registered_tentacle_packages(get_bot_api().get_edited_tentacles_config()).values():
        if not package_url == UNKNOWN_TENTACLES_PACKAGE_LOCATION:
            if not call_tentacle_manager(install_all_tentacles,
                                         package_url,
                                         setup_config=get_bot_api().get_edited_tentacles_config(),
                                         aiohttp_session=get_bot_api().get_aiohttp_session(),
                                         bot_install_dir=OCTOBOT_FOLDER
                                         ):
                return False
        else:
            message = "Tentacles installed however it is impossible to re-install tentacles with unknown package origin"
    return message


def update_packages():
    message = "Tentacles updated"
    for package_url in get_registered_tentacle_packages(get_bot_api().get_edited_tentacles_config()).values():
        if not package_url == UNKNOWN_TENTACLES_PACKAGE_LOCATION:
            if not call_tentacle_manager(update_all_tentacles,
                                         package_url,
                                         aiohttp_session=get_bot_api().get_aiohttp_session()):
                return False
        else:
            message = "Tentacles updated however it is impossible to update tentacles with unknown package origin"
    return message


def reset_packages():
    if call_tentacle_manager(uninstall_all_tentacles,
                             setup_config=get_bot_api().get_edited_tentacles_config(),
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
    return get_installed_tentacles_modules()
