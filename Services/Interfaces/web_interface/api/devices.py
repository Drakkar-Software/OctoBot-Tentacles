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

import octobot.community as community
import tentacles.Services.Interfaces.web_interface.api as api
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models


@api.api.route("/select_device", methods=['POST'])
@login.login_required_when_activated
def select_device():
    models.select_device(flask.request.get_json())
    device = models.get_selected_user_device()
    flask.flash(f"Selected {device['name']} device", "success")
    return flask.jsonify(device)


@api.api.route("/create_device", methods=['POST'])
@login.login_required_when_activated
def create_device():
    new_device_id = models.create_new_device()
    models.select_device(new_device_id)
    device = models.get_selected_user_device()
    flask.flash(f"Created and selected {device['name']} device", "success")
    return flask.jsonify(device)
