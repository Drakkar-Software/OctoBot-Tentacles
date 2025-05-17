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
import octobot_commons.logging as commons_logging
import octobot_commons.enums as commons_enums
import octobot_commons.authentication as authentication
import octobot_services.constants as services_constants
import tentacles.Services.Interfaces.web_interface.constants as constants
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models
import tentacles.Services.Interfaces.web_interface.util as util
import tentacles.Services.Interfaces.web_interface.flask_util as flask_util
import octobot_backtesting.api as backtesting_api
import octobot_trading.api as trading_api
import octobot_services.interfaces.util as interfaces_util


def register(blueprint):
    @blueprint.route('/configuration')
    @login.login_required_when_activated
    def configuration():
        display_intro = flask_util.BrowsingDataProvider.instance().get_and_unset_is_first_display(
            flask_util.BrowsingDataProvider.get_distribution_key(
                models.get_distribution(),
                flask_util.BrowsingDataProvider.CONFIGURATION,
            )
        )
        display_config = interfaces_util.get_edited_config()
        enabled_exchanges = trading_api.get_enabled_exchanges_names(display_config)
        config_symbols = models.get_enabled_trading_pairs()
        first_symbol_pair = next(iter(config_symbols)) if config_symbols else []
        config_exchanges = models.get_json_exchange_config(display_config)
        trading_mode = models.get_config_activated_trading_mode()
        media_url = flask.url_for("tentacle_media", _external=True)
        tentacle_docs = ""
        trading_mode_name = trading_mode.get_name() if trading_mode else "Missing trading mode"
        if trading_mode:
            tentacle_docs = models.get_tentacle_documentation(trading_mode.get_name(), media_url)
        return flask.render_template(
            'distributions/market_making/configuration.html',
            selected_exchange=enabled_exchanges[0] if enabled_exchanges else (config_exchanges[0][models.NAME] if config_exchanges else None),
            config_exchanges=config_exchanges,
            exchanges_schema=models.get_json_exchanges_schema(models.get_tested_exchange_list()),

            selected_pair=first_symbol_pair,

            trading_mode_name=trading_mode_name,
            tentacle_docs=tentacle_docs,

            simulated_portfolio=models.get_json_simulated_portfolio(display_config),
            portfolio_schema=models.JSON_PORTFOLIO_SCHEMA,
            trading_simulator_schema=models.JSON_TRADING_SIMULATOR_SCHEMA,
            config_trading_simulator=models.get_json_trading_simulator_config(display_config),

            display_intro=display_intro,
        )

    @blueprint.route('/configuration', methods=['POST'])
    @login.login_required_when_activated
    def save_market_making_config():
        request_data = flask.request.get_json()
        print(request_data)
        success = False
        response = "Restart to apply."
        err_message = None
        try:
            models.save_market_making_configuration(
                request_data["exchange"],
                request_data["tradingPair"],
                request_data["exchangesConfig"],
                request_data["tradingSimulatorConfig"],
                request_data["simulatedPortfolioConfig"],
                request_data["tradingModeName"],
                request_data["tradingModeConfig"],
            )
            success = True
        except Exception as e:
            err_message = f"Failed to save market making configuration: {e.__class__.__name__}: {e}"
        if success:
            return util.get_rest_reply(flask.jsonify(response))
        else:
            return util.get_rest_reply(flask.jsonify(err_message), 500)

