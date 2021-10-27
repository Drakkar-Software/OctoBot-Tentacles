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


@web_interface.server_instance.route("/strategy_design")
@login.login_required_when_activated
def strategy_design():
    return flask.render_template("strategy_design.html")


@web_interface.server_instance.route("/plotted_data")
@login.login_required_when_activated
def plotted_data():
    try:
        trading_mode = models.get_config_activated_trading_mode()
        # TODO remove
        import tentacles.Trading.Mode.scripted_trading_mode as scripted_trading_mode
        trading_mode = scripted_trading_mode.ScriptedTradingMode
        from tentacles.Trading.Mode.scripted_trading_mode.active_scripts.test_script.backtesting.test_script import backtest_test_script
        trading_mode.register_plot_script(backtest_test_script)
        # TODO remove
        return util.get_rest_reply(models.get_plotted_data(trading_mode), 200)
    except Exception as e:
        commons_logging.get_logger("plotted_data").exception(e)
        return util.get_rest_reply(str(e), 500)


@web_interface.server_instance.route("/update_plot_script")
@login.login_required_when_activated
def update_plot_script():
    try:
        trading_mode = models.get_config_activated_trading_mode()
        # TODO remove
        import tentacles.Trading.Mode.scripted_trading_mode as scripted_trading_mode
        trading_mode = scripted_trading_mode.ScriptedTradingMode
        # TODO remove
        return util.get_rest_reply(models.update_plot_script(trading_mode), 200)
    except Exception as e:
        commons_logging.get_logger("update_plot_script").exception(e)
        return util.get_rest_reply(str(e), 500)
