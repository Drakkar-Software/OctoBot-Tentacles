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
    const parentDiv = $(`#pnl_historyChart`);
    if(data.length > 1){
        parentDiv.removeClass(hidden_class);
        let total_pnl = 0;
        const chartedData = data.map((element) => {
            total_pnl += element.pnl;
            return {
                time: element.t,
                y1: total_pnl,
                y2: element.pnl,
            }
        })
        create_histogram_chart(
            document.getElementById("pnl_historyChart"), chartedData, `cumulated profit/loss`, "profit/loss", unit, 'white', false
        );
    }else{
        parentDiv.addClass(hidden_class);
    }
}

const loadPnlTableHistory = (data, update) => {
    let total_pnl = 0;
    const rows = data.map((element) => {
        total_pnl += element.pnl;
        return [
            {timestamp: element.t, date: element.d},
            round_digits(element.pnl, 8),
            round_digits(total_pnl, 8),
            round_digits(element.pnl_a, 8),
        ]
    });
    const pnlTable = $("#pnl_historyTable");
    const unit = pnlTable.data("unit");
    let previousOrder = [[0, "desc"]];
    if(update){
        const previousDatatable = pnlTable.DataTable();
        previousOrder = previousDatatable.order();
        previousDatatable.destroy();
    }
    pnlTable.DataTable({
        data: rows.reverse(),
        columns: [
            {
                title: 'Closing time',
                render: (data, type) => {
                    if (type === 'display') {
                        return data.date
                    }
                    return data.timestamp;
                },
            },
            { title: `${unit} Profit and Loss` },
            { title: `Cumulated ${unit} Profit and Loss` },
            { title: `${unit} traded volume` },
        ],
        order: previousOrder,
    });
}

const fetchPnlHistory = async (scale) => {
    const url = $("#pnl_historyChart").data("url");
    if(typeof url === "undefined"){
        return [];
    }
    return await async_send_and_interpret_bot_update(null, `${url}${scale}`, null, "GET")
}
