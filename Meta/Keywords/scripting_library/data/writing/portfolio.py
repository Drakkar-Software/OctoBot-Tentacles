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
import octobot_trading.errors as trading_errors
import octobot_trading.modes.script_keywords as script_keywords
import tentacles.Meta.Keywords.scripting_library.data.reading.exchange_private_data as exchange_private_data


async def withdraw(context, amount, currency):
    if not context.exchange_manager.is_backtesting:
        raise RuntimeError("withdraw is only supported in backtesting")
    amount_type, amount_value = script_keywords.parse_quantity(amount)

    if amount_type is script_keywords.QuantityType.UNKNOWN or amount_value <= 0:
        raise trading_errors.InvalidArgumentError("amount cant be zero or negative")
    if amount_type is script_keywords.QuantityType.DELTA:
        # nothing to do
        pass
    elif amount_type is script_keywords.QuantityType.PERCENT:
        amount_value = script_keywords.account_holdings(context, currency) * amount_value / 100
    else:
        raise trading_errors.InvalidArgumentError("make sure to use a supported syntax for amount")
    await context.trader.withdraw(amount_value, currency)
