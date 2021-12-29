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
                if(!isAreaDisplayed(divID, backtestingTableName)){
                    return;
                }
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
                if(!isAreaDisplayed(divID, backtestingTableName)){
                    return;
                }
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

function _hideNotShownUserInputs(tentacle, schema, is_hidden){
    let hiddenColumns = [];
    Object.keys(schema.properties).forEach((key) => {
        const value = schema.properties[key];
        if(typeof value.properties === "object"){
            hiddenColumns = hiddenColumns.concat(_hideNotShownUserInputs(key, value, is_hidden));
        }else{
            if(is_hidden || !value.options.in_summary){
                hiddenColumns.push(_userInputKey(key, tentacle));
                hiddenColumns.push(_userInputKey(key.replaceAll("_", " "), tentacle));
            }
        }
    })
    return hiddenColumns;
}

function _handleHiddenUserInputs(elements){
    hiddenBacktestingMetadataColumns = [];
    elements.data.elements.forEach(function (inputDetails) {
        hiddenBacktestingMetadataColumns = hiddenBacktestingMetadataColumns.concat(
            _hideNotShownUserInputs(inputDetails.tentacle, inputDetails.schema, inputDetails.is_hidden)
        );
    });
}

function _displayInputsForTentacle(elements, replot, editors, mainTab, tentacleType){
    elements.data.elements.forEach(function (inputDetails) {
        if(inputDetails.tentacle_type === tentacleType && !inputDetails.is_hidden){
            try{
                const tabIdentifier = mainTab == null ? inputDetails.tentacle : mainTab
                const divId = inputDetails.title.replaceAll(" ", "-");
                const masterTab = $(`#${tabIdentifier}-inputs`);
                masterTab.empty();
                masterTab.append(`<div id="${tabIdentifier}-${divId}"></div>`);
                const element = document.getElementById(`${tabIdentifier}-${divId}`)
                if(element === null){
                    window.console&&console.error(`Missing evaluator configuration tab "${tabIdentifier}-${divId}"`);
                    return;
                }
                editors[inputDetails.tentacle] = new JSONEditor(
                    element,
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
            }catch (error){
                window.console&&console.error(error);
            }
        }
    });
}

function _displayInputs(elements, replot, editors){
    _handleHiddenUserInputs(elements)
    _displayInputsForTentacle(elements, replot, editors, "trading", "trading_mode", backtestingTableName)
    _displayInputsForTentacle(elements, replot, editors, null, "evaluator", backtestingTableName)
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
    if(!parentDiv.length || !isAreaDisplayed(sub_element.name, backtestingTableName)){
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
        if(!isAreaDisplayed(sub_element.name, backtestingTableName)){
            return;
        }
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
                startIndex = w2ui[tableName].records.length;
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
                    type: _getTableDataType(records, search, "undefined", null),
                    options: search.options,
                }
            });
            const chartDivID = `${sub_element.name}-${element.title}`;
            if(typeof w2ui[tableName] === "undefined"){
                const parentDiv = $(document.getElementById(sub_element.name));
                parentDiv.append(`<div id="${chartDivID}" style="width: 100%; height: 400px;"></div>`);
            }
            const tableTitle = element.title.replaceAll("_", " ");
            _createTable(chartDivID, tableTitle, tableName, searches, columns, records, [],
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
    row["start time"] = typeof row["start time"] === "undefined" ? undefined : Math.round(row["start time"] * 1000);
    row["end time"] = typeof row["end time"] === "undefined" ? undefined : Math.round(row["end time"] * 1000);
    if(typeof row["user inputs"] !== "undefined"){
        Object.keys(row["user inputs"]).forEach((inputTentacle) => {
            Object.keys(row["user inputs"][inputTentacle]).forEach((userInput) => {
                row[_userInputKey(userInput, inputTentacle)] = row["user inputs"][inputTentacle][userInput];
            })
        })
    }
    Object.keys(row).forEach(function (key){
        if(typeof row[key] === "object" && key !== "children"){
            row[key] = JSON.stringify(row[key]);
        }
    })
    if(typeof row.children !== "undefined"){
        optimizerId = row.children[0]["optimizer id"]
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
    const tentaclesInputsCounts = {};
    Object.values(Object.values(optimizerRun.runs)[0]).forEach(function (inputDetail){
        const label = inputDetail.user_input.length > MAX_SEARCH_LABEL_SIZE ? `${inputDetail.user_input.slice(0, 
            MAX_SEARCH_LABEL_SIZE)} ...`: inputDetail.user_input;
        keys.push({
            text: `${label} (${inputDetail.tentacle})`,
            field: _userInputKey(inputDetail.user_input, inputDetail.tentacle)
        });
        if(typeof tentaclesInputsCounts[inputDetail.tentacle] !== "undefined"){
            tentaclesInputsCounts[inputDetail.tentacle] ++;
        }else{
            tentaclesInputsCounts[inputDetail.tentacle] = 1;
        }
    });
    const columns = keys.map((key) => {
        return {
            field: key.field,
            text: key.text,
            size: `${1 / keys.length * 100}%`,
            sortable: true,
        }
    });
    const columnGroups = Object.keys(tentaclesInputsCounts).map(function (key){
        return {
            text: key,
            span: tentaclesInputsCounts[key]
        }
    });
    const records = []
    let recId = 0;
    const userInputSamples = {};
    Object.values(optimizerRun.runs).map((run) => {
        const row = {
            recid: recId++
        };
        run.forEach(function (runUserInputDetails){
            const field = _userInputKey(runUserInputDetails.user_input, runUserInputDetails.tentacle)
            row[field] = runUserInputDetails.value;
            userInputSamples[field] = runUserInputDetails.value;
        })
        records.push(row);
    });
    const searches = keys.map((key) => {
        const sampleValue = userInputSamples[key.field];
        return {
            field: key.field,
            label: key.text,
            type:  TIMESTAMP_DATA.indexOf(key) !== -1 ? "datetime" : _getTableDataType(null,
                {type: null, field: key}, "text", sampleValue),
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
        tableName, searches, columns, records, columnGroups,
        true, false, true, true, _onReorderRow, _onDelete);

    function _createRunData(record, deleted){
        const run = [];
        Object.keys(record).forEach((key) => {
            if (key !== "recid"){
                const splitKey = key.split(TENTACLE_SEPARATOR);
                const inputName = splitKey[0];
                run.push({
                    user_input: inputName,
                    tentacle: splitKey[1],
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

function _ensureBacktestingMetadataColumnsOrder(runDataColumns){
    let idIndex = 0;
    runDataColumns.forEach((column, index) => {
        if(column.field === "id"){
            idIndex = index;
        }
    })
    runDataColumns.splice(0, 0, runDataColumns.splice(idIndex, 1)[0]);
}

function _userInputKey(userInput, tentacle){
    return `${userInput}${TENTACLE_SEPARATOR}${tentacle}`;
}

function createBacktestingMetadataTable(metadata, sectionHandler, forceSelectLatest){
    _clearBacktestingValues();
    if(metadata !== null && metadata.length){
        const sortedMetadata = metadata.sort((a, b) => b.timestamp - a.timestamp);
        $("#no-backtesting-message").addClass(hidden_class);
        const keys = Object.keys(sortedMetadata[0]);
        const runDataColumns = keys.map((key) => {
            return {
                field: key,
                text: key,
                size: `${1 / keys.length * 100}%`,
                sortable: true,
                hidden: METADATA_HIDDEN_FIELDS.indexOf(key) !== -1,
                render: TIMESTAMP_DATA.indexOf(key) !== -1 ? "datetime" : undefined,
            }
        })
        // Always put the id attribute first
        _ensureBacktestingMetadataColumnsOrder(runDataColumns);
        const columnGroups = [{text: "Run information", span: runDataColumns.length}];
        // Keep 1st column displayed to enable tree expand
        const runDataHidableColumns = runDataColumns.slice(1, runDataColumns.length);
        // Build user inputs columns. They are hidden by default
        const userInputColumns = [];
        const addedTentacles = [];
        const inputPerTentacle = {};
        const userInputKeys = [];
        if(hiddenBacktestingMetadataColumns === null){
            window.console&&console.error(`createBacktestingMetadataTable called before hiddenBacktestingMetadataColumns was initialized`);
            hiddenBacktestingMetadataColumns = [];
        }
        sortedMetadata.forEach((run_metadata) => {
            if(typeof run_metadata["user inputs"] !== "undefined"){
                Object.keys(run_metadata["user inputs"]).forEach((inputTentacle) => {
                    const hasTentacle = addedTentacles.indexOf(inputTentacle) === -1;
                    Object.keys(run_metadata["user inputs"][inputTentacle]).forEach((userInput) => {
                        const key = _userInputKey(userInput, inputTentacle);
                        if(userInputKeys.indexOf(key) === -1 && hiddenBacktestingMetadataColumns.indexOf(key) === -1){
                            userInputKeys.push(key);
                            userInputColumns.push({
                                field: key,
                                text: userInput,
                                sortable: true,
                                hidden: true
                            });
                            if(typeof inputPerTentacle[inputTentacle] !== "undefined"){
                                inputPerTentacle[inputTentacle] ++;
                            }else{
                                inputPerTentacle[inputTentacle] = 1;
                            }
                        }
                    })
                    if(!hasTentacle) {
                        addedTentacles.push(inputTentacle);
                    }
                })
            }
        })
        Object.keys(inputPerTentacle).forEach((key) => {
            columnGroups.push({
                text: key,
                span: inputPerTentacle[key]
            });
        })
        userInputColumns.sort((a, b) => {
            const aField = a.field.split(TENTACLE_SEPARATOR).reverse().join("");
            const bField = b.field.split(TENTACLE_SEPARATOR).reverse().join("");
            if(aField > bField){
                return 1;
            }else if(aField < bField){
                return -1;
            }
            return 0;
        });
        const userInputKeySize = `${1 / (userInputColumns.length + runDataColumns.length - runDataHidableColumns.length) * 100}%`;
        userInputColumns.forEach((column)=>{
            column.size = userInputKeySize;
        })
        const columns = runDataColumns.concat(userInputColumns);
        // init searches before formatting rows to access user_inputs objects
        const userInputSearches = userInputKeys.map((key) => {
            const splitKey = key.split(TENTACLE_SEPARATOR);
            const sampleValue = typeof sortedMetadata[0]["user inputs"][splitKey[1]] === "undefined" ? undefined :
                sortedMetadata[0]["user inputs"][splitKey[1]][splitKey[0]];
            const label = splitKey[0].length > MAX_SEARCH_LABEL_SIZE ?
                `${splitKey[0].slice(0, MAX_SEARCH_LABEL_SIZE)} ...`: splitKey[0];
            return {
                field: key,
                label: `${label} (${splitKey[1]})`,
                type:  TIMESTAMP_DATA.indexOf(key) !== -1 ? "datetime" : _getTableDataType(null,
                    {type: null, field: key}, "text", sampleValue),
            }
        })
        let recordId = 0;
        const records = sortedMetadata.map((row) => {
            recordId = _formatMetadataRow(row, recordId, 0);
            return row
        });
        const runDataSearches = keys.map((key) => {
            return {
                field: key,
                label: key,
                type: TIMESTAMP_DATA.indexOf(key) !== -1 ? "datetime" : _getTableDataType(records,
                    {type: null, field: key}, "undefined", null),
            };
        });
        _ensureBacktestingMetadataColumnsOrder(runDataSearches);
        const searches = runDataSearches.concat(userInputSearches);
        const name = "Select backtestings";
        const tableName = name.replaceAll(" ", "-");
        _createTable("backtesting-run-select-table", name, tableName,
                     searches, columns, records, columnGroups,
            true, false, false, false, null, null);
        const table = w2ui[tableName];
        _addBacktestingMetadataTableButtons(table, runDataHidableColumns, userInputColumns)
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

function _addBacktestingMetadataTableButtons(table, runDataHidableColumns, userInputColumns){
    // tabs
    function showRunInfo(){
        table.showColumn(...runDataHidableColumns.map((column) => column.field))
        table.hideColumn(...userInputColumns.map((column) => column.field))
        table.toolbar.disable('show-run-info');
        table.toolbar.enable('show-user-inputs');
    }
    function showUserInputInfo(){
        table.hideColumn(...runDataHidableColumns.map((column) => column.field))
        table.showColumn(...userInputColumns.map((column) => column.field))
        table.toolbar.disable('show-user-inputs');
        table.toolbar.enable('show-run-info');
    }
    table.toolbar.add({ type: 'button', id: 'show-run-info', text: 'Run info', img: 'fa fa-bolt', disabled: true , onClick: showRunInfo });
    table.toolbar.add({ type: 'button', id: 'show-user-inputs', text: 'User inputs', img: 'fa fa-user-cog', onClick: showUserInputInfo })

    // settings
    table.toolbar.add({ type: 'spacer' })
    const dataAreas = ["main-chart", "sub-chart",
        "backtesting-run-overview", "backtesting-details", "list-of-trades-part"];
    const areasItems = dataAreas.map((area) => {
        return {
            id: area,
            text: area,
        }
    })
    table.toolbar.add({
        type: 'menu-check', id: 'displayedAreasSelector', text: 'Display', icon: 'fa fa-cog',
        selected: dataAreas,
        onRefresh(event) {
            event.item.count = event.item.selected.length;
        },
        items: areasItems
    });
}

function isAreaDisplayed(areaId, tableName){
    const table = w2ui[tableName];
    if(typeof table !== "undefined") {
        return table.toolbar.get("displayedAreasSelector").selected.indexOf(areaId) !== -1
    }
    return true;
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

function _createTable(elementID, name, tableName, searches, columns, records, columnGroups,
                      selectable, addToTable, reorderRows, deleteRows, onReorderRowCallback, onDeleteCallback) {
    const tableExists = typeof w2ui[tableName] !== "undefined";
    if(tableExists && addToTable){
        w2ui[tableName].add(records)
    }else{
        if(tableExists){
            w2ui[tableName].destroy();
        }
        const table = $(document.getElementById(elementID)).w2grid({
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
            columnGroups: columnGroups,
            reorderRows: reorderRows,
            onDelete: onDeleteCallback,
            onReorderRow: onReorderRowCallback
        });
        table.toolbar.add({ type: 'button', id: 'exportTable', text: 'Export', img: 'fas fa-file-download' , onClick: downloadRecords });
        function downloadRecords(){
            _downloadRecords(name, table.columns, table.records);
        }
    }
    return tableName;
}


function _downloadRecords(name, columns, rows){
    const columnFields = columns.map((col) => col.field);
    let csv = columns.map((col) => col.text).join(",") + "\n";
    csv += rows.map((row) => {
        return columnFields.map((field) => {
            const value = row[field];
            if(typeof value === "string"){
                return value.replaceAll(",", " ");
            }
            return value
        }).join(",")
    }).join("\n");
    const hiddenElement = document.createElement('a');
    hiddenElement.href = 'data:text/csv;charset=utf-8,' + encodeURI(csv);
    hiddenElement.target = '_blank';
    hiddenElement.download = `${name}.csv`;
    hiddenElement.click();
    hiddenElement.remove();
}


function _getTableDataType(records, search, defaultValue, sampleValue){
    if (search.type !== null){
        return search.type;
    }
    const _sampleValue = sampleValue === null ? records[0][search.field] : sampleValue;
    if(typeof _sampleValue === "undefined"){
        return defaultValue;
    }
    if(typeof _sampleValue === "number"){
        return "float";
    }
    if(typeof _sampleValue === "string"){
        return "text";
    }
    if(typeof _sampleValue === "object"){
        return "list";
    }
    return defaultValue;
}

let hiddenBacktestingMetadataColumns = null;
const plotlyCreatedChartsIDs = [];
const ID_SEPARATOR = "_";
const TENTACLE_SEPARATOR = "###";
const MAX_SEARCH_LABEL_SIZE = 45;
const TIMESTAMP_DATA = ["timestamp", "start time", "end time"];
const METADATA_HIDDEN_FIELDS = ["backtesting files", "user inputs"]

function removeExplicitSize(figure){
  delete figure.layout.width;
  delete figure.layout.height;
  figure.layout.autosize = true;
  // Turn off responsive (ie. responsive to window resize)
  figure.config = { responsive: false };
  return figure;
}

// main entrypoint of this file
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
            _updateBacktestingValues(sub_element, replot, backtesting_id, added, backtestingTableName);
        }
    });
    if(backtestingPart){
        _updateBacktestingChart(data, true, backtesting_id, optimizer_id, added, backtestingTableName, chartIdentifier)
    }else{
        _updateMainCharts(data, replot, backtesting_id, optimizer_id, added, backtestingTableName, chartIdentifier);
    }
}
