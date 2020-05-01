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
from flask import render_template, request

from tentacles.Services.Interfaces.web_interface import server_instance
from tentacles.Services.Interfaces.web_interface.util.flask_util import get_rest_reply

APP_JSON_CONTENT_TYPE = "application/json"


@server_instance.errorhandler(404)
def not_found(_):
    if request.content_type == APP_JSON_CONTENT_TYPE:
        return get_rest_reply("We are sorry, but this doesn't exist", 404)
    return render_template("404.html")


@server_instance.errorhandler(500)
def internal_error(_):
    if request.content_type == APP_JSON_CONTENT_TYPE:
        return get_rest_reply("We are sorry, but an unexpected error occurred", 500)
    return render_template("500.html")
