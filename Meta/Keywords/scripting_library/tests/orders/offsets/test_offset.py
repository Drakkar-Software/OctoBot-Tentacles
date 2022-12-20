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

import octobot_trading.modes.script_keywords as script_keywords
import tentacles.Meta.Keywords.scripting_library.orders.offsets.offset as offset
import tentacles.Meta.Keywords.scripting_library.data.reading.exchange_public_data as exchange_public_data
import tentacles.Meta.Keywords.scripting_library.data.reading.exchange_private_data.open_positions as open_positions
import octobot_trading.errors as errors


from tentacles.Meta.Keywords.scripting_library.tests import event_loop, null_context

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def test_get_offset(null_context):
    with pytest.raises(errors.InvalidArgumentError):
        await offset.get_offset(null_context, "1sdsqdq")

    with mock.patch.object(exchange_public_data, "current_live_price", mock.AsyncMock(return_value=200)) \
            as current_price_mock:
        with mock.patch.object(script_keywords, "parse_quantity",
                               mock.Mock(return_value=(script_keywords.QuantityType.DELTA, decimal.Decimal(10)))) \
                as parse_quantity_mock:
            assert await offset.get_offset(null_context, 10) == decimal.Decimal(210)
            current_price_mock.assert_called_once_with(null_context)
            parse_quantity_mock.assert_called_once_with(10)
            current_price_mock.reset_mock()

        with mock.patch.object(script_keywords, "parse_quantity",
                               mock.Mock(return_value=(script_keywords.QuantityType.PERCENT, decimal.Decimal(-99)))):
            assert await offset.get_offset(null_context, 10) == decimal.Decimal(2)

        with mock.patch.object(script_keywords, "parse_quantity",
                               mock.Mock(return_value=(script_keywords.QuantityType.PERCENT, decimal.Decimal(1000)))):
            assert await offset.get_offset(null_context, 10) == decimal.Decimal(2200)

    with mock.patch.object(open_positions, "average_open_pos_entry", mock.AsyncMock(return_value=500)) \
            as average_open_pos_entry_mock:
        with mock.patch.object(script_keywords, "parse_quantity",
                               mock.Mock(return_value=(script_keywords.QuantityType.ENTRY_PERCENT, decimal.Decimal(-50)))):
            assert await offset.get_offset(null_context, 10, "sell") == decimal.Decimal(250)
            average_open_pos_entry_mock.assert_called_once_with(null_context, "sell")

    with mock.patch.object(open_positions, "average_open_pos_entry", mock.AsyncMock(return_value=500)) \
            as average_open_pos_entry_mock:
        with mock.patch.object(script_keywords, "parse_quantity",
                               mock.Mock(return_value=(script_keywords.QuantityType.ENTRY, decimal.Decimal(50)))):
            assert await offset.get_offset(null_context, 10, "sell") == decimal.Decimal(550)
            average_open_pos_entry_mock.assert_called_once()

    with mock.patch.object(script_keywords, "parse_quantity",
                           mock.Mock(return_value=(script_keywords.QuantityType.FLAT, decimal.Decimal(50)))):
        assert await offset.get_offset(null_context, 10) == decimal.Decimal(50)

    with mock.patch.object(script_keywords, "parse_quantity",
                           mock.Mock(return_value=(script_keywords.QuantityType.FLAT, decimal.Decimal(-50)))):
        with pytest.raises(errors.InvalidArgumentError):
            await offset.get_offset(null_context, 10)

    with mock.patch.object(script_keywords, "parse_quantity",
                           mock.Mock(return_value=(script_keywords.QuantityType.UNKNOWN, decimal.Decimal(-50)))):
        with pytest.raises(errors.InvalidArgumentError):
            await offset.get_offset(null_context, 10)

