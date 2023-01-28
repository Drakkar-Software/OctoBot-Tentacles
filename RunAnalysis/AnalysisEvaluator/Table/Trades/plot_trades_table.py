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
import octobot_commons.enums as commons_enums


async def plot_trades_table(meta_database, plotted_element):
    import tentacles.Meta.Keywords.scripting_library.run_analysis.run_analysis_plots as run_analysis_plots
    data = await meta_database.get_trades_db().all(commons_enums.DBTables.TRADES.value)
    key_to_label = {
        "y": "Price",
        "type": "Type",
        "side": "Side",
    }
    additional_columns = [
        {"field": "total", "label": "Total", "render": None},
        {"field": "fees", "label": "Fees", "render": None},
    ]

    def datum_columns_callback(datum):
        datum["total"] = datum["cost"]
        datum["fees"] = f'{datum["fees_amount"]} {datum["fees_currency"]}'

    run_analysis_plots.plot_table_data(
        data,
        plotted_element,
        commons_enums.DBTables.TRADES.value,
        key_to_label,
        additional_columns,
        datum_columns_callback,
    )
