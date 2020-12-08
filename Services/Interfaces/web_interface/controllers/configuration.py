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

import octobot_commons.constants as commons_constants
import octobot_services.constants as services_constants
import tentacles.Services.Interfaces.web_interface.constants as constants
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface as web_interface
import tentacles.Services.Interfaces.web_interface.models as models
import tentacles.Services.Interfaces.web_interface.util as util
import octobot_backtesting.api as backtesting_api
import octobot_services.interfaces.util as interfaces_util


@web_interface.server_instance.route('/config', methods=['GET', 'POST'])
@login.login_required_when_activated
def config():
    if flask.request.method == 'POST':
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
    else:
        media_url = flask.url_for("tentacle_media", _external=True)
        display_config = interfaces_util.get_edited_config()

        # service lists
        service_list = models.get_services_list()
        notifiers_list = models.get_notifiers_list()

        return flask.render_template('config.html',

                                     config_exchanges=display_config[commons_constants.CONFIG_EXCHANGES],
                                     config_trading=display_config[commons_constants.CONFIG_TRADING],
                                     config_trader=display_config[commons_constants.CONFIG_TRADER],
                                     config_trader_simulator=display_config[commons_constants.CONFIG_SIMULATOR],
                                     config_notifications=display_config[
                                         services_constants.CONFIG_CATEGORY_NOTIFICATION],
                                     config_services=display_config[services_constants.CONFIG_CATEGORY_SERVICES],
                                     config_symbols=models.format_config_symbols(display_config),
                                     config_reference_market=display_config[commons_constants.CONFIG_TRADING][
                                         commons_constants.CONFIG_TRADER_REFERENCE_MARKET],

                                     real_trader_activated=interfaces_util.has_real_and_or_simulated_traders()[0],

                                     ccxt_tested_exchanges=models.get_tested_exchange_list(),
                                     ccxt_simulated_tested_exchanges=models.get_simulated_exchange_list(),
                                     ccxt_other_exchanges=sorted(models.get_other_exchange_list()),
                                     services_list=service_list,
                                     notifiers_list=notifiers_list,
                                     symbol_list=sorted(models.get_symbol_list([exchange
                                                                                for exchange in display_config[
                                                                                    commons_constants.CONFIG_EXCHANGES]])),
                                     full_symbol_list=models.get_all_symbols_dict(),
                                     strategy_config=models.get_strategy_config(media_url),
                                     evaluator_startup_config=models.get_evaluators_tentacles_startup_activation(),
                                     trading_startup_config=models.get_trading_tentacles_startup_activation(),

                                     in_backtesting=backtesting_api.is_backtesting_enabled(display_config),

                                     config_tentacles_by_group=models.get_tentacles_activation_desc_by_group(media_url)
                                     )


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
            media_url = flask.url_for("tentacle_media", _external=True)
            tentacle_class, tentacle_type, tentacle_desc = models.get_tentacle_from_string(tentacle_name, media_url)
            evaluator_config = models.get_evaluator_detailed_config(media_url) if tentacle_type == "strategy" and \
                                                                                  tentacle_desc[
                                                                                      models.REQUIREMENTS_KEY] == [
                                                                                      "*"] else None
            strategy_config = models.get_strategy_config(media_url) if tentacle_type == "trading mode" and \
                                                                       len(tentacle_desc[
                                                                               models.REQUIREMENTS_KEY]) > 1 else None
            evaluator_startup_config = models.get_evaluators_tentacles_startup_activation() \
                if evaluator_config or strategy_config else None
            return flask.render_template('config_tentacle.html',
                                         name=tentacle_name,
                                         tentacle_type=tentacle_type,
                                         tentacle_class=tentacle_class,
                                         tentacle_desc=tentacle_desc,
                                         evaluator_startup_config=evaluator_startup_config,
                                         strategy_config=strategy_config,
                                         evaluator_config=evaluator_config,
                                         activated_trading_mode=models.get_config_activated_trading_mode(),
                                         data_files=models.get_data_files_with_description())
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
