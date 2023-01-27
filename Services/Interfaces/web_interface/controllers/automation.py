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

import octobot_commons.logging as commons_logging
import tentacles.Services.Interfaces.web_interface.util as util
import tentacles.Services.Interfaces.web_interface as web_interface
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models
import octobot.automation as bot_automation


@web_interface.server_instance.route("/automations", methods=["POST", "GET"])
@login.login_required_when_activated
def automations():
    if flask.request.method == 'POST':
        action = flask.request.args.get("action")
        success = True
        response = ""
        tentacle_name = bot_automation.Automation.get_name()
        tentacle_class = bot_automation.Automation
        restart = False
        if action == "update":
            request_data = flask.request.get_json()
            success, response = models.update_tentacle_config(
                tentacle_name,
                request_data,
                tentacle_class=tentacle_class
            )
            restart = True
        elif action == "factory_reset":
            # todo
            success, response = models.reset_config_to_default(tentacle_name, tentacle_class=tentacle_class)
            restart = True
        if restart:
            models.restart_global_automations()
        if success:
            return util.get_rest_reply(flask.jsonify(response))
        else:
            return util.get_rest_reply(response, 500)
    return flask.render_template('automations.html')


@web_interface.server_instance.route('/automations_edit_details')
@login.login_required_when_activated
def automations_edit_details():
    try:
        return util.get_rest_reply(
            models.get_tentacle_config_and_edit_display(
                bot_automation.Automation.get_name(),
                tentacle_class=bot_automation.Automation
            )
        )
    except Exception as e:
        commons_logging.get_logger("automations_edit_details").exception(e)
        return util.get_rest_reply(str(e), 500)
