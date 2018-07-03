import copy
import ccxt

from config.cst import EvaluatorStates, START_PENDING_EVAL_NOTE, TimeFrames
from config.cst import ExchangeConstantsMarketStatusColumns as Ecmsc
from tests.unit_tests.trading_modes_tests.trading_mode_test_toolkit import check_order_limits,\
    check_orders, check_portfolio
from tests.test_utils.config import load_test_config
from trading.exchanges.exchange_manager import ExchangeManager
from trading.trader.modes import HighFrequencyMode
from evaluator.symbol_evaluator import SymbolEvaluator
from evaluator.cryptocurrency_evaluator import CryptocurrencyEvaluator
from evaluator.Util.advanced_manager import AdvancedManager
from trading.trader.portfolio import Portfolio
from trading.trader.trader_simulator import TraderSimulator
from evaluator.Updaters.symbol_time_frames_updater import SymbolTimeFramesDataUpdaterThread
from evaluator.evaluator_threads_manager import EvaluatorThreadsManager
from tentacles.Evaluator.Strategies.Default.high_frequency_strategy_evaluator import HighFrequencyStrategiesEvaluator
from octobot import OctoBot


def _get_tools():
    config = load_test_config()
    symbol = "BTC/USDT"
    exchange_traders = {}
    exchange_traders2 = {}
    time_frame = TimeFrames.FIVE_MINUTES
    AdvancedManager.create_class_list(config)
    symbol_time_frame_updater_thread = SymbolTimeFramesDataUpdaterThread()
    exchange_manager = ExchangeManager(config, ccxt.binance, is_simulated=True)
    exchange_inst = exchange_manager.get_exchange()
    trader_inst = TraderSimulator(config, exchange_inst, 0.3)
    trader_inst.stop_order_manager()
    trader_inst2 = TraderSimulator(config, exchange_inst, 0.3)
    trader_inst2.stop_order_manager()
    trader_inst2.set_enabled(False)
    trader_inst.portfolio.portfolio["SUB"] = {
        Portfolio.TOTAL: 0.000000000000000000005,
        Portfolio.AVAILABLE: 0.000000000000000000005
    }
    trader_inst.portfolio.portfolio["BNB"] = {
        Portfolio.TOTAL: 0.000000000000000000005,
        Portfolio.AVAILABLE: 0.000000000000000000005
    }
    trader_inst.portfolio.portfolio["USDT"] = {
        Portfolio.TOTAL: 2000,
        Portfolio.AVAILABLE: 2000
    }
    crypto_currency_evaluator = CryptocurrencyEvaluator(config, "Bitcoin", [])
    symbol_evaluator = SymbolEvaluator(config, symbol, crypto_currency_evaluator)

    exchange_traders[exchange_inst.get_name()] = trader_inst
    exchange_traders2[exchange_inst.get_name()] = trader_inst2
    symbol_evaluator.set_trader_simulators(exchange_traders)
    symbol_evaluator.set_traders(exchange_traders2)
    trading_mode_inst = OctoBot.get_trading_mode_class(config)(config, exchange_inst)
    _ = EvaluatorThreadsManager(config, time_frame, symbol_time_frame_updater_thread,
                                symbol_evaluator, exchange_inst, trading_mode_inst, [])
    trading_mode = HighFrequencyMode(config, exchange_inst)
    trading_mode.add_symbol_evaluator(symbol_evaluator)

    return config, exchange_inst, trader_inst, symbol, trading_mode


def test_trading_mode_init():
    config, exchange, trader, symbol, trading_mode = _get_tools()

    # default simulator fees = 0.001
    assert trading_mode.nb_creators == 5
    assert len(trading_mode.get_creators(symbol)) == trading_mode.nb_creators
    assert len(trading_mode.get_deciders(symbol)) == 1


def test_creator_init():
    config, exchange, trader, symbol, trading_mode = _get_tools()
    creator = trading_mode.get_creator(symbol, trading_mode.get_only_creator_key(symbol))
    portfolio = trader.get_portfolio()
    sub_portfolio = creator.get_sub_portfolio()
    assert sub_portfolio
    assert sub_portfolio.get_parent_portfolio() == portfolio
    assert creator.get_trader() == trader


def test_creator_create_allin_order():
    config, exchange, trader, symbol, trading_mode = _get_tools()
    market_status = exchange.get_market_status(symbol)
    limit_cost = market_status[Ecmsc.LIMITS.value][Ecmsc.LIMITS_COST.value]
    min_cost = limit_cost[Ecmsc.LIMITS_COST_MIN.value]

    creator = trading_mode.get_creator(symbol, trading_mode.get_only_creator_key(symbol))
    portfolio = trader.get_portfolio()
    initial_portfolio = copy.deepcopy(portfolio.portfolio)
    sub_portfolio = creator.get_sub_portfolio()
    initial_sub_portfolio = copy.deepcopy(sub_portfolio.portfolio)

    created_orders = creator.create_new_order(None, symbol, exchange, trader, None, EvaluatorStates.VERY_SHORT)
    assert len(created_orders) == 1
    order = created_orders[0]
    check_orders(created_orders, 0, EvaluatorStates.VERY_SHORT, 1, market_status)
    check_order_limits(order, market_status)
    check_portfolio(portfolio, initial_portfolio, created_orders)
    check_portfolio(sub_portfolio, initial_sub_portfolio, created_orders)
    assert order.get_origin_quantity() == initial_sub_portfolio["BTC"][Portfolio.AVAILABLE]
    assert order.get_origin_quantity() == initial_sub_portfolio["BTC"][Portfolio.TOTAL]

    initial_portfolio = copy.deepcopy(portfolio.portfolio)
    initial_sub_portfolio = copy.deepcopy(sub_portfolio.portfolio)
    created_orders = creator.create_new_order(None, symbol, exchange, trader, None, EvaluatorStates.VERY_LONG)
    assert len(created_orders) == 1
    order = created_orders[0]
    check_orders(created_orders, 0, EvaluatorStates.VERY_LONG, 1, market_status)
    check_order_limits(order, market_status)
    check_portfolio(portfolio, initial_portfolio, created_orders)
    check_portfolio(sub_portfolio, initial_sub_portfolio, created_orders)
    order_cost = order.get_origin_quantity()*order.get_create_last_price()
    assert initial_sub_portfolio["USDT"][Portfolio.AVAILABLE] >= order_cost
    assert initial_sub_portfolio["USDT"][Portfolio.AVAILABLE] - order_cost < min_cost
    assert initial_sub_portfolio["USDT"][Portfolio.TOTAL] - order_cost < min_cost


def test_decider_init():
    config, exchange, trader, symbol, trading_mode = _get_tools()
    decider = trading_mode.get_only_decider_key(symbol)
    assert decider
    assert len(decider.blocked_creators) == 0
    assert len(decider.filled_creators) == trading_mode.nb_creators
    assert len(decider.pending_creators) == trading_mode.nb_creators


def test_set_final_eval():
    config, exchange, trader, symbol, trading_mode = _get_tools()
    strategy = trading_mode.get_strategy_instances_by_classes(symbol)[HighFrequencyStrategiesEvaluator] = \
        HighFrequencyStrategiesEvaluator()
    decider = trading_mode.get_only_decider_key(symbol)

    strategy.eval_note = 1
    decider.set_final_eval()
    assert decider.final_eval == 1

    strategy.eval_note = -1
    decider.set_final_eval()
    assert decider.final_eval == -1

    strategy.eval_note = None
    decider.set_final_eval()
    assert decider.final_eval == -1

    strategy.eval_note = START_PENDING_EVAL_NOTE
    decider.set_final_eval()
    assert decider.final_eval == -1


def test_get_required_difference_from_risk():
    config, exchange, trader, symbol, trading_mode = _get_tools()
    decider = trading_mode.get_only_decider_key(symbol)

    trader.set_risk(0.1)

    # nb_blocked_creators =0
    assert decider.get_required_difference_from_risk() == 1

    decider.blocked_creators.append(1)
    with_one_blocked = decider.get_required_difference_from_risk()
    assert with_one_blocked > 1

    decider.blocked_creators.append(1)
    with_two_blocked = decider.get_required_difference_from_risk()
    assert with_two_blocked > with_one_blocked

    decider.blocked_creators.append(1)
    with_three_blocked = decider.get_required_difference_from_risk()
    assert with_three_blocked > with_two_blocked

    decider.blocked_creators.append(1)
    with_four_blocked = decider.get_required_difference_from_risk()
    assert with_four_blocked > with_three_blocked

    trader.set_risk(0.8)

    decider.blocked_creators = []
    # nb_blocked_creators =0
    assert decider.get_required_difference_from_risk() == 1

    decider.blocked_creators.append(1)
    risky_with_one_blocked = decider.get_required_difference_from_risk()
    assert risky_with_one_blocked > 1
    assert risky_with_one_blocked < with_one_blocked

    decider.blocked_creators.append(1)
    risky_with_two_blocked = decider.get_required_difference_from_risk()
    assert risky_with_two_blocked > risky_with_one_blocked
    assert risky_with_two_blocked < with_two_blocked

    decider.blocked_creators.append(1)
    risky_with_three_blocked = decider.get_required_difference_from_risk()
    assert risky_with_three_blocked > risky_with_two_blocked
    assert risky_with_three_blocked < with_three_blocked

    decider.blocked_creators.append(1)
    risky_with_four_blocked = decider.get_required_difference_from_risk()
    assert risky_with_four_blocked > risky_with_three_blocked
    assert risky_with_four_blocked < with_four_blocked


def test_create_state():
    config, exchange, trader, symbol, trading_mode = _get_tools()
    decider = trading_mode.get_only_decider_key(symbol)
    init_state = decider.state

    decider.final_eval = 0
    decider.create_state()
    assert decider.state == init_state

    decider.final_eval = 0.2
    assert len(decider.filled_creators) == 5
    decider.create_state()
    assert decider.state == EvaluatorStates.VERY_SHORT
    # did not create orders because have no bought price info to check if selling is beneficial
    assert len(decider.filled_creators) == 5

    # now set beneficial bought price
    for creator in trading_mode.get_creators(symbol).values():
        creator.set_market_value(1)
    decider.create_state()
    assert decider.state == EvaluatorStates.VERY_SHORT
    # sold everything
    assert len(decider.filled_creators) == 0

    decider.final_eval = -0.005
    for i, _ in enumerate(trading_mode.get_creators(symbol)):
        decider.create_state()
        assert decider.state == EvaluatorStates.VERY_LONG
        assert len(decider.pending_creators) == 5-(i+1)


def test_create_state_with_block_creators():
    config, exchange, trader, symbol, trading_mode = _get_tools()
    decider = trading_mode.get_only_decider_key(symbol)
    trader.set_risk(0.1)

    decider.final_eval = -0.005
    decider.create_state()
    assert decider.state == EvaluatorStates.VERY_LONG
    assert len(decider.pending_creators) == 4

    decider.blocked_creators = [1]
    decider.create_state()
    assert decider.state == EvaluatorStates.VERY_LONG
    # did not create anything because need a higher eval (because 1 blocked creator)
    assert len(decider.pending_creators) == 4

    decider.final_eval = -0.006
    decider.blocked_creators = [1]
    decider.create_state()
    assert decider.state == EvaluatorStates.VERY_LONG
    assert len(decider.pending_creators) == 3

    decider.final_eval = -0.01
    decider.blocked_creators = [1]*2
    decider.create_state()
    assert decider.state == EvaluatorStates.VERY_LONG
    # ok created order
    assert len(decider.pending_creators) == 2

    decider.final_eval = -0.01
    decider.blocked_creators = [1]*3
    decider.create_state()
    assert decider.state == EvaluatorStates.VERY_LONG
    # nok did not create order
    assert len(decider.pending_creators) == 2
