const resizeObserver = new ResizeObserver(entries => {
    for (let entry of entries) {
        Plotly.Plots.resize(entry.target);
    }
});

let originalXAxis = {}

function getPlotlyConfig(){
    return {
        scrollZoom: true,
        modeBarButtonsToRemove: ["select2d", "lasso2d", "toggleSpikelines"],
        responsive: true,
        showEditInChartStudio: true,
        displaylogo: false // no logo to avoid 'rel="noopener noreferrer"' security issue (see https://webhint.io/docs/user-guide/hints/hint-disown-opener/)
    };
}

function createChart(chartDetails, chartData, yAxis, xAxis, xaxis_list, yaxis_list){
    const chartedElements = {
      x: chartDetails.x,
      mode: chartDetails.kind,
      type: chartDetails.kind,
      name: chartDetails.title,
    }
    Array("y", "open", "high", "low", "close", "volume").forEach(function (element){
        if(chartDetails[element] !== null){
            chartedElements[element] = chartDetails[element]
        }
    })
    const xaxis = {
        autorange: true,
        rangeslider: {
            visible: false,
        }
    };
    const yaxis = {
        fixedrange: true,
    };
    if(chartDetails.x_type !== null){
        xaxis.type = chartDetails.x_type;
    }
    if(xAxis > 1){
        xaxis.overlaying = "x"
        chartedElements.xaxis= `x${xAxis}`
    }
    if(yAxis > 1){
        yaxis.overlaying = "y"
        yaxis.side = 'right'
        chartedElements.yaxis= `y${yAxis}`
    }
    if(chartDetails.y_type !== null){
        yaxis.type = chartDetails.y_type;
    }
    chartData.push(chartedElements);
    const layout = {
        autosize: true,
        margin: {l: 50, r: 50, b: 15, t: 15, pad: 0},
        showlegend: true,
        legend: {x: 0.01, xanchor: 'left', y: 0.99, yanchor:"top"},
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: {
        color: "white"
        }
    };
    yaxis_list.push(yaxis)
    yaxis_list.forEach(function (axis, i){
        if(i > 0){
            layout[`yaxis${i + 1}`] = axis;
        }else{
            layout.yaxis = axis
        }
    });
    xaxis_list.push(xaxis)
    xaxis_list.forEach(function (axis, i){
        if(i > 0){
            layout[`xaxis${i + 1}`] = axis;
        }else{
            layout.xaxis = axis
        }
    });
    return layout
}

function updateBacktestingChart(data, divID, replot){
    data.data.sub_elements.forEach(function (sub_element) {
        const chartData = [];
        const xaxis_list = [];
        const yaxis_list = [];
        sub_element.data.elements.forEach(function (chartDetails) {
            let yAxis = 1;
            if(chartDetails.own_yaxis){
                yAxis += 1;
            }
            let xAxis = 1;
            if(chartDetails.own_xaxis){
                xAxis += 1;
            }
            const layout = createChart(chartDetails, chartData, yAxis, xAxis, xaxis_list, yaxis_list);
            if (replot) {
                Plotly.react(divID, chartData, layout, getPlotlyConfig())
            } else {
                Plotly.newPlot(divID, chartData, layout, getPlotlyConfig())
            }
        });
    });
}

function displayInputs(elements){
    ["backtesting", "trading"].forEach(function (tab){
        const masterTab = $(`#${tab}-inputs`);
        masterTab.empty();
        elements.data.elements.forEach(function (inputDetails) {
            const divId = inputDetails.title.replaceAll(" ", "-");
            masterTab.append(`<div id="${tab}-${divId}"></div>`)
            new JSONEditor(
                document.getElementById(`${tab}-${divId}`),
                {
                    schema: inputDetails.schema,
                    startval: inputDetails.value,
                    no_additional_properties: true,
                    prompt_before_delete: true,
                    disable_array_reorder: true,
                    disable_collapse: true,
                    disable_properties: true
                }
            );
        });
    })
}


function updateChartsAndInputs(data, replot){
    let mainLayout = undefined;
    if(data.data.sub_elements.length <= 1){
        $("#main-chart").resizable("option", "disabled", true );
    }
    if(data.data.sub_elements.length <= 2){
        $("#main-chart").addClass("max-width");
    }
    if(data.data.sub_elements.length > 2){
        $("#main-chart").removeClass("max-width");
    }
    data.data.sub_elements.forEach(function (sub_element) {
        if(sub_element.name == "inputs") {
            displayInputs(sub_element)
        }else {
            const chartData = [];
            const xaxis_list = [];
            const yaxis_list = [];
            const divID = sub_element.name;
            sub_element.data.elements.forEach(function (chartDetails) {
                let yAxis = 1;
                if (chartDetails.own_yaxis) {
                    yAxis += 1;
                }
                let xAxis = 1;
                if (chartDetails.own_xaxis) {
                    xAxis += 1;
                }
                const layout = createChart(chartDetails, chartData, yAxis, xAxis, xaxis_list, yaxis_list);
                if (divID === "main-chart") {
                    mainLayout = layout;
                }

                function afterPlot(target) {
                    removeExplicitSize(target);
                    resizeObserver.observe(target);
                    if (divID !== "main-chart") {
                        // Plotly.relayout("sub-chart", {xaxis: mainLayout.xaxis});
                        originalXAxis = {range: mainLayout.xaxis.range, type: mainLayout.xaxis.type};
                        Plotly.relayout("sub-chart", {
                            xaxis: {
                                range: mainLayout.xaxis.range.map((x) => x),
                                type: mainLayout.xaxis.type
                            }
                        });
                    }
                }

                if (replot) {
                    Plotly.react(divID, chartData, layout, getPlotlyConfig()).then(afterPlot)
                } else {
                    Plotly.newPlot(divID, chartData, layout, getPlotlyConfig()).then(afterPlot)
                }
            });
        }
    });
    document.getElementById("main-chart").on("plotly_relayout", function(eventdata) {
        Plotly.relayout("sub-chart", eventdata);
        // log(eventdata)
    });
    // TODO: fix unzoom desync (probalby due to autosize)
    // document.getElementById("main-chart").on("plotly_doubleclick", function(eventdata) {
    //     log(eventdata)
    //     eventdata.stopImmediatePropagation()
    //     log("event")
    //     log(originalXAxis)
    //     Plotly.relayout("sub-chart", {xaxis: {range:  mainLayout.xaxis.range.map((x) => x), type: mainLayout.xaxis.type}});
    // });
    // TODO: handle zoom propagation from any graph
    // chartDivs[1][0].on("plotly_relayout", function(eventdata) {
    //     Plotly.relayout("main-chart", eventdata);
    // });
}

function removeExplicitSize(figure){
  delete figure.layout.width;
  delete figure.layout.height;
  figure.layout.autosize = true;
  // Turn off responsive (ie. responsive to window resize)
  figure.config = { responsive: false };
  return figure;
}

function displayChartsAndInputs(replot){
    $.get({
        url: $("#charts").data("url"),
        dataType: "json",
        success: function (data) {
            updateChartsAndInputs(data, replot)
        },
        error: function(result, status) {
            const errorMessage = `Impossible to get charting data: ${result.responseText}. More details in logs.`;
            $("#main-chart").text(errorMessage)
            window.console && console.error(errorMessage);
        }
    });
}

function isLiveGraph(){
    //TODO
    return true;
}

function handleScriptButtons(){
    $("#reload-script").click(function (){
        const update_url = $("#reload-script").data("url")
        const data = {
            live: isLiveGraph(),
        };
        send_and_interpret_bot_update(data, update_url, null, reload_request_success_callback, generic_request_failure_callback);

    })
}

function reload_request_success_callback(updated_data, update_url, dom_root_element, msg, status){
    displayChartsAndInputs(true);
}

function handleResizables(){
    $(".resizable").resizable();
    $(".resizable").on("resize", function () {
        const currentChartsHeight = $("#charts").height()
        const newToolboxHeight = "calc(100vh - 96px - " + currentChartsHeight + "px)";
        $("#toolbox").css("height", newToolboxHeight);


        const currentMainChartHeight = $("#main-chart").height()
        const newSubChartHeight = "calc(100% - 5px - " + currentMainChartHeight + "px)"
        $("#sub-chart").css("height", newSubChartHeight);
    });
}

function updateBacktestingSelect(updated_data, update_url, dom_root_element, msg, status){
    const select = $("#backtesting-run-select");
    msg.data.sort()
    msg.data.reverse().forEach(function(element){
        const date = new Date(element.timestamp * 1000)
        const displayedTime = `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`
        select.append(new Option(`${element.id} ${element.name} ${displayedTime}`, element.id));
    })
    triggerBacktestingSelectUpdate();
}

function asyncInit(){
    send_and_interpret_bot_update({}, $("#backtesting-run-select").data("url"), null,
        updateBacktestingSelect, generic_request_failure_callback, "GET");
}

function updateBacktestingReport(updated_data, update_url, dom_root_element, msg, status){
    updateBacktestingChart(msg, "backtesting-chart", true);
}

function triggerBacktestingSelectUpdate(){
     const data = {
        id: $("#backtesting-run-select").val(),
    }
    send_and_interpret_bot_update(data, $("#backtesting-chart").data("url"), null,
        updateBacktestingReport, generic_request_failure_callback);
}

function handleSelects(){
    $("#backtesting-run-select").on("change", triggerBacktestingSelectUpdate);
}

$(document).ready(function() {
    displayChartsAndInputs(false);
    asyncInit();
    handleScriptButtons();
    handleResizables();
    handleSelects();
});
