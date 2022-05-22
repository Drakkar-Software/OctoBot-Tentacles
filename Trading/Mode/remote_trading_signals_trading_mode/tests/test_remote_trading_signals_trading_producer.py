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
import mock

import octobot_commons.constants as common_constants
import octobot_trading.enums as trading_enums
from tentacles.Trading.Mode.remote_trading_signals_trading_mode.tests import local_trader, mocked_signal


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def test_signal_callback(local_trader, mocked_signal):
    producer, _, _ = local_trader
    with mock.patch.object(producer, "submit_trading_evaluation", new=mock.AsyncMock()) \
         as submit_trading_evaluation_mock:
        await producer.signal_callback(mocked_signal)
        submit_trading_evaluation_mock.assert_called_once_with(
            cryptocurrency=producer.trading_mode.cryptocurrency,
            symbol=mocked_signal.symbol,
            time_frame=None,
            final_note=common_constants.INIT_EVAL_NOTE,
            state=trading_enums.EvaluatorStates(mocked_signal.state),
            data=mocked_signal
        )

        submit_trading_evaluation_mock.reset_mock()
        # with incompatible exchange type
        mocked_signal.exchange_type = trading_enums.ExchangeTypes.MARGIN.value
        await producer.signal_callback(mocked_signal)
        submit_trading_evaluation_mock.assert_not_called()

        # with invalid state
        mocked_signal.exchange_type = trading_enums.ExchangeTypes.SPOT.value
        mocked_signal.state = "123"
        with pytest.raises(ValueError):
            await producer.signal_callback(mocked_signal)
        submit_trading_evaluation_mock.assert_not_called()
