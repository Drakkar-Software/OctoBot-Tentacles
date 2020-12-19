function onProfileSelection(profileSelector, selectedDesc, selectedName, saveProfile, currentProfileId){
    const selectedId = profileSelector.val();
    const selectedOption = $(`option[value=${selectedId}]`);
    if(selectedDesc.length){
        selectedDesc.html(selectedOption.attr("data-desc"));
    }
    if(selectedName.length){
        selectedName.html(selectedOption.attr("data-name"));
    }
    if(saveProfile.length){
        saveProfile.attr("disabled", selectedId === currentProfileId);
    }
}

function handleProfileSelector(){
    const profileSelector = $("#profile-select");
    const selectedDesc = $("#selected-profile-description");
    const selectedName = $("#selected-profile-name");
    const saveProfile = $("#save-profile");
    if (profileSelector.length){
        const currentProfileId = $("#current-profile").attr("data-id");
        onProfileSelection(profileSelector, selectedDesc, selectedName, saveProfile, currentProfileId);
        profileSelector.on('change', function() {
            onProfileSelection(profileSelector, selectedDesc, selectedName, saveProfile, currentProfileId);
        });
        if (saveProfile.length){
            saveProfile.click(function (){
                profileSelector.attr("disabled", true);
                saveProfile.attr("disabled", true);
                const changeProfileURL = saveProfile.attr("data-url");
                window.location.replace(`${changeProfileURL}${profileSelector.val()}`);
            })
        }
    }
}

function handleProfileEditor(){
    const saveCurrentProfile = $("#save-current-profile");
    const currentProfileName = $('#current-profile-name');
    const currentProfileDescription = $('#current-profile-description');
    currentProfileName.on('save', function (){
        saveCurrentProfile.attr("disabled", false);
    });
    currentProfileDescription.on('save', function (){
        saveCurrentProfile.attr("disabled", false);
    });
    saveCurrentProfile.click(function (){
        saveCurrentProfile.attr("disabled", true);
        saveCurrentProfile.tooltip("hide");
        const updateURL = saveCurrentProfile.attr("data-url");
        const data = {
            id: $("#current-profile").attr("data-id"),
            name: currentProfileName.editable("getValue", true),
            description: currentProfileDescription.editable("getValue", true)
        }
        send_and_interpret_bot_update(data, updateURL, null,
            saveCurrentProfileSuccessCallback, saveCurrentProfileFailureCallback)
    });
}

function saveCurrentProfileSuccessCallback(updated_data, update_url, dom_root_element, msg, status){
    create_alert("success", "Profile updated");
    $("[data-role=profile-name]").each(function (){
        $(this).html(updated_data["name"]);
    })
}


function saveCurrentProfileFailureCallback(updated_data, update_url, dom_root_element, msg, status) {
    $("#save-current-profile").attr("disabled", false);
    create_alert("error", msg.responseText, "");
}

function handleProfileCreator(){
    const createButton = $("#create-new-profile");
    if(createButton.length){
        createButton.click(function (){
            send_and_interpret_bot_update({}, createButton.attr("data-url"), null,
                createProfileSuccessCallback, createProfileFailureCallback);
        });
    }
}

function createProfileSuccessCallback(updated_data, update_url, dom_root_element, msg, status){
    location.reload();
}


function createProfileFailureCallback(updated_data, update_url, dom_root_element, msg, status) {
    create_alert("error", msg.responseText, "");
}

function handleProfileImporter(){
    const importButton = $("#import-profile-button");
    const profileInput = $("#profile-input");
    const importForm = $("#import-form");
    if(importButton.length && profileInput.length && importForm.length){
        importButton.click(function (){
            profileInput.click();
        })
        profileInput.on("change", function (){
            importForm.submit();
        })
    }
}

function handleProfileExporter(){
    const exportButton = $("#export-profile");
    if(exportButton.length){
        exportButton.click(function (){
            window.window.location  = exportButton.attr("data-url");
        })
    }
}

$(document).ready(function() {
    handleProfileEditor();
    handleProfileCreator();
    handleProfileSelector();
    handleProfileImporter();
    handleProfileExporter();
});
