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

from octobot_commons.logging.logging_util import get_logger
from flask import render_template, jsonify

from octobot.disclaimer import DISCLAIMER
from octobot_interfaces.util.bot import get_bot_api
from tentacles.Interfaces.web_interface import server_instance
from tentacles.Interfaces.web_interface.models.configuration import get_metrics_enabled

logger = get_logger("ServerInstance Controller")


@server_instance.route("/commands")
@server_instance.route('/commands/<cmd>', methods=['GET', 'POST'])
def commands(cmd=None):
    if cmd == "restart":
        get_bot_api().restart_bot()
        return jsonify("Success")

    elif cmd == "stop":
        get_bot_api().stop_bot()
        return jsonify("Success")

    return render_template('commands.html',
                           cmd=cmd,
                           metrics_enabled=get_metrics_enabled(),
                           disclaimer=DISCLAIMER)
