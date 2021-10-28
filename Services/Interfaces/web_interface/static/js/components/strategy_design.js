
function updateCharts(data){
    const chartDivs = [];
    data.data.sub_elements.forEach(function (sub_element) {
        const chartData = [];
        const divID = sub_element.name;
        sub_element.data.elements.forEach(function (chartDetails){
            const chartedElements = {
              x: chartDetails.x,
              mode: chartDetails.kind,
              type: chartDetails.kind,
              name: chartDetails.title,
            }
            if(chartDetails.y !== null){
                chartedElements.y = chartDetails.y
            }
            if(chartDetails.open !== null){
                chartedElements.open = chartDetails.open
            }
            if(chartDetails.high !== null){
                chartedElements.high = chartDetails.high
            }
            if(chartDetails.low !== null){
                chartedElements.low = chartDetails.low
            }
            if(chartDetails.close !== null){
                chartedElements.close = chartDetails.close
            }
            if(chartDetails.volume !== null){
                chartedElements.volume = chartDetails.volume
            }
            chartData.push(chartedElements);
            const xaxis = {
                autorange: true,
                rangeslider: {
                    visible: false,
                }
            };
            if(chartDetails.x_type !== null){
                xaxis.type = chartDetails.x_type;
            }
            const yaxis = {
                fixedrange: true,
            };
            if(chartDetails.y_type !== null){
                yaxis.type = chartDetails.y_type;
            }
            const layout = {
                autosize: true,
                // height: 500,
                margin: {
                    l: 50,
                    r: 50,
                    b: 15,
                    t: 25,
                    pad: 0
                },
                xaxis: xaxis,
                yaxis: yaxis,
            };
            const plotlyConfig = {
                scrollZoom: true,
                modeBarButtonsToRemove: ["select2d", "lasso2d", "toggleSpikelines"],
                responsive: true,
                showEditInChartStudio: true,
                displaylogo: false // no logo to avoid 'rel="noopener noreferrer"' security issue (see https://webhint.io/docs/user-guide/hints/hint-disown-opener/)
            };
            Plotly.newPlot(divID, chartData, layout, plotlyConfig);
            chartDivs.push($(`#${divID}`))

        });
    });
    chartDivs[0][0].on("plotly_relayout", function(eventdata) {
        Plotly.relayout("sub-chart", eventdata);
    });
    // chartDivs[1][0].on("plotly_relayout", function(eventdata) {
    //     Plotly.relayout("main-chart", eventdata);
    // });
}

function displayCharts(){
    $.get({
        url: $("#charts").data("url"),
        dataType: "json",
        success: function (data) {
            updateCharts(data)
        },
        error: function(result, status) {
            const errorMessage = `Impossible to get charting data: ${result.responseText}. More details in logs.`;
            $("#main-chart").text(errorMessage)
            window.console && console.error(errorMessage);
        }
    });
}

function handleScriptButtons(){
    $("#reload-script").click(function (){
        const update_url = $("#reload-script").data("url")
        send_and_interpret_bot_update({}, update_url, null, reload_request_success_callback, generic_request_failure_callback);

    })
}

function reload_request_success_callback(updated_data, update_url, dom_root_element, msg, status){
    displayCharts();
}

function handleResizables(){
    $(".resizable").resizable();
    $(".resizable").on("resize", function (eventData){
        let otherDiv = "charts";
        if(eventData.currentTarget.id === "charts"){
            otherDiv = "toolbox";
        }
        document.getElementById(otherDiv).style.height = eventData.currentTarget.style.height;
    });
}

$(document).ready(function() {
    displayCharts();
    handleScriptButtons();
    handleResizables();
});
