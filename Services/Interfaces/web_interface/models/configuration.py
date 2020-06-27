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
from os.path import isfile, sep
import ccxt
import requests

from octobot_evaluators.evaluator.strategy_evaluator import StrategyEvaluator
from octobot_services.api.notification import create_notifier_factory
from octobot_services.constants import CONFIG_CATEGORY_SERVICES, CONFIG_WEB, CONFIG_WEB_PASSWORD
from octobot_tentacles_manager.api.configurator import get_tentacles_activation, \
    get_tentacle_config as manager_get_tentacle_config, update_tentacle_config as manager_update_tentacle_config, \
    get_tentacle_config_schema_path, factory_tentacle_reset_config, update_activation_configuration, \
    save_tentacles_setup_configuration
from octobot_tentacles_manager.api.inspector import get_tentacle_documentation_path, get_tentacle_resources_path, \
    get_tentacle_group
from octobot_tentacles_manager.constants import TENTACLES_TRADING_PATH, TENTACLES_EVALUATOR_PATH, \
    TENTACLES_SERVICES_PATH, TENTACLES_BACKTESTING_PATH
from octobot_trading.api.modes import get_activated_trading_mode
from tentacles.Services.Interfaces.web_interface.constants import UPDATED_CONFIG_SEPARATOR, ACTIVATION_KEY, \
    CURRENCIES_LIST_URL, TENTACLE_CLASS_NAME, STARTUP_CONFIG_KEY
from octobot_evaluators.constants import EVALUATOR_EVAL_DEFAULT_TYPE
from octobot_trading.constants import CONFIG_EXCHANGES, TESTED_EXCHANGES, SIMULATOR_TESTED_EXCHANGES
from octobot_commons.constants import CONFIG_METRICS, CONFIG_ENABLED_OPTION
from octobot_commons.logging.logging_util import get_logger
from octobot_services.interfaces.util.bot import get_global_config, get_edited_config, get_bot_api, \
    get_startup_tentacles_config, get_edited_tentacles_config
from octobot_services.api.services import get_available_services
import octobot_commons.config_manager as config_manager
from octobot_commons.tentacles_management.class_inspector import get_class_from_string, evaluator_parent_inspection, \
    trading_mode_parent_inspection
from octobot_evaluators.evaluator.abstract_evaluator import AbstractEvaluator
from octobot_backtesting.api.backtesting import is_backtesting_enabled
from octobot.community.community_manager import CommunityManager
from octobot.constants import CONFIG_FILE_SCHEMA

NAME_KEY = "name"
DESCRIPTION_KEY = "description"
REQUIREMENTS_KEY = "requirements"
COMPATIBLE_TYPES_KEY = "compatible-types"
REQUIREMENTS_COUNT_KEY = "requirements-min-count"
DEFAULT_CONFIG_KEY = "default-config"
TRADING_MODES_KEY = "trading-modes"
STRATEGIES_KEY = "strategies"
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

# tentacles from which configuration is not handled in strategies / evaluators configuration
NON_TRADING_STRATEGY_RELATED_TENTACLES = [TENTACLES_BACKTESTING_PATH, TENTACLES_SERVICES_PATH, TENTACLES_TRADING_PATH]

LOGGER = get_logger("WebConfigurationModel")

DEFAULT_EXCHANGE = "binance"

# buffers to faster config page loading
markets_by_exchanges = {}
all_symbols_dict = {}
# can't fetch symbols from coinmarketcap.com (which is in ccxt but is not an exchange and has a paid api)
exchange_symbol_fetch_blacklist = {"coinmarketcap"}


def _get_evaluators_tentacles_activation():
    return get_tentacles_activation(get_edited_tentacles_config())[TENTACLES_EVALUATOR_PATH]


def _get_trading_tentacles_activation():
    return get_tentacles_activation(get_edited_tentacles_config())[TENTACLES_TRADING_PATH]


def get_evaluators_tentacles_startup_activation():
    return get_tentacles_activation(get_startup_tentacles_config())[TENTACLES_EVALUATOR_PATH]


def get_trading_tentacles_startup_activation():
    return get_tentacles_activation(get_startup_tentacles_config())[TENTACLES_TRADING_PATH]


def get_tentacle_documentation(klass, media_url):
    doc_file = get_tentacle_documentation_path(klass)
    if isfile(doc_file):
        resource_url = f"{media_url}/{get_tentacle_resources_path(klass).replace(sep, '/')}/"
        with open(doc_file) as doc_file:
            doc_content = doc_file.read()
            # patch resources paths into the tentacle resource path
            return doc_content.replace("resources/", resource_url)
    return ""


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
        trading_config = _get_trading_tentacles_activation()
        for key, val in trading_config.items():
            config_class = get_class_from_string(key, AbstractTradingMode, modes, trading_mode_parent_inspection)
            if config_class:
                strategy_config[TRADING_MODES_KEY][key] = {}
                strategy_config[TRADING_MODES_KEY][key][ACTIVATION_KEY] = val
                strategy_config[TRADING_MODES_KEY][key][DESCRIPTION_KEY] = get_tentacle_documentation(key, media_url)
                strategy_config_classes[TRADING_MODES_KEY][key] = config_class

    evaluator_config = _get_evaluators_tentacles_activation()
    for key, val in evaluator_config.items():
        config_class = get_class_from_string(key, StrategyEvaluator,
                                             strategies, evaluator_parent_inspection)
        if config_class:
            strategy_config[STRATEGIES_KEY][key] = {}
            strategy_config[STRATEGIES_KEY][key][ACTIVATION_KEY] = val
            strategy_config[STRATEGIES_KEY][key][DESCRIPTION_KEY] = get_tentacle_documentation(key, media_url)
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


def _get_activation_state(name, activation_states):
    return name in activation_states and activation_states[name]


def get_tentacle_from_string(name, media_url, with_info=True):
    for package, abstract_class, tentacle_type in _get_tentacle_packages():
        is_trading_mode = tentacle_type == TRADING_MODE_KEY
        parent_inspector = trading_mode_parent_inspection if is_trading_mode else evaluator_parent_inspection
        klass = get_class_from_string(name, abstract_class, package, parent_inspector)
        if klass:
            if with_info:
                info = {
                    DESCRIPTION_KEY: get_tentacle_documentation(name, media_url),
                    NAME_KEY: name
                }
                if is_trading_mode:
                    _add_trading_mode_requirements_and_default_config(info, klass)
                    activation_states = _get_trading_tentacles_activation()
                else:
                    activation_states = _get_evaluators_tentacles_activation()
                    if tentacle_type == STRATEGY_KEY:
                        _add_strategy_requirements_and_default_config(info, klass)
                info[ACTIVATION_KEY] = _get_activation_state(name, activation_states)
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


def _get_tentacle_activation_desc(name, activated, startup_val, media_url):
    return {
        TENTACLE_CLASS_NAME: name,
        ACTIVATION_KEY: activated,
        DESCRIPTION_KEY: get_tentacle_documentation(name, media_url),
        STARTUP_CONFIG_KEY: startup_val
    }, get_tentacle_group(name)


def _add_tentacles_activation_desc_for_group(activation_by_group, tentacles_activation, startup_tentacles_activation,
                                             root_element, media_url):
    for tentacle_class_name, activated in tentacles_activation[root_element].items():
        startup_val = startup_tentacles_activation[root_element][tentacle_class_name]
        tentacle, group = _get_tentacle_activation_desc(tentacle_class_name, activated, startup_val, media_url)
        if group in activation_by_group:
            activation_by_group[group].append(tentacle)
        else:
            activation_by_group[group] = [tentacle]


def get_tentacles_activation_desc_by_group(media_url):
    tentacles_activation = get_tentacles_activation(get_edited_tentacles_config())
    startup_tentacles_activation = get_tentacles_activation(get_startup_tentacles_config())
    activation_by_group = {}
    for root_element in NON_TRADING_STRATEGY_RELATED_TENTACLES:
        try:
            _add_tentacles_activation_desc_for_group(activation_by_group, tentacles_activation,
                                                     startup_tentacles_activation, root_element, media_url)
        except KeyError:
            pass
    # only return tentacle groups for which there is an activation choice to simplify the config interface
    return {group: tentacles
            for group, tentacles in activation_by_group.items()
            if len(tentacles) > 1}


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
    requirements = REQUIREMENTS_KEY
    required_elements = set()
    for element_type in elements_config.values():
        for element_name, element in element_type.items():
            if element[ACTIVATION_KEY]:
                if requirements in element:
                    required_elements = required_elements.union(element[requirements])
    return required_elements


def _add_strategy_requirements_and_default_config(desc, klass):
    strategy_config = get_tentacle_config(klass)
    desc[REQUIREMENTS_KEY] = [evaluator for evaluator in klass.get_required_evaluators(strategy_config)]
    desc[COMPATIBLE_TYPES_KEY] = [evaluator for evaluator in klass.get_compatible_evaluators_types(strategy_config)]
    desc[DEFAULT_CONFIG_KEY] = [evaluator for evaluator in klass.get_default_evaluators(strategy_config)]


def _add_trading_mode_requirements_and_default_config(desc, klass):
    mode_config = get_tentacle_config(klass)
    required_strategies, required_strategies_count = klass.get_required_strategies_names_and_count(mode_config)
    if required_strategies:
        desc[REQUIREMENTS_KEY] = \
            [strategy for strategy in required_strategies]
        desc[DEFAULT_CONFIG_KEY] = \
            [strategy for strategy in klass.get_default_strategies(mode_config)]
        desc[REQUIREMENTS_COUNT_KEY] = required_strategies_count
    else:
        desc[REQUIREMENTS_KEY] = []
        desc[REQUIREMENTS_COUNT_KEY] = 0


def _add_strategies_requirements(strategies, strategy_config):
    required_elements = _get_required_element(strategy_config)
    for classKey, klass in strategies.items():
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
        detailed_config[eval_type_key][evaluator_name][ACTIVATION_KEY] = activated
        detailed_config[eval_type_key][evaluator_name][DESCRIPTION_KEY] = get_tentacle_documentation(evaluator_name,
                                                                                                     media_url)
        detailed_config[eval_type_key][evaluator_name][EVALUATION_FORMAT_KEY] = "float" \
            if klass.get_eval_type() == EVALUATOR_EVAL_DEFAULT_TYPE else str(klass.get_eval_type())
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
    evaluator_config = _get_evaluators_tentacles_activation()
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
                                             if details[ACTIVATION_KEY]]
    return detailed_config


def get_config_activated_trading_mode():
    return get_activated_trading_mode(get_bot_api().get_edited_tentacles_config())


def update_tentacles_activation_config(new_config, deactivate_others=False):
    tentacles_setup_configuration = get_edited_tentacles_config()
    try:
        updated_config = {
            element_name: activated if isinstance(activated, bool) else activated.lower() == "true"
            for element_name, activated in new_config.items()
        }
        if update_activation_configuration(get_edited_tentacles_config(), updated_config, deactivate_others):
            save_tentacles_setup_configuration(tentacles_setup_configuration)
        return True
    except Exception as e:
        LOGGER.exception(e, True, f"Error when updating tentacles activation {e}")
        return False


def _handle_special_fields(new_config):
    try:
        # replace web interface password by its hash before storage
        web_password_key = UPDATED_CONFIG_SEPARATOR.join([CONFIG_CATEGORY_SERVICES, CONFIG_WEB, CONFIG_WEB_PASSWORD])
        new_config[web_password_key] = config_manager.get_password_hash(new_config[web_password_key])
    except KeyError:
        pass


def update_global_config(new_config, delete=False):
    current_edited_config = get_edited_config()
    if not delete:
        _handle_special_fields(new_config)
    config_manager.update_global_config(new_config,
                                        current_edited_config,
                                        CONFIG_FILE_SCHEMA,
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
    for service in get_available_services():
        srv = service.instance()
        if srv.get_required_config():
            # do not add services without a config, ex: GoogleService (nothing to show on the web interface)
            services[srv.get_type()] = srv
    return services


def get_notifiers_list():
    return [service.instance().get_type()
            for notifier in create_notifier_factory({}).get_available_notifiers()
            for service in notifier.REQUIRED_SERVICES]


def get_symbol_list(exchanges):
    result = []
    for exchange in exchanges:
        if exchange not in exchange_symbol_fetch_blacklist:
            if exchange in markets_by_exchanges:
                result += markets_by_exchanges[exchange]
            else:
                try:
                    inst = getattr(ccxt, exchange)({'verbose': False})
                    inst.load_markets()
                    # filter symbols with a "." or no "/" because bot can't handle them for now
                    markets_by_exchanges[exchange] = [res for res in inst.symbols if "/" in res]
                    result += markets_by_exchanges[exchange]
                except Exception as e:
                    LOGGER.exception(e, True, f"error when loading symbol list for {exchange}: {e}")

    return list(set(result))


def get_all_symbols_dict():
    global all_symbols_dict
    if not all_symbols_dict:
        try:
            all_symbols_dict = {
                currency_data[NAME_KEY]: currency_data["symbol"]
                for currency_data in requests.get(CURRENCIES_LIST_URL).json()["data"]
            }
        except Exception as e:
            LOGGER.error(f"Failed to get currencies list from coinmarketcap : {e}")
            return {}
    return all_symbols_dict


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
