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
import json
import octobot_commons.singleton as singleton
import octobot_commons.logging as logging
import octobot_commons.constants as constants


class BrowsingDataProvider(singleton.Singleton):
    SESSIONS = "sessions"
    FIRST_DISPLAY = "first_display"
    HOME = "home"
    PROFILE = "profile"

    def __init__(self):
        self.browsing_data = self._get_default_data()
        self.logger = logging.get_logger(self.__class__.__name__)
        self._load_saved_data()

    def get_saved_sessions(self):
        try:
            return self.browsing_data[self.SESSIONS]
        except KeyError:
            return []

    def set_saved_sessions(self, sessions):
        if sessions != self.browsing_data[self.SESSIONS]:
            self.browsing_data[self.SESSIONS] = sessions
            self._dump_saved_data()

    def get_and_unset_is_first_display(self, element):
        value = self.browsing_data[self.FIRST_DISPLAY][element]
        if value := self.browsing_data[self.FIRST_DISPLAY][element]:
            self.set_is_first_display(element, False)
        return value

    def set_is_first_display(self, element, is_first_display):
        if self.browsing_data[self.FIRST_DISPLAY][element] != is_first_display:
            self.browsing_data[self.FIRST_DISPLAY][element] = is_first_display
            self._dump_saved_data()

    def set_first_displays(self, is_first_display):
        for key in self.browsing_data[self.FIRST_DISPLAY]:
            self.browsing_data[self.FIRST_DISPLAY][key] = is_first_display
        self._dump_saved_data()

    def _load_saved_data(self):
        try:
            with open(self._get_file()) as sessions_file:
                self.browsing_data = json.load(sessions_file)
                self.browsing_data.update(self._get_default_data())
        except FileNotFoundError:
            pass
        except Exception as err:
            self.logger.exception(err, True, f"Unexpected error when reading saved data: {err}")
        self.browsing_data = self._get_default_data()

    def _get_default_data(self):
        return {
            self.SESSIONS: [],
            self.FIRST_DISPLAY: {
                self.HOME: False,
                self.PROFILE: False,
            }
        }

    def _dump_saved_data(self):
        with open(self._get_file(), "w") as sessions_file:
            return json.dump(self.browsing_data, sessions_file)

    def _get_file(self):
        return os.path.join(constants.USER_FOLDER, f"{self.__class__.__name__}_data.json")

