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

from flask import render_template, request, jsonify, url_for

from tentacles.Interfaces.web_interface.constants import EVALUATOR_CONFIG_KEY
from . import advanced
from tentacles.Interfaces.web_interface.models.configuration import get_evaluator_detailed_config, \
    update_tentacles_activation_config, get_tentacles_startup_activation
from tentacles.Interfaces.web_interface.util.flask_util import get_rest_reply


@advanced.route("/evaluator_config")
@advanced.route('/evaluator_config', methods=['GET', 'POST'])
def evaluator_config():
    if request.method == 'POST':
        request_data = request.get_json()
        success = True
        response = ""

        if request_data:
            # update evaluator config if required
            if EVALUATOR_CONFIG_KEY in request_data and request_data[EVALUATOR_CONFIG_KEY]:
                success = success and update_tentacles_activation_config(request_data[EVALUATOR_CONFIG_KEY])

            response = {
                "evaluator_updated_config": request_data[EVALUATOR_CONFIG_KEY]
            }

        if success:
            return get_rest_reply(jsonify(response))
        else:
            return get_rest_reply('{"update": "ko"}', 500)
    else:
        media_url = url_for("tentacle_media", _external=True)
        return render_template('advanced_evaluator_config.html',

                               evaluator_config=get_evaluator_detailed_config(media_url),
                               evaluator_startup_config=get_tentacles_startup_activation()
                               )
