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


@web_interface.server_instance.route("/")
@web_interface.server_instance.route("/home")
@login.login_required_when_activated
def home():
    if flask.request.args:
        accepted = flask.request.args.get("accept_terms") == "True"
        models.accept_terms(accepted)
    if models.accepted_terms():
        in_backtesting = models.get_in_backtesting_mode()
        return flask.render_template('index.html',
                                     watched_symbols=models.get_watched_symbols(),
                                     backtesting_mode=in_backtesting)
    else:
        return flask.redirect("/terms")
