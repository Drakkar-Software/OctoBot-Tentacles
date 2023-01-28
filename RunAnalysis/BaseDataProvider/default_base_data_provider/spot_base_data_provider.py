#  Drakkar-Software OctoBot-Trading
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
import octobot_commons.symbols.symbol_util as symbol_util
import tentacles.RunAnalysis.BaseDataProvider.default_base_data_provider.base_data_provider as base_data_provider
import octobot_trading.enums as trading_enums
import octobot_commons.enums as commons_enums
from octobot_commons.enums import PlotAttributes as PlotAttrs


class SpotRunAnalysisBaseDataGenerator(base_data_provider.RunAnalysisBaseDataGenerator):
    async def generate_transactions(self) -> None:
        if not self.trading_transactions_history:
            # only calculate once per execution
            self.trading_transactions_history = []
            self.buy_fees_by_currency: dict = {"total": 0}
            self.sell_fees_by_currency: dict = {"total": 0}
            self.portfolio_history_by_currency: dict = {}

            prev_transaction_id = 0
            buy_order_volume_by_prices_and_currency_and_ref_market = {}

            all_sorted_trades = initialize_and_sort_all_spot_trades(
                self.trades_data,
                buy_order_volume_by_prices_and_currency_and_ref_market,
                self.starting_portfolio,
                self.price_data,
                self.portfolio_history_by_currency,
                self.start_time * 1000,
            )

            for trade in all_sorted_trades:
                trade_volume = trade[PlotAttrs.VOLUME.value]
                if not trade_volume:
                    # TODO investigate why some trades with 0 volume are
                    # in storage, but not on exchange
                    base_data_provider.get_logger().warning(
                        "Trade found without a volume"
                    )
                    continue
                parsed_symbol = symbol_util.parse_symbol(trade[PlotAttrs.SYMBOL.value])
                buy_order_volume_by_price_and_ref_market: dict = (
                    buy_order_volume_by_prices_and_currency_and_ref_market[
                        parsed_symbol.base
                    ]
                )
                if (
                    trade[PlotAttrs.SIDE.value]
                    == trading_enums.TradeOrderSide.BUY.value
                ):
                    handle_spot_buy_trade(
                        parsed_symbol,
                        self.buy_fees_by_currency,
                        trade,
                        self.trading_transactions_history,
                        self.portfolio_history_by_currency,
                        prev_transaction_id,
                        buy_order_volume_by_price_and_ref_market,
                    )
                elif (
                    trade[PlotAttrs.SIDE.value]
                    == trading_enums.TradeOrderSide.SELL.value
                ):
                    handle_spot_sell_trade(
                        parsed_symbol,
                        self.sell_fees_by_currency,
                        trade,
                        self.trading_transactions_history,
                        self.portfolio_history_by_currency,
                        prev_transaction_id,
                        buy_order_volume_by_price_and_ref_market,
                        self.price_data,
                    )
                else:
                    base_data_provider.get_logger().error(
                        f"Unknown trade side: {trade}"
                    )


def handle_spot_sell_trade(
    parsed_symbol,
    sell_fees_by_currency: dict,
    trade,
    trading_transactions_history,
    portfolio_history_by_currency,
    prev_transaction_id,
    buy_order_volume_by_price_and_ref_market,
    price_data: dict,
):
    trade_volume = trade[PlotAttrs.VOLUME.value]

    paid_fees: float = get_sell_fees_in_quote_currency(
        trade, parsed_symbol, sell_fees_by_currency
    )
    buy_cost, local_pnl = close_position(
        parsed_symbol,
        buy_order_volume_by_price_and_ref_market,
        trade_volume,
        trade,
        paid_fees,
        price_data,
    )
    add_updated_portfolio_for_sell_trade(
        trade, parsed_symbol, portfolio_history_by_currency, paid_fees
    )
    # sell fees transaction
    add_transaction(
        trading_transactions_history=trading_transactions_history,
        prev_transaction_id=prev_transaction_id,
        trade=trade,
        _type=trading_enums.TransactionType.TRADING_FEE.value,
        pair=trade[PlotAttrs.SYMBOL.value],
        transaction_currency=parsed_symbol.quote,
        transaction_quantity=-paid_fees,
    )
    # realized pnl transaction
    add_transaction(
        trading_transactions_history=trading_transactions_history,
        prev_transaction_id=prev_transaction_id,
        trade=trade,
        _type=trading_enums.TransactionType.REALIZED_PNL.value,
        pair=trade[PlotAttrs.SYMBOL.value],
        transaction_currency=parsed_symbol.quote,
        side="long",
        realized_pnl=local_pnl,
        closed_quantity=-trade_volume,
        cumulated_closed_quantity=0,  # todo
        transaction_first_entry_time=0,  # todo
        average_entry_price=buy_cost / trade_volume,
        average_exit_price=trade[PlotAttrs.Y.value],
        order_exit_price=trade[PlotAttrs.Y.value],
    )


def close_position(
    parsed_symbol,
    buy_order_volume_by_price_and_ref_market,
    trade_volume,
    trade,
    paid_fees,
    price_data,
):
    remaining_sell_volume = trade_volume
    volume_by_bought_prices = {}
    (
        buy_order_volume_by_price_and_ref_market[parsed_symbol.quote],
        volume_by_bought_prices,
        remaining_sell_volume,
    ) = _close_position(
        buy_order_volume_by_price_and_ref_market[parsed_symbol.quote],
        volume_by_bought_prices,
        remaining_sell_volume,
        conversion_value=1,
    )
    if remaining_sell_volume > 0:
        if remaining_sell_volume < 0.000001:
            base_data_provider.get_logger().error(
                f"Rounding issue detectected {trade['symbol']}, "
                f"remaining sell volume {remaining_sell_volume} "
                f"Run analysis will not be accurate - trade: {trade}"
            )
        else:
            # handle closing open trade from other pair
            for ref_market in buy_order_volume_by_price_and_ref_market:
                if remaining_sell_volume <= 0:
                    break
                if ref_market == parsed_symbol.quote:
                    continue
                conversion_symbol = f"{parsed_symbol.quote}/{ref_market}"
                converion_price = None
                if conversion_symbol not in price_data:
                    conversion_symbol = f"{ref_market}/{parsed_symbol.quote}"
                    if conversion_symbol not in price_data:
                        base_data_provider.get_logger().error(
                            f"Unable to handle sell trade {trade['symbol']}, no pair "
                            "aivailable to convert value plots "
                            f"will not be accurate: {trade}"
                        )
                        break
                for candle in price_data[conversion_symbol]:
                    if candle[0] <= trade["x"]:
                        converion_price = candle[4]
                    else:
                        break

                (
                    buy_order_volume_by_price_and_ref_market[ref_market],
                    volume_by_bought_prices,
                    remaining_sell_volume,
                ) = _close_position(
                    buy_order_volume_by_price_and_ref_market[ref_market],
                    volume_by_bought_prices,
                    remaining_sell_volume,
                    conversion_value=converion_price,
                )

    if not volume_by_bought_prices:
        base_data_provider.get_logger().error(
            f"Unable to handle sell trade, plots will not be accurate: {trade}"
        )

    buy_cost = sum(price * volume for price, volume in volume_by_bought_prices.items())
    local_pnl = trade[PlotAttrs.Y.value] * trade_volume - paid_fees - buy_cost
    return buy_cost, local_pnl


def _close_position(
    buy_order_volume_by_prices,
    volume_by_bought_prices,
    remaining_sell_volume,
    conversion_value,
):
    for order_price in list(buy_order_volume_by_prices.keys()):
        if buy_order_volume_by_prices[order_price] > remaining_sell_volume:
            buy_order_volume_by_prices[order_price] -= remaining_sell_volume
            volume_by_bought_prices[
                order_price * conversion_value
            ] = remaining_sell_volume
            remaining_sell_volume = 0
        elif buy_order_volume_by_prices[order_price] == remaining_sell_volume:
            buy_order_volume_by_prices.pop(order_price)
            volume_by_bought_prices[
                order_price * conversion_value
            ] = remaining_sell_volume
            remaining_sell_volume = 0
        else:
            # buy_order_volume_by_price[order_price] < remaining_sell_volume
            buy_volume = buy_order_volume_by_prices.pop(order_price)
            volume_by_bought_prices[order_price * conversion_value] = buy_volume
            remaining_sell_volume -= buy_volume
        if remaining_sell_volume <= 0:
            break
    return buy_order_volume_by_prices, volume_by_bought_prices, remaining_sell_volume


def handle_spot_buy_trade(
    parsed_symbol,
    buy_fees_by_currency: dict,
    trade,
    trading_transactions_history,
    portfolio_history_by_currency,
    prev_transaction_id,
    buy_order_volume_by_price_and_ref_market,
):
    paid_fees: float = get_buy_fees_in_base_currency(
        trade, parsed_symbol, buy_fees_by_currency
    )

    net_volume = add_to_open_positions(
        trade,
        parsed_symbol,
        buy_order_volume_by_price_and_ref_market,
        paid_fees,
    )
    add_updated_portfolio_for_buy_trade(
        trade, parsed_symbol, portfolio_history_by_currency, net_volume
    )
    # buy fees transaction
    add_transaction(
        trading_transactions_history=trading_transactions_history,
        prev_transaction_id=prev_transaction_id,
        trade=trade,
        _type=trading_enums.TransactionType.TRADING_FEE.value,
        pair=trade[PlotAttrs.SYMBOL.value],
        transaction_currency=parsed_symbol.base,
        transaction_quantity=-paid_fees,
    )


def add_updated_portfolio_for_sell_trade(
    trade, parsed_symbol, portfolio_history_by_currency, paid_fees
):
    add_updated_portfolio_for_this_coin(
        parsed_symbol.base,
        portfolio_history_by_currency,
        trade[PlotAttrs.X.value],
        amount_to_add=-trade[PlotAttrs.VOLUME.value],
    )
    add_updated_portfolio_for_this_coin(
        parsed_symbol.quote,
        portfolio_history_by_currency,
        trade[PlotAttrs.X.value],
        amount_to_add=(
            trade[PlotAttrs.VOLUME.value] * trade[PlotAttrs.Y.value] - paid_fees
        ),
    )


def add_updated_portfolio_for_buy_trade(
    trade, parsed_symbol, portfolio_history_by_currency, net_volume
):
    amount_to_add_to_base = net_volume
    amount_to_add_to_quote = -trade[PlotAttrs.VOLUME.value] * trade[PlotAttrs.Y.value]

    add_updated_portfolio_for_this_coin(
        parsed_symbol.base,
        portfolio_history_by_currency,
        trade[PlotAttrs.X.value],
        amount_to_add_to_base,
    )
    add_updated_portfolio_for_this_coin(
        parsed_symbol.quote,
        portfolio_history_by_currency,
        trade[PlotAttrs.X.value],
        amount_to_add_to_quote,
    )


def add_updated_portfolio_for_this_coin(
    coin,
    portfolio_history_by_currency,
    timestamp,
    # negative amount to reduce portfolio
    amount_to_add,
):
    current_amount = 0
    if coin in portfolio_history_by_currency:
        # get current amount from last update
        current_amount = portfolio_history_by_currency[coin][-1][PlotAttrs.VOLUME.value]
    else:
        portfolio_history_by_currency[coin] = []

    portfolio_history_by_currency[coin].append(
        {
            PlotAttrs.VOLUME.value: current_amount + amount_to_add,
            PlotAttrs.X.value: timestamp,
        }
    )


def add_to_open_positions(
    trade,
    parsed_symbol,
    buy_order_volume_by_price_and_ref_market: dict,
    paid_fees: float,
) -> float:
    this_ref_market_buy_order_volume_by_prices: dict = (
        buy_order_volume_by_price_and_ref_market[parsed_symbol.quote]
    )
    trade_volume: float = trade[PlotAttrs.VOLUME.value]

    buy_cost: float = trade_volume * trade[PlotAttrs.Y.value]
    net_volume: float = trade_volume - paid_fees
    # average price == average cost per share
    # average entry price includes fees
    average_price: float = buy_cost / net_volume
    if average_price in this_ref_market_buy_order_volume_by_prices:
        this_ref_market_buy_order_volume_by_prices[average_price] += net_volume
    else:
        this_ref_market_buy_order_volume_by_prices[average_price] = net_volume
    return net_volume


def get_buy_fees_in_base_currency(trade, parsed_symbol, buy_fees_by_currency) -> float:
    return get_fees(trade, parsed_symbol.base, buy_fees_by_currency)


def get_sell_fees_in_quote_currency(
    trade, parsed_symbol, sell_fees_by_currency
) -> float:
    return get_fees(trade, parsed_symbol.quote, sell_fees_by_currency)


def get_fees(trade, currency, fees_by_currency) -> float:
    fees = trade[commons_enums.DBTables.FEES_AMOUNT.value]
    fees_multiplier = (
        1
        if trade[commons_enums.DBTables.FEES_CURRENCY.value] == currency
        else trade[PlotAttrs.Y.value]
    )
    paid_fees = fees * fees_multiplier
    # store paid fees by currency
    if currency in fees_by_currency:
        fees_by_currency[currency] += paid_fees
    else:
        fees_by_currency[currency] = paid_fees

    # TODO calculate total fees in ref market
    # sell_fees_by_currency["total"] += paid_fees
    return paid_fees


def initialize_and_sort_all_spot_trades(
    trades_data,
    buy_order_volume_by_price_by_currency,
    starting_portfolio,
    price_data,
    portfolio_history_by_currency,
    start_time,
) -> list:
    all_sorted_trades = []
    for pair, trades in trades_data.items():
        parsed_symbol = symbol_util.parse_symbol(pair)
        if parsed_symbol.base not in buy_order_volume_by_price_by_currency:
            buy_order_volume_by_price_by_currency[parsed_symbol.base] = {}
        if (
            parsed_symbol.quote
            not in buy_order_volume_by_price_by_currency[parsed_symbol.base]
        ):
            buy_order_volume_by_price_by_currency[parsed_symbol.base][
                parsed_symbol.quote
            ] = (
                {
                    # set start portfolio to buy_order_volume_by_price_by_currency
                    starting_portfolio[parsed_symbol.base]["total"]: price_data[pair][
                        0
                    ][4],
                }
                if parsed_symbol.base in starting_portfolio
                and starting_portfolio[parsed_symbol.base]["total"]
                else {}
            )

        for trade in trades:
            all_sorted_trades.append(trade)
    for coin, holding in starting_portfolio.items():
        if holding["total"]:
            add_updated_portfolio_for_this_coin(
                coin,
                portfolio_history_by_currency,
                0,  # use start_time when fixed for live
                holding["total"],
            )
    return sorted(all_sorted_trades, key=lambda trade: trade[PlotAttrs.X.value])


def add_transaction(
    trading_transactions_history,
    prev_transaction_id,
    trade,
    _type,
    pair,
    transaction_currency,
    transaction_quantity=None,
    side=None,
    realized_pnl=None,
    closed_quantity=None,
    cumulated_closed_quantity=None,
    transaction_first_entry_time=None,
    average_entry_price=None,
    average_exit_price=None,
    order_exit_price=None,
):
    trading_transactions_history.append(
        {
            "x": trade[PlotAttrs.X.value],
            "type": _type,
            "id": prev_transaction_id,
            "symbol": pair,
            "trading_mode": trade["trading_mode"],
            "currency": transaction_currency,
            "quantity": transaction_quantity,
            "order_id": trade["id"],
            "funding_rate": None,
            "realized_pnl": realized_pnl,
            "transaction_fee": None,
            "closed_quantity": closed_quantity,
            "cumulated_closed_quantity": cumulated_closed_quantity,
            "first_entry_time": transaction_first_entry_time,
            "average_entry_price": average_entry_price,
            "average_exit_price": average_exit_price,
            "order_exit_price": order_exit_price,
            "leverage": 0,
            "trigger_source": None,
            "side": side,
            "y": 0,
            "chart": "main-chart",
            "kind": "scattergl",
            "mode": "markers",
        }
    )
    prev_transaction_id += 1
