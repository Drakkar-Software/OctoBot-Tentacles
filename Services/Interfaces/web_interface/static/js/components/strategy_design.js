function displayChartsAndInputs(replot, backtestingRunId, added){
    const chartIdentifier = backtestingRunId ? backtestingRunId : "live";
    let url = $("#charts").data("live-url")
    if(replot){
       url = $("#charts").data("backtesting-url") + backtestingRunId
    }
    $.get({
        url: url,
        dataType: "json",
        success: function (data) {
            updateDisplayedElement(data, replot, editors, false, backtestingRunId, added, backtestingTableName, chartIdentifier)
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
        send_and_interpret_bot_update(data, update_url, null, reloadRequestSuccessCallback, generic_request_failure_callback);
    })
}

function postBacktestingDone(){
    const update_url = $("#charts").data("backtesting-run-id-url")
    send_and_interpret_bot_update({}, update_url, null, backtestingRunIdFetchedCallback, generic_request_failure_callback, "GET");
}

function backtestingRunIdFetchedCallback(updated_data, update_url, dom_root_element, msg, status){
    initBacktestingRunSelector()
}

function reloadRequestSuccessCallback(updated_data, update_url, dom_root_element, msg, status){
    const reloadScript = $("#reload-script");
    const backtestingUrl = reloadScript.data("backtesting-url")
    const data = {
        exchange_id: reloadScript.data("exchange-id"),
        // start_timestamp: 1633095582000,    // TODO (Friday 1 October 2021 13:39:42)
        start_timestamp: 1635757030000,    // TODO (Monday 1 November 2021 08:57:10)
        end_timestamp: new Date().getTime(),    // TODO (today)
    }
    start_backtesting(data, backtestingUrl);
}


function updateWindowSizes(){
    const currentChartsHeight = $("#charts").outerHeight(true)
    const currentMainMenuSize = $("nav.navbar.navbar-expand-md.navbar-dark").outerHeight(true)
    const currentFooterSize = $("footer.page-footer").outerHeight(true)
    const currentHeaderFooterSize = currentFooterSize + currentMainMenuSize;
    const currentTotalCalcSize =  currentHeaderFooterSize + currentChartsHeight
    const newToolboxHeight = "calc(100vh - " + currentTotalCalcSize + "px)";
    $("#toolbox").css("height", newToolboxHeight);

    const newStrategyBodyHeight =  "calc(100% - " + currentHeaderFooterSize + "px)"
    $(".strategy_body").css("height", newStrategyBodyHeight);

    const currentToolbarHeight =  $(".toolbox-tabs").outerHeight(true)
    const newChartsMaxHeight =  "calc(100% - " + currentToolbarHeight + "px)"
    $("#charts").css("max-height", newChartsMaxHeight);

    const newTabContentHeight = newChartsMaxHeight
    $(".tab-content").css("height", newTabContentHeight)

    const currentMainChartHeight = $("#main-chart").outerHeight(true)
    const newSubChartHeight = "calc(100% - 4px - " + currentMainChartHeight + "px)" /* 4px is from the slider draggable*/
    $("#sub-chart").css("height", newSubChartHeight)


    const currentBacktestingTableHeight = $("#backtesting-table").outerHeight(true)
    if (currentBacktestingTableHeight != 0) {
        const newBacktestingChartHeight = "calc(100% - 4px - " + currentBacktestingTableHeight + "px)" /* 4px is from the slider draggable*/
        $("#backtesting-chart").css("height", newBacktestingChartHeight)
    } else {
        const newBacktestingChartHeight = "calc(65% - 4px - " + currentBacktestingTableHeight + "px)" /* 4px is from the slider draggable*/
        $("#backtesting-chart").css("height", newBacktestingChartHeight)
    }
    handleScreenSizeButtons(currentChartsHeight);
}

function handleScreenSizeButtons(currentChartsHeight){
    if (currentChartsHeight != 0){
        $(".fullscreen-size-btn.fullscreen").removeClass("is-full-screen");
        } else {
        $(".fullscreen-size-btn.fullscreen").addClass("is-full-screen");
    }

    const currentToolBoxHeight =  $(".strategy-toolbox").outerHeight(true)
    if (currentToolBoxHeight <= 45){
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
    const currentChartsHeight = $("#charts").outerHeight(true)
    if (currentChartsHeight != 0){
        $("#charts").css("height", "0px");
    } else {
        $("#charts").css("height", "55vh");
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
    const currentToolBoxHeight =  $(".strategy-toolbox").outerHeight(true)
    if (currentToolBoxHeight <= 45){
        $("#charts").css("height", "55vh");
    } else {
        $("#charts").css("height", "100%");
    }
    updateWindowSizes();
}

function resizeOnToolBoxTabClicks(){
    const currentToolBoxHeight =  $(".strategy-toolbox").outerHeight(true)
    if (currentToolBoxHeight <= 45){
        $("#charts").css("height", "35vh");
        updateWindowSizes();
    }
}


function handleResizables(){
    $(".resizable").resizable();
    $(".resizable").on("resize", updateWindowSizes());
    window.addEventListener('resize', function(event){updateWindowSizes()});
    $("#charts").on('resize', function(event){updateWindowSizes()});
    $("#backtesting-table").on('resize', function(event){updateWindowSizes()});
    $(".fullscreen-size-btn.fullscreen").on('click', function(event){fullScreenToggle()});
    $(".fullscreen-size-btn.minimize").on('click', function(event){minimizeScreenToggle()});
    $(".main-toolbox-tabs li").on('click', function(event){resizeOnToolBoxTabClicks()});
    updateWindowSizes();
}

function updateBacktestingSelector(updated_data, update_url, dom_root_element, msg, status){
    function updateSelection(event, selected){
        if(typeof event.recid !== "undefined"){
            updateBacktestingAnalysisReport(w2ui[event.target].get(event.recid).id, selected);
        }
        if(typeof event.recids !== "undefined"){
            event.recids.forEach(function (id){
                updateBacktestingAnalysisReport(w2ui[event.target].get(id).id, selected);
            })
        }
    }
    backtestingTableName = createBacktestingMetadataTable(msg.data, updateSelection)
}

function initBacktestingRunSelector(){
    send_and_interpret_bot_update({}, $("#backtesting-run-select-table").data("url"), null,
        updateBacktestingSelector, generic_request_failure_callback, "GET");
}

function updateBacktestingReport(updated_data, update_url, dom_root_element, msg, status){
    updateDisplayedElement(msg, true, editors, true, updated_data.id, updated_data.added, backtestingTableName, updated_data.id,)
}

function updateBacktestingAnalysisReport(run_id, addReport){
    // upper charts
    displayChartsAndInputs(true, run_id, addReport)
    // toolbox
    send_and_interpret_bot_update({id: run_id, added: addReport}, $("#backtesting-chart").data("url"), null,
        updateBacktestingReport, generic_request_failure_callback);
}

function updateTentacleConfig(saveButton, updatedConfig){
    const update_url = saveButton.data("url");
    send_and_interpret_bot_update(updatedConfig, update_url, null, handle_tentacle_config_update_success_callback, handle_tentacle_config_update_error_callback);
}

function handle_tentacle_config_update_success_callback(updated_data, update_url, dom_root_element, msg, status){
    create_alert("success", "Configuration saved", msg);
    reloadRequestSuccessCallback(null, null, null, null, null);
}

function handle_tentacle_config_update_error_callback(updated_data, update_url, dom_root_element, msg, status){
    create_alert("error", "Error when updating config", msg.responseText);
}

function check_config(editor){
    const errors = editor.validate();
    return !errors.length;
}

function handleUserInputsActions(){
    $(".user-input-save").click(function () {
        const editor = editors[$(this).data("tentacle")];
        if (check_config(editor))
            updateTentacleConfig($(this), editor.getValue());
        else
            create_alert("error", "Error when saving configuration", "Invalid configuration data.");
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
        "strategy-optimizer-results-tab",
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
    const startOptimizerButton  = $("#optimizer-input-save-and-start-button");
    const url = startOptimizerButton.data("start-url");
    const updatedConfig = {
        config: getOptimizerSettingsValues(),
        exchange_id: startOptimizerButton.data("exchange-id")
    };
    send_and_interpret_bot_update(updatedConfig, url, null, startStrategyOptimizerSuccessCallback, generic_request_failure_callback);
}

function startStrategyOptimizerSuccessCallback(updated_data, update_url, dom_root_element, msg, status){
    create_alert("success", "Optimizer started", msg);
    check_optimizer_state();
}

const editors = {};

function on_optimizer_state_update(data){
    const status = data["status"];
    const progress_bar = $("#backtesting_progress_bar");
    const cancelButton = $("#optimizer-cancel-button");
    if(status === "computing") {
        $("#optimizer_progress_bar_title").removeClass(hidden_class)
        cancelButton.removeClass(hidden_class);
        $("#backtesting_progress_bar_title").addClass(hidden_class)
        const overall_progress = data["overall_progress"];
        progress_bar.show();
        update_progress(overall_progress);
        setTimeout(function (){check_optimizer_state();}, 500)
    }else{
        cancelButton.addClass(hidden_class);
        $("#optimizer_progress_bar_title").addClass(hidden_class)
        $("#backtesting_progress_bar_title").removeClass(hidden_class)
        progress_bar.hide();
    }
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

const optimizerSocket = get_websocket("/strategy_optimizer");
let backtestingTableName = undefined;

$(document).ready(function() {
    displayChartsAndInputs(false, null, true);
    initBacktestingRunSelector();
    handleScriptButtons();
    handleResizables();
    handleUserInputsActions();
    handleOptimizerActions();
    handleTabSelectionEvents();
    init_backtesting_status_websocket();
    init_optimizer_status_websocket();
    backtesting_done_callbacks.push(postBacktestingDone)
});
