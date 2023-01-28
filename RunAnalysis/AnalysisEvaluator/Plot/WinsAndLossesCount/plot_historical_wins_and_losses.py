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


def plot_historical_wins_and_losses(
    run_data: base_data_provider.RunAnalysisBaseDataGenerator,
    plotted_element,
    x_as_trade_count: bool = False,
    own_yaxis: bool = True,
):
    run_data.generate_wins_and_losses(x_as_trade_count)
    plotted_element.plot(
        mode="scatter",
        x=run_data.wins_and_losses_x_data,
        y=run_data.wins_and_losses_data,
        x_type="tick0" if x_as_trade_count else "date",
        title="wins and losses count",
        own_yaxis=own_yaxis,
        line_shape="hv",
    )
