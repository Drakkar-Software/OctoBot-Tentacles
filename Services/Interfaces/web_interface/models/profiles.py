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


def get_current_profile():
    return interfaces_util.get_edited_config(dict_only=False).profile


def select_profile(profile_id):
    config = interfaces_util.get_edited_config(dict_only=False)
    config.select_profile(profile_id)
    config.save()


def get_profiles():
    return interfaces_util.get_edited_config(dict_only=False).profile_by_id


def update_profile(profile_id, json_profile):
    config = interfaces_util.get_edited_config(dict_only=False)
    profile = config.profile_by_id[profile_id]
    profile.name = json_profile.get("name", profile.name)
    profile.description = json_profile.get("description", profile.description)
    profile.avatar = json_profile.get("avatar", profile.avatar)
    config.save()


def export_profile(profile_id, export_path):
    profiles.export_profile(
        interfaces_util.get_edited_config(dict_only=False).profile_by_id[profile_id],
        export_path
    )


def import_profile(profile_path):
    profiles.import_profile(profile_path)
