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
import json
import flask_cors

import octobot.api as octobot_api
import octobot.constants as constants
import octobot_services.interfaces as interfaces
import tentacles.Services.Interfaces.web_interface.api as api
import octobot_commons.timestamp_util as timestamp_util


@api.api.route("/ping")
@flask_cors.cross_origin()
def ping():
    start_time = interfaces.get_bot_api().get_start_time()
    return json.dumps(
        f"Running since {timestamp_util.convert_timestamp_to_datetime(start_time, '%Y-%m-%d %H:%M:%S')}."
    )


@api.api.route("/version")
def version():
    return json.dumps(f"{interfaces.AbstractInterface.project_name} {interfaces.AbstractInterface.project_version}")


@api.api.route("/upgrade_version")
def upgrade_version():
    async def fetch_upgrade_version():
        updater = octobot_api.get_updater()
        return await updater.get_latest_version() if updater and await updater.should_be_updated() else None

    return json.dumps(interfaces.run_in_bot_async_executor(fetch_upgrade_version()))


@api.api.route("/user_feedback")
def user_feedback():
    return json.dumps(constants.OCTOBOT_FEEDBACK_FORM_URL)


@api.api.route("/announcements")
def announcements():
    return ""
    # return json.dumps("external_resources_manager.get_external_resource(
    #     service_constants.EXTERNAL_RESOURCE_PUBLIC_ANNOUNCEMENTS,
    #     catch_exception=True)")
