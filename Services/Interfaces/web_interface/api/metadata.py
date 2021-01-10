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

import tentacles.Services.Interfaces.web_interface.api as api
import octobot_services.constants as service_constants
import octobot_commons.external_resources_manager as external_resources_manager
import octobot_services.interfaces as interfaces


@api.api.route("/version")
def version():
    return json.dumps(f"{interfaces.AbstractInterface.project_name} {interfaces.AbstractInterface.project_version}")


@api.api.route("/user_feedback")
def user_feedback():
    return json.dumps(external_resources_manager.get_external_resource(
        service_constants.EXTERNAL_RESOURCE_CURRENT_USER_FORM,
        catch_exception=True))


@api.api.route("/announcements")
def announcements():
    return json.dumps(external_resources_manager.get_external_resource(
        service_constants.EXTERNAL_RESOURCE_PUBLIC_ANNOUNCEMENTS,
        catch_exception=True))
