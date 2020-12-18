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
        const updateURL = saveCurrentProfile.attr("data-url");
        const data = {
            id: $("#current-profile").attr("data-id"),
            name: currentProfileName.editable("getValue", true),
            description: currentProfileDescription.editable("getValue", true)
        }
        log(data)
        send_and_interpret_bot_update(data, updateURL, null,
            saveCurrentProfileSuccessCallback, saveCurrentProfileFailureCallback)
    });
}

function saveCurrentProfileSuccessCallback(updated_data, update_url, dom_root_element, msg, status){
    create_alert("success", "Profile updated");
}


function saveCurrentProfileFailureCallback(updated_data, update_url, dom_root_element, msg, status) {
    $('#current-profile-description').attr("disabled", false);
    create_alert("error", msg.responseText, "");
}

$(document).ready(function() {
    handleProfileEditor();
    handleProfileSelector();
});
