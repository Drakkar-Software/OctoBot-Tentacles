#  Drakkar-Software OctoBot-Tentacles
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
from flask_socketio import emit

from octobot_trading.enums import ExchangeConstantsOrderColumns
from tentacles.Interfaces.web_interface import register_notifier, DASHBOARD_NOTIFICATION_KEY
from tentacles.Interfaces.web_interface.models.dashboard import get_currency_price_graph_update, get_value_from_dict_or_string, \
    format_trades
from octobot_commons.pretty_printer import PrettyPrinter
from octobot_interfaces.util.profitability import get_global_profitability
from tentacles.Interfaces.web_interface.websockets import namespaces
from tentacles.Interfaces.web_interface.websockets.abstract_websocket_namespace_notifier import AbstractWebSocketNamespaceNotifier


class DashboardNamespace(AbstractWebSocketNamespaceNotifier):

    @staticmethod
    def _get_profitability():
        profitability_digits = 4
        has_real_trader, has_simulated_trader, \
        _, _, \
        real_percent_profitability, simulated_percent_profitability, \
        real_no_trade_profitability, simulated_no_trade_profitability, \
        market_average_profitability = get_global_profitability()
        profitability_data = \
            {"market_average_profitability":
                 PrettyPrinter.round_with_decimal_count(market_average_profitability, profitability_digits)}
        if has_real_trader:
            profitability_data["bot_real_profitability"] = \
                PrettyPrinter.round_with_decimal_count(real_percent_profitability, profitability_digits)
            profitability_data["real_no_trade_profitability"] = \
                PrettyPrinter.round_with_decimal_count(real_no_trade_profitability, profitability_digits)
        if has_simulated_trader:
            profitability_data["bot_simulated_profitability"] = \
                PrettyPrinter.round_with_decimal_count(simulated_percent_profitability, profitability_digits)
            profitability_data["simulated_no_trade_profitability"] = \
                PrettyPrinter.round_with_decimal_count(simulated_no_trade_profitability, profitability_digits)
        return profitability_data

    @staticmethod
    def _format_new_data(real_trades=None, simulated_trades=None):
        if real_trades is None:
            real_trades = []
        if simulated_trades is None:
            simulated_trades = []
        symbol = None
        if real_trades:
            symbol = real_trades[0][ExchangeConstantsOrderColumns.SYMBOL.value]
        elif simulated_trades:
            symbol = simulated_trades[0][ExchangeConstantsOrderColumns.SYMBOL.value]
        return {
            "real_trades": format_trades(real_trades),
            "simulated_trades": format_trades(simulated_trades),
            "symbol": symbol
        }

    def on_profitability(self):
        emit("profitability", self._get_profitability())

    def all_clients_send_notifications(self, **kwargs) -> bool:
        if self._has_clients():
            try:
                self.socketio.emit("new_data", {
                                        "data": self._format_new_data(**kwargs)
                                   },
                                   namespace=self.namespace)
                return True
            except Exception as e:
                self.logger.exception(e, True, f"Error when sending web notification: {e}")
        return False

    def on_candle_graph_update(self, data):
        try:
            emit("candle_graph_update_data", {
                "request": data,
                "data": get_currency_price_graph_update(data["exchange_id"],
                                                        get_value_from_dict_or_string(data["symbol"]),
                                                        data["time_frame"],
                                                        backtesting=False,
                                                        minimal_candles=True,
                                                        ignore_trades=True)
            })
        except KeyError as e:
            emit("error", "missing exchange manager")

    def on_connect(self):
        super().on_connect()
        self.on_profitability()


notifier = DashboardNamespace('/dashboard')
register_notifier(DASHBOARD_NOTIFICATION_KEY, notifier)
namespaces.append(notifier)
