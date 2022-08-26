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

import octobot_commons.logging as bot_logging
import octobot.constants as constants
import octobot.disclaimer as disclaimer
import tentacles.Services.Interfaces.web_interface as web_interface
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models

logger = bot_logging.get_logger("ServerInstance Controller")


@web_interface.server_instance.route("/about")
@login.login_required_when_activated
def about():
    return flask.render_template('about.html',
                                 octobot_beta_program_form_url=constants.OCTOBOT_BETA_PROGRAM_FORM_URL,
                                 beta_env_enabled_in_config=models.get_beta_env_enabled_in_config(),
                                 metrics_enabled=models.get_metrics_enabled(),
                                 disclaimer=disclaimer.DISCLAIMER)


@web_interface.server_instance.route('/commands/<cmd>', methods=['GET', 'POST'])
@login.login_required_when_activated
def commands(cmd=None):
    if cmd == "restart":
        models.restart_bot()
        return flask.jsonify("Success")

    elif cmd == "stop":
        models.stop_bot()
        return flask.jsonify("Success")

    elif cmd == "update":
        models.schedule_delayed_command(models.update_bot())
        return flask.jsonify("Update started")

    else:
        raise RuntimeError("Unknown command")
