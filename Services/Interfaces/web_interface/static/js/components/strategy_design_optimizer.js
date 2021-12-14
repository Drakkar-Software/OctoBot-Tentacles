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
        const tentacleName = element.tentacle
        const inputGroupId = _appendInputGroupFromTemplate(settingsRoot, tentacleName);
        const inputGroupContent = $(`#${inputGroupId}`).find(".input-content");
        Object.values(element.schema.properties).forEach(function (inputDetail) {
            const valueType = _getValueType(inputDetail);
            const newInputSetting = _getInputSettingFromTemplate(valueType, inputDetail, tentacleName)
            inputGroupContent.append(newInputSetting);
            _updateInputDetailValues(valueType, inputDetail, configValues, tentacleName);
        });
    })
    _updateInputSettingsDisplay(settingsRoot);
}

function _appendInputGroupFromTemplate(settingsRoot, tentacleName){
    const template = $("#optimizer-settings-tentacle-group-template");
    let inputGroup = template.html().replace(new RegExp("XYZ","g"), tentacleName);
    settingsRoot.append(inputGroup);
    return `optimizer-settings-${tentacleName}-tentacle-group-template`;
}

function _getInputSettingFromTemplate(valueType, inputDetail, tentacleName){
    const template = _getInputSettingTemplate(valueType);
    let inputSettings = template.html().replace(new RegExp("XYZ","g"), inputDetail.title);
    inputSettings = inputSettings.replace(new RegExp("ZYXDefaultValue","g"), inputDetail.default);
    inputSettings = inputSettings.replace(new RegExp("TENTACLEABC","g"), tentacleName);
    return inputSettings
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
    }
    return schemaValueType;
}

function _updateInputDetailValues(valueType, inputDetail, configValues, tentacleName){
    const rawValue = configValues[`${tentacleName}-${inputDetail.title.replaceAll(" ", "_")}`];
    let configValue = undefined;
    let isEnabled = false;
    if(typeof rawValue !== "undefined"){
        configValue = rawValue.value;
        isEnabled = rawValue.enabled;
    }
    if(valueType === "options" || valueType === "boolean"){
        let values = typeof configValue === "undefined" ? [] : configValue
        const valuesSelect = $(document.getElementById(`${tentacleName}-${inputDetail.title}-Input-setting-${valueType}`));
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
            const element = $(document.getElementById(`${tentacleName}-${inputDetail.title}-Input-setting-number-${suffix}`));
            const value = values[suffix];
            element.val(value);
        })
    }
    $(document.getElementById(`${tentacleName}-${inputDetail.title}-Input-enabled-value`)).prop("checked", isEnabled);
}

function _updateInputSettingsDisplay(settingsRoot){
    settingsRoot.find("select[multiple=\"multiple\"]").select2({
        width: 'resolve', // need to override the changed default
        closeOnSelect: false,
        placeholder: "Select values to use"
    });
}
