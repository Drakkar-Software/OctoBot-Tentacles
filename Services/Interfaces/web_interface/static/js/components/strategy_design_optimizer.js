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
        const clearedSettingName = rawSettingName.replaceAll(" ", "_");
        let settingValue = inputSetting.val();
        if(inputSetting.data("type") === "number"){
            const minInputSetting = inputSetting
            const maxInputSetting = $(document.getElementById(`${rawSettingName}Input-setting-number-max`));
            const stepInputSetting = $(document.getElementById(`${rawSettingName}Input-setting-number-step`));
            settingValue = {
                min: Number(minInputSetting.val()),
                max: Number(maxInputSetting.val()),
                step: Number(stepInputSetting.val()),
            }
        }else if(inputSetting.data("type") === "boolean"){
            settingValue = inputSetting.val().map((x) => (x.toLowerCase() === "true"));
        }
        const enabled = $(document.getElementById(`${rawSettingName}Input-enabled-value`)).prop("checked");
        settings[clearedSettingName] = {
            value: settingValue,
            enabled: enabled
        };
    })
    return settings;
}

function _buildOptimizerSettingsForm(schemaElements, configValues){
    const settingsRoot = $("#optimizer-settings-root");
    settingsRoot.empty();
    Object.values(schemaElements.data.elements[0].schema.properties).forEach(function (inputDetail) {
        const valueType = _getValueType(inputDetail);
        const newInputSetting = _getInputSettingFromTemplate(valueType, inputDetail)
        settingsRoot.append(newInputSetting).hide().fadeIn();
        _updateInputDetailValues(valueType, inputDetail, configValues);
    });
    _updateInputSettingsDisplay(settingsRoot);
}

function _getInputSettingFromTemplate(valueType, inputDetail){
    const template = _getInputSettingTemplate(valueType);
    let inputSettings = template.html().replace(new RegExp("XYZ","g"), inputDetail.title);
    inputSettings = inputSettings.replace(new RegExp("ZYXDefaultValue","g"), inputDetail.default);
    return inputSettings
}

function _getInputSettingTemplate(valueType){
    return $(`#optimizer-settings-${valueType}-template`);
}

function _getValueType(inputDetail){
    const schemaValueType = inputDetail.type;
    if(schemaValueType === "string"){
        return "options";
    }
    return schemaValueType;
}

function _updateInputDetailValues(valueType, inputDetail, configValues){
    const rawValue = configValues[inputDetail.title.replaceAll(" ", "_")];
    let configValue = undefined;
    let isEnabled = false;
    if(typeof rawValue !== "undefined"){
        configValue = configValues[inputDetail.title.replaceAll(" ", "_")].value;
        isEnabled = rawValue.enabled;
    }
    if(valueType === "options" || valueType === "boolean"){
        let values = typeof configValue === "undefined" ? [] : configValue
        const valuesSelect = $(document.getElementById(`${inputDetail.title}Input-setting-${valueType}`));
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
            const element = $(document.getElementById(`${inputDetail.title}Input-setting-number-${suffix}`));
            const value = values[suffix];
            element.val(value);
        })
    }
    $(document.getElementById(`${inputDetail.title}Input-enabled-value`)).prop("checked", isEnabled);
}

function _updateInputSettingsDisplay(settingsRoot){
    settingsRoot.find("select[multiple=\"multiple\"]").select2({
        width: 'resolve', // need to override the changed default
        closeOnSelect: false,
        placeholder: "Select values to use"
    });
}
