#  Drakkar-Software OctoBot-Tentacles
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
import pytest

from octobot_commons.tests.test_config import load_test_config
from octobot_tentacles_manager.api.configurator import create_tentacles_setup_config_with_tentacles
from tests.test_utils.memory_check_util import run_independent_backtestings_with_memory_check
from tentacles.Evaluator.Strategies import SimpleStrategyEvaluator
from tentacles.Evaluator.TA import RSIMomentumEvaluator, DoubleMovingAverageTrendEvaluator
from tentacles.Trading.Mode import DailyTradingMode


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def test_run_independent_backtestings_with_memory_check():
    tentacles_setup_config = create_tentacles_setup_config_with_tentacles(DailyTradingMode,
                                                                          SimpleStrategyEvaluator,
                                                                          RSIMomentumEvaluator,
                                                                          DoubleMovingAverageTrendEvaluator)
    await run_independent_backtestings_with_memory_check(load_test_config(), tentacles_setup_config)
