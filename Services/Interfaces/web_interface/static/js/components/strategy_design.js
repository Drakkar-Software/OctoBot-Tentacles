function displayChartsAndInputs(replot){
    $.get({
        url: $("#charts").data("url"),
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
        send_and_interpret_bot_update(data, update_url, null, reload_request_success_callback, generic_request_failure_callback);

    })
}

function reload_request_success_callback(updated_data, update_url, dom_root_element, msg, status){
    displayChartsAndInputs(true);
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
}

function handleResizables(){
    $(".resizable").resizable();
    $(".resizable").on("resize", updateWindowSizes());
    window.addEventListener('resize', function(event){updateWindowSizes()});
    $("#charts").on('resize', function(event){updateWindowSizes()});
    updateWindowSizes();
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

function updateTentacleConfig(saveButton, updatedConfig){
    const update_url = saveButton.data("url");
    log(update_url)
    send_and_interpret_bot_update(updatedConfig, update_url, null, handle_tentacle_config_update_success_callback, handle_tentacle_config_update_error_callback);
}

function handle_tentacle_config_update_success_callback(updated_data, update_url, dom_root_element, msg, status){
    create_alert("success", "Configuration saved", msg);
    displayChartsAndInputs(true);
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

const editors = {};

$(document).ready(function() {
    displayChartsAndInputs(false);
    asyncInit();
    handleScriptButtons();
    handleResizables();
    handleSelects();
    handleUserInputsActions();
});
