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
import werkzeug
import os
from datetime import datetime

import octobot_commons.constants as commons_constants
import octobot_services.constants as services_constants
import tentacles.Services.Interfaces.web_interface.constants as constants
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface as web_interface
import tentacles.Services.Interfaces.web_interface.models as models
import tentacles.Services.Interfaces.web_interface.util as util
import tentacles.Services.Interfaces.web_interface.flask_util as flask_util
import octobot_backtesting.api as backtesting_api
import octobot_services.interfaces.util as interfaces_util


@web_interface.server_instance.route('/profile')
@login.login_required_when_activated
def profile():
    selected_profile = flask.request.args.get("select", None)
    if selected_profile is not None and selected_profile != models.get_current_profile().profile_id:
        models.select_profile(selected_profile)
        current_profile = models.get_current_profile()
        flask.flash(f"Switched to {current_profile.name} profile.", "success")
    else:
        current_profile = models.get_current_profile()
    media_url = flask.url_for("tentacle_media", _external=True)
    display_config = interfaces_util.get_edited_config()

    missing_tentacles = set()
    profiles = models.get_profiles()
    config_exchanges = display_config[commons_constants.CONFIG_EXCHANGES]

    return flask.render_template('profile.html',
                                 current_profile=current_profile,
                                 profiles=profiles,
                                 profiles_activated_tentacles=models.get_profiles_activated_tentacles(profiles),

                                 config_exchanges=config_exchanges,
                                 config_trading=display_config[commons_constants.CONFIG_TRADING],
                                 config_trader=display_config[commons_constants.CONFIG_TRADER],
                                 config_trader_simulator=display_config[commons_constants.CONFIG_SIMULATOR],
                                 config_symbols=models.format_config_symbols(display_config),
                                 config_reference_market=display_config[commons_constants.CONFIG_TRADING][
                                     commons_constants.CONFIG_TRADER_REFERENCE_MARKET],

                                 real_trader_activated=interfaces_util.has_real_and_or_simulated_traders()[0],

                                 symbol_list=sorted(models.get_symbol_list([exchange
                                                                            for exchange in display_config[
                                                                                commons_constants.CONFIG_EXCHANGES]])),
                                 full_symbol_list=models.get_all_symbols_dict(),
                                 evaluator_config=models.get_evaluator_detailed_config(media_url, missing_tentacles),
                                 strategy_config=models.get_strategy_config(media_url, missing_tentacles),
                                 evaluator_startup_config=models.get_evaluators_tentacles_startup_activation(),
                                 trading_startup_config=models.get_trading_tentacles_startup_activation(),
                                 missing_tentacles=missing_tentacles,

                                 in_backtesting=backtesting_api.is_backtesting_enabled(display_config),

                                 config_tentacles_by_group=models.get_tentacles_activation_desc_by_group(media_url,
                                                                                                         missing_tentacles),

                                 exchanges_details=models.get_exchanges_details(config_exchanges)
                                 )


@web_interface.server_instance.route('/profiles_management/<action>', methods=["POST", "GET"])
@login.login_required_when_activated
def profiles_management(action):
    if action == "update":
        data = flask.request.get_json()
        models.update_profile(flask.request.get_json()["id"], data)
        return util.get_rest_reply(flask.jsonify(data))
    if action == "duplicate":
        profile_id = flask.request.args.get("profile_id")
        models.duplicate_and_select_profile(profile_id)
        flask.flash(f"New profile successfully created and selected.", "success")
        return util.get_rest_reply(flask.jsonify("Profile created"))
    if action == "remove":
        data = flask.request.get_json()
        to_remove_id = data["id"]
        removed_profile, err = models.remove_profile(to_remove_id)
        if err is not None:
            return util.get_rest_reply(flask.jsonify(str(err)), code=400)
        flask.flash(f"{removed_profile.name} profile removed.", "success")
        return util.get_rest_reply(flask.jsonify("Profile created"))
    if action == "import":
        file = flask.request.files['file']
        name = werkzeug.utils.secure_filename(flask.request.files['file'].filename)
        models.import_profile(file, name)
        flask.flash(f"{name} profile successfully imported.", "success")
        return flask.redirect(flask.url_for('profile'))
    if action == "export":
        profile_id = flask.request.args.get("profile_id")
        temp_file = os.path.abspath("profile")
        file_path = models.export_profile(profile_id, temp_file)
        name = models.get_profile_name(profile_id)
        return flask_util.send_and_remove_file(file_path, f"{name}_{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip")


@web_interface.server_instance.route('/accounts')
@login.login_required_when_activated
def accounts():
    display_config = interfaces_util.get_edited_config()

    # service lists
    service_list = models.get_services_list()
    notifiers_list = models.get_notifiers_list()

    config_exchanges = display_config[commons_constants.CONFIG_EXCHANGES]
    return flask.render_template('accounts.html',
                                 ccxt_tested_exchanges=models.get_tested_exchange_list(),
                                 ccxt_simulated_tested_exchanges=models.get_simulated_exchange_list(),
                                 ccxt_other_exchanges=sorted(models.get_other_exchange_list()),
                                 exchanges_details=models.get_exchanges_details(config_exchanges),

                                 config_exchanges=config_exchanges,
                                 config_notifications=display_config[
                                     services_constants.CONFIG_CATEGORY_NOTIFICATION],
                                 config_services=display_config[services_constants.CONFIG_CATEGORY_SERVICES],

                                 services_list=service_list,
                                 notifiers_list=notifiers_list,
                                 )


@web_interface.server_instance.route('/config', methods=['POST'])
@login.login_required_when_activated
def config():
    request_data = flask.request.get_json()
    success = True
    response = ""

    if request_data:

        # update trading config if required
        if constants.TRADING_CONFIG_KEY in request_data and request_data[constants.TRADING_CONFIG_KEY]:
            success = success and models.update_tentacles_activation_config(
                request_data[constants.TRADING_CONFIG_KEY])
        else:
            request_data[constants.TRADING_CONFIG_KEY] = ""

        # update tentacles config if required
        if constants.TENTACLES_CONFIG_KEY in request_data and request_data[constants.TENTACLES_CONFIG_KEY]:
            success = success and models.update_tentacles_activation_config(
                request_data[constants.TENTACLES_CONFIG_KEY])
        else:
            request_data[constants.TENTACLES_CONFIG_KEY] = ""

        # update evaluator config if required
        if constants.EVALUATOR_CONFIG_KEY in request_data and request_data[constants.EVALUATOR_CONFIG_KEY]:
            deactivate_others = False
            if constants.DEACTIVATE_OTHERS in request_data:
                deactivate_others = request_data[constants.DEACTIVATE_OTHERS]
            success = success and models.update_tentacles_activation_config(
                request_data[constants.EVALUATOR_CONFIG_KEY],
                deactivate_others)
        else:
            request_data[constants.EVALUATOR_CONFIG_KEY] = ""

        # remove elements from global config if any to remove
        removed_elements_key = "removed_elements"
        if removed_elements_key in request_data and request_data[removed_elements_key]:
            success = success and models.update_global_config(request_data[removed_elements_key], delete=True)
        else:
            request_data[removed_elements_key] = ""

        # update global config if required
        if constants.GLOBAL_CONFIG_KEY in request_data and request_data[constants.GLOBAL_CONFIG_KEY]:
            success = models.update_global_config(request_data[constants.GLOBAL_CONFIG_KEY])
        else:
            request_data[constants.GLOBAL_CONFIG_KEY] = ""

        response = {
            "evaluator_updated_config": request_data[constants.EVALUATOR_CONFIG_KEY],
            "trading_updated_config": request_data[constants.TRADING_CONFIG_KEY],
            "tentacle_updated_config": request_data[constants.TENTACLES_CONFIG_KEY],
            "global_updated_config": request_data[constants.GLOBAL_CONFIG_KEY],
            removed_elements_key: request_data[removed_elements_key]
        }

    if success:
        if request_data.get("restart_after_save", False):
            models.schedule_delayed_command(models.restart_bot)
        return util.get_rest_reply(flask.jsonify(response))
    else:
        return util.get_rest_reply('{"update": "ko"}', 500)


@web_interface.server_instance.route('/config_tentacle', methods=['GET', 'POST'])
@login.login_required_when_activated
def config_tentacle():
    if flask.request.method == 'POST':
        tentacle_name = flask.request.args.get("name")
        action = flask.request.args.get("action")
        success = True
        response = ""
        if action == "update":
            request_data = flask.request.get_json()
            success, response = models.update_tentacle_config(tentacle_name, request_data)
        elif action == "factory_reset":
            success, response = models.reset_config_to_default(tentacle_name)
        if success:
            return util.get_rest_reply(flask.jsonify(response))
        else:
            return util.get_rest_reply(response, 500)
    else:
        if flask.request.args:
            tentacle_name = flask.request.args.get("name")
            missing_tentacles = set()
            media_url = flask.url_for("tentacle_media", _external=True)
            tentacle_class, tentacle_type, tentacle_desc = models.get_tentacle_from_string(tentacle_name, media_url)
            evaluator_config = models.get_evaluator_detailed_config(media_url,
                                                                    missing_tentacles) if tentacle_type == "strategy" and \
                                                                                          tentacle_desc[
                                                                                              models.REQUIREMENTS_KEY] == [
                                                                                              "*"] else None
            strategy_config = models.get_strategy_config(media_url,
                                                         missing_tentacles) if tentacle_type == "trading mode" and \
                                                                               len(tentacle_desc[
                                                                                       models.REQUIREMENTS_KEY]) > 1 else None
            evaluator_startup_config = models.get_evaluators_tentacles_startup_activation() \
                if evaluator_config or strategy_config else None
            tentacle_commands = models.get_tentacle_user_commands(tentacle_class)
            return flask.render_template('config_tentacle.html',
                                         name=tentacle_name,
                                         tentacle_type=tentacle_type,
                                         tentacle_class=tentacle_class,
                                         tentacle_desc=tentacle_desc,
                                         evaluator_startup_config=evaluator_startup_config,
                                         strategy_config=strategy_config,
                                         evaluator_config=evaluator_config,
                                         activated_trading_mode=models.get_config_activated_trading_mode(),
                                         data_files=models.get_data_files_with_description(),
                                         missing_tentacles=missing_tentacles,
                                         user_commands=tentacle_commands,
                                         current_profile=models.get_current_profile()
                                         )
        else:
            return flask.render_template('config_tentacle.html')


@web_interface.server_instance.route('/metrics_settings', methods=['POST'])
@login.login_required_when_activated
def metrics_settings():
    enable_metrics = flask.request.get_json()
    return util.get_rest_reply(flask.jsonify(models.manage_metrics(enable_metrics)))


@web_interface.server_instance.route('/config_actions', methods=['POST'])
@login.login_required_when_activated
def config_actions():
    # action = flask.request.args.get("action")
    return util.get_rest_reply("No specified action.", code=500)


@web_interface.server_instance.route('/account_configurations')
@login.login_required_when_activated
def account_configurations():
    configurations = []
    try:
        configurations = models.get_account_configurations()
    except RuntimeError:
        pass
    if models.is_logged_in_on_community():
        return flask.render_template('account_configurations.html',
                                     configurations=configurations,
                                     current_configuration=models.get_current_account_configuration())
    return flask.redirect('community_login?next=account_configuration')
