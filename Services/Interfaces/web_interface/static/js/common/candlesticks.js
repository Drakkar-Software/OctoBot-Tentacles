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

function get_symbol_price_graph(element_id, exchange_id, exchange_name, symbol, time_frame, backtesting=false,
                                replace=false, should_retry=false, attempts=0,
                                data=undefined, success_callback=undefined, no_data_callback=undefined){
    if(isDefined(data)){
        create_or_update_candlestick_graph(element_id, data, symbol, exchange_name, time_frame, replace);
    }else{
        const backtesting_enabled = backtesting ? "backtesting" : "live";
        const ajax_url = "/dashboard/currency_price_graph_update/"+ exchange_id +"/" + symbol + "/"
            + time_frame + "/" + backtesting_enabled;
        $.ajax({
            url: ajax_url,
            type: "GET",
            dataType: "json",
            contentType: 'application/json',
            success: function(data, status){
                if(data !== null && "error" in data && data["error"].includes("no data for")){
                    if(isDefined(no_data_callback)) {
                        no_data_callback(element_id);
                    }
                }else if (!create_or_update_candlestick_graph(element_id, data, symbol, exchange_name, time_frame, replace)){
                    if (should_retry && attempts < max_attempts){
                        const marketsElement = $("#loadingMarketsDiv");
                        marketsElement.removeClass(disabled_item_class);
                        setTimeout(function(){
                            marketsElement.addClass(disabled_item_class);
                            get_symbol_price_graph(element_id, exchange_id, exchange_name, symbol, time_frame, backtesting, replace, should_retry,attempts+1, data, success_callback);
                        }, 3000);
                    }
                }else{
                    const loadingSelector = $("div[name='loadingSpinner']");
                    if (loadingSelector.length) {
                        $.each(loadingSelector, function () {
                            $(this).addClass(disabled_item_class);
                        });
                    }
                    if(isDefined(success_callback)){
                        success_callback();
                    }
                }
            },
            error: function(result, status, error){
                window.console&&console.error(error, result, status);
                const loadingSelector = $("div[name='loadingSpinner']");
                if (loadingSelector.length) {
                    loadingSelector.addClass(hidden_class);
                }
                $(document.getElementById(element_id)).html(`<h7>Error when loading graph: ${error} [${result.responseText}]. More details in logs.</h7>`)
            }
        });
    }
}

function get_first_symbol_price_graph(element_id, in_backtesting_mode=false, callback=undefined) {
    const url = $("#first_symbol_graph").attr(update_url_attr);
    $.get(url,function(data) {
        if($.isEmptyObject(data)){
            // no exchange data available yet, retry soon, bot must be starting
            setTimeout(function(){
                get_first_symbol_price_graph(element_id, in_backtesting_mode, callback);
            }, 300);
        }else{
            if("time_frame" in data){
                let formatted_symbol = data["symbol"].replace(new RegExp("/","g"), "|");
                get_symbol_price_graph(element_id, data["exchange_id"], data["exchange_name"], formatted_symbol,
                    data["time_frame"], in_backtesting_mode, false, true,
                    0, undefined, function () {
                        if(isDefined(callback)){
                            callback(data["exchange_id"], data["symbol"], data["time_frame"], element_id);
                        }
                    });
            }
        }
    });
}

function get_watched_symbol_price_graph(element, callback=undefined, no_data_callback=undefined) {
    const symbol = element.attr("symbol");
    let formatted_symbol = symbol.replace(new RegExp("/","g"), "|");
    const ajax_url = "/dashboard/watched_symbol/"+ formatted_symbol;
    $.get(ajax_url,function(data) {
        if("time_frame" in data){
            let formatted_symbol = data["symbol"].replace(new RegExp("/","g"), "|");
            get_symbol_price_graph(element.attr("id"), data["exchange_id"], data["exchange_name"], formatted_symbol,
                data["time_frame"], false, false, true,
                0, undefined, function () {
                    if(isDefined(callback)){
                        callback(data["exchange_id"], data["symbol"], data["time_frame"], element.attr("id"));
                    }
                }, no_data_callback);
        }else if($.isEmptyObject(data)){
            // OctoBot is starting, try again
            const marketsElement = $("#loadingMarketsDiv");
            marketsElement.removeClass(disabled_item_class);
            setTimeout(function(){
                get_watched_symbol_price_graph(element, callback, no_data_callback);
            }, 1000);
        }
    });
}

const sell_color = "#ff0000";
const buy_color = "#009900";

function create_candlesticks(candles){
    const data_time = candles["time"];
    const data_close = candles["close"];
    const data_high = candles["high"];
    const data_low = candles["low"];
    const data_open = candles["open"];

    return {
      x: data_time,
      close: data_close,
      decreasing: {line: {color: '#F65A33'}},
      high: data_high,
      increasing: {line: {color: '#7DF98D'}},
      line: {color: 'rgba(31,119,180,1)'},
      low: data_low,
      open: data_open,
      type: 'candlestick',
      name: 'Prices',
      xaxis: 'x',
      yaxis: 'y2'
    };
}

function create_volume(candles){

    const data_time = candles["time"];
    const data_close = candles["close"];
    const data_volume = candles["vol"];
    
    const colors = [];
    $.each(data_close, function (i, value) {
        if(i !== 0) {
            if (value > data_close[i - 1]) {
                colors.push(buy_color);
            }else{
                colors.push(sell_color);
            }
        }
        else{
            colors.push(sell_color);
        }

    });

    return {
          x: data_time,
          y: data_volume,
          marker: {
              color: colors
          },
          type: 'bar',
          name: 'Volume',
          xaxis: 'x',
          yaxis: 'y1'
    };
}

function create_trades(trades, trader){

    if (isDefined(trades) && isDefined(trades["time"]) && trades["time"].length > 0) {
        const data_time = trades["time"];
        const data_price = trades["price"];
        const data_trade_description = trades["trade_description"];
        const data_order_side = trades["order_side"];

        const marker_size = trader === "Simulator" ? 14 : 16;
        const marker_opacity = trader === "Simulator" ? 0.5 : 0.65;
        const border_line_color = "#b6b8c3";
        const colors = [];
        $.each(data_order_side, function (index, value) {
            if (value === "sell") {
                colors.push(sell_color);
            } else {
                colors.push(buy_color);
            }
        });

        const line_with = trader === "Simulator" ? 0 : 1;

        return {
            x: data_time,
            y: data_price,
            mode: 'markers',
            name: trader,
            text: data_trade_description,
            marker: {
                color: colors,
                size: marker_size,
                opacity: marker_opacity,
                line: {
                    width: line_with,
					color: border_line_color
                }
            },
            xaxis: 'x',
            yaxis: 'y2'
        }
    }else{
        return {}
    }
}

function update_trades(trades, trader_name, reference_trades){
    if(isDefined(reference_trades) && isDefined(reference_trades.y)){
        if(isDefined(trades.time) && trades.time.length){
            const new_trades = create_trades(trades, trader_name);
            if(new_trades.mode){
                for(let i=0; i<new_trades.x.length; i++){
                    reference_trades.x.push(new_trades.x[i]);
                    reference_trades.y.push(new_trades.y[i]);
                    reference_trades.text.push(new_trades.text[i]);
                    reference_trades.marker.color.push(new_trades.marker.color[i]);
                }
            }
        }
    }else{
        reference_trades = create_trades(trades, trader_name)
    }
    return reference_trades;
}

function update_last_candle(to_update_candles, to_update_vols, new_candles, last_price_trace_index, last_candle_index){
    to_update_candles.open[last_price_trace_index] = new_candles["open"][last_candle_index];
    to_update_candles.high[last_price_trace_index] = new_candles["high"][last_candle_index];
    to_update_candles.low[last_price_trace_index] = new_candles["low"][last_candle_index];
    to_update_candles.close[last_price_trace_index] = new_candles["close"][last_candle_index];
    to_update_vols.y[last_price_trace_index] = new_candles["vol"][last_candle_index];
    const prev_vol_color = new_candles["close"][last_candle_index] >= new_candles["open"][last_candle_index] ?
        buy_color : sell_color;
    to_update_vols.marker.color[last_price_trace_index] = prev_vol_color;
}

function create_layout(graph_title){
    return {
        title: graph_title,
        dragmode: 'zoom',
        margin: {
            r: 10,
            t: 25,
            b: 40,
            l: 60
        },
        showlegend: true,
        xaxis: {
            autorange: true,
            domain: [0, 1],
            title: 'Date',
            type: 'date',
            rangeslider: {
                visible: false,
            }
        },
        yaxis1: {
            domain: [0, 0.2],
            title: 'Volume',
            autorange: true,
            showgrid: false,
            showticklabels: false
        },
        yaxis2: {
            domain: [0.2, 1],
            autorange: true,
            title: 'Price'
        },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: {
            color: "white"
        }
    };
}

function push_new_candle(price_trace, volume_trace, candles, candle_index, last_candle_time){
    price_trace.x.push(last_candle_time);
    price_trace.open.push(candles["open"][candle_index]);
    price_trace.high.push(candles["high"][candle_index]);
    price_trace.low.push(candles["low"][candle_index]);
    price_trace.close.push(candles["close"][candle_index]);
    volume_trace.y.push(candles["vol"][candle_index]);
    const vol_color = candles["close"][candle_index] >= candles["open"][candle_index] ?
        buy_color : sell_color;
    volume_trace.marker.color.push(vol_color);
}

function create_or_update_candlestick_graph(element_id, symbol_price_data, symbol, exchange_name, time_frame, replace=false){
    if (symbol_price_data) {
        const candles = symbol_price_data["candles"];
        const real_trades = symbol_price_data["real_trades"];
        const simulated_trades = symbol_price_data["simulated_trades"];

        let layout = undefined;

        let price_trace = undefined;
        let volume_trace = undefined;

        let real_trader_trades = undefined;
        let simulator_trades = undefined;

        const prev_data = document.getElementById(element_id);
        const prev_layout = prev_data.layout;

        if (prev_layout && !replace) {
            volume_trace = prev_data.data[0];
            price_trace = prev_data.data[1];
            real_trader_trades = prev_data.data[2];
            simulator_trades = prev_data.data[3];

            // keep layout
            layout = prev_layout;
            // update data revision to force graph update
            layout.datarevision = layout.datarevision + 1;

            // trades
            real_trader_trades = update_trades(real_trades, "Real trader", real_trader_trades);
            simulator_trades = update_trades(simulated_trades, "Simulator", simulator_trades);

            // candles
            if(isDefined(candles) && isDefined(candles.time) && candles.time.length){
                const last_price_trace_index = price_trace.close.length - 1;
                const last_candle_index = candles["close"].length - 1;
                const last_candle_time = candles["time"][last_candle_index];

                if (last_candle_index > 0){
                    // Candle update with last candle being and in-construction candle
                    if (price_trace.x[last_price_trace_index] !== last_candle_time) {
                        update_last_candle(price_trace, volume_trace, candles, last_price_trace_index, last_candle_index - 1);
                        push_new_candle(price_trace, volume_trace, candles, last_candle_index, last_candle_time);
                    } else {
                        update_last_candle(price_trace, volume_trace, candles, last_price_trace_index, last_candle_index);
                    }
                } else if(price_trace.x[last_price_trace_index].indexOf(last_candle_time) === -1) {
                    // Candle update with only one candle but this candle is not displayed (no in-construction candle)
                    push_new_candle(price_trace, volume_trace, candles, last_candle_index, last_candle_time);
                }
            }
        }
        if(!isDefined(layout)){
            let graph_title = symbol;
            if (exchange_name !== "ExchangeSimulator") {
                graph_title = graph_title + " (" + exchange_name + ", time frame: " + time_frame + ")";
            }
            layout = create_layout(graph_title);
        }
        if(!isDefined(price_trace)){
            price_trace = create_candlesticks(candles);
        }
        if(!isDefined(volume_trace)){
            volume_trace = create_volume(candles);
        }
        if(!isDefined(real_trader_trades)){
            real_trader_trades = create_trades(real_trades, "Real trader");
        }
        if(!isDefined(simulator_trades)){
            simulator_trades = create_trades(simulated_trades, "Simulator");
        }

        const data = [volume_trace, price_trace, real_trader_trades, simulator_trades];
        const plotlyConfig = {
            scrollZoom: true,
            modeBarButtonsToRemove: ["select2d", "lasso2d", "toggleSpikelines"],
            responsive: true,
            showEditInChartStudio: true,
            displaylogo: false // no logo to avoid 'rel="noopener noreferrer"' security issue (see https://webhint.io/docs/user-guide/hints/hint-disown-opener/)
        };
        if(replace){
            Plotly.newPlot(element_id, data, layout, plotlyConfig);
        }else{
            Plotly.react(element_id, data, layout, plotlyConfig);
        }
        return true;
    }else{
        return false
    }
}
