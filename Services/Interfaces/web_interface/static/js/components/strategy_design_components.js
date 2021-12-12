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

function _getChartedElements(chartDetails, yAxis, xAxis, backtesting_id, optimizer_id, chartIdentifier){
    const chartedElements = {
      x: chartDetails.x,
      mode: chartDetails.kind,
      type: chartDetails.kind,
      text: chartDetails.text,
      name: `${chartDetails.title} (${chartIdentifier})`,
      backtesting_id: backtesting_id,
      optimizer_id: optimizer_id,
    }
    const markerAttributes = ["color", "size", "opacity", "line", "symbol"];
    chartedElements.marker = {};
    markerAttributes.forEach(function (attribute){
        if (chartDetails[attribute] !== null){
            chartedElements.marker[attribute] = chartDetails[attribute];
        }
    });
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

function createChart(chartDetails, chartData, yAxis, xAxis, xaxis_list, yaxis_list, backtesting_id, optimizer_id, chartIdentifier){
    const chartedElements = _getChartedElements(chartDetails, yAxis, xAxis, backtesting_id, optimizer_id, chartIdentifier);
    const xaxis = {
        gridcolor: "#2a2e39",
        color: "#b2b5be",
        autorange: true,
        rangeslider: {
            visible: false,
        }
    };
    const yaxis = {
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

function _updateChart(data, replot, backtesting_id, optimizer_id, added, backtestingTableName, chartIdentifier, afterPlot, hiddenXAxisIDs) {
    const toRemoveTracesByDivID = {};
    const checkedDivIDsForClear = [];
    if (added) {
        const selectedBacktestingIDsWithOptimizer = getSelectedBacktestingIDsWithOptimizer(backtestingTableName)
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
                                if(selectedBacktestingIDsWithOptimizer.indexOf(
                                    mergeBacktestingOptimizerID(datum.backtesting_id, datum.optimizer_id)) === -1){
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
                        const chartedElements = _getChartedElements(chartDetails, yAxis, xAxis, backtesting_id, optimizer_id, chartIdentifier);
                        Plotly.addTraces(divID, chartedElements);
                    } else {
                        const layout = createChart(chartDetails, chartData, yAxis, xAxis, xaxis_list, yaxis_list, backtesting_id, optimizer_id, chartIdentifier);
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

function _updateBacktestingChart(data, replot, backtesting_id, optimizer_id, added, backtestingTableName, chartIdentifier) {
    _updateChart(data, replot, backtesting_id, optimizer_id, added, backtestingTableName, chartIdentifier, afterGraphPlot, []);
}

function afterGraphPlot(target){
    const plottedDivID = $(target).attr("id");
    removeExplicitSize(target);
    resizeObserver.observe(target);
    if (plottedDivID !== "main-chart") {
        const mainLayout = document.getElementById("main-chart").layout;
        if(typeof mainLayout === "undefined"){
            return;
        }
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
    let hasSubChart = _getEnabledCharts().length > 1;
    data.data.sub_elements.forEach(function (sub_element) {
        if (sub_element.type == "chart") {
            if(sub_element.name === "sub-chart"){
                hasSubChart = true;
            }
        }
    });
   if(!hasSubChart){
       $("#main-chart-outer").css("height", "100%")
       $("#main-chart-outer").css("max-height", "100%")
       updateWindowSizes()
   }else if($("#sub-chart").css("height") === "0px"){
       $("#main-chart-outer").css("height", "65%")
       $("#main-chart-outer").css("max-height", "calc(100% - 25px)")
       updateWindowSizes()
   }
}

function _updateMainCharts(data, replot, backtesting_id, optimizer_id, added, backtestingTableName, chartIdentifier) {
    _updateChartLayout();
    hideSubChartWhenEmpty(data);
    const hiddenXAxisChartIDs = ["sub-chart"];
    _updateChart(data, replot, backtesting_id, optimizer_id, added, backtestingTableName, chartIdentifier, afterGraphPlot, hiddenXAxisChartIDs);
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
                    startval: inputDetails.config,
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

function updateDisplayedElement(data, replot, editors, backtestingPart, backtesting_id, optimizer_id, added, backtestingTableName, chartIdentifier){
    data.data.sub_elements.forEach(function (sub_element) {
        if (backtesting_id === null && sub_element.type === "input") {
            // only update inputs on live data
            _displayInputs(sub_element, replot, editors);
            displayOptimizerSettings(sub_element, replot);
        }
        if (sub_element.type === "table"){
            _updateTables(sub_element, replot, backtesting_id, optimizer_id, added, backtestingTableName);
        }
        if (sub_element.type === "value"){
            _updateBacktestingValues(sub_element, replot, backtesting_id, added);
        }
    });
    if(backtestingPart){
        _updateBacktestingChart(data, true, backtesting_id, optimizer_id, added, backtestingTableName, chartIdentifier)
    }else{
        _updateMainCharts(data, replot, backtesting_id, optimizer_id, added, backtestingTableName, chartIdentifier);
    }
}

function updateOptimizerQueueEditor(optimizerQueue, containerId, queueUpdateCallback){
    createOptimizerQueueTables(optimizerQueue, containerId, queueUpdateCallback)
}

function _getEnabledCharts(){
    const charts = ["main-chart", "sub-chart"];
    const enabledCharts = [];
    charts.forEach(function (chart){
        if(typeof document.getElementById(chart).data !== "undefined"){
            enabledCharts.push(chart)
        }
    })
    return enabledCharts;
}

function _updateChartLayout(){
    const subElementCount = _getEnabledCharts().length;
    if(subElementCount <= 1){
        $("#main-chart-outer").resizable("option", "disabled", true );
    }else {
        $("#main-chart-outer").resizable("option", "disabled", false );
    }
    if(subElementCount <= 2){
        $("#main-chart-outer").addClass("max-width");
    }else {
        $("#main-chart-outer").removeClass("max-width");
    }
}

function _updateBacktestingValues(sub_element, replot, backtesting_id, added){
    const parentDiv = $(document.getElementById(sub_element.name));
    if(!parentDiv.length){
        return
    }
    const backtestingParentDivId = `${backtesting_id}-part`;
    let backtestingRunParentDiv = parentDiv.find(`#${backtestingParentDivId}`);
    if(backtestingRunParentDiv.length){
        if(added){
            backtestingRunParentDiv.empty();
        }else{
            backtestingRunParentDiv.remove();
        }
    }else if(added){
        parentDiv.append(`<div id="${backtestingParentDivId}" class="backtesting-run-container"></div>`)
        backtestingRunParentDiv = parentDiv.find(`#${backtestingParentDivId}`);
    }
    if(added){
        _add_labelled_backtesting_values(sub_element, backtesting_id, backtestingRunParentDiv, parentDiv)
    }
}

function _clearBacktestingValues(){
    $(".backtesting-run-container").remove();
}

function _add_labelled_backtesting_values(sub_element, backtesting_id, backtestingRunParentDiv, parentDiv){
        const backtestingValuesGridId = `${backtesting_id}-values-grid`;
        backtestingRunParentDiv.append(
            `<div class="backtesting-run-container-title text-center">
                <h4>Backtesting ${backtesting_id}</h4>
             </div>`
        );
        backtestingRunParentDiv.append(
            `<div id="${backtestingValuesGridId}" class="backtesting-run-container-values container-fluid row"></div>`
        );
        const backtestingValuesGridDiv = parentDiv.find(`#${backtestingValuesGridId}`);
        sub_element.data.elements.forEach(function (element){
            if(element.html === null){
                backtestingValuesGridDiv.append(
                    `<div class="col-6 col-md-3 ${sub_element.data.elements.length > 4 ? 'col-xl-2' : ''} text-center">
                        <div class="backtesting-run-container-values-label">${element.title}</div>
                        <div class="backtesting-run-container-values-value">${element.value}</div>
                    </div>`
                );
            }else{
                backtestingValuesGridDiv.append(element.html);
            }
        });
}

function _updateTables(sub_element, replot, backtesting_id, optimizer_id, added, backtestingTableName){
    sub_element.data.elements.forEach(function (element){
        const toRemove = [];
        const tableName = element.title.replaceAll(" ", "-").replaceAll("*", "-");
        if(added) {
            // remove potentially now unselected elements
            if(typeof w2ui[tableName] !== "undefined"){
                let hasThisBacktestingAlready = false;
                const selectedBacktestingIDsWithOptimizer = getSelectedBacktestingIDsWithOptimizer(backtestingTableName);
                w2ui[tableName].records.forEach(function (record){
                    if(selectedBacktestingIDsWithOptimizer.indexOf(mergeBacktestingOptimizerID(record.backtesting_id, record.optimizer_id)) === -1){
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
            element.columns.push(
                {
                    "field": "backtesting_id",
                    "label": "Backtesting id",
                },
                {
                    "field": "optimizer_id",
                    "label": "Optimizer id",
                }
            )
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
                row.optimizer_id = optimizer_id;
                row.recid = startIndex + index;
                return row;
            });
            element.searches.push(
                {
                    "field": "backtesting_id",
                    "label": "Backtesting id",
                    "type": null,
                },
                {
                    "field": "optimizer_id",
                    "label": "Optimizer id",
                    "type": null,
                }
            )
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
            _createTable(chartDivID, element.title, tableName, searches, columns, records,
                false, true, false, false, null, null);
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

function _formatMetadataRow(row, recordId, optimizerId){
    row.timestamp = typeof row.timestamp === "undefined" ? undefined : Math.round(row.timestamp * 1000);
    row.start_time = typeof row.start_time === "undefined" ? undefined : Math.round(row.start_time * 1000);
    row.end_time = typeof row.end_time === "undefined" ? undefined : Math.round(row.end_time * 1000);
    Object.keys(row).forEach(function (key){
        if(typeof row[key] === "object" && key !== "children"){
            row[key] = JSON.stringify(row[key]);
        }
    })
    if(typeof row.children !== "undefined"){
        optimizerId = row.children[0].optimizer_id
        row.id = `${row.id} [optimizer ${optimizerId}]`
        const subRows = [];
        row.children.forEach(function (rowChild){
            recordId = _formatMetadataRow(rowChild, recordId, optimizerId)
            subRows.push(rowChild)
        })
        row.w2ui = {
            children: subRows
        }
        delete row.children
    }else{
        row.id = `${row.id} [backtesting]`
    }
    delete row.optimizer_id
    row.recid = mergeBacktestingOptimizerID(recordId ++, optimizerId);
    return recordId
}

function createOptimizerQueueTables(optimizerQueue, containerId, queueUpdateCallback){
    const mainContainer = $(`#${containerId}`);
    const noRunMessage = $("#no-optimizer-queue-message");
    mainContainer.empty();
    if(optimizerQueue.length){
        noRunMessage.addClass(hidden_class);
        optimizerQueue.forEach(function (optimizerRun){
            if(Object.values(optimizerRun.runs).length){
                _createOptimizerRunQueueTable(optimizerRun, mainContainer, queueUpdateCallback);
            }
        })
    }else{
        noRunMessage.removeClass(hidden_class);
    }
}

function _createOptimizerRunQueueTable(optimizerRun, mainContainer, queueUpdateCallback){
    const optimizerId = optimizerRun.id;
    const dataFiles = optimizerRun.data_files;
    const divID = `optimizer-queue-${optimizerId}`;
    const queueData = {
        id: optimizerId,
        data_files: dataFiles,
        deletedRows: [],
    }
    const queueDiv = `<div id="${divID}" class="h-75"></div>`;
    mainContainer.append(queueDiv);
    $(`#${divID}`).data("queueData", queueData)
    const keys = [];
    Object.values(Object.values(optimizerRun.runs)[0]).forEach(function (inputDetail){
        keys.push(`${inputDetail.user_input} value`);
        keys.push(`${inputDetail.user_input} tentacle`);
    });
    const columns = keys.map((key) => {
        return {
            field: key,
            text: key,
            size: `${1 / keys.length * 100}%`,
            sortable: true,
        }
    })
    const records = []
    let recId = 0;
    Object.values(optimizerRun.runs).map((run) => {
        const row = {
            recid: recId++
        };
        run.forEach(function (runUserInputDetails){
            row[`${runUserInputDetails.user_input} value`] = runUserInputDetails.value
            row[`${runUserInputDetails.user_input} tentacle`] = runUserInputDetails.tentacle
        })
        records.push(row);
    });
    const searches = keys.map((key) => {
        return {
            field: key,
            label: key,
            type: "text",
        }
    });
    function _onReorderRow(event){
        event.onComplete = _afterTableUpdate
    }
    function _onDelete(event){
        event.force = true;
        const table = w2ui[event.target];
        const tableDiv = $(`#${table.box.id}`)
        tableDiv.data("queueData").deletedRows = table.getSelection().map((recId) => table.get(recId));
        event.onComplete = _afterTableUpdate;
    }
    const tableName = `${divID}-table`;
    _createTable(divID, `Runs for optimizer ${optimizerId}`,
        tableName, searches, columns, records,
        true, false, true, true, _onReorderRow, _onDelete);

    function _createRunData(record, deleted){
        const run = [];
        Object.keys(record).forEach((key) => {
            if (key.endsWith(" value")){
                const inputName = key.split(" value")[0];
                run.push({
                    user_input: inputName,
                    tentacle: record[`${inputName} tentacle`],
                    value: record[key],
                    deleted: deleted,
                });
            }
        });
        return run;
    }
    function _updateOptimizerQueue(queueInfo, records){
        let runs = records.map((record) => _createRunData(record, false));
        runs = runs.concat(queueInfo.deletedRows.map((record) => _createRunData(record, true)));
        queueInfo.deletedRows = [];
        const updatedQueue = {
            id: queueInfo.id,
            data_files: queueInfo.data_files,
            runs: runs,
        }
        queueUpdateCallback(updatedQueue);
    }
    function _afterTableUpdate(event){
        const table = w2ui[event.target];
        const tableDiv = $(`#${table.box.id}`)
        const queueInfo = tableDiv.data("queueData")
        _updateOptimizerQueue(queueInfo, table.records)
    }
}

function createBacktestingMetadataTable(metadata, sectionHandler, forceSelectLatest){
    _clearBacktestingValues();
    if(metadata !== null && metadata.length){
        $("#no-backtesting-message").addClass(hidden_class);
        const keys = Object.keys(metadata[0]);
        const dateKeys = ["timestamp", "start_time", "end_time"]
        const columns = keys.map((key) => {
            return {
                field: key,
                text: key,
                size: `${1 / keys.length * 100}%`,
                sortable: true,
                render: dateKeys.indexOf(key) !== -1 ? "datetime" : undefined,
            }
        })
        let recordId = 0;
        const records = metadata.map((row) => {
            recordId = _formatMetadataRow(row, recordId, 0);
            return row
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
                     searches, columns, records,
            true, false, false, false, null, null);
        const table = w2ui[tableName];
        table.on("select", function (event){
            sectionHandler(event, true);
        })
        table.on("unselect", function (event){
            sectionHandler(event, false);
        })
        if(records.length){
            table.sort("timestamp", "desc");
            if(forceSelectLatest || autoSelectFirstBacktesting()){
                table.click(table.getFirst());
            }
            return tableName;
        }
    }
    $("#no-backtesting-message").removeClass(hidden_class);
}

function autoSelectFirstBacktesting(){
    // TODO (use js localstorage ?)
    return false;
}

function getSelectedBacktestingIDsWithOptimizer(tableName){
    const table = w2ui[tableName];
    if(typeof table !== "undefined") {
        return table.getSelection().map((recid) =>
            mergeBacktestingOptimizerID(getIdFromTableRow(table, recid), getOptimizerIdFromTableRow(recid)));
    }
    return [];
}

function mergeBacktestingOptimizerID(backtestingId, optimizerId){
    return `${backtestingId}${ID_SEPARATOR}${optimizerId}`
}

function getIdFromTableRow(table, recid){
    return Number(table.get(recid).id.split(" ")[0]);
}

function getOptimizerIdFromTableRow(recid){
    return Number(recid.split(ID_SEPARATOR)[1]);
}

function _createTable(elementID, name, tableName, searches, columns, records,
                      selectable, addToTable, reorderRows, deleteRows, onReorderRowCallback, onDeleteCallback) {
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
                toolbarDelete: deleteRows,
                selectColumn: selectable,
                orderColumn: reorderRows,
            },
            multiSearch: true,
            searches: searches,
            columns: columns,
            records: records,
            reorderRows: reorderRows,
            onDelete: onDeleteCallback,
            onReorderRow: onReorderRowCallback,
            onSave: function (event) {
                w2alert('save');
            },
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

const plotlyCreatedChartsIDs = [];
const ID_SEPARATOR = "_";

function removeExplicitSize(figure){
  delete figure.layout.width;
  delete figure.layout.height;
  figure.layout.autosize = true;
  // Turn off responsive (ie. responsive to window resize)
  figure.config = { responsive: false };
  return figure;
}
