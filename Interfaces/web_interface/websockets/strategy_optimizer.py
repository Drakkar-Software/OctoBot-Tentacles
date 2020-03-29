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

from tentacles.Interfaces.web_interface.models.strategy_optimizer import get_optimizer_status
from tentacles.Interfaces.web_interface.websockets import namespaces
from tentacles.Interfaces.web_interface.websockets.abstract_websocket_namespace_notifier import AbstractWebSocketNamespaceNotifier


class StrategyOptimizerNamespace(AbstractWebSocketNamespaceNotifier):

    @staticmethod
    def _get_strategy_optimizer_status():
        optimizer_status, progress, overall_progress, errors = get_optimizer_status()
        return {"status": optimizer_status,
                "progress": progress,
                "overall_progress": overall_progress,
                "errors": errors}

    def on_strategy_optimizer_status(self):
        emit("strategy_optimizer_status", self._get_strategy_optimizer_status())

    def on_connect(self):
        super().on_connect()
        self.on_strategy_optimizer_status()


namespaces.append(StrategyOptimizerNamespace('/strategy_optimizer'))
