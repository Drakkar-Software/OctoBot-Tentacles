/*
 * Drakkar-Software OctoBot
 * Copyright (c) Drakkar-Software, All rights reserved.
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 3.0 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library.
 */

const loadPnlFullChartHistory = (data, update) => {
    const unit = $("#pnl_historyChart").data("unit");
    const parentDiv = $(`#trading-pnl-history`);
    if(data.length > 1){
        parentDiv.removeClass(hidden_class);
        let total_pnl = 0;
        const chartedData = data.map((element) => {
            total_pnl += element.pnl;
            return {
                time: element.t,
                y1: total_pnl,
                y2: element.pnl_p,
            }
        })
        create_histogram_chart(
            document.getElementById("pnl_historyChart"), chartedData, `cumulated ${unit}`, "% change", 'white', update
        );
    }else{
        parentDiv.addClass(hidden_class);
    }
}

const loadPnlTableHistory = (data) => {
    let total_pnl = 0;
    const rows = data.map((element) => {
        total_pnl += element.pnl;
        return [
            {timestamp: element.t, date: element.d},
            element.pnl,
            round_digits(element.pnl_p, 2),
            round_digits(element.pnl_a, 8),
            round_digits(total_pnl, 8),
        ]
    });
    log("rows", rows)
    const pnlTable = $("#pnl_historyTable");
    const unit = pnlTable.data("unit");
    pnlTable.DataTable({
        data: rows.reverse(),
        columns: [
            {
                title: 'Closing time',
                render: {
                    "_": "date",
                    "sort": "timestamp"  // not working for unknown reasons
                }
            },
            { title: `${unit} Profit and Loss` },
            { title: '% Profit and Loss' },
            { title: `${unit} traded volume` },
            { title: `Cumulated ${unit} Profit and Loss` },
        ],
        ordering: false,
    });
}

const fetchPnlHistory = async () => {
    const url = $("#pnl_historyChart").data("url");
    return await async_send_and_interpret_bot_update(null, url, null, "GET")
}
