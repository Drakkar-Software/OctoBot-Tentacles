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
import sortedcontainers
import octobot_services.interfaces.util as interfaces_util
import octobot_trading.api as trading_api
import octobot_trading.enums as trading_enums
import octobot_commons.enums as commons_enums
import octobot_commons.constants as commons_constants
import tentacles.Services.Interfaces.web_interface.errors as errors
import tentacles.Services.Interfaces.web_interface.models.dashboard as dashboard


def ensure_valid_exchange_id(exchange_id) -> str:
    try:
        trading_api.get_exchange_manager_from_exchange_id(exchange_id)
    except KeyError as e:
        raise errors.MissingExchangeId() from e


def get_exchange_time_frames(exchange_id):
    try:
        exchange_manager = trading_api.get_exchange_manager_from_exchange_id(exchange_id)
        return trading_api.get_watched_timeframes(exchange_manager), trading_api.get_exchange_name(exchange_manager)
    except KeyError:
        return [], ""


def get_initializing_currencies_prices_set():
    initializing_currencies = set()
    for exchange_manager in interfaces_util.get_exchange_managers():
        initializing_currencies = initializing_currencies.union(
            trading_api.get_initializing_currencies_prices(exchange_manager))
    return initializing_currencies


def get_evaluation(symbol, exchange_name, exchange_id):
    try:
        if exchange_name:
            exchange_manager = trading_api.get_exchange_manager_from_exchange_name_and_id(exchange_name, exchange_id)
            for trading_mode in trading_api.get_trading_modes(exchange_manager):
                if trading_api.get_trading_mode_symbol(trading_mode) == symbol:
                    state_desc, val_state = trading_api.get_trading_mode_current_state(trading_mode)
                    try:
                        val_state = round(val_state)
                    except TypeError:
                        pass
                    return f"{state_desc.replace('_', ' ')}, {val_state}"
    except KeyError:
        pass
    return "N/A"


def get_exchanges_load():
    return {
        trading_api.get_exchange_name(exchange_manager): {
            "load": trading_api.get_currently_handled_pair_with_time_frame(exchange_manager),
            "max_load": trading_api.get_max_handled_pair_with_time_frame(exchange_manager),
            "overloaded": trading_api.is_overloaded(exchange_manager),
            "has_websocket": trading_api.get_has_websocket(exchange_manager)
        }
        for exchange_manager in interfaces_util.get_exchange_managers()
    }


def _add_exchange_portfolio(portfolio, exchange, holdings_per_symbol):
    exchanges_key = "exchanges"
    total_key = "total"
    free_key = "free"
    locked_key = "locked"
    for currency, amounts in portfolio.items():
        total_amount = amounts.total
        free_amount = amounts.available
        if total_amount > 0:
            if currency not in holdings_per_symbol:
                holdings_per_symbol[currency] = {
                    exchanges_key: {}
                }
            holdings_per_symbol[currency][exchanges_key][exchange] = {
                total_key: total_amount,
                free_key: free_amount,
                locked_key: total_amount - free_amount,
            }
            holdings_per_symbol[currency][total_key] = holdings_per_symbol[currency].get(total_key, 0) + total_amount
            holdings_per_symbol[currency][free_key] = holdings_per_symbol[currency].get(free_key, 0) + free_amount
            holdings_per_symbol[currency][locked_key] = holdings_per_symbol[currency][total_key] - \
                holdings_per_symbol[currency][free_key]


def get_exchange_holdings_per_symbol():
    holdings_per_symbol = {}
    for exchange_manager in interfaces_util.get_exchange_managers():
        if trading_api.is_trader_existing_and_enabled(exchange_manager):
            portfolio = trading_api.get_portfolio(exchange_manager)
            _add_exchange_portfolio(portfolio, trading_api.get_exchange_name(exchange_manager), holdings_per_symbol)
    return holdings_per_symbol


def get_symbols_values(symbols, has_real_trader, has_simulated_trader):
    loading = 0
    value_per_symbols = {symbol: loading for symbol in symbols}
    real_portfolio_holdings, simulated_portfolio_holdings = interfaces_util.get_portfolio_holdings()
    portfolio = real_portfolio_holdings if has_real_trader else simulated_portfolio_holdings
    value_per_symbols.update(portfolio)
    return value_per_symbols


def _get_exchange_historical_portfolio(exchange_manager, currency, time_frame, from_timestamp, to_timestamp):
    return trading_api.get_portfolio_historical_values(exchange_manager, currency, time_frame,
                                                       from_timestamp=from_timestamp, to_timestamp=to_timestamp)


def _merge_all_exchanges_historical_portfolio(currency, time_frame, from_timestamp, to_timestamp):
    merged_result = sortedcontainers.SortedDict()
    for exchange_manager in trading_api.get_exchange_managers_from_exchange_ids(trading_api.get_exchange_ids()):
        for value in _get_exchange_historical_portfolio(
                exchange_manager, currency, time_frame, from_timestamp, to_timestamp
        ):
            if value[trading_enums.HistoricalPortfolioValue.TIME.value] not in merged_result:
                merged_result[value[trading_enums.HistoricalPortfolioValue.TIME.value]] = \
                    value[trading_enums.HistoricalPortfolioValue.VALUE.value]
            else:
                merged_result[value[trading_enums.HistoricalPortfolioValue.TIME.value]] += \
                    value[trading_enums.HistoricalPortfolioValue.VALUE.value]
    return [
        {
            trading_enums.HistoricalPortfolioValue.TIME.value: key,
            trading_enums.HistoricalPortfolioValue.VALUE.value: val,
        }
        for key, val in merged_result.items()
    ]


def get_portfolio_historical_values(currency, time_frame=None, from_timestamp=None, to_timestamp=None, exchange=None):
    time_frame = commons_enums.TimeFrames(time_frame) if time_frame else commons_enums.TimeFrames.ONE_DAY
    if exchange is None:
        return _merge_all_exchanges_historical_portfolio(currency, time_frame, from_timestamp, to_timestamp)
    return _get_exchange_historical_portfolio(
        dashboard.get_first_exchange_data(exchange)[0],
        currency, time_frame, from_timestamp, to_timestamp
    )


def clear_exchanges_orders_history(simulated_only=False):
    _run_on_exchange_ids(trading_api.clear_orders_storage_history, simulated_only=simulated_only)
    return {"title": "Cleared orders history"}


def clear_exchanges_trades_history(simulated_only=False):
    _run_on_exchange_ids(trading_api.clear_trades_storage_history, simulated_only=simulated_only)
    return {"title": "Cleared trades history"}


def clear_exchanges_transactions_history(simulated_only=False):
    _run_on_exchange_ids(trading_api.clear_transactions_storage_history, simulated_only=simulated_only)
    return {"title": "Cleared transactions history"}


def clear_exchanges_portfolio_history(simulated_only=False, simulated_portfolio=None):
    # apply updated simulated portfolio to init new historical values on this new portfolio
    simulated_portfolio = simulated_portfolio or \
        interfaces_util.get_edited_config(dict_only=True).get(commons_constants.CONFIG_SIMULATOR, {}).get(
            commons_constants.CONFIG_STARTING_PORTFOLIO, None)
    if simulated_portfolio:
        _sync_run_on_exchange_ids(trading_api.set_simulated_portfolio_initial_config, simulated_only=simulated_only,
                                  portfolio_content=simulated_portfolio)
    _run_on_exchange_ids(trading_api.clear_portfolio_storage_history, simulated_only=simulated_only)
    return {"title": "Cleared portfolio history"}


async def _async_run_on_exchange_ids(coro, exchange_ids, simulated_only, **kwargs):
    for exchange_manager in trading_api.get_exchange_managers_from_exchange_ids(exchange_ids):
        if not simulated_only or trading_api.is_trader_simulated(exchange_manager):
            await coro(exchange_manager, **kwargs)


def _run_on_exchange_ids(coro, simulated_only=False, **kwargs):
    interfaces_util.run_in_bot_main_loop(
        _async_run_on_exchange_ids(coro, trading_api.get_exchange_ids(), simulated_only, **kwargs)
    )


def _sync_run_on_exchange_ids(func, simulated_only=False, **kwargs):
    for exchange_manager in trading_api.get_exchange_managers_from_exchange_ids(trading_api.get_exchange_ids()):
        if not simulated_only or trading_api.is_trader_simulated(exchange_manager):
            func(exchange_manager, **kwargs)
