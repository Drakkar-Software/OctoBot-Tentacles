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

function addOrRemoveWatchedSymbol(event){
    const sourceElement = $(event.target);
    const symbol = sourceElement.attr("symbol");
    let action = "add";
    if(sourceElement.hasClass("fas")){
        action = "remove";
    }
    const request = {};
    request["action"]=action;
    request["symbol"]=symbol;
    const update_url = sourceElement.attr("update_url");
    send_and_interpret_bot_update(request, update_url, sourceElement, watched_symbols_success_callback, watched_symbols_error_callback)
}

function watched_symbols_success_callback(updated_data, update_url, dom_root_element, msg, status){
    create_alert("success", msg, "");
    if(updated_data["action"] === "add"){
        dom_root_element.removeClass("far");
        dom_root_element.addClass("fas");
    }else{
        dom_root_element.removeClass("fas");
        dom_root_element.addClass("far");
    }
}

function watched_symbols_error_callback(updated_data, update_url, dom_root_element, result, status, error){
    create_alert("error", result.responseText, "");
}

function update_pairs_colors(){
    $(".pair_status_card").each(function () {
        const first_eval = $(this).find(".status");
        const status = first_eval.attr("status");
        if(status.toLowerCase().includes("very long")){
            $(this).addClass("card-very-long");
        }else if(status.toLowerCase().includes("long")){
            $(this).addClass("card-long");
        }else if(status.toLowerCase().includes("very short")){
            $(this).addClass("card-very-short");
        }else if(status.toLowerCase().includes("short")){
            $(this).addClass("card-short");
        }
    })
}

function get_displayed_orders_desc(){
    const orders_desc = [];
    ordersDataTable.rows({filter: 'applied'}).data().each(function (value) {
        orders_desc.push($(value[cancelButtonIndex]).attr("order_desc"));
    });
    return orders_desc;
}

function handle_cancel_buttons() {
    $("#cancel_all_orders").click(function () {
        $("#ordersCount").text(ordersDataTable.rows({filter: 'applied'}).data().length);
        const to_cancel_orders = get_displayed_orders_desc();
        cancel_after_confirm($('#CancelAllOrdersModal'), to_cancel_orders, $(this).attr(update_url_attr), true);
    });
}

function handle_close_buttons() {
    $("button[data-action=close_position]").each(function () {
        $(this).click(function () {
            close_after_confirm($('#ClosePositionModal'), $(this).data("position_symbol"),
                $(this).data("position_side"), $(this).data("update-url"));
        });
    });
}

function cancel_after_confirm(modalElement, data, update_url, disable_cancel_buttons=false){
    modalElement.modal("toggle");
    const confirmButton = modalElement.find(".btn-danger");
    confirmButton.off("click");
    modalElement.keypress(function(e) {
        if(e.which === 13) {
            handle_confirm(modalElement, confirmButton, data, update_url, disable_cancel_buttons);
        }
    });
    confirmButton.click(function () {
        handle_confirm(modalElement, confirmButton, data, update_url, disable_cancel_buttons);
    });
}

function close_after_confirm(modalElement, symbol, side, update_url){
    modalElement.modal("toggle");
    const confirmButton = modalElement.find(".btn-danger");
    confirmButton.off("click");
    const data = {
        symbol: symbol,
        side: side,
    }
    modalElement.keypress(function(e) {
        if(e.which === 13) {
            handle_close_confirm(modalElement, confirmButton, data, update_url);
        }
    });
    confirmButton.click(function () {
        handle_close_confirm(modalElement, confirmButton, data, update_url);
    });
}

function handle_close_confirm(modalElement, confirmButton, data, update_url){
    send_and_interpret_bot_update(data, update_url, null, orders_request_success_callback, position_request_failure_callback);
    modalElement.unbind("keypress");
    modalElement.modal("hide");
}

function handle_confirm(modalElement, confirmButton, data, update_url, disable_cancel_buttons){
    if (disable_cancel_buttons){
        disable_cancel_all_buttons();
    }
    send_and_interpret_bot_update(data, update_url, null, orders_request_success_callback, orders_request_failure_callback);
    modalElement.unbind("keypress");
    modalElement.modal("hide");
}

function add_cancel_individual_orders_button(){
    $("button[action=cancel_order]").each(function () {
        $(this).click(function () {
            cancel_after_confirm($('#CancelOrderModal'), $(this).attr("order_desc"), $(this).attr(update_url_attr));
        });
    });
}

function disable_cancel_all_buttons(){
    $("#cancel_all_orders").prop("disabled",true);
    $("#cancel_order_progress_bar").show();
    const cancelIcon = $("#cancel_all_icon");
    cancelIcon.removeClass("fas fa-ban");
    cancelIcon.addClass("fa fa-spinner fa-spin");
    $("button[action=cancel_order]").each(function () {
        $(this).prop("disabled",true);
    });
}

function orders_request_success_callback(updated_data, update_url, dom_root_element, msg, status) {
    if(msg.hasOwnProperty("title")){
        create_alert("success", msg["title"], msg["details"]);
    }else{
        create_alert("success", msg, "");
    }
    reloadDisplay(true);
}

function orders_request_failure_callback(updated_data, update_url, dom_root_element, msg, status) {
    create_alert("error", msg.responseText, "");
    reload_orders(true);
}

function position_request_failure_callback(updated_data, update_url, dom_root_element, msg, status) {
    create_alert("error", msg.responseText, "");
}


const _displaySort = (data, type) => {
    if (type === 'display') {
        return data.display
    }
    return data.sort;
}

const reload_positions = async (update) => {
    const table = $("#positions-table");
    const url = table.data("url");
    const closePositionUrl = table.data("close-url");
    const positions = await async_send_and_interpret_bot_update(null, url, null, "GET")
    $("#positions-waiter").hide();
    const rows = positions.map((element) => {
        return [
            `${element.side.toUpperCase()} ${element.contract}`,
            round_digits(element.amount, 5),
            {display: `${round_digits(element.value, 5)} ${element.market}`, sort: element.value},
            round_digits(element.entry_price, 8),
            round_digits(element.liquidation_price, 8),
            {display: `${round_digits(element.margin, 5)} ${element.market}`, sort: element.margin},
            {display: `${round_digits(element.unrealized_pnl, 5)} ${element.market}`, sort: element.unrealized_pnl},
            element.exchange,
            element.SoR,
            {symbol: element.symbol, side: element.side},
        ]
    });
    let previousSearch = undefined;
    let previousOrder = undefined;
    if (update) {
        const previousDataTable = table.DataTable();
        previousSearch = previousDataTable.search();
        previousOrder = previousDataTable.order();
        previousDataTable.destroy();
    }
    table.DataTable({
        data: rows,
        columns: [
            {title: "Contract"},
            {title: "Size"},
            {title: "Value", render: _displaySort},
            {title: "Entry price"},
            {title: "Liquidation price"},
            {title: "Position margin", render: _displaySort},
            {title: "Unrealized PNL", render: _displaySort},
            {title: "Exchange"},
            {title: "#"},
            {
                title: "Close",
                render: (data, type) => {
                    if (type === 'display') {
                        return `<button type="button" class="btn btn-sm btn-outline-danger waves-effect" 
                                       data-action="close_position" data-position_symbol=${data.symbol} 
                                       data-position_side="${data.side}"
                                       data-update-url="${closePositionUrl}">
                                       <i class="fas fa-ban"></i></button>`
                    }
                    return data;
                },
            },
        ],
        paging: false,
        search: {
            search: previousSearch,
        },
        order: previousOrder,
    });
    handle_close_buttons();
}

const reload_trades = async (update) => {
    const table = $("#trades-table");
    const url = table.data("url");
    const trades = await async_send_and_interpret_bot_update(null, url, null, "GET")
    $("#trades-waiter").hide();
    const rows = trades.map((element) => {
        return [
            element.symbol,
            element.type,
            round_digits(element.price, 8),
            round_digits(element.amount, 8),
            element.exchange,
            {display: `${round_digits(element.cost, 5)} ${element.market}`, sort: element.cost},
            {display: `${round_digits(element.fee_cost, 5)} ${element.fee_currency}`, sort: element.fee_cost},
            {display: element.date, sort: element.time},
            element.id,
            element.SoR,
        ]
    });
    let previousSearch = undefined;
    let previousOrder = [[7, "desc"]];
    if (update) {
        const previousDataTable = table.DataTable();
        previousSearch = previousDataTable.search();
        previousOrder = previousDataTable.order();
        previousDataTable.destroy();
    }
    table.DataTable({
        data: rows,
        columns: [
            {title: "Pair"},
            {title: "Type"},
            {title: "Price"},
            {title: "Quantity"},
            {title: "Exchange"},
            {title: "Total", render: _displaySort},
            {title: "Fee", render: _displaySort},
            {title: "Execution", render: _displaySort},
            {title: "ID"},
            {title: "#"},
        ],
        paging: true,
        search: {
            search: previousSearch,
        },
        order: previousOrder,
    });
    handle_close_buttons();
}

const reload_orders = async (update) => {
    const table = $("#orders-table");
    const url = table.data("url");
    const cancelOrderUrl = table.data("cancel-url");
    const orders = await async_send_and_interpret_bot_update(null, url, null, "GET")
    $("#orders-waiter").hide();
    const rows = orders.map((element) => {
        return [
            element.symbol,
            element.type,
            round_digits(element.price, 8),
            round_digits(element.amount, 8),
            element.exchange,
            {display: element.date, sort: element.time},
            {display: `${round_digits(element.cost, 8)} ${element.market}`, sort: element.cost},
            element.SoR,
            element.id,
            element.id,
        ]
    });
    let previousSearch = undefined;
    let previousOrder = undefined;
    if(update){
        const previousDataTable = table.DataTable();
        previousSearch = previousDataTable.search();
        previousOrder = previousDataTable.order();
        previousDataTable.destroy();
    }
    table.DataTable({
        data: rows,
        columns: [
            { title: "Pair" },
            { title: "Type" },
            { title: "Price" },
            { title: "Quantity" },
            { title: "Exchange" },
            { title: "Date", render: _displaySort },
            { title: "Total", render: _displaySort },
            { title: "#" },
            {
                title: "Cancel",
                render: function (data, type) {
                    if (type === 'display') {
                       return `<button type="button" class="btn btn-sm btn-outline-danger waves-effect" 
                                       action="cancel_order" order_desc="${ data }" 
                                       update-url="${cancelOrderUrl}">
                                       <i class="fas fa-ban"></i></button>`
                    }
                    return data;
                },
            },
        ],
        paging: false,
        search: {
            search: previousSearch,
        },
        order: previousOrder,
    });
    add_cancel_individual_orders_button();
    const cancelIcon = $("#cancel_all_icon");
    $("#cancel_order_progress_bar").hide();
    if(cancelIcon.hasClass("fa-spinner")){
        cancelIcon.removeClass("fa fa-spinner fa-spin");
        cancelIcon.addClass("fas fa-ban");
    }
    if ($("button[action=cancel_order]").length === 0){
        $("#cancel_all_orders").prop("disabled", true);
    }else{
        $("#cancel_all_orders").prop("disabled", false);
    }
}

function ordersNotificationCallback(title, _) {
    if(title.toLowerCase().indexOf("order") !== -1){
        debounce(function() {
            reloadDisplay(true);
        }, 500);
    }
}

const cancelButtonIndex = 8;
let ordersDataTable = null;
let positionsDataTable = null;

const reloadDisplay = async (update) => {
    await Promise.all([
        reload_orders(update),
        reload_positions(update),
        reload_trades(update),
    ]);
}

$(document).ready(async () => {
    update_pairs_colors();
    $(".watched_element").each(function () {
        $(this).click(addOrRemoveWatchedSymbol);
    });
    handle_cancel_buttons();
    register_notification_callback(ordersNotificationCallback);
    await reloadDisplay(false)
});
