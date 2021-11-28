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

function _getChartedElements(chartDetails, yAxis, xAxis, backtesting_id, chartIdentifier){
    const chartedElements = {
      x: chartDetails.x,
      mode: chartDetails.kind,
      type: chartDetails.kind,
      name: `${chartDetails.title} (${chartIdentifier})`,
      backtesting_id: backtesting_id,
    }
    if (chartDetails.color !== null){
        chartedElements.marker = {
          color: chartDetails.color
        }
    }
    Array("y", "open", "high", "low", "close", "volume").forEach(function (element){
        if(chartDetails[element] !== null){
            chartedElements[element] = chartDetails[element]
        }
    })
    if(xAxis > 1){
        chartedElements.xaxis= `x${xAxis}`
    }
    if(yAxis > 1){
        chartedElements.yaxis= `y${yAxis}`
    }
    return chartedElements;
}

function createChart(chartDetails, chartData, yAxis, xAxis, xaxis_list, yaxis_list, backtesting_id, chartIdentifier){
    const chartedElements = _getChartedElements(chartDetails, yAxis, xAxis, backtesting_id, chartIdentifier);
    const xaxis = {
        showspikes: true,
        spikethickness: 1,
        spikesnap: "cursor",
        spikemode: "across",
        spikecolor: "#b2b5be",
        gridcolor: "#2a2e39",
        color: "#b2b5be",
        autorange: true,
        rangeslider: {
            visible: false,
        }
    };
    const yaxis = {
        showspikes: true,
        spikethickness: 1,
        spikesnap: "cursor",
        spikemode: "across",
        spikecolor: "#b2b5be",
        gridcolor: "#2a2e39",
        color: "#b2b5be",
        fixedrange: false,
    };
    if(chartDetails.x_type !== null){
        xaxis.type = chartDetails.x_type;
    }
    if(xAxis > 1){
        xaxis.overlaying = "x"
    }
    if(yAxis > 1){
        yaxis.overlaying = "y"
        yaxis.side = 'right'
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
        },
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

function _updateChart(data, replot, backtesting_id, added, backtestingTableName, chartIdentifier, afterPlot, hiddenXAxisIDs) {
    const toRemoveTracesByDivID = {};
    const checkedDivIDsForClear = [];
    if (added) {
        const selectedBacktestingIDs = getSelectedBacktestingIDs(backtestingTableName)
        data.data.sub_elements.forEach(function (sub_element) {
            if (sub_element.type == "chart") {
                const divID = sub_element.name;
                let isAlreadyDisplayed = false;
                if(backtesting_id !== null && checkedDivIDsForClear.indexOf(divID) === -1){
                    // remove potentially now unselected elements
                    checkedDivIDsForClear.push(divID);
                    toRemoveTracesByDivID[divID] = [];
                    const graphDiv = document.getElementById(divID);
                    if(typeof graphDiv.data !== "undefined"){
                        graphDiv.data.forEach(function (datum){
                            if(datum.backtesting_id !== null){
                                if(selectedBacktestingIDs.indexOf(datum.backtesting_id) === -1){
                                    // backtesting graphs are to be removed => not selected anymore
                                    toRemoveTracesByDivID[divID].push(datum);
                                }
                                if(datum.backtesting_id == backtesting_id){
                                    isAlreadyDisplayed = true;
                                }
                            }
                        })
                    }
                }
                if(isAlreadyDisplayed){
                    // already displayed, jump to next graph
                    return;
                }

                const chartData = [];
                const xaxis_list = [];
                const yaxis_list = [];
                sub_element.data.elements.forEach(function (chartDetails) {
                    let yAxis = 1;
                    if (chartDetails.own_yaxis) {
                        yAxis += 1;
                    }
                    let xAxis = 1;
                    if (chartDetails.own_xaxis) {
                        xAxis += 1;
                    }
                    if (plotlyCreatedChartsIDs.indexOf(divID) !== -1) {
                        const chartedElements = _getChartedElements(chartDetails, yAxis, xAxis, backtesting_id, chartIdentifier);
                        Plotly.addTraces(divID, chartedElements);
                    } else {
                        const layout = createChart(chartDetails, chartData, yAxis, xAxis, xaxis_list, yaxis_list, backtesting_id, chartIdentifier);
                        if (hiddenXAxisIDs.indexOf(divID) !== -1) {
                            layout.xaxis.visible = false;
                        }
                        if (replot) {
                            Plotly.react(divID, chartData, layout, getPlotlyConfig()).then(afterPlot);
                        } else {
                            Plotly.newPlot(divID, chartData, layout, getPlotlyConfig()).then(afterPlot);
                        }
                    }
                });
                if(plotlyCreatedChartsIDs.indexOf(divID) === -1){
                    plotlyCreatedChartsIDs.push(divID);
                }
            }
        });
    } else{
        data.data.sub_elements.forEach(function (sub_element) {
            if (sub_element.type == "chart") {
                const divID = sub_element.name;
                if(checkedDivIDsForClear.indexOf(divID) === -1) {
                    toRemoveTracesByDivID[divID] = [];
                    if(typeof document.getElementById(divID).data !== "undefined"){
                        document.getElementById(divID).data.forEach(function (data) {
                            if (data.backtesting_id === backtesting_id) {
                                toRemoveTracesByDivID[divID].push(data);
                            }
                        })
                    }
                    checkedDivIDsForClear.push(divID);
                }
            }
        });
    }
    Object.keys(toRemoveTracesByDivID).forEach(function (divID){
        toRemoveTracesByDivID[divID].forEach(function (data){
            Plotly.deleteTraces(divID, document.getElementById(divID).data.indexOf(data));
        });
    })
}

function _updateBacktestingChart(data, replot, backtesting_id, added, backtestingTableName, chartIdentifier) {
    _updateChart(data, replot, backtesting_id, added, backtestingTableName, chartIdentifier, afterGraphPlot, []);
}

function afterGraphPlot(target){
    const plottedDivID = $(target).attr("id");
    removeExplicitSize(target);
    resizeObserver.observe(target);
    if (plottedDivID !== "main-chart") {
        const mainLayout = document.getElementById("main-chart").layout;
        originalXAxis = {range: mainLayout.xaxis.range, type: mainLayout.xaxis.type};
        if(typeof document.getElementById("sub-chart").data !== "undefined"
            && typeof document.getElementById("main-chart").data !== "undefined") {
            Plotly.relayout("sub-chart", {
                xaxis: {
                    range: mainLayout.xaxis.range.map((x) => x),
                    type: mainLayout.xaxis.type,
                    visible: false,
                }
            });
        }
    }
}

function hideSubChartWhenEmpty(data){
    let hasSubChart = false;
    data.data.sub_elements.forEach(function (sub_element) {
        if (sub_element.type == "chart") {
            if(sub_element.name === "sub-chart"){
                hasSubChart = true;
            }
        }
    });
    if(!hasSubChart){
        $("#main-chart").css("height", "100%")
        $("#main-chart").css("max-height", "100%")
        updateWindowSizes()
    }else if($("#sub-chart").outerHeight(true) === 0){
        $("#main-chart").css("height", "65%")
        $("#main-chart").css("max-height", "calc(100% - 25px)")
        updateWindowSizes()
    }
}

function _updateMainCharts(data, replot, backtesting_id, added, backtestingTableName, chartIdentifier) {
    _updateChartLayout(data.data.sub_elements.length);
    hideSubChartWhenEmpty(data);
    const hiddenXAxisChartIDs = ["sub-chart"];
    _updateChart(data, replot, backtesting_id, added, backtestingTableName, chartIdentifier, afterGraphPlot, hiddenXAxisChartIDs);
    if(!replot){
        if(typeof document.getElementById("sub-chart").data !== "undefined"
            && typeof document.getElementById("main-chart").data !== "undefined"){
            document.getElementById("main-chart").on("plotly_relayout", function(eventdata) {
                if(typeof eventdata["xaxis.range[0]"] !== "undefined"){
                    const subChartLayout = document.getElementById("sub-chart").layout;
                    subChartLayout.xaxis.range[0]=eventdata["xaxis.range[0]"]
                    subChartLayout.xaxis.range[1]=eventdata["xaxis.range[1]"]
                    Plotly.relayout("sub-chart", subChartLayout);
                }
            });
            document.getElementById("sub-chart").on("plotly_relayout", function (eventdata) {
                if (typeof eventdata["xaxis.range[0]"] !== "undefined") {
                    const mainLayout = document.getElementById("main-chart").layout;
                    mainLayout.xaxis.range[0] = eventdata["xaxis.range[0]"]
                    mainLayout.xaxis.range[1] = eventdata["xaxis.range[1]"]
                    Plotly.relayout("main-chart", mainLayout).then(function () {
                        mainLayout.xaxis.autorange = false;
                    });
                }
            });
        }
    }
}

function _displayInputsForTentacle(elements, replot, editors, mainTab, tentacleType){
    elements.data.elements.forEach(function (inputDetails) {
        if(inputDetails.tentacle_type === tentacleType){
            const tabIdentifier = mainTab == null ? inputDetails.tentacle : mainTab
            const divId = inputDetails.title.replaceAll(" ", "-");
            const masterTab = $(`#${tabIdentifier}-inputs`);
            masterTab.empty();
            masterTab.append(`<div id="${tabIdentifier}-${divId}"></div>`);
            editors[inputDetails.tentacle] = new JSONEditor(
                document.getElementById(`${tabIdentifier}-${divId}`),
                {
                    schema: inputDetails.schema,
                    startval: replot ? inputDetails.config : masterTab.data("config"),
                    no_additional_properties: true,
                    prompt_before_delete: true,
                    disable_array_reorder: true,
                    disable_collapse: true,
                    disable_properties: true
                }
            );
        }
    });
}

function _displayInputs(elements, replot, editors){
    _displayInputsForTentacle(elements, replot, editors, "trading", "trading_mode")
    _displayInputsForTentacle(elements, replot, editors, null, "evaluator")
}

function updateDisplayedElement(data, replot, editors, backtestingPart, backtesting_id, added, backtestingTableName, chartIdentifier){
    data.data.sub_elements.forEach(function (sub_element) {
        if (backtesting_id === null && sub_element.type === "input") {
            // only update inputs on live data
            _displayInputs(sub_element, replot, editors);
            displayOptimizerSettings(sub_element, replot);
        }
        if (sub_element.type === "table"){
            _updateTables(sub_element, replot, backtesting_id, added, backtestingTableName);
        }
    });
    if(backtestingPart){
        _updateBacktestingChart(data, true, backtesting_id, added, backtestingTableName, chartIdentifier)
    }else{
        _updateMainCharts(data, replot, backtesting_id, added, backtestingTableName, chartIdentifier);
    }
}

function _updateChartLayout(subElementCount){
    if(subElementCount <= 1){
        $("#main-chart").resizable("option", "disabled", true );
    }
    if(subElementCount <= 2){
        $("#main-chart").addClass("max-width");
    }
    if(subElementCount > 2){
        $("#main-chart").removeClass("max-width");
    }
}


function _updateTables(sub_element, replot, backtesting_id, added, backtestingTableName){
    sub_element.data.elements.forEach(function (element){
        const toRemove = [];
        const tableName = element.title.replaceAll(" ", "-").replaceAll("*", "-");
        if(added) {
            // remove potentially now unselected elements
            if(typeof w2ui[tableName] !== "undefined"){
                let hasThisBacktestingAlready = false;
                const selectedBacktestingIDs = getSelectedBacktestingIDs(backtestingTableName);
                w2ui[tableName].records.forEach(function (record){
                    if(selectedBacktestingIDs.indexOf(record.backtesting_id) === -1){
                        toRemove.push(record.recid)
                    }
                    if(record.backtesting_id === backtesting_id){
                        hasThisBacktestingAlready = true;
                    }
                })
                if(hasThisBacktestingAlready){
                    return
                }
            }
            // add new elements
            element.columns.push({
                "field": "backtesting_id",
                "label": "Backtesting id",
            })
            const columns = element.columns.map((col) => {
                return {
                    field: col.field,
                    text: col.label,
                    size: `${1 / element.columns.length * 100}%`,
                    sortable: true,
                    attr: col.attr,
                    render: col.render,
                }
            });
            let startIndex = 0;
            if(typeof w2ui[tableName] !== "undefined"){
                startIndex = w2ui[tableName].records.length - 1;
            }
            const records = element.rows.map((row, index) => {
                row.backtesting_id = backtesting_id;
                row.recid = startIndex + index;
                return row;
            });
            element.searches.push({
                "field": "backtesting_id",
                "label": "Backtesting id",
                "type": null,
            })
            const searches = element.searches.map((search) => {
                return {
                    field: search.field,
                    label: search.label,
                    type: _getTableDataType(records, search),
                    options: search.options,
                }
            });
            const chartDivID = `${sub_element.name}-${element.title}`;
            if(typeof w2ui[tableName] === "undefined"){
                const parentDiv = $(document.getElementById(sub_element.name));
                parentDiv.append(`<div id="${chartDivID}" style="width: 100%; height: 400px;"></div>`);
            }
            _createTable(chartDivID, element.title, tableName, searches, columns, records, false, true);
        }else{
            if(typeof w2ui[tableName] !== "undefined"){
                w2ui[tableName].records.forEach(function (record){
                    if(record.backtesting_id === backtesting_id){
                        toRemove.push(record.recid)
                    }
                })
            }
        }
        if(toRemove.length){
            w2ui[tableName].remove(...toRemove);
        }
    });
}

function createBacktestingMetadataTable(metadata, sectionHandler){
    if(metadata !== null && metadata.length){
        $("#no-backtesting-message").addClass(hidden_class);
        const keys = Object.keys(metadata[0]);
        const columns = keys.map((key) => {
            return {
                field: key,
                text: key,
                size: `${1 / keys.length * 100}%`,
                sortable: true,
                render: key === "timestamp" ? "datetime" : undefined,
            }
        })
        const records = metadata.map((row, index) => {
            row.recid = index;
            row.timestamp = typeof row.timestamp === "undefined" ? undefined : Math.round(row.timestamp * 1000);
            Object.keys(row).forEach(function (key){
                if(typeof row[key] === "object"){
                    row[key] = JSON.stringify(row[key]);
                }
            })
            return row;
        });
        const searches = keys.map((key) => {
            search = {
                type: null,
                field: key,
            }
            return {
                field: key,
                label: key,
                type:  key === "timestamp" ? "datetime" : _getTableDataType(records, search),
            }
        });
        const name = "Select backtestings";
        const tableName = name.replaceAll(" ", "-");
        _createTable("backtesting-run-select-table", name, tableName,
                     searches, columns, records, true, false);
        const table = w2ui[tableName];
        table.on("select", function (event){
            sectionHandler(event, true);
        })
        table.on("unselect", function (event){
            sectionHandler(event, false);
        })
        if(records.length){
            table.sort("timestamp", "desc");
            table.click(table.getFirst());
        }
        return tableName;
    }
    $("#no-backtesting-message").removeClass(hidden_class);
}

function getSelectedBacktestingIDs(tableName){
    const table = w2ui[tableName];
    if(typeof table !== "undefined") {
        return table.getSelection().map((recid) => table.get(recid).id);
    }
    return [];
}

function _createTable(elementID, name, tableName, searches, columns, records, selectable, addToTable) {
    const tableExists = typeof w2ui[tableName] !== "undefined";
    if(tableExists && addToTable){
        w2ui[tableName].add(records)
    }else{
        if(tableExists){
            w2ui[tableName].destroy();
        }
        $(document.getElementById(elementID)).w2grid({
            name:  tableName,
            header: name,
            show: {
                header: true,
                toolbar: true,
                footer: true,
                toolbarReload: false,
                selectColumn: selectable
            },
            multiSearch: true,
            searches: searches,
            columns: columns,
            records: records,
        });
    }
    return tableName;
}


function _getTableDataType(records, search){
    if (search.type !== null){
        return search.type;
    }
    const valueType = records[0][search.field]
    if(typeof valueType === "undefined"){
        return undefined;
    }
    if(typeof valueType === "number"){
        return "float";
    }
    if(typeof valueType === "string"){
        return "text";
    }
    if(typeof valueType === "object"){
        return "list";
    }
}

const plotlyCreatedChartsIDs = []

function removeExplicitSize(figure){
  delete figure.layout.width;
  delete figure.layout.height;
  figure.layout.autosize = true;
  // Turn off responsive (ie. responsive to window resize)
  figure.config = { responsive: false };
  return figure;
}
