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
import json
from octobot_trading.api.exchange import get_exchange_ids

import octobot_trading.enums as trading_enums
import octobot_trading.personal_data.portfolios.portfolio_util as portfolio_util
import octobot_trading.api as trading_api
import octobot_backtesting.api as backtesting_api
import octobot_commons.symbols.symbol_util as symbol_util
import octobot_commons.constants
import octobot_commons.enums as commons_enums
import octobot_commons.time_frame_manager as time_frame_manager
import octobot_commons.logging as commons_logging


class RunAnalysisBaseDataGenerator:
    price_data = None
    trades_data = None
    ref_market: str = None
    start_time: float or int = None
    starting_portfolio: dict = None
    moving_portfolio_data = None
    trading_type = None
    metadata = None
    trading_transactions_history: list = None
    portfolio_history_by_currency: dict = None
    buy_fees_by_currency: dict = None
    sell_fees_by_currency: dict = None
    total_start_balance_in_ref_market = None
    pairs = None
    longest_candles = None
    funding_fees_history_by_pair = None
    exchange = None
    realized_pnl_x_data: list = None
    realized_pnl_trade_gains_data: list = None
    realized_pnl_cumulative: list = None
    wins_and_losses_x_data: list = []
    wins_and_losses_data: list = []
    win_rates_x_data: list = []
    win_rates_data: list = []
    best_case_growth_x_data: list = []
    best_case_growth_data: list = []
    historical_portfolio_values_by_coin: dict = None
    historical_portfolio_amounts_by_coin: dict = None
    historical_portfolio_times: list = None
    run_database = None
    run_display = None
    ctx = None
    analysis_settings = None
    trading_transactions_history: list = None
    buy_fees_by_currency: dict = None
    sell_fees_by_currency: dict = None
    portfolio_history_by_currency: dict = None

    def __init__(self, ctx, run_database, run_display, metadata):
        self.run_database = run_database
        self.run_display = run_display
        self.ctx = ctx
        self.metadata = metadata
        self.analysis_settings = ctx.analysis_settings
        self.trading_transactions_history: list = None
        self.buy_fees_by_currency: dict = None
        self.sell_fees_by_currency: dict = None
        self.portfolio_history_by_currency: dict = None

    async def load_base_data(self):
        await self.load_historical_values()
        await self.generate_transactions()

        self.total_start_balance_in_ref_market = self.starting_portfolio[
            self.ref_market
        ][
            "total"
        ]  # todo all coins balance
        self.pairs = list(self.trades_data)
        self._set_longest_candles()

    async def get_trades(self, symbol):
        return await self.run_database.get_trades_db().select(
            commons_enums.DBTables.TRADES.value,
            (await self.run_database.get_orders_db().search()).symbol == symbol,
        )

    def load_starting_portfolio(self) -> dict:
        portfolio = self.metadata[
            commons_enums.BacktestingMetadata.START_PORTFOLIO.value
        ]
        self.starting_portfolio = json.loads(portfolio.replace("'", '"'))

    async def load_historical_values(
        self,
        exchange=None,
        with_candles=True,
        with_trades=True,
        with_portfolio=True,
        time_frame=None,
    ):
        self.price_data = {}
        self.trades_data = {}
        self.moving_portfolio_data = {}
        self.start_time: float or int = self.metadata["start_time"]
        self.load_starting_portfolio()
        self.exchange = (
            exchange
            or self.metadata[commons_enums.DBRows.EXCHANGES.value][0]
            or (
                self.run_database.run_dbs_identifier.context.exchange_name
                if self.run_database.run_dbs_identifier.context
                else None
            )
        )  # TODO handle multi exchanges
        self.ref_market = self.metadata[commons_enums.DBRows.REFERENCE_MARKET.value]
        self.trading_type = self.metadata[commons_enums.DBRows.TRADING_TYPE.value]
        contracts = (
            self.metadata[commons_enums.DBRows.FUTURE_CONTRACTS.value][self.exchange]
            if self.trading_type == "future"
            else {}
        )
        # init data
        for pair in self.metadata[commons_enums.DBRows.SYMBOLS.value]:
            symbol = symbol_util.parse_symbol(pair).base
            is_inverse_contract = (
                self.trading_type == "future"
                and trading_api.is_inverse_future_contract(
                    trading_enums.FutureContractType(contracts[pair]["contract_type"])
                )
            )
            if symbol != self.ref_market or is_inverse_contract:
                candles_sources = await self.run_database.get_symbol_db(
                    self.exchange, pair
                ).all(commons_enums.DBTables.CANDLES_SOURCE.value)
                if time_frame is None:
                    time_frames = [
                        source[commons_enums.DBRows.TIME_FRAME.value]
                        for source in candles_sources
                    ]
                    time_frame = (
                        time_frame_manager.find_min_time_frame(time_frames)
                        if time_frames
                        else time_frame
                    )
                if with_candles and pair not in self.price_data:
                    try:
                        self.price_data[pair] = await self._get_candles(
                            candles_sources, pair, time_frame
                        )
                    except KeyError as error:
                        raise CandlesLoadingError(
                            f"Unable to load {pair}/{time_frames} candles"
                        ) from error
                if with_trades and pair not in self.trades_data:
                    self.trades_data[pair] = await self.get_trades(pair)
            if with_portfolio:
                try:
                    self.moving_portfolio_data[symbol] = self.starting_portfolio[
                        symbol
                    ][octobot_commons.constants.PORTFOLIO_TOTAL]
                except KeyError:
                    self.moving_portfolio_data[symbol] = 0
                try:
                    self.moving_portfolio_data[
                        self.ref_market
                    ] = self.starting_portfolio[self.ref_market][
                        octobot_commons.constants.PORTFOLIO_TOTAL
                    ]
                except KeyError:
                    self.moving_portfolio_data[self.ref_market] = 0

    async def _get_candles(self, candles_sources, pair, time_frame) -> list:
        if (
            candles_sources[0][commons_enums.DBRows.VALUE.value]
            == octobot_commons.constants.LOCAL_BOT_DATA
        ):

            return self._get_live_candles(pair, time_frame)
        else:
            return await self._get_backtesting_candles(candles_sources, pair, time_frame)

    def _get_live_candles(self, symbol, time_frame):
        # todo get/download history from first tradetime or start time
        # todo multi exchange
        exchange_manager = trading_api.get_exchange_manager_from_exchange_id(
            get_exchange_ids()[0]
        )
        _raw_candles = trading_api.get_symbol_historical_candles(
            trading_api.get_symbol_data(exchange_manager, symbol, allow_creation=False),
            time_frame,
        )
        raw_candles = []
        for index in range(len(_raw_candles[0])):
            raw_candles.append(
                [
                    # convert candles timestamp in millis
                    _raw_candles[commons_enums.PriceIndexes.IND_PRICE_TIME.value][index]
                    * 1000,
                    _raw_candles[commons_enums.PriceIndexes.IND_PRICE_OPEN.value][
                        index
                    ],
                    _raw_candles[commons_enums.PriceIndexes.IND_PRICE_HIGH.value][
                        index
                    ],
                    _raw_candles[commons_enums.PriceIndexes.IND_PRICE_LOW.value][index],
                    _raw_candles[commons_enums.PriceIndexes.IND_PRICE_CLOSE.value][
                        index
                    ],
                    _raw_candles[commons_enums.PriceIndexes.IND_PRICE_VOL.value][index],
                ]
            )
        return raw_candles

    async def _get_backtesting_candles(self, candles_sources, symbol, time_frame):
        raw_candles = await backtesting_api.get_all_ohlcvs(
            candles_sources[0][commons_enums.DBRows.VALUE.value],
            self.exchange,
            symbol,
            commons_enums.TimeFrames(time_frame),
            inferior_timestamp=self.metadata[commons_enums.DBRows.START_TIME.value],
            superior_timestamp=self.metadata[commons_enums.DBRows.END_TIME.value],
        )
        # convert candles timestamp in millis
        for candle in raw_candles:
            candle[commons_enums.PriceIndexes.IND_PRICE_TIME.value] = (
                candle[commons_enums.PriceIndexes.IND_PRICE_TIME.value] * 1000
            )
        return raw_candles

    async def generate_historical_portfolio_value(self):
        if not self.historical_portfolio_values_by_coin:
            if self.trading_type == "future":
                # TODO remove when FuturesBaseDataGenerator is added
                return
            self.historical_portfolio_values_by_coin: dict = {}
            self.historical_portfolio_amounts_by_coin: dict = {}
            self.historical_portfolio_times = [
                candle[commons_enums.PriceIndexes.IND_PRICE_TIME.value]
                for candle in self.longest_candles
            ]
            _tmp_portfolio_history_by_currency = {**self.portfolio_history_by_currency}
            longest_candles_len = len(self.longest_candles)
            for coin in self.portfolio_history_by_currency.keys():
                _this_tmp_portfolio_history = _tmp_portfolio_history_by_currency[coin]
                static_price_data = False
                price_data = None
                if self.ref_market == coin:
                    static_price_data = True
                else:
                    # handle indirect multi pair conversion
                    try:
                        price_data = self.price_data[f"{coin}/{self.ref_market}"]
                    except KeyError as error:
                        # if coin in self.pairs:

                        # conversion_symbol = f"{parsed_symbol.quote}/{ref_market}"
                        # converion_price = None
                        # if conversion_symbol not in price_data:
                        #     conversion_symbol = f"{ref_market}/{parsed_symbol.quote}"
                        #     if conversion_symbol not in price_data:
                        #         run_analysis_data.get_logger().error(
                        #             f"Unable to handle sell trade {trade['symbol']}, no pair "
                        #             "aivailable to convert value plots "
                        #             f"will not be accurate: {trade}"
                        #         )
                        #         break
                        # conversion_pair = f"{}/{self.ref_market}"
                        get_logger().exception(
                            error,
                            True,
                            f"Unable to get price data for {coin}/{self.ref_market} "
                            "- make sure this pair is enabled for this run - "
                            "Run analysis plots will not be accurate!",
                        )
                        continue
                    candles_len = len(price_data)
                    if longest_candles_len != candles_len:
                        # add 0 values to make all candles the same len
                        price_data = (
                            [[0, 0, 0, 0, 0]] * (longest_candles_len - candles_len)
                        ) + price_data

                self.historical_portfolio_values_by_coin[coin] = []
                self.historical_portfolio_amounts_by_coin[coin] = []
                current_amount = 0
                for index in range(longest_candles_len):
                    if static_price_data:
                        price = 1
                    else:
                        price = price_data[index][
                            commons_enums.PriceIndexes.IND_PRICE_CLOSE.value
                        ]
                    time = self.longest_candles[index][
                        commons_enums.PriceIndexes.IND_PRICE_TIME.value
                    ]
                    # get currency amount closest to current candle time
                    while (
                        len(_this_tmp_portfolio_history)
                        and _this_tmp_portfolio_history[0]["x"] <= time
                    ):
                        current_amount = _this_tmp_portfolio_history[0]["volume"]
                        del _this_tmp_portfolio_history[0]
                    self.historical_portfolio_values_by_coin[coin].append(
                        price * current_amount
                    )
                    self.historical_portfolio_amounts_by_coin[coin].append(
                        current_amount
                    )

            # total value in ref_market
            pairs = list(self.historical_portfolio_amounts_by_coin.keys())
            self.historical_portfolio_values_by_coin["total"] = []
            self.historical_portfolio_amounts_by_coin["total"] = []
            for index in range(longest_candles_len):
                time = self.longest_candles[index][
                    commons_enums.PriceIndexes.IND_PRICE_TIME.value
                ]
                this_candle_value = 0
                for pair in pairs:
                    this_candle_value += self.historical_portfolio_values_by_coin[pair][
                        index
                    ]
                self.historical_portfolio_values_by_coin["total"].append(
                    this_candle_value
                )

    def _set_longest_candles(self) -> list:
        longest_pair = None
        longest_len = 0
        for pair, candles in self.price_data.items():
            if pair not in self.pairs:
                continue
            if (new_len := len(candles)) > longest_len:
                longest_len = new_len
                longest_pair = pair
        self.longest_candles = self.price_data[longest_pair]

    def _read_pnl_from_transactions(
        self,
        x_data,
        pnl_data,
        cumulative_pnl_data,
        x_as_trade_count,
    ):
        previous_value = 0
        for transaction in self.trading_transactions_history:
            transaction_pnl = (
                0
                if transaction["realized_pnl"] is None
                else transaction["realized_pnl"]
            )
            transaction_quantity = (
                0 if transaction["quantity"] is None else transaction["quantity"]
            )
            local_quantity = transaction_pnl + transaction_quantity
            cumulated_pnl = local_quantity + previous_value
            pnl_data.append(local_quantity)
            cumulative_pnl_data.append(cumulated_pnl)
            previous_value = cumulated_pnl
            if x_as_trade_count:
                x_data.append(len(pnl_data) - 1)
            else:
                x_data.append(transaction[commons_enums.PlotAttributes.X.value])

    async def load_realized_pnl(
        self,
        x_as_trade_count=True,
    ):
        # PNL:
        # 1. open position: consider position opening fee from PNL
        # 2. close position: consider closed amount + closing fee into PNL
        # what is a trade ?
        #   futures: when position going to 0 (from long/short) => trade is closed
        #   spot: when position lowered => trade is closed
        if not (self.price_data and next(iter(self.price_data.values()))):
            return
        self.realized_pnl_x_data = [
            0
            if x_as_trade_count
            else next(iter(self.price_data.values()))[0][
                commons_enums.PriceIndexes.IND_PRICE_TIME.value
            ]
        ]
        self.realized_pnl_trade_gains_data = [0]
        self.realized_pnl_cumulative = [0]
        if self.trading_transactions_history:
            # can rely on pnl history
            self._read_pnl_from_transactions(
                self.realized_pnl_x_data,
                self.realized_pnl_trade_gains_data,
                self.realized_pnl_cumulative,
                x_as_trade_count,
            )
            # else:
            #     # recreate pnl history from trades
            #     self._read_pnl_from_trades(
            #         x_data,
            #         pnl_data,
            #         cumulative_pnl_data,
            #         x_as_trade_count,
            #     )

            if not x_as_trade_count:
                # x axis is time: add a value at the end of the axis if missing
                # to avoid a missing values at the end feeling
                last_time_value = next(iter(self.price_data.values()))[-1][
                    commons_enums.PriceIndexes.IND_PRICE_TIME.value
                ]
                if self.realized_pnl_x_data[-1] != last_time_value:
                    # append the latest value at the end of the x axis
                    self.realized_pnl_x_data.append(last_time_value)
                    self.realized_pnl_trade_gains_data.append(0)
                    self.realized_pnl_cumulative.append(
                        self.realized_pnl_cumulative[-1]
                    )

    # async def total_paid_fees(meta_database, all_trades):
    #     paid_fees = 0
    #     fees_currency = None
    #     if trading_transactions_history:
    #         for transaction in trading_transactions_history:
    #             if fees_currency is None:
    #                 fees_currency = transaction["currency"]
    #             if transaction["currency"] != fees_currency:
    #                 get_logger().error(f"Unknown funding fee value: {transaction}")
    #             else:
    #                 # - because funding fees are stored as negative number when paid (positive when "gained")
    #                 paid_fees -= transaction["quantity"]
    #     for trade in all_trades:
    #         currency = symbol_util.parse_symbol(
    #             trade[commons_enums.DBTables.SYMBOL.value]
    #         ).base
    #         if trade[commons_enums.DBTables.FEES_CURRENCY.value] == currency:
    #             if trade[commons_enums.DBTables.FEES_CURRENCY.value] == fees_currency:
    #                 paid_fees += trade[commons_enums.DBTables.FEES_AMOUNT.value]
    #             else:
    #                 paid_fees += (
    #                     trade[commons_enums.DBTables.FEES_AMOUNT.value]
    #                     * trade[commons_enums.PlotAttributes.Y.value]
    #                 )
    #         else:
    #             if trade[commons_enums.DBTables.FEES_CURRENCY.value] == fees_currency:
    #                 paid_fees += (
    #                     trade[commons_enums.DBTables.FEES_AMOUNT.value]
    #                     / trade[commons_enums.PlotAttributes.Y.value]
    #                 )
    #             else:
    #                 paid_fees += trade[commons_enums.DBTables.FEES_AMOUNT.value]
    #     return paid_fees

    def generate_wins_and_losses(self, x_as_trade_count):
        if not (self.wins_and_losses_x_data and self.wins_and_losses_data):
            if not (self.price_data and next(iter(self.price_data.values()))):
                return
            if self.trading_transactions_history:
                # can rely on pnl history
                for transaction in self.trading_transactions_history:
                    transaction_pnl = (
                        0
                        if transaction["realized_pnl"] is None
                        else transaction["realized_pnl"]
                    )
                    current_cumulative_wins = (
                        self.wins_and_losses_data[-1]
                        if self.wins_and_losses_data
                        else 0
                    )
                    if transaction_pnl < 0:
                        self.wins_and_losses_data.append(current_cumulative_wins - 1)
                    elif transaction_pnl > 0:
                        self.wins_and_losses_data.append(current_cumulative_wins + 1)
                    else:
                        continue

                    if x_as_trade_count:
                        self.wins_and_losses_x_data.append(
                            len(self.wins_and_losses_data) - 1
                        )
                    else:
                        self.wins_and_losses_x_data.append(
                            transaction[commons_enums.PlotAttributes.X.value]
                        )

    def generate_win_rates(self, x_as_trade_count):
        if not (self.win_rates_x_data and self.win_rates_data):
            if not (self.price_data and next(iter(self.price_data.values()))):
                return
            if self.trading_transactions_history:
                wins_count = 0
                losses_count = 0

                for transaction in self.trading_transactions_history:
                    transaction_pnl = (
                        0
                        if transaction["realized_pnl"] is None
                        else transaction["realized_pnl"]
                    )
                    if transaction_pnl < 0:
                        losses_count += 1
                    elif transaction_pnl > 0:
                        wins_count += 1
                    else:
                        continue

                    self.win_rates_data.append(
                        (wins_count / (losses_count + wins_count)) * 100
                    )
                    if x_as_trade_count:
                        self.win_rates_x_data.append(len(self.win_rates_data) - 1)
                    else:
                        self.win_rates_x_data.append(
                            transaction[commons_enums.PlotAttributes.X.value]
                        )

    async def get_best_case_growth_from_transactions(
        self,
        x_as_trade_count,
    ):
        if not (self.best_case_growth_x_data and self.best_case_growth_data):
            if not (self.price_data and next(iter(self.price_data.values()))):
                return
            if self.trading_transactions_history:
                (
                    self.best_case_growth_data,
                    _,
                    _,
                    _,
                    self.best_case_growth_x_data,
                ) = await portfolio_util.get_coefficient_of_determination_data(
                    transactions=self.trading_transactions_history,
                    longest_candles=self.longest_candles,
                    start_balance=self.total_start_balance_in_ref_market,
                    use_high_instead_of_end_balance=True,
                    x_as_trade_count=x_as_trade_count,
                )

    async def generate_transactions(self):
        raise NotImplementedError("generate_transactions() must be implemented")


def get_logger(_=None):
    return commons_logging.get_logger("RunAnalysisBaseDataGenerator")


# def _position_factory(symbol, contract_data):
#     # TODO: historical unrealized pnl, maybe find a better solution that this
#     import mock

#     class _TraderMock:
#         def __init__(self):
#             self.exchange_manager = mock.Mock()
#             self.simulate = True

#     contract = trading_exchange_data.FutureContract(
#         symbol,
#         trading_enums.MarginType(contract_data["margin_type"]),
#         trading_enums.FutureContractType(contract_data["contract_type"]),
#     )
#     return trading_personal_data.create_position_from_type(_TraderMock(), contract)




class CandlesLoadingError(Exception):
    """
    raised when unable to load candles
    """
