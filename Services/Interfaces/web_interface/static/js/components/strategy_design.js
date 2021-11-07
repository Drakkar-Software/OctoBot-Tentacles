function displayChartsAndInputs(replot, backtestingRunId){
    let url = $("#charts").data("live-url")
    if(replot){
       url = $("#charts").data("backtesting-url") + backtestingRunId
    }
    $.get({
        url: url,
        dataType: "json",
        success: function (data) {
            updateChartsAndInputs(data, replot, editors)
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
    const backtestingRunId = msg.id;
    displayChartsAndInputs(true, backtestingRunId)
    initBacktestingRunSelect()
}

function reloadRequestSuccessCallback(updated_data, update_url, dom_root_element, msg, status){
    const reloadScript = $("#reload-script");
    const backtestingUrl = reloadScript.data("backtesting-url")
    const data = {
        exchange_id: reloadScript.data("exchange-id"),
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
}

function handleResizables(){
    $(".resizable").resizable();
    $(".resizable").on("resize", updateWindowSizes());
    window.addEventListener('resize', function(event){updateWindowSizes()});
    $("#charts").on('resize', function(event){updateWindowSizes()});
    $("#backtesting-table").on('resize', function(event){updateWindowSizes()});

    updateWindowSizes();
}

function updateBacktestingSelect(updated_data, update_url, dom_root_element, msg, status){
    const select = $("#backtesting-run-select");
    select.empty();
    // select.selectpicker("refresh");
    msg.data.sort()
    let defaultVal = null
    msg.data.reverse().forEach(function(element){
        const date = new Date(element.timestamp * 1000)
        const displayedTime = `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`
        select.append(new Option(`${element.id} ${element.name} ${displayedTime}`, element.id,
            defaultVal === null, defaultVal === null));
        if(defaultVal === null){
            defaultVal = element.id;
        }
    })
    select.selectpicker("refresh");
    select.val(defaultVal).selectpicker("refresh");
    triggerBacktestingSelectUpdate();
}

function initBacktestingRunSelect(){
    send_and_interpret_bot_update({}, $("#backtesting-run-select").data("url"), null,
        updateBacktestingSelect, generic_request_failure_callback, "GET");
}

function asyncInit(){
    initBacktestingRunSelect();
}

function updateBacktestingReport(updated_data, update_url, dom_root_element, msg, status){
    updateBacktestingChart(msg, "backtesting-chart", true);
}

function triggerBacktestingSelectUpdate(){
    updateBacktestingAnalysisReport($("#backtesting-run-select").val())
}

function updateBacktestingAnalysisReport(run_id){
    send_and_interpret_bot_update({id: run_id}, $("#backtesting-chart").data("url"), null,
        updateBacktestingReport, generic_request_failure_callback);
}

function handleSelects(){
    $("#backtesting-run-select").on("change", triggerBacktestingSelectUpdate);
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
}

const editors = {};

function on_optimizer_state_update(data){
    const status = data["status"];
    const progress_bar = $("#backtesting_progress_bar");
    if(status === "computing") {
        $("#optimizer_progress_bar_title").removeClass(hidden_class)
        $("#backtesting_progress_bar_title").addClass(hidden_class)
        const overall_progress = data["overall_progress"];
        progress_bar.show();
        update_progress(overall_progress);
    }else{
        $("#optimizer_progress_bar_title").addClass(hidden_class)
        $("#backtesting_progress_bar_title").removeClass(hidden_class)
        progress_bar.hide();
    }
}

function check_optimizer_state(socket){
    socket.emit("strategy_optimizer_status");
}

function init_optimizer_status_websocket(){
    const socket = get_websocket("/strategy_optimizer");
    socket.on("strategy_optimizer_status", function (data) {
        on_optimizer_state_update(data);
    });
    setInterval(function(){check_optimizer_state(socket);}, 500);
    return socket;
}

$(document).ready(function() {
    displayChartsAndInputs(false, null);
    asyncInit();
    handleScriptButtons();
    handleResizables();
    handleSelects();
    handleUserInputsActions();
    handleOptimizerActions();
    init_backtesting_status_websocket();
    init_optimizer_status_websocket();
    backtesting_done_callbacks.push(postBacktestingDone)
});
