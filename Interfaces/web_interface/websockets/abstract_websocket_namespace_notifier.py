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
from flask_socketio import Namespace

from octobot_commons.logging.logging_util import get_logger
from tentacles.Interfaces.web_interface import Notifier


class AbstractWebSocketNamespaceNotifier(Namespace, Notifier):

    def __init__(self, namespace=None):
        super(Namespace, self).__init__(namespace)
        self.logger = get_logger(self.__class__.__name__)
        self.clients_count = 0

    def all_clients_send_notifications(self, **kwargs) -> bool:
        raise NotImplementedError("all_clients_send_notifications is not implemented")

    def on_connect(self):
        self.clients_count += 1

    def on_disconnect(self):
        # will be called after some time (requires timeout)
        self.clients_count -= 1

    def _has_clients(self):
        return self.clients_count > 0
