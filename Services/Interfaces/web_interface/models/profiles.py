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
import os

import octobot_services.interfaces.util as interfaces_util
import octobot_commons.profiles as profiles
import octobot_commons.errors as errors
import octobot_tentacles_manager.api as tentacles_manager_api


ACTIVATION = "activation"
VERSION = "version"
IMPORTED = "imported"


def get_current_profile():
    return interfaces_util.get_edited_config(dict_only=False).profile


def duplicate_and_select_profile(profile_id):
    config = interfaces_util.get_edited_config(dict_only=False)
    to_duplicate = config.profile_by_id[profile_id]
    new_profile = config.profile_by_id[profile_id].duplicate(name=f"{to_duplicate.name}_(copy)",
                                                             description=to_duplicate.description)
    tentacles_manager_api.refresh_profile_tentacles_setup_config(new_profile.path)
    config.load_profiles()
    _select_and_save(config, new_profile.profile_id)


def select_profile(profile_id):
    config = interfaces_util.get_edited_config(dict_only=False)
    _select_and_save(config, profile_id)


def _select_and_save(config, profile_id):
    config.select_profile(profile_id)
    _update_edited_tentacles_config(config)
    config.save()


def _update_edited_tentacles_config(config):
    updated_tentacles_config = tentacles_manager_api.get_tentacles_setup_config(config.get_tentacles_config_path())
    interfaces_util.set_edited_tentacles_config(updated_tentacles_config)


def get_profiles():
    return interfaces_util.get_edited_config(dict_only=False).profile_by_id


def get_profiles_tentacles_details(profiles_list):
    tentacles_by_profile_id = {}
    for profile in profiles_list.values():
        try:
            tentacles_setup_config = tentacles_manager_api.get_tentacles_setup_config(
                profile.get_tentacles_config_path()
            )
            tentacles_by_profile_id[profile.profile_id] = {
                ACTIVATION: tentacles_manager_api.get_activated_tentacles(tentacles_setup_config),
                VERSION: tentacles_manager_api.get_tentacles_installation_version(tentacles_setup_config),
                IMPORTED: profile.imported
            }
        except Exception:
            # do not raise here to prevent avoid config display
            pass
    return tentacles_by_profile_id


def update_profile(profile_id, json_profile):
    config = interfaces_util.get_edited_config(dict_only=False)
    profile = config.profile_by_id[profile_id]
    new_name = json_profile.get("name", profile.name)
    renamed = profile.name != new_name
    if renamed and get_current_profile().profile_id == profile_id:
        return False, "Can't rename the active profile"
    profile.name = new_name
    profile.description = json_profile.get("description", profile.description)
    profile.avatar = json_profile.get("avatar", profile.avatar)
    profile.validate_and_save_config()
    if renamed:
        profile.rename_folder(new_name, False)
    return True, "Profile updated"


def remove_profile(profile_id):
    profile = None
    if get_current_profile().profile_id == profile_id:
        return profile, "Can't remove the active profile"
    try:
        profile = interfaces_util.get_edited_config(dict_only=False).profile_by_id[profile_id]
        interfaces_util.get_edited_config(dict_only=False).remove_profile(profile_id)
    except errors.ProfileRemovalError as err:
        return profile, err
    return profile, None


def export_profile(profile_id, export_path) -> str:
    return profiles.export_profile(
        interfaces_util.get_edited_config(dict_only=False).profile_by_id[profile_id],
        export_path
    )


def import_profile(profile_path, name, profile_url=None):
    profile = profiles.import_profile(profile_path, name=name, origin_url=profile_url)
    interfaces_util.get_edited_config(dict_only=False).load_profiles()
    return profile


def download_and_import_profile(profile_url):
    name = profile_url.split('/')[-1]
    file_path = profiles.download_profile(profile_url, name)
    profile = import_profile(file_path, name, profile_url=profile_url)
    if os.path.isfile(file_path):
        os.remove(file_path)
    return profile


def get_profile_name(profile_id) -> str:
    return interfaces_util.get_edited_config(dict_only=False).profile_by_id[profile_id].name
