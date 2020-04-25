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

from flask_socketio import emit

from tentacles.Interfaces.web_interface import BACKTESTING_NOTIFICATION_KEY, register_notifier
from tentacles.Interfaces.web_interface.models.backtesting import get_backtesting_status
from tentacles.Interfaces.web_interface.websockets import namespaces
from tentacles.Interfaces.web_interface.websockets.abstract_websocket_namespace_notifier import \
    AbstractWebSocketNamespaceNotifier


class BacktestingNamespace(AbstractWebSocketNamespaceNotifier):

    @staticmethod
    def _get_backtesting_status():
        backtesting_status, progress = get_backtesting_status()
        return {"status": backtesting_status, "progress": progress}

    def on_backtesting_status(self):
        emit("backtesting_status", self._get_backtesting_status())

    def all_clients_send_notifications(self, **kwargs) -> bool:
        if self._has_clients():
            try:
                self.socketio.emit("backtesting_status", self._get_backtesting_status(), namespace=self.namespace)
                return True
            except Exception as e:
                self.logger.exception(e, True, f"Error when sending backtesting_status: {e}")
        return False

    def on_connect(self):
        super().on_connect()
        self.on_backtesting_status()


notifier = BacktestingNamespace('/backtesting')
register_notifier(BACKTESTING_NOTIFICATION_KEY, notifier)
namespaces.append(notifier)
