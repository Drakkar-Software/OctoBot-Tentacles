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
import decimal

import tentacles.Meta.Keywords.scripting_library.data.reading.exchange_public_data as exchange_public_data
import tentacles.Meta.Keywords.scripting_library.data.reading.exchange_private_data.open_positions as open_positions
import octobot_trading.modes.script_keywords as script_keywords
import octobot_trading.errors as errors


async def get_offset(context, offset_in, side=None):
    if offset_in is None:
        raise errors.InvalidArgumentError("offset is required")
    offset_type, offset_value = script_keywords.parse_quantity(offset_in)

    if offset_type is script_keywords.QuantityType.DELTA:
        current_price_val = decimal.Decimal(await exchange_public_data.current_live_price(context))
        return current_price_val + offset_value  # offset should be negative when wanting to buy bellow current price

    elif offset_type is script_keywords.QuantityType.PERCENT:
        current_price_val = decimal.Decimal(await exchange_public_data.current_live_price(context))
        return current_price_val * (1 + (offset_value / 100))

    elif offset_type is script_keywords.QuantityType.ENTRY_PERCENT:
        average_open_pos_entry_val = await open_positions.average_open_pos_entry(context, side)
        return average_open_pos_entry_val * (1 + (offset_value / 100))

    elif offset_type is script_keywords.QuantityType.ENTRY:
        average_open_pos_entry_val = await open_positions.average_open_pos_entry(context, side)
        return average_open_pos_entry_val + offset_value

    elif offset_type is script_keywords.QuantityType.FLAT:
        if offset_value < 0:
            raise errors.InvalidArgumentError("Flat offsets should be a positive price. Ex: @10")
        return offset_value

    raise errors.InvalidArgumentError("make sure to use a supported syntax for offset, "
                                      "supported parameters are: @65100 5% e5% e500")

