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

import praw

import octobot_services.constants as services_constants
import octobot_services.services as services
import octobot.constants as constants


class RedditService(services.AbstractService):
    CLIENT_ID = "client-id"
    CLIENT_SECRET = "client-secret"
    PASSWORD = "password"
    USERNAME = "username"

    def __init__(self):
        super().__init__()
        self.reddit_api = None

    def get_fields_description(self):
        return {
            self.CLIENT_ID: "Your client ID.",
            self.CLIENT_SECRET: "Your client ID secret.",
            self.PASSWORD: "Your Reddit password.",
            self.USERNAME: "Your Reddit username."
        }

    def get_default_value(self):
        return {
            self.CLIENT_ID: "",
            self.CLIENT_SECRET: "",
            self.PASSWORD: "",
            self.USERNAME: ""
        }

    def get_required_config(self):
        return [self.CLIENT_ID, self.CLIENT_SECRET, self.PASSWORD, self.USERNAME]

    @classmethod
    def get_help_page(cls) -> str:
        return f"{constants.OCTOBOT_WIKI_URL}/Reddit-interface#reddit-interface"

    @staticmethod
    def is_setup_correctly(config):
        return services_constants.CONFIG_REDDIT in config[services_constants.CONFIG_CATEGORY_SERVICES] \
               and services_constants.CONFIG_SERVICE_INSTANCE in config[services_constants.CONFIG_CATEGORY_SERVICES][
                   services_constants.CONFIG_REDDIT]

    async def prepare(self):
        if not self.reddit_api:
            self.reddit_api = \
                praw.Reddit(client_id=
                            self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_REDDIT][
                                self.CLIENT_ID],
                            client_secret=
                            self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_REDDIT][
                                self.CLIENT_SECRET],
                            password=
                            self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_REDDIT][
                                self.PASSWORD],
                            user_agent='bot',
                            username=
                            self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_REDDIT][
                                self.USERNAME])

    def get_type(self):
        return services_constants.CONFIG_REDDIT

    def get_website_url(self):
        return "https://www.reddit.com"

    def get_endpoint(self):
        return self.reddit_api

    def has_required_configuration(self):
        return services_constants.CONFIG_CATEGORY_SERVICES in self.config \
               and services_constants.CONFIG_REDDIT in self.config[services_constants.CONFIG_CATEGORY_SERVICES] \
               and self.check_required_config(
            self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_REDDIT])

    def get_successful_startup_message(self):
        return f"Successfully initialized using {self.config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_REDDIT][self.USERNAME]}" \
               f" account.", True
