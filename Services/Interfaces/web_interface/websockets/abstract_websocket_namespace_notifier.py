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
from functools import wraps
from flask_login import current_user
from flask_socketio import Namespace, disconnect

from octobot_commons.logging.logging_util import get_logger
from tentacles.Services.Interfaces.web_interface import Notifier
from tentacles.Services.Interfaces.web_interface.login.web_login_manager import IS_LOGIN_REQUIRED


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


def websocket_with_login_required_when_activated(func):
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        # Use == because of the flask proxy (this is not a simple python None value)
        if IS_LOGIN_REQUIRED and (current_user == None or not current_user.is_authenticated):
            disconnect(self)
        else:
            return func(self, *args, **kwargs)
    return wrapped
