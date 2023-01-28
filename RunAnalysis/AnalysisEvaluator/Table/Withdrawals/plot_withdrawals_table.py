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


async def plot_withdrawals_table(
    run_data: base_data_provider.RunAnalysisBaseDataGenerator, plotted_element
):
    import tentacles.Meta.Keywords.scripting_library.run_analysis.run_analysis_plots as run_analysis_plots
    withdrawal_history = await run_data.load_spot_or_futures_base_data(
        transaction_types=(trading_enums.TransactionType.BLOCKCHAIN_WITHDRAWAL.value,)
    )

    # apply quantity to y for each withdrawal
    for withdrawal in withdrawal_history:
        withdrawal["y"] = withdrawal["quantity"]
    key_to_label = {
        "y": "Quantity",
        "currency": "Currency",
        "side": "Side",
    }
    additional_columns = []

    run_analysis_plots.plot_table_data(
        withdrawal_history,
        plotted_element,
        "Withdrawals",
        key_to_label,
        additional_columns,
        None,
    )
