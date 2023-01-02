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
import octobot_commons.constants as commons_constants
import tentacles.Services.Interfaces.web_interface as web_interface
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models
import tentacles.Services.Interfaces.web_interface.controllers.community_authentication as community_authentication
import tentacles.Services.Interfaces.web_interface.flask_util as flask_util
import octobot_services.interfaces.util as interfaces_util


@web_interface.server_instance.route("/profiles_selector")
@login.login_required_when_activated
def profiles_selector():
    reboot = flask.request.args.get("reboot", False)
    reboot_delay = 2
    profiles = models.get_profiles()
    current_profile = models.get_current_profile()
    display_config = interfaces_util.get_edited_config()

    config_exchanges = display_config[commons_constants.CONFIG_EXCHANGES]

    enabled_exchanges = [
        exchange
        for exchange, exchange_config in config_exchanges.items()
        if exchange_config.get(commons_constants.CONFIG_ENABLED_OPTION, True)
    ]
    media_url = flask.url_for("tentacle_media", _external=True)
    missing_tentacles = set()

    models.wait_for_login_if_processing()
    logged_in_email = None
    form = community_authentication.CommunityLoginForm(flask.request.form) \
        if flask.request.form else community_authentication.CommunityLoginForm()
    try:
        authenticator = authentication.Authenticator.instance()
        logged_in_email = authenticator.get_logged_in_email()
    except (authentication.AuthenticationRequired, authentication.UnavailableError):
        pass

    display_intro = flask_util.BrowsingDataProvider.instance().get_and_unset_is_first_display(
        flask_util.BrowsingDataProvider.PROFILE_SELECTOR
    )
    return_val = flask.render_template(
        'profiles_selector.html',
        read_only=True,
        waiting_reboot=reboot,
        display_intro=display_intro,

        current_logged_in_email=logged_in_email,
        selected_user_bot=models.get_selected_user_bot(),
        can_logout=models.can_logout(),
        form=form,

        current_profile=current_profile,
        profiles=profiles.values(),
        profiles_tentacles_details=models.get_profiles_tentacles_details(profiles),

        evaluator_config=models.get_evaluator_detailed_config(media_url, missing_tentacles),
        strategy_config=models.get_strategy_config(media_url, missing_tentacles),

        config_exchanges=config_exchanges,

        symbol_list=sorted(models.get_symbol_list(enabled_exchanges or config_exchanges)),
    )
    if reboot and not models.is_rebooting():
        # schedule reboot now that the page render has been computed
        models.restart_bot(delay=reboot_delay)
    return return_val
