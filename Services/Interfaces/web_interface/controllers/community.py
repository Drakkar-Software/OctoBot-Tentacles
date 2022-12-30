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

import octobot_commons.authentication as authentication
import tentacles.Services.Interfaces.web_interface as web_interface
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models


@web_interface.server_instance.route("/community")
@login.login_required_when_activated
def community():
    authenticator = authentication.Authenticator.instance()
    logged_in_email = None
    use_preview = not authenticator.can_authenticate()
    try:
        models.wait_for_login_if_processing()
        logged_in_email = authenticator.get_logged_in_email()
    except (authentication.AuthenticationRequired, authentication.UnavailableError):
        pass
    except Exception as e:
        flask.flash(f"Error when contacting the community server: {e}", "error")
    if logged_in_email is None and not use_preview:
        return flask.redirect('community_login')
    tentacles_packages = models.get_account_tentacles_packages(authenticator) if logged_in_email else []
    default_image = flask.url_for('static', filename="img/community/tentacles_packages_previews/octobot.png")
    return flask.render_template(
        'community.html',
        use_preview=use_preview,
        preview_tentacles_packages=models.get_preview_tentacles_packages(flask.url_for),
        current_logged_in_email=logged_in_email,
        role=authenticator.user_account.supports.support_role,
        is_donor=bool(authenticator.user_account.supports.is_donor()),
        tentacles_packages=tentacles_packages,
        current_bots_stats=models.get_current_octobots_stats(),
        all_user_bots=models.get_all_user_bots(),
        selected_user_bot=models.get_selected_user_bot(),
        default_tentacles_package_image=default_image,
        can_logout=models.can_logout(),
        can_select_bot=models.can_select_bot(),
    )


@web_interface.server_instance.route("/community_metrics")
@login.login_required_when_activated
def community_metrics():
    can_get_metrics = models.can_get_community_metrics()
    display_metrics = models.get_community_metrics_to_display() if can_get_metrics else None
    return flask.render_template('community_metrics.html',
                                 can_get_metrics=can_get_metrics,
                                 community_metrics=display_metrics
                                 )
