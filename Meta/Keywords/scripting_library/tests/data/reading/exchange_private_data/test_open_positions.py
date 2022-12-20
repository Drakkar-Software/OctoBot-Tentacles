#  Drakkar-Software OctoBot-Trading
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
import decimal

import octobot_trading.personal_data as trading_personal_data
import tentacles.Meta.Keywords.scripting_library.data.reading.exchange_private_data.open_positions as open_positions
import octobot_trading.enums as trading_enums
import octobot_trading.constants as trading_constants

from tentacles.Meta.Keywords.scripting_library.tests import event_loop, mock_context
from tentacles.Meta.Keywords.scripting_library.tests.exchanges import backtesting_trader, \
    backtesting_config, backtesting_exchange_manager, fake_backtesting


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def test_open_position_size(mock_context):
    mock_context.exchange_manager.is_future = False
    # init portfolio with 0.5 BTC, 20 ETH and 30000 USDT and only 0.1 available BTC
    mock_context.symbol = "ETH/USDT"
    assert open_positions.open_position_size(mock_context, trading_enums.TradeOrderSide.BUY.value) == \
           decimal.Decimal("20")
    mock_context.symbol = "BTC/USDT"
    assert open_positions.open_position_size(mock_context, trading_enums.TradeOrderSide.BUY.value) == \
           decimal.Decimal("0.5")

    # TODO future tests


@pytest.mark.parametrize("backtesting_config", ["USDT"], indirect=["backtesting_config"])
async def test_average_open_pos_entry(mock_context):
    mock_context.exchange_manager.is_future = False
    with mock.patch.object(open_positions, "get_position",
                           mock.Mock(return_value=(mock.Mock(entry_price=decimal.Decimal("40000"))))) \
         as get_position_mock:
        mock_context.symbol = "ETH/USDT"
        assert await open_positions.average_open_pos_entry(mock_context, trading_enums.TradeOrderSide.BUY.value) == \
               trading_constants.ZERO
        mock_context.exchange_manager.is_future = True
        mock_context.symbol = "ETH/USDT"
        assert await open_positions.average_open_pos_entry(mock_context, trading_enums.TradeOrderSide.BUY.value) == \
               decimal.Decimal("40000")
        get_position_mock.assert_called_once_with(mock_context, "ETH/USDT", trading_enums.TradeOrderSide.BUY.value)
        get_position_mock.reset_mock()
        mock_context.symbol = "BTC/USDT"
        assert await open_positions.average_open_pos_entry(mock_context, trading_enums.TradeOrderSide.BUY.value) == \
               decimal.Decimal("40000")
        get_position_mock.assert_called_once_with(mock_context, "BTC/USDT", trading_enums.TradeOrderSide.BUY.value)


async def test_is_position_open(mock_context):
    with mock.patch.object(open_positions, "open_position_size",
                           mock.Mock(return_value=decimal.Decimal("40000"))) as open_position_size_mock:
        assert open_positions.is_position_open(mock_context, side="side") is True
        open_position_size_mock.assert_called_once_with(mock_context, side="side")
    with mock.patch.object(open_positions, "open_position_size",
                           mock.Mock(return_value=decimal.Decimal("-40000"))) as open_position_size_mock:
        assert open_positions.is_position_open(mock_context, side="side") is True
        open_position_size_mock.assert_called_once_with(mock_context, side="side")
    with mock.patch.object(open_positions, "open_position_size",
                           mock.Mock(return_value=decimal.Decimal("0"))) as open_position_size_mock:
        assert open_positions.is_position_open(mock_context, side="side") is False
        open_position_size_mock.assert_called_once_with(mock_context, side="side")
