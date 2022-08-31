/*
 * Drakkar-Software OctoBot
 * Copyright (c) Drakkar-Software, All rights reserved.
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 3.0 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library.
 */

function disablePackagesOperations(should_lock=true){
    const disabled_attr = 'disabled';
    $("#synchronize-tentacles").prop(disabled_attr, should_lock);
    $(".install-package-button").prop(disabled_attr, should_lock);
}

function syncPackages(source){
    const update_url = source.attr(update_url_attr);
    disablePackagesOperations();
    send_and_interpret_bot_update({}, update_url, source, packagesOperationSuccessCallback, packagesOperationErrorCallback);
}

function reloadTable(){
    $('.table').each(function () {
        $(this).DataTable();
    });
    registerPackagesEvents();
}

function registerPackagesEvents(){
    $(".install-package-button").click(function (){
        const element = $(this);
        const update_url = element.attr(update_url_attr);
        const data = {
            "url": element.data("package-url"),
            "version": element.data("package-latest-compatible-version")
        };
        disablePackagesOperations();
        send_and_interpret_bot_update(data, update_url, element, packagesOperationSuccessCallback, packagesOperationErrorCallback);
    });
}

function reloadOwnedPackages(){
    $("#owned-tentacles").load(location.href + " #owned-tentacles", function(){
        reloadTable();
    });
}

function packagesOperationSuccessCallback(updated_data, update_url, dom_root_element, msg, status){
    disablePackagesOperations(false);
    reloadOwnedPackages();
    create_alert("success", "Packages operation succeed", msg);
}

function packagesOperationErrorCallback(updated_data, update_url, dom_root_element, result, status, error){
    disablePackagesOperations(false);
    reloadOwnedPackages();
    create_alert("error", "Error when managing packages: "+result.responseText, "");
}

function displayDeviceSelectorWhenNoSelectedDevice(){
    if($("#device-selector").find("button[data-role='selected-device']").length === 0) {
        // no selected device, force selection
        $('#device-select-modal').modal({backdrop: 'static', keyboard: false})
    }
}

function initDevicesCallbacks(){
    $("#device-selector").find("button[data-role='select-device']").click((element) => {
        const data = $(element.target).data("device-id");
        const update_url = $("#device-selector").data("update-url");
        send_and_interpret_bot_update(data, update_url, null,
            deviceOperationSuccessCallback, deviceOperationErrorCallback);

    })
    $("#create-new-device").click((element) => {
        const createButton = $(element.target);
        const update_url = createButton.data("update-url");
        createButton.attr("disabled", true);
        createButton.text("Creating ...")
        send_and_interpret_bot_update({}, update_url, null,
            deviceOperationSuccessCallback, deviceOperationErrorCallback);
    })
}

function deviceOperationSuccessCallback(updated_data, update_url, dom_root_element, result, status, error){
    // reload the page to retest devices
    window.location.reload();
}

function deviceOperationErrorCallback(updated_data, update_url, dom_root_element, result, status, error){
    create_alert("error", "Error when managing devices: "+result.responseText, "");
}

function initLoginSubmit(){
    $("form[name=community-login]").on("submit", () => {
        $("input[value=Login]").attr("disabled", true);
    });
}

$(document).ready(function() {
    reloadTable();
    $("#synchronize-tentacles").click(function(){
        syncPackages($(this));
    });
    displayDeviceSelectorWhenNoSelectedDevice();
    initDevicesCallbacks();
    initLoginSubmit();
});
