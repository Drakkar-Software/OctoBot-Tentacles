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

$(document).ready(function() {
    const displayFeedbackFormIfNecessary = () => {
        const feedbackFormData = $("#feedback-form-data");
        if(feedbackFormData.data("display-form") === "True") {
            displayFeedbackForm(
                feedbackFormData.data("form-to-display"),
                feedbackFormData.data("user-id"),
                feedbackFormData.data("on-submit-url"),
            );
        }
    };
    const onEditorChange = (newValue) => {
        updateTentacleConfig(newValue);
    };
    const startAutomations = () => {
        const successCallback = (updated_data, update_url, dom_root_element, msg, status) => {
            create_alert("success", "Automations started");
        }
        const update_url = $("button[data-role='startAutomations']").attr(update_url_attr);
        send_and_interpret_bot_update(null, update_url, null, successCallback);
    }
    if (!startTutorialIfNecessary("automations")){
        displayFeedbackFormIfNecessary();
    }
    addEditorChangeEventCallback(onEditorChange);
    $("button[data-role='startAutomations']").on("click", startAutomations);
});
