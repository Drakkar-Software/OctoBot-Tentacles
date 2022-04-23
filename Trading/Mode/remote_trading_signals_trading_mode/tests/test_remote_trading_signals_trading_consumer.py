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
import decimal
import pytest
import mock

import octobot_trading.enums as trading_enums
import octobot_trading.errors as errors
import octobot_trading.signals as trading_signals
import octobot_trading.personal_data as trading_personal_data
import octobot_services.api as services_api

from tentacles.Trading.Mode.remote_trading_signals_trading_mode.tests import exchange, mocked_signal


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def test_internal_callback(exchange, mocked_signal):
    _, consumer, _ = exchange
    consumer.logger = mock.Mock(info=mock.Mock(), exception=mock.Mock())
    with mock.patch.object(consumer, "_handle_signal_orders", new=mock.AsyncMock()) \
         as _handle_signal_orders_mock:
        await consumer.internal_callback("trading_mode_name", "cryptocurrency", "symbol", "time_frame", "final_note",
                                         "state", "data")
        _handle_signal_orders_mock.assert_called_once_with("data")
        consumer.logger.info.assert_not_called()
        consumer.logger.exception.assert_not_called()

    with mock.patch.object(consumer, "_handle_signal_orders",
                           new=mock.AsyncMock(side_effect=errors.MissingMinimalExchangeTradeVolume)) \
         as _handle_signal_orders_mock:
        await consumer.internal_callback("trading_mode_name", "cryptocurrency", "symbol", "time_frame", "final_note",
                                         "state", "data")
        _handle_signal_orders_mock.assert_called_once_with("data")
        consumer.logger.info.assert_called_once()
        consumer.logger.exception.assert_not_called()
        consumer.logger.info.reset_mock()

    with mock.patch.object(consumer, "_handle_signal_orders",
                           new=mock.AsyncMock(side_effect=RuntimeError)) \
         as _handle_signal_orders_mock:
        await consumer.internal_callback("trading_mode_name", "cryptocurrency", "symbol", "time_frame", "final_note",
                                         "state", "data")
        _handle_signal_orders_mock.assert_called_once_with("data")
        consumer.logger.info.assert_not_called()
        consumer.logger.exception.assert_called_once()


async def test_handle_signal_orders(exchange, mocked_signal):
    _, consumer, exchange_manager = exchange
    assert exchange_manager.exchange_personal_data.orders_manager.get_open_orders() == []
    assert consumer.trading_mode.last_signal_description == ""
    await consumer._handle_signal_orders(mocked_signal)
    # ensure orders are created
    orders = exchange_manager.exchange_personal_data.orders_manager.get_open_orders()
    assert len(orders) == 2
    # market order is filled, chained & bundled orders got created
    assert isinstance(orders[0], trading_personal_data.StopLossOrder)
    assert isinstance(orders[0].order_group, trading_personal_data.BalancedTakeProfitAndStopOrderGroup)
    assert orders[0].origin_quantity == decimal.Decimal("0.10713784")
    assert isinstance(orders[1], trading_personal_data.SellLimitOrder)
    assert orders[1].order_group is orders[0].order_group
    trades = list(exchange_manager.exchange_personal_data.trades_manager.trades.values())
    assert len(trades) == 1
    assert trades[0].trade_type, trading_enums.TraderOrderType.BUY_MARKET
    assert trades[0].status is trading_enums.OrderStatus.FILLED
    assert "2" in consumer.trading_mode.last_signal_description

    # disable created order group so that changing their groups doesnt cancel them
    await orders[0].order_group.enable(False)
    # now edit, cancel orders and create a new one
    # change StopLossOrder group and cancel SellLimitOrder
    new_signal = _group_edit_cancel_create_order(
        orders[0].shared_signal_order_id, "new_group_id", trading_personal_data.OneCancelsTheOtherOrderGroup.__name__,
        orders[0].shared_signal_order_id, "3.356892%", 2000,
        orders[1].shared_signal_order_id
    )
    await consumer._handle_signal_orders(new_signal)
    # ensure orders are created
    orders = exchange_manager.exchange_personal_data.orders_manager.get_open_orders()
    assert len(orders) == 2
    # market order is filled, chained & bundled orders got created
    assert isinstance(orders[0], trading_personal_data.StopLossOrder)
    assert isinstance(orders[0].order_group, trading_personal_data.OneCancelsTheOtherOrderGroup)
    assert orders[0].order_group.name == "new_group_id"
    assert orders[0].origin_quantity == decimal.Decimal("0.339282105005844")
    assert orders[0].origin_price == decimal.Decimal("2000")
    assert isinstance(orders[1], trading_personal_data.BuyLimitOrder)
    trades = list(exchange_manager.exchange_personal_data.trades_manager.trades.values())
    assert len(trades) == 2
    assert trades[0].trade_type, trading_enums.TraderOrderType.BUY_MARKET
    assert trades[1].trade_type, trading_enums.TraderOrderType.SellLimitOrder
    assert trades[1].status is trading_enums.OrderStatus.CANCELED
    assert "1" in consumer.trading_mode.last_signal_description


async def test_send_alert_notification(exchange, mocked_signal):
    _, consumer, _ = exchange
    with mock.patch.object(services_api, "send_notification", mock.AsyncMock()) as send_notification_mock:
        await consumer._send_alert_notification("BTC/USDT", 42, 62, 78)
        send_notification_mock.assert_called_once()
        notification = send_notification_mock.mock_calls[0].args[0]
        assert all(str(counter) in notification.text for counter in (42, 62, 78))

        send_notification_mock.reset_mock()
        await consumer._send_alert_notification("BTC/USDT", 0, 0, 99)
        send_notification_mock.assert_called_once()
        notification = send_notification_mock.mock_calls[0].args[0]
        assert "99" in notification.text
        assert "0" not in notification.text


# TODO add more unit hedge case tests when arch is validated


def _group_edit_cancel_create_order(to_group_id, group_id, group_type,
                                    to_edit_id, to_edit_target_amount, to_edit_price,
                                    to_cancel_id):
    orders = [
        {
            trading_enums.TradingSignalOrdersAttrs.ACTION.value:
                trading_enums.TradingSignalOrdersActions.ADD_TO_GROUP.value,
            trading_enums.TradingSignalOrdersAttrs.SIDE.value: trading_enums.TradeOrderSide.SELL.value,
            trading_enums.TradingSignalOrdersAttrs.TYPE.value: trading_enums.TraderOrderType.BUY_LIMIT.value,
            trading_enums.TradingSignalOrdersAttrs.QUANTITY.value: 0.004,
            trading_enums.TradingSignalOrdersAttrs.TARGET_AMOUNT.value: "5.3574085830652285%",
            trading_enums.TradingSignalOrdersAttrs.TARGET_POSITION.value: 0,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_TARGET_AMOUNT.value: 0,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_TARGET_POSITION.value: 0,
            trading_enums.TradingSignalOrdersAttrs.LIMIT_PRICE.value: 800.69,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_LIMIT_PRICE.value: 0,
            trading_enums.TradingSignalOrdersAttrs.STOP_PRICE.value: 0.0,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_STOP_PRICE.value: 0.0,
            trading_enums.TradingSignalOrdersAttrs.CURRENT_PRICE.value: 1000.69,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_CURRENT_PRICE.value: 0.0,
            trading_enums.TradingSignalOrdersAttrs.REDUCE_ONLY.value: True,
            trading_enums.TradingSignalOrdersAttrs.POST_ONLY.value: False,
            trading_enums.TradingSignalOrdersAttrs.GROUP_ID.value: group_id,
            trading_enums.TradingSignalOrdersAttrs.GROUP_TYPE.value: group_type,
            trading_enums.TradingSignalOrdersAttrs.TAG.value: "second wave order",
            trading_enums.TradingSignalOrdersAttrs.SHARED_SIGNAL_ORDER_ID.value: to_group_id,
            trading_enums.TradingSignalOrdersAttrs.BUNDLED_WITH.value: None,
            trading_enums.TradingSignalOrdersAttrs.CHAINED_TO.value: None
        },
        {
            trading_enums.TradingSignalOrdersAttrs.ACTION.value: trading_enums.TradingSignalOrdersActions.EDIT.value,
            trading_enums.TradingSignalOrdersAttrs.SIDE.value: None,
            trading_enums.TradingSignalOrdersAttrs.TYPE.value: None,
            trading_enums.TradingSignalOrdersAttrs.TARGET_AMOUNT.value: 0,
            trading_enums.TradingSignalOrdersAttrs.TARGET_POSITION.value: 0,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_TARGET_AMOUNT.value: to_edit_target_amount,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_TARGET_POSITION.value: 0,
            trading_enums.TradingSignalOrdersAttrs.LIMIT_PRICE.value: None,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_LIMIT_PRICE.value: to_edit_price,
            trading_enums.TradingSignalOrdersAttrs.STOP_PRICE.value: None,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_STOP_PRICE.value: None,
            trading_enums.TradingSignalOrdersAttrs.CURRENT_PRICE.value: None,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_CURRENT_PRICE.value: None,
            trading_enums.TradingSignalOrdersAttrs.REDUCE_ONLY.value: None,
            trading_enums.TradingSignalOrdersAttrs.POST_ONLY.value: None,
            trading_enums.TradingSignalOrdersAttrs.GROUP_ID.value: None,
            trading_enums.TradingSignalOrdersAttrs.GROUP_TYPE.value: None,
            trading_enums.TradingSignalOrdersAttrs.TAG.value: None,
            trading_enums.TradingSignalOrdersAttrs.SHARED_SIGNAL_ORDER_ID.value: to_edit_id,
            trading_enums.TradingSignalOrdersAttrs.BUNDLED_WITH.value: None,
            trading_enums.TradingSignalOrdersAttrs.CHAINED_TO.value: None
        },
        {
            trading_enums.TradingSignalOrdersAttrs.ACTION.value: trading_enums.TradingSignalOrdersActions.CANCEL.value,
            trading_enums.TradingSignalOrdersAttrs.SIDE.value: None,
            trading_enums.TradingSignalOrdersAttrs.TYPE.value: None,
            trading_enums.TradingSignalOrdersAttrs.TARGET_AMOUNT.value: 0,
            trading_enums.TradingSignalOrdersAttrs.TARGET_POSITION.value: 0,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_TARGET_AMOUNT.value: 0,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_TARGET_POSITION.value: 0,
            trading_enums.TradingSignalOrdersAttrs.LIMIT_PRICE.value: None,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_LIMIT_PRICE.value: None,
            trading_enums.TradingSignalOrdersAttrs.STOP_PRICE.value: None,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_STOP_PRICE.value: None,
            trading_enums.TradingSignalOrdersAttrs.CURRENT_PRICE.value: None,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_CURRENT_PRICE.value: None,
            trading_enums.TradingSignalOrdersAttrs.REDUCE_ONLY.value: None,
            trading_enums.TradingSignalOrdersAttrs.POST_ONLY.value: None,
            trading_enums.TradingSignalOrdersAttrs.GROUP_ID.value: None,
            trading_enums.TradingSignalOrdersAttrs.GROUP_TYPE.value: None,
            trading_enums.TradingSignalOrdersAttrs.TAG.value: None,
            trading_enums.TradingSignalOrdersAttrs.SHARED_SIGNAL_ORDER_ID.value: to_cancel_id,
            trading_enums.TradingSignalOrdersAttrs.BUNDLED_WITH.value: None,
            trading_enums.TradingSignalOrdersAttrs.CHAINED_TO.value: None
        },
        {
            trading_enums.TradingSignalOrdersAttrs.ACTION.value: trading_enums.TradingSignalOrdersActions.CREATE.value,
            trading_enums.TradingSignalOrdersAttrs.SIDE.value: trading_enums.TradeOrderSide.SELL.value,
            trading_enums.TradingSignalOrdersAttrs.TYPE.value: trading_enums.TraderOrderType.BUY_LIMIT.value,
            trading_enums.TradingSignalOrdersAttrs.QUANTITY.value: 0.004,
            trading_enums.TradingSignalOrdersAttrs.TARGET_AMOUNT.value: "5.3574085830652285%",
            trading_enums.TradingSignalOrdersAttrs.TARGET_POSITION.value: 0,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_TARGET_AMOUNT.value: 0,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_TARGET_POSITION.value: 0,
            trading_enums.TradingSignalOrdersAttrs.LIMIT_PRICE.value: 800.69,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_LIMIT_PRICE.value: 0.0,
            trading_enums.TradingSignalOrdersAttrs.STOP_PRICE.value: 0.0,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_STOP_PRICE.value: 0.0,
            trading_enums.TradingSignalOrdersAttrs.CURRENT_PRICE.value: 1000.69,
            trading_enums.TradingSignalOrdersAttrs.UPDATED_CURRENT_PRICE.value: 0.0,
            trading_enums.TradingSignalOrdersAttrs.REDUCE_ONLY.value: True,
            trading_enums.TradingSignalOrdersAttrs.POST_ONLY.value: False,
            trading_enums.TradingSignalOrdersAttrs.GROUP_ID.value: None,
            trading_enums.TradingSignalOrdersAttrs.GROUP_TYPE.value: None,
            trading_enums.TradingSignalOrdersAttrs.TAG.value: "second wave order",
            trading_enums.TradingSignalOrdersAttrs.SHARED_SIGNAL_ORDER_ID.value: "aaaa-f970-45d9-9ba8-f63da17f17ba",
            trading_enums.TradingSignalOrdersAttrs.BUNDLED_WITH.value: None,
            trading_enums.TradingSignalOrdersAttrs.CHAINED_TO.value: None
        }
    ]
    return trading_signals.TradingSignal("moonmoon", "bybit", "spot", "BTC/USDT",
                                         None, None, orders, identifier="identifier",
                                         version="version")
