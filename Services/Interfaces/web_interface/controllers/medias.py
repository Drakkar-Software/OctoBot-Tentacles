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
from flask import send_from_directory

from tentacles.Services.Interfaces.web_interface import server_instance
from tentacles.Services.Interfaces.web_interface.login.web_login_manager import login_required_when_activated
from tentacles.Services.Interfaces.web_interface.models.medias import is_valid_tentacle_image_path


@server_instance.route('/tentacle_media')
@server_instance.route('/tentacle_media/<path:path>')
@login_required_when_activated
def tentacle_media(path=None):
    # images
    if is_valid_tentacle_image_path(path):
        # reference point is the web interface directory: use OctoBot root folder as a reference
        return send_from_directory("../../../..", path)
