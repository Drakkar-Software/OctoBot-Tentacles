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
import math

import mock
import pytest
import os.path
import pytest_asyncio

import async_channel.util as channel_util
import octobot_backtesting.api as backtesting_api
import octobot_commons.asyncio_tools as asyncio_tools
import octobot_commons.constants as commons_constants
import octobot_commons.symbols as commons_symbols
import octobot_commons.tests.test_config as test_config
import octobot_trading.constants as trading_constants
import octobot_trading.api as trading_api
import octobot_trading.exchange_channel as exchanges_channel
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges
import octobot_trading.errors as errors
import octobot_trading.personal_data as trading_personal_data
import octobot_trading.signals as trading_signals
import octobot_trading.modes.script_keywords as script_keywords
import tentacles.Trading.Mode as Mode
import tests.test_utils.config as test_utils_config
import tests.test_utils.test_exchanges as test_exchanges
import octobot_tentacles_manager.api as tentacles_manager_api


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def tools():
    tentacles_manager_api.reload_tentacle_info()
    exchange_manager = None
    try:
        symbol = "BTC/USDT"
        config = test_config.load_test_config()
        config[commons_constants.CONFIG_SIMULATOR][commons_constants.CONFIG_STARTING_PORTFOLIO]["USDT"] = 2000
        exchange_manager = test_exchanges.get_test_exchange_manager(config, "binance")
        exchange_manager.tentacles_setup_config = test_utils_config.get_tentacles_setup_config()

        # use backtesting not to spam exchanges apis
        exchange_manager.is_simulated = True
        exchange_manager.is_backtesting = True
        exchange_manager.use_cached_markets = False
        backtesting = await backtesting_api.initialize_backtesting(
            config,
            exchange_ids=[exchange_manager.id],
            matrix_id=None,
            data_files=[
                os.path.join(test_config.TEST_CONFIG_FOLDER, "AbstractExchangeHistoryCollector_1586017993.616272.data")
            ])
        exchange_manager.exchange = exchanges.ExchangeSimulator(exchange_manager.config,
                                                                exchange_manager,
                                                                backtesting)
        await exchange_manager.exchange.initialize()
        for exchange_channel_class_type in [exchanges_channel.ExchangeChannel, exchanges_channel.TimeFrameExchangeChannel]:
            await channel_util.create_all_subclasses_channel(exchange_channel_class_type, exchanges_channel.set_chan,
                                                             exchange_manager=exchange_manager)

        trader = exchanges.TraderSimulator(config, exchange_manager)
        await trader.initialize()

        mode = Mode.TradingViewSignalsTradingMode(config, exchange_manager)
        mode.symbol = symbol
        await mode.initialize()
        # add mode to exchange manager so that it can be stopped and freed from memory
        exchange_manager.trading_modes.append(mode)
        producer = mode.producers[0]
        consumer = mode.get_trading_mode_consumers()[0]

        # set BTC/USDT price at 7009.194999999998 USDT
        last_btc_price = 7009.194999999998
        trading_api.force_set_mark_price(exchange_manager, symbol, last_btc_price)
        exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder.portfolio_current_value = \
            decimal.Decimal(str(last_btc_price * 10))

        yield exchange_manager, symbol, mode, producer, consumer
    finally:
        if exchange_manager:
            try:
                await _stop(exchange_manager)
            except Exception as err:
                print(f"error when stopping exchange manager: {err}")


async def _stop(exchange_manager):
    for importer in backtesting_api.get_importers(exchange_manager.exchange.backtesting):
        await backtesting_api.stop_importer(importer)
    await exchange_manager.exchange.backtesting.stop()
    await exchange_manager.stop()
    # let updaters gracefully shutdown
    await asyncio_tools.wait_asyncio_next_cycle()


async def test_parse_signal_data():
    errors = []
    assert Mode.TradingViewSignalsTradingMode.parse_signal_data(
        """
        
        
        KEY=value
        EXCHANGE=1
        
        
        
        PLOp=true
        """,
        errors
    ) == {
        "KEY": "value",
        "EXCHANGE": "1",
        "PLOp": True,
    }
    assert errors == []

    errors = []
    assert Mode.TradingViewSignalsTradingMode.parse_signal_data(
        "KEY=value\nEXCHANGE=1\n\n\n\nPLOp=false\n",
        errors
    ) == {
        "KEY": "value",
        "EXCHANGE": "1",
        "PLOp": False,
    }
    assert errors == []

    errors = []
    assert Mode.TradingViewSignalsTradingMode.parse_signal_data(
        "KEY=value\\nEXCHANGE=1\\nPLOp=ABC",
        errors
    ) == {
        "KEY": "value",
        "EXCHANGE": "1",
        "PLOp": "ABC",
    }
    assert errors == []

    errors = []
    assert Mode.TradingViewSignalsTradingMode.parse_signal_data(
        "KEY=value\\nEXCHANGE\\nPLOp=ABC",
        errors
    ) == {
        "KEY": "value",
        "PLOp": "ABC",
    }
    assert len(errors) == 1
    assert "EXCHANGE" in str(errors[0])
    assert "nPLOp" not in str(errors[0])
    assert "KEY" not in str(errors[0])

    errors = []
    assert Mode.TradingViewSignalsTradingMode.parse_signal_data(
        "KEY=value;EXCHANGE;;;;;PLOp=ABC;TAKE_PROFIT_PRICE=1;;TAKE_PROFIT_PRICE_2=3",
        errors
    ) == {
        "KEY": "value",
        "PLOp": "ABC",
        "TAKE_PROFIT_PRICE": "1",
        "TAKE_PROFIT_PRICE_2": "3",
    }
    assert len(errors) == 1
    assert "EXCHANGE" in str(errors[0])
    assert "nPLOp" not in str(errors[0])
    assert "KEY" not in str(errors[0])

    errors = []
    assert Mode.TradingViewSignalsTradingMode.parse_signal_data(
        ";KEY=value;EXCHANGE\nPLOp=ABC\\nGG=HIHI;LEVERAGE=3",
        errors
    ) == {
        "KEY": "value",
        "PLOp": "ABC",
        "GG": "HIHI",
        "LEVERAGE": "3",
    }
    assert len(errors) == 1
    assert "EXCHANGE" in str(errors[0])
    assert "nPLOp" not in str(errors[0])
    assert "KEY" not in str(errors[0])
    assert "LEVERAGE" not in str(errors[0])


async def test_trading_view_signal_callback(tools):
    exchange_manager, symbol, mode, producer, consumer = tools
    context = script_keywords.get_base_context(producer.trading_mode)
    with mock.patch.object(script_keywords, "get_base_context", mock.Mock(return_value=context)) \
         as get_base_context_mock:
        for exception in (errors.MissingFunds, errors.InvalidArgumentError):
            # ensure exception is caught
            with mock.patch.object(
                    producer, "signal_callback", mock.AsyncMock(side_effect=exception)
            ) as signal_callback_mock:
                signal = f"""
                    EXCHANGE={exchange_manager.exchange_name}
                    SYMBOL={symbol}
                    SIGNAL=BUY
                """
                await mode._trading_view_signal_callback({"metadata": signal})
                signal_callback_mock.assert_awaited_once()
                get_base_context_mock.assert_called_once()
                get_base_context_mock.reset_mock()

        with mock.patch.object(producer, "signal_callback", mock.AsyncMock()) as signal_callback_mock:
            # invalid data
            data = ""
            await mode._trading_view_signal_callback({"metadata": data})
            signal_callback_mock.assert_not_awaited()
            signal_callback_mock.reset_mock()
            get_base_context_mock.assert_not_called()

            # invalid symbol
            data = f"""
            EXCHANGE={exchange_manager.exchange_name}
            SYMBOL={symbol}PLOP
            SIGNAL=BUY
            """
            await mode._trading_view_signal_callback({"metadata": data})
            signal_callback_mock.assert_not_awaited()
            signal_callback_mock.reset_mock()
            get_base_context_mock.assert_not_called()

            # minimal signal
            data = f"""
            EXCHANGE={exchange_manager.exchange_name}
            SYMBOL={symbol}
            SIGNAL=BUY
            """
            await mode._trading_view_signal_callback({"metadata": data})
            signal_callback_mock.assert_awaited_once_with({
                mode.EXCHANGE_KEY: exchange_manager.exchange_name,
                mode.SYMBOL_KEY: symbol,
                mode.SIGNAL_KEY: "BUY",
            }, context)
            signal_callback_mock.reset_mock()
            get_base_context_mock.assert_called_once()
            get_base_context_mock.reset_mock()

            # minimal signal
            signal = f"""
                EXCHANGE={exchange_manager.exchange_name}
                SYMBOL={symbol}
                SIGNAL=BUY
            """
            await mode._trading_view_signal_callback({"metadata": signal})
            signal_callback_mock.assert_awaited_once_with({
                mode.EXCHANGE_KEY: exchange_manager.exchange_name,
                mode.SYMBOL_KEY: symbol,
                mode.SIGNAL_KEY: "BUY",
            }, context)
            signal_callback_mock.reset_mock()
            get_base_context_mock.assert_called_once()
            get_base_context_mock.reset_mock()

            # other signals
            signal = f"""
                EXCHANGE={exchange_manager.exchange_name}
                SYMBOL={commons_symbols.parse_symbol(symbol).merged_str_base_and_quote_only_symbol(
                market_separator=""
            )}
                SIGNAL=BUY
                HEELLO=True
                PLOP=faLse
            """
            await mode._trading_view_signal_callback({"metadata": signal})
            signal_callback_mock.assert_awaited_once_with({
                mode.EXCHANGE_KEY: exchange_manager.exchange_name,
                mode.SYMBOL_KEY: commons_symbols.parse_symbol(symbol).merged_str_base_and_quote_only_symbol(
                    market_separator=""
                ),
                mode.SIGNAL_KEY: "BUY",
                "HEELLO": True,
                "PLOP": False,
            }, context)
            signal_callback_mock.reset_mock()
            get_base_context_mock.assert_called_once()
            get_base_context_mock.reset_mock()


async def test_signal_callback(tools):
    exchange_manager, symbol, mode, producer, consumer = tools
    context = script_keywords.get_base_context(producer.trading_mode)
    with mock.patch.object(producer, "_set_state", mock.AsyncMock()) as _set_state_mock, \
        mock.patch.object(mode, "set_leverage", mock.AsyncMock()) as set_leverage_mock:
        await producer.signal_callback({
            mode.EXCHANGE_KEY: exchange_manager.exchange_name,
            mode.SYMBOL_KEY: "unused",
            mode.SIGNAL_KEY: "BUY",
        }, context)
        _set_state_mock.assert_awaited_once()
        set_leverage_mock.assert_not_called()
        assert _set_state_mock.await_args[0][1] == symbol
        assert _set_state_mock.await_args[0][2] == trading_enums.EvaluatorStates.VERY_LONG
        assert compare_dict_with_nan(_set_state_mock.await_args[0][3], {
            consumer.PRICE_KEY: trading_constants.ZERO,
            consumer.VOLUME_KEY: trading_constants.ZERO,
            consumer.STOP_PRICE_KEY: decimal.Decimal(math.nan),
            consumer.STOP_ONLY: False,
            consumer.TAKE_PROFIT_PRICE_KEY: decimal.Decimal(math.nan),
            consumer.ADDITIONAL_TAKE_PROFIT_PRICES_KEY: [],
            consumer.ADDITIONAL_TAKE_PROFIT_VOLUME_RATIOS_KEY: [],
            consumer.REDUCE_ONLY_KEY: False,
            consumer.TAG_KEY: None,
            consumer.TRAILING_PROFILE: None,
            consumer.EXCHANGE_ORDER_IDS: None,
            consumer.LEVERAGE: None,
            consumer.ORDER_EXCHANGE_CREATION_PARAMS: {},
            consumer.CANCEL_POLICY: None,
            consumer.CANCEL_POLICY_PARAMS: None,
        })
        _set_state_mock.reset_mock()

        await producer.signal_callback({
            mode.EXCHANGE_KEY: exchange_manager.exchange_name,
            mode.SYMBOL_KEY: "unused",
            mode.SIGNAL_KEY: "SELL",
            mode.ORDER_TYPE_SIGNAL: "stop",
            mode.STOP_PRICE_KEY: 25000,
            mode.VOLUME_KEY: "12%",
            mode.TAG_KEY: "stop_1_tag",
            mode.CANCEL_POLICY: trading_personal_data.ExpirationTimeOrderCancelPolicy.__name__,
            mode.CANCEL_POLICY_PARAMS: {
                "expiration_time": 1000.0,
            },
            consumer.EXCHANGE_ORDER_IDS: None,

        }, context)
        set_leverage_mock.assert_not_called()
        _set_state_mock.assert_awaited_once()
        assert _set_state_mock.await_args[0][1] == symbol
        assert _set_state_mock.await_args[0][2] == trading_enums.EvaluatorStates.SHORT
        assert compare_dict_with_nan(_set_state_mock.await_args[0][3], {
            consumer.PRICE_KEY: trading_constants.ZERO,
            consumer.VOLUME_KEY: decimal.Decimal("1.2"),
            consumer.STOP_PRICE_KEY: decimal.Decimal("25000"),
            consumer.STOP_ONLY: True,
            consumer.TAKE_PROFIT_PRICE_KEY: decimal.Decimal(math.nan),
            consumer.ADDITIONAL_TAKE_PROFIT_PRICES_KEY: [],
            consumer.ADDITIONAL_TAKE_PROFIT_VOLUME_RATIOS_KEY: [],
            consumer.REDUCE_ONLY_KEY: False,
            consumer.TAG_KEY: "stop_1_tag",
            consumer.EXCHANGE_ORDER_IDS: None,
            consumer.TRAILING_PROFILE: None,
            consumer.LEVERAGE: None,
            consumer.ORDER_EXCHANGE_CREATION_PARAMS: {},
            consumer.CANCEL_POLICY: trading_personal_data.ExpirationTimeOrderCancelPolicy.__name__,
            consumer.CANCEL_POLICY_PARAMS: {'expiration_time': 1000.0},
        })
        _set_state_mock.reset_mock()

        await producer.signal_callback({
            mode.EXCHANGE_KEY: exchange_manager.exchange_name,
            mode.SYMBOL_KEY: "unused",
            mode.SIGNAL_KEY: "SelL",
            mode.PRICE_KEY: "123",
            mode.VOLUME_KEY: "12%",
            mode.REDUCE_ONLY_KEY: True,
            mode.ORDER_TYPE_SIGNAL: "LiMiT",
            mode.STOP_PRICE_KEY: "12",
            mode.TAKE_PROFIT_PRICE_KEY: "22222",
            mode.EXCHANGE_ORDER_IDS: ["ab1", "aaaaa"],
            mode.CANCEL_POLICY: "chainedorderfillingpriceordercancelpolicy",
            consumer.LEVERAGE: 22,
            "PARAM_TAG_1": "ttt",
            "PARAM_Plop": False,
        }, context)
        set_leverage_mock.assert_called_once()
        assert set_leverage_mock.mock_calls[0].args[2] == decimal.Decimal(22)
        set_leverage_mock.reset_mock()
        _set_state_mock.assert_awaited_once()
        assert _set_state_mock.await_args[0][1] == symbol
        assert _set_state_mock.await_args[0][2] == trading_enums.EvaluatorStates.SHORT
        assert compare_dict_with_nan(_set_state_mock.await_args[0][3], {
            consumer.PRICE_KEY: decimal.Decimal("123"),
            consumer.VOLUME_KEY: decimal.Decimal("1.2"),
            consumer.STOP_PRICE_KEY: decimal.Decimal("12"),
            consumer.STOP_ONLY: False,
            consumer.TAKE_PROFIT_PRICE_KEY: decimal.Decimal("22222"),
            consumer.ADDITIONAL_TAKE_PROFIT_PRICES_KEY: [],
            consumer.ADDITIONAL_TAKE_PROFIT_VOLUME_RATIOS_KEY: [],
            consumer.REDUCE_ONLY_KEY: True,
            consumer.TAG_KEY: None,
            mode.EXCHANGE_ORDER_IDS: ["ab1", "aaaaa"],
            consumer.TRAILING_PROFILE: None,
            consumer.LEVERAGE: 22,
            consumer.ORDER_EXCHANGE_CREATION_PARAMS: {
                "TAG_1": "ttt",
                "Plop": False,
            },
            consumer.CANCEL_POLICY: trading_personal_data.ChainedOrderFillingPriceOrderCancelPolicy.__name__,
            consumer.CANCEL_POLICY_PARAMS: None,
        })
        _set_state_mock.reset_mock()

        # with trailing profile and TP volume
        await producer.signal_callback({
            mode.EXCHANGE_KEY: exchange_manager.exchange_name,
            mode.SYMBOL_KEY: "unused",
            mode.SIGNAL_KEY: "SelL",
            mode.PRICE_KEY: "123",
            mode.VOLUME_KEY: "12%",
            mode.REDUCE_ONLY_KEY: True,
            mode.ORDER_TYPE_SIGNAL: "LiMiT",
            mode.STOP_PRICE_KEY: "12",
            mode.TAKE_PROFIT_PRICE_KEY: "22222",
            mode.TAKE_PROFIT_VOLUME_RATIO_KEY: "1",
            mode.EXCHANGE_ORDER_IDS: ["ab1", "aaaaa"],
            mode.TRAILING_PROFILE: "fiLLED_take_profit",
            mode.CANCEL_POLICY: "expirationtimeordercancelpolicy",
            mode.CANCEL_POLICY_PARAMS: "{'expiration_time': 1000.0}",
            consumer.LEVERAGE: 22,
            "PARAM_TAG_1": "ttt",
            "PARAM_Plop": False,
        }, context)
        set_leverage_mock.assert_called_once()
        assert set_leverage_mock.mock_calls[0].args[2] == decimal.Decimal(22)
        set_leverage_mock.reset_mock()
        _set_state_mock.assert_awaited_once()
        assert _set_state_mock.await_args[0][1] == symbol
        assert _set_state_mock.await_args[0][2] == trading_enums.EvaluatorStates.SHORT
        assert compare_dict_with_nan(_set_state_mock.await_args[0][3], {
            consumer.PRICE_KEY: decimal.Decimal("123"),
            consumer.VOLUME_KEY: decimal.Decimal("1.2"),
            consumer.STOP_PRICE_KEY: decimal.Decimal("12"),
            consumer.STOP_ONLY: False,
            consumer.TAKE_PROFIT_PRICE_KEY: decimal.Decimal("22222"),
            consumer.ADDITIONAL_TAKE_PROFIT_PRICES_KEY: [],
            consumer.ADDITIONAL_TAKE_PROFIT_VOLUME_RATIOS_KEY: [decimal.Decimal(1)],
            consumer.REDUCE_ONLY_KEY: True,
            consumer.TAG_KEY: None,
            mode.EXCHANGE_ORDER_IDS: ["ab1", "aaaaa"],
            consumer.LEVERAGE: 22,
            consumer.TRAILING_PROFILE: "filled_take_profit",
            consumer.ORDER_EXCHANGE_CREATION_PARAMS: {
                "TAG_1": "ttt",
                "Plop": False,
            },
            consumer.CANCEL_POLICY: trading_personal_data.ExpirationTimeOrderCancelPolicy.__name__,
            consumer.CANCEL_POLICY_PARAMS: {'expiration_time': 1000.0},
        })
        _set_state_mock.reset_mock()

        # future exchange: call set_leverage
        exchange_manager.is_future = True
        trading_api.load_pair_contract(
            exchange_manager,
            trading_api.create_default_future_contract(
                "BTC/USDT", decimal.Decimal(4), trading_enums.FutureContractType.LINEAR_PERPETUAL,
                trading_constants.DEFAULT_SYMBOL_POSITION_MODE
            ).to_dict()
        )
        await producer.signal_callback({
            mode.EXCHANGE_KEY: exchange_manager.exchange_name,
            mode.SYMBOL_KEY: "unused",
            mode.SIGNAL_KEY: "SelL",
            mode.PRICE_KEY: "123@",  # price = 123
            mode.VOLUME_KEY: "100q",  # base amount
            mode.REDUCE_ONLY_KEY: False,
            mode.ORDER_TYPE_SIGNAL: "LiMiT",
            mode.STOP_PRICE_KEY: "-10%",  # price - 10%
            f"{mode.TAKE_PROFIT_PRICE_KEY}_0": "120.333333333333333d",   # price  + 120.333333333333333
            f"{mode.TAKE_PROFIT_PRICE_KEY}_1": "122.333333333333333d",   # price  + 122.333333333333333
            f"{mode.TAKE_PROFIT_PRICE_KEY}_2": "4444d",   # price  + 4444
            f"{mode.TAKE_PROFIT_VOLUME_RATIO_KEY}_0": "1",
            f"{mode.TAKE_PROFIT_VOLUME_RATIO_KEY}_1": "1.122",
            f"{mode.TAKE_PROFIT_VOLUME_RATIO_KEY}_2": "0.2222",
            mode.EXCHANGE_ORDER_IDS: ["ab1", "aaaaa"],
            consumer.LEVERAGE: 22,
            "PARAM_TAG_1": "ttt",
            "PARAM_Plop": False,
        }, context)
        set_leverage_mock.assert_called_once()
        assert set_leverage_mock.mock_calls[0].args[2] == decimal.Decimal("22")
        _set_state_mock.assert_awaited_once()
        assert _set_state_mock.await_args[0][1] == symbol
        assert _set_state_mock.await_args[0][2] == trading_enums.EvaluatorStates.SHORT
        assert compare_dict_with_nan(_set_state_mock.await_args[0][3], {
            consumer.PRICE_KEY: decimal.Decimal("123"),
            consumer.VOLUME_KEY: decimal.Decimal("0.8130081300813008130081300813"),
            consumer.STOP_PRICE_KEY: decimal.Decimal("6308.27549999"),
            consumer.STOP_ONLY: False,
            consumer.TAKE_PROFIT_PRICE_KEY: decimal.Decimal("nan"), # only additional TP orders are provided
            consumer.ADDITIONAL_TAKE_PROFIT_PRICES_KEY: [
                decimal.Decimal("7129.52833333"), decimal.Decimal("7131.52833333"), decimal.Decimal('11453.19499999')
            ],
            consumer.ADDITIONAL_TAKE_PROFIT_VOLUME_RATIOS_KEY: [
                decimal.Decimal("1"), decimal.Decimal("1.122"), decimal.Decimal("0.2222"),
            ],
            consumer.REDUCE_ONLY_KEY: False,
            consumer.TAG_KEY: None,
            mode.EXCHANGE_ORDER_IDS: ["ab1", "aaaaa"],
            consumer.TRAILING_PROFILE: None,
            consumer.LEVERAGE: 22,
            consumer.ORDER_EXCHANGE_CREATION_PARAMS: {
                "TAG_1": "ttt",
                "Plop": False,
            },
            consumer.CANCEL_POLICY: None,
            consumer.CANCEL_POLICY_PARAMS: None,
        })
        _set_state_mock.reset_mock()
        set_leverage_mock.reset_mock()

        with pytest.raises(errors.MissingFunds):
            await producer.signal_callback({
                mode.EXCHANGE_KEY: exchange_manager.exchange_name,
                mode.SYMBOL_KEY: "unused",
                mode.SIGNAL_KEY: "SelL",
                mode.PRICE_KEY: "123000q",  # price = 123
                mode.VOLUME_KEY: "11111b",  # base amount: not enough funds
                mode.REDUCE_ONLY_KEY: True,
                mode.ORDER_TYPE_SIGNAL: "LiMiT",
                mode.STOP_PRICE_KEY: "-10%",  # price - 10%
                mode.TAKE_PROFIT_PRICE_KEY: "120.333333333333333d",   # price  + 120.333333333333333
                mode.EXCHANGE_ORDER_IDS: ["ab1", "aaaaa"],
                mode.LEVERAGE: None,
                "PARAM_TAG_1": "ttt",
                "PARAM_Plop": False,
            }, context)
        set_leverage_mock.assert_not_called()
        _set_state_mock.assert_not_called()

        with pytest.raises(errors.InvalidArgumentError):
            await producer.signal_callback({
                mode.EXCHANGE_KEY: exchange_manager.exchange_name,
                mode.SYMBOL_KEY: "unused",
                mode.SIGNAL_KEY: "DSDSDDSS",
                mode.PRICE_KEY: "123000q",  # price = 123
                mode.VOLUME_KEY: "11111b",  # base amount: not enough funds
                mode.REDUCE_ONLY_KEY: True,
                mode.ORDER_TYPE_SIGNAL: "LiMiT",
                mode.STOP_PRICE_KEY: "-10%",  # price - 10%
                mode.TAKE_PROFIT_PRICE_KEY: "120.333333333333333d",   # price  + 120.333333333333333
                mode.EXCHANGE_ORDER_IDS: ["ab1", "aaaaa"],
                mode.LEVERAGE: None,
                "PARAM_TAG_1": "ttt",
                "PARAM_Plop": False,
            }, context)
        set_leverage_mock.assert_not_called()
        _set_state_mock.assert_not_called()

        with pytest.raises(errors.InvalidCancelPolicyError):
            await producer.signal_callback({
                mode.EXCHANGE_KEY: exchange_manager.exchange_name,
                mode.SYMBOL_KEY: "unused",
                mode.SIGNAL_KEY: "SelL",
                mode.CANCEL_POLICY: "unknown_cancel_policy",
            }, context)
        set_leverage_mock.assert_not_called()
        _set_state_mock.assert_not_called()


async def test_signal_callback_with_cancel_policies(tools):
    exchange_manager, symbol, mode, producer, consumer = tools
    context = script_keywords.get_base_context(producer.trading_mode)
    mode.CANCEL_PREVIOUS_ORDERS = True

    async def _apply_cancel_policies(*args, **kwargs):
        return True, trading_signals.get_orders_dependencies([mock.Mock(order_id="123"), mock.Mock(order_id="456-cancel_policy")])
    async def _cancel_symbol_open_orders(*args, **kwargs):
        return True, trading_signals.get_orders_dependencies([mock.Mock(order_id="456-cancel_symbol_open_orders")])

    with mock.patch.object(producer, "_set_state", mock.AsyncMock()) as _set_state_mock, \
        mock.patch.object(producer, "_process_pre_state_update_actions", mock.AsyncMock()) as _process_pre_state_update_actions_mock, \
        mock.patch.object(producer, "_parse_order_details", mock.AsyncMock(return_value=(trading_enums.EvaluatorStates.LONG, {}))) as _parse_order_details_mock, \
        mock.patch.object(producer, "apply_cancel_policies", mock.AsyncMock(side_effect=_apply_cancel_policies)) as apply_cancel_policies_mock, \
        mock.patch.object(producer, "cancel_symbol_open_orders", mock.AsyncMock(side_effect=_cancel_symbol_open_orders)) as cancel_symbol_open_orders_mock:
        await producer.signal_callback({
            mode.EXCHANGE_KEY: exchange_manager.exchange_name,
            mode.SYMBOL_KEY: "unused",
            mode.SIGNAL_KEY: "BUY",
        }, context)
        _process_pre_state_update_actions_mock.assert_awaited_once()
        _parse_order_details_mock.assert_awaited_once()
        apply_cancel_policies_mock.assert_awaited_once()
        cancel_symbol_open_orders_mock.assert_awaited_once()
        _set_state_mock.assert_awaited_once()
        assert _set_state_mock.mock_calls[0].kwargs["dependencies"] == trading_signals.get_orders_dependencies([
            mock.Mock(order_id="123"), 
            mock.Mock(order_id="456-cancel_policy"), 
            mock.Mock(order_id="456-cancel_symbol_open_orders")
        ])
    mode.CANCEL_PREVIOUS_ORDERS = False
    with mock.patch.object(producer, "_set_state", mock.AsyncMock()) as _set_state_mock, \
        mock.patch.object(producer, "_process_pre_state_update_actions", mock.AsyncMock()) as _process_pre_state_update_actions_mock, \
        mock.patch.object(producer, "_parse_order_details", mock.AsyncMock(return_value=(trading_enums.EvaluatorStates.LONG, {}))) as _parse_order_details_mock, \
        mock.patch.object(producer, "apply_cancel_policies", mock.AsyncMock(side_effect=_apply_cancel_policies)) as apply_cancel_policies_mock, \
        mock.patch.object(producer, "cancel_symbol_open_orders", mock.AsyncMock(side_effect=_cancel_symbol_open_orders)) as cancel_symbol_open_orders_mock:
        await producer.signal_callback({
            mode.EXCHANGE_KEY: exchange_manager.exchange_name,
            mode.SYMBOL_KEY: "unused",
            mode.SIGNAL_KEY: "BUY",
        }, context)
        _process_pre_state_update_actions_mock.assert_awaited_once()
        _parse_order_details_mock.assert_awaited_once()
        apply_cancel_policies_mock.assert_awaited_once()
        cancel_symbol_open_orders_mock.assert_not_called() # CANCEL_PREVIOUS_ORDERS is False
        _set_state_mock.assert_awaited_once()
        assert _set_state_mock.mock_calls[0].kwargs["dependencies"] == trading_signals.get_orders_dependencies([
            mock.Mock(order_id="123"), 
            mock.Mock(order_id="456-cancel_policy"),
        ])


def compare_dict_with_nan(d_1, d_2):
    try:
        for key, val in d_1.items():
            assert (
                d_2[key] == d_1[key]
                or (isinstance(d_2[key], decimal.Decimal) and d_2[key].is_nan() and isinstance(d_1[key], decimal.Decimal) and d_1[key].is_nan())
                or compare_dict_with_nan(d_1[key], d_2[key])
            ), f"Key {key} is not equal: {d_1[key]} != {d_2[key]}"
        return True
    except (KeyError, AttributeError) as err:
        # print(f"Error comparing dicts: {err.__class__.__name__}: {err}")
        return False
