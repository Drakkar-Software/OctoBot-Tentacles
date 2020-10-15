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

import datetime
import flask

import octobot_services.interfaces.util as interfaces_util
import tentacles.Services.Interfaces.web_interface as web_interface
import octobot_trading.constants as trading_constants
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models


@web_interface.server_instance.route("/portfolio")
@login.login_required_when_activated
def portfolio():
    has_real_trader, has_simulated_trader = interfaces_util.has_real_and_or_simulated_traders()

    real_portfolio, simulated_portfolio = interfaces_util.get_global_portfolio_currencies_amounts()

    filtered_real_portfolio = {currency: amounts
                               for currency, amounts in real_portfolio.items()
                               if amounts[trading_constants.CONFIG_PORTFOLIO_TOTAL] > 0}
    filtered_simulated_portfolio = {currency: amounts
                                    for currency, amounts in simulated_portfolio.items()
                                    if amounts[trading_constants.CONFIG_PORTFOLIO_TOTAL] > 0}

    _, _, portfolio_real_current_value, portfolio_simulated_current_value = interfaces_util.get_portfolio_current_value()
    reference_market = interfaces_util.get_reference_market()
    initializing_currencies_prices_set = models.get_initializing_currencies_prices_set()

    return flask.render_template('portfolio.html',
                                 has_real_trader=has_real_trader,
                                 has_simulated_trader=has_simulated_trader,
                                 simulated_portfolio=filtered_simulated_portfolio,
                                 real_portfolio=filtered_real_portfolio,
                                 simulated_total_value=round(portfolio_simulated_current_value, 8),
                                 real_total_value=round(portfolio_real_current_value, 8),
                                 reference_unit=reference_market,
                                 initializing_currencies_prices=initializing_currencies_prices_set
                                 )


@web_interface.server_instance.route("/portfolio_holdings")
@login.login_required_when_activated
def portfolio_holdings():
    result = {}
    real_portfolio_holdings, simulated_portfolio_holdings = interfaces_util.get_portfolio_holdings()
    result["real_portfolio_holdings"] = real_portfolio_holdings
    result["simulated_portfolio_holdings"] = simulated_portfolio_holdings
    return flask.jsonify(result)


@web_interface.server_instance.route("/symbol_market_status")
@web_interface.server_instance.route('/symbol_market_status', methods=['GET', 'POST'])
@login.login_required_when_activated
def symbol_market_status():
    exchange_id = flask.request.args["exchange_id"]
    symbol = flask.request.args["symbol"]
    symbol_time_frames, exchange = models.get_exchange_time_frames(exchange_id)
    time_frames = list(symbol_time_frames)
    time_frames.reverse()
    symbol_evaluation = models.get_evaluation(symbol, exchange, exchange_id)
    return flask.render_template('symbol_market_status.html',
                                 symbol=symbol,
                                 exchange=exchange,
                                 exchange_id=exchange_id,
                                 symbol_evaluation=symbol_evaluation,
                                 time_frames=time_frames,
                                 backtesting_mode=models.get_in_backtesting_mode())


@web_interface.server_instance.route("/trading")
@login.login_required_when_activated
def trading():
    real_open_orders, simulated_open_orders = interfaces_util.get_all_open_orders()
    has_real_trader, _ = interfaces_util.has_real_and_or_simulated_traders()
    return flask.render_template('trading.html',
                                 real_open_orders=real_open_orders,
                                 simulated_open_orders=simulated_open_orders,
                                 watched_symbols=models.get_watched_symbols(),
                                 pairs_with_status=interfaces_util.get_currencies_with_status(),
                                 has_real_trader=has_real_trader)


@web_interface.server_instance.route("/trades")
@login.login_required_when_activated
def trades():
    real_trades_history, simulated_trades_history = interfaces_util.get_trades_history()
    return flask.render_template('trades.html',
                                 real_trades_history=real_trades_history,
                                 simulated_trades_history=simulated_trades_history)


@web_interface.server_instance.context_processor
def utility_processor():
    def convert_timestamp(str_time):
        return datetime.datetime.fromtimestamp(str_time).strftime('%Y-%m-%d %H:%M:%S')

    def convert_type(order_type):
        return order_type.name

    return dict(convert_timestamp=convert_timestamp, convert_type=convert_type)
