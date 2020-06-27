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
from flask import render_template, request, jsonify, url_for

from octobot_commons.constants import CONFIG_CRYPTO_CURRENCIES
from octobot_services.interfaces.util.bot import get_edited_config
from octobot_trading.constants import CONFIG_EXCHANGES, CONFIG_TRADING, CONFIG_TRADER, CONFIG_SIMULATOR, \
    CONFIG_TRADER_REFERENCE_MARKET
from octobot_services.constants import CONFIG_CATEGORY_SERVICES
from octobot_services.constants import CONFIG_CATEGORY_NOTIFICATION
from tentacles.Services.Interfaces.web_interface.constants import GLOBAL_CONFIG_KEY, EVALUATOR_CONFIG_KEY, \
    TRADING_CONFIG_KEY, DEACTIVATE_OTHERS, TENTACLES_CONFIG_KEY
from tentacles.Services.Interfaces.web_interface import server_instance
from tentacles.Services.Interfaces.web_interface.login.web_login_manager import login_required_when_activated
from tentacles.Services.Interfaces.web_interface.models.commands import schedule_delayed_command, restart_bot
from tentacles.Services.Interfaces.web_interface.models.configuration import get_strategy_config, \
    get_services_list, get_notifiers_list, get_symbol_list, update_global_config, get_all_symbols_dict, \
    get_tested_exchange_list, get_simulated_exchange_list, get_other_exchange_list, \
    manage_metrics, get_tentacle_from_string, update_tentacle_config, reset_config_to_default, \
    get_evaluator_detailed_config, REQUIREMENTS_KEY, get_config_activated_trading_mode, \
    update_tentacles_activation_config, get_evaluators_tentacles_startup_activation, \
    get_trading_tentacles_startup_activation, get_tentacle_config, \
    get_tentacle_config_schema, get_tentacles_activation_desc_by_group
from tentacles.Services.Interfaces.web_interface.models.backtesting import get_data_files_with_description
from tentacles.Services.Interfaces.web_interface.util.flask_util import get_rest_reply
from octobot_backtesting.api.backtesting import is_backtesting_enabled
from octobot_services.interfaces.util.trader import has_real_and_or_simulated_traders


@server_instance.route('/config', methods=['GET', 'POST'])
@login_required_when_activated
def config():
    if request.method == 'POST':
        request_data = request.get_json()
        success = True
        response = ""

        if request_data:

            # update trading config if required
            if TRADING_CONFIG_KEY in request_data and request_data[TRADING_CONFIG_KEY]:
                success = success and update_tentacles_activation_config(request_data[TRADING_CONFIG_KEY])
            else:
                request_data[TRADING_CONFIG_KEY] = ""

            # update tentacles config if required
            if TENTACLES_CONFIG_KEY in request_data and request_data[TENTACLES_CONFIG_KEY]:
                success = success and update_tentacles_activation_config(request_data[TENTACLES_CONFIG_KEY])
            else:
                request_data[TENTACLES_CONFIG_KEY] = ""

            # update evaluator config if required
            if EVALUATOR_CONFIG_KEY in request_data and request_data[EVALUATOR_CONFIG_KEY]:
                deactivate_others = False
                if DEACTIVATE_OTHERS in request_data:
                    deactivate_others = request_data[DEACTIVATE_OTHERS]
                success = success and update_tentacles_activation_config(request_data[EVALUATOR_CONFIG_KEY],
                                                                         deactivate_others)
            else:
                request_data[EVALUATOR_CONFIG_KEY] = ""

            # remove elements from global config if any to remove
            removed_elements_key = "removed_elements"
            if removed_elements_key in request_data and request_data[removed_elements_key]:
                success = success and update_global_config(request_data[removed_elements_key], delete=True)
            else:
                request_data[removed_elements_key] = ""

            # update global config if required
            if GLOBAL_CONFIG_KEY in request_data and request_data[GLOBAL_CONFIG_KEY]:
                success = update_global_config(request_data[GLOBAL_CONFIG_KEY])
            else:
                request_data[GLOBAL_CONFIG_KEY] = ""

            response = {
                "evaluator_updated_config": request_data[EVALUATOR_CONFIG_KEY],
                "trading_updated_config": request_data[TRADING_CONFIG_KEY],
                "tentacle_updated_config": request_data[TENTACLES_CONFIG_KEY],
                "global_updated_config": request_data[GLOBAL_CONFIG_KEY],
                removed_elements_key: request_data[removed_elements_key]
            }

        if success:
            if request_data.get("restart_after_save", False):
                schedule_delayed_command(restart_bot)
            return get_rest_reply(jsonify(response))
        else:
            return get_rest_reply('{"update": "ko"}', 500)
    else:
        media_url = url_for("tentacle_media", _external=True)
        display_config = get_edited_config()

        # service lists
        service_list = get_services_list()
        notifiers_list = get_notifiers_list()

        return render_template('config.html',

                               config_exchanges=display_config[CONFIG_EXCHANGES],
                               config_trading=display_config[CONFIG_TRADING],
                               config_trader=display_config[CONFIG_TRADER],
                               config_trader_simulator=display_config[CONFIG_SIMULATOR],
                               config_notifications=display_config[CONFIG_CATEGORY_NOTIFICATION],
                               config_services=display_config[CONFIG_CATEGORY_SERVICES],
                               config_symbols=display_config[CONFIG_CRYPTO_CURRENCIES],
                               config_reference_market=display_config[CONFIG_TRADING][CONFIG_TRADER_REFERENCE_MARKET],

                               real_trader_activated=has_real_and_or_simulated_traders()[0],

                               ccxt_tested_exchanges=get_tested_exchange_list(),
                               ccxt_simulated_tested_exchanges=get_simulated_exchange_list(),
                               ccxt_other_exchanges=sorted(get_other_exchange_list()),
                               services_list=service_list,
                               notifiers_list=notifiers_list,
                               symbol_list=sorted(get_symbol_list([exchange
                                                                   for exchange in display_config[CONFIG_EXCHANGES]])),
                               full_symbol_list=get_all_symbols_dict(),
                               strategy_config=get_strategy_config(media_url),
                               evaluator_startup_config=get_evaluators_tentacles_startup_activation(),
                               trading_startup_config=get_trading_tentacles_startup_activation(),

                               in_backtesting=is_backtesting_enabled(display_config),

                               config_tentacles_by_group=get_tentacles_activation_desc_by_group(media_url)
                               )


@server_instance.route('/config_tentacle', methods=['GET', 'POST'])
@login_required_when_activated
def config_tentacle():
    if request.method == 'POST':
        tentacle_name = request.args.get("name")
        action = request.args.get("action")
        success = True
        response = ""
        if action == "update":
            request_data = request.get_json()
            success, response = update_tentacle_config(tentacle_name, request_data)
        elif action == "factory_reset":
            success, response = reset_config_to_default(tentacle_name)
        if success:
            return get_rest_reply(jsonify(response))
        else:
            return get_rest_reply(response, 500)
    else:
        if request.args:
            tentacle_name = request.args.get("name")
            media_url = url_for("tentacle_media", _external=True)
            tentacle_class, tentacle_type, tentacle_desc = get_tentacle_from_string(tentacle_name, media_url)
            evaluator_config = get_evaluator_detailed_config(media_url) if tentacle_type == "strategy" and \
                tentacle_desc[REQUIREMENTS_KEY] == ["*"] else None
            strategy_config = get_strategy_config(media_url) if tentacle_type == "trading mode" and \
                len(tentacle_desc[REQUIREMENTS_KEY]) > 1 else None
            evaluator_startup_config = get_evaluators_tentacles_startup_activation() \
                if evaluator_config or strategy_config else None
            return render_template('config_tentacle.html',
                                   name=tentacle_name,
                                   tentacle_type=tentacle_type,
                                   tentacle_class=tentacle_class,
                                   tentacle_desc=tentacle_desc,
                                   evaluator_startup_config=evaluator_startup_config,
                                   strategy_config=strategy_config,
                                   evaluator_config=evaluator_config,
                                   activated_trading_mode=get_config_activated_trading_mode(),
                                   data_files=get_data_files_with_description())
        else:
            return render_template('config_tentacle.html')


@server_instance.route('/metrics_settings', methods=['POST'])
@login_required_when_activated
def metrics_settings():
    enable_metrics = request.get_json()
    return get_rest_reply(jsonify(manage_metrics(enable_metrics)))


@server_instance.route('/config_actions', methods=['POST'])
@login_required_when_activated
def config_actions():
    # action = request.args.get("action")
    return get_rest_reply("No specified action.", code=500)


@server_instance.template_filter()
def is_dict(value):
    return isinstance(value, dict)


@server_instance.template_filter()
def is_list(value):
    return isinstance(value, list)


@server_instance.template_filter()
def is_bool(value):
    return isinstance(value, bool)


@server_instance.context_processor
def tentacles_utils():
    def get_tentacle_config_file_content(tentacle_class):
        return get_tentacle_config(tentacle_class)

    def get_tentacle_config_schema_content(tentacle_class):
        return get_tentacle_config_schema(tentacle_class)

    return dict(get_tentacle_config_file_content=get_tentacle_config_file_content,
                get_tentacle_config_schema_content=get_tentacle_config_schema_content)
