
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

function start_backtesting(request, update_url){
    send_and_interpret_bot_update(request, update_url, null, start_success_callback, start_error_callback);
}

function start_success_callback(updated_data, update_url, dom_root_element, msg, status){
    $("#progess_bar_anim").css('width', 0+'%').attr("aria-valuenow", 0);
    create_alert("success", msg, "");
}

function start_error_callback(updated_data, update_url, dom_root_element, result, status, error){
    create_alert("error", result.responseText, "");
    $(`#${backtestingMainProgressBar}`).hide();
    lock_interface(false);
}

function lock_interface(lock=true){
    let should_lock = lock;
    if(!should_lock){
        lock_interface_callbacks.forEach(function (value) {
            if(value()){
                should_lock = true;
            }
        });
    }
    $('#startBacktesting').prop('disabled', should_lock);
}

function load_report(report, should_alert=False) {
    const reportDiv = $("#backtestingReport");
    if (reportDiv.length) {
        const url = reportDiv.attr(update_url_attr);
        $.get(url, function (data) {
            if ("bot_report" in data) {
                report.show();
                const profitabilities = [];
                const show_exchanges = Object.keys(data["bot_report"]["profitability"]).length > 1;
                $.each(data["bot_report"]["profitability"], function (exchange, profitability) {
                    const exch = show_exchanges ? `${exchange}: ` : "";
                    profitabilities.push(`${exch}${profitability}`);
                });
                let profitability = profitabilities.join(", ");
                const errors_count = data["errors_count"];
                if ("error" in data || errors_count > 0) {
                    let error_message = "Warning: error(s) during backtesting";
                    if ("error" in data) {
                        error_message += " " + data["error"];
                    }
                    if (errors_count > 0) {
                        error_message += " " + errors_count + " error(s)";
                    }
                    error_message += ", more details in logs.";
                    profitability = profitability + " " + error_message;
                    if (should_alert) {
                        create_alert("error", error_message, "");
                    }
                    $("#backtestingErrorsAlert").show();
                } else {
                    $("#backtestingErrorsAlert").hide();
                }

                const symbol_reports = [];
                $.each(data["symbol_report"], function (index, value) {
                    $.each(value, function (symbol, profitability) {
                        symbol_reports.push(`${symbol}: ${round_digits(profitability, 4)}%`);
                    });
                });
                const all_profitability = symbol_reports.join(", ");
                $("#bProf").html(`${round_digits(profitability, 4)}%`);
                const avg_profitabilities = [];
                $.each(data["bot_report"]["market_average_profitability"], function (exchange, market_average_profitability) {
                    const exch = show_exchanges ? `${exchange}: ` : "";
                    avg_profitabilities.push(`${exch}${round_digits(market_average_profitability, 4)}%`);
                });
                $("#maProf").html(avg_profitabilities.join(", "));
                $("#refM").html(data["bot_report"]["reference_market"]);
                $("#sProf").html(all_profitability);
                $("#reportTradingModeName").html(data["bot_report"]["trading_mode"]);
                $("#reportTradingModeNameLink").attr("href", $("#reportTradingModeNameLink").attr("base_href") + data["bot_report"]["trading_mode"]);
                const end_portfolio_reports = [];
                $.each(data["bot_report"]["end_portfolio"], function (exchange, portfolio) {
                    let exchange_portfolio = show_exchanges ? `${exchange} ` : "";
                    $.each(portfolio, function (symbol, holdings) {
                        const digits = holdings["total"] > 10 ? 2 : 10;
                        exchange_portfolio = `${exchange_portfolio} ${symbol}: ${round_digits(holdings["total"], digits)}`;
                    });
                    end_portfolio_reports.push(exchange_portfolio);
                });
                $("#ePort").html(end_portfolio_reports.join(", "));
                const starting_portfolio_reports = [];
                $.each(data["bot_report"]["starting_portfolio"], function (exchange, portfolio) {
                    let exchange_portfolio = show_exchanges ? `${exchange} ` : "";
                    $.each(portfolio, function (symbol, holdings) {
                        exchange_portfolio = `${exchange_portfolio} ${symbol}: ${holdings["total"]}`;
                    });
                    starting_portfolio_reports.push(exchange_portfolio);
                });
                $("#sPort").html(starting_portfolio_reports.join(", "));

                add_graphs(data["chart_identifiers"]);
            }
        }).fail(function () {
            report.hide();
        }).always(function () {
            report.attr("loading", "false");
        });
    }
}


function add_graphs(chart_identifiers){
    const result_graph_id = "result-graph-";
    const graph_symbol_price_id = "graph-symbol-price-";
    const result_graphs = $("#result-graphs");
    result_graphs.empty();
    $.each(chart_identifiers, function (_, chart_identifier) {
        const target_template = $("#"+result_graph_id+config_default_value);
        const symbol = chart_identifier["symbol"];
        const exchange_id = chart_identifier["exchange_id"];
        const exchange_name = chart_identifier["exchange_name"];
        const time_frame = chart_identifier["time_frame"];
        const graph_card = target_template.html().replace(new RegExp(config_default_value,"g"), exchange_id+symbol);
        result_graphs.append(graph_card);
        const formated_symbol = symbol.replace(new RegExp("/","g"), "|");
        get_symbol_price_graph(`${graph_symbol_price_id}${exchange_id}${symbol}`, exchange_id, exchange_name, formated_symbol, time_frame, true);
    })
}

function updateBacktestingProgress(progress){
    updateProgressBar("progess_bar_anim", progress);
}

function refreshBacktestingStatus(){
    backtestingSocket.emit('backtesting_status');
}

function init_backtesting_status_websocket(){
    backtestingSocket = get_websocket("/backtesting");
    backtestingSocket.on('backtesting_status', function(backtesting_status_data) {
        _handle_backtesting(backtesting_status_data);
    });
}

function _handle_backtesting(backtesting_status_data){
    const backtesting_status = backtesting_status_data["status"];
    const progress = backtesting_status_data["progress"];

    const report = $("#backtestingReport");
    const progress_bar = $(`#${backtestingMainProgressBar}`);
    const stopButton = $("#backtester-stop-button");

    if(backtesting_status === "computing" || backtesting_status === "starting"){
        lock_interface(true);
        progress_bar.show();
        if(stopButton.length){
            stopButton.removeClass(hidden_class);
        }
        updateBacktestingProgress(progress);
        first_refresh_state = backtesting_status;
        if(report.is(":visible")){
            report.hide();
        }
        backtesting_computing_callbacks.forEach((callback) => callback());
        // re-schedule progress refresh
        setTimeout(function () {refreshBacktestingStatus()}, 50);
    }
    else{
        lock_interface(false);
        progress_bar.hide();
        if(stopButton.length){
            stopButton.addClass(hidden_class);
        }
        if(backtesting_status === "finished"){
            const should_alert = first_refresh_state !== "" && first_refresh_state !== "finished";
            if(should_alert){
                create_alert("success", "Backtesting finished.", "");
                first_refresh_state="finished";
            }
            if(!report.is(":visible") && report.attr("loading") === "false"){
                report.attr("loading", "true");
                load_report(report, should_alert);
            }

            if(previousBacktestingStatus === "computing") {
                backtesting_done_callbacks.forEach((callback) => callback());
            }
        }
    }
    if(first_refresh_state === ""){
        first_refresh_state = backtesting_status;
    }
    previousBacktestingStatus = backtesting_status;
}

let first_refresh_state = "";

let backtestingSocket = undefined;
const lock_interface_callbacks = [];
const backtesting_done_callbacks = [];
const backtesting_computing_callbacks = [];
let previousBacktestingStatus = undefined;
let backtestingMainProgressBar = "backtesting_progress_bar";
