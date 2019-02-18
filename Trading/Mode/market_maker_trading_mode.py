"""
OctoBot Tentacle

$tentacle_description: {
    "name": "market_maker_trading_mode",
    "type": "Trading",
    "subtype": "Mode",
    "version": "1.1.0",
    "requirements": ["instant_fluctuations_evaluator", "market_making_startegy_evaluator"],
    "config_files": ["MarketMakerTradingMode.json"],
    "tests":["test_market_marker_trading_mode"],
    "developing": true
}
"""
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
from ccxt import InsufficientFunds

from config import ExchangeConstantsOrderBookInfoColumns, TraderOrderType, ExchangeConstantsMarketPropertyColumns
from trading.trader.modes import AbstractTradingModeCreator, AbstractTradingModeDecider
from trading.trader.modes.abstract_trading_mode import AbstractTradingMode


class MarketMakerTradingMode(AbstractTradingMode):
    DESCRIPTION = "MarketMakerTradingMode"

    DELTA_ASK = "delta_ask"
    DELTA_BID = "delta_bid"

    def __init__(self, config, exchange):
        super().__init__(config, exchange)

        self.trading_mode_config = MarketMakerTradingMode.get_trading_mode_config()

    def create_deciders(self, symbol, symbol_evaluator):
        self.add_decider(symbol, MarketMakerTradingModeDecider(self, symbol_evaluator, self.exchange))

    def create_creators(self, symbol, _):
        self.add_creator(symbol, MarketMakerTradingModeCreator(self))


class MarketMakerTradingModeCreator(AbstractTradingModeCreator):
    LIMIT_ORDER_ATTENUATION = 10
    FEES_ATTENUATION = 2

    def __init__(self, trading_mode):
        super().__init__(trading_mode)

        self.config_delta_ask = 0  # percent
        self.config_delta_bid = 0  # percent
        self.fees = {}

        if MarketMakerTradingMode.DELTA_ASK not in trading_mode.trading_mode_config or \
                MarketMakerTradingMode.DELTA_BID not in trading_mode.trading_mode_config:
            self.logger.error(f"Can't create any trade : some configuration is missing "
                              f"in {MarketMakerTradingMode.get_config_file_name()}, "
                              f"please check {MarketMakerTradingMode.DELTA_ASK} and {MarketMakerTradingMode.DELTA_BID}")
        else:
            self.config_delta_ask = trading_mode.trading_mode_config[MarketMakerTradingMode.DELTA_ASK]
            self.config_delta_bid = trading_mode.trading_mode_config[MarketMakerTradingMode.DELTA_BID]

    def verify_and_adapt_delta_with_fees(self, symbol):
        if symbol in self.fees:
            return self.fees[symbol]

        exchange_fees = self.trading_mode.exchange.get_fees(symbol)
        delta_ask = self.config_delta_ask
        delta_bid = self.config_delta_bid

        # check ask -> limit_orders -> MAKER ? not sure -> max
        common_fees = max(exchange_fees[ExchangeConstantsMarketPropertyColumns.TAKER.value],
                          exchange_fees[ExchangeConstantsMarketPropertyColumns.FEE.value],
                          exchange_fees[ExchangeConstantsMarketPropertyColumns.MAKER.value])

        if delta_ask < (common_fees / self.FEES_ATTENUATION):
            delta_ask = common_fees / self.FEES_ATTENUATION

        if delta_bid < (common_fees / self.FEES_ATTENUATION):
            delta_bid = common_fees / self.FEES_ATTENUATION

        self.fees[symbol] = delta_ask, delta_bid
        return self.fees[symbol]

    def _get_quantity_from_risk(self, trader, quantity):
        return quantity * trader.get_risk() / self.LIMIT_ORDER_ATTENUATION

    @staticmethod
    async def can_create_order(symbol, exchange, state, portfolio):
        return True

    async def create_new_order(self, eval_note, symbol, exchange, trader, portfolio, state):
        current_order = None

        try:
            delta_ask, delta_bid = self.verify_and_adapt_delta_with_fees(symbol)
            best_bid_price = eval_note[ExchangeConstantsOrderBookInfoColumns.BIDS.value][0]
            best_ask_price = eval_note[ExchangeConstantsOrderBookInfoColumns.ASKS.value][0]

            current_symbol_holding, current_market_quantity, market_quantity, price, symbol_market = \
                await self.get_pre_order_data(exchange, symbol, portfolio)

            created_orders = []

            # Create SHORT order
            quantity = self._get_quantity_from_risk(trader, current_symbol_holding)
            quantity = self.add_dusts_to_quantity_if_necessary(quantity, price,
                                                               symbol_market, current_symbol_holding)
            limit_price = best_ask_price - (best_ask_price * delta_ask)

            for order_quantity, order_price in self.check_and_adapt_order_details_if_necessary(quantity,
                                                                                               limit_price,
                                                                                               symbol_market):
                current_order = trader.create_order_instance(order_type=TraderOrderType.SELL_LIMIT,
                                                             symbol=symbol,
                                                             current_price=price,
                                                             quantity=order_quantity,
                                                             price=order_price)
                updated_limit = await trader.create_order(current_order, portfolio)
                created_orders.append(updated_limit)

                await trader.create_order(current_order, portfolio)

            # Create LONG order
            quantity = self._get_quantity_from_risk(trader, market_quantity)
            quantity = self.add_dusts_to_quantity_if_necessary(quantity, price,
                                                               symbol_market, current_symbol_holding)

            limit_price = best_bid_price + (best_bid_price * delta_bid)

            for order_quantity, order_price in self.check_and_adapt_order_details_if_necessary(quantity,
                                                                                               limit_price,
                                                                                               symbol_market):
                current_order = trader.create_order_instance(order_type=TraderOrderType.BUY_LIMIT,
                                                             symbol=symbol,
                                                             current_price=price,
                                                             quantity=order_quantity,
                                                             price=order_price)
                await trader.create_order(current_order, portfolio)
                created_orders.append(current_order)

            return created_orders

        except InsufficientFunds as e:
            raise e

        except Exception as e:
            self.logger.error(f"Failed to create order : {e}. "
                              f"Order: {current_order.get_string_info() if current_order else None}")
            self.logger.exception(e)
            return None


class MarketMakerTradingModeDecider(AbstractTradingModeDecider):
    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True

    def check_valid_market_making_note(self, eval_note) -> bool:
        if ExchangeConstantsOrderBookInfoColumns.BIDS.value not in eval_note or \
                ExchangeConstantsOrderBookInfoColumns.ASKS.value not in eval_note:
            self.logger.warning("Incorrect eval_note format, can't create any order.")
            return False
        return True

    def set_final_eval(self):
        for evaluated_strategies in self.symbol_evaluator.get_strategies_eval_list(self.exchange):
            strategy_eval = evaluated_strategies.get_eval_note()
            if self.check_valid_market_making_note(strategy_eval):
                self.final_eval = strategy_eval
        return self.check_valid_market_making_note(self.final_eval)

    async def create_state(self):
        # previous_state = self.state
        self.logger.info(f"{self.symbol} ** REPLACING MARKET MAKING ORDERS **")

        # cancel open orders
        await self.cancel_symbol_open_orders()

        # create notification
        if self.symbol_evaluator.matrices:
            await self.notifier.notify_alert(
                "",
                self.symbol_evaluator.get_crypto_currency_evaluator(),
                self.symbol_evaluator.get_symbol(),
                self.symbol_evaluator.get_trader(self.exchange),
                "REPLACING.ORDERS",
                self.symbol_evaluator.get_matrix(self.exchange).get_matrix())

        # call orders creation method
        await self.create_final_state_orders(self.notifier, self.trading_mode.get_only_creator_key(self.symbol))
