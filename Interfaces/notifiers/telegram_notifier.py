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
from octobot_commons.enums import MarkdownFormat
from octobot_notifications.notification.notification import Notification
from octobot_notifications.notifier.abstract_notifier import AbstractNotifier
from tentacles.Interfaces.services import TelegramService


class TelegramNotifier(AbstractNotifier):
    REQUIRED_SERVICE = TelegramService
    NOTIFICATION_TYPE_KEY = "telegram"

    async def _handle_notification(self, notification: Notification):
        self.logger.debug(f"sending notification: {notification}")
        title = notification.title
        text = notification.markdown_text
        if notification.markdown_format is not MarkdownFormat.NONE:
            text = f"{notification.markdown_format.value}{text}{notification.markdown_format.value}"
        if title:
            title = f"{MarkdownFormat.CODE.value}{title}{MarkdownFormat.CODE.value}"
            text = f"{title}\n{text}"
        await self.service.send_message(text, markdown=notification.markdown_format is not MarkdownFormat.NONE)
