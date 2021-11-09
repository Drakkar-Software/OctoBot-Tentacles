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

function _getChartedElements(chartDetails, yAxis, xAxis, backtesting_id){
    const chartedElements = {
      x: chartDetails.x,
      mode: chartDetails.kind,
      type: chartDetails.kind,
      name: `${chartDetails.title} (${backtesting_id})`,
      backtesting_id: backtesting_id,
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

function createChart(chartDetails, chartData, yAxis, xAxis, xaxis_list, yaxis_list, backtesting_id){
    const chartedElements = _getChartedElements(chartDetails, yAxis, xAxis, backtesting_id);
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

function updateBacktestingChart(data, divID, replot, backtesting_id, added, backtestingTableName) {
    const graphDiv = document.getElementById(divID);
    const toRemoveTraces = [];
    if (added) {
        // remove potentially now unselected elements
        const selectedBacktestingIDs = getSelectedBacktestingIDs(backtestingTableName)
        let isAlreadyDisplayed = false;
        if(typeof graphDiv.data !== "undefined"){
            graphDiv.data.forEach(function (datum){
                if(selectedBacktestingIDs.indexOf(datum.backtesting_id) === -1){
                    toRemoveTraces.push(datum);
                }
                if(datum.backtesting_id == backtesting_id){
                    isAlreadyDisplayed = true;
                }
            })
        }
        if(!isAlreadyDisplayed){
            data.data.sub_elements.forEach(function (sub_element) {
                if (sub_element.type == "chart") {
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
                            const chartedElements = _getChartedElements(chartDetails, yAxis, xAxis, backtesting_id);
                            Plotly.addTraces(divID, chartedElements);
                        } else {

                            function afterPlot(target) {
                                removeExplicitSize(target);
                                resizeObserver.observe(target);
                            }
                            const layout = createChart(chartDetails, chartData, yAxis, xAxis, xaxis_list, yaxis_list, backtesting_id);
                            if (replot) {
                                Plotly.react(divID, chartData, layout, getPlotlyConfig()).then(afterPlot);
                            } else {
                                Plotly.newPlot(divID, chartData, layout, getPlotlyConfig()).then(afterPlot);
                            }
                        }
                    });
                }
            });
            plotlyCreatedChartsIDs.push(divID);
        }
    } else{
        graphDiv.data.forEach(function (data){
            if(data.backtesting_id === backtesting_id){
                toRemoveTraces.push(data);
            }
        })
    }
    toRemoveTraces.forEach(function (data){
        Plotly.deleteTraces(divID, graphDiv.data.indexOf(data));
    })
}

function _displayInputs(elements, replot, editors){
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

function updateDisplayedElement(data, replot, editors, backtestingPart, backtesting_id, added, backtestingTableName){
    data.data.sub_elements.forEach(function (sub_element) {
        if (sub_element.type === "input") {
            _displayInputs(sub_element, replot, editors);
            displayOptimizerSettings(sub_element, replot);
        }else if (sub_element.type === "table"){
            _updateTables(sub_element, replot, backtesting_id, added, backtestingTableName);
        }
    });
    if(backtestingPart){
        updateBacktestingChart(data, "backtesting-chart", true, backtesting_id, added, backtestingTableName)
    }else{
        _updateMainCharts(data, replot);
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

function _updateMainCharts(data, replot){
    let mainLayout = undefined;
    _updateChartLayout(data.data.sub_elements.length);
    data.data.sub_elements.forEach(function (sub_element) {
        if(sub_element.type == "chart") {
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

function _updateTables(sub_element, replot, backtesting_id, added, backtestingTableName){
    sub_element.data.elements.forEach(function (element){
        const toRemove = [];
        const tableName = element.title.replaceAll(" ", "-");
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

const relayouting = []
const plotlyCreatedChartsIDs = []

function removeExplicitSize(figure){
  delete figure.layout.width;
  delete figure.layout.height;
  figure.layout.autosize = true;
  // Turn off responsive (ie. responsive to window resize)
  figure.config = { responsive: false };
  return figure;
}
