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

import octobot_commons.symbols.symbol_util as symbol_util
import octobot_commons.constants as commons_constants
import octobot_trading.personal_data as personal_data
import octobot_trading.constants as trading_constants
import octobot_trading.enums as trading_enums
import tentacles.Meta.Keywords.scripting_library.data.reading.exchange_public_data as exchange_public_data
import tentacles.Meta.Keywords.scripting_library.orders.offsets.offset as offsets
import tentacles.Meta.Keywords.scripting_library.orders.position_size.amount as amounts


def is_current_contract_inverse(context, symbol=None, side=trading_enums.PositionSide.BOTH.value):
    return get_position(context, symbol=symbol, side=side).symbol_contract.is_inverse_contract()


def get_position(context, symbol=None, side=trading_enums.PositionSide.BOTH.value):
    return context.exchange_manager.exchange_personal_data.positions_manager.get_symbol_position(
        symbol or context.symbol,
        _get_position_side(context, side)
    )


# returns negative values when in a short position
def open_position_size(
        context,
        side=trading_enums.PositionSide.BOTH.value,
        symbol=None,
        amount_type=commons_constants.PORTFOLIO_TOTAL
):
    symbol = symbol or context.symbol
    if context.exchange_manager.is_future:
        return get_position(context, symbol, side).size
    currency = symbol_util.parse_symbol(context.symbol).base
    portfolio = context.exchange_manager.exchange_personal_data.portfolio_manager.portfolio
    return portfolio.get_currency_portfolio(currency).total if amount_type == commons_constants.PORTFOLIO_TOTAL \
        else portfolio.get_currency_portfolio(currency).available
    # todo handle reference market change
    # todo handle futures: its account balance from exchange
    # todo handle futures and return negative for shorts


async def average_open_pos_entry(
        context,
        side="long"
):
    if context.exchange_manager.is_future:
        return get_position(context, context.symbol, side).entry_price
    elif context.exchange_manager.is_margin:
        return trading_constants.ZERO
    else:
        return trading_constants.ZERO

    # for spot just get the current currency value
    # todo for spot: collect data to get average entry and use input field for already existing funds
    # TODO: get real average entry price (for now position entry price is giving a different result)


def _get_position_side(ctx, side):
    if is_in_one_way_position_mode(ctx):
        return trading_enums.PositionSide.BOTH

    # hedge mode
    # todo solve side buy sell from orders
    if side == "long":
        return trading_enums.PositionSide.LONG
    elif side == "short":
        return trading_enums.PositionSide.SHORT
    elif side == "both":
        raise RuntimeError("average_open_pos_entry: both sides are not implemented yet for hedged mode")
    else:
        raise RuntimeError('average_open_pos_entry: side needs to be "long", "short" or "both"')


def is_in_one_way_position_mode(ctx):
    return ctx.exchange_manager.exchange.get_pair_future_contract(ctx.symbol).is_one_way_position_mode()


def is_position_open(
        context,
        side=None
):
    if side is None:
        long_open = open_position_size(context, side="long") != trading_constants.ZERO
        short_open = open_position_size(context, side="short") != trading_constants.ZERO
        return True if long_open or short_open else False
    else:
        return open_position_size(context, side=side) != trading_constants.ZERO


def is_position_long(
        context,
):
    return get_position(context).is_long()


def is_position_short(
        context,
):
    return get_position(context).is_short()
