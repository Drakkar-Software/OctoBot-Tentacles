#  Drakkar-Software OctoBot-Interfaces
#  Copyright (c) Drakkar-Software, All rights reserved.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.

from octobot_commons.logging.logging_util import get_logger
from copy import copy
from os.path import isfile, sep
import ccxt
import requests

from octobot_evaluators.evaluator.strategy_evaluator import StrategyEvaluator
from octobot_interfaces.util.util import run_in_bot_main_loop
from octobot_tentacles_manager.api.configurator import get_tentacles_activation, \
    get_tentacle_config as manager_get_tentacle_config, update_tentacle_config as manager_update_tentacle_config, \
    get_tentacle_config_schema_path, factory_tentacle_reset_config, update_activation_configuration
from octobot_tentacles_manager.api.inspector import get_tentacle_documentation_path
from octobot_trading.api.modes import get_activated_trading_mode
from tentacles.Interfaces.web_interface.constants import UPDATED_CONFIG_SEPARATOR, EVALUATOR_ACTIVATION, \
    CURRENCIES_LIST_URL
from octobot_evaluators.constants import EVALUATOR_EVAL_DEFAULT_TYPE
from octobot_trading.constants import CONFIG_EXCHANGES, TESTED_EXCHANGES, SIMULATOR_TESTED_EXCHANGES
from octobot_commons.constants import CONFIG_METRICS, CONFIG_ENABLED_OPTION, CONFIG_ADVANCED_CLASSES
from octobot_interfaces.util.bot import get_global_config, get_edited_config, get_bot_api, \
    get_startup_tentacles_config, get_edited_tentacles_config
from octobot_services.api.services import get_available_services
import octobot_commons.config_manager as config_manager
from octobot_commons.tentacles_management.class_inspector import get_class_from_string, evaluator_parent_inspection, \
    trading_mode_parent_inspection
from octobot_evaluators.evaluator.abstract_evaluator import AbstractEvaluator
from octobot_backtesting.api.backtesting import is_backtesting_enabled
from octobot.community.community_manager import CommunityManager
from octobot_tentacles_manager.api.configurator import save_tentacles_setup_configuration
from octobot_tentacles_manager.api.inspector import get_tentacle_resources_path

NAME_KEY = "name"
DESCRIPTION_KEY = "description"
REQUIREMENTS_KEY = "requirements"
REQUIREMENTS_COUNT_KEY = "requirements-min-count"
DEFAULT_CONFIG_KEY = "default-config"
TRADING_MODES_KEY = "trading-modes"
STRATEGIES_KEY = "strategies"
ADVANCED_CLASS_KEY = "advanced_class"
TRADING_MODE_KEY = "trading mode"
STRATEGY_KEY = "strategy"
TA_EVALUATOR_KEY = "technical evaluator"
SOCIAL_EVALUATOR_KEY = "social evaluator"
RT_EVALUATOR_KEY = "real time evaluator"
REQUIRED_KEY = "required"
SOCIAL_KEY = "social"
TA_KEY = "ta"
RT_KEY = "real-time"
ACTIVATED_STRATEGIES = "activated_strategies"
BASE_CLASSES_KEY = "base_classes"
EVALUATION_FORMAT_KEY = "evaluation_format"

LOGGER = get_logger("WebConfigurationModel")

DEFAULT_EXCHANGE = "binance"


def _get_tentacles_activation():
    return get_tentacles_activation(get_edited_tentacles_config())


def get_tentacles_startup_activation():
    return get_tentacles_activation(get_startup_tentacles_config())


def reset_trading_history():
    previous_state_manager = get_bot_api().get_previous_states_manager()
    if previous_state_manager:
        previous_state_manager.reset_trading_history()


def is_trading_persistence_activated():
    return get_bot_api().get_previous_states_manager() is not None


def get_tentacle_documentation(klass, media_url):
    doc_file = get_tentacle_documentation_path(klass)
    if isfile(doc_file):
        resource_url = f"{media_url}/{get_tentacle_resources_path(klass).replace(sep, '/')}/"
        with open(doc_file) as doc_file:
            doc_content = doc_file.read()
            # patch resources paths into the tentacle resource path
            return doc_content.replace("resources/", resource_url)
    return ""


def _get_advanced_class_details(class_name, klass, media_url, is_trading_mode=False, is_strategy=False):
    from octobot_commons.tentacles_management.advanced_manager import get_class
    details = {}
    config = get_global_config()
    advanced_class = get_class(config, klass)
    if advanced_class and advanced_class.get_name() != class_name:
        details[NAME_KEY] = advanced_class.get_name()
        details[DESCRIPTION_KEY] = get_tentacle_documentation(advanced_class, media_url)
        details[BASE_CLASSES_KEY] = [k.get_name() for k in advanced_class.__bases__]
        if is_trading_mode:
            required_strategies, required_strategies_count = klass.get_required_strategies_names_and_count()
            details[REQUIREMENTS_KEY] = [strategy for strategy in required_strategies]
            details[REQUIREMENTS_COUNT_KEY] = required_strategies_count
        elif is_strategy:
            details[REQUIREMENTS_KEY] = [evaluator for evaluator in advanced_class.get_required_evaluators()]
            details[DEFAULT_CONFIG_KEY] = [evaluator for evaluator in advanced_class.get_default_evaluators(config)]
    return details


def _get_strategy_activation_state(with_trading_modes, media_url):
    from octobot_trading.modes.abstract_trading_mode import AbstractTradingMode
    import tentacles.Trading.Mode as modes
    import tentacles.Evaluator.Strategies as strategies
    strategy_config = {
        TRADING_MODES_KEY: {},
        STRATEGIES_KEY: {}
    }
    strategy_config_classes = {
        TRADING_MODES_KEY: {},
        STRATEGIES_KEY: {}
    }

    if with_trading_modes:
        trading_config = _get_tentacles_activation()
        for key, val in trading_config.items():
            config_class = get_class_from_string(key, AbstractTradingMode, modes, trading_mode_parent_inspection)
            if config_class:
                strategy_config[TRADING_MODES_KEY][key] = {}
                strategy_config[TRADING_MODES_KEY][key][EVALUATOR_ACTIVATION] = val
                strategy_config[TRADING_MODES_KEY][key][DESCRIPTION_KEY] = get_tentacle_documentation(config_class,
                                                                                                      media_url)
                strategy_config[TRADING_MODES_KEY][key][ADVANCED_CLASS_KEY] = \
                    _get_advanced_class_details(key, config_class, media_url, is_trading_mode=True)
                strategy_config_classes[TRADING_MODES_KEY][key] = config_class

    evaluator_config = _get_tentacles_activation()
    for key, val in evaluator_config.items():
        config_class = get_class_from_string(key, StrategyEvaluator,
                                             strategies, evaluator_parent_inspection)
        if config_class:
            strategy_config[STRATEGIES_KEY][key] = {}
            strategy_config[STRATEGIES_KEY][key][EVALUATOR_ACTIVATION] = val
            strategy_config[STRATEGIES_KEY][key][DESCRIPTION_KEY] = get_tentacle_documentation(config_class, media_url)
            strategy_config[STRATEGIES_KEY][key][ADVANCED_CLASS_KEY] = \
                _get_advanced_class_details(key, config_class, media_url, is_strategy=True)
            strategy_config_classes[STRATEGIES_KEY][key] = config_class

    return strategy_config, strategy_config_classes


def _get_tentacle_packages():
    import tentacles.Trading.Mode as modes
    from octobot_trading.modes.abstract_trading_mode import AbstractTradingMode
    yield modes, AbstractTradingMode, TRADING_MODE_KEY
    import tentacles.Evaluator.Strategies as strategies
    yield strategies, StrategyEvaluator, STRATEGY_KEY
    import tentacles.Evaluator.TA as ta
    yield ta, AbstractEvaluator, TA_EVALUATOR_KEY
    import tentacles.Evaluator.Social as social
    yield social, AbstractEvaluator, SOCIAL_EVALUATOR_KEY
    import tentacles.Evaluator.RealTime as rt
    yield rt, AbstractEvaluator, RT_EVALUATOR_KEY


def _get_activation_state(name, details):
    activation_states = _get_tentacles_activation()
    if ADVANCED_CLASS_KEY in details:
        for parent_class in details[ADVANCED_CLASS_KEY][BASE_CLASSES_KEY]:
            if parent_class in activation_states and activation_states[parent_class]:
                return True
    return name in activation_states and activation_states[name]


def get_tentacle_from_string(name, media_url, with_info=True):
    for package, abstract_class, tentacle_type in _get_tentacle_packages():
        is_trading_mode = tentacle_type == TRADING_MODE_KEY
        parent_inspector = trading_mode_parent_inspection if is_trading_mode else evaluator_parent_inspection
        klass = get_class_from_string(name, abstract_class, package, parent_inspector)
        if klass:
            if with_info:
                info = {}
                info[DESCRIPTION_KEY] = get_tentacle_documentation(klass, media_url)
                info[NAME_KEY] = name
                for parent_class in klass.__bases__:
                    if hasattr(parent_class, "get_name"):
                        advanced_details = _get_advanced_class_details(parent_class.get_name(), parent_class, media_url,
                                                                       is_strategy=(tentacle_type == STRATEGY_KEY))
                        if advanced_details:
                            info[ADVANCED_CLASS_KEY] = advanced_details
                info[EVALUATOR_ACTIVATION] = _get_activation_state(name, info)
                if is_trading_mode:
                    _add_trading_mode_requirements_and_default_config(info, klass)
                elif tentacle_type == STRATEGY_KEY:
                    _add_strategy_requirements_and_default_config(info, klass)
                return klass, tentacle_type, info
            else:
                return klass, tentacle_type, None
    return None, None, None


def get_tentacle_config(klass):
    return manager_get_tentacle_config(klass)


def get_tentacle_config_schema(klass):
    try:
        with open(get_tentacle_config_schema_path(klass)) as schema_file:
            return schema_file.read()
    except Exception:
        return ""


def update_tentacle_config(tentacle_name, config_update):
    try:
        klass, _, _ = get_tentacle_from_string(tentacle_name, None, with_info=False)
        manager_update_tentacle_config(klass, config_update)
        return True, f"{tentacle_name} updated"
    except Exception as e:
        LOGGER.exception(e)
        return False, f"Error when updating tentacle config: {e}"


def reset_config_to_default(tentacle_name):
    try:
        klass, _, _ = get_tentacle_from_string(tentacle_name, None, with_info=False)
        factory_tentacle_reset_config(klass)
        return True, f"{tentacle_name} configuration reset to default values"
    except Exception as e:
        LOGGER.exception(e)
        return False, f"Error when resetting factory tentacle config: {e}"


def _get_required_element(elements_config):
    advanced_class_key = ADVANCED_CLASS_KEY
    requirements = REQUIREMENTS_KEY
    required_elements = set()
    for element_type in elements_config.values():
        for element_name, element in element_type.items():
            if element[EVALUATOR_ACTIVATION]:
                if element[advanced_class_key] and requirements in element[advanced_class_key]:
                    required_elements = required_elements.union(element[advanced_class_key][requirements])
                elif requirements in element:
                    required_elements = required_elements.union(element[requirements])
    return required_elements


def _add_strategy_requirements_and_default_config(desc, klass):
    desc[REQUIREMENTS_KEY] = [evaluator for evaluator in klass.get_required_evaluators()]
    desc[DEFAULT_CONFIG_KEY] = [evaluator for evaluator in klass.get_default_evaluators()]


def _add_trading_mode_requirements_and_default_config(desc, klass):
    required_strategies, required_strategies_count = klass.get_required_strategies_names_and_count()
    if required_strategies:
        desc[REQUIREMENTS_KEY] = \
            [strategy for strategy in required_strategies]
        desc[DEFAULT_CONFIG_KEY] = \
            [strategy for strategy in klass.get_default_strategies()]
        desc[REQUIREMENTS_COUNT_KEY] = required_strategies_count
    else:
        desc[REQUIREMENTS_KEY] = []
        desc[REQUIREMENTS_COUNT_KEY] = 0


def _add_strategies_requirements(strategies, strategy_config):
    required_elements = _get_required_element(strategy_config)
    for classKey, klass in strategies.items():
        if not strategy_config[STRATEGIES_KEY][classKey][ADVANCED_CLASS_KEY]:
            # no need for requirement if advanced class: requirements are already in advanced class
            _add_strategy_requirements_and_default_config(strategy_config[STRATEGIES_KEY][classKey], klass)
        strategy_config[STRATEGIES_KEY][classKey][REQUIRED_KEY] = classKey in required_elements


def _add_trading_modes_requirements(trading_modes, strategy_config):
    for classKey, klass in trading_modes.items():
        try:
            _add_trading_mode_requirements_and_default_config(strategy_config[TRADING_MODES_KEY][classKey], klass)
        except Exception as e:
            LOGGER.exception(e)


def get_strategy_config(media_url, with_trading_modes=True):
    strategy_config, strategy_config_classes = _get_strategy_activation_state(with_trading_modes, media_url)
    if with_trading_modes:
        _add_trading_modes_requirements(strategy_config_classes[TRADING_MODES_KEY], strategy_config)
    _add_strategies_requirements(strategy_config_classes[STRATEGIES_KEY], strategy_config)
    return strategy_config


def get_in_backtesting_mode():
    return is_backtesting_enabled(get_global_config())


def accepted_terms():
    return config_manager.accepted_terms(get_edited_config())


def accept_terms(accepted):
    return config_manager.accept_terms(get_edited_config(), accepted)


def _fill_evaluator_config(evaluator_name, activated, eval_type_key,
                           evaluator_type, detailed_config, media_url, is_strategy=False):
    klass = get_class_from_string(evaluator_name, AbstractEvaluator, evaluator_type, evaluator_parent_inspection)
    if klass:
        detailed_config[eval_type_key][evaluator_name] = {}
        detailed_config[eval_type_key][evaluator_name][EVALUATOR_ACTIVATION] = activated
        detailed_config[eval_type_key][evaluator_name][DESCRIPTION_KEY] = get_tentacle_documentation(klass, media_url)
        detailed_config[eval_type_key][evaluator_name][EVALUATION_FORMAT_KEY] = "float" \
            if klass.get_eval_type() == EVALUATOR_EVAL_DEFAULT_TYPE else str(klass.get_eval_type())
        detailed_config[eval_type_key][evaluator_name][ADVANCED_CLASS_KEY] = \
            _get_advanced_class_details(evaluator_name, klass, media_url, is_strategy=is_strategy)
        return True, klass
    return False, klass


def get_evaluator_detailed_config(media_url):
    import tentacles.Evaluator.Strategies as strategies
    import tentacles.Evaluator.TA as ta
    import tentacles.Evaluator.Social as social
    import tentacles.Evaluator.RealTime as rt
    detailed_config = {
        SOCIAL_KEY: {},
        TA_KEY: {},
        RT_KEY: {}
    }
    strategy_config = {
        STRATEGIES_KEY: {}
    }
    strategy_class_by_name = {}
    evaluator_config = _get_tentacles_activation()
    for evaluator_name, activated in evaluator_config.items():
        is_TA, klass = _fill_evaluator_config(evaluator_name, activated, TA_KEY, ta, detailed_config, media_url)
        if not is_TA:
            is_social, klass = _fill_evaluator_config(evaluator_name, activated, SOCIAL_KEY,
                                                      social, detailed_config, media_url)
            if not is_social:
                is_real_time, klass = _fill_evaluator_config(evaluator_name, activated, RT_KEY,
                                                             rt, detailed_config, media_url)
                if not is_real_time:
                    is_strategy, klass = _fill_evaluator_config(evaluator_name, activated, STRATEGIES_KEY,
                                                                strategies, strategy_config, media_url,
                                                                is_strategy=True)
                    if is_strategy:
                        strategy_class_by_name[evaluator_name] = klass

    _add_strategies_requirements(strategy_class_by_name, strategy_config)
    required_elements = _get_required_element(strategy_config)
    for eval_type in detailed_config.values():
        for eval_name, eval_details in eval_type.items():
            eval_details[REQUIRED_KEY] = eval_name in required_elements

    detailed_config[ACTIVATED_STRATEGIES] = [s for s, details in strategy_config[STRATEGIES_KEY].items()
                                             if details[EVALUATOR_ACTIVATION]]
    return detailed_config


def get_config_activated_trading_mode(edited_config=False):
    config = get_global_config()
    if edited_config:
        config = copy(get_edited_config())
        # rebind advanced classes to use in get_activated_trading_mode
        config[CONFIG_ADVANCED_CLASSES] = get_global_config()[CONFIG_ADVANCED_CLASSES]
    return get_activated_trading_mode(config, get_bot_api().get_edited_tentacles_config())


def update_tentacles_activation_config(new_config, deactivate_others=False):
    tentacles_setup_configuration = get_edited_tentacles_config()
    try:
        updated_config = {
            element_name: activated if isinstance(activated, bool) else activated.lower() == "true"
            for element_name, activated in new_config.items()
        }
        if update_activation_configuration(get_edited_tentacles_config(), updated_config, deactivate_others):
            run_in_bot_main_loop(save_tentacles_setup_configuration(tentacles_setup_configuration))
        return True
    except Exception as e:
        LOGGER.exception(e, True, f"Error when updating tentacles activation {e}")
        return False


def update_global_config(new_config, delete=False):
    current_edited_config = get_edited_config()
    config_manager.update_global_config(new_config,
                                        current_edited_config,
                                        is_backtesting_enabled(current_edited_config),
                                        UPDATED_CONFIG_SEPARATOR,
                                        update_input=True,
                                        delete=delete)
    return True


def manage_metrics(enable_metrics):
    current_edited_config = get_edited_config()
    if CONFIG_METRICS not in current_edited_config:
        current_edited_config[CONFIG_METRICS] = {CONFIG_ENABLED_OPTION: enable_metrics}
    else:
        current_edited_config[CONFIG_METRICS][CONFIG_ENABLED_OPTION] = enable_metrics
    if enable_metrics and CommunityManager.should_register_bot(current_edited_config):
        CommunityManager.background_get_id_and_register_bot(get_bot_api())
    config_manager.simple_save_config_update(current_edited_config)


def get_metrics_enabled():
    return config_manager.get_metrics_enabled(get_edited_config())


def get_services_list():
    services = {}
    services_names = []
    for service in get_available_services():
        srv = service.instance()
        if srv.get_required_config():
            # do not add services without a config, ex: GoogleService (nothing to show on the web interface)
            services[srv.get_type()] = srv
            services_names.append(srv.get_type())
    return services, services_names


def get_symbol_list(exchanges):
    result = []

    for exchange in exchanges:
        try:
            inst = getattr(ccxt, exchange)({'verbose': False})
            inst.load_markets()
            result += inst.symbols
        except Exception as e:
            LOGGER.error(f"error when loading symbol list for {exchange}: {e}")

    # filter symbols with a "." or no "/" because bot can't handle them for now
    symbols = [res for res in result if "/" in res]

    return list(set(symbols))


def get_all_symbol_list():
    try:
        currencies_list = requests.get(CURRENCIES_LIST_URL).json()
        return {
            currency_data[NAME_KEY]: currency_data["symbol"]
            for currency_data in currencies_list["data"]
        }
    except Exception as e:
        LOGGER.error(f"Failed to get currencies list from coinmarketcap : {e}")
        return {}


def get_full_exchange_list(remove_config_exchanges=False):
    g_config = get_global_config()
    if remove_config_exchanges:
        user_exchanges = [e for e in g_config[CONFIG_EXCHANGES]]
        full_exchange_list = list(set(ccxt.exchanges) - set(user_exchanges))
    else:
        full_exchange_list = list(set(ccxt.exchanges))
    # can't handle exchanges containing UPDATED_CONFIG_SEPARATOR character in their name
    return [exchange for exchange in full_exchange_list if UPDATED_CONFIG_SEPARATOR not in exchange]


def get_tested_exchange_list():
    full_exchange_list = list(set(ccxt.exchanges))
    return [exchange for exchange in TESTED_EXCHANGES if exchange in full_exchange_list]


def get_simulated_exchange_list():
    full_exchange_list = list(set(ccxt.exchanges))
    return [exchange for exchange in SIMULATOR_TESTED_EXCHANGES if exchange in full_exchange_list]


def get_other_exchange_list(remove_config_exchanges=False):
    full_list = get_full_exchange_list(remove_config_exchanges)
    return [exchange for exchange in full_list
            if exchange not in TESTED_EXCHANGES and exchange not in SIMULATOR_TESTED_EXCHANGES]


def get_current_exchange():
    g_config = get_global_config()
    exchanges = g_config[CONFIG_EXCHANGES]
    if exchanges:
        return next(iter(exchanges))
    else:
        return DEFAULT_EXCHANGE
