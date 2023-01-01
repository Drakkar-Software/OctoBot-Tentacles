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
import secrets
import octobot_commons.singleton as singleton
import octobot_commons.logging as logging
import octobot_commons.constants as constants
import octobot_commons.configuration as commons_configuration


class BrowsingDataProvider(singleton.Singleton):
    SESSION_SEC_KEY = "session_sec_key"
    FIRST_DISPLAY = "first_display"
    HOME = "home"
    PROFILE = "profile"
    PROFILE_SELECTOR = "profile_selector"
    DISPLAY_KEYS = [
        HOME, PROFILE, PROFILE_SELECTOR
    ]

    def __init__(self):
        self.browsing_data = {}
        self.logger = logging.get_logger(self.__class__.__name__)
        self._load_saved_data()

    def get_or_create_session_secret_key(self):
        try:
            return self._get_session_secret_key()
        except KeyError:
            self._generate_session_secret_key()
        except Exception as err:
            self.logger.exception(err, True, f"Unexpected error when reading session key: {err}")
            self._generate_session_secret_key()
        return self._get_session_secret_key()

    def get_and_unset_is_first_display(self, element):
        try:
            value = self.browsing_data[self.FIRST_DISPLAY][element]
        except KeyError:
            value = False
        if value:
            self.set_is_first_display(element, False)
        return value

    def set_is_first_display(self, element, is_first_display):
        if self.browsing_data[self.FIRST_DISPLAY][element] != is_first_display:
            self.browsing_data[self.FIRST_DISPLAY][element] = is_first_display
            self._dump_saved_data()

    def set_first_displays(self, is_first_display):
        for key in self.DISPLAY_KEYS:
            self.browsing_data[self.FIRST_DISPLAY][key] = is_first_display
        self._dump_saved_data()

    def _get_session_secret_key(self):
        return commons_configuration.decrypt(self.browsing_data[self.SESSION_SEC_KEY]).encode()

    def _create_session_secret_key(self):
        # always generate a new unique session secret key, reuse it to save sessions after restart
        # https://flask.palletsprojects.com/en/2.2.x/quickstart/#sessions
        return commons_configuration.encrypt(secrets.token_hex()).decode()

    def _generate_session_secret_key(self):
        self.browsing_data[self.SESSION_SEC_KEY] = self._create_session_secret_key()
        self._dump_saved_data()

    def _get_default_data(self):
        return {
            self.SESSION_SEC_KEY: self._create_session_secret_key(),
            self.FIRST_DISPLAY: {
                key: False
                for key in self.DISPLAY_KEYS
            }
        }

    def _load_saved_data(self):
        self.browsing_data = self._get_default_data()
        read_data = {}
        try:
            with open(self._get_file()) as sessions_file:
                read_data = json.load(sessions_file)
                self.browsing_data.update(read_data)
        except FileNotFoundError:
            pass
        except Exception as err:
            self.logger.exception(err, True, f"Unexpected error when reading saved data: {err}")
        if any(key not in read_data for key in self.browsing_data):
            # save fixed data
            self._dump_saved_data()

    def _dump_saved_data(self):
        try:
            with open(self._get_file(), "w") as sessions_file:
                return json.dump(self.browsing_data, sessions_file)
        except Exception as err:
            self.logger.exception(err, True, f"Unexpected error when reading saved data: {err}")

    def _get_file(self):
        return os.path.join(constants.USER_FOLDER, f"{self.__class__.__name__}_data.json")
