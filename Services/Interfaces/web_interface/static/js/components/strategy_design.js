const resizeObserver = new ResizeObserver(entries => {
    log("resize")
    for (let entry of entries) {
        Plotly.Plots.resize(entry.target);
    }
});

function updateCharts(data){
    const chartDivs = [];
    let mainLayout = undefined;
    log(data.data.sub_elements.length)
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
        const chartData = [];
        const divID = sub_element.name;
        log("    data.data.sub_elements")
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
                showlegend: true,
                legend: {
                    x: 1,
                    xanchor: 'right',
                    y: 1
                },
            };
            const plotlyConfig = {
                scrollZoom: true,
                modeBarButtonsToRemove: ["select2d", "lasso2d", "toggleSpikelines"],
                responsive: true,
                showEditInChartStudio: true,
                displaylogo: false // no logo to avoid 'rel="noopener noreferrer"' security issue (see https://webhint.io/docs/user-guide/hints/hint-disown-opener/)
            };
            log("Plotly.newPlot")
            Plotly.newPlot(divID, chartData, layout, plotlyConfig).then(function (target){
                removeExplicitSize(target);
                resizeObserver.observe(target);
                if(divID !== "main-chart"){
                    // Plotly.relayout("sub-chart", {xaxis: mainLayout.xaxis});
                    Plotly.relayout("sub-chart", {xaxis: {range: mainLayout.xaxis.range, type: mainLayout.xaxis.type}});
                }
            })
            if(divID === "main-chart"){
                mainLayout = layout;
            }
            chartDivs.push($(`#${divID}`))

        });
    });
    document.getElementById("main-chart").on("plotly_relayout", function(eventdata) {
        Plotly.relayout("sub-chart", eventdata);
    });
    // chartDivs[1][0].on("plotly_relayout", function(eventdata) {
    //     Plotly.relayout("main-chart", eventdata);
    // });
}

function removeExplicitSize(figure){
  delete figure.layout.width;
  delete figure.layout.height;
  figure.layout.autosize = true;
  // Turn off responsive (ie. responsive to window resize)
  figure.config = { responsive: false };
  return figure;
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
    displayCharts();
}

function handleResizables(){
    $(".resizable").resizable();
    $(".resizable").on("resize", function () {
        current_charts_height = $("#charts").height()
        new_toolbox_height = "calc(100vh - 96px - " + current_charts_height + "px)";
        $("#toolbox").css("height", new_toolbox_height);


        current_main_chart_height = $("#main-chart").height()
        new_sub_chart_height = "calc(100% - 5px - " + current_main_chart_height + "px)"
        $("#sub-chart").css("height", new_sub_chart_height);
    });
}

$(document).ready(function() {
    displayCharts();
    handleScriptButtons();
    handleResizables();
});
