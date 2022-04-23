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

import octobot_services.interfaces.util as interfaces_util
import tentacles.Services.Interfaces.web_interface.api as api
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models
import tentacles.Services.Interfaces.web_interface.util as util


@api.api.route('/get_config_currency', methods=["GET"])
@login.login_required_when_activated
def get_config_currency():
    return flask.jsonify(models.format_config_symbols(interfaces_util.get_edited_config()))


@api.api.route('/set_config_currency', methods=["POST"])
@login.login_required_when_activated
def set_config_currency():
    request_data = flask.request.get_json()
    success, reply = models.update_config_currencies(request_data["currencies"],
                        replace=(request_data.get("action", "update") == "replace"))
    return util.get_rest_reply(flask.jsonify(reply)) if success else util.get_rest_reply(reply, 500)


@api.api.route('/change_reference_market_on_config_currencies', methods=["POST"])
@login.login_required_when_activated
def change_reference_market_on_config_currencies():
    request_data = flask.request.get_json()
    success, reply = models.change_reference_market_on_config_currencies(request_data["old_base_currency"],
                                                                         request_data["new_base_currency"])
    return util.get_rest_reply(flask.jsonify(reply)) if success else util.get_rest_reply(reply, 500)


@api.api.route('/start_copy_trading', methods=["POST"])
@login.login_required_when_activated
def start_copy_trading():
    try:
        copy_id = flask.request.get_json()["copy_id"]
        profile_id = flask.request.get_json()["profile_id"]
        if models.get_current_profile().profile_id != profile_id:
            models.select_profile(profile_id)
        response = f"{models.get_current_profile().name} profile selected"
        success, config_resp = models.update_copied_trading_id(copy_id)
        response = f"{response}, {config_resp}"
        return util.get_rest_reply(flask.jsonify(response)) if success else util.get_rest_reply(response, 500)
    except Exception as e:
        return util.get_rest_reply(f"Unexpected error : {e}", 500)
