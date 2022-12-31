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

let bot_simulated_profitability = undefined;
let simulated_no_trade_profitability = undefined;
let bot_real_profitability = undefined;
let real_no_trade_profitability = undefined;
let market_profitability = undefined;
let profitability_chart = undefined;

function _refresh_profitability(socket) {
    socket.emit('profitability');
    waiting_profitability_update = false;
}

function handle_profitability(socket) {
    socket.on("profitability", function (data) {
        bot_simulated_profitability = data["bot_simulated_profitability"];
        simulated_no_trade_profitability = data["simulated_no_trade_profitability"];
        bot_real_profitability = data["bot_real_profitability"];
        real_no_trade_profitability = data["real_no_trade_profitability"];
        market_profitability = data["market_average_profitability"];
        if (is_worth_displaying_profitability()) {
            $("#graph-profitability-description").html("");
            display_profitability("graph-profitability");
        } else {
            $("#graph-profitability-description").html("<h4>Nothing to display yet: profitability is 0 for the moment.</h4>");
        }
        if (!waiting_profitability_update) {
            // re-schedule profitability refresh
            waiting_profitability_update = true;
            setTimeout(function () {
                _refresh_profitability(socket);
            }, profitability_graph_update_interval);
        }
    })
}

function should_display_profitability(profitability) {
    return isDefined(profitability) && (isDefined(profitability_chart) || Math.abs(profitability) >= 0.2);
}

function is_worth_displaying_profitability() {
    return (
        should_display_profitability(bot_simulated_profitability)
        || should_display_profitability(bot_real_profitability)
        || should_display_profitability(market_profitability)
    );
}

function fill_profitabiliy_bar(profitability, reference_profitability, label, labels, backgroundColors, borderColor, profitabilities, color_theme) {
    if (isDefined(profitability)) {
        let color = ['rgba(255, 99, 132, 0.2)', 'rgba(255, 99, 132, 1)']; //red
        if (color_theme === "wallet") {
            color = ['rgba(255, 99, 132, 0.2)', 'rgba(255, 99, 132, 1)']; //red
            if (profitability >= reference_profitability) {
                color = ['rgba(75, 192, 192, 0.2)', 'rgba(75, 192, 192, 1)']; //blue
            }
        } else {
            color = ['rgba(197, 202, 233, 0.2)', 'rgba(255, 99, 132, 1)'];  //gray_red_border
            if (profitability >= reference_profitability) {
                color = ['rgba(197, 202, 233, 0.2)', 'rgba(75, 192, 192, 1)']; //gray_blue_border
            }
        }
        labels.push(label);
        backgroundColors.push(color[0]);
        borderColor.push(color[1]);
        profitabilities.push(profitability);
    }
}

function display_profitability(element_id) {
    if (isDefined(market_profitability)) {
        const labels = [];
        const backgroundColors = [];
        const borderColor = [];
        const profitabilities = [];
        fill_profitabiliy_bar(bot_real_profitability, real_no_trade_profitability, "Current Real Portfolio", labels, backgroundColors, borderColor, profitabilities, "wallet");
        fill_profitabiliy_bar(real_no_trade_profitability, market_profitability, "Initial Real Portfolio", labels, backgroundColors, borderColor, profitabilities, "wallet");
        fill_profitabiliy_bar(bot_simulated_profitability, simulated_no_trade_profitability, "Current Simulated Portfolio", labels, backgroundColors, borderColor, profitabilities, "wallet");
        fill_profitabiliy_bar(simulated_no_trade_profitability, market_profitability, "Initial Simulated Portfolio", labels, backgroundColors, borderColor, profitabilities, "wallet");
        fill_profitabiliy_bar(market_profitability, 0, "Traded symbols average profitability", labels, backgroundColors, borderColor, profitabilities, "market");
        let datasets = [{
            label: '% Profitability',
            data: profitabilities,
            backgroundColor: backgroundColors,
            borderColor: borderColor,
            color: 'white',
            borderWidth: 1
        }];
        if (!isDefined(profitability_chart)) {
            profitability_chart = create_bars_chart($("#graph-profitability")[0], labels, datasets, 0, false);
        } else {
            update_bars_chart(profitability_chart, datasets);
        }
    }
}

function get_in_backtesting_mode() {
    return $("#first_symbol_graph").attr("backtesting_mode") === "True";
}

function init_dashboard_websocket() {
    socket = get_websocket("/dashboard");
}

function get_announcements() {
    const annoncementsAlertDiv = $("#annoncementsAlert");
    $.get({
        url: annoncementsAlertDiv.attr(update_url_attr),
        dataType: "json",
        success: function (msg, status) {
            if (msg) {
                annoncementsAlertDiv.text(msg);
                annoncementsAlertDiv.removeClass(disabled_item_class);
            }
        }
    })
}

function get_version_upgrade() {
    const upgradeVersionAlertDiv = $("#upgradeVersion");
    $.get({
        url: upgradeVersionAlertDiv.attr(update_url_attr),
        dataType: "json",
        success: function (msg, status) {
            if (msg) {
                upgradeVersionAlertDiv.text(msg);
                upgradeVersionAlertDiv.parent().parent().removeClass(disabled_item_class);
            }
        }
    })
}

function handle_graph_update() {
    socket.on('candle_graph_update_data', function (data) {
        update_graph(data);
    });
    socket.on('new_data', function (data) {
        update_graph(data, false);
    });
    socket.on('error', function (data) {
        if ("missing exchange manager" === data) {
            socket.off("candle_graph_update_data");
            socket.off("new_data");
            socket.off("error");
            socket.off("profitability");
            profitability_chart = undefined;
            $('#exchange-specific-data').load(document.URL + ' #exchange-specific-data', function (data) {
                init_graphs();
            });
        }
    });
}

function _find_symbol_details(symbol) {
    let found_update_detail = undefined;
    $.each(update_details, function (i, update_detail) {
        if (update_detail.symbol === symbol) {
            found_update_detail = update_detail;
        }
    })
    return found_update_detail;
}

function update_graph(data, re_update = true) {
    const candle_data = data.data;
    let update_detail = undefined;
    if (isDefined(data.request)) {
        update_detail = data.request;
    } else {
        update_detail = _find_symbol_details(candle_data.symbol);
    }
    if (isDefined(update_detail)) {
        get_symbol_price_graph(update_detail.elem_id, update_details.exchange_id, "",
            "", update_details.time_frame, get_in_backtesting_mode(),
            false, true, 0, candle_data);
        if (re_update) {
            setTimeout(function () {
                socket.emit("candle_graph_update", update_detail);
            }, price_graph_update_interval);
        }
    }
}

function init_updater(exchange_id, symbol, time_frame, elem_id) {
    if (!get_in_backtesting_mode()) {
        const update_detail = {};
        update_detail.exchange_id = exchange_id;
        update_detail.symbol = symbol;
        update_detail.time_frame = time_frame;
        update_detail.elem_id = elem_id;
        update_details.push(update_detail);
        setTimeout(function () {
                if (isDefined(socket)) {
                    socket.emit("candle_graph_update", update_detail);
                }
            },
            3000);
    }
}

function enable_default_graph() {
    $("#first_symbol_graph").removeClass(hidden_class);
    get_first_symbol_price_graph("graph-symbol-price", get_in_backtesting_mode(), init_updater);
}

function no_data_for_graph(element_id) {
    document.getElementById(element_id).parentElement.classList.add(hidden_class);
    if ($(".candle-graph").not(`.${hidden_class}`).length === 0) {
        // enable default graph if no watched symbol graph can be displayed
        enable_default_graph();
    }
}

function init_graphs() {
    update_details = [];
    let useDefaultGraph = true;
    $(".watched-symbol-graph").each(function () {
        useDefaultGraph = false;
        get_watched_symbol_price_graph($(this), init_updater, no_data_for_graph);
    });
    if (useDefaultGraph) {
        enable_default_graph();
    }
    handle_graph_update(socket);
    handle_profitability(socket);
}

let update_details = [];
let waiting_profitability_update = false;

let socket = undefined;

$(document).ready(function () {
    get_announcements();
    get_version_upgrade();
    init_dashboard_websocket();
    init_graphs();
    startTutorialIfNecessary("home");
});
