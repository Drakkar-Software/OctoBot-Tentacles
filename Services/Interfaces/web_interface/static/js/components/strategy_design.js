function displayChartsAndInputs(replot, backtestingRunId, optimizerId, added, symbol, time_frame, cleanCharts, resolve, reject){
    const chartIdentifier = backtestingRunId ? backtestingRunId : "live";
    const chartsDiv = $("#charts");
    let url = `${chartsDiv.data("live-url")}?exchange_id=${getExchangeId()}`;
    if(replot){
       url = `${chartsDiv.data("backtesting-url")}?exchange_id=${getExchangeId()}&run_id=${backtestingRunId}&optimizer_id=${optimizerId}`
    }
    url = `${url}&symbol=${symbol}&time_frame=${time_frame}`
    $.get({
        url: url,
        dataType: "json",
        success: function (data) {
            if(cleanCharts){
                $("#main-chart").empty();
                $("#sub-chart").empty();
                plotlyCreatedChartsIDs.splice(0, plotlyCreatedChartsIDs.length);
            }
            updateDisplayedElement(data, replot, editors, false, backtestingRunId, optimizerId, added, backtestingTableName, chartIdentifier);
            if(resolve !== null){
                resolve(data);
            }
        },
        error: function(result, status) {
            const errorMessage = `Impossible to get charting data: ${result.responseText}. More details in logs.`;
            $("#main-chart").text(errorMessage)
            window.console && console.error(errorMessage);
            if(reject !== null){
                reject(result);
            }
        }
    });
}

function handleScriptButtons(){
    $("#reload-script").click(function (){
        const update_url = $("#reload-script").data("url")
        const data = {
            live: true,
        };
        send_and_interpret_bot_update(data, update_url, null, reloadRequestSuccessCallback, generic_request_failure_callback);
    })
}

function handleCacheButtons(){
    ["delete-script-cache", "delete-all-cache",
        "delete-simulated-orders", "delete-simulated-trades"].forEach(function (id){
        $(`#${id}`).click(function (){
            send_and_interpret_bot_update({}, $(this).data("url"), null,
                cacheClearSuccessCallback, generic_request_failure_callback);
        });
    })
}

function cacheClearSuccessCallback(updated_data, update_url, dom_root_element, msg, status) {
    create_alert("success", msg["title"], msg["details"]);
    updateSymbolGraphs(null, null);
}

function handleBacktestingButtons(){
    $("#backtester-start-button").click(function (){
        startBacktestingUsingSettings();
    });
    $("#backtester-stop-button").click(function (){
        const url = $("#backtester-stop-button").data("stop-backtesting-url");
        send_and_interpret_bot_update({}, url, null, generic_request_success_callback, generic_request_failure_callback);
    });
}

function postCollectorDoneCallback(){
    $("#collector_progress_bar_title").addClass(hidden_class)
    setToolboxHeight($(".main-toolbox-tabs").outerHeight(true));
}

function collectorCollectingCallback(){
    $("#collector_progress_bar_title").removeClass(hidden_class)
    _reduceToolboxTabHeightWhenProgressBar();
}

function postBacktestingDoneCallback(){
    $("#backtesting_progress_bar_title").addClass(hidden_class)
    setToolboxHeight($(".main-toolbox-tabs").outerHeight(true));
    const update_url = $("#charts").data("backtesting-run-id-url")
    send_and_interpret_bot_update({}, update_url, null, backtestingRunIdFetchedCallback, generic_request_failure_callback, "GET");
}

function backtestingComputingCallback(){
    $("#backtesting_progress_bar_title").removeClass(hidden_class)
    $("#collector_progress_bar_title").addClass(hidden_class)
    _reduceToolboxTabHeightWhenProgressBar();
}

function _reduceToolboxTabHeightWhenProgressBar(){
    const currentToolbarHeight =  $(".main-toolbox-tabs").outerHeight(true)
    const currentBacktestingProgressBar = $("#main_progress_bar").outerHeight(true)
    setToolboxHeight(`${currentBacktestingProgressBar}px - ${currentToolbarHeight}`);
}

function backtestingRunIdFetchedCallback(updated_data, update_url, dom_root_element, msg, status){
    initBacktestingRunSelector(true)
}

function reloadRequestSuccessCallback(updated_data, update_url, dom_root_element, msg, status){
    (new Promise(updateSymbolGraphs)).then(() => initBacktestingRunSelector(false));
    startBacktestingUsingSettings();
}


function startBacktestingUsingSettings(){
    const backtestingUrl = $("#reload-script").data("backtesting-url")
    const startDate = $("#startDate");
    const endDate = $("#endDate");
    const data = {
        exchange_id: getExchangeId(),
        start_timestamp: startDate.val().length ? (new Date(startDate.val()).getTime()) : null,
        end_timestamp: endDate.val().length ? (new Date(endDate.val()).getTime()) : null,
    }
    start_backtesting(data, backtestingUrl);
}

function handleMainNavBarWidthChange(){
    const currentMainDropDownWidth = $(".main-dropdown-menu").outerWidth(true)
    const currentNavBarRightWidth = $("#nav-bar-right").outerWidth(true)
    const newNavBarLeftWidth = "calc(100% - " + currentNavBarRightWidth + "px)"
    $("#nav-bar-left").css("max-width", newNavBarLeftWidth)
    $("#nav-bar-left").css("min-width", newNavBarLeftWidth)

    const currentTimeFrameDropdownWidth = $("#config-activated-time-frame-selector").outerWidth(true)
    const currentActiveTfTabsWidth = $("#time-frame-selector").outerWidth(true)
    $("#pairs-tabs").css("max-width", "calc(100% - " + currentTimeFrameDropdownWidth + "px - " + currentActiveTfTabsWidth + "px)")

}

// show hide when not in charts crosshair
function handleCrosshairVisibility(){
    const charts = $("#pairs-tabcontent");
    charts.on('mouseover', function(event){showCrosshair()});
    charts.on('mouseout', function(event){hideCrosshair()});
    const backtestingChart = $("#backtesting-run-overview");
    backtestingChart.on('mouseover', function(event){showCrosshair()});
    backtestingChart.on('mouseout', function(event){hideCrosshair()});
}

function hideCrosshair(){
   $(".hair").css("display", "none")
}

function showCrosshair(){
   $(".hair").css("display", "block")
}

function updateWindowSizes(){
    const currentChartsHeight = $("#pairs-tabcontent").outerHeight(true)
    const currentMainMenuSize = $("#pairs-tabs").outerHeight(true)
    const currentFooterSize = $("footer.page-footer").outerHeight(true)
    const currentHeaderFooterSize = currentFooterSize + currentMainMenuSize;
    const currentTotalCalcSize =  currentHeaderFooterSize + currentChartsHeight
    const newToolboxHeight = "calc(100vh - " + currentTotalCalcSize + "px)";
    $("#toolbox").css("height", newToolboxHeight);

    const newStrategyBodyHeight =  "calc(100% - " + currentHeaderFooterSize + "px)"
    $(".strategy_body").css("height", newStrategyBodyHeight);

    const currentToolbarHeight =  $(".main-toolbox-tabs").outerHeight(true)
    const newChartsMaxHeight =  "calc(100% - " + currentToolbarHeight + "px)"
    $("#pairs-tabcontent").css("max-height", newChartsMaxHeight);

    const newTabContentHeight = newChartsMaxHeight
    $("#toolbox-tabcontent").css("height", newTabContentHeight)


    const currentMainChartHeight = $("#main-chart-outer").outerHeight(true)
    const newSubChartHeight = "calc(100% - 4px - " + currentMainChartHeight + "px)" /* 4px is from the slider draggable*/
    $("#sub-chart").css("height", newSubChartHeight)


    const currentBacktestingTableHeight = $("#backtesting-table").outerHeight(true)
    if (currentBacktestingTableHeight != 0) {
        const newBacktestingChartHeight = "calc(100% - 4px - " + currentBacktestingTableHeight + "px)" /* 4px is from the slider draggable*/
        $("#backtesting-run-overview").css("height", newBacktestingChartHeight)
    } else {
        const newBacktestingChartHeight = "calc(65% - 4px - " + currentBacktestingTableHeight + "px)" /* 4px is from the slider draggable*/
        $("#backtesting-run-overview").css("height", newBacktestingChartHeight)
    }
    handleScreenSizeButtons(currentChartsHeight);
}
/** resize only on window change **/
function handleBrowserWindowSizeChange (){
    const currentBacktestingTabsHeight = $("#backtesting-tabs").outerHeight(true)
    $("#backtesting-tabcontent").css("height", "calc(100% - " + currentBacktestingTabsHeight + "px)")
    const currentOptimizerTabsHeight = $("#optimizer-tabs").outerHeight(true)
    $("#optimizer-tabcontent").css("height", "calc(100% - " + currentBacktestingTabsHeight + "px)")
    updateWindowSizes()
}

function handleScreenSizeButtons(currentChartsHeight){
    if (currentChartsHeight != 0){
        $(".fullscreen-size-btn.fullscreen").removeClass("is-full-screen");
        } else {
        $(".fullscreen-size-btn.fullscreen").addClass("is-full-screen");
    }

    const currentToolBoxHeight =  $("#toolbox-tabcontent").outerHeight(true)
    if (currentToolBoxHeight === 0){
        $(".fullscreen-size-btn.minimize").addClass("is-minimized");
        $(".fullscreen-size-btn.minimize i").removeClass("far fa-window-minimize");
        $(".fullscreen-size-btn.minimize i").addClass("fas fa-chevron-up");
    } else {
        $(".fullscreen-size-btn.minimize").removeClass("is-minimized");
        $(".fullscreen-size-btn.minimize i").removeClass("fas fa-chevron-up");
        $(".fullscreen-size-btn.minimize i").addClass("far fa-window-minimize");
    }
}

function fullScreenToggle(){
    const currentChartsHeight = $("#pairs-tabcontent").outerHeight(true)
    if (currentChartsHeight != 0){
        $("#pairs-tabcontent").css("height", "0px");
    } else {
        $("#timeframepairs-tabcontent").css("height", "55vh");
    }
    updateWindowSizes();
    updateToolboxDisplay();
}


function updateToolboxDisplay(){
    const activeTab = $("#toolbox-tabcontent").children(".tab-pane.show.active");
    const activeSubTab = activeTab.find(".tab-pane.show.active");
    refreshElements(`#${activeSubTab.attr("id")}`);
}


function minimizeScreenToggle(){
    const currentToolBoxHeight =  $("#toolbox-tabcontent").outerHeight(true)
    if (currentToolBoxHeight === 0){
        $("#pairs-tabcontent").css("height", "55vh");
    } else {
        $("#pairs-tabcontent").css("height", "100%");
    }
    updateWindowSizes();
}

function resizeOnToolBoxTabClicks(){
    const currentToolBoxHeight =  $("#toolbox-tabcontent").outerHeight(true)
    if (currentToolBoxHeight === 0){
        $("#pairs-tabcontent").css("height", "35vh");
        updateWindowSizes();
    }
}

function handleResizables(){
    $(".resizable").resizable();
    $(".resizable").on("resize", updateWindowSizes());
    window.addEventListener('resize', function(event){handleBrowserWindowSizeChange ()});
    $("#pairs-tabcontent").on('resize', function(event){updateWindowSizes()});
    $("#time-frame-selector").on('resize', function(event){handleMainNavBarWidthChange()});
    window.addEventListener('resize', function(event){handleMainNavBarWidthChange()});
    $("#backtesting-table").on('resize', function(event){updateWindowSizes()});
    $(".fullscreen-size-btn.fullscreen").on('click', function(event){fullScreenToggle()});
    $(".fullscreen-size-btn.minimize").on('click', function(event){minimizeScreenToggle()});
    $(".open-toolbox-onclick").on('click', function(event){resizeOnToolBoxTabClicks()});
}

function updateBacktestingSelector(updated_data, update_url, dom_root_element, msg, status){
    function updateSelection(event, selected){
        if(typeof event.recid !== "undefined"){
            updateBacktestingAnalysisReport(getIdFromTableRow(w2ui[event.target], event.recid),
                getOptimizerIdFromTableRow(event.recid), selected);
        }
        if(typeof event.recids !== "undefined"){
            event.recids.forEach(function (id){
                updateBacktestingAnalysisReport(getIdFromTableRow(w2ui[event.target], id),
                    getOptimizerIdFromTableRow(id), selected);
            })
        }
    }
    backtestingTableName = createBacktestingMetadataTable(msg.data, updateSelection,
        updated_data.forceSelectLatestBacktesting)
}

function initBacktestingRunSelector(forceSelectLatestBacktesting){
    const data = {
        forceSelectLatestBacktesting: forceSelectLatestBacktesting
    }
    send_and_interpret_bot_update(data, $("#backtesting-run-select-table").data("url"), null,
        updateBacktestingSelector, generic_request_failure_callback, "GET");
}

function updateBacktestingReport(updated_data, update_url, dom_root_element, msg, status){
    updateDisplayedElement(msg, true, editors, true, updated_data.id, updated_data.optimizer_id, updated_data.added, backtestingTableName, updated_data.id,)
}

function updateBacktestingAnalysisReport(run_id, optimizer_id, addReport){
    const fullId = mergeBacktestingOptimizerID(run_id, optimizer_id);
    if(addReport && displayedRunIds.indexOf(fullId) === -1){
        displayedRunIds.push(fullId)
    }
    if(!addReport && displayedRunIds.indexOf(fullId) !== -1){
        displayedRunIds.splice(displayedRunIds.indexOf(fullId), 1);
    }
    // upper charts
    displayChartsAndInputs(true, run_id, optimizer_id, addReport, getSelectedSymbol(), getSelectedTimeFrame(), false, null, null)
    // toolbox
    const data = {
        id: run_id,
        optimizer_id: optimizer_id,
        exchange: getExchangeName(),
        symbol: getSelectedSymbol(),
        time_frame: getSelectedTimeFrame(),
        added: addReport,
    }
    send_and_interpret_bot_update(data, $("#backtesting-run-overview").data("url"), null,
        updateBacktestingReport, generic_request_failure_callback);
}

function updateTentacleConfigurations(url, tentaclesConfigByTentacle, startBacktesting){
    send_and_interpret_bot_update(tentaclesConfigByTentacle, url, null,
        startBacktesting ? handle_tentacle_config_update_success_start_backtesting_callback: handle_tentacle_config_update_success_callback,
        handle_tentacle_config_update_error_callback);
}

function handle_tentacle_config_update_success_callback(updated_data, update_url, dom_root_element, msg, status){
    create_alert("success", "Configuration saved", msg);
}

function handle_tentacle_config_update_success_start_backtesting_callback(updated_data, update_url, dom_root_element, msg, status){
    create_alert("success", "Configuration saved", msg);
    reloadRequestSuccessCallback(null, null, null, null, null);
}

function handle_tentacle_config_update_error_callback(updated_data, update_url, dom_root_element, msg, status){
    create_alert("error", "Error when updating config", msg.responseText);
}

function handleTimeFramesSelector(){
    const timeFramesSelector = $("#time-frame-selector");
    timeFramesSelector.find(".active-timeframe").each(function () {
        $(this).click(function (){
            const activatedTimeFrame = $(this).data("time-frame");
            if(activatedTimeFrame !== getSelectedTimeFrame()){
                timeFramesSelector.find(".active-timeframe").each(function () {
                    const tfSelect = $(this);
                    if($(this).data("time-frame") !== activatedTimeFrame){
                        tfSelect.removeClass("selected")
                    }else{
                        tfSelect.addClass("selected")
                    }
                });
                updateSymbolGraphs(null, null);
            }
        });
    })
}

function handleConfigTimeFramesSelectors(){
    const configTimeFramesSelector = $("#config-activated-time-frame-selector");
    configTimeFramesSelector.on("hide.bs.dropdown", function (){
        const tentacle = configTimeFramesSelector.data("strategy-tentacle")
        if(tentacle !== "None"){
            const activatedTimeFrames = []
            configTimeFramesSelector.find("input.config-time-frame-selector:checked:enabled").each(function (){
                activatedTimeFrames.push($(this).data("time-frame"));
            })
            const tentaclesConfigByTentacle = {};
            tentaclesConfigByTentacle[tentacle] = {
                required_time_frames: activatedTimeFrames
            }
            updateTentacleConfigurations(configTimeFramesSelector.data("strategy-config-url"), tentaclesConfigByTentacle, false)
        }
    })
}

function check_config(editor){
    const errors = editor.validate();
    return !errors.length;
}

function handleUserInputsActions(){
    $(".user-input-save").click(function () {
        const tentaclesConfigByTentacle = {};
        let save = true;
        $(".user-input-config").each(function (index, element){
            const tentacle = $(element).data("tentacle");
            if (editors.hasOwnProperty(tentacle)){
                if (check_config(editors[tentacle]))
                    tentaclesConfigByTentacle[tentacle] = editors[tentacle].getValue();
                else {
                    save = false;
                    create_alert("error", `Error when saving ${tentacle} configuration`, "Invalid configuration data.");
                }
            }
        });
        if (save){
            updateTentacleConfigurations($(this).data("url"), tentaclesConfigByTentacle, false);
        }
    })
}

function handleOptimizerActions(){
    $("#optimizer-input-save-and-start-button").click(function (){
        const url = $(this).data("config-url");
        const updatedConfig = {
            config: getOptimizerSettingsValues()
        };
        send_and_interpret_bot_update(updatedConfig, url, null, handleOptimizerConfigUpdateSuccessCallback, handle_tentacle_config_update_error_callback);
    })
    $("#optimizer-cancel-button").click(function (){
        const url = $(this).data("url");
        send_and_interpret_bot_update({}, url, null, generic_request_success_callback, generic_request_failure_callback);
    })
    $("#optimizer-resume-button").click(function (){
        const url = $(this).data("url");
        send_and_interpret_bot_update({}, url, null, optimizerResumedSuccessCallback, generic_request_failure_callback);
    })
}

function optimizerResumedSuccessCallback(updated_data, update_url, dom_root_element, msg, status){
    create_alert("success", "Strategy optimizer is resuming.", msg);
    check_optimizer_state();
}

function handleOptimizerConfigUpdateSuccessCallback(updated_data, update_url, dom_root_element, msg, status){
    create_alert("success", "Optimizer configuration saved", msg);
    startStrategyDesignOptimizer();
}

function refreshElements(parentElementSelector){
    const parentElement = $(parentElementSelector);
    parentElement.find(".w2ui-grid").each(function (index, child){
        $(child).w2grid().refresh();
    })
    parentElement.find(".plot-container.plotly").each(function (index, child){
        Plotly.relayout($(child).parent().attr("id"), {autosize: true});
    })
}

function handleTabSelectionEvents(){
    const refreshedTabs = [
        "backtesting-results-tab",
        "performance-summary-tab",
        "list-of-trades-tab",
        "strategy-optimizer-queue-tab",
        "backtesting-tab",
        "optimizer-tab",
    ]
    refreshedTabs.forEach(function (tab){
        $(`#${tab}`).on("shown.bs.tab", function (event){
            refreshElements($(event.target).attr("href"));
        })
    })
}

function startStrategyDesignOptimizer(){
    const url = $("#optimizer-input-save-and-start-button").data("start-url");
    const updatedConfig = {
        config: getOptimizerSettingsValues(),
        exchange_id: getExchangeId()
    };
    send_and_interpret_bot_update(updatedConfig, url, null, startStrategyOptimizerSuccessCallback, generic_request_failure_callback);
}

function startStrategyOptimizerSuccessCallback(updated_data, update_url, dom_root_element, msg, status){
    create_alert("success", "Optimizer started", msg);
    check_optimizer_state();
    init_optimizer_queue_editor();
}

function checkOptimizerResumability(optimizerQueue){
    const resumeButton = $("#optimizer-resume-button");
    const startButton = $("#optimizer-input-save-and-start-button");
    if(optimizerQueue.length){
        if(previousOptimizerStatus === "computing"){
            // still running
            resumeButton.addClass(hidden_class);
            startButton.addClass("disabled");
        }else{
            // not running
            resumeButton.removeClass(hidden_class);
            startButton.removeClass("disabled");
        }
    }
}

const editors = {};

function on_optimizer_state_update(data){
    const status = data["status"];
    const progress_bar = $("#main_progress_bar");
    const cancelButton = $("#optimizer-cancel-button");
    const resumeButton = $("#optimizer-resume-button");
    const startButton = $("#optimizer-input-save-and-start-button");
    const currentToolbarHeight =  $(".main-toolbox-tabs").outerHeight(true)
    if(status === "computing") {
        $("#optimizer_progress_bar_title").removeClass(hidden_class)
        cancelButton.removeClass(hidden_class);
        resumeButton.addClass(hidden_class);
        startButton.addClass("disabled");
        $("#main_progress_bar_title").addClass(hidden_class)
        const overall_progress = data["overall_progress"];
        progress_bar.show();

        const currentBacktestingProgressBar = $("#main_progress_bar").outerHeight(true)
        setToolboxHeight(`${currentBacktestingProgressBar}px - ${currentToolbarHeight}`);

        updateBacktestingProgress(overall_progress);
        setTimeout(function (){check_optimizer_state();}, 500)
    }else{
        cancelButton.addClass(hidden_class);
        startButton.removeClass("disabled");
        $("#optimizer_progress_bar_title").addClass(hidden_class)
        $("#main_progress_bar_title").removeClass(hidden_class)
        progress_bar.hide();

        setToolboxHeight(currentToolbarHeight);
    }
    if(status === "finished" && previousOptimizerStatus === "computing"){
        postBacktestingDoneCallback();
        init_optimizer_queue_editor();
    }
    previousOptimizerStatus = status;
}

function setToolboxHeight(height){
    $("#toolbox-tabcontent").css("height", `calc(100% - ${height}px)`)
}

function check_optimizer_state(){
    optimizerSocket.emit("strategy_optimizer_status");
}

function init_optimizer_status_websocket(){
    optimizerSocket.on("strategy_optimizer_status", function (data) {
        on_optimizer_state_update(data);
    });
    check_optimizer_state();
}

function init_optimizer_queue_editor(){
    const queue_url = $("#strategy-optimizer-queue-table").data("queue-url")
    send_and_interpret_bot_update({}, queue_url, null,
        optimizerQueueFetchedCallback, generic_request_failure_callback, "GET");

}

function optimizerQueueFetchedCallback(optimizer_queue, update_url, dom_root_element, msg, status){
    handleOptimizerQueue(msg.queue)
}

function queueUpdateCallback(updatedQueue){
    const queue_url = $("#strategy-optimizer-queue-table").data("queue-url")
    send_and_interpret_bot_update({queue: updatedQueue}, queue_url, null,
        optimizerQueueUpdatedCallback, optimizerQueueUpdateFailureCallback);
}

function optimizerQueueUpdatedCallback(optimizer_queue, update_url, dom_root_element, msg, status){
    create_alert("success", "Optimizer queue updated", msg);
    handleOptimizerQueue(msg.queue)
}

function optimizerQueueUpdateFailureCallback(optimizer_queue, update_url, dom_root_element, msg, status){
    create_alert("error", "Error when updating optimizer queue", msg.responseJSON.message);
    handleOptimizerQueue(msg.responseJSON.queue)
}

function handleOptimizerQueue(optimizerQueue){
    checkOptimizerResumability(optimizerQueue);
    updateOptimizerQueueEditor(optimizerQueue, "strategy-optimizer-queue-table", queueUpdateCallback);
}

function handleDateSelectors(){
    const nowDate = new Date().toISOString().split("T")[0];
    const startDatePicker = $("#startDate");
    const endDatePicker = $("#endDate");
    endDatePicker[0].max = nowDate;
    startDatePicker[0].max = nowDate;
    startDatePicker.on("change", function (){
        $("#endDate")[0].min = $(this).val();
    })
    endDatePicker.on("change", function (){
        $("#startDate")[0].max = $(this).val();
    })
}

function getSelectedSymbol(){
    return $("#pairs-tabs").find(".primary-tab-selector.active").data("symbol");
}

function getSelectedTimeFrame(){
    return $("#time-frame-selector").find(".selected").data("time-frame");
}

function getExchangeId(){
    return $("#strategy_body").data("exchange-id");
}

function getExchangeName(){
    return $("#strategy_body").data("exchange-name");
}

function updateExchangeId(){
    send_and_interpret_bot_update({}, $("#strategy_body").data("exchange-details-url"), null,
        updateExchangeIdCallback, updateExchangeIdFailureCallback, "GET");
}

function updateExchangeIdCallback(requestData, update_url, dom_root_element, msg, status){
    $("#strategy_body").data("exchange-id", msg.exchange_id).data("exchange-name", msg.exchange_name);
    const exchangeLogo = $("#exchange_logo");
    exchangeLogo.attr("alt", msg.exchange_name);
    exchangeLogo.attr("src", "");
    const exchangeLogoBaseURL = exchangeLogo.attr("url").slice(0, exchangeLogo.attr("url").lastIndexOf("/") + 1);
    exchangeLogo.addClass(hidden_class);
    exchangeLogo.attr("url", `${exchangeLogoBaseURL}${msg.exchange_name}`);
    fetch_images();
}

function updateExchangeIdFailureCallback(requestData, update_url, dom_root_element, msg, status, error){
    if(error === "NOT FOUND"){
        // bot might be starting, retry soon
        setTimeout(updateExchangeId, 400)
    }else{
        create_alert("error", "Error when connecting to the exchange", msg.responseText);
    }
}

function updateSymbolGraphs(resolve, reject){
    const selectedSymbol =getSelectedSymbol();
    const selectedTimeFrame = getSelectedTimeFrame();
    displayChartsAndInputs(false, null, null, true, selectedSymbol,selectedTimeFrame, true, resolve, reject);
    displayedRunIds.forEach(function (fullId) {
        const splitIds = fullId.split(ID_SEPARATOR);
        const runID = Number(splitIds[0]);
        const optimizerId = Number(splitIds[1]);
        displayChartsAndInputs(true, runID, optimizerId, true, selectedSymbol,selectedTimeFrame, false, null, null);
    })
}

function handleSymbolSelectors(){
    $(".symbol-selector").on("shown.bs.tab", function (){
        updateSymbolGraphs(null, null);
    })
}

// handle sidebar width change
function updateSideBarWidth(){
    const currentStrategyBodyWidth = $("#strategy_body").outerWidth(true)
    const newSideBarWidth = "calc(100vw - " + currentStrategyBodyWidth + "px)";
    $("#slide-out").css("width", newSideBarWidth);
}

function handleSidebarWidthChange(){
    $("#strategy_body").on('resize', function(event){updateSideBarWidth()});
}

const optimizerSocket = get_websocket("/strategy_optimizer");
const displayedRunIds = [];
let backtestingTableName = undefined;
let previousOptimizerStatus = undefined;


function handleHorizontalScrolling(){
    /** handle horizontal mousewheel scrolling **/
    $.fn.hScroll = function (amount) {
        amount = amount || 120;
        $(this).bind("DOMMouseScroll mousewheel", function (event) {
            var oEvent = event.originalEvent,
                direction = oEvent.detail ? oEvent.detail * -amount : oEvent.wheelDelta,
                position = $(this).scrollLeft();
            position += direction > 0 ? -amount : amount;
            $(this).scrollLeft(position);
            event.preventDefault();
        })
    };
    $('.scroll_horizontal').hScroll(40); // You can pass (optionally) scrolling amount
}

function handleCrossHair(){
    // todo remove from event listener when not on chart instead of display none
    $('#crosshair-h').removeClass(hidden_class);
    $('#crosshair-v').removeClass(hidden_class);
    $(document).on('mousemove',function(e){
        $('#crosshair-h').css('top',e.pageY);
        $('#crosshair-v').css('left',e.pageX);
    });
}

function registerBacktestingAndCollectorsElements(){
    backtestingMainProgressBar = "main_progress_bar";
    backtesting_done_callbacks.push(postBacktestingDoneCallback);
    backtesting_computing_callbacks.push(backtestingComputingCallback);
    collectorMainProgressBar = "main_progress_bar";
    collectorHideProgressBarWhenFinished = false;
    DataCollectorDoneCallbacks.push(postCollectorDoneCallback);
    DataCollectorDoneCallbacks.push(refreshBacktestingStatus);
    DataCollectorCollectingCallbacks.push(collectorCollectingCallback);
    init_backtesting_status_websocket();
    init_data_collector_status_websocket();
}

function initDesignerRemoteObjectsDisplay(){
    (new Promise(updateSymbolGraphs)).then(() => initBacktestingRunSelector(false));
    init_optimizer_queue_editor();
}

$(document).ready(function() {
    handleCrossHair();
    initDesignerRemoteObjectsDisplay();
    handleScriptButtons();
    handleCacheButtons();
    handleBacktestingButtons();
    handleResizables();
    handleBrowserWindowSizeChange();
    updateWindowSizes();
    handleCrosshairVisibility();
    handleUserInputsActions();
    handleOptimizerActions();
    handleTabSelectionEvents();
    handleDateSelectors();
    handleSymbolSelectors();
    handleTimeFramesSelector();
    handleConfigTimeFramesSelectors();
    init_optimizer_status_websocket();
    handleMainNavBarWidthChange();
    handleSidebarWidthChange();
    registerBacktestingAndCollectorsElements()
    handleHorizontalScrolling();
    registerReconnectedCallback(updateExchangeId);
});
