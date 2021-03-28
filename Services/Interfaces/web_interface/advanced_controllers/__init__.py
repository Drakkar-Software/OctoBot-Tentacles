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

advanced = flask.Blueprint('advanced', __name__, url_prefix='/advanced', template_folder="../advanced_templates")

from . import home
from . import configuration
from . import strategy_optimizer
from . import matrix


from tentacles.Services.Interfaces.web_interface.advanced_controllers import configuration
from tentacles.Services.Interfaces.web_interface.advanced_controllers import home
from tentacles.Services.Interfaces.web_interface.advanced_controllers import matrix
from tentacles.Services.Interfaces.web_interface.advanced_controllers import strategy_optimizer
from tentacles.Services.Interfaces.web_interface.advanced_controllers import tentacles

from tentacles.Services.Interfaces.web_interface.advanced_controllers.configuration import (
    evaluator_config,
)

from tentacles.Services.Interfaces.web_interface.advanced_controllers.tentacles import (
    tentacle_packages,
)


__all__ = [
    "evaluator_config",
    "home",
    "matrix",
    "strategy_optimizer",
    "tentacles",
    "tentacle_packages",
]


