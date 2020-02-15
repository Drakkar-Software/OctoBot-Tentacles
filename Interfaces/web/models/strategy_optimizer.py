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

import threading

from backtesting.strategy_optimizer.strategy_optimizer import StrategyOptimizer

from octobot_backtesting.api.backtesting import is_independent_backtesting_in_progress, create_independent_backtesting
from octobot_evaluators.api.inspection import get_relevant_TAs_for_strategy
from octobot_interfaces.util.bot import get_bot_api, get_global_config
from octobot_commons.tentacles_management.advanced_manager import create_advanced_types_list
from octobot_evaluators.evaluator.strategy_evaluator import StrategyEvaluator
from octobot_interfaces.util.util import run_in_bot_main_loop
from tentacles.Evaluator import Strategies
from octobot_commons.tentacles_management.class_inspector import get_class_from_string, evaluator_parent_inspection
from octobot_commons.time_frame_manager import parse_time_frames
from tentacles.Interfaces import WebInterface
from tentacles.Interfaces.web.constants import BOT_TOOLS_STRATEGY_OPTIMIZER, BOT_TOOLS_BACKTESTING


def get_strategies_list():
    try:
        classes = create_advanced_types_list(StrategyEvaluator, get_global_config())
        return set(strategy.get_name() for strategy in classes)
    except Exception:
        return []


def get_time_frames_list(strategy_name):
    if strategy_name:
        strategy_class = get_class_from_string(strategy_name, StrategyEvaluator,
                                               Strategies, evaluator_parent_inspection)
        return [tf.value for tf in strategy_class.get_required_time_frames(get_global_config())]
    else:
        return []


def get_evaluators_list(strategy_name):
    if strategy_name:
        strategy_class = get_class_from_string(strategy_name, StrategyEvaluator,
                                               Strategies, evaluator_parent_inspection)
        evaluators = get_relevant_TAs_for_strategy(strategy_class, get_global_config())
        return set(evaluator.get_name() for evaluator in evaluators)
    else:
        return []


def get_risks_list():
    return [i/10 for i in range(10, 0, -1)]


def get_current_strategy():
    try:
        first_symbol_evaluator = next(iter(get_bot_api().get_symbol_evaluator_list().values()))
        first_exchange = next(iter(get_bot_api().get_exchanges_list().values()))
        return first_symbol_evaluator.get_strategies_eval_list(first_exchange)[0].get_name()
    except Exception:
        strategy_list = get_strategies_list()
        return next(iter(strategy_list)) if strategy_list else ""


def start_optimizer(strategy, time_frames, evaluators, risks):
    tools = WebInterface.tools
    independent_backtesting = tools[BOT_TOOLS_STRATEGY_OPTIMIZER]
    if independent_backtesting is not None and independent_backtesting.get_is_computing():
        return False, "Optimizer already running"
    independent_backtesting = tools[BOT_TOOLS_BACKTESTING]
    if independent_backtesting and is_independent_backtesting_in_progress(independent_backtesting):
        return False, "A backtesting is already running"
    else:
        formatted_time_frames = parse_time_frames(time_frames)
        float_risks = [float(risk) for risk in risks]
        temp_independent_backtesting = create_independent_backtesting(get_global_config(),  [])
        optimizer_config = run_in_bot_main_loop(temp_independent_backtesting.initialize_config())
        optimizer = StrategyOptimizer(optimizer_config, strategy)
        tools[BOT_TOOLS_STRATEGY_OPTIMIZER] = optimizer
        thread = threading.Thread(target=optimizer.find_optimal_configuration,
                                  args=(evaluators, formatted_time_frames, float_risks),
                                  name=f"{optimizer.get_name()}-WebInterface-runner")
        thread.start()
        return True, "Optimizer started"


def get_optimizer_results():
    optimizer = WebInterface.tools[BOT_TOOLS_STRATEGY_OPTIMIZER]
    if optimizer:
        results = optimizer.get_results()
        return [result.get_result_dict(i) for i, result in enumerate(results)]
    else:
        return []


def get_optimizer_report():
    if get_optimizer_status()[0] == "finished":
        optimizer = WebInterface.tools[BOT_TOOLS_STRATEGY_OPTIMIZER]
        return optimizer.get_report()
    else:
        return []


def get_current_run_params():
    params = {
        "strategy_name": [],
        "time_frames": [],
        "evaluators": [],
        "risks": [],
        "trading_mode": []
    }
    if WebInterface.tools[BOT_TOOLS_STRATEGY_OPTIMIZER]:
        optimizer = WebInterface.tools[BOT_TOOLS_STRATEGY_OPTIMIZER]
        params = {
            "strategy_name": [optimizer.strategy_class.get_name()],
            "time_frames": [tf.value for tf in optimizer.all_time_frames],
            "evaluators": optimizer.all_TAs,
            "risks": optimizer.risks,
            "trading_mode": [optimizer.trading_mode]
        }
    return params


def get_trading_mode():
    return get_bot_api().get_trading_mode().get_name()


def get_optimizer_status():
    optimizer = WebInterface.tools[BOT_TOOLS_STRATEGY_OPTIMIZER]
    if optimizer:
        if optimizer.get_is_computing():
            return "computing", optimizer.get_current_test_suite_progress(), optimizer.get_overall_progress(), \
                   optimizer.get_errors_description()
        else:
            return "finished", 100, 100, optimizer.get_errors_description()
    else:
        return "not started", 0, 0, None
