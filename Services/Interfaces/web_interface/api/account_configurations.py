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

import tentacles.Services.Interfaces.web_interface.api as api
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models


@api.api.route("/account_configurations", methods=['GET'])
@login.login_required_when_activated
def account_configurations():
    try:
        return flask.jsonify(models.get_account_configurations())
    except RuntimeError:
        return flask.jsonify([])


@api.api.route("/apply_account_configuration", methods=['POST'])
@login.login_required_when_activated
def apply_account_configuration():
    return flask.jsonify(models.apply_account_configuration(flask.request.get_json()["id"]))


@api.api.route("/new_account_configuration", methods=['POST'])
@login.login_required_when_activated
def new_account_configuration():
    request_data = flask.request.get_json()
    new_config = models.create_or_rename_account_configuration(
        request_data["name"]
    )
    return flask.jsonify(new_config)


@api.api.route("/rename_account_configuration", methods=['POST'])
@login.login_required_when_activated
def rename_account_configuration():
    request_data = flask.request.get_json()
    updated_config = models.create_or_rename_account_configuration(
        request_data["name"],
        request_data["id"]
    )
    return flask.jsonify(updated_config)


@api.api.route("/delete_account_configuration", methods=['POST'])
@login.login_required_when_activated
def delete_account_configuration():
    models.delete_account_configuration(flask.request.get_json()["id"])
    return flask.jsonify()
