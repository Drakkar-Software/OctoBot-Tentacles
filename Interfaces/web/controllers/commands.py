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
from copy import copy
from flask import render_template, jsonify

from config.disclaimer import DISCLAIMER
from octobot_interfaces.util.bot import get_bot
from tentacles.Interfaces.web import server_instance, get_notifications, flush_notifications, get_errors_count
# from tools.commands import Commands
from tentacles.Interfaces.web.models.configuration import get_metrics_enabled
from tools.commands import stop_bot, restart_bot

logger = get_logger("ServerInstance Controller")


@server_instance.route("/commands")
@server_instance.route('/commands/<cmd>', methods=['GET', 'POST'])
def commands(cmd=None):
    if cmd == "restart":
        restart_bot()
        return jsonify("Success")

    elif cmd == "stop":
        stop_bot(get_bot())
        return jsonify("Success")

    return render_template('commands.html',
                           cmd=cmd,
                           metrics_enabled=get_metrics_enabled(),
                           disclaimer=DISCLAIMER)


@server_instance.route("/update")
def update():
    update_data = {
        "notifications": copy(get_notifications()),
        "errors_count": get_errors_count()
    }
    flush_notifications()
    return jsonify(update_data)
