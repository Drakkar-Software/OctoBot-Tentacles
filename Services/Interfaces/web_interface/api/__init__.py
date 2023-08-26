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
import flask

import tentacles.Services.Interfaces.web_interface.api.config
import tentacles.Services.Interfaces.web_interface.api.exchanges
import tentacles.Services.Interfaces.web_interface.api.feedback
import tentacles.Services.Interfaces.web_interface.api.metadata
import tentacles.Services.Interfaces.web_interface.api.trading
import tentacles.Services.Interfaces.web_interface.api.user_commands
import tentacles.Services.Interfaces.web_interface.api.bots
import tentacles.Services.Interfaces.web_interface.api.webhook

from tentacles.Services.Interfaces.web_interface.api.webhook import (
    has_webhook,
    register_webhook
)


def register():
    blueprint = flask.Blueprint('api', __name__, url_prefix='/api', template_folder="")

    tentacles.Services.Interfaces.web_interface.api.config.register(blueprint)
    tentacles.Services.Interfaces.web_interface.api.exchanges.register(blueprint)
    tentacles.Services.Interfaces.web_interface.api.feedback.register(blueprint)
    tentacles.Services.Interfaces.web_interface.api.metadata.register(blueprint)
    tentacles.Services.Interfaces.web_interface.api.trading.register(blueprint)
    tentacles.Services.Interfaces.web_interface.api.user_commands.register(blueprint)
    tentacles.Services.Interfaces.web_interface.api.bots.register(blueprint)
    tentacles.Services.Interfaces.web_interface.api.webhook.register(blueprint)

    return blueprint


__all__ = [
    "has_webhook",
    "register_webhook",
    "register",
]
