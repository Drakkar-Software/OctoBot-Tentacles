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
import tentacles.Services.Interfaces.web_interface.util as util
import octobot_commons.logging as commons_logging
import octobot_commons.enums as commons_enums
import octobot_commons.symbol_util as symbol_util
import octobot_commons


@web_interface.server_instance.route("/strategy_design")
@login.login_required_when_activated
def strategy_design():
    trading_mode = models.get_config_activated_trading_mode()
    exchange_manager, exchange_name, exchange_id = models.get_first_exchange_data()
    symbols = models.get_enabled_trading_pairs()
    activated_evaluators = models.get_config_activated_evaluators()
    strategies = models.get_config_activated_strategies()
    activated_strategy = strategies[0] if strategies else None
    return flask.render_template(
        "strategy_design.html",
        trading_mode_name=trading_mode.get_name(),
        tentacle_class=trading_mode,
        exchange_id=exchange_id,
        exchange_name=exchange_name,
        symbols=sorted([symbol_util.convert_symbol(s, octobot_commons.MARKET_SEPARATOR, "|") for s in symbols]),
        time_frames=[tf.value for tf in models.get_traded_time_frames(exchange_manager)],
        enabled_time_frames=[tf.value for tf in models.get_config_time_frames()],
        exchange_time_frames=[tf.value for tf in commons_enums.TimeFrames],
        activated_evaluators=activated_evaluators,
        activated_strategy=activated_strategy,
    )


@web_interface.server_instance.route("/plotted_data")
@login.login_required_when_activated
def plotted_data():
    try:
        exchange_id = flask.request.args.get('exchange_id')
        symbol = flask.request.args.get('symbol')
        time_frame = flask.request.args.get('time_frame')
        trading_mode = models.get_config_activated_trading_mode()
        return util.get_rest_reply(models.get_plotted_data(trading_mode, symbol_util.convert_symbol(symbol, "|"),
                                                           time_frame, exchange_id=exchange_id), 200)
    except Exception as e:
        commons_logging.get_logger("plotted_data").exception(e)
        return util.get_rest_reply(str(e), 500)


@web_interface.server_instance.route("/backtesting_main_plotted_data")
@login.login_required_when_activated
def backtesting_main_plotted_data():
    try:
        exchange_id = flask.request.args.get('exchange_id')
        symbol = flask.request.args.get('symbol')
        time_frame = flask.request.args.get('time_frame')
        run_id = flask.request.args.get('run_id')
        optimizer_id = int(flask.request.args.get('optimizer_id', 0)) or None
        trading_mode = models.get_config_activated_trading_mode()
        return util.get_rest_reply(
            models.get_plotted_data(trading_mode, symbol_util.convert_symbol(symbol, "|"),
                                    time_frame, run_id=run_id, optimizer_id=optimizer_id, exchange_id=exchange_id),
            200)
    except Exception as e:
        commons_logging.get_logger("plotted_data").exception(e)
        return util.get_rest_reply(str(e), 500)


@web_interface.server_instance.route("/backtesting_run_plotted_data", methods=["POST"])
@login.login_required_when_activated
def backtesting_run_plotted_data():
    try:
        request_data = flask.request.get_json()
        trading_mode = models.get_config_activated_trading_mode()
        symbol = symbol_util.convert_symbol(request_data["symbol"], "|")
        optimizer_id = int(request_data.get('optimizer_id', 0)) or None
        return util.get_rest_reply(models.get_backtesting_run_plotted_data(trading_mode, request_data["exchange"],
                                                                           symbol, request_data["id"],
                                                                           optimizer_id),
                                   200)
    except Exception as e:
        commons_logging.get_logger("backtesting_run_plotted_data").exception(e)
        return util.get_rest_reply(str(e), 500)


@web_interface.server_instance.route("/update_plot_script", methods=["POST"])
@login.login_required_when_activated
def update_plot_script():
    try:
        return util.get_rest_reply(models.reload_scripts(), 200)
    except Exception as e:
        commons_logging.get_logger("update_plot_script").exception(e)
        return util.get_rest_reply(str(e), 500)


@web_interface.server_instance.route("/get_run_data")
@login.login_required_when_activated
def get_run_data():
    try:
        trading_mode = models.get_config_activated_trading_mode()
        return util.get_rest_reply(models.get_run_data(trading_mode), 200)
    except Exception as e:
        commons_logging.get_logger("get_run_data").exception(e)
        return util.get_rest_reply(str(e), 500)


@web_interface.server_instance.route("/strategy_design_config_optimizer", methods=["GET", "POST"])
@login.login_required_when_activated
def strategy_design_config_optimizer():
    trading_mode = models.get_config_activated_trading_mode()
    if flask.request.method == 'POST':
        try:
            request_data = flask.request.get_json()
            return util.get_rest_reply(flask.jsonify(models.save_strategy_design_optimizer_config(trading_mode, request_data["config"])))
        except Exception as e:
            commons_logging.get_logger("strategy_design_config_optimizer").exception(e)
            return util.get_rest_reply(str(e), 500)
    else:
        return models.get_strategy_design_optimizer_config(trading_mode)


@web_interface.server_instance.route("/strategy_design_start_optimizer", methods=["POST"])
@login.login_required_when_activated
def strategy_design_start_optimizer():
    try:
        trading_mode = models.get_config_activated_trading_mode()
        request_data = flask.request.get_json()
        exchange_id = request_data.get("exchange_id", None)
        config = request_data.get("config", None)
        randomly_chose_runs = request_data.get("randomly_chose_runs", False)
        success, message = models.start_strategy_design_optimizer(trading_mode,
                                                                  config,
                                                                  exchange_id,
                                                                  randomly_chose_runs)
        return util.get_rest_reply(flask.jsonify(message), 200 if success else 500)
    except Exception as e:
        commons_logging.get_logger("strategy_design_start_optimizer").exception(e)
        return util.get_rest_reply(str(e), 500)
