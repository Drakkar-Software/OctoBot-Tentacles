function displayOptimizerSettings(schemaElements, replot){
    $.get({
        url: $("#optimizer-input-save-and-start-button").data("config-url"),
        dataType: "json",
        success: function (data) {
            _buildOptimizerSettingsForm(schemaElements, data)
        },
        error: function(result, status) {
            const errorMessage = `Impossible to optimizer data: ${result.responseText}. More details in logs.`;
            $("#main-chart").text(errorMessage)
            window.console && console.error(errorMessage);
        }
    });
}

function getOptimizerSettingsValues(){
    const settingsRoot = $("#optimizer-settings-root");
    const settings = {};
    settingsRoot.find(".optimizer-input-setting").each(function (i, jsInputSetting){
        const inputSetting = $(jsInputSetting);
        const rawSettingName = inputSetting.data("input-setting-base-name")
        const tentacleValue = inputSetting.data("tentacle-name")
        const clearedSettingName = rawSettingName.replaceAll(" ", "_");
        let settingValue = inputSetting.val();
        if(inputSetting.data("type") === "number"){
            const minInputSetting = inputSetting
            const maxInputSetting = $(document.getElementById(`${tentacleValue}-${rawSettingName}-Input-setting-number-max`));
            const stepInputSetting = $(document.getElementById(`${tentacleValue}-${rawSettingName}-Input-setting-number-step`));
            settingValue = {
                min: Number(minInputSetting.val()),
                max: Number(maxInputSetting.val()),
                step: Number(stepInputSetting.val()),
            }
        }else if(inputSetting.data("type") === "boolean"){
            settingValue = inputSetting.val().map((x) => (x.toLowerCase() === "true"));
        }
        const enabled = $(document.getElementById(`${tentacleValue}-${rawSettingName}-Input-enabled-value`)).prop("checked");
        settings[`${tentacleValue}-${clearedSettingName}`] = {
            value: settingValue,
            user_input: clearedSettingName,
            tentacle: tentacleValue,
            enabled: enabled
        };
    })
    return settings;
}

function _buildOptimizerSettingsForm(schemaElements, configValues){
    const settingsRoot = $("#optimizer-settings-root");
    settingsRoot.empty();
    schemaElements.data.elements.forEach(function (element){
        if(element.is_hidden){
            return;
        }
        let atLeastOneUserInput = false;
        const tentacleName = element.tentacle
        const inputGroupId = _appendInputGroupFromTemplate(settingsRoot, tentacleName);
        const inputGroupContent = $(`#${inputGroupId}`).find(".input-content");
        Object.values(element.schema.properties).forEach(function (inputDetail) {
            if (_buildOptimizerConfigElementSettingForm(inputGroupContent, inputDetail,
                configValues, tentacleName, inputDetail.title)) {
                atLeastOneUserInput = true;
            }
        });
        if(!atLeastOneUserInput){
            $(`#${inputGroupId}`).remove();
        }
    })
    _updateInputSettingsDisplay(settingsRoot);
}

function _buildUserInputConfigEntry(inputGroupContent, valueType, inputDetail, configValues, tentacleName){
    const newInputSetting = _getInputSettingFromTemplate(valueType, inputDetail, tentacleName)
    if(newInputSetting !== null){
        inputGroupContent.append(newInputSetting);
        _updateInputDetailValues(valueType, inputDetail, configValues, tentacleName);
    }
}

function _buildOptimizerConfigElementSettingForm(inputGroupContent, inputDetails, configValues,
                                                 parentInputIdentifier, inputIdentifier){
    if(inputDetails.options.in_optimizer) {
        const valueType = _getValueType(inputDetails);
        if (valueType === "nested_config") {
            _buildOptimizerNestedConfigSettingsForm(inputGroupContent, inputDetails, configValues,
                `${parentInputIdentifier}${_INPUT_SEPARATOR}${inputIdentifier}`);
        } else {
            _buildUserInputConfigEntry(inputGroupContent, valueType, inputDetails, configValues,
                parentInputIdentifier);
        }
        return true;
    }
    return false;
}

function _buildOptimizerNestedConfigSettingsForm(inputGroupContent, inputDetail, configValues, parentInputIdentifier){
    let atLeastOneUserInput = false;
    const nestedInputGroupId = _appendNestedInputGroupFromTemplate(inputGroupContent,parentInputIdentifier, inputDetail.title);
    const nestedInputGroupContent = $(`#${nestedInputGroupId}`).find(".input-content");
    Object.keys(inputDetail.properties).forEach(function (nestedInput) {
        const nestedInputDetails = inputDetail.properties[nestedInput];
        if(_buildOptimizerConfigElementSettingForm(nestedInputGroupContent, nestedInputDetails,
            configValues, parentInputIdentifier, nestedInput)){
            atLeastOneUserInput = true;
        }
    });
    if(!atLeastOneUserInput){
        $(`#${nestedInputGroupId}`).remove();
    }
}

function _appendInputGroup(parent, template, groupIdentifier, groupName){
    let inputGroup = template.html().replace(new RegExp("XYZT","g"), groupName);
    inputGroup = inputGroup.replace(new RegExp("XYZ","g"), groupIdentifier);
    parent.append(inputGroup);
}

function _appendInputGroupFromTemplate(settingsRoot, tentacleName){
    const template = $("#optimizer-settings-tentacle-group-template");
    _appendInputGroup(settingsRoot, template, tentacleName, tentacleName)
    return `optimizer-settings-${tentacleName}-tentacle-group-template`;
}

function _appendNestedInputGroupFromTemplate(settingsRoot, nestedConfigIdentifier, nestedConfigName){
    const template = $("#optimizer-settings-nested-tentacle-config-template");
    _appendInputGroup(settingsRoot, template, nestedConfigIdentifier, nestedConfigName)
    return `optimizer-settings-${nestedConfigIdentifier}-nested-tentacle-config-template`;
}

function _getInputSettingFromTemplate(valueType, inputDetail, tentacleName){
    const template = _getInputSettingTemplate(valueType);
    if(template.length){
        let inputSettings = template.html().replace(new RegExp("XYZT","g"), inputDetail.title);
        inputSettings = inputSettings.replace(new RegExp("XYZ","g"), inputDetail.title);
        inputSettings = inputSettings.replace(new RegExp("ZYXDefaultValue","g"), inputDetail.default);
        inputSettings = inputSettings.replace(new RegExp("TENTACLEABC","g"), tentacleName);
        return inputSettings;
    }
    else {
        log(`Unhandled value type: "${valueType}": no strategy optimizer template found.`)
        return null;
    }
}

function _getInputSettingTemplate(valueType){
    return $(`#optimizer-settings-${valueType}-template`);
}

function _getValueType(inputDetail){
    const schemaValueType = inputDetail.type;
    if(schemaValueType === "string"){
        return "options";
    }else if(schemaValueType === "array"){
        return "multiple-options";
    }else if(schemaValueType === "object"){
        return "nested_config"
    }
    return schemaValueType;
}

function _updateInputDetailValues(valueType, inputDetail, configValues, tentacleIdentifier){
    const rawValue = configValues[`${tentacleIdentifier}-${inputDetail.title.replaceAll(" ", "_")}`];
    let configValue = undefined;
    let isEnabled = false;
    if(typeof rawValue !== "undefined"){
        configValue = rawValue.value;
        isEnabled = rawValue.enabled;
    }
    if(valueType === "options" || valueType === "boolean"){
        let values = typeof configValue === "undefined" ? [] : configValue
        const valuesSelect = $(document.getElementById(`${tentacleIdentifier}-${inputDetail.title}-Input-setting-${valueType}`));
        if(valueType === "options"){
            inputDetail.enum.forEach(function (value){
                const isSelected = values.indexOf(value) !== -1;
                valuesSelect.append(new Option(value, value, false, isSelected));
            })
        }else if (valueType === "boolean"){
            values = values.map((x) => String(x))
            valuesSelect.find("option").each(function (i, jsOption){
                const option = $(jsOption);
                const isSelected = values.indexOf(option.attr("value")) !== -1;
                option.attr("selected", isSelected);
            })
        }
    }else if(valueType === "number"){
        let values = typeof configValue === "undefined" ? {min: 0, max: 0, step: 0} : configValue;
        ["min", "max", "step"].forEach(function (suffix){
            const element = $(document.getElementById(`${tentacleIdentifier}-${inputDetail.title}-Input-setting-number-${suffix}`));
            const value = values[suffix];
            element.val(value);
        })
    }
    $(document.getElementById(`${tentacleIdentifier}-${inputDetail.title}-Input-enabled-value`)).prop("checked", isEnabled);
}

function _updateInputSettingsDisplay(settingsRoot){
    settingsRoot.find("select[multiple=\"multiple\"]").select2({
        width: 'resolve', // need to override the changed default
        closeOnSelect: false,
        placeholder: "Select values to use"
    });
}

const _INPUT_SEPARATOR = "_-_"
