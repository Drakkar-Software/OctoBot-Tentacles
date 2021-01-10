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

import tentacles.Services.Interfaces.web_interface as web_interface
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models


@web_interface.server_instance.route('/tentacle_media')
@web_interface.server_instance.route('/tentacle_media/<path:path>')
@login.login_required_when_activated
def tentacle_media(path=None):
    # images
    if models.is_valid_tentacle_image_path(path):
        # reference point is the web interface directory: use OctoBot root folder as a reference
        return flask.send_from_directory("../../../..", path)


@web_interface.server_instance.route('/exchange_logo/<name>')
@login.login_required_when_activated
def exchange_logo(name):
    return flask.jsonify(models.get_exchange_logo(name))
