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
    send_and_interpret_bot_update({}, update_url, source, packagesOperationSuccessCallback, packagesOperationErrorCallback)
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
        }
        disablePackagesOperations();
        send_and_interpret_bot_update(data, update_url, element, packagesOperationSuccessCallback, packagesOperationErrorCallback)
    })
}

function reloadOwnedPackages(){
    $("#owned-tentacles").load(location.href + " #owned-tentacles", function(){
        reloadTable();
    });
}

function packagesOperationSuccessCallback(updated_data, update_url, dom_root_element, msg, status){
    disablePackagesOperations(false);
    reloadOwnedPackages();
    create_alert("success", "Packages operation success", msg);
}

function packagesOperationErrorCallback(updated_data, update_url, dom_root_element, result, status, error){
    disablePackagesOperations(false);
    reloadOwnedPackages();
    create_alert("error", "Error when managing packages: "+result.responseText, "");
}

$(document).ready(function() {
    reloadTable();
    $("#synchronize-tentacles").click(function(){
        syncPackages($(this));
    });
});
