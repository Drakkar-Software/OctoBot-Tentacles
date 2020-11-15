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

api = flask.Blueprint('api', __name__, url_prefix='/api', template_folder="")

from tentacles.Services.Interfaces.web_interface.api import metadata
from tentacles.Services.Interfaces.web_interface.api import trading


from tentacles.Services.Interfaces.web_interface.api.metadata import (
    version,
    user_feedback,
    announcements,
)
from tentacles.Services.Interfaces.web_interface.api.trading import (
    orders,
    refresh_portfolio,
    currency_list,
)


__all__ = [
    "version",
    "user_feedback",
    "announcements",
    "orders",
    "refresh_portfolio",
    "currency_list",
]
