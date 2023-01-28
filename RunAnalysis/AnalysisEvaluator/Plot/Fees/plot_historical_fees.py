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
from tentacles.RunAnalysis.BaseDataProvider.default_base_data_provider import (
    base_data_provider,
)
import octobot_commons.enums as commons_enums


async def plot_historical_fees(
    run_data: base_data_provider.RunAnalysisBaseDataGenerator,
    plotted_element,
    own_yaxis: bool = True,
    fees_for_each_symbol=False,
    trading_fees=False,
    funding_fees=False,
    total_fees=True,
):
    fees_by_title = calculate_historical_fees(
        run_data,
        trading_fees,
        funding_fees,
        total_fees,
        fees_for_each_symbol,
    )
    for fee_title, data in fees_by_title.items():
        plotted_element.plot(
            mode="scatter",
            x=data["times"],
            y=data["cumulative_fees"],
            title=fee_title,
            own_yaxis=own_yaxis,
            line_shape="hv",
        )
    # if funding_fees and run_data.trading_type == "future":
    #     await run_data.load_grouped_funding_fees()
    #     for currency, fees in run_data.funding_fees_history_by_pair.items():
    #         cumulative_fees = []
    #         previous_fee = 0
    #         for fee in fees:
    #             cumulated_fee = fee["quantity"] + previous_fee
    #             cumulative_fees.append(cumulated_fee)
    #             previous_fee = cumulated_fee
    #         plotted_element.plot(
    #             mode="scatter",
    #             x=[fee[commons_enums.PlotAttributes.X.value] for fee in fees],
    #             y=cumulative_fees,
    #             title=f"{currency} paid funding fees",
    #             own_yaxis=own_yaxis,
    #             line_shape="hv",
    #         )
    # if total_fees:
    #     pass


def calculate_historical_fees(
    run_data: base_data_provider.RunAnalysisBaseDataGenerator,
    trading_fees: bool,
    funding_fees: bool,
    total_fees: bool,
    fees_for_each_symbol: bool,
) -> dict:
    fees_by_title = {}
    for transaction in run_data.trading_transactions_history:
        if trading_fees:
            pass
        if funding_fees:
            pass
        if total_fees:
            pass
        if fees_for_each_symbol:
            pass

    return fees_by_title
