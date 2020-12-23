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
import octobot_services.interfaces.util as interfaces_util
import octobot_commons.profiles as profiles
import octobot_commons.errors as errors
import octobot_tentacles_manager.api as tentacles_manager_api


def get_current_profile():
    return interfaces_util.get_edited_config(dict_only=False).profile


def duplicate_and_select_profile(profile_id):
    config = interfaces_util.get_edited_config(dict_only=False)
    to_duplicate = config.profile_by_id[profile_id]
    new_profile = config.profile_by_id[profile_id].duplicate(name=f"{to_duplicate.name} (copy)",
                                                             description=to_duplicate.description)
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


def get_profiles_activated_tentacles(profiles_list):
    tentacles_by_profile_id = {}
    for profile in profiles_list.values():
        try:
            tentacles_by_profile_id[profile.profile_id] = tentacles_manager_api.get_activated_tentacles(
                tentacles_manager_api.get_tentacles_setup_config(profile.get_tentacles_config_path())
            )
        except Exception:
            # do not raise here to prevent avoid config display
            pass
    return tentacles_by_profile_id


def update_profile(profile_id, json_profile):
    config = interfaces_util.get_edited_config(dict_only=False)
    profile = config.profile_by_id[profile_id]
    profile.name = json_profile.get("name", profile.name)
    profile.description = json_profile.get("description", profile.description)
    profile.avatar = json_profile.get("avatar", profile.avatar)
    profile.validate_and_save_config()


def remove_profile(profile_id):
    profile = None
    if get_current_profile().profile_id == profile_id:
        return profile, "Can't remove the activated profile"
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


def import_profile(profile_path, name):
    profiles.import_profile(profile_path, name=name)
    interfaces_util.get_edited_config(dict_only=False).load_profiles()
