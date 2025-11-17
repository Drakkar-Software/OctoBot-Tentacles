#  Drakkar-Software OctoBot-Commons
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

import numpy as np


from tentacles.Meta.DSL_operators.exchange_operators.tests import (
    historical_prices,
    historical_volume,
    exchange_manager_with_candles,
    interpreter,
)


@pytest.mark.asyncio
async def test_mocks(interpreter, historical_prices, historical_volume):
    assert np.array_equal(await interpreter.interprete("close"), historical_prices)
    assert await interpreter.interprete("close[-1]") == historical_prices[-1] == 92.22
    assert np.array_equal(await interpreter.interprete("volume"), historical_volume)
    assert await interpreter.interprete("volume[-1]") == historical_volume[-1] == 1113
