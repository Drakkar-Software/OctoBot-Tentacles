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
from octobot_services.notification.notification import Notification
from octobot_services.notifier.abstract_notifier import AbstractNotifier
from tentacles.Services.Interfaces.web_interface import add_notification
from tentacles.Services import WebService


class WebNotifier(AbstractNotifier):
    REQUIRED_SERVICES = [WebService]
    NOTIFICATION_TYPE_KEY = "web"

    async def _handle_notification(self, notification: Notification):
        await add_notification(notification.level, notification.title, notification.text.replace("\n", "<br>"))
