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
import os

import tentacles.Services.Interfaces.web_interface as web_interface
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models
import tentacles.Services.Interfaces.web_interface.flask_util as flask_util


@web_interface.server_instance.route("/logs")
@login.login_required_when_activated
def logs():
    web_interface.flush_errors_count()
    return flask.render_template("logs.html",
                                 logs=web_interface.get_logs())


@web_interface.server_instance.route("/export_logs")
@login.login_required_when_activated
def export_logs():
    temp_file = os.path.abspath("exported_logs")
    temp_file_with_ext = f"{temp_file}.{models.LOG_EXPORT_FORMAT}"
    if os.path.isdir(temp_file_with_ext):
        raise RuntimeError(f"To be able to export logs, please remove or rename the {temp_file_with_ext} directory")
    elif os.path.isfile(temp_file_with_ext):
        os.remove(temp_file_with_ext)
    file_path = models.export_logs(temp_file)
    return flask_util.send_and_remove_file(file_path, "logs_export.zip")
