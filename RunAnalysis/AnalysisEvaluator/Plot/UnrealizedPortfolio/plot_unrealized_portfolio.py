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


async def plot_unrealized_portfolio_value(
    run_data: base_data_provider.RunAnalysisBaseDataGenerator,
    plotted_element,
    own_yaxis: bool = False,
    all_coins_in_ref_market: bool = False,
    all_coins_amounts: bool = False,
):
    await run_data.generate_historical_portfolio_value()
    # TODO remove checks as it should work or break
    if run_data.historical_portfolio_times:
        if all_coins_in_ref_market and run_data.historical_portfolio_values_by_coin:
            for (
                coin,
                portfolio_values,
            ) in run_data.historical_portfolio_values_by_coin.items():
                plotted_element.plot(
                    mode="scatter",
                    x=run_data.historical_portfolio_times,
                    y=portfolio_values,
                    title=f"Unrealized {coin} portfolio value in {run_data.ref_market}",
                    own_yaxis=own_yaxis,
                )
        if all_coins_amounts and run_data.historical_portfolio_amounts_by_coin:
            for (
                coin,
                portfolio_values,
            ) in run_data.historical_portfolio_amounts_by_coin.items():
                plotted_element.plot(
                    mode="scatter",
                    x=run_data.historical_portfolio_times,
                    y=portfolio_values,
                    title=f"Unrealized {coin} portfolio value in {run_data.ref_market}",
                    own_yaxis=own_yaxis,
                )
        elif (
            run_data.historical_portfolio_values_by_coin
            and "total" in run_data.historical_portfolio_values_by_coin
        ):
            plotted_element.plot(
                mode="scatter",
                x=run_data.historical_portfolio_times,
                y=run_data.historical_portfolio_values_by_coin["total"],
                title=f"Unrealized total portfolio value in {run_data.ref_market}",
                own_yaxis=own_yaxis,
            )
