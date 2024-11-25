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
        await memory_check_util.run_independent_backtestings_with_memory_check(
            config, tentacles_setup_config, use_multiple_asset_data_file=True
        )


def _get_config(tools, update):
    mode, trader = tools
    config = tentacles_manager_api.get_tentacle_config(trader.exchange_manager.tentacles_setup_config, mode.__class__)
    return {**config, **update}


async def test_init_default_values(tools):
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, {}))
    assert mode.refresh_interval_days == 1
    assert mode.rebalance_trigger_min_ratio == decimal.Decimal("0.05")
    assert mode.ratio_per_asset == {'BTC': {'name': 'BTC', 'value': decimal.Decimal(100)}}
    assert mode.total_ratio_per_asset == decimal.Decimal(100)
    assert mode.indexed_coins == ["BTC"]


async def test_init_config_values(tools):
    update = {
        "refresh_interval": 72,
        "rebalance_trigger_min_percent": 10.2,
        "index_content": [
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
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    assert mode.refresh_interval_days == 72
    assert mode.rebalance_trigger_min_ratio == decimal.Decimal("0.102")
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
    mode.init_user_inputs({})
    assert mode.refresh_interval_days == 72
    assert mode.rebalance_trigger_min_ratio == decimal.Decimal("0.102")
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
    assert mode.rebalance_trigger_min_ratio == decimal.Decimal("0.102")
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
    mode.init_user_inputs({})
    assert mode.refresh_interval_days == 72
    assert mode.rebalance_trigger_min_ratio == decimal.Decimal("0.102")
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
        assert cancel_order_mock.call_count == 2
        assert cancel_order_mock.mock_calls[0].args[0] is open_order_1
        assert cancel_order_mock.mock_calls[1].args[0] is open_order_2
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
    mode._update_coins_distribution()
    assert mode.get_target_ratio("ETH") == decimal.Decimal('0.3333333333333333617834929233')
    assert mode.get_target_ratio("BTC") == decimal.Decimal("0.3333333333333333617834929233")
    assert mode.get_target_ratio("SOL") == decimal.Decimal("0.3333333333333333617834929233")
    assert mode.get_target_ratio("ADA") == decimal.Decimal("0")

    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["ETH/USDT", "BTC/USDT"]
    ]
    mode._update_coins_distribution()
    assert mode.get_target_ratio("ETH") == decimal.Decimal('0.5')
    assert mode.get_target_ratio("BTC") == decimal.Decimal("0.5")
    assert mode.get_target_ratio("SOL") == decimal.Decimal("0")

    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["ETH/USDT", "BTC/USDT", "ADA/USDT", "SOL/USDT"]
    ]
    mode._update_coins_distribution()
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
            assert get_exchange_current_time_mock.call_count == 2
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
            assert get_exchange_current_time_mock.call_count == 2
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
    ) as _wait_for_symbol_prices_and_profitability_init_mock:
        with mock.patch.object(producer, "_trigger_rebalance", mock.AsyncMock()) as _trigger_rebalance_mock:
            with mock.patch.object(
                    producer, "_get_rebalance_details", mock.Mock(return_value=(False, {}))
            ) as _get_rebalance_details_mock:
                await producer.ensure_index()
                assert producer.last_activity == octobot_trading.modes.TradingModeActivity(
                    index_trading.IndexActivity.REBALANCING_SKIPPED
                )
                _wait_for_symbol_prices_and_profitability_init_mock.assert_called_once()
                _wait_for_symbol_prices_and_profitability_init_mock.reset_mock()
                _get_rebalance_details_mock.assert_called_once()
                _trigger_rebalance_mock.assert_not_called()
            with mock.patch.object(
                    producer, "_get_rebalance_details", mock.Mock(return_value=(True, {"plop": 1}))
            ) as _get_rebalance_details_mock:
                await producer.ensure_index()
                assert producer.last_activity == octobot_trading.modes.TradingModeActivity(
                    index_trading.IndexActivity.REBALANCING_DONE, {"plop": 1}
                )
                _wait_for_symbol_prices_and_profitability_init_mock.assert_called_once()
                _wait_for_symbol_prices_and_profitability_init_mock.reset_mock()
                _get_rebalance_details_mock.assert_called_once()
                _trigger_rebalance_mock.assert_called_once_with({"plop": 1})


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
    mode._update_coins_distribution()
    mode.rebalance_trigger_min_ratio = decimal.Decimal("0.1")
    portfolio_value_holder = trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder
    with mock.patch.object(producer, "_resolve_swaps", mock.Mock()) as _resolve_swaps_mock:
        with mock.patch.object(
                portfolio_value_holder, "get_holdings_ratio", mock.Mock(return_value=decimal.Decimal("0.3"))
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
                }
                assert get_holdings_ratio_mock.call_count == len(mode.indexed_coins)
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
                }
                assert get_holdings_ratio_mock.call_count == \
                       len(mode.indexed_coins) + len(details[index_trading.RebalanceDetails.REMOVE.value])
                get_removed_coins_from_config_mock.assert_called_once()
                _resolve_swaps_mock.assert_called_once_with(details)
                _resolve_swaps_mock.reset_mock()
                get_holdings_ratio_mock.reset_mock()
        with mock.patch.object(
                portfolio_value_holder, "get_holdings_ratio", mock.Mock(return_value=decimal.Decimal("0.2"))
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
                }
                assert get_holdings_ratio_mock.call_count == len(mode.indexed_coins)
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
                }
                assert get_holdings_ratio_mock.call_count == \
                       len(mode.indexed_coins) + len(details[index_trading.RebalanceDetails.REMOVE.value])
                get_removed_coins_from_config_mock.assert_called_once()
                _resolve_swaps_mock.assert_called_once_with(details)
                _resolve_swaps_mock.reset_mock()
                get_holdings_ratio_mock.reset_mock()

        # rebalance cap larger than ratio
        mode.rebalance_trigger_min_ratio = decimal.Decimal("0.5")
        with mock.patch.object(
                portfolio_value_holder, "get_holdings_ratio", mock.Mock(return_value=decimal.Decimal("0.3"))
        ) as get_holdings_ratio_mock:
            should_rebalance, details = producer._get_rebalance_details()
            assert should_rebalance is False
            assert details == {
                index_trading.RebalanceDetails.SELL_SOME.value: {},
                index_trading.RebalanceDetails.BUY_MORE.value: {},
                index_trading.RebalanceDetails.REMOVE.value: {},
                index_trading.RebalanceDetails.ADD.value: {},
                index_trading.RebalanceDetails.SWAP.value: {},
            }
            assert get_holdings_ratio_mock.call_count == len(mode.indexed_coins)
            get_holdings_ratio_mock.reset_mock()
            _resolve_swaps_mock.assert_called_once_with(details)
            _resolve_swaps_mock.reset_mock()
        with mock.patch.object(
                portfolio_value_holder, "get_holdings_ratio", mock.Mock(return_value=decimal.Decimal("0.00000001"))
        ) as get_holdings_ratio_mock:
            should_rebalance, details = producer._get_rebalance_details()
            assert should_rebalance is False
            assert details == {
                index_trading.RebalanceDetails.SELL_SOME.value: {},
                index_trading.RebalanceDetails.BUY_MORE.value: {},
                index_trading.RebalanceDetails.REMOVE.value: {},
                index_trading.RebalanceDetails.ADD.value: {},
                index_trading.RebalanceDetails.SWAP.value: {},
            }
            assert get_holdings_ratio_mock.call_count == len(mode.indexed_coins)
            get_holdings_ratio_mock.reset_mock()
            _resolve_swaps_mock.assert_called_once_with(details)
            _resolve_swaps_mock.reset_mock()
        with mock.patch.object(
                portfolio_value_holder, "get_holdings_ratio", mock.Mock(return_value=decimal.Decimal("0.9"))
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
            }
            assert get_holdings_ratio_mock.call_count == len(details[index_trading.RebalanceDetails.SELL_SOME.value])
            get_holdings_ratio_mock.reset_mock()
            _resolve_swaps_mock.assert_called_once_with(details)
            _resolve_swaps_mock.reset_mock()
        with mock.patch.object(
                portfolio_value_holder, "get_holdings_ratio", mock.Mock(return_value=decimal.Decimal("0"))
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
            }
            assert get_holdings_ratio_mock.call_count == len(details[index_trading.RebalanceDetails.ADD.value])
            get_holdings_ratio_mock.reset_mock()
            _resolve_swaps_mock.assert_called_once_with(details)
            _resolve_swaps_mock.reset_mock()


async def test_get_removed_coins_from_config(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
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
        assert await consumer._rebalance_portfolio("details") == ["sell", "buy"]
        _ensure_enough_funds_to_buy_after_selling_mock.assert_called_once()
        _sell_indexed_coins_for_reference_market_mock.assert_called_once_with("details")
        _split_reference_market_into_indexed_coins_mock.assert_called_once_with("details")

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
        ) as _split_reference_market_into_indexed_coins_mock:
            assert await consumer._rebalance_portfolio("details") == []
            _ensure_enough_funds_to_buy_after_selling_mock.assert_called_once()
            _sell_indexed_coins_for_reference_market_mock.assert_called_once_with("details")
            _split_reference_market_into_indexed_coins_mock.assert_not_called()
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
                    consumer, "_sell_indexed_coins_for_reference_market", mock.AsyncMock(
                        return_value=["sell"]
                    )
                ) as _sell_indexed_coins_for_reference_market_mock, mock.patch.object(
            consumer, "_split_reference_market_into_indexed_coins", mock.AsyncMock(
                return_value=["buy"]
            )
        ) as _split_reference_market_into_indexed_coins_mock:
            assert await consumer._rebalance_portfolio("details") == []
            _ensure_enough_funds_to_buy_after_selling_mock.assert_called_once()
            _sell_indexed_coins_for_reference_market_mock.assert_not_called()
            _split_reference_market_into_indexed_coins_mock.assert_not_called()
            _update_producer_last_activity_mock.assert_called_once_with(
                index_trading.IndexActivity.REBALANCING_SKIPPED,
                index_trading.RebalanceSkipDetails.NOT_ENOUGH_AVAILABLE_FOUNDS.value
            )
            _update_producer_last_activity_mock.reset_mock()

        with mock.patch.object(
                consumer, "_ensure_enough_funds_to_buy_after_selling", mock.AsyncMock()
        ) as _ensure_enough_funds_to_buy_after_selling_mock, \
                mock.patch.object(
                    consumer, "_sell_indexed_coins_for_reference_market", mock.AsyncMock(
                        return_value=["sell"]
                    )
                ) as _sell_indexed_coins_for_reference_market_mock, mock.patch.object(
            consumer, "_split_reference_market_into_indexed_coins", mock.AsyncMock(
                side_effect=trading_errors.MissingMinimalExchangeTradeVolume
            )
        ) as _split_reference_market_into_indexed_coins_mock:
            assert await consumer._rebalance_portfolio("details") == ["sell"]
            _ensure_enough_funds_to_buy_after_selling_mock.assert_called_once()
            _sell_indexed_coins_for_reference_market_mock.assert_called_once_with("details")
            _split_reference_market_into_indexed_coins_mock.assert_called_once_with("details")
            _update_producer_last_activity_mock.assert_called_once_with(
                index_trading.IndexActivity.REBALANCING_SKIPPED,
                index_trading.RebalanceSkipDetails.NOT_ENOUGH_AVAILABLE_FOUNDS.value
            )
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
    }) == ["BTC", "SOL"]
    assert consumer._get_coins_to_sell({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {},
        index_trading.RebalanceDetails.ADD.value: {},
        index_trading.RebalanceDetails.SWAP.value: {},
    }) == ["BTC", "ETH", "DOGE", "SHIB"]
    assert consumer._get_coins_to_sell({
        index_trading.RebalanceDetails.SELL_SOME.value: {},
        index_trading.RebalanceDetails.BUY_MORE.value: {},
        index_trading.RebalanceDetails.REMOVE.value: {
            "XRP": trading_constants.ONE_HUNDRED
        },
        index_trading.RebalanceDetails.ADD.value: {},
        index_trading.RebalanceDetails.SWAP.value: {},
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
    with mock.patch.object(
            consumer,
            "_get_symbols_and_amounts", mock.AsyncMock(
                side_effect=lambda coins, _: {f"{coin}/USDT": decimal.Decimal(i + 1) for i, coin in enumerate(coins)}
            )
    ) as _get_symbols_and_amounts_mock:
        with mock.patch.object(
                trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
                "get_currency_portfolio", mock.Mock(return_value=mock.Mock(available=decimal.Decimal("2")))
        ) as get_currency_portfolio_mock, mock.patch.object(
            consumer, "_buy_coin", mock.AsyncMock(return_value=["order"])
        ) as _buy_coin_mock:
            with pytest.raises(trading_errors.MissingMinimalExchangeTradeVolume):
                await consumer._split_reference_market_into_indexed_coins(details)
            get_currency_portfolio_mock.assert_called_once_with("USDT")
            _buy_coin_mock.assert_not_called()
            _get_symbols_and_amounts_mock.assert_called_once()
            _get_symbols_and_amounts_mock.reset_mock()

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
            assert await consumer._split_reference_market_into_indexed_coins(details) == ["order", "order"]
            _get_symbols_and_amounts_mock.assert_called_once()
            _get_symbols_and_amounts_mock.reset_mock()
            get_traded_assets_holdings_value_mock.assert_called_once_with("USDT", None)
            get_currency_portfolio_mock.assert_not_called()
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
                await consumer._split_reference_market_into_indexed_coins(details)
            _get_symbols_and_amounts_mock.assert_called_once()
            _get_symbols_and_amounts_mock.reset_mock()
            get_currency_portfolio_mock.assert_called_once_with("USDT")
            assert _buy_coin_mock.call_count == 2

        # bought coins
        mode.indexed_coins = ["ETH", "BTC"]
        with mock.patch.object(
                trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
                "get_currency_portfolio", mock.Mock(return_value=mock.Mock(available=decimal.Decimal("2")))
        ) as get_currency_portfolio_mock, mock.patch.object(
            consumer, "_buy_coin", mock.AsyncMock(return_value=["order"])
        ) as _buy_coin_mock:
            assert await consumer._split_reference_market_into_indexed_coins(details) == ["order", "order"]
            _get_symbols_and_amounts_mock.assert_called_once()
            _get_symbols_and_amounts_mock.reset_mock()
            get_currency_portfolio_mock.assert_called_once_with("USDT")
            assert _buy_coin_mock.call_count == 2


async def test_get_symbols_and_amounts(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["BTC/USDT"]
    ]
    mode._update_coins_distribution()
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
        mode._update_coins_distribution()
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
    mode._update_coins_distribution()
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
    with mock.patch.object(
            mode,
            "create_order", mock.AsyncMock(side_effect=lambda x: x)
    ) as create_order_mock:
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
        with mock.patch.object(
                consumer.exchange_manager.exchange, "get_trade_fee", mock.Mock(return_value={
                    trading_enums.FeePropertyColumns.COST.value: "10",
                    trading_enums.FeePropertyColumns.CURRENCY.value: "USDT",
                })
        ) as get_trade_fee_mock:
            orders = await consumer._buy_coin("BTC/USDT", decimal.Decimal("0.5"))
            get_trade_fee_mock.assert_called_once()
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
            get_trade_fee_mock.assert_called_once()
            assert len(orders) == 1
            create_order_mock.assert_called_once_with(orders[0])
            assert isinstance(orders[0], trading_personal_data.BuyMarketOrder)
            assert orders[0].symbol == "BTC/USDT"
            assert orders[0].origin_price == decimal.Decimal(1000)
            assert orders[0].origin_quantity == decimal.Decimal("1.98")  # 2 - fees denominated in BTC
            assert orders[0].total_cost == decimal.Decimal('1980')
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
        with mock.patch.object(
                consumer.exchange_manager.exchange, "get_trade_fee", mock.Mock(return_value={
                    trading_enums.FeePropertyColumns.COST.value: "10",
                    trading_enums.FeePropertyColumns.CURRENCY.value: "USDT",
                })
        ) as get_trade_fee_mock:
            orders = await consumer._buy_coin("BTC/USDT", decimal.Decimal("0.5"))
            get_trade_fee_mock.assert_called_once()
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
            get_trade_fee_mock.assert_called_once()
            assert len(orders) == 1
            is_market_open_for_order_type_mock.assert_called_once_with("BTC/USDT", trading_enums.TraderOrderType.BUY_MARKET)
            create_order_mock.assert_called_once_with(orders[0])
            assert isinstance(orders[0], trading_personal_data.BuyLimitOrder)
            assert orders[0].symbol == "BTC/USDT"
            assert orders[0].origin_price == decimal.Decimal(1005)
            assert orders[0].origin_quantity == decimal.Decimal('1.97014925')  # 2 - fees denominated in BTC
            assert decimal.Decimal('1979.999') < orders[0].total_cost < decimal.Decimal('1980')
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
