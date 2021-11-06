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
        showEditInChartStudio: false,
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
        margin: {l: 50, r: 50, b: 30, t: 0, pad: 0},
        showlegend: true,
        legend: {x: 0.01, xanchor: 'left', y: 0.99, yanchor:"top"},
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        dragmode: "pan",
        font: {
            color: "#b2b5be"
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

function displayInputs(elements, replot, editors){
    ["backtesting", "trading"].forEach(function (tab){
        const masterTab = $(`#${tab}-inputs`);
        masterTab.empty();
        elements.data.elements.forEach(function (inputDetails) {
            const divId = inputDetails.title.replaceAll(" ", "-");
            masterTab.append(`<div id="${tab}-${divId}"></div>`)
            editors[inputDetails.tentacle] = new JSONEditor(
                document.getElementById(`${tab}-${divId}`),
                {
                    schema: inputDetails.schema,
                    startval: replot ? inputDetails.config : $(`#save-${inputDetails.tentacle}`).data("config"),
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


function updateChartsAndInputs(data, replot, editors){
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
            displayInputs(sub_element, replot, editors)
            displayOptimizerSettings(sub_element, replot)
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
                }else{
                    layout.xaxis.visible = false;
                }

                function afterPlot(target) {
                    const plottedDivID = $(target).attr("id");
                    removeExplicitSize(target);
                    resizeObserver.observe(target);
                    if (plottedDivID !== "main-chart") {
                        // Plotly.relayout("sub-chart", {xaxis: mainLayout.xaxis});
                        originalXAxis = {range: mainLayout.xaxis.range, type: mainLayout.xaxis.type};
                        Plotly.relayout("sub-chart", {
                            xaxis: {
                                range: mainLayout.xaxis.range.map((x) => x),
                                type: mainLayout.xaxis.type,
                                visible: false,
                            }
                        });
                    }else{
                        // TODO figure out how to disable autorange in order to unlock range change from sub chart
                        //  BUT without reseting x axis to year 2000
                        // mainLayout.xaxis.autorange = false
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
    if(!replot){
        document.getElementById("main-chart").on("plotly_relayout", function(eventdata) {
            relayouting.push("main-chart");
            if(relayouting.indexOf("sub-chart") === -1){
                Plotly.relayout("sub-chart", eventdata);
                relayouting.push("sub-chart");
            }else{
                relayouting.splice(0, relayouting.length);
            }
        });
        document.getElementById("sub-chart").on("plotly_relayout", function(eventdata) {
            relayouting.push("sub-chart");
            if(relayouting.indexOf("main-chart") === -1){
                mainLayout.xaxis.range[0]=eventdata["xaxis.range[0]"]
                mainLayout.xaxis.range[1]=eventdata["xaxis.range[1]"]
                Plotly.relayout("main-chart", mainLayout);
                relayouting.push("main-chart");
            }else{
                relayouting.splice(0, relayouting.length);
            }
        });
    }
}

const relayouting = []

function removeExplicitSize(figure){
  delete figure.layout.width;
  delete figure.layout.height;
  figure.layout.autosize = true;
  // Turn off responsive (ie. responsive to window resize)
  figure.config = { responsive: false };
  return figure;
}
