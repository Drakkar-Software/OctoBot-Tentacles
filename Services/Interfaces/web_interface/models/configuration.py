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
import asyncio
import os.path as path
import ccxt
import ccxt.async_support
import copy
import requests.adapters
import requests.packages.urllib3.util.retry
import octobot_commons.display as display

import octobot_evaluators.constants as evaluators_constants
import octobot_evaluators.evaluators as evaluators
import octobot_evaluators.api as evaluators_api
import octobot_services.api as services_api
import octobot_services.constants as services_constants
import octobot_services.interfaces.util as interfaces_util
import octobot_tentacles_manager.api as tentacles_manager_api
import octobot_tentacles_manager.constants as tentacles_manager_constants
import octobot_trading.api as trading_api
import octobot_trading.constants as trading_constants
import octobot_trading.modes as trading_modes
import octobot_trading.exchanges as trading_exchanges
import tentacles.Services.Interfaces.web_interface.constants as constants
import octobot_commons.constants as commons_constants
import octobot_commons.logging as bot_logging
import octobot_commons.enums as commons_enums
import octobot_commons.configuration as configuration
import octobot_commons.tentacles_management as tentacles_management
import octobot_commons.time_frame_manager as time_frame_manager
import octobot_commons.authentication as authentication
import octobot_commons.symbols as commons_symbols
import octobot_commons
import octobot_backtesting.api as backtesting_api
import octobot.community as community
import octobot.constants as octobot_constants
import octobot.enums as octobot_enums

NAME_KEY = "name"
SYMBOL_KEY = "symbol"
ID_KEY = "id"
EXCLUDED_CURRENCY_SUBNAME = tuple(("X Long", "X Short"))
DESCRIPTION_KEY = "description"
REQUIREMENTS_KEY = "requirements"
COMPATIBLE_TYPES_KEY = "compatible-types"
REQUIREMENTS_COUNT_KEY = "requirements-min-count"
DEFAULT_CONFIG_KEY = "default-config"
TRADING_MODES_KEY = "trading-modes"
STRATEGIES_KEY = "strategies"
TRADING_MODE_KEY = "trading mode"
EXCHANGE_KEY = "exchange"
STRATEGY_KEY = "strategy"
TA_EVALUATOR_KEY = "technical evaluator"
SOCIAL_EVALUATOR_KEY = "social evaluator"
RT_EVALUATOR_KEY = "real time evaluator"
SCRIPTED_EVALUATOR_KEY = "scripted evaluator"
REQUIRED_KEY = "required"
SOCIAL_KEY = "social"
TA_KEY = "ta"
RT_KEY = "real-time"
SCRIPTED_KEY = "scripted"
ACTIVATED_STRATEGIES = "activated_strategies"
BASE_CLASSES_KEY = "base_classes"
EVALUATION_FORMAT_KEY = "evaluation_format"
CONFIG_KEY = "config"
DISPLAYED_ELEMENTS_KEY = "displayed_elements"

# tentacles from which configuration is not handled in strategies / evaluators configuration
NON_TRADING_STRATEGY_RELATED_TENTACLES = [tentacles_manager_constants.TENTACLES_BACKTESTING_PATH,
                                          tentacles_manager_constants.TENTACLES_SERVICES_PATH,
                                          tentacles_manager_constants.TENTACLES_TRADING_PATH]

DEFAULT_EXCHANGE = "binance"


def _get_currency_dict(symbol, identifier):
    return {
        SYMBOL_KEY: symbol.upper(),
        ID_KEY: identifier
    }


# forced cryptocurrencies to be displayed in currency selector
FORCED_CURRENCIES_DICT = {
    "HollaEx": _get_currency_dict("XHT", "hollaex-token")
}

# buffers to faster config page loading
markets_by_exchanges = {}
all_symbols_dict = {}
exchange_logos = {}
# can't fetch symbols from coinmarketcap.com (which is in ccxt but is not an exchange and has a paid api)
exchange_symbol_fetch_blacklist = {"coinmarketcap"}
_LOGGER = None


def _get_logger():
    global _LOGGER
    if _LOGGER is None:
        _LOGGER = bot_logging.get_logger("WebConfigurationModel")
    return _LOGGER


def _get_evaluators_tentacles_activation():
    return tentacles_manager_api.get_tentacles_activation(interfaces_util.get_edited_tentacles_config())[
        tentacles_manager_constants.TENTACLES_EVALUATOR_PATH]


def _get_trading_tentacles_activation():
    return tentacles_manager_api.get_tentacles_activation(interfaces_util.get_edited_tentacles_config())[
        tentacles_manager_constants.TENTACLES_TRADING_PATH]


def get_evaluators_tentacles_startup_activation():
    return tentacles_manager_api.get_tentacles_activation(interfaces_util.get_startup_tentacles_config())[
        tentacles_manager_constants.TENTACLES_EVALUATOR_PATH]


def get_trading_tentacles_startup_activation():
    return tentacles_manager_api.get_tentacles_activation(interfaces_util.get_startup_tentacles_config())[
        tentacles_manager_constants.TENTACLES_TRADING_PATH]


def get_tentacle_documentation(name, media_url, missing_tentacles: set = None):
    try:
        doc_file = tentacles_manager_api.get_tentacle_documentation_path(name)
        if path.isfile(doc_file):
            resource_url = f"{media_url}/{tentacles_manager_api.get_tentacle_resources_path(name).replace(path.sep, '/')}/"
            with open(doc_file) as doc_file:
                doc_content = doc_file.read()
                # patch resources paths into the tentacle resource path
                return doc_content.replace(f"{tentacles_manager_constants.TENTACLE_RESOURCES}/", resource_url)
    except KeyError as e:
        if missing_tentacles is None or name not in missing_tentacles:
            _get_logger().error(f"Impossible to load tentacle documentation for {name} ({e.__class__.__name__}: {e}). "
                                f"This is probably an issue with the {name} tentacle matadata.json file, please "
                                f"make sure this file is accurate and is referring {name} in the 'tentacles' list.")
        return ""
    except TypeError:
        # can happen when tentacles metadata.json are invalid
        return ""

def _get_strategy_activation_state(with_trading_modes, media_url, missing_tentacles: set):
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
            config_class = tentacles_management.get_class_from_string(key, trading_modes.AbstractTradingMode, modes,
                                                                      tentacles_management.trading_mode_parent_inspection)
            if config_class:
                strategy_config[TRADING_MODES_KEY][key] = {}
                strategy_config[TRADING_MODES_KEY][key][constants.ACTIVATION_KEY] = val
                strategy_config[TRADING_MODES_KEY][key][DESCRIPTION_KEY] = get_tentacle_documentation(key, media_url)
                strategy_config_classes[TRADING_MODES_KEY][key] = config_class
            else:
                _add_to_missing_tentacles_if_missing(key, missing_tentacles)

    evaluator_config = _get_evaluators_tentacles_activation()
    for key, val in evaluator_config.items():
        config_class = tentacles_management.get_class_from_string(key, evaluators.StrategyEvaluator,
                                                                  strategies,
                                                                  tentacles_management.evaluator_parent_inspection)
        if config_class:
            strategy_config[STRATEGIES_KEY][key] = {}
            strategy_config[STRATEGIES_KEY][key][constants.ACTIVATION_KEY] = val
            strategy_config[STRATEGIES_KEY][key][DESCRIPTION_KEY] = get_tentacle_documentation(key, media_url)
            strategy_config_classes[STRATEGIES_KEY][key] = config_class
        else:
            _add_to_missing_tentacles_if_missing(key, missing_tentacles)

    return strategy_config, strategy_config_classes


def _add_to_missing_tentacles_if_missing(tentacle_name: str, missing_tentacles: set):
    # if tentacle_name can't be accessed in tentacles manager, this tentacle is not available
    try:
        tentacles_manager_api.get_tentacle_version(tentacle_name)
    except KeyError:
        missing_tentacles.add(tentacle_name)
    except AttributeError:
        _get_logger().debug(f"Missing tentacles data for {tentacle_name}. This is likely due to an error in the "
                            f"associated metadata.json file.")
        missing_tentacles.add(tentacle_name)


def _get_tentacle_packages():
    import tentacles.Trading.Mode as modes
    yield modes, trading_modes.AbstractTradingMode, TRADING_MODE_KEY
    import tentacles.Evaluator.Strategies as strategies
    yield strategies, evaluators.StrategyEvaluator, STRATEGY_KEY
    import tentacles.Evaluator.TA as ta
    yield ta, evaluators.AbstractEvaluator, TA_EVALUATOR_KEY
    import tentacles.Evaluator.Social as social
    yield social, evaluators.AbstractEvaluator, SOCIAL_EVALUATOR_KEY
    import tentacles.Evaluator.RealTime as rt
    yield rt, evaluators.AbstractEvaluator, RT_EVALUATOR_KEY
    import tentacles.Evaluator.Scripted as scripted
    yield scripted, evaluators.ScriptedEvaluator, SCRIPTED_EVALUATOR_KEY
    import tentacles.Trading.Exchange as exchanges
    yield exchanges, trading_exchanges.AbstractExchange, EXCHANGE_KEY


def _get_activation_state(name, activation_states):
    return name in activation_states and activation_states[name]


def get_tentacle_from_string(name, media_url, with_info=True):
    for package, abstract_class, tentacle_type in _get_tentacle_packages():
        parent_inspector = tentacles_management.evaluator_parent_inspection
        if tentacle_type == TRADING_MODE_KEY:
            parent_inspector = tentacles_management.trading_mode_parent_inspection
        if tentacle_type == EXCHANGE_KEY:
            parent_inspector = tentacles_management.default_parents_inspection
        klass = tentacles_management.get_class_from_string(name, abstract_class, package, parent_inspector)
        if klass:
            if with_info:
                info = {
                    DESCRIPTION_KEY: get_tentacle_documentation(name, media_url),
                    NAME_KEY: name
                }
                if tentacle_type == TRADING_MODE_KEY:
                    _add_trading_mode_requirements_and_default_config(info, klass)
                    activation_states = _get_trading_tentacles_activation()
                elif tentacle_type == EXCHANGE_KEY:
                    activation_states = _get_trading_tentacles_activation()
                else:
                    activation_states = _get_evaluators_tentacles_activation()
                    if tentacle_type == STRATEGY_KEY:
                        _add_strategy_requirements_and_default_config(info, klass)
                info[constants.ACTIVATION_KEY] = _get_activation_state(name, activation_states)
                return klass, tentacle_type, info
            else:
                return klass, tentacle_type, None
    return None, None, None


def get_tentacle_user_commands(klass):
    return klass.get_user_commands() if klass is not None and hasattr(klass, "get_user_commands") else {}


def get_tentacle_config_and_edit_display(tentacle):
    tentacle_class = tentacles_manager_api.get_tentacle_class_from_string(tentacle)
    config, user_inputs = interfaces_util.run_in_bot_main_loop(
        tentacle_class.get_raw_config_and_user_inputs(
            interfaces_util.get_edited_config(),
            interfaces_util.get_edited_tentacles_config(),
            interfaces_util.get_bot_api().get_bot_id()
        )
    )
    display_elements = display.display_translator_factory()
    display_elements.add_user_inputs(user_inputs)
    return {
        NAME_KEY: tentacle,
        CONFIG_KEY: config or {},
        DISPLAYED_ELEMENTS_KEY: display_elements.to_json()
    }


def get_tentacle_config(klass):
    return tentacles_manager_api.get_tentacle_config(interfaces_util.get_edited_tentacles_config(), klass)


def get_tentacle_config_schema(klass):
    try:
        with open(tentacles_manager_api.get_tentacle_config_schema_path(klass)) as schema_file:
            return schema_file.read()
    except Exception:
        return ""


def _get_tentacle_activation_desc(name, activated, startup_val, media_url, missing_tentacles: set):
    return {
               constants.TENTACLE_CLASS_NAME: name,
               constants.ACTIVATION_KEY: activated,
               DESCRIPTION_KEY: get_tentacle_documentation(name, media_url, missing_tentacles),
               constants.STARTUP_CONFIG_KEY: startup_val
           }, tentacles_manager_api.get_tentacle_group(name)


def _add_tentacles_activation_desc_for_group(activation_by_group, tentacles_activation, startup_tentacles_activation,
                                             root_element, media_url, missing_tentacles: set):
    for tentacle_class_name, activated in tentacles_activation[root_element].items():
        startup_val = startup_tentacles_activation[root_element][tentacle_class_name]
        try:
            tentacle, group = _get_tentacle_activation_desc(tentacle_class_name, activated, startup_val, media_url,
                                                            missing_tentacles)
            if group in activation_by_group:
                activation_by_group[group].append(tentacle)
            else:
                activation_by_group[group] = [tentacle]
        except AttributeError:
            # can happen when tentacles metadata.json are invalid
            pass

def get_tentacles_activation_desc_by_group(media_url, missing_tentacles: set):
    tentacles_activation = tentacles_manager_api.get_tentacles_activation(interfaces_util.get_edited_tentacles_config())
    startup_tentacles_activation = tentacles_manager_api.get_tentacles_activation(
        interfaces_util.get_startup_tentacles_config())
    activation_by_group = {}
    for root_element in NON_TRADING_STRATEGY_RELATED_TENTACLES:
        try:
            _add_tentacles_activation_desc_for_group(activation_by_group, tentacles_activation,
                                                     startup_tentacles_activation, root_element, media_url,
                                                     missing_tentacles)
        except KeyError:
            pass
    # only return tentacle groups for which there is an activation choice to simplify the config interface
    return {group: tentacles
            for group, tentacles in activation_by_group.items()
            if len(tentacles) > 1}


def update_tentacle_config(tentacle_name, config_update):
    try:
        klass, _, _ = get_tentacle_from_string(tentacle_name, None, with_info=False)
        if klass is None:
            return False, f"Can't find {tentacle_name} class"
        tentacles_manager_api.update_tentacle_config(interfaces_util.get_edited_tentacles_config(),
                                                     klass,
                                                     config_update)
        return True, f"{tentacle_name} updated"
    except Exception as e:
        _get_logger().exception(e, False)
        return False, f"Error when updating tentacle config: {e}"


def update_copied_trading_id(copy_id):
    import tentacles.Trading.Mode as modes
    return update_tentacle_config(
        modes.RemoteTradingSignalsTradingMode.get_name(),
        {
            "trading_strategy": copy_id
        }
    )


def reset_config_to_default(tentacle_name):
    try:
        klass, _, _ = get_tentacle_from_string(tentacle_name, None, with_info=False)
        tentacles_manager_api.factory_tentacle_reset_config(interfaces_util.get_edited_tentacles_config(),
                                                            klass)
        return True, f"{tentacle_name} configuration reset to default values"
    except FileNotFoundError as e:
        error_message = f"Error when resetting factory tentacle config: no default values file at {e.filename}"
        _get_logger().error(error_message)
        return False, error_message
    except Exception as e:
        _get_logger().exception(e, False)
        return False, f"Error when resetting factory tentacle config: {e}"


def _get_required_element(elements_config):
    requirements = REQUIREMENTS_KEY
    required_elements = set()
    for element_type in elements_config.values():
        for element_name, element in element_type.items():
            if element[constants.ACTIVATION_KEY]:
                if requirements in element:
                    required_elements = required_elements.union(element[requirements])
    return required_elements


def _add_strategy_requirements_and_default_config(desc, klass):
    tentacles_config = interfaces_util.get_startup_tentacles_config()
    strategy_config = get_tentacle_config(klass)
    desc[REQUIREMENTS_KEY] = [evaluator for evaluator in klass.get_required_evaluators(tentacles_config,
                                                                                       strategy_config)]
    desc[COMPATIBLE_TYPES_KEY] = [evaluator for evaluator in klass.get_compatible_evaluators_types(tentacles_config,
                                                                                                   strategy_config)]
    desc[DEFAULT_CONFIG_KEY] = [evaluator for evaluator in klass.get_default_evaluators(tentacles_config,
                                                                                        strategy_config)]


def _add_trading_mode_requirements_and_default_config(desc, klass):
    tentacles_config = interfaces_util.get_startup_tentacles_config()
    mode_config = get_tentacle_config(klass)
    required_strategies, required_strategies_count = klass.get_required_strategies_names_and_count(tentacles_config,
                                                                                                   mode_config)
    if required_strategies:
        desc[REQUIREMENTS_KEY] = \
            [strategy for strategy in required_strategies]
        desc[DEFAULT_CONFIG_KEY] = \
            [strategy for strategy in klass.get_default_strategies(tentacles_config, mode_config)]
        desc[REQUIREMENTS_COUNT_KEY] = required_strategies_count
    else:
        desc[REQUIREMENTS_KEY] = []
        desc[REQUIREMENTS_COUNT_KEY] = 0


def _add_strategies_requirements(strategies, strategy_config):
    required_elements = _get_required_element(strategy_config)
    for classKey, klass in strategies.items():
        _add_strategy_requirements_and_default_config(strategy_config[STRATEGIES_KEY][classKey], klass)
        strategy_config[STRATEGIES_KEY][classKey][REQUIRED_KEY] = classKey in required_elements


def _add_trading_modes_requirements(trading_modes_list, strategy_config):
    for classKey, klass in trading_modes_list.items():
        try:
            _add_trading_mode_requirements_and_default_config(strategy_config[TRADING_MODES_KEY][classKey], klass)
        except Exception as e:
            _get_logger().exception(e, False)


def get_strategy_config(media_url, missing_tentacles: set, with_trading_modes=True):
    strategy_config, strategy_config_classes = _get_strategy_activation_state(with_trading_modes,
                                                                              media_url,
                                                                              missing_tentacles)
    if with_trading_modes:
        _add_trading_modes_requirements(strategy_config_classes[TRADING_MODES_KEY], strategy_config)
    _add_strategies_requirements(strategy_config_classes[STRATEGIES_KEY], strategy_config)
    return strategy_config


def get_in_backtesting_mode():
    return backtesting_api.is_backtesting_enabled(interfaces_util.get_global_config())


def accepted_terms():
    return interfaces_util.get_edited_config(dict_only=False).accepted_terms()


def accept_terms(accepted):
    return interfaces_util.get_edited_config(dict_only=False).accept_terms(accepted)


def _fill_evaluator_config(evaluator_name, activated, eval_type_key,
                           evaluator_type, detailed_config, media_url, is_strategy=False):
    klass = tentacles_management.get_class_from_string(evaluator_name, evaluators.AbstractEvaluator, evaluator_type,
                                                       tentacles_management.evaluator_parent_inspection)
    if klass:
        detailed_config[eval_type_key][evaluator_name] = {}
        detailed_config[eval_type_key][evaluator_name][constants.ACTIVATION_KEY] = activated
        detailed_config[eval_type_key][evaluator_name][DESCRIPTION_KEY] = get_tentacle_documentation(evaluator_name,
                                                                                                     media_url)
        detailed_config[eval_type_key][evaluator_name][EVALUATION_FORMAT_KEY] = "float" \
            if klass.get_eval_type() == evaluators_constants.EVALUATOR_EVAL_DEFAULT_TYPE else str(klass.get_eval_type())
        return True, klass
    return False, klass


def get_evaluator_detailed_config(media_url, missing_tentacles: set):
    import tentacles.Evaluator.Strategies as strategies
    import tentacles.Evaluator.TA as ta
    import tentacles.Evaluator.Social as social
    import tentacles.Evaluator.RealTime as rt
    import tentacles.Evaluator.Scripted as scripted
    detailed_config = {
        SOCIAL_KEY: {},
        TA_KEY: {},
        RT_KEY: {},
        SCRIPTED_KEY: {}
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
                    is_scripted, klass = _fill_evaluator_config(evaluator_name, activated, SCRIPTED_KEY,
                                                                scripted, detailed_config, media_url)
                    if not is_scripted:
                        is_strategy, klass = _fill_evaluator_config(evaluator_name, activated, STRATEGIES_KEY,
                                                                    strategies, strategy_config, media_url,
                                                                    is_strategy=True)
                        if is_strategy:
                            strategy_class_by_name[evaluator_name] = klass
                        else:
                            _add_to_missing_tentacles_if_missing(evaluator_name, missing_tentacles)

    _add_strategies_requirements(strategy_class_by_name, strategy_config)
    required_elements = _get_required_element(strategy_config)
    for eval_type in detailed_config.values():
        for eval_name, eval_details in eval_type.items():
            eval_details[REQUIRED_KEY] = eval_name in required_elements

    detailed_config[ACTIVATED_STRATEGIES] = [s for s, details in strategy_config[STRATEGIES_KEY].items()
                                             if details[constants.ACTIVATION_KEY]]
    return detailed_config


def get_config_activated_trading_mode():
    return trading_api.get_activated_trading_mode(interfaces_util.get_bot_api().get_edited_tentacles_config())


def get_config_activated_strategies():
    return evaluators_api.get_activated_strategies_classes(interfaces_util.get_bot_api().get_edited_tentacles_config())


def get_config_activated_evaluators():
    return evaluators_api.get_activated_evaluators(interfaces_util.get_bot_api().get_edited_tentacles_config())


def update_tentacles_activation_config(new_config, deactivate_others=False):
    tentacles_setup_configuration = interfaces_util.get_edited_tentacles_config()
    try:
        updated_config = {
            element_name: activated if isinstance(activated, bool) else activated.lower() == "true"
            for element_name, activated in new_config.items()
        }
        if tentacles_manager_api.update_activation_configuration(interfaces_util.get_edited_tentacles_config(),
                                                                 updated_config, deactivate_others):
            tentacles_manager_api.save_tentacles_setup_configuration(tentacles_setup_configuration)
        return True
    except Exception as e:
        _get_logger().exception(e, True, f"Error when updating tentacles activation {e}")
        return False


def _handle_special_fields(config, new_config):
    try:
        # replace web interface password by its hash before storage
        web_password_key = constants.UPDATED_CONFIG_SEPARATOR.join([services_constants.CONFIG_CATEGORY_SERVICES,
                                                                    services_constants.CONFIG_WEB,
                                                                    services_constants.CONFIG_WEB_PASSWORD])
        if web_password_key in new_config:
            new_config[web_password_key] = configuration.get_password_hash(new_config[web_password_key])
        # add exchange enabled param if missing
        for key in list(new_config.keys()):
            values = key.split(constants.UPDATED_CONFIG_SEPARATOR)
            if values[0] == commons_constants.CONFIG_EXCHANGES and \
                    values[1] not in config[commons_constants.CONFIG_EXCHANGES]:
                enabled_key = constants.UPDATED_CONFIG_SEPARATOR.join([commons_constants.CONFIG_EXCHANGES,
                                                                       values[1],
                                                                       commons_constants.CONFIG_ENABLED_OPTION])
                if enabled_key not in new_config:
                    new_config[enabled_key] = True
    except KeyError:
        pass


def update_global_config(new_config, delete=False):
    try:
        current_edited_config = interfaces_util.get_edited_config(dict_only=False)
        if not delete:
            _handle_special_fields(current_edited_config.config, new_config)
        current_edited_config.update_config_fields(new_config,
                                                   backtesting_api.is_backtesting_enabled(current_edited_config.config),
                                                   constants.UPDATED_CONFIG_SEPARATOR,
                                                   delete=delete)
        return True
    except Exception as e:
        _get_logger().exception(e, True, f"Error when updating global config {e}")
        return False


def activate_metrics(enable_metrics):
    current_edited_config = interfaces_util.get_edited_config(dict_only=False)
    if commons_constants.CONFIG_METRICS not in current_edited_config.config:
        current_edited_config.config[commons_constants.CONFIG_METRICS] = {
            commons_constants.CONFIG_ENABLED_OPTION: enable_metrics}
    else:
        current_edited_config.config[commons_constants.CONFIG_METRICS][
            commons_constants.CONFIG_ENABLED_OPTION] = enable_metrics
    if enable_metrics and community.CommunityManager.should_register_bot(current_edited_config):
        community.CommunityManager.background_get_id_and_register_bot(interfaces_util.get_bot_api())
    current_edited_config.save()


def activate_beta_env(enable_beta):
    new_env = octobot_enums.CommunityEnvironments.Staging if enable_beta \
        else octobot_enums.CommunityEnvironments.Production
    current_edited_config = interfaces_util.get_edited_config(dict_only=False)
    if octobot_constants.CONFIG_COMMUNITY not in current_edited_config.config:
        current_edited_config.config[octobot_constants.CONFIG_COMMUNITY] = {}
    current_edited_config.config[octobot_constants.CONFIG_COMMUNITY][
        octobot_constants.CONFIG_COMMUNITY_ENVIRONMENT] = new_env.value
    current_edited_config.save()


def get_metrics_enabled():
    return interfaces_util.get_edited_config(dict_only=False).get_metrics_enabled()


def get_beta_env_enabled_in_config():
    return community.IdentifiersProvider.is_staging_environment_enabled(
        interfaces_util.get_edited_config(dict_only=True)
    )


def get_services_list():
    services = {}
    for service in services_api.get_available_services():
        srv = service.instance()
        if srv.get_required_config():
            # do not add services without a config, ex: GoogleService (nothing to show on the web interface)
            services[srv.get_type()] = srv
    return services


def get_notifiers_list():
    return [service.instance().get_type()
            for notifier in services_api.create_notifier_factory({}).get_available_notifiers()
            for service in notifier.REQUIRED_SERVICES]


def get_enabled_trading_pairs() -> set:
    symbols = set()
    for values in format_config_symbols(interfaces_util.get_edited_config()).values():
        if values[commons_constants.CONFIG_ENABLED_OPTION]:
            symbols = symbols.union(set(values[commons_constants.CONFIG_CRYPTO_PAIRS]))
    return symbols


def get_symbol_list(exchanges):
    result = interfaces_util.run_in_bot_async_executor(_load_markets(exchanges))
    return list(set(result))


def _get_filtered_exchange_symbols(symbols):
    return [res for res in symbols if octobot_commons.MARKET_SEPARATOR in res]


async def _load_market(exchange, results):
    try:
        async with getattr(ccxt.async_support, exchange)({'verbose': False}) as exchange_inst:
            await exchange_inst.load_markets()
            # filter symbols with a "." or no "/" because bot can't handle them for now
            markets_by_exchanges[exchange] = _get_filtered_exchange_symbols(exchange_inst.symbols)
            results.append(markets_by_exchanges[exchange])
    except Exception as e:
        _get_logger().exception(e, True, f"error when loading symbol list for {exchange}: {e}")


async def _load_markets(exchanges):
    result = []
    results = []
    fetch_coros = []
    exchange_managers = trading_api.get_exchange_managers_from_exchange_ids(
        trading_api.get_exchange_ids()
    )
    exchange_manager_by_exchange_name = {
        trading_api.get_exchange_name(exchange_manager): exchange_manager
        for exchange_manager in exchange_managers
    }
    for exchange in exchanges:
        if exchange not in exchange_symbol_fetch_blacklist:
            if exchange in exchange_manager_by_exchange_name and exchange not in markets_by_exchanges:
                markets_by_exchanges[exchange] = _get_filtered_exchange_symbols(
                    trading_api.get_all_exchange_symbols(exchange_manager_by_exchange_name[exchange])
                )
            if exchange in markets_by_exchanges:
                result += markets_by_exchanges[exchange]
            else:
                fetch_coros.append(_load_market(exchange, results))
    if fetch_coros:
        await asyncio.gather(*fetch_coros)
        for res in results:
            result += res
    return result


def get_config_time_frames() -> list:
    return time_frame_manager.get_config_time_frame(interfaces_util.get_global_config())


def get_timeframes_list(exchanges):
    timeframes_list = []
    allowed_timeframes = set(tf.value for tf in commons_enums.TimeFrames)
    for exchange in exchanges:
        if exchange not in exchange_symbol_fetch_blacklist:
            timeframes_list += interfaces_util.run_in_bot_async_executor(
                    trading_api.get_exchange_available_time_frames(exchange))
    return [commons_enums.TimeFrames(time_frame)
            for time_frame in list(set(timeframes_list))
            if time_frame in allowed_timeframes]


def get_strategy_required_time_frames(strategy_class):
    return strategy_class.get_required_time_frames({}, interfaces_util.get_edited_tentacles_config())


def format_config_symbols(config):
    for currency, data in config[commons_constants.CONFIG_CRYPTO_CURRENCIES].items():
        if commons_constants.CONFIG_ENABLED_OPTION not in data:
            config[commons_constants.CONFIG_CRYPTO_CURRENCIES][currency] = \
                {**{commons_constants.CONFIG_ENABLED_OPTION: True}, **data}
    return config[commons_constants.CONFIG_CRYPTO_CURRENCIES]


def _is_legit_currency(currency):
    return not any(sub_name in currency for sub_name in EXCLUDED_CURRENCY_SUBNAME) and len(currency) < 30


def get_all_symbols_dict():
    if not all_symbols_dict:
        request_response = None
        base_error = "Failed to get currencies list from coingecko.com (this is a display only issue): "
        try:
            # inspired from https://github.com/man-c/pycoingecko
            session = requests.Session()
            retries = requests.packages.urllib3.util.retry.Retry(total=3, backoff_factor=0.5,
                                                                 status_forcelist=[502, 503, 504])
            session.mount('http://', requests.adapters.HTTPAdapter(max_retries=retries))
            # get top 500 coins (2 * 250)
            for i in range(1, 3):
                request_response = session.get(f"{constants.CURRENCIES_LIST_URL}{i}")
                if request_response.status_code == 429:
                    # rate limit issue
                    all_symbols_dict.clear()
                    _get_logger().warning(f"{base_error}Too many requests, retry in a few seconds")
                    break
                for currency_data in request_response.json():
                    if _is_legit_currency(currency_data[NAME_KEY]):
                        all_symbols_dict[currency_data[NAME_KEY]] = _get_currency_dict(
                            currency_data[SYMBOL_KEY],
                            currency_data[ID_KEY]
                        )
            _add_forced_currencies(all_symbols_dict)
        except Exception as e:
            details = f"code: {request_response.status_code}, body: {request_response.text}" \
                if request_response else {request_response}
            _get_logger().exception(e, True, f"{base_error}{e}")
            _get_logger().debug(f"coingecko.com response {details}")
            return {}
    return all_symbols_dict


def _add_forced_currencies(symbols_dict):
    symbols_dict.update(FORCED_CURRENCIES_DICT)


def get_exchange_logo(exchange_name):
    try:
        return exchange_logos[exchange_name]
    except KeyError:
        try:
            exchange_logos[exchange_name] = {"image": "", "url": ""}
            if isinstance(exchange_name, str) and exchange_name != "Bitcoin":
                exchange = getattr(ccxt, exchange_name)()
                exchange_logos[exchange_name]["image"] = exchange.urls["logo"]
                exchange_logos[exchange_name]["url"] = exchange.urls["www"]
        except KeyError:
            pass
    return exchange_logos[exchange_name]


def get_traded_time_frames(exchange_manager):
    return trading_api.get_relevant_time_frames(exchange_manager)


def get_full_exchange_list(remove_config_exchanges=False):
    g_config = interfaces_util.get_global_config()
    if remove_config_exchanges:
        user_exchanges = [e for e in g_config[commons_constants.CONFIG_EXCHANGES]]
        full_exchange_list = list(set(ccxt.exchanges) - set(user_exchanges))
    else:
        full_exchange_list = list(set(ccxt.exchanges))
    # can't handle exchanges containing UPDATED_CONFIG_SEPARATOR character in their name
    return [exchange for exchange in full_exchange_list if constants.UPDATED_CONFIG_SEPARATOR not in exchange]


def get_tested_exchange_list():
    full_exchange_list = list(set(ccxt.exchanges))
    return [exchange for exchange in trading_constants.TESTED_EXCHANGES if exchange in full_exchange_list]


def get_simulated_exchange_list():
    full_exchange_list = list(set(ccxt.exchanges))
    return [exchange for exchange in trading_constants.SIMULATOR_TESTED_EXCHANGES if exchange in full_exchange_list]


def get_other_exchange_list(remove_config_exchanges=False):
    full_list = get_full_exchange_list(remove_config_exchanges)
    return [exchange for exchange in full_list
            if
            exchange not in trading_constants.TESTED_EXCHANGES and exchange not in trading_constants.SIMULATOR_TESTED_EXCHANGES]


def get_exchanges_details(exchanges_config) -> dict:
    details = {}
    tentacles_setup_config = interfaces_util.get_edited_tentacles_config()
    import tentacles.Trading.Exchange as exchanges
    for exchange_name in exchanges_config:
        exchange_class = tentacles_management.get_class_from_string(
            exchange_name, trading_exchanges.AbstractExchange,
            exchanges,
            tentacles_management.default_parents_inspection
        )
        details[exchange_name] = {
            "has_websockets": trading_api.supports_websockets(exchange_name, tentacles_setup_config),
            "configurable": False if exchange_class is None else exchange_class.is_configurable(),
            "supported_exchange_types": trading_api.get_supported_exchange_types(exchange_name),
            "default_exchange_type": trading_api.get_default_exchange_type(exchange_name),
        }
    return details


def get_compatibility_result(exchange_name, auth_success, compatible_account, supporter_account,
                             configured_account, supporting_exchange, error_message):
    return {
        "exchange": exchange_name,
        "auth_success": auth_success,
        "compatible_account": compatible_account,
        "supporter_account": supporter_account,
        "configured_account": configured_account,
        "supporting_exchange": supporting_exchange,
        "error_message": error_message
    }


async def _fetch_is_compatible_account(exchange_name, to_check_config,
                                       compatibility_results, is_sponsoring, is_supporter):
    is_compatible, auth_success, error = await trading_api.is_compatible_account(
        exchange_name,
        to_check_config,
        interfaces_util.get_edited_tentacles_config(),
        to_check_config.get(commons_constants.CONFIG_EXCHANGE_SANDBOXED, False)
    )
    compatibility_results[exchange_name] = get_compatibility_result(
        exchange_name,
        auth_success,
        is_compatible,
        is_supporter,
        True,
        is_sponsoring,
        error
    )


def are_compatible_accounts(exchange_details: dict) -> dict:
    compatibility_results = {}
    check_coro = []
    for exchange, exchange_detail in exchange_details.items():
        exchange_name = exchange_detail["exchange"]
        api_key = exchange_detail["apiKey"]
        api_sec = exchange_detail["apiSecret"]
        api_pass = exchange_detail["apiPassword"]
        sandboxed = exchange_detail[commons_constants.CONFIG_EXCHANGE_SANDBOXED]
        to_check_config = copy.deepcopy(interfaces_util.get_edited_config()[commons_constants.CONFIG_EXCHANGES].get(
            exchange_name, {}))
        if _is_real_exchange_value(api_key):
            to_check_config[commons_constants.CONFIG_EXCHANGE_KEY] = configuration.encrypt(api_key).decode()
        if _is_real_exchange_value(api_sec):
            to_check_config[commons_constants.CONFIG_EXCHANGE_SECRET] = configuration.encrypt(api_sec).decode()
        if _is_real_exchange_value(api_pass):
            to_check_config[commons_constants.CONFIG_EXCHANGE_PASSWORD] = configuration.encrypt(api_pass).decode()
        to_check_config[commons_constants.CONFIG_EXCHANGE_SANDBOXED] = sandboxed
        is_compatible = auth_success = is_configured = False
        is_sponsoring = trading_api.is_sponsoring(exchange_name)
        is_supporter = authentication.Authenticator.instance().user_account.supports.is_supporting()
        error = None
        if _is_possible_exchange_config(to_check_config):
            check_coro.append(_fetch_is_compatible_account(exchange_name, to_check_config,
                                                           compatibility_results, is_sponsoring, is_supporter))
        else:
            compatibility_results[exchange_name] = get_compatibility_result(
                exchange_name,
                auth_success,
                is_compatible,
                is_supporter,
                is_configured,
                is_sponsoring,
                error
            )
    if check_coro:
        async def gather_wrapper(coros):
            await asyncio.gather(*coros)
        interfaces_util.run_in_bot_async_executor(
            gather_wrapper(check_coro)
        )
    return compatibility_results


def _is_possible_exchange_config(exchange_config):
    valid_count = 0
    for key, value in exchange_config.items():
        if key in commons_constants.CONFIG_EXCHANGE_ENCRYPTED_VALUES and _is_real_exchange_value(value):
            valid_count += 1
    # require at least 2 data to consider a configuration possible
    return valid_count >= 2


def _is_real_exchange_value(value):
    placeholder_key = "******"
    if placeholder_key in value:
        return False
    return value not in commons_constants.DEFAULT_CONFIG_VALUES


def get_current_exchange():
    for exchange_manager in interfaces_util.get_exchange_managers():
        return trading_api.get_exchange_name(exchange_manager)
    else:
        return DEFAULT_EXCHANGE


def change_reference_market_on_config_currencies(old_base_currency: str, new_quote_currency: str) -> bool:
    """
    Change the base currency from old to new for all configured pair
    :return: bool, str
    """
    success = True
    message = "Reference market changed for each pair using the old reference market"
    try:
        config_currencies = format_config_symbols(interfaces_util.get_edited_config())
        for currencies_config in config_currencies.values():
            currencies_config[commons_constants.CONFIG_CRYPTO_PAIRS] = \
                list(set([
                    _change_base(pair, new_quote_currency)
                    for pair in currencies_config[commons_constants.CONFIG_CRYPTO_PAIRS]
                ]))
        interfaces_util.get_edited_config(dict_only=False).save()
    except Exception as e:
        message = f"Error while changing reference market on currencies list: {e}"
        success = False
        bot_logging.get_logger("ConfigurationWebInterfaceModel").exception(e, False)
    return success, message


def _change_base(pair, new_quote_currency):
    parsed_symbol = commons_symbols.parse_symbol(pair)
    parsed_symbol.quote = new_quote_currency
    return parsed_symbol.merged_str_symbol()


def send_command_to_activated_tentacles(command, wait_for_processing=True):
    trading_mode_name = get_config_activated_trading_mode().get_name()
    evaluator_names = [
        evaluator.get_name()
        for evaluator in get_config_activated_evaluators()
    ]
    send_command_to_tentacles(command, [trading_mode_name] + evaluator_names, wait_for_processing=wait_for_processing)


def send_command_to_tentacles(command, tentacle_names: list, wait_for_processing=True):
    for tentacle_name in tentacle_names:
        interfaces_util.run_in_bot_main_loop(
            services_api.send_user_command(
                interfaces_util.get_bot_api().get_bot_id(),
                tentacle_name,
                command,
                None,
                wait_for_processing=wait_for_processing
            )
        )


def reload_scripts():
    try:
        send_command_to_activated_tentacles(commons_enums.UserCommands.RELOAD_SCRIPT.value)
        return {"success": True}
    except Exception as e:
        _get_logger().exception(e, True, f"Failed to reload scripts: {e}")
        raise


def reload_activated_tentacles_config():
    try:
        send_command_to_activated_tentacles(commons_enums.UserCommands.RELOAD_CONFIG.value)
        return {"success": True}
    except Exception as e:
        _get_logger().exception(e, True, f"Failed to reload configurations: {e}")
        raise


def reload_tentacle_config(tentacle_name):
    try:
        send_command_to_tentacles(commons_enums.UserCommands.RELOAD_CONFIG.value, [tentacle_name])
        return {"success": True}
    except Exception as e:
        _get_logger().exception(e, True, f"Failed to reload {tentacle_name} configuration: {e}")
        raise


def update_config_currencies(currencies: list, replace: bool=False):
    """
    Update the configured currencies list
    :param currencies: currencies list
    :param replace: replace the current list
    :return: bool, str
    """
    success = True
    message = "Currencies list updated"
    try:
        config_currencies = interfaces_util.get_edited_config()[commons_constants.CONFIG_CRYPTO_CURRENCIES]
        config_currencies = currencies if replace else \
            configuration.merge_dictionaries_by_appending_keys(config_currencies, currencies, merge_sub_array=True)
        interfaces_util.get_edited_config(dict_only=False).save()
    except Exception as e:
        message = f"Error while updating currencies list: {e}"
        success = False
        bot_logging.get_logger("ConfigurationWebInterfaceModel").exception(e, False)
    return success, message


def get_config_required_candles_count(exchange_manager):
    return trading_api.get_required_historical_candles_count(exchange_manager)
