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
            "rebalance_cap_percent": 5,
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
    assert mode.rebalance_cap_ratio == decimal.Decimal("0.05")
    assert mode.ratio_per_asset == {}
    assert mode.total_ratio_per_asset == trading_constants.ZERO
    assert mode.indexed_coins == ["BTC"]


async def test_init_config_values(tools):
    update = {
        "refresh_interval": 72,
        "rebalance_cap_percent": 10.2,
        "index_content": [
            {
                "name": "ETH",
                "ratio": 53,
            },
            {
                "name": "BTC",
                "ratio": 1,
            },
            {
                "name": "SOL",
                "ratio": 1,
            },
        ]
    }
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    trader.exchange_manager.exchange_config.traded_symbols = [
        commons_symbols.parse_symbol(symbol)
        for symbol in ["ETH/USDT", "ADA/USDT", "BTC/USDT"]
    ]
    assert mode.refresh_interval_days == 72
    assert mode.rebalance_cap_ratio == decimal.Decimal("0.102")
    assert mode.ratio_per_asset == {
        "ETH": {
            "name": "ETH",
            "ratio": 53,
        },
        "BTC": {
            "name": "BTC",
            "ratio": 1,
        },
        "SOL": {
            "name": "SOL",
            "ratio": 1,
        },
    }
    assert mode.total_ratio_per_asset == decimal.Decimal("55")
    assert mode.indexed_coins == ["BTC"]

    # refresh user inputs
    mode.init_user_inputs({})
    assert mode.refresh_interval_days == 72
    assert mode.rebalance_cap_ratio == decimal.Decimal("0.102")
    assert mode.ratio_per_asset == {
        "ETH": {
            "name": "ETH",
            "ratio": 53,
        },
        "BTC": {
            "name": "BTC",
            "ratio": 1,
        },
        "SOL": {
            "name": "SOL",
            "ratio": 1,
        },
    }
    assert mode.total_ratio_per_asset == decimal.Decimal("55")
    assert mode.indexed_coins == ["BTC", "ETH"]  # sorted list


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
        "rebalance_cap_percent": 10.2,
        "index_content": [
            {
                "name": "BTC",
                "ratio": 1,
            },
            {
                "name": "ETH",
                "ratio": 53,
            },
        ]
    }
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    assert mode.get_target_ratio("ETH") == decimal.Decimal('0.9814814814814814814814814815')
    assert mode.get_target_ratio("BTC") == decimal.Decimal("0.01851851851851851851851851852")
    assert mode.get_target_ratio("SOL") == decimal.Decimal("0")


async def test_get_target_ratio_without_config(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    assert mode.get_target_ratio("ETH") == decimal.Decimal('1')
    assert mode.get_target_ratio("BTC") == decimal.Decimal("1")
    assert mode.get_target_ratio("SOL") == decimal.Decimal("1")

    mode.indexed_coins = ["BTC", "ETH"]
    assert mode.get_target_ratio("ETH") == decimal.Decimal('0.5')
    assert mode.get_target_ratio("BTC") == decimal.Decimal("0.5")
    assert mode.get_target_ratio("SOL") == decimal.Decimal("0.5")

    mode.indexed_coins = ["BTC", "ETH", "A", "B"]
    assert mode.get_target_ratio("ETH") == decimal.Decimal('0.25')
    assert mode.get_target_ratio("BTC") == decimal.Decimal("0.25")
    assert mode.get_target_ratio("SOL") == decimal.Decimal("0.25")


async def test_ohlcv_callback(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    current_time = time.time()
    with mock.patch.object(producer, "ensure_index", mock.AsyncMock()) as ensure_index_mock:
        with mock.patch.object(
            trader.exchange_manager.exchange, "get_exchange_current_time", mock.Mock(return_value=current_time)
        ) as get_exchange_current_time_mock:
            # not enough indexed coins
            mode.indexed_coins = []
            assert producer._last_trigger_time == 0
            await producer.ohlcv_callback("binance", "123", "BTC", "BTC/USDT", None, None)
            ensure_index_mock.assert_not_called()
            get_exchange_current_time_mock.assert_called_once()
            get_exchange_current_time_mock.reset_mock()
            assert producer._last_trigger_time == current_time

            # enough coins
            mode.indexed_coins = [1, 2, 3]
            # already called on this time
            await producer.ohlcv_callback("binance", "123", "BTC", "BTC/USDT", None, None)
            ensure_index_mock.assert_not_called()
            get_exchange_current_time_mock.assert_called_once()

            assert producer._last_trigger_time == current_time
        with mock.patch.object(
            trader.exchange_manager.exchange, "get_exchange_current_time", mock.Mock(return_value=current_time*2)
        ) as get_exchange_current_time_mock:
            mode.indexed_coins = [1, 2, 3]
            await producer.ohlcv_callback("binance", "123", "BTC", "BTC/USDT", None, None)
            ensure_index_mock.assert_called_once()
            get_exchange_current_time_mock.assert_called_once()
            assert producer._last_trigger_time == current_time * 2


async def test_ensure_index(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    with mock.patch.object(
        producer, "_wait_for_symbol_prices_and_profitability_init", mock.AsyncMock()
    ) as _wait_for_symbol_prices_and_profitability_init_mock:
        with mock.patch.object(producer, "_trigger_rebalance", mock.AsyncMock()) as _trigger_rebalance_mock:
            with mock.patch.object(
                producer, "_should_rebalance", mock.Mock(return_value=False)
            ) as _should_rebalance_mock:
                await producer.ensure_index()
                _wait_for_symbol_prices_and_profitability_init_mock.assert_called_once()
                _wait_for_symbol_prices_and_profitability_init_mock.reset_mock()
                _should_rebalance_mock.assert_called_once()
                _trigger_rebalance_mock.assert_not_called()
            with mock.patch.object(
                producer, "_should_rebalance", mock.Mock(return_value=True)
            ) as _should_rebalance_mock:
                await producer.ensure_index()
                _wait_for_symbol_prices_and_profitability_init_mock.assert_called_once()
                _wait_for_symbol_prices_and_profitability_init_mock.reset_mock()
                _should_rebalance_mock.assert_called_once()
                _trigger_rebalance_mock.assert_called_once()


async def test_trigger_rebalance(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    with mock.patch.object(
        producer, "submit_trading_evaluation", mock.AsyncMock()
    ) as _wait_for_symbol_prices_and_profitability_init_mock:
        await producer._trigger_rebalance()
        _wait_for_symbol_prices_and_profitability_init_mock.assert_called_once_with(
            cryptocurrency=None,
            symbol=None,
            time_frame=None,
            final_note=None,
            state=trading_enums.EvaluatorStates.NEUTRAL
        )


async def test_should_rebalance(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    mode.indexed_coins = ["BTC", "ETH", "SOL"]
    mode.rebalance_cap_ratio = decimal.Decimal("0.1")
    portfolio_value_holder = trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio_value_holder
    with mock.patch.object(
        portfolio_value_holder, "get_holdings_ratio", mock.Mock(return_value=decimal.Decimal("0.3"))
    ) as get_holdings_ratio_mock:
        assert producer._should_rebalance() is False
        assert get_holdings_ratio_mock.call_count == len(mode.indexed_coins)
        get_holdings_ratio_mock.reset_mock()
    with mock.patch.object(
        portfolio_value_holder, "get_holdings_ratio", mock.Mock(return_value=decimal.Decimal("0.2"))
    ) as get_holdings_ratio_mock:
        assert producer._should_rebalance() is True
        get_holdings_ratio_mock.assert_called_once_with("BTC", traded_symbols_only=True)
        assert get_holdings_ratio_mock.call_count == 1
        get_holdings_ratio_mock.reset_mock()

    # rebalance cap larger than ratio
    mode.rebalance_cap_ratio = decimal.Decimal("0.5")
    with mock.patch.object(
        portfolio_value_holder, "get_holdings_ratio", mock.Mock(return_value=decimal.Decimal("0.3"))
    ) as get_holdings_ratio_mock:
        assert producer._should_rebalance() is False
        assert get_holdings_ratio_mock.call_count == len(mode.indexed_coins)
        get_holdings_ratio_mock.reset_mock()
    with mock.patch.object(
        portfolio_value_holder, "get_holdings_ratio", mock.Mock(return_value=decimal.Decimal("0.00000001"))
    ) as get_holdings_ratio_mock:
        assert producer._should_rebalance() is False
        assert get_holdings_ratio_mock.call_count == len(mode.indexed_coins)
        get_holdings_ratio_mock.reset_mock()
    with mock.patch.object(
        portfolio_value_holder, "get_holdings_ratio", mock.Mock(return_value=decimal.Decimal("0.9"))
    ) as get_holdings_ratio_mock:
        assert producer._should_rebalance() is True
        assert get_holdings_ratio_mock.call_count == 1
        get_holdings_ratio_mock.reset_mock()
    with mock.patch.object(
        portfolio_value_holder, "get_holdings_ratio", mock.Mock(return_value=decimal.Decimal("0"))
    ) as get_holdings_ratio_mock:
        assert producer._should_rebalance() is True
        assert get_holdings_ratio_mock.call_count == 1
        get_holdings_ratio_mock.reset_mock()


async def test_create_new_orders(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    with mock.patch.object(
        consumer, "_rebalance_portfolio", mock.AsyncMock(return_value="plop")
    ) as _rebalance_portfolio_mock:
        assert await consumer.create_new_orders(None, None, None) == []
        _rebalance_portfolio_mock.assert_not_called()
        assert await consumer.create_new_orders(None, None, trading_enums.EvaluatorStates.NEUTRAL.value) == "plop"
        _rebalance_portfolio_mock.assert_called_once()


async def test_rebalance_portfolio(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    with mock.patch.object(
        consumer, "_sell_indexed_coins_for_reference_market", mock.AsyncMock(return_value=["sell"])
    ) as _sell_indexed_coins_for_reference_market_mock, \
        mock.patch.object(
            consumer, "_split_reference_market_into_indexed_coins", mock.AsyncMock(return_value=["buy"])
        ) as _sell_indexed_coins_for_reference_market_mock:
        assert await consumer._rebalance_portfolio() == ["sell", "buy"]
        _sell_indexed_coins_for_reference_market_mock.assert_called_once()
        _sell_indexed_coins_for_reference_market_mock.assert_called_once()


async def test_sell_indexed_coins_for_reference_market(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    with mock.patch.object(
        octobot_trading.modes, "convert_assets_to_target_asset", mock.AsyncMock(return_value=["1", "2"])
    ) as convert_assets_to_target_asset_mock, \
        mock.patch.object(
            trading_personal_data, "wait_for_order_fill", mock.AsyncMock()
        ) as wait_for_order_fill_mock:
        assert await consumer._sell_indexed_coins_for_reference_market() == ["1", "2"]
        convert_assets_to_target_asset_mock.assert_called_once_with(
            mode, mode.indexed_coins,
            consumer.exchange_manager.exchange_personal_data.portfolio_manager.reference_market, {}
        )
        assert wait_for_order_fill_mock.call_count == 2


async def test_split_reference_market_into_indexed_coins(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    # no indexed coin
    mode.indexed_coins = []
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
        "get_currency_portfolio", mock.Mock(return_value=mock.Mock(available=decimal.Decimal("2")))
    ) as get_currency_portfolio_mock, mock.patch.object(
        consumer, "_buy_coin", mock.AsyncMock(return_value=["order"])
    ) as _buy_coin_mock:
        with pytest.raises(trading_errors.MissingMinimalExchangeTradeVolume):
            await consumer._split_reference_market_into_indexed_coins()
        get_currency_portfolio_mock.assert_called_once_with("USDT")
        _buy_coin_mock.assert_not_called()

    # no bought coin
    mode.indexed_coins = ["ETH", "BTC"]
    with mock.patch.object(
        trader.exchange_manager.exchange_personal_data.portfolio_manager.portfolio,
        "get_currency_portfolio", mock.Mock(return_value=mock.Mock(available=decimal.Decimal("2")))
    ) as get_currency_portfolio_mock, mock.patch.object(
        consumer, "_buy_coin", mock.AsyncMock(return_value=[])
    ) as _buy_coin_mock:
        with pytest.raises(trading_errors.MissingMinimalExchangeTradeVolume):
            await consumer._split_reference_market_into_indexed_coins()
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
        assert await consumer._split_reference_market_into_indexed_coins() == ["order", "order"]
        get_currency_portfolio_mock.assert_called_once_with("USDT")
        assert _buy_coin_mock.call_count == 2


async def test_buy_coin(tools):
    update = {}
    mode, producer, consumer, trader = await _init_mode(tools, _get_config(tools, update))
    with mock.patch.object(
        mode,
        "create_order", mock.AsyncMock(side_effect=lambda x: x)
    ) as create_order_mock:
        # ratio = 1
        with mock.patch.object(
            mode, "get_target_ratio", mock.Mock(return_value=decimal.Decimal(1))
        ) as get_target_ratio:
            orders = await consumer._buy_coin("BTC", decimal.Decimal(2000))
            get_target_ratio.assert_called_once_with("BTC")
            assert len(orders) == 1
            create_order_mock.assert_called_once_with(orders[0])
            assert isinstance(orders[0], trading_personal_data.BuyMarketOrder)
            assert orders[0].symbol == "BTC/USDT"
            assert orders[0].origin_price == decimal.Decimal(1000)
            assert orders[0].origin_quantity == decimal.Decimal(2)
            create_order_mock.reset_mock()

        # ratio = 0.25
        with mock.patch.object(
            mode, "get_target_ratio", mock.Mock(return_value=decimal.Decimal(0.25))
        ) as get_target_ratio:
            orders = await consumer._buy_coin("BTC", decimal.Decimal(2000))
            get_target_ratio.assert_called_once_with("BTC")
            assert len(orders) == 1
            create_order_mock.assert_called_once_with(orders[0])
            assert isinstance(orders[0], trading_personal_data.BuyMarketOrder)
            assert orders[0].symbol == "BTC/USDT"
            assert orders[0].origin_price == decimal.Decimal(1000)
            assert orders[0].origin_quantity == decimal.Decimal("0.5")  # 2 * 0.25
            create_order_mock.reset_mock()
            get_target_ratio.reset_mock()

            # given reference_market_available_holdings is lower
            orders = await consumer._buy_coin("BTC", decimal.Decimal(100))
            get_target_ratio.assert_called_once_with("BTC")
            assert len(orders) == 1
            create_order_mock.assert_called_once_with(orders[0])
            assert isinstance(orders[0], trading_personal_data.BuyMarketOrder)
            assert orders[0].symbol == "BTC/USDT"
            assert orders[0].origin_price == decimal.Decimal(1000)
            assert orders[0].origin_quantity == decimal.Decimal("0.025")  # use 100 instead of all 2000 USDT in pf
            create_order_mock.reset_mock()
            get_target_ratio.reset_mock()

        # adapt for fees
        with mock.patch.object(
            consumer.exchange_manager.exchange, "get_trade_fee", mock.Mock(return_value={
                trading_enums.FeePropertyColumns.COST.value: "10",
                trading_enums.FeePropertyColumns.CURRENCY.value: "USDT",
            })
        ) as get_trade_fee_mock:
            with mock.patch.object(
                mode, "get_target_ratio", mock.Mock(return_value=decimal.Decimal(0.25))
            ) as get_target_ratio:
                orders = await consumer._buy_coin("BTC", decimal.Decimal(2000))
                get_target_ratio.assert_called_once_with("BTC")
                get_trade_fee_mock.assert_called_once()
                assert len(orders) == 1
                create_order_mock.assert_called_once_with(orders[0])
                assert isinstance(orders[0], trading_personal_data.BuyMarketOrder)
                assert orders[0].symbol == "BTC/USDT"
                assert orders[0].origin_price == decimal.Decimal(1000)
                # no adaptation needed as not all funds are used (1/4 ratio)
                assert orders[0].origin_quantity == decimal.Decimal("0.5")
                create_order_mock.reset_mock()
                get_trade_fee_mock.reset_mock()

            with mock.patch.object(
                mode, "get_target_ratio", mock.Mock(return_value=decimal.Decimal(1))
            ) as get_target_ratio:
                orders = await consumer._buy_coin("BTC", decimal.Decimal(2000))
                get_target_ratio.assert_called_once_with("BTC")
                get_trade_fee_mock.assert_called_once()
                assert len(orders) == 1
                create_order_mock.assert_called_once_with(orders[0])
                assert isinstance(orders[0], trading_personal_data.BuyMarketOrder)
                assert orders[0].symbol == "BTC/USDT"
                assert orders[0].origin_price == decimal.Decimal(1000)
                assert orders[0].origin_quantity == decimal.Decimal("1.98")    # 2 - fees denominated in BTC
                create_order_mock.reset_mock()


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
