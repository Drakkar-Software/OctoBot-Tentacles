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
import tentacles.RunAnalysis.BaseDataProvider.default_base_data_provider.base_data_provider as base_data_provider
import octobot_trading.enums as trading_enums


async def plot_positions_table(
    run_data: base_data_provider.RunAnalysisBaseDataGenerator, plotted_element
):
    import tentacles.Meta.Keywords.scripting_library.run_analysis.run_analysis_plots as run_analysis_plots
    realized_pnl_history = await run_data.load_spot_or_futures_base_data(
        transaction_types=(
            trading_enums.TransactionType.REALIZED_PNL.value,
            trading_enums.TransactionType.CLOSE_REALIZED_PNL.value,
        )
    )
    key_to_label = {
        "x": "Exit time",
        "first_entry_time": "Entry time",
        "average_entry_price": "Average entry price",
        "average_exit_price": "Average exit price",
        "cumulated_closed_quantity": "Cumulated closed quantity",
        "realized_pnl": "Realized PNL",
        "side": "Side",
        "trigger_source": "Closed by",
    }

    run_analysis_plots.plot_table_data(
        realized_pnl_history, plotted_element, "Positions", key_to_label, [], None
    )
