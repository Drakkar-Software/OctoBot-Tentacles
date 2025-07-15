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
import time
import pytest
import pytest_asyncio
import os.path
import mock
import decimal

import async_channel.util as channel_util

import octobot_commons.enums as commons_enum
import octobot_commons.tests.test_config as test_config
import octobot_commons.constants as commons_constants
import octobot_commons.symbols as commons_symbols
import octobot_commons.configuration as commons_configuration

import octobot_backtesting.api as backtesting_api

import octobot_tentacles_manager.api as tentacles_manager_api

import octobot_trading.api as trading_api
import octobot_trading.exchange_channel as exchanges_channel
import octobot_trading.exchanges as exchanges
import octobot_trading.personal_data as trading_personal_data
import octobot_trading.enums as trading_enums
import octobot_trading.constants as trading_constants
import octobot_trading.modes
import octobot_trading.errors as trading_errors

import tentacles.Trading.Mode as Mode
import tentacles.Trading.Mode.index_trading_mode.index_trading as index_trading
import tentacles.Trading.Mode.index_trading_mode.index_distribution as index_distribution

import tests.test_utils.memory_check_util as memory_check_util
import tests.test_utils.config as test_utils_config
import tests.test_utils.test_exchanges as test_exchanges

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def tools():
    trader = None
    try:
        tentacles_manager_api.reload_tentacle_info()
        mode, trader = await _get_tools()
        yield mode, trader
    finally:
        if trader:
            await _stop(trader.exchange_manager)


async def test_run_independent_backtestings_with_memory_check():
    """
    Should always be called first here to avoid other tests' related memory check issues
    """
    tentacles_setup_config = tentacles_manager_api.create_tentacles_setup_config_with_tentacles(
        Mode.IndexTradingMode,
    )
    config = test_config.load_test_config()
    config[commons_constants.CONFIG_TIME_FRAME] = [commons_enum.TimeFrames.FOUR_HOURS]

    _CONFIG = {
        Mode.IndexTradingMode.get_name(): {
            "required_strategies": [],
            "refresh_interval": 7,
            "rebalance_trigger_min_percent": 5,
            "index_content": []
        },
    }

    def config_proxy(tentacles_setup_config, klass):
        try:
            return _CONFIG[klass if isinstance(klass, str) else klass.get_name()]
        except KeyError:
            return {}

    with tentacles_manager_api.local_tentacle_config_proxy(config_proxy):
        with mock.patch.object(octobot_trading.modes.AbstractTradingMode, "get_historical_config", mock.Mock()) \
            as get_historical_config:
            await memory_check_util.run_independent_backtestings_with_memory_check(
                config, tentacles_setup_config, use_multiple_asset_data_file=True
            )
            # should not be called when no historical config is available (or it will log errors)
            get_historical_config.assert_not_called()


def _get_config(tools, update):
    mode, trader = tools
    config = tentacles_manager_api.get_tentacle_config(trader.exchange_manager.tentacles_setup_config, mode.__class__)
    return {**config, **update}


async def test_init_default_values(tools):
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, {}))
    assert mode.refresh_interval_days == 1
    assert mode.rebalance_trigger_min_ratio == decimal.Decimal(str(index_trading.DEFAULT_REBALANCE_TRIGGER_MIN_RATIO))
    assert mode.quote_asset_rebalance_ratio_threshold == decimal.Decimal(str(index_trading.DEFAULT_QUOTE_ASSET_REBALANCE_TRIGGER_MIN_RATIO))
    assert mode.ratio_per_asset == {'BTC': {'name': 'BTC', 'value': decimal.Decimal(100)}}
    assert mode.total_ratio_per_asset == decimal.Decimal(100)
    assert mode.synchronization_policy == index_trading.SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_AS_SOON_AS_POSSIBLE
    assert mode.requires_initializing_appropriate_coins_distribution is False
    assert mode.indexed_coins == ["BTC"]
    assert mode.selected_rebalance_trigger_profile is None
    assert mode.rebalance_trigger_profiles is None


async def test_init_config_values(tools):
    update = {
        index_trading.IndexTradingModeProducer.REFRESH_INTERVAL: 72,
        index_trading.IndexTradingModeProducer.SYNCHRONIZATION_POLICY: index_trading.SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE.value,
        index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_MIN_PERCENT: 10.2,
        index_trading.IndexTradingModeProducer.SELECTED_REBALANCE_TRIGGER_PROFILE: None,
        index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILES: [
            {
                index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_NAME: "profile-1",
                index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_MIN_PERCENT: 5.2,
            },
            {
                index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_NAME: "profile-2",
                index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_MIN_PERCENT: 20.2,
            },
        ],
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_distribution.DISTRIBUTION_NAME: "ETH",
                index_distribution.DISTRIBUTION_VALUE: 53,
            },
            {
                index_distribution.DISTRIBUTION_NAME: "BTC",
                index_distribution.DISTRIBUTION_VALUE: 1,
            },
            {
                index_distribution.DISTRIBUTION_NAME: "SOL",
                index_distribution.DISTRIBUTION_VALUE: 1,
            },
        ]
    }
    # no selected rebalance trigger profile
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    assert mode.refresh_interval_days == 72
    assert mode.rebalance_trigger_min_ratio == decimal.Decimal("0.102")
    assert mode.selected_rebalance_trigger_profile is None
    assert mode.rebalance_trigger_profiles ==  [
        {
            index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_NAME: "profile-1",
            index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_MIN_PERCENT: 5.2,
        },
        {
            index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_NAME: "profile-2",
            index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_MIN_PERCENT: 20.2,
        },
    ]
    assert mode.synchronization_policy == index_trading.SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE
    assert mode.requires_initializing_appropriate_coins_distribution is True
    assert mode.ratio_per_asset == {
        "BTC": {
            index_distribution.DISTRIBUTION_NAME: "BTC",
            index_distribution.DISTRIBUTION_VALUE: 1,
        },
    }
    assert mode.total_ratio_per_asset == decimal.Decimal("1")
    assert mode.indexed_coins == ["BTC"]

    # now with ETH as traded assets
    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["ETH/USDT", "ADA/USDT", "BTC/USDT"]
    ]
    mode.trading_config[index_trading.IndexTradingModeProducer.SELECTED_REBALANCE_TRIGGER_PROFILE] = "profile-1"
    mode.init_user_inputs({})
    assert mode.refresh_interval_days == 72
    assert mode.rebalance_trigger_profiles ==  [
        {
            index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_NAME: "profile-1",
            index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_MIN_PERCENT: 5.2,
        },
        {
            index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_NAME: "profile-2",
            index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_MIN_PERCENT: 20.2,
        },
    ]
    assert mode.selected_rebalance_trigger_profile == {
        index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_NAME: "profile-1",
        index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_MIN_PERCENT: 5.2,
    }   # applied profile
    assert mode.rebalance_trigger_min_ratio == decimal.Decimal("0.052")
    assert mode.ratio_per_asset == {
        "ETH": {
            index_distribution.DISTRIBUTION_NAME: "ETH",
            index_distribution.DISTRIBUTION_VALUE: 53,
        },
        "BTC": {
            index_distribution.DISTRIBUTION_NAME: "BTC",
            index_distribution.DISTRIBUTION_VALUE: 1,
        }
        # SOL is not added
    }
    assert mode.total_ratio_per_asset == decimal.Decimal("54")
    assert mode.indexed_coins == ["BTC", "ETH"]  # sorted list

    # refresh user inputs
    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["ETH/USDT", "ADA/USDT", "BTC/USDT", "SOL/USDT"]
    ]
    mode.init_user_inputs({})
    assert mode.refresh_interval_days == 72
    assert mode.rebalance_trigger_min_ratio == decimal.Decimal("0.052")
    assert mode.ratio_per_asset == {
        "ETH": {
            index_distribution.DISTRIBUTION_NAME: "ETH",
            index_distribution.DISTRIBUTION_VALUE: 53,
        },
        "BTC": {
            index_distribution.DISTRIBUTION_NAME: "BTC",
            index_distribution.DISTRIBUTION_VALUE: 1,
        },
        "SOL": {
            index_distribution.DISTRIBUTION_NAME: "SOL",
            index_distribution.DISTRIBUTION_VALUE: 1,
        },
    }
    assert mode.total_ratio_per_asset == decimal.Decimal("55")
    assert mode.indexed_coins == ["BTC", "ETH", "SOL"]  # sorted list

    # add ref market in coin rations
    mode.trading_config["index_content"] = [
        {
            index_distribution.DISTRIBUTION_NAME: "USDT",
            index_distribution.DISTRIBUTION_VALUE: 75,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "BTC",
            index_distribution.DISTRIBUTION_VALUE: 25,
        },
    ]
    # select profile 2
    mode.trading_config[index_trading.IndexTradingModeProducer.SELECTED_REBALANCE_TRIGGER_PROFILE] = "profile-2"
    mode.init_user_inputs({})
    assert mode.refresh_interval_days == 72
    assert mode.selected_rebalance_trigger_profile == {
        index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_NAME: "profile-2",
        index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_MIN_PERCENT: 20.2,
    }   # applied profile
    assert mode.rebalance_trigger_min_ratio == decimal.Decimal("0.202")
    assert mode.ratio_per_asset == {
        "BTC": {
            index_distribution.DISTRIBUTION_NAME: "BTC",
            index_distribution.DISTRIBUTION_VALUE: 25,
        },
        "USDT": {
            index_distribution.DISTRIBUTION_NAME: "USDT",
            index_distribution.DISTRIBUTION_VALUE: 75,
        },
    }
    assert mode.total_ratio_per_asset == decimal.Decimal("100")
    assert mode.indexed_coins == ["BTC", "USDT"]  # sorted list

    # unknown profile
    mode.trading_config[index_trading.IndexTradingModeProducer.SELECTED_REBALANCE_TRIGGER_PROFILE] = "unknown"
    mode.init_user_inputs({})
    # back to non-profile config values bu profiles are loaded
    assert mode.rebalance_trigger_profiles ==  [
        {
            index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_NAME: "profile-1",
            index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_MIN_PERCENT: 5.2,
        },
        {
            index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_NAME: "profile-2",
            index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_MIN_PERCENT: 20.2,
        },
    ]
    assert mode.selected_rebalance_trigger_profile is None
    assert mode.rebalance_trigger_min_ratio == decimal.Decimal(str(10.2 / 100))


async def test_single_exchange_process_optimize_initial_portfolio(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))

    with mock.patch.object(
            octobot_trading.modes, "convert_assets_to_target_asset", mock.AsyncMock(return_value=["order_1"])
    ) as convert_assets_to_target_asset_mock, mock.patch.object(
        mode, "cancel_order", mock.AsyncMock()
    ) as cancel_order_mock:
        # no open order
        orders = await mode.single_exchange_process_optimize_initial_portfolio(["BTC", "ETH"], "USDT", {})
        convert_assets_to_target_asset_mock.assert_called_once_with(mode, ["BTC", "ETH"], "USDT", {})
        cancel_order_mock.assert_not_called()
        assert orders == ["order_1"]
        convert_assets_to_target_asset_mock.reset_mock()

        # open orders of the given symbol are cancelled
        open_order_1 = trading_personal_data.SellLimitOrder(trader)
        open_order_2 = trading_personal_data.BuyLimitOrder(trader)
        open_order_3 = trading_personal_data.BuyLimitOrder(trader)
        open_order_1.update(order_type=trading_enums.TraderOrderType.SELL_LIMIT,
                            order_id="open_order_1_id",
                            symbol="BTC/USDT",
                            current_price=decimal.Decimal("70"),
                            quantity=decimal.Decimal("10"),
                            price=decimal.Decimal("70"))
        open_order_2.update(order_type=trading_enums.TraderOrderType.BUY_LIMIT,
                            order_id="open_order_2_id",
                            symbol="ETH/USDT",
                            current_price=decimal.Decimal("70"),
                            quantity=decimal.Decimal("10"),
                            price=decimal.Decimal("70"),
                            reduce_only=True)
        open_order_3.update(order_type=trading_enums.TraderOrderType.BUY_LIMIT,
                            order_id="open_order_2_id",
                            symbol="ADA/USDT",
                            current_price=decimal.Decimal("70"),
                            quantity=decimal.Decimal("10"),
                            price=decimal.Decimal("70"),
                            reduce_only=True)
        await mode.exchange_manager.exchange_personal_data.orders_manager.upsert_order_instance(open_order_1)
        await mode.exchange_manager.exchange_personal_data.orders_manager.upsert_order_instance(open_order_2)
        await mode.exchange_manager.exchange_personal_data.orders_manager.upsert_order_instance(open_order_3)
        mode.exchange_manager.exchange_config.traded_symbol_pairs = ["BTC/USDT", "ETH/USDT"]

        orders = await mode.single_exchange_process_optimize_initial_portfolio(["BTC", "ETH"], "USDT", {})
        convert_assets_to_target_asset_mock.assert_called_once_with(mode, ["BTC", "ETH"], "USDT", {})
        cancel_order_mock.assert_not_called()
        assert orders == ["order_1"]
        convert_assets_to_target_asset_mock.reset_mock()


async def test_get_target_ratio_with_config(tools):
    update = {
        "refresh_interval": 72,
        "rebalance_trigger_min_percent": 10.2,
        "index_content": [
            {
                index_distribution.DISTRIBUTION_NAME: "BTC",
                index_distribution.DISTRIBUTION_VALUE: 1,
            },
            {
                index_distribution.DISTRIBUTION_NAME: "ETH",
                index_distribution.DISTRIBUTION_VALUE: 53,
            },
        ]
    }
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    assert mode.get_target_ratio("ETH") == decimal.Decimal('0')
    assert mode.get_target_ratio("BTC") == decimal.Decimal("1")  # use 100% BTC as others are not in traded pairs
    assert mode.get_target_ratio("SOL") == decimal.Decimal("0")

    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["ETH/USDT", "ADA/USDT", "BTC/USDT", "SOL/USDT"]
    ]
    mode.init_user_inputs({})
    assert mode.get_target_ratio("ETH") == decimal.Decimal('0.9814814814814814814814814815')
    assert mode.get_target_ratio("BTC") == decimal.Decimal("0.01851851851851851851851851852")
    assert mode.get_target_ratio("SOL") == decimal.Decimal("0")


async def test_get_target_ratio_without_config(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    assert mode.get_target_ratio("ETH") == decimal.Decimal('0')
    assert mode.get_target_ratio("BTC") == decimal.Decimal("1")
    assert mode.get_target_ratio("SOL") == decimal.Decimal("0")
    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["ETH/USDT", "SOL/USDT", "BTC/USDT"]
    ]
    mode.ensure_updated_coins_distribution()
    assert mode.get_target_ratio("ETH") == decimal.Decimal('0.3333333333333333617834929233')
    assert mode.get_target_ratio("BTC") == decimal.Decimal("0.3333333333333333617834929233")
    assert mode.get_target_ratio("SOL") == decimal.Decimal("0.3333333333333333617834929233")
    assert mode.get_target_ratio("ADA") == decimal.Decimal("0")

    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["ETH/USDT", "BTC/USDT"]
    ]
    mode.ensure_updated_coins_distribution()
    assert mode.get_target_ratio("ETH") == decimal.Decimal('0.5')
    assert mode.get_target_ratio("BTC") == decimal.Decimal("0.5")
    assert mode.get_target_ratio("SOL") == decimal.Decimal("0")

    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["ETH/USDT", "BTC/USDT", "ADA/USDT", "SOL/USDT"]
    ]
    mode.ensure_updated_coins_distribution()
    assert mode.get_target_ratio("ETH") == decimal.Decimal('0.25')
    assert mode.get_target_ratio("BTC") == decimal.Decimal("0.25")
    assert mode.get_target_ratio("SOL") == decimal.Decimal("0.25")


async def test_ohlcv_callback(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    current_time = time.time()
    with mock.patch.object(producer, "ensure_index", mock.AsyncMock()) as ensure_index_mock, \
        mock.patch.object(producer, "_notify_if_missing_too_many_coins", mock.Mock()) \
            as _notify_if_missing_too_many_coins_mock:
        with mock.patch.object(
                trader.exchange_manager.exchange, "get_exchange_current_time", mock.Mock(return_value=current_time)
        ) as get_exchange_current_time_mock:
            # not enough indexed coins
            mode.indexed_coins = []
            assert producer._last_trigger_time == 0
            await producer.ohlcv_callback("binance", "123", "BTC", "BTC/USDT", None, None)
            ensure_index_mock.assert_not_called()
            _notify_if_missing_too_many_coins_mock.assert_not_called()
            assert get_exchange_current_time_mock.call_count == 1   # only called once as no historical config exists
            get_exchange_current_time_mock.reset_mock()
            assert producer._last_trigger_time == current_time

            # enough coins
            mode.indexed_coins = [1, 2, 3]
            # already called on this time
            await producer.ohlcv_callback("binance", "123", "BTC", "BTC/USDT", None, None)
            ensure_index_mock.assert_not_called()
            _notify_if_missing_too_many_coins_mock.assert_not_called()
            assert get_exchange_current_time_mock.call_count == 1

            assert producer._last_trigger_time == current_time
        with mock.patch.object(
                trader.exchange_manager.exchange, "get_exchange_current_time", mock.Mock(return_value=current_time * 2)
        ) as get_exchange_current_time_mock:
            mode.indexed_coins = [1, 2, 3]
            await producer.ohlcv_callback("binance", "123", "BTC", "BTC/USDT", None, None)
            ensure_index_mock.assert_called_once()
            _notify_if_missing_too_many_coins_mock.assert_called_once()
            assert get_exchange_current_time_mock.call_count == 1
            assert producer._last_trigger_time == current_time * 2


async def test_notify_if_missing_too_many_coins(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    with mock.patch.object(producer.logger, "error", mock.Mock()) as error_mock:
        mode.trading_config[producer.INDEX_CONTENT] = [1, 2, 3, 4, 5]
        mode.indexed_coins = [1, 2, 3, 4, 5]
        producer._notify_if_missing_too_many_coins()
        error_mock.assert_not_called()

        mode.indexed_coins = [1, 2, 3]
        producer._notify_if_missing_too_many_coins()
        error_mock.assert_not_called()

        # error
        mode.indexed_coins = [1, 2]
        producer._notify_if_missing_too_many_coins()
        error_mock.assert_called_once()
        error_mock.reset_mock()

        # error
        mode.indexed_coins = []
        producer._notify_if_missing_too_many_coins()
        error_mock.assert_called_once()
        error_mock.reset_mock()


async def test_ensure_index(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    with mock.patch.object(
            producer, "_wait_for_symbol_prices_and_profitability_init", mock.AsyncMock()
    ) as _wait_for_symbol_prices_and_profitability_init_mock, \
        mock.patch.object(producer, "cancel_traded_pairs_open_orders_if_any", mock.AsyncMock()) \
            as _cancel_traded_pairs_open_orders_if_any:
        with mock.patch.object(producer, "_trigger_rebalance", mock.AsyncMock()) as _trigger_rebalance_mock:
            with mock.patch.object(
                    producer, "_get_rebalance_details", mock.Mock(return_value=(False, {}))
            ) as _get_rebalance_details_mock:
                await producer.ensure_index()
                assert producer.last_activity == octobot_trading.modes.TradingModeActivity(
                    index_trading.IndexActivity.REBALANCING_SKIPPED
                )
                _cancel_traded_pairs_open_orders_if_any.assert_called_once()
                _cancel_traded_pairs_open_orders_if_any.reset_mock()
                _wait_for_symbol_prices_and_profitability_init_mock.assert_called_once()
                _wait_for_symbol_prices_and_profitability_init_mock.reset_mock()
                _get_rebalance_details_mock.assert_called_once()
                _trigger_rebalance_mock.assert_not_called()
            with mock.patch.object(
                    producer, "_get_rebalance_details", mock.Mock(return_value=(True, {"plop": 1}))
            ) as _get_rebalance_details_mock:
                producer.trading_mode.cancel_open_orders = False
                await producer.ensure_index()
                assert producer.last_activity == octobot_trading.modes.TradingModeActivity(
                    index_trading.IndexActivity.REBALANCING_DONE, {"plop": 1}
                )
                _wait_for_symbol_prices_and_profitability_init_mock.assert_called_once()
                _wait_for_symbol_prices_and_profitability_init_mock.reset_mock()
                _get_rebalance_details_mock.assert_called_once()
                _cancel_traded_pairs_open_orders_if_any.assert_not_called()
                _trigger_rebalance_mock.assert_called_once_with({"plop": 1})

        # Test with requires_initializing_appropriate_coins_distribution = True
        with mock.patch.object(producer, "_trigger_rebalance", mock.AsyncMock()) as _trigger_rebalance_mock:
            with mock.patch.object(
                    producer, "_get_rebalance_details", mock.Mock(return_value=(False, {}))
            ) as _get_rebalance_details_mock:
                with mock.patch.object(
                        mode, "ensure_updated_coins_distribution", mock.Mock()
                ) as ensure_updated_coins_distribution_mock:
                    # Set the flag to True
                    mode.requires_initializing_appropriate_coins_distribution = True
                    producer.trading_mode.cancel_open_orders = True
                    await producer.ensure_index()
                    # Verify ensure_updated_coins_distribution was called with adapt_to_holdings=True
                    ensure_updated_coins_distribution_mock.assert_called_once_with(adapt_to_holdings=True)
                    # Verify the flag was set to False
                    assert mode.requires_initializing_appropriate_coins_distribution is False
                    assert producer.last_activity == octobot_trading.modes.TradingModeActivity(
                        index_trading.IndexActivity.REBALANCING_SKIPPED
                    )
                    _cancel_traded_pairs_open_orders_if_any.assert_called_once()
                    _wait_for_symbol_prices_and_profitability_init_mock.assert_called_once()
                    _get_rebalance_details_mock.assert_called_once()
                    _trigger_rebalance_mock.assert_not_called()
                    ensure_updated_coins_distribution_mock.reset_mock()
                    _cancel_traded_pairs_open_orders_if_any.reset_mock()
                    _wait_for_symbol_prices_and_profitability_init_mock.reset_mock()
                    _get_rebalance_details_mock.reset_mock()

            with mock.patch.object(
                    producer, "_get_rebalance_details", mock.Mock(return_value=(True, {"plop": 1}))
            ) as _get_rebalance_details_mock:
                with mock.patch.object(
                        mode, "ensure_updated_coins_distribution", mock.Mock()
                ) as ensure_updated_coins_distribution_mock:
                    # Set the flag to True and disable cancel_open_orders
                    mode.requires_initializing_appropriate_coins_distribution = True
                    producer.trading_mode.cancel_open_orders = False
                    await producer.ensure_index()
                    # Verify ensure_updated_coins_distribution was called with adapt_to_holdings=True
                    ensure_updated_coins_distribution_mock.assert_called_once_with(adapt_to_holdings=True)
                    # Verify the flag was set to False
                    assert mode.requires_initializing_appropriate_coins_distribution is False
                    assert producer.last_activity == octobot_trading.modes.TradingModeActivity(
                        index_trading.IndexActivity.REBALANCING_DONE, {"plop": 1}
                    )
                    _wait_for_symbol_prices_and_profitability_init_mock.assert_called_once()
                    _get_rebalance_details_mock.assert_called_once()
                    _cancel_traded_pairs_open_orders_if_any.assert_not_called()
                    _trigger_rebalance_mock.assert_called_once_with({"plop": 1})
                    ensure_updated_coins_distribution_mock.reset_mock()
                    _wait_for_symbol_prices_and_profitability_init_mock.reset_mock()
                    _get_rebalance_details_mock.reset_mock()
                    _trigger_rebalance_mock.reset_mock()

        # Test with requires_initializing_appropriate_coins_distribution = False (default)
        with mock.patch.object(producer, "_trigger_rebalance", mock.AsyncMock()) as _trigger_rebalance_mock:
            with mock.patch.object(
                    producer, "_get_rebalance_details", mock.Mock(return_value=(False, {}))
            ) as _get_rebalance_details_mock:
                with mock.patch.object(
                        mode, "ensure_updated_coins_distribution", mock.Mock()
                ) as ensure_updated_coins_distribution_mock:
                    # Ensure the flag is False (default state)
                    mode.requires_initializing_appropriate_coins_distribution = False
                    producer.trading_mode.cancel_open_orders = True
                    await producer.ensure_index()
                    # Verify ensure_updated_coins_distribution was NOT called
                    ensure_updated_coins_distribution_mock.assert_not_called()
                    # Verify the flag remains False
                    assert mode.requires_initializing_appropriate_coins_distribution is False
                    assert producer.last_activity == octobot_trading.modes.TradingModeActivity(
                        index_trading.IndexActivity.REBALANCING_SKIPPED
                    )
                    _cancel_traded_pairs_open_orders_if_any.assert_called_once()
                    _wait_for_symbol_prices_and_profitability_init_mock.assert_called_once()
                    _get_rebalance_details_mock.assert_called_once()
                    _trigger_rebalance_mock.assert_not_called()


async def test_cancel_traded_pairs_open_orders_if_any(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    orders = [
        mock.Mock(symbol="BTC/USDT"),
        mock.Mock(symbol="BTC/USDT"),
        mock.Mock(symbol="ETH/USDT"),
        mock.Mock(symbol="DOGE/USDT"),
    ]
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.orders_manager, "get_open_orders", mock.Mock(return_value=orders)
    ) as get_open_orders_mock, \
        mock.patch.object(mode, "cancel_order", mock.AsyncMock()) \
            as cancel_order_mock:
        await producer.cancel_traded_pairs_open_orders_if_any()
        get_open_orders_mock.assert_called_once()
        assert cancel_order_mock.call_count == 2
        assert cancel_order_mock.mock_calls[0].args[0] is orders[0]
        assert cancel_order_mock.mock_calls[1].args[0] is orders[1]


async def test_trigger_rebalance(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    with mock.patch.object(
            producer, "submit_trading_evaluation", mock.AsyncMock()
    ) as _wait_for_symbol_prices_and_profitability_init_mock:
        details = {"hi": "ho"}
        await producer._trigger_rebalance(details)
        _wait_for_symbol_prices_and_profitability_init_mock.assert_called_once_with(
            cryptocurrency=None,
            symbol=None,
            time_frame=None,
            final_note=None,
            state=trading_enums.EvaluatorStates.NEUTRAL,
            data=details
        )


async def test_get_rebalance_details(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["ETH/USDT", "BTC/USDT", "SOL/USDT"]
    ]
    mode.ensure_updated_coins_distribution()
    mode.rebalance_trigger_min_ratio = decimal.Decimal("0.1")
    portfolio_value_holder = trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder
    with mock.patch.object(producer, "_resolve_swaps", mock.Mock()) as _resolve_swaps_mock:
        def _get_holdings_ratio(coin, **kwargs):
            if coin == "USDT":
                return decimal.Decimal("0")
            return decimal.Decimal("0.3")
        with mock.patch.object(
            portfolio_value_holder, "get_holdings_ratio", mock.Mock(side_effect=_get_holdings_ratio)
        ) as get_holdings_ratio_mock:
            with mock.patch.object(
                mode, "get_removed_coins_from_config", mock.Mock(return_value=[])
            ) as get_removed_coins_from_config_mock:
                should_rebalance, details = producer._get_rebalance_details()
                assert should_rebalance is False
                assert details == {
                    index_trading.RebalanceDetails.SELL_SOME.value: {},
                    index_trading.RebalanceDetails.BUY_MORE.value: {},
                    index_trading.RebalanceDetails.REMOVE.value: {},
                    index_trading.RebalanceDetails.ADD.value: {},
                    index_trading.RebalanceDetails.SWAP.value: {},
                index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
                }
                assert get_holdings_ratio_mock.call_count == len(mode.indexed_coins) + 1  # +1 for USDT
                get_removed_coins_from_config_mock.assert_called_once()
                _resolve_swaps_mock.assert_called_once_with(details)
                _resolve_swaps_mock.reset_mock()
                get_holdings_ratio_mock.reset_mock()
            with mock.patch.object(
                    mode, "get_removed_coins_from_config", mock.Mock(return_value=["SOL", "ADA"])
            ) as get_removed_coins_from_config_mock:
                should_rebalance, details = producer._get_rebalance_details()
                assert should_rebalance is True
                assert details == {
                    index_trading.RebalanceDetails.SELL_SOME.value: {},
                    index_trading.RebalanceDetails.BUY_MORE.value: {},
                    index_trading.RebalanceDetails.REMOVE.value: {
                        "SOL": decimal.Decimal("0.3"),
                        # "ADA": decimal.Decimal("0.3")  # ADA is not in traded pairs, it's not removed
                    },
                    index_trading.RebalanceDetails.ADD.value: {},
                    index_trading.RebalanceDetails.SWAP.value: {},
                index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
                }
                assert get_holdings_ratio_mock.call_count == \
                       len(mode.indexed_coins) + len(details[index_trading.RebalanceDetails.REMOVE.value]) + 1  # +1 for USDT
                get_removed_coins_from_config_mock.assert_called_once()
                _resolve_swaps_mock.assert_called_once_with(details)
                _resolve_swaps_mock.reset_mock()
                get_holdings_ratio_mock.reset_mock()
        def _get_holdings_ratio(coin, **kwargs):
            if coin == "USDT":
                return decimal.Decimal("0")
            return decimal.Decimal("0.2")
        with mock.patch.object(
                portfolio_value_holder, "get_holdings_ratio", mock.Mock(side_effect=_get_holdings_ratio)
        ) as get_holdings_ratio_mock:
            with mock.patch.object(
                    mode, "get_removed_coins_from_config", mock.Mock(return_value=[])
            ) as get_removed_coins_from_config_mock:
                should_rebalance, details = producer._get_rebalance_details()
                assert should_rebalance is True
                assert details == {
                    index_trading.RebalanceDetails.SELL_SOME.value: {},
                    index_trading.RebalanceDetails.BUY_MORE.value: {
                        'BTC': decimal.Decimal('0.3333333333333333617834929233'),
                        'ETH': decimal.Decimal('0.3333333333333333617834929233'),
                        'SOL': decimal.Decimal('0.3333333333333333617834929233')
                    },
                    index_trading.RebalanceDetails.REMOVE.value: {},
                    index_trading.RebalanceDetails.ADD.value: {},
                    index_trading.RebalanceDetails.SWAP.value: {},
                index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
                }
                assert get_holdings_ratio_mock.call_count == len(mode.indexed_coins) + 1  # +1 for USDT
                get_removed_coins_from_config_mock.assert_called_once()
                _resolve_swaps_mock.assert_called_once_with(details)
                _resolve_swaps_mock.reset_mock()
                get_holdings_ratio_mock.reset_mock()
            with mock.patch.object(
                    mode, "get_removed_coins_from_config", mock.Mock(return_value=["SOL", "ADA"])
            ) as get_removed_coins_from_config_mock:
                should_rebalance, details = producer._get_rebalance_details()
                assert should_rebalance is True
                assert details == {
                    index_trading.RebalanceDetails.SELL_SOME.value: {},
                    index_trading.RebalanceDetails.BUY_MORE.value: {
                        'BTC': decimal.Decimal('0.3333333333333333617834929233'),
                        'ETH': decimal.Decimal('0.3333333333333333617834929233'),
                        'SOL': decimal.Decimal('0.3333333333333333617834929233')
                    },
                    index_trading.RebalanceDetails.REMOVE.value: {
                        "SOL": decimal.Decimal("0.2"),
                        # "ADA": decimal.Decimal("0.2")  # not in traded pairs
                    },
                    index_trading.RebalanceDetails.ADD.value: {},
                    index_trading.RebalanceDetails.SWAP.value: {},
                index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
                }
                assert get_holdings_ratio_mock.call_count == \
                       len(mode.indexed_coins) + len(details[index_trading.RebalanceDetails.REMOVE.value]) + 1  # +1 for USDT
                get_removed_coins_from_config_mock.assert_called_once()
                _resolve_swaps_mock.assert_called_once_with(details)
                _resolve_swaps_mock.reset_mock()
                get_holdings_ratio_mock.reset_mock()

        # rebalance cap larger than ratio
        def _get_holdings_ratio(coin, **kwargs):
            if coin == "USDT":
                return decimal.Decimal("0")
            return decimal.Decimal("0.3")
        mode.rebalance_trigger_min_ratio = decimal.Decimal("0.5")
        with mock.patch.object(
                portfolio_value_holder, "get_holdings_ratio", mock.Mock(side_effect=_get_holdings_ratio)
        ) as get_holdings_ratio_mock:
            should_rebalance, details = producer._get_rebalance_details()
            assert should_rebalance is False
            assert details == {
                index_trading.RebalanceDetails.SELL_SOME.value: {},
                index_trading.RebalanceDetails.BUY_MORE.value: {},
                index_trading.RebalanceDetails.REMOVE.value: {},
                index_trading.RebalanceDetails.ADD.value: {},
                index_trading.RebalanceDetails.SWAP.value: {},
                index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
            }
            assert get_holdings_ratio_mock.call_count == len(mode.indexed_coins) + 1  # +1 for USDT
            get_holdings_ratio_mock.reset_mock()
            _resolve_swaps_mock.assert_called_once_with(details)
            _resolve_swaps_mock.reset_mock()
        def _get_holdings_ratio(coin, **kwargs):
            if coin == "USDT":
                return decimal.Decimal("0")
            return decimal.Decimal("0.00000001")
        with mock.patch.object(
                portfolio_value_holder, "get_holdings_ratio", mock.Mock(side_effect=_get_holdings_ratio)
        ) as get_holdings_ratio_mock:
            should_rebalance, details = producer._get_rebalance_details()
            assert should_rebalance is False
            assert details == {
                index_trading.RebalanceDetails.SELL_SOME.value: {},
                index_trading.RebalanceDetails.BUY_MORE.value: {},
                index_trading.RebalanceDetails.REMOVE.value: {},
                index_trading.RebalanceDetails.ADD.value: {},
                index_trading.RebalanceDetails.SWAP.value: {},
                index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
            }
            assert get_holdings_ratio_mock.call_count == len(mode.indexed_coins) + 1  # +1 for USDT
            get_holdings_ratio_mock.reset_mock()
            _resolve_swaps_mock.assert_called_once_with(details)
            _resolve_swaps_mock.reset_mock()
        def _get_holdings_ratio(coin, **kwargs):
            if coin == "USDT":
                return decimal.Decimal("0")
            return decimal.Decimal("0.9")
        with mock.patch.object(
                portfolio_value_holder, "get_holdings_ratio", mock.Mock(side_effect=_get_holdings_ratio)
        ) as get_holdings_ratio_mock:
            should_rebalance, details = producer._get_rebalance_details()
            assert should_rebalance is True
            assert details == {
                index_trading.RebalanceDetails.SELL_SOME.value: {
                    'BTC': decimal.Decimal('0.3333333333333333617834929233'),
                    'ETH': decimal.Decimal('0.3333333333333333617834929233'),
                    'SOL': decimal.Decimal('0.3333333333333333617834929233')
                },
                index_trading.RebalanceDetails.BUY_MORE.value: {},
                index_trading.RebalanceDetails.REMOVE.value: {},
                index_trading.RebalanceDetails.ADD.value: {},
                index_trading.RebalanceDetails.SWAP.value: {},
                index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
            }
            assert get_holdings_ratio_mock.call_count == len(details[index_trading.RebalanceDetails.SELL_SOME.value]) + 1  # +1 for USDT
            get_holdings_ratio_mock.reset_mock()
            _resolve_swaps_mock.assert_called_once_with(details)
            _resolve_swaps_mock.reset_mock()
        def _get_holdings_ratio(coin, **kwargs):
            return decimal.Decimal("0")
        with mock.patch.object(
                portfolio_value_holder, "get_holdings_ratio", mock.Mock(side_effect=_get_holdings_ratio)
        ) as get_holdings_ratio_mock:
            should_rebalance, details = producer._get_rebalance_details()
            assert should_rebalance is True
            assert details == {
                index_trading.RebalanceDetails.SELL_SOME.value: {},
                index_trading.RebalanceDetails.BUY_MORE.value: {},
                index_trading.RebalanceDetails.REMOVE.value: {},
                index_trading.RebalanceDetails.ADD.value: {
                    'BTC': decimal.Decimal('0.3333333333333333617834929233'),
                    'ETH': decimal.Decimal('0.3333333333333333617834929233'),
                    'SOL': decimal.Decimal('0.3333333333333333617834929233')
                },
                index_trading.RebalanceDetails.SWAP.value: {},
                index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
            }
            assert get_holdings_ratio_mock.call_count == len(details[index_trading.RebalanceDetails.ADD.value]) + 1  # +1 for USDT
            get_holdings_ratio_mock.reset_mock()
            _resolve_swaps_mock.assert_called_once_with(details)
            _resolve_swaps_mock.reset_mock()

        # will only add ETH
        def _get_holdings_ratio(coin, **kwargs):
            if coin == "ETH":
                return decimal.Decimal("0")
            return decimal.Decimal("0.33")
        with mock.patch.object(
            portfolio_value_holder, "get_holdings_ratio", mock.Mock(side_effect=_get_holdings_ratio)
        ) as get_holdings_ratio_mock:
            should_rebalance, details = producer._get_rebalance_details()
            assert should_rebalance is True
            assert details == {
                index_trading.RebalanceDetails.SELL_SOME.value: {},
                index_trading.RebalanceDetails.BUY_MORE.value: {},
                index_trading.RebalanceDetails.REMOVE.value: {},
                index_trading.RebalanceDetails.ADD.value: {
                    'ETH': decimal.Decimal('0.3333333333333333617834929233'),
                },
                index_trading.RebalanceDetails.SWAP.value: {},
                index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
            }
            assert get_holdings_ratio_mock.call_count == 3 + 1  # called for each coin + 1 for USDT
            get_holdings_ratio_mock.reset_mock()
            _resolve_swaps_mock.assert_called_once_with(details)
            _resolve_swaps_mock.reset_mock()
        
async def test_get_rebalance_details_with_usdt_without_coin_distribution_update(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["ETH/USDT", "BTC/USDT", "SOL/USDT"]
    ]
    mode.ensure_updated_coins_distribution()
    mode.rebalance_trigger_min_ratio = decimal.Decimal("0.1")
    mode.synchronization_policy = index_trading.SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_AS_SOON_AS_POSSIBLE
    portfolio_value_holder = trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder
    with mock.patch.object(producer, "_resolve_swaps", mock.Mock()) as _resolve_swaps_mock, \
        mock.patch.object(mode, "ensure_updated_coins_distribution", mock.Mock()) as ensure_updated_coins_distribution_mock:
        def _get_holdings_ratio(coin, **kwargs):
            # USDT is 1/3 of the portfolio
            if coin == "USDT":
                return decimal.Decimal("0.33")
            # other coins are 2/3 of the portfolio
            return decimal.Decimal("0.33") * decimal.Decimal("2") / decimal.Decimal("3")

        # with added USDT to the portfolio
        with mock.patch.object(
            portfolio_value_holder, "get_holdings_ratio", mock.Mock(side_effect=_get_holdings_ratio)
        ) as get_holdings_ratio_mock:
            should_rebalance, details = producer._get_rebalance_details()
            assert should_rebalance is True
            assert details == {
                index_trading.RebalanceDetails.SELL_SOME.value: {},
                index_trading.RebalanceDetails.BUY_MORE.value: {
                    'BTC': decimal.Decimal('0.3333333333333333617834929233'),
                    'ETH': decimal.Decimal('0.3333333333333333617834929233'),
                    'SOL': decimal.Decimal('0.3333333333333333617834929233')
                },
                index_trading.RebalanceDetails.REMOVE.value: {},
                index_trading.RebalanceDetails.ADD.value: {},
                index_trading.RebalanceDetails.SWAP.value: {},
                index_trading.RebalanceDetails.FORCED_REBALANCE.value: True,
            }
            assert get_holdings_ratio_mock.call_count == len(mode.indexed_coins) + 1  # called to check non-indexed assets ratio
            ensure_updated_coins_distribution_mock.assert_not_called()
            get_holdings_ratio_mock.reset_mock()
            _resolve_swaps_mock.assert_not_called()
            _resolve_swaps_mock.reset_mock()
        
async def test_get_rebalance_details_with_usdt_and_coin_distribution_update(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["ETH/USDT", "BTC/USDT", "SOL/USDT"]
    ]
    mode.ensure_updated_coins_distribution()
    mode.rebalance_trigger_min_ratio = decimal.Decimal("0.1")
    portfolio_value_holder = trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder
    mode.synchronization_policy = index_trading.SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE
    with mock.patch.object(producer, "_resolve_swaps", mock.Mock()) as _resolve_swaps_mock, \
        mock.patch.object(mode, "ensure_updated_coins_distribution", mock.Mock()) as ensure_updated_coins_distribution_mock:
        def _get_holdings_ratio(coin, **kwargs):
            # USDT is 1/3 of the portfolio
            if coin == "USDT":
                return decimal.Decimal("0.33")
            # other coins are 2/3 of the portfolio
            return decimal.Decimal("0.33") * decimal.Decimal("2") / decimal.Decimal("3")

        # with added USDT to the portfolio
        with mock.patch.object(
            portfolio_value_holder, "get_holdings_ratio", mock.Mock(side_effect=_get_holdings_ratio)
        ) as get_holdings_ratio_mock:
            should_rebalance, details = producer._get_rebalance_details()
            assert should_rebalance is True
            assert details == {
                index_trading.RebalanceDetails.SELL_SOME.value: {},
                index_trading.RebalanceDetails.BUY_MORE.value: {
                    'BTC': decimal.Decimal('0.3333333333333333617834929233'),
                    'ETH': decimal.Decimal('0.3333333333333333617834929233'),
                    'SOL': decimal.Decimal('0.3333333333333333617834929233')
                },
                index_trading.RebalanceDetails.REMOVE.value: {},
                index_trading.RebalanceDetails.ADD.value: {},
                index_trading.RebalanceDetails.SWAP.value: {},
                index_trading.RebalanceDetails.FORCED_REBALANCE.value: True,
            }
            # 2 x called to check non-indexed assets ratio (once for current and one for latest distribution)
            assert get_holdings_ratio_mock.call_count == 2 * (len(mode.indexed_coins) + 1)  
            ensure_updated_coins_distribution_mock.assert_called_once()
            get_holdings_ratio_mock.reset_mock()
            _resolve_swaps_mock.assert_not_called()
            _resolve_swaps_mock.reset_mock()


async def test_should_rebalance_due_to_non_indexed_quote_assets_ratio(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    assert mode.quote_asset_rebalance_ratio_threshold == decimal.Decimal("0.1")
    rebalance_details = {
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {},
        index_trading.RebalanceDetails.ADD.value: {},
        index_trading.RebalanceDetails.SWAP.value: {},
        index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
    }
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.23"), rebalance_details) is True
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.1"), rebalance_details) is True
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.09"), rebalance_details) is False
    # lower threshold
    mode.quote_asset_rebalance_ratio_threshold = decimal.Decimal("0.05")
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.09"), rebalance_details) is True
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.04"), rebalance_details) is False

    # test added coins
    rebalance_details[index_trading.RebalanceDetails.ADD.value] = {
        "BTC": decimal.Decimal("0.1")
    }
    rebalance_details[index_trading.RebalanceDetails.BUY_MORE.value] = {
        "ETH": decimal.Decimal("0.1")
    }
    # can't swap quote for BTC & ETH
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.1"), rebalance_details) is True
    # can swap quote for BTC & ETH: don't rebalance
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.2"), rebalance_details) is False
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.21"), rebalance_details) is False
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.18"), rebalance_details) is False
    # beyond QUOTE_ASSET_TO_INDEXED_SWAP_RATIO_THRESHOLD threshold
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.17"), rebalance_details) is True

    # with removed coins: can't "just swap quote for added coins", perform regular quote ratio check
    rebalance_details[index_trading.RebalanceDetails.REMOVE.value] = {
        "BTC": decimal.Decimal("0.1")
    }
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.2"), rebalance_details) is True  # is False when no coins are to remove
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.03"), rebalance_details) is False  # bellow threshold: still false

    # with sell some coins and removed coins: can't "just swap quote for added coins", perform regular quote ratio check
    rebalance_details[index_trading.RebalanceDetails.SELL_SOME.value] = {
        "BTC": decimal.Decimal("0.1")
    }
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.2"), rebalance_details) is True  # is False when no coins are to remove
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.03"), rebalance_details) is False  # bellow threshold: still false
    # with only sell some coin
    rebalance_details[index_trading.RebalanceDetails.REMOVE.value] = {}
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.2"), rebalance_details) is True  # is False when no coins are to remove
    assert producer._should_rebalance_due_to_non_indexed_quote_assets_ratio(decimal.Decimal("0.03"), rebalance_details) is False  # bellow threshold: still false


async def test_get_removed_coins_from_config_sell_removed_coins_asap(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    mode.synchronization_policy = index_trading.SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_AS_SOON_AS_POSSIBLE
    mode.sell_unindexed_traded_coins = False
    assert mode.get_removed_coins_from_config([]) == []
    mode.trading_config = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "AA"
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BB"
            }
        ]
    }
    assert mode.get_removed_coins_from_config([]) == []
    mode.previous_trading_config = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "AA"
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BB"
            }
        ]
    }
    mode.trading_config = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "AA"
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "CC"
            }
        ]
    }
    assert mode.get_removed_coins_from_config([]) == ["BB"]
    # with sell_unindexed_traded_coins=True
    mode.sell_unindexed_traded_coins = True
    mode.indexed_coins = ["BTC"]
    mode.previous_trading_config = None
    assert mode.get_removed_coins_from_config(["BTC", "ETH"]) == ["ETH"]
    mode.previous_trading_config = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "AA"
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BB"
            }
        ]
    }
    assert sorted(mode.get_removed_coins_from_config(["BTC", "ETH"])) == sorted(["ETH", "BB"])


async def test_get_removed_coins_from_config_sell_removed_on_ratio_rebalance(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    mode.synchronization_policy = index_trading.SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE
    mode.sell_unindexed_traded_coins = False
    assert mode.get_removed_coins_from_config([]) == []
    # without historical config
    mode.trading_config = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC"
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "SOL"
            }
        ]
    }
    assert mode.get_removed_coins_from_config([]) == []
    # with sell_unindexed_traded_coins=True
    mode.sell_unindexed_traded_coins = True
    mode.indexed_coins = ["BTC"]
    assert mode.get_removed_coins_from_config(["BTC", "ETH"]) == ["ETH"]

    # with historical config
    historical_config_1 = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC"
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "ADA"
            }
        ]
    }
    historical_config_2 = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC"
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "DOT"
            }
        ]
    }
    commons_configuration.add_historical_tentacle_config(mode.trading_config, 1, historical_config_1)
    commons_configuration.add_historical_tentacle_config(mode.trading_config, 2, historical_config_2)
    mode.historical_master_config = mode.trading_config
    with mock.patch.object(mode.exchange_manager.exchange, "get_exchange_current_time", mock.Mock(return_value=0)):
        assert mode.get_removed_coins_from_config(["BTC", "ETH", "SOL"]) == ["ETH", "SOL"]
    with mock.patch.object(mode.exchange_manager.exchange, "get_exchange_current_time", mock.Mock(return_value=2)):
        assert sorted(mode.get_removed_coins_from_config(["BTC", "ETH", "SOL"])) == sorted(
            ["ETH", "SOL", "ADA", "DOT"]
        )
        assert sorted(mode.get_removed_coins_from_config(["BTC", "ETH"])) == sorted(['ADA', 'DOT', 'ETH'])

    # with sell_unindexed_traded_coins=False
    mode.sell_unindexed_traded_coins = False
    with mock.patch.object(mode.exchange_manager.exchange, "get_exchange_current_time", mock.Mock(return_value=0)):
        assert mode.get_removed_coins_from_config(["BTC", "ETH", "SOL"]) == []
    with mock.patch.object(mode.exchange_manager.exchange, "get_exchange_current_time", mock.Mock(return_value=2)):
        assert sorted(mode.get_removed_coins_from_config(["BTC", "ETH", "SOL"])) == sorted(
            ["ADA", "DOT"]
        )
        assert sorted(mode.get_removed_coins_from_config(["BTC", "ETH"])) == sorted(['ADA', 'DOT'])


async def test_create_new_orders(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    with mock.patch.object(
            consumer, "_rebalance_portfolio", mock.AsyncMock(return_value="plop")
    ) as _rebalance_portfolio_mock:
        with pytest.raises(KeyError):
            # missing "data"
            await consumer.create_new_orders(None, None, None)
        assert await consumer.create_new_orders(None, None, None, data="hello") == []
        _rebalance_portfolio_mock.assert_not_called()
        assert await consumer.create_new_orders(
            None, None, trading_enums.EvaluatorStates.NEUTRAL.value, data="hello"
        ) == "plop"
        _rebalance_portfolio_mock.assert_called_once_with("hello")


async def test_rebalance_portfolio(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    with mock.patch.object(
            consumer, "_ensure_enough_funds_to_buy_after_selling", mock.AsyncMock()
    ) as _ensure_enough_funds_to_buy_after_selling_mock, mock.patch.object(
        consumer, "_sell_indexed_coins_for_reference_market", mock.AsyncMock(return_value=["sell"])
    ) as _sell_indexed_coins_for_reference_market_mock, mock.patch.object(
        consumer, "_split_reference_market_into_indexed_coins", mock.AsyncMock(return_value=["buy"])
    ) as _split_reference_market_into_indexed_coins_mock:
        with mock.patch.object(
            consumer, "_can_simply_buy_coins_without_selling", mock.Mock(return_value=False)
        ) as _can_simply_buy_coins_without_selling_mock:
            assert await consumer._rebalance_portfolio("details") == ["sell", "buy"]
            _ensure_enough_funds_to_buy_after_selling_mock.assert_called_once()
            _sell_indexed_coins_for_reference_market_mock.assert_called_once_with("details")
            _split_reference_market_into_indexed_coins_mock.assert_called_once_with("details", False)
            _can_simply_buy_coins_without_selling_mock.assert_called_once_with("details")
            _ensure_enough_funds_to_buy_after_selling_mock.reset_mock()
            _sell_indexed_coins_for_reference_market_mock.reset_mock()
            _split_reference_market_into_indexed_coins_mock.reset_mock()
        with mock.patch.object(
            consumer, "_can_simply_buy_coins_without_selling", mock.Mock(return_value=True)
        ) as _can_simply_buy_coins_without_selling_mock:
            assert await consumer._rebalance_portfolio("details") == ["buy"]
            _ensure_enough_funds_to_buy_after_selling_mock.assert_called_once()
            _sell_indexed_coins_for_reference_market_mock.assert_not_called()
            _split_reference_market_into_indexed_coins_mock.assert_called_once_with("details", True)
            _can_simply_buy_coins_without_selling_mock.assert_called_once_with("details")

    with mock.patch.object(
            consumer, "_update_producer_last_activity", mock.Mock()
    ) as _update_producer_last_activity_mock:
        with mock.patch.object(
                consumer, "_ensure_enough_funds_to_buy_after_selling", mock.AsyncMock()
        ) as _ensure_enough_funds_to_buy_after_selling_mock, mock.patch.object(
            consumer, "_sell_indexed_coins_for_reference_market", mock.AsyncMock(
                side_effect=trading_errors.MissingMinimalExchangeTradeVolume
            )
        ) as _sell_indexed_coins_for_reference_market_mock, mock.patch.object(
            consumer, "_split_reference_market_into_indexed_coins", mock.AsyncMock(return_value=["buy"])
        ) as _split_reference_market_into_indexed_coins_mock, mock.patch.object(
            consumer, "_can_simply_buy_coins_without_selling", mock.Mock(return_value=False)
        ) as _can_simply_buy_coins_without_selling_mock:
            assert await consumer._rebalance_portfolio("details") == []
            _ensure_enough_funds_to_buy_after_selling_mock.assert_called_once()
            _sell_indexed_coins_for_reference_market_mock.assert_called_once_with("details")
            _split_reference_market_into_indexed_coins_mock.assert_not_called()
            _can_simply_buy_coins_without_selling_mock.assert_called_once_with("details")
            _update_producer_last_activity_mock.assert_called_once_with(
                index_trading.IndexActivity.REBALANCING_SKIPPED,
                index_trading.RebalanceSkipDetails.NOT_ENOUGH_AVAILABLE_FOUNDS.value
            )
            _update_producer_last_activity_mock.reset_mock()

        with mock.patch.object(
            consumer, "_ensure_enough_funds_to_buy_after_selling", mock.AsyncMock(
                side_effect=trading_errors.MissingMinimalExchangeTradeVolume
            )
        ) as _ensure_enough_funds_to_buy_after_selling_mock, \
            mock.patch.object(
                consumer, "_sell_indexed_coins_for_reference_market", mock.AsyncMock(return_value=["sell"])
        ) as _sell_indexed_coins_for_reference_market_mock, mock.patch.object(
            consumer, "_split_reference_market_into_indexed_coins", mock.AsyncMock(return_value=["buy"])
        ) as _split_reference_market_into_indexed_coins_mock, mock.patch.object(
            consumer, "_can_simply_buy_coins_without_selling", mock.Mock(return_value=False)
        ) as _can_simply_buy_coins_without_selling_mock:
            assert await consumer._rebalance_portfolio("details") == []
            _ensure_enough_funds_to_buy_after_selling_mock.assert_called_once()
            _sell_indexed_coins_for_reference_market_mock.assert_not_called()
            _split_reference_market_into_indexed_coins_mock.assert_not_called()
            _can_simply_buy_coins_without_selling_mock.assert_not_called()
            _update_producer_last_activity_mock.assert_called_once_with(
                index_trading.IndexActivity.REBALANCING_SKIPPED,
                index_trading.RebalanceSkipDetails.NOT_ENOUGH_AVAILABLE_FOUNDS.value
            )
            _update_producer_last_activity_mock.reset_mock()

        with mock.patch.object(
            consumer, "_ensure_enough_funds_to_buy_after_selling", mock.AsyncMock()
        ) as _ensure_enough_funds_to_buy_after_selling_mock, \
        mock.patch.object(
            consumer, "_sell_indexed_coins_for_reference_market", mock.AsyncMock(return_value=["sell"])
        ) as _sell_indexed_coins_for_reference_market_mock, mock.patch.object(
            consumer, "_split_reference_market_into_indexed_coins", mock.AsyncMock(
                side_effect=trading_errors.MissingMinimalExchangeTradeVolume
            )
        ) as _split_reference_market_into_indexed_coins_mock:
            with mock.patch.object(
                consumer, "_can_simply_buy_coins_without_selling", mock.Mock(return_value=False)
            ) as _can_simply_buy_coins_without_selling_mock:
                assert await consumer._rebalance_portfolio("details") == ["sell"]
                _ensure_enough_funds_to_buy_after_selling_mock.assert_called_once()
                _sell_indexed_coins_for_reference_market_mock.assert_called_once_with("details")
                _split_reference_market_into_indexed_coins_mock.assert_called_once_with("details", False)
                _update_producer_last_activity_mock.assert_called_once_with(
                    index_trading.IndexActivity.REBALANCING_SKIPPED,
                    index_trading.RebalanceSkipDetails.NOT_ENOUGH_AVAILABLE_FOUNDS.value
                )
                _ensure_enough_funds_to_buy_after_selling_mock.reset_mock()
                _sell_indexed_coins_for_reference_market_mock.reset_mock()
                _split_reference_market_into_indexed_coins_mock.reset_mock()
                _update_producer_last_activity_mock.reset_mock()
            with mock.patch.object(
                consumer, "_can_simply_buy_coins_without_selling", mock.Mock(return_value=True)
            ) as _can_simply_buy_coins_without_selling_mock:
                assert await consumer._rebalance_portfolio("details") == []
                _ensure_enough_funds_to_buy_after_selling_mock.assert_called_once()
                _sell_indexed_coins_for_reference_market_mock.assert_not_called()
                _split_reference_market_into_indexed_coins_mock.assert_called_once_with("details", True)
                _update_producer_last_activity_mock.assert_called_once_with(
                    index_trading.IndexActivity.REBALANCING_SKIPPED,
                    index_trading.RebalanceSkipDetails.NOT_ENOUGH_AVAILABLE_FOUNDS.value
                )
                _ensure_enough_funds_to_buy_after_selling_mock.reset_mock()
                _sell_indexed_coins_for_reference_market_mock.reset_mock()
                _split_reference_market_into_indexed_coins_mock.reset_mock()
                _update_producer_last_activity_mock.reset_mock()


async def test_ensure_enough_funds_to_buy_after_selling(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    with mock.patch.object(
            trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
            "get_traded_assets_holdings_value", mock.Mock(return_value=decimal.Decimal("2000"))
    ) as get_traded_assets_holdings_value_mock, mock.patch.object(
        consumer, "_get_symbols_and_amounts", mock.AsyncMock()
    ) as _get_symbols_and_amounts_mock:
        await consumer._ensure_enough_funds_to_buy_after_selling()
        get_traded_assets_holdings_value_mock.assert_called_once_with("USDT", None)
        _get_symbols_and_amounts_mock.assert_called_once_with(["BTC"], decimal.Decimal("2000"))


async def test_can_simply_buy_coins_without_selling(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    details = "details"
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
        "get_traded_assets_holdings_value", mock.Mock(return_value=decimal.Decimal("2000"))
    ) as get_traded_assets_holdings_value_mock:

        # no coins to simply buy
        with mock.patch.object(
            consumer, "_get_simple_buy_coins", return_value=[]
        ) as _get_simple_buy_coins_mock, mock.patch.object(
            trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
            "get_currency_portfolio", mock.Mock(return_value=mock.Mock(available=decimal.Decimal("160")))
        ) as get_currency_portfolio_mock:
            assert consumer._can_simply_buy_coins_without_selling(details) is False
            _get_simple_buy_coins_mock.assert_called_once_with(details)
            get_traded_assets_holdings_value_mock.assert_not_called()
            get_currency_portfolio_mock.assert_not_called()

        # there are coins to simply buy
        with mock.patch.object(
            mode, "get_target_ratio", return_value=decimal.Decimal("0.25")
        ) as get_target_ratio_mock, mock.patch.object(
            consumer, "_get_simple_buy_coins", return_value=["BTC"]
        ) as _get_simple_buy_coins_mock:

            # not enough free funds in portfolio to buy for 25% of 2000
            with mock.patch.object(
                trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
                "get_currency_portfolio", mock.Mock(return_value=mock.Mock(available=decimal.Decimal("160")))
            ) as get_currency_portfolio_mock:
                assert consumer._can_simply_buy_coins_without_selling(details) is False
                _get_simple_buy_coins_mock.assert_called_once_with(details)
                get_traded_assets_holdings_value_mock.assert_called_once_with("USDT", None)
                get_currency_portfolio_mock.assert_called_once_with("USDT")
                get_target_ratio_mock.assert_called_once_with("BTC")
                _get_simple_buy_coins_mock.reset_mock()
                get_traded_assets_holdings_value_mock.reset_mock()
                get_target_ratio_mock.reset_mock()

            # enough free funds in portfolio to buy for 25% of 2000 (using tolerance)
            with mock.patch.object(
                trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
                "get_currency_portfolio", mock.Mock(return_value=mock.Mock(available=decimal.Decimal("450")))
            ) as get_currency_portfolio_mock:
                assert consumer._can_simply_buy_coins_without_selling(details) is True
                _get_simple_buy_coins_mock.assert_called_once_with(details)
                get_traded_assets_holdings_value_mock.assert_called_once_with("USDT", None)
                get_currency_portfolio_mock.assert_called_once_with("USDT")
                get_target_ratio_mock.assert_called_once_with("BTC")
                _get_simple_buy_coins_mock.reset_mock()
                get_traded_assets_holdings_value_mock.reset_mock()
                get_target_ratio_mock.reset_mock()

            # more than enough free funds in portfolio to buy for 25% of 2000
            with mock.patch.object(
                trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
                "get_currency_portfolio", mock.Mock(return_value=mock.Mock(available=decimal.Decimal("600.811")))
            ) as get_currency_portfolio_mock:
                assert consumer._can_simply_buy_coins_without_selling(details) is True
                _get_simple_buy_coins_mock.assert_called_once_with(details)
                get_traded_assets_holdings_value_mock.assert_called_once_with("USDT", None)
                get_currency_portfolio_mock.assert_called_once_with("USDT")
                get_target_ratio_mock.assert_called_once_with("BTC")
                _get_simple_buy_coins_mock.reset_mock()
                get_traded_assets_holdings_value_mock.reset_mock()
                get_target_ratio_mock.reset_mock()

            # now having multiple coins to buy
            with  mock.patch.object(
                consumer, "_get_simple_buy_coins", return_value=["BTC", "ETH"]
            ) as _get_simple_buy_coins_mock:
                # enough funds for 1 but not 2 coins at 25%
                with mock.patch.object(
                    trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
                    "get_currency_portfolio",
                    mock.Mock(return_value=mock.Mock(available=decimal.Decimal("600.811")))
                ) as get_currency_portfolio_mock:
                    assert consumer._can_simply_buy_coins_without_selling(details) is False
                    _get_simple_buy_coins_mock.assert_called_once_with(details)
                    get_traded_assets_holdings_value_mock.assert_called_once_with("USDT", None)
                    get_currency_portfolio_mock.assert_called_once_with("USDT")
                    assert get_target_ratio_mock.call_count == 2
                    assert get_target_ratio_mock.mock_calls[0].args[0] == "BTC"
                    assert get_target_ratio_mock.mock_calls[1].args[0] == "ETH"
                    _get_simple_buy_coins_mock.reset_mock()
                    get_traded_assets_holdings_value_mock.reset_mock()
                    get_target_ratio_mock.reset_mock()

                # enough funds for 2 coins at 25%
                with mock.patch.object(
                    trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
                    "get_currency_portfolio",
                    mock.Mock(return_value=mock.Mock(available=decimal.Decimal("1000.811")))
                ) as get_currency_portfolio_mock:
                    assert consumer._can_simply_buy_coins_without_selling(details) is True
                    _get_simple_buy_coins_mock.assert_called_once_with(details)
                    get_traded_assets_holdings_value_mock.assert_called_once_with("USDT", None)
                    get_currency_portfolio_mock.assert_called_once_with("USDT")
                    assert get_target_ratio_mock.call_count == 2
                    assert get_target_ratio_mock.mock_calls[0].args[0] == "BTC"
                    assert get_target_ratio_mock.mock_calls[1].args[0] == "ETH"
                    _get_simple_buy_coins_mock.reset_mock()
                    get_traded_assets_holdings_value_mock.reset_mock()
                    get_target_ratio_mock.reset_mock()


async def test_get_simple_buy_coins(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    mode.indexed_coins = ["BTC", "ETH", "SOL"]
    assert consumer._get_simple_buy_coins({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {},
        index_trading.RebalanceDetails.ADD.value: {},
        index_trading.RebalanceDetails.SWAP.value: {},
        index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
    }) == []
    assert consumer._get_simple_buy_coins({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {},
        index_trading.RebalanceDetails.ADD.value: {"BTC": decimal.Decimal("0.2"), "ETH": decimal.Decimal("0.2")},
        index_trading.RebalanceDetails.SWAP.value: {},
        index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
    }) == ["BTC", "ETH"]
    # keep index coins order
    assert consumer._get_simple_buy_coins({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {"SOL": decimal.Decimal("0.2")},
        index_trading.RebalanceDetails.REMOVE.value: {},
        index_trading.RebalanceDetails.ADD.value: {"ETH": decimal.Decimal("0.2"), "BTC": decimal.Decimal("0.2")},
        index_trading.RebalanceDetails.SWAP.value: {},
        index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
    }) == ["BTC", "ETH", "SOL"]
    # TRX not in indexed coins: added at the end
    assert consumer._get_simple_buy_coins({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {"SOL": decimal.Decimal("0.1"), "TRX": decimal.Decimal("0.2")},
        index_trading.RebalanceDetails.REMOVE.value: {},
        index_trading.RebalanceDetails.ADD.value: {"ETH": decimal.Decimal("0.2"), "BTC": decimal.Decimal("0.5")},
        index_trading.RebalanceDetails.SWAP.value: {},
        index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
    }) == ["BTC", "ETH", "SOL", "TRX"]

    # don't return anything when other values are set
    assert consumer._get_simple_buy_coins({
        index_trading.RebalanceDetails.SELL_SOME.value: {"BTC": decimal.Decimal("0.2")},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {},
        index_trading.RebalanceDetails.ADD.value: {"ETH": decimal.Decimal("0.2")},
        index_trading.RebalanceDetails.SWAP.value: {},
        index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
    }) == []
    assert consumer._get_simple_buy_coins({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {"BTC": decimal.Decimal("0.2")},
        index_trading.RebalanceDetails.ADD.value: {"ETH": decimal.Decimal("0.2")},
        index_trading.RebalanceDetails.SWAP.value: {},
        index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
    }) == []
    assert consumer._get_simple_buy_coins({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {},
        index_trading.RebalanceDetails.ADD.value: {"ETH": decimal.Decimal("0.2")},
        index_trading.RebalanceDetails.SWAP.value: {"BTC": decimal.Decimal("0.2")},
        index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
    }) == []
    # whatever is in other values, return [] when forced rebalance
    assert consumer._get_simple_buy_coins({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {},
        index_trading.RebalanceDetails.ADD.value: {"ETH": decimal.Decimal("0.2")},
        index_trading.RebalanceDetails.SWAP.value: {"BTC": decimal.Decimal("0.2")},
        index_trading.RebalanceDetails.FORCED_REBALANCE.value: True,
    }) == []
    # should return [BTC, ETH] but doesn't because of forced rebalance
    assert consumer._get_simple_buy_coins({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {},
        index_trading.RebalanceDetails.ADD.value: {"BTC": decimal.Decimal("0.2"), "ETH": decimal.Decimal("0.2")},
        index_trading.RebalanceDetails.SWAP.value: {},
        index_trading.RebalanceDetails.FORCED_REBALANCE.value: True,
    }) == []


async def test_sell_indexed_coins_for_reference_market(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    orders = [
        mock.Mock(
            symbol="BTC/USDT",
            side=trading_enums.TradeOrderSide.SELL
        ),
        mock.Mock(
            symbol="ETH/USDT",
            side=trading_enums.TradeOrderSide.SELL
        )
    ]
    with mock.patch.object(
            octobot_trading.modes, "convert_assets_to_target_asset", mock.AsyncMock(return_value=orders)
    ) as convert_assets_to_target_asset_mock, mock.patch.object(
        trading_personal_data, "wait_for_order_fill", mock.AsyncMock()
    ) as wait_for_order_fill_mock, mock.patch.object(
        consumer, "_get_coins_to_sell", mock.Mock(return_value=[1, 2, 3])
    ) as _get_coins_to_sell_mock:
        details = {
            index_trading.RebalanceDetails.REMOVE.value: {}
        }
        assert await consumer._sell_indexed_coins_for_reference_market(details) == orders
        convert_assets_to_target_asset_mock.assert_called_once_with(
            mode, [1, 2, 3],
            consumer.exchange_manager.exchange_personal_data.portfolio_manager.reference_market, {}
        )
        assert wait_for_order_fill_mock.call_count == 2
        _get_coins_to_sell_mock.assert_called_once_with(details)
        convert_assets_to_target_asset_mock.reset_mock()
        wait_for_order_fill_mock.reset_mock()
        _get_coins_to_sell_mock.reset_mock()

        # with valid remove coins
        details = {
            index_trading.RebalanceDetails.REMOVE.value: {"BTC": 0.01},
            index_trading.RebalanceDetails.BUY_MORE.value: {},
            index_trading.RebalanceDetails.ADD.value: {},
            index_trading.RebalanceDetails.SWAP.value: {},
            index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
        }
        assert await consumer._sell_indexed_coins_for_reference_market(details) == orders + orders
        assert convert_assets_to_target_asset_mock.call_count == 2
        assert wait_for_order_fill_mock.call_count == 4
        _get_coins_to_sell_mock.assert_called_once_with(details)
        convert_assets_to_target_asset_mock.reset_mock()
        wait_for_order_fill_mock.reset_mock()
        _get_coins_to_sell_mock.reset_mock()

        with mock.patch.object(
                octobot_trading.modes, "convert_assets_to_target_asset", mock.AsyncMock(return_value=[])
        ) as convert_assets_to_target_asset_mock_2:
            # with remove coins that can't be sold
            details = {
                index_trading.RebalanceDetails.REMOVE.value: {"BTC": 0.01},
                index_trading.RebalanceDetails.BUY_MORE.value: {},
                index_trading.RebalanceDetails.ADD.value: {},
                index_trading.RebalanceDetails.SWAP.value: {},
                index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
            }
            with pytest.raises(trading_errors.MissingMinimalExchangeTradeVolume):
                assert await consumer._sell_indexed_coins_for_reference_market(details) == orders + orders
            convert_assets_to_target_asset_mock_2.assert_called_once_with(
                mode, ["BTC"],
                consumer.exchange_manager.exchange_personal_data.portfolio_manager.reference_market, {}
            )
            wait_for_order_fill_mock.assert_not_called()
            _get_coins_to_sell_mock.assert_not_called()


async def test_get_coins_to_sell(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    mode.indexed_coins = ["BTC", "ETH", "DOGE", "SHIB"]
    assert consumer._get_coins_to_sell({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {},
        index_trading.RebalanceDetails.ADD.value: {},
        index_trading.RebalanceDetails.SWAP.value: {},
        index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
    }) == ["BTC", "ETH", "DOGE", "SHIB"]
    assert consumer._get_coins_to_sell({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {},
        index_trading.RebalanceDetails.ADD.value: {},
        index_trading.RebalanceDetails.SWAP.value: {
            "BTC": "ETH"
        },
    }) == ["BTC"]
    assert consumer._get_coins_to_sell({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {
            "XRP": trading_constants.ONE_HUNDRED
        },
        index_trading.RebalanceDetails.ADD.value: {},
        index_trading.RebalanceDetails.SWAP.value: {
            "BTC": "ETH",
            "SOL": "ADA",
        },
        index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
    }) == ["BTC", "SOL"]
    assert consumer._get_coins_to_sell({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {},
        index_trading.RebalanceDetails.ADD.value: {},
        index_trading.RebalanceDetails.SWAP.value: {},
        index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
    }) == ["BTC", "ETH", "DOGE", "SHIB"]
    assert consumer._get_coins_to_sell({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {
            "XRP": trading_constants.ONE_HUNDRED
        },
        index_trading.RebalanceDetails.ADD.value: {},
        index_trading.RebalanceDetails.SWAP.value: {},
        index_trading.RebalanceDetails.FORCED_REBALANCE.value: False,
    }) == ["BTC", "ETH", "DOGE", "SHIB"]


async def test_resolve_swaps(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    mode.rebalance_trigger_min_ratio = decimal.Decimal("0.05")  # %5
    rebalance_details = {
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {},
        index_trading.RebalanceDetails.ADD.value: {},
        index_trading.RebalanceDetails.SWAP.value: {},
    }
    # regular full rebalance
    producer._resolve_swaps(rebalance_details)
    assert rebalance_details[index_trading.RebalanceDetails.SWAP.value] == {}

    # regular full rebalance with removed coins to sell
    rebalance_details[index_trading.RebalanceDetails.REMOVE.value] = {"SOL": decimal.Decimal("0.3")}
    producer._resolve_swaps(rebalance_details)
    assert rebalance_details[index_trading.RebalanceDetails.SWAP.value] == {}

    # rebalances with a coin swap only from ADD coin
    rebalance_details[index_trading.RebalanceDetails.ADD.value] = {"ADA": decimal.Decimal("0.3")}
    producer._resolve_swaps(rebalance_details)
    assert rebalance_details[index_trading.RebalanceDetails.SWAP.value] == {"SOL": "ADA"}

    # rebalances with a coin swap only from BUY_MORE coin
    rebalance_details[index_trading.RebalanceDetails.ADD.value] = {}
    rebalance_details[index_trading.RebalanceDetails.BUY_MORE.value] = {"ADA": decimal.Decimal("0.3")}
    producer._resolve_swaps(rebalance_details)
    assert rebalance_details[index_trading.RebalanceDetails.SWAP.value] == {"SOL": "ADA"}
    rebalance_details[index_trading.RebalanceDetails.BUY_MORE.value] = {}

    # rebalances with an incompatible coin swap (ratio too different)
    rebalance_details[index_trading.RebalanceDetails.BUY_MORE.value] = {"ADA": decimal.Decimal("0.1")}
    producer._resolve_swaps(rebalance_details)
    assert rebalance_details[index_trading.RebalanceDetails.SWAP.value] == {}
    rebalance_details[index_trading.RebalanceDetails.BUY_MORE.value] = {}

    # rebalances with an incompatible coin swap (ratio too different)
    rebalance_details[index_trading.RebalanceDetails.ADD.value] = {"ADA": decimal.Decimal("0.5")}
    producer._resolve_swaps(rebalance_details)
    assert rebalance_details[index_trading.RebalanceDetails.SWAP.value] == {}

    # rebalances with 2 removed coins: sell everything
    rebalance_details[index_trading.RebalanceDetails.REMOVE.value] = {
        "SOL": decimal.Decimal("0.3"),
        "XRP": decimal.Decimal("0.3"),
    }
    producer._resolve_swaps(rebalance_details)
    assert rebalance_details[index_trading.RebalanceDetails.SWAP.value] == {}

    # rebalances with 2 coin swaps: sell everything
    rebalance_details[index_trading.RebalanceDetails.ADD.value] = {
        "ADA": decimal.Decimal("0.3"),
        "ADA2": decimal.Decimal("0.3"),
    }
    producer._resolve_swaps(rebalance_details)
    assert rebalance_details[index_trading.RebalanceDetails.SWAP.value] == {}

    # rebalance with regular buy / sell more
    rebalance_details[index_trading.RebalanceDetails.BUY_MORE.value] = {"LTC": decimal.Decimal(1)}
    producer._resolve_swaps(rebalance_details)
    assert rebalance_details[index_trading.RebalanceDetails.SWAP.value] == {}

    # rebalance with regular buy / sell more
    rebalance_details[index_trading.RebalanceDetails.SELL_SOME.value] = {"BTC": decimal.Decimal(1)}
    producer._resolve_swaps(rebalance_details)
    assert rebalance_details[index_trading.RebalanceDetails.SWAP.value] == {}


async def test_split_reference_market_into_indexed_coins(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    # no indexed coin
    mode.indexed_coins = []
    details = {index_trading.RebalanceDetails.SWAP.value: {}}
    is_simple_buy_without_selling = False
    with mock.patch.object(
        consumer, "_get_symbols_and_amounts", mock.AsyncMock(
            side_effect=lambda coins, _: {f"{coin}/USDT": decimal.Decimal(i + 1) for i, coin in enumerate(coins)}
        )
    ) as _get_symbols_and_amounts_mock:
        with mock.patch.object(
            consumer, "_get_simple_buy_coins", mock.Mock()
        ) as _get_simple_buy_coins_mock:
            with mock.patch.object(
                    trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
                    "get_currency_portfolio", mock.Mock(return_value=mock.Mock(available=decimal.Decimal("2")))
            ) as get_currency_portfolio_mock, mock.patch.object(
                consumer, "_buy_coin", mock.AsyncMock(return_value=["order"])
            ) as _buy_coin_mock:
                with pytest.raises(trading_errors.MissingMinimalExchangeTradeVolume):
                    await consumer._split_reference_market_into_indexed_coins(details, is_simple_buy_without_selling)
                get_currency_portfolio_mock.assert_called_once_with("USDT")
                _buy_coin_mock.assert_not_called()
                _get_symbols_and_amounts_mock.assert_called_once()
                _get_symbols_and_amounts_mock.reset_mock()
                _get_simple_buy_coins_mock.assert_not_called()

            # coins to swap
            mode.indexed_coins = []
            details = {index_trading.RebalanceDetails.SWAP.value: {"BTC": "ETH", "ADA": "SOL"}}
            with mock.patch.object(
                    trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
                    "get_currency_portfolio", mock.Mock(return_value=mock.Mock(available=decimal.Decimal("2")))
            ) as get_currency_portfolio_mock, mock.patch.object(
                trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
                "get_traded_assets_holdings_value", mock.Mock(return_value=decimal.Decimal("2000"))
            ) as get_traded_assets_holdings_value_mock, mock.patch.object(
                consumer, "_buy_coin", mock.AsyncMock(return_value=["order"])
            ) as _buy_coin_mock:
                assert await consumer._split_reference_market_into_indexed_coins(
                    details, is_simple_buy_without_selling
                ) == ["order", "order"]
                _get_symbols_and_amounts_mock.assert_called_once()
                _get_symbols_and_amounts_mock.reset_mock()
                get_traded_assets_holdings_value_mock.assert_called_once_with("USDT", None)
                get_currency_portfolio_mock.assert_not_called()
                _get_simple_buy_coins_mock.assert_not_called()
                assert _buy_coin_mock.call_count == 2
                assert _buy_coin_mock.mock_calls[0].args == ("ETH/USDT", decimal.Decimal("1"))
                assert _buy_coin_mock.mock_calls[1].args == ("SOL/USDT", decimal.Decimal("2"))

            # no bought coin
            details = {index_trading.RebalanceDetails.SWAP.value: {}}
            mode.indexed_coins = ["ETH", "BTC"]
            with mock.patch.object(
                    trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
                    "get_currency_portfolio", mock.Mock(return_value=mock.Mock(available=decimal.Decimal("2")))
            ) as get_currency_portfolio_mock, mock.patch.object(
                consumer, "_buy_coin", mock.AsyncMock(return_value=[])
            ) as _buy_coin_mock:
                with pytest.raises(trading_errors.MissingMinimalExchangeTradeVolume):
                    await consumer._split_reference_market_into_indexed_coins(details, is_simple_buy_without_selling)
                _get_symbols_and_amounts_mock.assert_called_once()
                _get_symbols_and_amounts_mock.reset_mock()
                get_currency_portfolio_mock.assert_called_once_with("USDT")
                _get_simple_buy_coins_mock.assert_not_called()
                assert _buy_coin_mock.call_count == 2

            # bought coins
            mode.indexed_coins = ["ETH", "BTC"]
            with mock.patch.object(
                    trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
                    "get_currency_portfolio", mock.Mock(return_value=mock.Mock(available=decimal.Decimal("2")))
            ) as get_currency_portfolio_mock, mock.patch.object(
                consumer, "_buy_coin", mock.AsyncMock(return_value=["order"])
            ) as _buy_coin_mock:
                assert await consumer._split_reference_market_into_indexed_coins(
                    details, is_simple_buy_without_selling
                ) == ["order", "order"]
                _get_symbols_and_amounts_mock.assert_called_once()
                _get_symbols_and_amounts_mock.reset_mock()
                get_currency_portfolio_mock.assert_called_once_with("USDT")
                _get_simple_buy_coins_mock.assert_not_called()
                assert _buy_coin_mock.call_count == 2
                assert _buy_coin_mock.mock_calls[0].args[0] == "ETH/USDT"
                assert _buy_coin_mock.mock_calls[1].args[0] == "BTC/USDT"

        with mock.patch.object(
            consumer, "_get_simple_buy_coins", mock.Mock(return_value=["ETH"])
        ) as _get_simple_buy_coins_mock:
            # simple buy without selling => buying only ETH
            is_simple_buy_without_selling = True
            mode.indexed_coins = ["ETH", "BTC"]
            with mock.patch.object(
                    trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
                    "get_currency_portfolio", mock.Mock(return_value=mock.Mock(available=decimal.Decimal("2")))
            ) as get_currency_portfolio_mock, mock.patch.object(
                consumer, "_buy_coin", mock.AsyncMock(return_value=["order"])
            ) as _buy_coin_mock, mock.patch.object(
                trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
                "get_traded_assets_holdings_value", mock.Mock(return_value=decimal.Decimal("2000"))
            ) as get_traded_assets_holdings_value_mock:
                assert await consumer._split_reference_market_into_indexed_coins(
                    details, is_simple_buy_without_selling
                ) == ["order"]
                _get_symbols_and_amounts_mock.assert_called_once()
                _get_symbols_and_amounts_mock.reset_mock()
                get_currency_portfolio_mock.assert_not_called()
                get_traded_assets_holdings_value_mock.assert_called_once_with("USDT", None)
                _get_simple_buy_coins_mock.assert_called_once_with(details)
                assert _buy_coin_mock.call_count == 1
                assert _buy_coin_mock.mock_calls[0].args[0] == "ETH/USDT"


async def test_get_symbols_and_amounts(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["BTC/USDT"]
    ]
    mode.ensure_updated_coins_distribution()
    assert await consumer._get_symbols_and_amounts(["BTC"], decimal.Decimal(3000)) == {
        "BTC/USDT": decimal.Decimal(3)
    }
    with mock.patch.object(
            trading_personal_data, "get_up_to_date_price", mock.AsyncMock(return_value=decimal.Decimal(1000))
    ) as get_up_to_date_price_mock:
        assert await consumer._get_symbols_and_amounts(["BTC", "ETH"], decimal.Decimal(3000)) == {
            "BTC/USDT": decimal.Decimal(3)
        }
        assert get_up_to_date_price_mock.call_count == 2
        get_up_to_date_price_mock.reset_mock()
        trader.exchange_manager.exchange_config.traded_symbols = [
            commons_symbols.parse_symbol(symbol)
            for symbol in ["BTC/USDT", "ETH/USDT"]
        ]
        mode.ensure_updated_coins_distribution()
        assert await consumer._get_symbols_and_amounts(["BTC", "ETH"], decimal.Decimal(3000)) == {
            "BTC/USDT": decimal.Decimal("1.5"),
            "ETH/USDT": decimal.Decimal("1.5")
        }
        assert get_up_to_date_price_mock.call_count == 2

    # not enough funds
    with pytest.raises(trading_errors.MissingMinimalExchangeTradeVolume):
        await consumer._get_symbols_and_amounts(["BTC"], decimal.Decimal(0.0003))
    with mock.patch.object(
            trading_personal_data, "get_up_to_date_price", mock.AsyncMock(return_value=decimal.Decimal(0.000000001))
    ) as get_up_to_date_price_mock:
        with pytest.raises(trading_errors.MissingMinimalExchangeTradeVolume):
            await consumer._get_symbols_and_amounts(["BTC", "ETH"], decimal.Decimal(0.01))
        assert get_up_to_date_price_mock.call_count == 1

    # with ref market in coins config
    mode.trading_config = {
        "index_content": [
            {
                "name": "BTC",
                "value": 70
            },
            {
                "name": "USDT",
                "value": 30
            }
        ],
        "refresh_interval": 1,
        "required_strategies": [],
        "rebalance_trigger_min_percent": 5
    }
    mode.ensure_updated_coins_distribution()
    with mock.patch.object(
            trading_personal_data, "get_up_to_date_price", mock.AsyncMock(return_value=decimal.Decimal(1000))
    ) as get_up_to_date_price_mock:
        # USDT is not counted in orders to create (nothing to buy as USDT is the reference market everything is sold to)
        assert await consumer._get_symbols_and_amounts(["BTC", "USDT"], decimal.Decimal(3000)) == {
            "BTC/USDT": decimal.Decimal("2.1")
        }
        assert get_up_to_date_price_mock.call_count == 1


async def test_buy_coin(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    portfolio = trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio
    with mock.patch.object(mode, "create_order", mock.AsyncMock(side_effect=lambda x: x)) as create_order_mock:
        # coin already held
        portfolio["BTC"].available = decimal.Decimal(20)
        assert await consumer._buy_coin("BTC/USDT", decimal.Decimal(2)) == []
        create_order_mock.assert_not_called()

        # coin already partially held
        portfolio["BTC"].available = decimal.Decimal(0.5)
        orders = await consumer._buy_coin("BTC/USDT", decimal.Decimal(2))
        assert len(orders) == 1
        create_order_mock.assert_called_once_with(orders[0])
        assert isinstance(orders[0], trading_personal_data.BuyMarketOrder)
        assert orders[0].symbol == "BTC/USDT"
        assert orders[0].origin_price == decimal.Decimal(1000)
        assert orders[0].origin_quantity == decimal.Decimal("1.5")
        assert orders[0].total_cost == decimal.Decimal("1500")
        create_order_mock.reset_mock()

        # coin not already held
        portfolio["BTC"].available = decimal.Decimal(0)
        orders = await consumer._buy_coin("BTC/USDT", decimal.Decimal(2))
        assert len(orders) == 1
        create_order_mock.assert_called_once_with(orders[0])
        assert isinstance(orders[0], trading_personal_data.BuyMarketOrder)
        assert orders[0].symbol == "BTC/USDT"
        assert orders[0].origin_price == decimal.Decimal(1000)
        assert orders[0].origin_quantity == decimal.Decimal(2)
        assert orders[0].total_cost == decimal.Decimal("2000")
        create_order_mock.reset_mock()

        # given ideal_amount is lower
        orders = await consumer._buy_coin("BTC/USDT", decimal.Decimal("0.025"))
        assert len(orders) == 1
        create_order_mock.assert_called_once_with(orders[0])
        assert isinstance(orders[0], trading_personal_data.BuyMarketOrder)
        assert orders[0].symbol == "BTC/USDT"
        assert orders[0].origin_price == decimal.Decimal(1000)
        assert orders[0].origin_quantity == decimal.Decimal("0.025")  # use 100 instead of all 2000 USDT in pf
        assert orders[0].total_cost == decimal.Decimal("25")
        create_order_mock.reset_mock()

        # adapt for fees
        fee_usdt_cost = decimal.Decimal(10)
        with mock.patch.object(
                consumer.exchange_manager.exchange, "get_trade_fee", mock.Mock(return_value={
                    trading_enums.FeePropertyColumns.COST.value: str(fee_usdt_cost),
                    trading_enums.FeePropertyColumns.CURRENCY.value: "USDT",
                })
        ) as get_trade_fee_mock:
            orders = await consumer._buy_coin("BTC/USDT", decimal.Decimal("0.5"))
            assert get_trade_fee_mock.call_count == 2
            assert len(orders) == 1
            create_order_mock.assert_called_once_with(orders[0])
            assert isinstance(orders[0], trading_personal_data.BuyMarketOrder)
            assert orders[0].symbol == "BTC/USDT"
            assert orders[0].origin_price == decimal.Decimal(1000)
            # no adaptation needed as not all funds are used (1/4 ratio)
            assert orders[0].origin_quantity == decimal.Decimal("0.5")
            assert orders[0].total_cost == decimal.Decimal("500")
            create_order_mock.reset_mock()
            get_trade_fee_mock.reset_mock()

            orders = await consumer._buy_coin("BTC/USDT", decimal.Decimal(2))
            assert get_trade_fee_mock.call_count == 2
            assert len(orders) == 1
            create_order_mock.assert_called_once_with(orders[0])
            assert isinstance(orders[0], trading_personal_data.BuyMarketOrder)
            assert orders[0].symbol == "BTC/USDT"
            assert orders[0].origin_price == decimal.Decimal(1000)
            btc_fees = fee_usdt_cost / orders[0].origin_price
            # 2 - fees denominated in BTC
            assert orders[0].origin_quantity == decimal.Decimal("2") - btc_fees * trading_constants.FEES_SAFETY_MARGIN
            assert orders[0].total_cost == decimal.Decimal('1987.5000')
            create_order_mock.reset_mock()


async def test_buy_coin_using_limit_order(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    portfolio = trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio.portfolio
    with mock.patch.object(
            mode,
            "create_order", mock.AsyncMock(side_effect=lambda x: x)
    ) as create_order_mock, mock.patch.object(
            mode.exchange_manager.exchange,
            "is_market_open_for_order_type", mock.Mock(return_value=False)
    ) as is_market_open_for_order_type_mock:
        # coin already held
        portfolio["BTC"].available = decimal.Decimal(20)
        assert await consumer._buy_coin("BTC/USDT", decimal.Decimal(2)) == []
        create_order_mock.assert_not_called()
        is_market_open_for_order_type_mock.assert_not_called()

        # coin already partially held: buy more using limit order
        portfolio["BTC"].available = decimal.Decimal(0.5)
        orders = await consumer._buy_coin("BTC/USDT", decimal.Decimal(2))
        assert len(orders) == 1
        is_market_open_for_order_type_mock.assert_called_once_with("BTC/USDT", trading_enums.TraderOrderType.BUY_MARKET)
        create_order_mock.assert_called_once_with(orders[0])
        assert isinstance(orders[0], trading_personal_data.BuyLimitOrder)
        assert orders[0].symbol == "BTC/USDT"
        assert orders[0].origin_price == decimal.Decimal(1005)  # a bit above market price to instant fill
        assert orders[0].origin_quantity == decimal.Decimal('1.49253731')  # reduced a bit to compensate price increase
        assert decimal.Decimal("1499.99999") < orders[0].total_cost < decimal.Decimal("1500")
        create_order_mock.reset_mock()
        is_market_open_for_order_type_mock.reset_mock()

        # coin not already held
        portfolio["BTC"].available = decimal.Decimal(0)
        orders = await consumer._buy_coin("BTC/USDT", decimal.Decimal(2))
        assert len(orders) == 1
        is_market_open_for_order_type_mock.assert_called_once_with("BTC/USDT", trading_enums.TraderOrderType.BUY_MARKET)
        create_order_mock.assert_called_once_with(orders[0])
        assert isinstance(orders[0], trading_personal_data.BuyLimitOrder)
        assert orders[0].symbol == "BTC/USDT"
        assert orders[0].origin_price == decimal.Decimal('1005.000')
        assert orders[0].origin_quantity == decimal.Decimal('1.99004975')
        assert decimal.Decimal("1999.99999") < orders[0].total_cost < decimal.Decimal("2000")
        create_order_mock.reset_mock()
        is_market_open_for_order_type_mock.reset_mock()

        # given ideal_amount is lower
        orders = await consumer._buy_coin("BTC/USDT", decimal.Decimal("0.025"))
        assert len(orders) == 1
        is_market_open_for_order_type_mock.assert_called_once_with("BTC/USDT", trading_enums.TraderOrderType.BUY_MARKET)
        create_order_mock.assert_called_once_with(orders[0])
        assert isinstance(orders[0], trading_personal_data.BuyLimitOrder)
        assert orders[0].symbol == "BTC/USDT"
        assert orders[0].origin_price == decimal.Decimal(1005)
        assert orders[0].origin_quantity == decimal.Decimal('0.02487562')  # use 100 instead of all 2000 USDT in pf
        assert decimal.Decimal('24.999') < orders[0].total_cost < decimal.Decimal("25")
        create_order_mock.reset_mock()
        is_market_open_for_order_type_mock.reset_mock()

        # adapt for fees
        fee_usdt_cost = decimal.Decimal(10)
        with mock.patch.object(
                consumer.exchange_manager.exchange, "get_trade_fee", mock.Mock(return_value={
                    trading_enums.FeePropertyColumns.COST.value: str(fee_usdt_cost),
                    trading_enums.FeePropertyColumns.CURRENCY.value: "USDT",
                })
        ) as get_trade_fee_mock:
            orders = await consumer._buy_coin("BTC/USDT", decimal.Decimal("0.5"))
            assert get_trade_fee_mock.call_count == 2
            assert len(orders) == 1
            is_market_open_for_order_type_mock.assert_called_once_with("BTC/USDT", trading_enums.TraderOrderType.BUY_MARKET)
            create_order_mock.assert_called_once_with(orders[0])
            assert isinstance(orders[0], trading_personal_data.BuyLimitOrder)
            assert orders[0].symbol == "BTC/USDT"
            assert orders[0].origin_price == decimal.Decimal(1005)
            # no adaptation needed as not all funds are used (1/4 ratio)
            assert orders[0].origin_quantity == decimal.Decimal('0.49751243')
            assert decimal.Decimal('499.999') < orders[0].total_cost < decimal.Decimal("500")
            create_order_mock.reset_mock()
            get_trade_fee_mock.reset_mock()
            is_market_open_for_order_type_mock.reset_mock()

            orders = await consumer._buy_coin("BTC/USDT", decimal.Decimal(2))
            assert get_trade_fee_mock.call_count == 2
            assert len(orders) == 1
            is_market_open_for_order_type_mock.assert_called_once_with("BTC/USDT", trading_enums.TraderOrderType.BUY_MARKET)
            create_order_mock.assert_called_once_with(orders[0])
            assert isinstance(orders[0], trading_personal_data.BuyLimitOrder)
            assert orders[0].symbol == "BTC/USDT"
            assert orders[0].origin_price == decimal.Decimal(1005)
            # 2 - fees denominated in BTC
            symbol_market = trader.exchange_manager.exchange.get_market_status(orders[0].symbol, with_fixer=False)
            assert orders[0].origin_quantity == trading_personal_data.decimal_adapt_quantity(
                symbol_market,
                (
                    decimal.Decimal("2000") - fee_usdt_cost * trading_constants.FEES_SAFETY_MARGIN
                ) / orders[0].origin_price
            )
            assert decimal.Decimal('1985') < orders[0].total_cost < decimal.Decimal('1990')
            create_order_mock.reset_mock()
            is_market_open_for_order_type_mock.reset_mock()


async def _get_tools(symbol="BTC/USDT"):
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
        data_files=[os.path.join(test_config.TEST_CONFIG_FOLDER,
                                 "AbstractExchangeHistoryCollector_1586017993.616272.data")])
    exchange_manager.exchange = exchanges.ExchangeSimulator(
        exchange_manager.config, exchange_manager, backtesting
    )
    await exchange_manager.exchange.initialize()
    exchange_manager.exchange_config.set_config_traded_pairs()
    for exchange_channel_class_type in [exchanges_channel.ExchangeChannel, exchanges_channel.TimeFrameExchangeChannel]:
        await channel_util.create_all_subclasses_channel(exchange_channel_class_type, exchanges_channel.set_chan,
                                                         exchange_manager=exchange_manager)

    trader = exchanges.TraderSimulator(config, exchange_manager)
    await trader.initialize()
    exchange_manager.exchange_personal_data.portfolio_manager.reference_market = "USDT"

    mode = Mode.IndexTradingMode(config, exchange_manager)
    mode.symbol = None if mode.get_is_symbol_wildcard() else symbol
    # trading mode is not initialized: to be initialized with the required config in tests

    # add mode to exchange manager so that it can be stopped and freed from memory
    exchange_manager.trading_modes.append(mode)

    # set BTC/USDT price at 1000 USDT
    trading_api.force_set_mark_price(exchange_manager, symbol, 1000)

    return mode, trader


async def _init_mode(tools, config):
    mode, trader = tools
    await mode.initialize(trading_config=config)
    return mode, mode.producers[0], mode.get_trading_mode_consumers()[0], trader


async def _stop(exchange_manager):
    for importer in backtesting_api.get_importers(exchange_manager.exchange.backtesting):
        await backtesting_api.stop_importer(importer)
    await exchange_manager.exchange.backtesting.stop()
    await exchange_manager.stop()


async def test_automatically_update_historical_config_on_set_intervals(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    
    # Test with SELL_REMOVED_INDEX_COINS_AS_SOON_AS_POSSIBLE policy
    mode.synchronization_policy = index_trading.SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_AS_SOON_AS_POSSIBLE
    with mock.patch.object(mode, "supports_historical_config", mock.Mock(return_value=True)) as supports_historical_config_mock:
        assert mode.automatically_update_historical_config_on_set_intervals() is True
        supports_historical_config_mock.assert_called_once()
        supports_historical_config_mock.reset_mock()
    
    with mock.patch.object(mode, "supports_historical_config", mock.Mock(return_value=False)) as supports_historical_config_mock:
        assert mode.automatically_update_historical_config_on_set_intervals() is False
        supports_historical_config_mock.assert_called_once()
        supports_historical_config_mock.reset_mock()
    
    # Test with SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE policy
    mode.synchronization_policy = index_trading.SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE
    with mock.patch.object(mode, "supports_historical_config", mock.Mock(return_value=True)) as supports_historical_config_mock:
        assert mode.automatically_update_historical_config_on_set_intervals() is False
        supports_historical_config_mock.assert_called_once()
        supports_historical_config_mock.reset_mock()
    
    with mock.patch.object(mode, "supports_historical_config", mock.Mock(return_value=False)) as supports_historical_config_mock:
        assert mode.automatically_update_historical_config_on_set_intervals() is False
        supports_historical_config_mock.assert_called_once()
        supports_historical_config_mock.reset_mock()


async def test_ensure_updated_coins_distribution(tools):
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, {}))
    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["ETH/USDT", "SOL/USDT", "BTC/USDT"]
    ]
    distribution = [
        {
            index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
            index_trading.index_distribution.DISTRIBUTION_VALUE: 50
        },
        {
            index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
            index_trading.index_distribution.DISTRIBUTION_VALUE: 30
        },
        {
            index_trading.index_distribution.DISTRIBUTION_NAME: "SOL",
            index_trading.index_distribution.DISTRIBUTION_VALUE: 20
        },
    ]
    with mock.patch.object(mode, "_get_supported_distribution", mock.Mock(return_value=distribution)) as _get_supported_distribution_mock:
        mode.ensure_updated_coins_distribution()
        _get_supported_distribution_mock.assert_called_once()
        _get_supported_distribution_mock.reset_mock()
        assert mode.ratio_per_asset == {
            "BTC": {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 50
            },
            "ETH": {
                index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 30
            },
            "SOL": {
                index_trading.index_distribution.DISTRIBUTION_NAME: "SOL",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 20
            }
        }
        assert mode.total_ratio_per_asset == 100
        assert mode.indexed_coins == ["BTC", "ETH", "SOL"]
    
    # include ref market in distribution
    distribution = [
        {
            index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
            index_trading.index_distribution.DISTRIBUTION_VALUE: 50
        },
        {
            index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
            index_trading.index_distribution.DISTRIBUTION_VALUE: 30
        },
        {
            index_trading.index_distribution.DISTRIBUTION_NAME: "USDT",
            index_trading.index_distribution.DISTRIBUTION_VALUE: 20
        },
    ]
    with mock.patch.object(mode, "_get_supported_distribution", mock.Mock(return_value=distribution)) as _get_supported_distribution_mock:
        mode.ensure_updated_coins_distribution()
        _get_supported_distribution_mock.assert_called_once()
        _get_supported_distribution_mock.reset_mock()
        assert mode.ratio_per_asset == {
            "BTC": {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 50
            },
            "ETH": {
                index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 30
            },
            "USDT": {
                index_trading.index_distribution.DISTRIBUTION_NAME: "USDT",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 20
            }
        }
        assert mode.total_ratio_per_asset == 100
        assert mode.indexed_coins == ["BTC", "ETH", "USDT"]


async def test_get_supported_distribution(tools):
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, {}))
    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT"]
    ]
    mode.trading_config = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT:  [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 25
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 25
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "SOL",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 25
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "ADA",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 25
            },
        ]
    }
    with mock.patch.object(mode, "get_ideal_distribution", mock.Mock(wraps=mode.get_ideal_distribution)) as get_ideal_distribution_mock:
        # no ideal distribution: return uniform distribution over traded assets
        assert mode._get_supported_distribution(False, False) == mode.trading_config[
            index_trading.IndexTradingModeProducer.INDEX_CONTENT
        ]
        get_ideal_distribution_mock.assert_called_once()

    mode.trading_config = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT:  [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 50
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 30
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "USDT",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 20
            },
        ]
    }
    with mock.patch.object(mode, "get_ideal_distribution", mock.Mock(wraps=mode.get_ideal_distribution)) as get_ideal_distribution_mock:
        assert mode._get_supported_distribution(False, False) == mode.trading_config[
            index_trading.IndexTradingModeProducer.INDEX_CONTENT
        ]
        get_ideal_distribution_mock.assert_called_once()

    mode.trading_config = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT:  [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 50
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 30
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "USDT",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 20
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "PLOP", # not traded
                index_trading.index_distribution.DISTRIBUTION_VALUE: 20
            },
        ]
    }
    with mock.patch.object(mode, "get_ideal_distribution", mock.Mock(wraps=mode.get_ideal_distribution)) as get_ideal_distribution_mock:
        assert mode._get_supported_distribution(False, False) == [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 50
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 30
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "USDT",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 20
            },
            # {
            #     index_trading.index_distribution.DISTRIBUTION_NAME: "PLOP", # not traded
            #     index_trading.index_distribution.DISTRIBUTION_VALUE: 20
            # },
        ]
        get_ideal_distribution_mock.assert_called_once()

    mode.trading_config = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT:  [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 50
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 30
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "USDT",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 20
            },
        ]
    }

    # synchronization policy is not SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE
    mode.synchronization_policy = index_trading.SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_AS_SOON_AS_POSSIBLE
    with mock.patch.object(mode, "get_ideal_distribution", mock.Mock(wraps=mode.get_ideal_distribution)) as get_ideal_distribution_mock:
        with mock.patch.object(mode, "_get_currently_applied_historical_config_according_to_holdings", mock.Mock()) as _get_currently_applied_historical_config_according_to_holdings_mock, \
            mock.patch.object(mode, "get_historical_configs", mock.Mock()) as get_historical_configs_mock:
            assert mode._get_supported_distribution(True, False) == mode.trading_config[
                index_trading.IndexTradingModeProducer.INDEX_CONTENT
            ]
            get_ideal_distribution_mock.assert_called_once()
            _get_currently_applied_historical_config_according_to_holdings_mock.assert_not_called()
            get_historical_configs_mock.assert_not_called()
            _get_currently_applied_historical_config_according_to_holdings_mock.reset_mock()
            get_historical_configs_mock.reset_mock()
            get_ideal_distribution_mock.reset_mock()
            assert mode._get_supported_distribution(False, True) == mode.trading_config[
                index_trading.IndexTradingModeProducer.INDEX_CONTENT
            ]
            get_ideal_distribution_mock.assert_called_once()
            _get_currently_applied_historical_config_according_to_holdings_mock.assert_not_called()
            get_historical_configs_mock.assert_not_called()
    
    # synchronization policy is SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE
    mode.synchronization_policy = index_trading.SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE
    holding_adapted_config = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 50
            },
        ]
    }
    with mock.patch.object(mode, "get_ideal_distribution", mock.Mock(wraps=mode.get_ideal_distribution)) as get_ideal_distribution_mock:
        with mock.patch.object(mode, "_get_currently_applied_historical_config_according_to_holdings", mock.Mock(return_value=holding_adapted_config)) as _get_currently_applied_historical_config_according_to_holdings_mock, \
            mock.patch.object(mode, "get_historical_configs", mock.Mock()) as get_historical_configs_mock:
            assert mode._get_supported_distribution(True, False) == holding_adapted_config[
                index_trading.IndexTradingModeProducer.INDEX_CONTENT
            ]
            assert get_ideal_distribution_mock.call_count == 2
            _get_currently_applied_historical_config_according_to_holdings_mock.assert_called_once_with(
                mode.trading_config, {'ADA', 'BTC', 'SOL', 'USDT', 'ETH'}
            )
            get_historical_configs_mock.assert_not_called()
            get_ideal_distribution_mock.reset_mock()
        
        # with historical configs
        latest_config = {
            index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
                {
                    index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
                    index_trading.index_distribution.DISTRIBUTION_VALUE: 50
                },
            ]
        }
        historical_configs = [
            latest_config,
            holding_adapted_config,

        ]
        with mock.patch.object(mode, "_get_currently_applied_historical_config_according_to_holdings", mock.Mock()) as _get_currently_applied_historical_config_according_to_holdings_mock, \
            mock.patch.object(mode, "get_historical_configs", mock.Mock(return_value=historical_configs)) as get_historical_configs_mock:
            assert mode._get_supported_distribution(False, True) == latest_config[
                index_trading.IndexTradingModeProducer.INDEX_CONTENT
            ]
            assert get_ideal_distribution_mock.call_count == 3
            _get_currently_applied_historical_config_according_to_holdings_mock.assert_not_called()
            get_historical_configs_mock.assert_called_once_with(
                0, mode.exchange_manager.exchange.get_exchange_current_time()
            )
            get_ideal_distribution_mock.reset_mock()

        # without historical configs
        with mock.patch.object(mode, "_get_currently_applied_historical_config_according_to_holdings", mock.Mock()) as _get_currently_applied_historical_config_according_to_holdings_mock, \
            mock.patch.object(mode, "get_historical_configs", mock.Mock(return_value=[])) as get_historical_configs_mock:
            # use current config
            assert mode._get_supported_distribution(False, True) == mode.trading_config[
                index_trading.IndexTradingModeProducer.INDEX_CONTENT
            ]
            assert get_ideal_distribution_mock.call_count == 2
            _get_currently_applied_historical_config_according_to_holdings_mock.assert_not_called()
            get_historical_configs_mock.assert_called_once_with(
                0, mode.exchange_manager.exchange.get_exchange_current_time()
            )
            get_ideal_distribution_mock.reset_mock()


async def test_get_currently_applied_historical_config_according_to_holdings(tools):
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, {}))
    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT"]
    ]
    traded_bases = set(
        symbol.base
        for symbol in trader.exchange_manager.exchange_config.traded_symbols
    )
    # 1. using latest config
    with mock.patch.object(mode, "_is_index_config_applied", mock.Mock(return_value=True)) as _is_index_config_applied_mock:
        assert mode._get_currently_applied_historical_config_according_to_holdings(
            mode.trading_config, traded_bases
        ) == mode.trading_config
        _is_index_config_applied_mock.assert_called_once_with(mode.trading_config, traded_bases)

    # 2. using historical configs
    with mock.patch.object(mode, "_is_index_config_applied", mock.Mock(return_value=False)) as _is_index_config_applied_mock, mock.patch.object(mode.exchange_manager.exchange, "get_exchange_current_time", mock.Mock(return_value=2)) as get_exchange_current_time_mock:
        # 2.1. no historical configs
        assert mode._get_currently_applied_historical_config_according_to_holdings(
            mode.trading_config, traded_bases
        ) == mode.trading_config
        _is_index_config_applied_mock.assert_called_once_with(mode.trading_config, traded_bases)
        _is_index_config_applied_mock.reset_mock()
        get_exchange_current_time_mock.assert_called_once()
        get_exchange_current_time_mock.reset_mock()

        # 2.2. with historical configs but as _is_index_config_applied always return False, fallback to current config
        hist_config_1 = {
            index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
                {
                    index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                    index_trading.index_distribution.DISTRIBUTION_VALUE: 50
                },
                {
                    index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
                    index_trading.index_distribution.DISTRIBUTION_VALUE: 30
                },
            ]
        }
        hist_config_2 = {
            index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
                {
                    index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                    index_trading.index_distribution.DISTRIBUTION_VALUE: 50
                },
            ]
        }
        commons_configuration.add_historical_tentacle_config(mode.trading_config, 1, hist_config_1)
        commons_configuration.add_historical_tentacle_config(mode.trading_config, 2, hist_config_2)
        mode.historical_master_config = mode.trading_config
        assert mode._get_currently_applied_historical_config_according_to_holdings(
            mode.trading_config, traded_bases
        ) == mode.trading_config
        assert _is_index_config_applied_mock.call_count == 3
        assert _is_index_config_applied_mock.mock_calls[0].args[0] == mode.trading_config
        assert _is_index_config_applied_mock.mock_calls[1].args[0] == hist_config_2
        assert _is_index_config_applied_mock.mock_calls[2].args[0] == hist_config_1
        _is_index_config_applied_mock.reset_mock()
        get_exchange_current_time_mock.assert_called_once()
        get_exchange_current_time_mock.reset_mock()

        __is_index_config_applied_calls = []
        accepted_config_index = 1
        def __is_index_config_applied(*args):
            __is_index_config_applied_calls.append(1)
            if len(__is_index_config_applied_calls) - 1 >= accepted_config_index:
                return True
            return False

        # 2.3. with historical configs using historical config
        with mock.patch.object(mode, "_is_index_config_applied", mock.Mock(side_effect=__is_index_config_applied)) as _is_index_config_applied_mock:
            # 1. use most up to date config
            assert mode._get_currently_applied_historical_config_according_to_holdings(
                mode.trading_config, traded_bases
            ) == hist_config_2
            assert _is_index_config_applied_mock.call_count == 2
            assert _is_index_config_applied_mock.mock_calls[0].args[0] == mode.trading_config
            assert _is_index_config_applied_mock.mock_calls[1].args[0] == hist_config_2
            _is_index_config_applied_mock.reset_mock()
            get_exchange_current_time_mock.assert_called_once()
            get_exchange_current_time_mock.reset_mock()

        __is_index_config_applied_calls.clear()
        accepted_config_index = 2
        with mock.patch.object(mode, "_is_index_config_applied", mock.Mock(side_effect=__is_index_config_applied)) as _is_index_config_applied_mock:
            # 2. use oldest config
            assert mode._get_currently_applied_historical_config_according_to_holdings(
                mode.trading_config, traded_bases
            ) == hist_config_1
            assert _is_index_config_applied_mock.call_count == 3
            assert _is_index_config_applied_mock.mock_calls[0].args[0] == mode.trading_config
            assert _is_index_config_applied_mock.mock_calls[1].args[0] == hist_config_2
            assert _is_index_config_applied_mock.mock_calls[2].args[0] == hist_config_1
            _is_index_config_applied_mock.reset_mock()


async def test_is_index_config_applied(tools):
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, {}))
    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT"]
    ]
    traded_bases = set(
        symbol.base
        for symbol in trader.exchange_manager.exchange_config.traded_symbols
    )
    
    # Test 1: No ideal distribution - should return False
    config_without_distribution = {}
    assert mode._is_index_config_applied(config_without_distribution, traded_bases) is False
    
    # Test 2: Empty ideal distribution - should return False
    config_with_empty_distribution = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: []
    }
    assert mode._is_index_config_applied(config_with_empty_distribution, traded_bases) is False
    
    # Test 3: Distribution with only non-traded assets - should return False
    config_with_non_traded_assets = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "NON_TRADED_COIN",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 100
            }
        ]
    }
    assert mode._is_index_config_applied(config_with_non_traded_assets, traded_bases) is False
    
    # Test 4: Distribution with zero total ratio - should return False
    config_with_zero_total = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 0
            }
        ]
    }
    assert mode._is_index_config_applied(config_with_zero_total, traded_bases) is False
    
    # Test 5: Valid distribution with holdings matching target ratios
    config_with_valid_distribution = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 60
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 40
            }
        ]
    }
    
    # Mock holdings ratios to match target ratios exactly
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
        "get_holdings_ratio", mock.Mock(side_effect=lambda coin, **kwargs: {
            "BTC": decimal.Decimal("0.6"),  # 60% target
            "ETH": decimal.Decimal("0.4"),  # 40% target
        }.get(coin, decimal.Decimal("0")))
    ) as get_holdings_ratio_mock:
        assert mode._is_index_config_applied(config_with_valid_distribution, traded_bases) is True
        assert get_holdings_ratio_mock.call_count == 2
        assert get_holdings_ratio_mock.mock_calls[0].args[0] == "BTC"
        assert get_holdings_ratio_mock.mock_calls[1].args[0] == "ETH"
        get_holdings_ratio_mock.reset_mock()
    
    # Test 6: Valid distribution with holdings within tolerance range
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
        "get_holdings_ratio", mock.Mock(side_effect=lambda coin, **kwargs: {
            "BTC": decimal.Decimal("0.62"),  # 60% target + 2% (within 5% tolerance)
            "ETH": decimal.Decimal("0.38"),  # 40% target - 2% (within 5% tolerance)
        }.get(coin, decimal.Decimal("0")))
    ) as get_holdings_ratio_mock:
        assert mode._is_index_config_applied(config_with_valid_distribution, traded_bases) is True
        assert get_holdings_ratio_mock.call_count == 2
        get_holdings_ratio_mock.reset_mock()
    
    # Test 7: Holdings outside tolerance range - should return False
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
        "get_holdings_ratio", mock.Mock(side_effect=lambda coin, **kwargs: {
            "BTC": decimal.Decimal("0.68"),  # 60% target + 8% (outside 5% tolerance)
            "ETH": decimal.Decimal("0.32"),  # 40% target - 8% (outside 5% tolerance)
        }.get(coin, decimal.Decimal("0")))
    ) as get_holdings_ratio_mock:
        assert mode._is_index_config_applied(config_with_valid_distribution, traded_bases) is False
        assert get_holdings_ratio_mock.call_count == 1  # only BTC is considered
        get_holdings_ratio_mock.assert_called_once_with("BTC", traded_symbols_only=True)
        get_holdings_ratio_mock.reset_mock()
    
    # Test 8: Missing coin in portfolio - should return False
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
        "get_holdings_ratio", mock.Mock(side_effect=lambda coin, **kwargs: {
            "BTC": decimal.Decimal("0.6"),  # 60% target
            "ETH": decimal.Decimal("0"),     # Missing ETH
        }.get(coin, decimal.Decimal("0")))
    ) as get_holdings_ratio_mock:
        assert mode._is_index_config_applied(config_with_valid_distribution, traded_bases) is False
        assert get_holdings_ratio_mock.call_count == 2
        get_holdings_ratio_mock.reset_mock()
    
    # Test 9: Too much of a coin in portfolio - should return False
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
        "get_holdings_ratio", mock.Mock(side_effect=lambda coin, **kwargs: {
            "BTC": decimal.Decimal("0.6"),  # 60% target: OK
            "ETH": decimal.Decimal("0.3"),  # 40% target - 10% (too little)
        }.get(coin, decimal.Decimal("0")))
    ) as get_holdings_ratio_mock:
        assert mode._is_index_config_applied(config_with_valid_distribution, traded_bases) is False
        assert get_holdings_ratio_mock.call_count == 2  # BTC and ETH considered
        assert get_holdings_ratio_mock.mock_calls[0].args[0] == "BTC"
        assert get_holdings_ratio_mock.mock_calls[1].args[0] == "ETH"
        get_holdings_ratio_mock.reset_mock()
    
    # Test 10a: Custom rebalance trigger ratio in config from REBALANCE_TRIGGER_MIN_PERCENT
    config_with_custom_trigger = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 50
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 50
            }
        ],
        index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_MIN_PERCENT: 10.0  # 10% tolerance
    }
    
    # Holdings within 10% tolerance
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
        "get_holdings_ratio", mock.Mock(side_effect=lambda coin, **kwargs: {
            "BTC": decimal.Decimal("0.57"),  # 50% target + 7% (within 10% tolerance)
            "ETH": decimal.Decimal("0.43"),  # 50% target - 7% (within 10% tolerance)
        }.get(coin, decimal.Decimal("0")))
    ) as get_holdings_ratio_mock:
        assert mode._is_index_config_applied(config_with_custom_trigger, traded_bases) is True
        assert get_holdings_ratio_mock.call_count == 2
        get_holdings_ratio_mock.reset_mock()
    
    # Holdings outside 10% tolerance
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
        "get_holdings_ratio", mock.Mock(side_effect=lambda coin, **kwargs: {
            "BTC": decimal.Decimal("0.65"),  # 50% target + 15% (outside 10% tolerance)
            "ETH": decimal.Decimal("0.35"),  # 50% target - 15% (outside 10% tolerance)
        }.get(coin, decimal.Decimal("0")))
    ) as get_holdings_ratio_mock:
        assert mode._is_index_config_applied(config_with_custom_trigger, traded_bases) is False
        assert get_holdings_ratio_mock.call_count == 1  # only BTC is considered
        get_holdings_ratio_mock.assert_called_once_with("BTC", traded_symbols_only=True)
        get_holdings_ratio_mock.reset_mock()
    
    # Test 10b: Custom rebalance trigger ratio in config from REBALANCE_TRIGGER_MIN_PERCENT
    config_with_custom_trigger = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 50
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 50
            }
        ],
        index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILES: [
            {
                index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_NAME: "profile-1",
                index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_MIN_PERCENT: 10.0  # 10% tolerance
            }
        ],
        index_trading.IndexTradingModeProducer.SELECTED_REBALANCE_TRIGGER_PROFILE: "profile-1",
        index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_MIN_PERCENT: 99.0  # 99% tolerance
    }
    
    # Holdings within 10% tolerance (profile 1)
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
        "get_holdings_ratio", mock.Mock(side_effect=lambda coin, **kwargs: {
            "BTC": decimal.Decimal("0.57"),  # 50% target + 7% (within 10% tolerance)
            "ETH": decimal.Decimal("0.43"),  # 50% target - 7% (within 10% tolerance)
        }.get(coin, decimal.Decimal("0")))
    ) as get_holdings_ratio_mock:
        assert mode._is_index_config_applied(config_with_custom_trigger, traded_bases) is True
        assert get_holdings_ratio_mock.call_count == 2
        get_holdings_ratio_mock.reset_mock()
    
    # Holdings outside 10% tolerance (profile 1)
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
        "get_holdings_ratio", mock.Mock(side_effect=lambda coin, **kwargs: {
            "BTC": decimal.Decimal("0.65"),  # 50% target + 15% (outside 10% tolerance)
            "ETH": decimal.Decimal("0.35"),  # 50% target - 15% (outside 10% tolerance)
        }.get(coin, decimal.Decimal("0")))
    ) as get_holdings_ratio_mock:
        assert mode._is_index_config_applied(config_with_custom_trigger, traded_bases) is False
        assert get_holdings_ratio_mock.call_count == 1  # only BTC is considered
        get_holdings_ratio_mock.assert_called_once_with("BTC", traded_symbols_only=True)
        get_holdings_ratio_mock.reset_mock()
    
    # Test 11: Mixed traded and non-traded assets
    config_with_mixed_assets = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "BTC",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 60
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "ETH",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 30
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "NON_TRADED_COIN",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 10
            }
        ]
    }
    
    # Should only consider traded assets (BTC and ETH)
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
        "get_holdings_ratio", mock.Mock(side_effect=lambda coin, **kwargs: {
            "BTC": decimal.Decimal("0.6666666666666666666666666667"),  # 60/90 = 66.67%
            "ETH": decimal.Decimal("0.3333333333333333333333333333"),  # 30/90 = 33.33%
        }.get(coin, decimal.Decimal("0")))
    ) as get_holdings_ratio_mock:
        assert mode._is_index_config_applied(config_with_mixed_assets, traded_bases) is False
        get_holdings_ratio_mock.assert_not_called()
    
    # Test 12: All assets non-traded
    config_all_non_traded = {
        index_trading.IndexTradingModeProducer.INDEX_CONTENT: [
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "NON_TRADED_1",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 50
            },
            {
                index_trading.index_distribution.DISTRIBUTION_NAME: "NON_TRADED_2",
                index_trading.index_distribution.DISTRIBUTION_VALUE: 50
            }
        ]
    }
    assert mode._is_index_config_applied(config_all_non_traded, traded_bases) is False
    
    # Test 13: Zero holdings for all coins
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder,
        "get_holdings_ratio", mock.Mock(return_value=decimal.Decimal("0"))
    ) as get_holdings_ratio_mock:
        assert mode._is_index_config_applied(config_with_valid_distribution, traded_bases) is False
        assert get_holdings_ratio_mock.call_count == 1  # only BTC considered
        get_holdings_ratio_mock.assert_called_once_with("BTC", traded_symbols_only=True)
        get_holdings_ratio_mock.reset_mock()


async def test_get_config_min_ratio(tools):
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, {}))
    # 1. With selected profile
    config_with_profiles = {
        index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILES: [
            {
                index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_NAME: "profile-1",
                index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_MIN_PERCENT: 7.5,
            },
            {
                index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_NAME: "profile-2",
                index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_MIN_PERCENT: 15.0,
            },
        ],
        index_trading.IndexTradingModeProducer.SELECTED_REBALANCE_TRIGGER_PROFILE: "profile-2",
    }
    # Should pick 15.0% from profile-2
    assert mode._get_config_min_ratio(config_with_profiles) == decimal.Decimal("0.15")

    # 2. With direct config value only
    config_with_direct = {
        index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_MIN_PERCENT: 3.3
    }
    # Should pick 3.3% from direct config
    assert mode._get_config_min_ratio(config_with_direct) == decimal.Decimal("0.033")

    # 3. With neither, should fall back to mode.rebalance_trigger_min_ratio
    mode.rebalance_trigger_min_ratio = decimal.Decimal("0.123")
    config_empty = {}
    assert mode._get_config_min_ratio(config_empty) == decimal.Decimal("0.123")

    # 4. With profiles but no selected profile matches, should fall back to direct config
    config_profiles_no_match = {
        index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILES: [
            {
                index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_NAME: "profile-1",
                index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_PROFILE_MIN_PERCENT: 7.5,
            }
        ],
        index_trading.IndexTradingModeProducer.SELECTED_REBALANCE_TRIGGER_PROFILE: "profile-x",
        index_trading.IndexTradingModeProducer.REBALANCE_TRIGGER_MIN_PERCENT: 2.2
    }
    assert mode._get_config_min_ratio(config_profiles_no_match) == decimal.Decimal("0.022")
