"""
OctoBot Tentacle

$tentacle_description: {
    "name": "in_development_social_evaluators",
    "type": "Evaluator",
    "subtype": "Social",
    "version": "1.1.0",
    "requirements": [],
    "config_files": [],
    "developing": true
}
"""

#  Drakkar-Software OctoBot
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


from config import *
from evaluator.Social.social_evaluator import ForumSocialEvaluator, NewsSocialEvaluator


class BTCTalkForumEvaluator(ForumSocialEvaluator):

    def get_data(self):
        pass

    async def eval_impl(self):
        pass

    async def start_task(self):
        pass


class MediumNewsEvaluator(NewsSocialEvaluator):

    def get_data(self):
        pass

    async def eval_impl(self):
        await self.notify_evaluator_task_managers(self.__class__.__name__)

    async def start_task(self):
        pass

    def set_default_config(self):
        self.social_config = {
            CONFIG_REFRESH_RATE: 2
        }
