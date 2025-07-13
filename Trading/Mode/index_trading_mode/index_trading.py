#  Drakkar-Software OctoBot
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
import asyncio
import decimal
import enum

import octobot_commons.constants as commons_constants
import octobot_commons.enums as commons_enums
import octobot_commons.symbols.symbol_util as symbol_util
import octobot_commons.authentication as authentication
import octobot_trading.constants as trading_constants
import octobot_trading.enums as trading_enums
import octobot_trading.errors as trading_errors
import octobot_trading.modes as trading_modes
import octobot_trading.util as trading_util
import octobot_trading.personal_data as trading_personal_data

import tentacles.Trading.Mode.index_trading_mode.index_distribution as index_distribution


class IndexActivity(enum.Enum):
    REBALANCING_DONE = "rebalancing_done"
    REBALANCING_SKIPPED = "rebalancing_skipped"


class RebalanceSkipDetails(enum.Enum):
    ALREADY_BALANCED = "already_balanced"
    NOT_ENOUGH_AVAILABLE_FOUNDS = "not_enough_available_founds"


class RebalanceDetails(enum.Enum):
    SELL_SOME = "SELL_SOME"
    BUY_MORE = "BUY_MORE"
    REMOVE = "REMOVE"
    ADD = "ADD"
    SWAP = "SWAP"
    FORCED_REBALANCE = "FORCED_REBALANCE"


class SynchronizationPolicy(enum.Enum):
    SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE = "sell removed index coins on ratio rebalance"
    SELL_REMOVED_INDEX_COINS_AS_SOON_AS_POSSIBLE = "sell removed index coins as soon as possible"


class IndexTradingModeConsumer(trading_modes.AbstractTradingModeConsumer):
    FILL_ORDER_TIMEOUT = 60
    SIMPLE_ADD_MIN_TOLERANCE_RATIO = decimal.Decimal("0.8")  # 20% tolerance

    async def create_new_orders(self, symbol, _, state, **kwargs):
        details = kwargs["data"]
        if state == trading_enums.EvaluatorStates.NEUTRAL.value:
            return await self._rebalance_portfolio(details)
        self.logger.error(f"Unknown index state: {state}")
        return []

    async def _rebalance_portfolio(self, details: dict):
        self.logger.info(f"Executing rebalance on [{self.exchange_manager.exchange_name}]")
        orders = []
        try:
            # 1. make sure we can actually rebalance the portfolio
            self.logger.info("Step 1/3: ensuring enough funds are available for rebalance")
            await self._ensure_enough_funds_to_buy_after_selling()
            # 2. sell indexed coins for reference market
            is_simple_buy_without_selling = self._can_simply_buy_coins_without_selling(details)
            if is_simple_buy_without_selling:
                self.logger.info(
                    f"Step 2/3: skipped: no coin to sell for "
                    f"{self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market}"
                )
            else:
                self.logger.info(
                    f"Step 2/3: selling coins to free "
                    f"{self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market}"
                )
                orders += await self._sell_indexed_coins_for_reference_market(details)
            # 3. split reference market into indexed coins
            self.logger.info(
                f"Step 3/3: buying coins using "
                f"{self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market}"
            )
            orders += await self._split_reference_market_into_indexed_coins(details, is_simple_buy_without_selling)
        except trading_errors.MissingMinimalExchangeTradeVolume as err:
            self.logger.warning(f"Aborting rebalance on {self.exchange_manager.exchange_name}: {err}")
            self._update_producer_last_activity(
                IndexActivity.REBALANCING_SKIPPED,
                RebalanceSkipDetails.NOT_ENOUGH_AVAILABLE_FOUNDS.value
            )
        finally:
            self.logger.info("Portoflio rebalance complete")
        return orders

    async def _sell_indexed_coins_for_reference_market(self, details: dict) -> list:
        removed_coins_to_sell_orders = []
        if removed_coins_to_sell := list(details[RebalanceDetails.REMOVE.value]):
            removed_coins_to_sell_orders = await trading_modes.convert_assets_to_target_asset(
                self.trading_mode, removed_coins_to_sell,
                self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market, {}
            )
            if (
                details[RebalanceDetails.REMOVE.value] and
                not (
                    details[RebalanceDetails.BUY_MORE.value]
                    or details[RebalanceDetails.ADD.value]
                    or details[RebalanceDetails.SWAP.value]
                )
            ):
                # if rebalance is triggered by removed assets, make sure that the asset can actually be sold
                # otherwise the whole rebalance is useless
                sold_coins = [
                    symbol_util.parse_symbol(order.symbol).base
                    if order.side is trading_enums.TradeOrderSide.SELL
                    else symbol_util.parse_symbol(order.symbol).quote
                    for order in removed_coins_to_sell_orders
                ]
                if not any(
                    asset in sold_coins
                    for asset in details[RebalanceDetails.REMOVE.value]
                ):
                    self.logger.info(
                        f"Cancelling rebalance: not enough {list(details[RebalanceDetails.REMOVE.value])} funds to sell"
                    )
                    raise trading_errors.MissingMinimalExchangeTradeVolume(
                        f"not enough {list(details[RebalanceDetails.REMOVE.value])} funds to sell"
                    )
        order_coins_to_sell = self._get_coins_to_sell(details)
        orders = await trading_modes.convert_assets_to_target_asset(
            self.trading_mode, order_coins_to_sell,
            self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market, {}
        ) + removed_coins_to_sell_orders
        if orders:
            # ensure orders are filled
            await asyncio.gather(
                *[
                    trading_personal_data.wait_for_order_fill(
                        order, self.FILL_ORDER_TIMEOUT, True
                    ) for order in orders
                ]
            )
        return orders

    def _get_coins_to_sell(self, details: dict) -> list:
        return list(details[RebalanceDetails.SWAP.value]) or (
            self.trading_mode.indexed_coins
        )

    def _can_simply_buy_coins_without_selling(self, details: dict) -> bool:
        simple_buy_coins = self._get_simple_buy_coins(details)
        if not simple_buy_coins:
            return False
        # check if there is enough free funds to buy those coins
        ref_market = self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
        reference_market_to_split = self.exchange_manager.exchange_personal_data.portfolio_manager. \
            portfolio_value_holder.get_traded_assets_holdings_value(ref_market, None)
        free_reference_market_holding = \
            self.exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio(
                ref_market
            ).available
        cumulated_ratio = sum(
            self.trading_mode.get_target_ratio(coin)
            for coin in simple_buy_coins
        )
        tolerated_min_amount = reference_market_to_split * cumulated_ratio * self.SIMPLE_ADD_MIN_TOLERANCE_RATIO
        # can reach target ratios without selling if this condition is met
        return tolerated_min_amount <= free_reference_market_holding


    def _get_simple_buy_coins(self, details: dict) -> list:
        # Returns the list of coins to simply buy.
        # Used to avoid a full rebalance when coins are seen as added to a basket
        # AND funds are available to buy it AND no asset should be sold
        added = details[RebalanceDetails.ADD.value] or details[RebalanceDetails.BUY_MORE.value]
        if added and not (
            details[RebalanceDetails.SWAP.value]
            or details[RebalanceDetails.SELL_SOME.value]
            or details[RebalanceDetails.REMOVE.value]
            or details[RebalanceDetails.FORCED_REBALANCE.value]
        ):
            added_coins = list(details[RebalanceDetails.ADD.value]) + list(details[RebalanceDetails.BUY_MORE.value])
            return [
                coin
                for coin in self.trading_mode.indexed_coins # iterate over self.trading_mode.indexed_coins to keep order
                if coin in added_coins
            ] + [
                coin
                for coin in added_coins
                if coin not in self.trading_mode.indexed_coins
            ]
        return []

    async def _ensure_enough_funds_to_buy_after_selling(self):
        reference_market_to_split = self.exchange_manager.exchange_personal_data.portfolio_manager. \
            portfolio_value_holder.get_traded_assets_holdings_value(
                self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market, None
            )
        # will raise if funds are missing
        await self._get_symbols_and_amounts(self.trading_mode.indexed_coins, reference_market_to_split)

    async def _split_reference_market_into_indexed_coins(self, details: dict, is_simple_buy_without_selling: bool):
        orders = []
        ref_market = self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
        if details[RebalanceDetails.SWAP.value] or is_simple_buy_without_selling:
            # has to infer total reference market holdings
            reference_market_to_split = self.exchange_manager.exchange_personal_data.portfolio_manager. \
                portfolio_value_holder.get_traded_assets_holdings_value(ref_market, None)
            coins_to_buy = (
                self._get_simple_buy_coins(details) if is_simple_buy_without_selling
                else list(details[RebalanceDetails.SWAP.value].values())
            )
        else:
            # can use actual reference market holdings: everything has been sold
            reference_market_to_split = \
                self.exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio(
                    ref_market
                ).available
            coins_to_buy = self.trading_mode.indexed_coins
        self.logger.info(f"Splitting {reference_market_to_split} {ref_market} to buy {coins_to_buy}")
        amount_by_symbol = await self._get_symbols_and_amounts(coins_to_buy, reference_market_to_split)
        for symbol, ideal_amount in amount_by_symbol.items():
            orders.extend(await self._buy_coin(symbol, ideal_amount))
        if not orders:
            raise trading_errors.MissingMinimalExchangeTradeVolume()
        return orders

    async def _get_symbols_and_amounts(self, coins_to_buy, reference_market_to_split):
        amount_by_symbol = {}
        for coin in coins_to_buy:
            if coin == self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market:
                # nothing to do for reference market, keep as is
                continue
            symbol = symbol_util.merge_currencies(
                coin,
                self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
            )
            price = await trading_personal_data.get_up_to_date_price(
                self.exchange_manager, symbol, timeout=trading_constants.ORDER_DATA_FETCHING_TIMEOUT
            )
            symbol_market = self.exchange_manager.exchange.get_market_status(symbol, with_fixer=False)
            ratio = self.trading_mode.get_target_ratio(coin)
            if ratio == trading_constants.ZERO:
                # coin is not to handle
                continue
            ideal_amount = ratio * reference_market_to_split / price
            # worse case (ex with 5USDT min order size): exactly 5 USDT can be in portfolio, we therefore want to
            # trade at lease 5 USDT to be able to buy more.
            # - we want ideal_amount - min_cost > min_cost
            # - in other words ideal_amount > 2*min_cost => ideal_amount/2 > min cost
            adapted_quantity = trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                ideal_amount / decimal.Decimal(2),
                price,
                symbol_market
            )
            if not adapted_quantity:
                # if we can't create an order in this case, we won't be able to balance the portfolio.
                # don't try to avoid triggering new rebalances on each wakeup cycling market sell & buy orders
                raise trading_errors.MissingMinimalExchangeTradeVolume(
                    f"Can't buy {symbol}: available funds are too low to buy {ratio*trading_constants.ONE_HUNDRED}% "
                    f"of {reference_market_to_split} holdings: {round(ideal_amount / decimal.Decimal(2), 9)} {coin} "
                    f"required order size is not compatible with {symbol} exchange requirements: "
                    f"{symbol_market[trading_enums.ExchangeConstantsMarketStatusColumns.LIMITS.value]}."
                )
            amount_by_symbol[symbol] = ideal_amount
        return amount_by_symbol

    async def _buy_coin(self, symbol, ideal_amount) -> list:
        current_symbol_holding, current_market_holding, market_quantity, price, symbol_market = \
            await trading_personal_data.get_pre_order_data(
                self.exchange_manager, symbol=symbol, timeout=trading_constants.ORDER_DATA_FETCHING_TIMEOUT
            )
        order_target_price = price
        # ideally use the expected reference_market_available_holdings ratio, fallback to available
        # holdings if necessary
        target_quantity = min(ideal_amount, current_market_holding / order_target_price)
        ideal_quantity = target_quantity - current_symbol_holding
        if ideal_quantity <= trading_constants.ZERO:
            return []
        quantity = trading_personal_data.decimal_adapt_order_quantity_because_fees(
            self.exchange_manager, symbol, trading_enums.TraderOrderType.BUY_MARKET, ideal_quantity,
            order_target_price, trading_enums.TradeOrderSide.BUY
        )
        created_orders = []
        orders_should_have_been_created = False
        ideal_order_type = trading_enums.TraderOrderType.BUY_MARKET
        order_type = (
            ideal_order_type
            if self.exchange_manager.exchange.is_market_open_for_order_type(symbol, ideal_order_type)
            else trading_enums.TraderOrderType.BUY_LIMIT
        )

        if trading_personal_data.get_trade_order_type(order_type) is not trading_enums.TradeOrderType.MARKET:
            # can't use market orders: use limit orders with price a bit above the current price to instant fill it.
            order_target_price, quantity = \
                trading_modes.get_instantly_filled_limit_order_adapted_price_and_quantity(
                    order_target_price, quantity, order_type
                )
        for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
            quantity,
            order_target_price,
            symbol_market
        ):
            orders_should_have_been_created = True
            current_order = trading_personal_data.create_order_instance(
                trader=self.exchange_manager.trader,
                order_type=order_type,
                symbol=symbol,
                current_price=price,
                quantity=order_quantity,
                price=order_price,
            )
            created_order = await self.trading_mode.create_order(current_order)
            created_orders.append(created_order)
        if created_orders:
            return created_orders
        if orders_should_have_been_created:
            raise trading_errors.OrderCreationError()
        raise trading_errors.MissingMinimalExchangeTradeVolume()


class IndexTradingModeProducer(trading_modes.AbstractTradingModeProducer):
    REFRESH_INTERVAL = "refresh_interval"
    CANCEL_OPEN_ORDERS = "cancel_open_orders"
    REBALANCE_TRIGGER_MIN_PERCENT = "rebalance_trigger_min_percent"
    QUOTE_ASSET_REBALANCE_TRIGGER_MIN_PERCENT = "quote_asset_rebalance_trigger_min_percent"
    SYNCHRONIZATION_POLICY = "synchronization_policy"
    SELL_UNINDEXED_TRADED_COINS = "sell_unindexed_traded_coins"
    INDEX_CONTENT = "index_content"
    MIN_INDEXED_COINS = 1
    ALLOWED_1_TO_1_SWAP_COUNTS = 1
    MIN_RATIO_TO_SELL = decimal.Decimal("0.0001")  # 1/10000
    QUOTE_ASSET_TO_INDEXED_SWAP_RATIO_THRESHOLD = decimal.Decimal("0.1")  # 10%

    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)
        self._last_trigger_time = 0
        self.state = trading_enums.EvaluatorStates.NEUTRAL

    async def stop(self):
        if self.trading_mode is not None:
            self.trading_mode.flush_trading_mode_consumers()
        await super().stop()

    async def ohlcv_callback(self, exchange: str, exchange_id: str, cryptocurrency: str, symbol: str,
                             time_frame: str, candle: dict, init_call: bool = False):
        await self._check_index_if_necessary()

    async def kline_callback(self, exchange: str, exchange_id: str, cryptocurrency: str, symbol: str,
                             time_frame, kline: dict):
        await self._check_index_if_necessary()

    async def _check_index_if_necessary(self):
        current_time = self.exchange_manager.exchange.get_exchange_current_time()
        if (
            current_time - self._last_trigger_time
        ) >= self.trading_mode.refresh_interval_days * commons_constants.DAYS_TO_SECONDS:
            if self.trading_mode.automatically_update_historical_config_on_set_intervals():
                self.trading_mode.update_config_and_user_inputs_if_necessary()
            if len(self.trading_mode.indexed_coins) < self.MIN_INDEXED_COINS:
                self.logger.error(
                    f"At least {self.MIN_INDEXED_COINS} coin is required to maintain an index. Please "
                    f"select more trading pairs using "
                    f"{self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market} as "
                    f"quote currency."
                )
            else:
                self._notify_if_missing_too_many_coins()
                await self.ensure_index()
            if not self.trading_mode.is_updating_at_each_price_change():
                self.logger.debug(f"Next index check in {self.trading_mode.refresh_interval_days} days")
            self._last_trigger_time = current_time

    async def ensure_index(self):
        await self._wait_for_symbol_prices_and_profitability_init(self._get_config_init_timeout())
        self.logger.info(
            f"Ensuring Index on [{self.exchange_manager.exchange_name}] "
            f"{len(self.trading_mode.indexed_coins)} coins: {self.trading_mode.indexed_coins} with reference market: "
            f"{self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market}"
        )
        if self.trading_mode.cancel_open_orders:
            await self.cancel_traded_pairs_open_orders_if_any()
        if self.trading_mode.requires_initializing_appropriate_coins_distribution:
            self.trading_mode.ensure_updated_coins_distribution(adapt_to_holdings=True)
            self.trading_mode.requires_initializing_appropriate_coins_distribution = False
        is_rebalance_required, rebalance_details = self._get_rebalance_details()
        if is_rebalance_required:
            await self._trigger_rebalance(rebalance_details)
            self.last_activity = trading_modes.TradingModeActivity(
                IndexActivity.REBALANCING_DONE,
                rebalance_details,
            )
        else:
            self.logger.info(
                f"[{self.exchange_manager.exchange_name}] is following the index: no rebalance is required."
            )
            self.last_activity = trading_modes.TradingModeActivity(IndexActivity.REBALANCING_SKIPPED)

    async def _trigger_rebalance(self, rebalance_details: dict):
        self.logger.info(
            f"Triggering rebalance on [{self.exchange_manager.exchange_name}] "
            f"with rebalance details: {rebalance_details}."
        )
        await self.submit_trading_evaluation(
            cryptocurrency=None,
            symbol=None,    # never set symbol in order to skip consumer.can_create_order check
            time_frame=None,
            final_note=None,
            state=trading_enums.EvaluatorStates.NEUTRAL,
            data=rebalance_details
        )
        # send_notification
        await self._send_alert_notification()

    async def _send_alert_notification(self):
        if self.exchange_manager.is_backtesting:
            return
        try:
            import octobot_services.api as services_api
            import octobot_services.enums as services_enum
            title = "Index trigger"
            alert = f"Rebalance triggered for {len(self.trading_mode.indexed_coins)} coins"
            await services_api.send_notification(services_api.create_notification(
                alert, title=title, markdown_text=alert,
                category=services_enum.NotificationCategory.PRICE_ALERTS
            ))
        except ImportError as e:
            self.logger.exception(e, True, f"Impossible to send notification: {e}")

    def _notify_if_missing_too_many_coins(self):
        if ideal_distribution := self.trading_mode.get_ideal_distribution(self.trading_mode.trading_config):
            if len(self.trading_mode.indexed_coins) < len(ideal_distribution) / 2:
                self.logger.error(
                    f"Less than half of configured coins can be traded on {self.exchange_manager.exchange_name}. "
                    f"Traded: {self.trading_mode.indexed_coins}, configured: {ideal_distribution}"
                )

    def _register_coins_update(self, rebalance_details: dict) -> bool:
        should_rebalance = False
        for coin in set(self.trading_mode.indexed_coins):
            target_ratio = self.trading_mode.get_target_ratio(coin)
            coin_ratio = self.exchange_manager.exchange_personal_data.portfolio_manager. \
                portfolio_value_holder.get_holdings_ratio(
                    coin, traded_symbols_only=True
                )
            beyond_ratio = True
            if coin_ratio == trading_constants.ZERO and target_ratio > trading_constants.ZERO:
                # missing coin in portfolio
                rebalance_details[RebalanceDetails.ADD.value][coin] = target_ratio
                should_rebalance = True
            elif coin_ratio < target_ratio - self.trading_mode.rebalance_trigger_min_ratio:
                # not enough in portfolio
                rebalance_details[RebalanceDetails.BUY_MORE.value][coin] = target_ratio
                should_rebalance = True
            elif coin_ratio > target_ratio + self.trading_mode.rebalance_trigger_min_ratio:
                # too much in portfolio
                rebalance_details[RebalanceDetails.SELL_SOME.value][coin] = target_ratio
                should_rebalance = True
            else:
                beyond_ratio = False
            if beyond_ratio:
                self.logger.info(
                    f"{coin} is beyond the target ratio of {round(target_ratio * trading_constants.ONE_HUNDRED, 3)}%, "
                    f"ratio: {round(coin_ratio * trading_constants.ONE_HUNDRED, 3)}%. A rebalance is required."
                )
        return should_rebalance

    def _register_removed_coin(self, rebalance_details: dict, available_traded_bases: set[str]) -> bool:
        should_rebalance = False
        for coin in self.trading_mode.get_removed_coins_from_config(available_traded_bases):
            if coin in available_traded_bases:
                coin_ratio = self.exchange_manager.exchange_personal_data.portfolio_manager. \
                    portfolio_value_holder.get_holdings_ratio(
                        coin, traded_symbols_only=True
                    )
                if coin_ratio >= self.MIN_RATIO_TO_SELL:
                    # coin to sell in portfolio
                    rebalance_details[RebalanceDetails.REMOVE.value][coin] = coin_ratio
                    self.logger.info(
                        f"{coin} (holdings: {round(coin_ratio * trading_constants.ONE_HUNDRED, 3)}%) is not in index "
                        f"anymore. A rebalance is required."
                    )
                    should_rebalance = True
            else:
                if trading_util.is_symbol_disabled(self.exchange_manager.config, coin):
                    self.logger.info(
                        f"Ignoring {coin} holding: {coin} is not in index anymore but is disabled."
                    )
                else:
                    self.logger.error(
                        f"Ignoring {coin} holding: Can't sell {coin} as it is not in any trading pair"
                        f" but is not in index anymore. This is unexpected"
                    )
        return should_rebalance

    def _register_quote_asset_rebalance(self, rebalance_details: dict) -> bool:
        non_indexed_quote_assets_ratio = self._get_non_indexed_quote_assets_ratio()
        if self._should_rebalance_due_to_non_indexed_quote_assets_ratio(
            non_indexed_quote_assets_ratio, rebalance_details
        ):
            rebalance_details[RebalanceDetails.FORCED_REBALANCE.value] = True
            self.logger.info(
                f"Rebalancing due to a high non-indexed quote asset holdings ratio: "
                f"{round(non_indexed_quote_assets_ratio * trading_constants.ONE_HUNDRED, 2)}%, quote rebalance "
                f"threshold = {self.trading_mode.quote_asset_rebalance_ratio_threshold * trading_constants.ONE_HUNDRED}%"
            )
            return True
        return False
    
    def _empty_rebalance_details(self) -> dict:
        return {
            RebalanceDetails.SELL_SOME.value: {},
            RebalanceDetails.BUY_MORE.value: {},
            RebalanceDetails.REMOVE.value: {},
            RebalanceDetails.ADD.value: {},
            RebalanceDetails.SWAP.value: {},
            RebalanceDetails.FORCED_REBALANCE.value: False,
        }

    def _get_rebalance_details(self) -> (bool, dict):
        rebalance_details = self._empty_rebalance_details()
        should_rebalance = False
        # look for coins update in indexed_coins
        available_traded_bases = set(
            symbol.base
            for symbol in self.exchange_manager.exchange_config.traded_symbols
        )

        # compute rebalance details for current coins distribution
        if self.trading_mode.synchronization_policy == SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_AS_SOON_AS_POSSIBLE:
            should_rebalance = self._register_removed_coin(rebalance_details, available_traded_bases)
        should_rebalance = self._register_coins_update(rebalance_details) or should_rebalance
        should_rebalance = self._register_quote_asset_rebalance(rebalance_details) or should_rebalance
        if (
            should_rebalance 
            and self.trading_mode.synchronization_policy == SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE
        ):
            # use latest coins distribution to compute rebalance details
            self.trading_mode.ensure_updated_coins_distribution(force_latest=True)
            # re-compute the whole rebalance details for latest coins distribution 
            # to avoid side effects from previous distribution
            rebalance_details = self._empty_rebalance_details()
            self._register_removed_coin(rebalance_details, available_traded_bases)
            self._register_coins_update(rebalance_details)
            self._register_quote_asset_rebalance(rebalance_details)

        if not rebalance_details[RebalanceDetails.FORCED_REBALANCE.value]:
            # finally, compute swaps when no forced rebalance is required
            self._resolve_swaps(rebalance_details)
            for origin, target in rebalance_details[RebalanceDetails.SWAP.value].items():
                origin_ratio = round(
                    rebalance_details[RebalanceDetails.REMOVE.value][origin] * trading_constants.ONE_HUNDRED,
                    3
                )
                target_ratio = round(
                    rebalance_details[RebalanceDetails.ADD.value].get(
                        target,
                        rebalance_details[RebalanceDetails.BUY_MORE.value].get(target, trading_constants.ZERO)
                    ) * trading_constants.ONE_HUNDRED,
                    3
                ) or "???"
                self.logger.info(
                    f"Swapping {origin} (holding ratio: {origin_ratio}%) for {target} (to buy ratio: {target_ratio}%) "
                    f"on [{self.exchange_manager.exchange_name}]: ratios are similar enough to allow swapping."
                )   
        return (should_rebalance or rebalance_details[RebalanceDetails.FORCED_REBALANCE.value]), rebalance_details

    def _should_rebalance_due_to_non_indexed_quote_assets_ratio(self, non_indexed_quote_assets_ratio: decimal.Decimal, rebalance_details: dict) -> bool:
        total_added_ratio = (
            self._sum_ratios(rebalance_details, RebalanceDetails.ADD.value) 
            + self._sum_ratios(rebalance_details, RebalanceDetails.BUY_MORE.value)
        )
        
        if (
            total_added_ratio * (trading_constants.ONE - self.QUOTE_ASSET_TO_INDEXED_SWAP_RATIO_THRESHOLD)
            <= non_indexed_quote_assets_ratio
            <= total_added_ratio * (trading_constants.ONE + self.QUOTE_ASSET_TO_INDEXED_SWAP_RATIO_THRESHOLD)
        ):
            total_removed_ratio = (
                self._sum_ratios(rebalance_details, RebalanceDetails.REMOVE.value) 
                + self._sum_ratios(rebalance_details, RebalanceDetails.SELL_SOME.value)
            )
            # added coins are equivalent to free quote assets: just buy with quote assets
            if total_removed_ratio == trading_constants.ZERO:
                return False
        # there are removed coins or added ratio is not equivalent to free quote assets: rebalance if necessary
        min_ratio = min(
            min(
                self.trading_mode.get_target_ratio(coin)
                for coin in self.trading_mode.indexed_coins
            ) if self.trading_mode.indexed_coins else self.trading_mode.quote_asset_rebalance_ratio_threshold,
            self.trading_mode.quote_asset_rebalance_ratio_threshold
        )
        return non_indexed_quote_assets_ratio >= min_ratio

    @staticmethod
    def _sum_ratios(rebalance_details: dict, key: str) -> decimal.Decimal:
        return decimal.Decimal(str(sum(
            ratio
            for ratio in rebalance_details[key].values()
        ))) if rebalance_details[key] else trading_constants.ZERO 

    def _get_non_indexed_quote_assets_ratio(self) -> decimal.Decimal:
        return decimal.Decimal(str(sum(
            self.exchange_manager.exchange_personal_data.portfolio_manager. \
                portfolio_value_holder.get_holdings_ratio(
                    quote, traded_symbols_only=True
                )
            for quote in set(
                symbol.quote
                for symbol in self.exchange_manager.exchange_config.traded_symbols
                if symbol.quote not in self.trading_mode.indexed_coins
            )
        )))

    def _resolve_swaps(self, details: dict):
        removed = details[RebalanceDetails.REMOVE.value]
        details[RebalanceDetails.SWAP.value] = {}
        if details[RebalanceDetails.SELL_SOME.value]:
            # rebalance within held coins: global rebalance required
            return
        added = {**details[RebalanceDetails.ADD.value], **details[RebalanceDetails.BUY_MORE.value]}
        if len(removed) == len(added) == self.ALLOWED_1_TO_1_SWAP_COUNTS:
            for removed_coin, removed_ratio, added_coin, added_ratio in zip(
                removed, removed.values(), added, added.values()
            ):
                added_holding_ratio = self.exchange_manager.exchange_personal_data.portfolio_manager. \
                    portfolio_value_holder.get_holdings_ratio(
                        added_coin, traded_symbols_only=True,
                        coins_whitelist=self.trading_mode.get_coins_to_consider_for_ratio()
                    )
                required_added_ratio = added_ratio - added_holding_ratio
                if (
                    removed_ratio - self.trading_mode.rebalance_trigger_min_ratio
                    < required_added_ratio
                    < removed_ratio + self.trading_mode.rebalance_trigger_min_ratio
                ):
                    # removed can be swapped for added: only sell removed
                    details[RebalanceDetails.SWAP.value][removed_coin] = added_coin
                else:
                    # reset to_sell to sell everything
                    details[RebalanceDetails.SWAP.value] = {}
                    return

    def get_channels_registration(self):
        # use candles to trigger at each candle interval and when initializing
        topics = [
            self.TOPIC_TO_CHANNEL_NAME[commons_enums.ActivationTopics.FULL_CANDLES.value],
        ]
        if self.trading_mode.is_updating_at_each_price_change():
            # use kline to trigger at each price change
            self.logger.info(f"Using price change bound update instead of time-based update.")
            topics.append(
                self.TOPIC_TO_CHANNEL_NAME[commons_enums.ActivationTopics.IN_CONSTRUCTION_CANDLES.value]
            )
        return topics

    async def cancel_traded_pairs_open_orders_if_any(self):
        if symbol_open_orders := [
            order
            for order in self.exchange_manager.exchange_personal_data.orders_manager.get_open_orders()
            if order.symbol in self.exchange_manager.exchange_config.traded_symbol_pairs
        ]:
            self.logger.info(
                f"Cancelling {len(symbol_open_orders)} open orders"
            )
            for order in symbol_open_orders:
                try:
                    await self.trading_mode.cancel_order(order)
                except trading_errors.UnexpectedExchangeSideOrderStateError as err:
                    self.logger.warning(f"Skipped order cancel: {err}, order: {order}")


class IndexTradingMode(trading_modes.AbstractTradingMode):
    MODE_PRODUCER_CLASSES = [IndexTradingModeProducer]
    MODE_CONSUMER_CLASSES = [IndexTradingModeConsumer]
    SUPPORTS_INITIAL_PORTFOLIO_OPTIMIZATION = True
    SUPPORTS_HEALTH_CHECK = False

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.refresh_interval_days = 1
        self.rebalance_trigger_min_ratio = decimal.Decimal("0.05")  # 5%
        self.ratio_per_asset = {}
        self.sell_unindexed_traded_coins = True
        self.cancel_open_orders = True
        self.total_ratio_per_asset = trading_constants.ZERO
        self.quote_asset_rebalance_ratio_threshold = decimal.Decimal("0.1")  # 10%
        self.synchronization_policy: SynchronizationPolicy = SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_AS_SOON_AS_POSSIBLE
        self.requires_initializing_appropriate_coins_distribution = False
        self.indexed_coins = [] 

    def init_user_inputs(self, inputs: dict) -> None:
        """
        Called right before starting the tentacle, should define all the tentacle's user inputs unless
        those are defined somewhere else.
        """
        trading_config = self.trading_config
        self.refresh_interval_days = float(self.UI.user_input(
            IndexTradingModeProducer.REFRESH_INTERVAL, commons_enums.UserInputTypes.FLOAT,
            self.refresh_interval_days, inputs,
            min_val=0,
            title="Trigger period: Days to wait between each rebalance. Can be a fraction of a day. "
                  "When set to 0, every new price will trigger a rebalance check.",
        ))
        self.rebalance_trigger_min_ratio = decimal.Decimal(str(self.UI.user_input(
            IndexTradingModeProducer.REBALANCE_TRIGGER_MIN_PERCENT, commons_enums.UserInputTypes.FLOAT,
            float(self.rebalance_trigger_min_ratio * trading_constants.ONE_HUNDRED), inputs,
            min_val=0, max_val=100,
            title="Rebalance cap: maximum allowed percent holding of a coin beyond initial ratios before "
                  "triggering a rebalance.",
        ))) / trading_constants.ONE_HUNDRED
        self.quote_asset_rebalance_ratio_threshold = decimal.Decimal(str(self.UI.user_input(
            IndexTradingModeProducer.QUOTE_ASSET_REBALANCE_TRIGGER_MIN_PERCENT, commons_enums.UserInputTypes.FLOAT,
            float(self.quote_asset_rebalance_ratio_threshold * trading_constants.ONE_HUNDRED), inputs,
            min_val=0, max_val=100,
            title="Quote asset rebalance cap: maximum allowed percent holding of traded pairs' quote asset before "
                  "triggering a rebalance. Useful to force a rebalance when adding quote asset to the portfolio",
        ))) / trading_constants.ONE_HUNDRED
        sync_policy: str = self.UI.user_input(
            IndexTradingModeProducer.SYNCHRONIZATION_POLICY, commons_enums.UserInputTypes.OPTIONS,
            self.synchronization_policy.value, inputs, 
            options=[p.value for p in SynchronizationPolicy],
            title="Synchronization policy: should coins that are removed from index be sold as soon as possible or only when rebalancing is triggered when coins don't follow the configured ratios.",
        )
        try:
            self.synchronization_policy = SynchronizationPolicy(sync_policy)
        except TypeError as err:
            self.logger.exception(
                err, 
                True, 
                f"Impossible to parse synchronization policy: {err}. Using default policy: {self.synchronization_policy.value}."
            )
        self.cancel_open_orders = float(self.UI.user_input(
            IndexTradingModeProducer.CANCEL_OPEN_ORDERS, commons_enums.UserInputTypes.BOOLEAN,
            self.cancel_open_orders, inputs,
            title="Cancel open orders: When enabled, open orders of the index trading pairs will be canceled to free "
                  "funds and invest in the index content.",
        ))
        self.sell_unindexed_traded_coins = trading_config.get(
            IndexTradingModeProducer.SELL_UNINDEXED_TRADED_COINS,
            self.sell_unindexed_traded_coins
        )
        if (not self.exchange_manager or not self.exchange_manager.is_backtesting) and \
                authentication.Authenticator.instance().has_open_source_package():
            self.UI.user_input(IndexTradingModeProducer.INDEX_CONTENT, commons_enums.UserInputTypes.OBJECT_ARRAY,
                               trading_config.get(IndexTradingModeProducer.INDEX_CONTENT, None), inputs,
                               item_title="Coin",
                               other_schema_values={"minItems": 0, "uniqueItems": True},
                               title="Custom distribution: when used, only coins listed in this distribution and "
                                     "in your profile traded pairs will be traded. "
                                     "Leave empty to evenly allocate funds in each traded coin.")
            self.UI.user_input(index_distribution.DISTRIBUTION_NAME, commons_enums.UserInputTypes.TEXT,
                               "BTC", inputs,
                               other_schema_values={"minLength": 1},
                               parent_input_name=IndexTradingModeProducer.INDEX_CONTENT,
                               title="Name of the coin.")
            self.UI.user_input(index_distribution.DISTRIBUTION_VALUE, commons_enums.UserInputTypes.FLOAT,
                               50, inputs,
                               min_val=0,
                               parent_input_name=IndexTradingModeProducer.INDEX_CONTENT,
                               title="Weight of the coin within this distribution.")
        self.requires_initializing_appropriate_coins_distribution = self.synchronization_policy == SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE
        self.ensure_updated_coins_distribution()

    @classmethod
    def get_tentacle_config_traded_symbols(cls, config: dict, reference_market: str) -> list:
        return [
            symbol_util.merge_currencies(asset[index_distribution.DISTRIBUTION_NAME], reference_market)
            for asset in (cls.get_ideal_distribution(config) or [])
        ]

    def is_updating_at_each_price_change(self):
        return self.refresh_interval_days == 0

    def automatically_update_historical_config_on_set_intervals(self) -> bool:
        return (
            self.supports_historical_config() 
            and self.synchronization_policy == SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_AS_SOON_AS_POSSIBLE
        )

    def ensure_updated_coins_distribution(self, adapt_to_holdings: bool = False, force_latest: bool = False):
        distribution = self._get_supported_distribution(adapt_to_holdings, force_latest)
        self.ratio_per_asset = {
            asset[index_distribution.DISTRIBUTION_NAME]: asset
            for asset in distribution
        }
        self.total_ratio_per_asset = decimal.Decimal(sum(
            asset[index_distribution.DISTRIBUTION_VALUE]
            for asset in self.ratio_per_asset.values()
        ))
        self.indexed_coins = self._get_filtered_traded_coins(self.ratio_per_asset)

    def _get_filtered_traded_coins(self, ratio_per_asset: dict):
        if self.exchange_manager:
            ref_market = self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
            coins = set(
                symbol.base
                for symbol in self.exchange_manager.exchange_config.traded_symbols
                if symbol.base in ratio_per_asset and symbol.quote == ref_market
            )
            if ref_market in ratio_per_asset and coins:
                # there is at least 1 coin traded against ref market, can add ref market if necessary
                coins.add(ref_market)
            return sorted(list(coins))
        return []

    def get_coins_to_consider_for_ratio(self) -> list:
        return self.indexed_coins + [self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market]

    @classmethod
    def get_ideal_distribution(cls, config: dict):
        return config.get(IndexTradingModeProducer.INDEX_CONTENT, None)

    def _get_currently_applied_historical_config_according_to_holdings(
        self, config: dict, traded_bases: set[str]
    ) -> dict:
        # 1. check if latest config is the running one
        if self._is_index_config_applied(config, traded_bases):
            self.logger.info(f"Using {self.get_name()} latest config.")
            return config
        # 2. check if historical configs are available (iterating from most recent to oldest)
        historical_configs = self.get_historical_configs(
            0, self.exchange_manager.exchange.get_exchange_current_time()
        )
        if not historical_configs or (
            # only 1 historical config which is the same as the latest config
            len(historical_configs) == 1 and (
                self.get_ideal_distribution(historical_configs[0]) == self.get_ideal_distribution(config)
                and historical_configs[0][IndexTradingModeProducer.REBALANCE_TRIGGER_MIN_PERCENT] == config[IndexTradingModeProducer.REBALANCE_TRIGGER_MIN_PERCENT]
            )
        ):
            # current config is the first historical config
            self.logger.info(f"Using {self.get_name()} latest config as no historical configs are available.")
            return config
        for index, historical_config in enumerate(historical_configs):
            if self._is_index_config_applied(historical_config, traded_bases):
                self.logger.info(f"Using [N-{index}] {self.get_name()} historical config: {historical_config}.")
                return historical_config
        # 3. no suitable config found: return latest config
        self.logger.info(f"No suitable {self.get_name()} config found: using latest config: {config}.")
        return config

    def _is_index_config_applied(self, config: dict, traded_bases: set[str]) -> bool:
        full_assets_distribution = self.get_ideal_distribution(config)
        if not full_assets_distribution:
            return False
        # ignore assets that are not traded (handle delisted coins)
        assets_distribution = [
            asset
            for asset in full_assets_distribution
            if asset[index_distribution.DISTRIBUTION_NAME] in traded_bases
        ]
        total_ratio = decimal.Decimal(sum(
            asset[index_distribution.DISTRIBUTION_VALUE]
            for asset in assets_distribution
        ))
        if total_ratio == trading_constants.ZERO:
            return False
        if config_min_ratio := config.get(IndexTradingModeProducer.REBALANCE_TRIGGER_MIN_PERCENT):
            min_trigger_ratio = decimal.Decimal(str(config_min_ratio)) / trading_constants.ONE_HUNDRED
        else:
            min_trigger_ratio =  self.rebalance_trigger_min_ratio
        for asset_distrib in assets_distribution:
            target_ratio = decimal.Decimal(str(asset_distrib[index_distribution.DISTRIBUTION_VALUE])) / total_ratio
            coin_ratio = self.exchange_manager.exchange_personal_data.portfolio_manager. \
                portfolio_value_holder.get_holdings_ratio(
                    asset_distrib[index_distribution.DISTRIBUTION_NAME], traded_symbols_only=True
                )
            if not (target_ratio - min_trigger_ratio <= coin_ratio <= target_ratio + min_trigger_ratio):
                # not enough or too much in portfolio
                return False
        return True

    def _get_supported_distribution(self, adapt_to_holdings: bool, force_latest: bool) -> list:
        if detailed_distribution := self.get_ideal_distribution(self.trading_config):
            traded_bases = set(
                symbol.base
                for symbol in self.exchange_manager.exchange_config.traded_symbols
            )
            traded_bases.add(self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market)
            if (
                (adapt_to_holdings or force_latest) 
                and self.synchronization_policy == SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE
            ):
                if adapt_to_holdings:
                    # when policy is SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE, the latest config might not be the 
                    # running one: confirm this using historical configs
                    index_config = self._get_currently_applied_historical_config_according_to_holdings(
                        self.trading_config, traded_bases
                    )
                else:
                    # force latest available config
                    try:
                        index_config = self.get_historical_configs(
                            0, self.exchange_manager.exchange.get_exchange_current_time()
                        )[0]
                        self.logger.info(f"Updated {self.get_name()} to use latest config: {index_config}.")
                    except IndexError:
                        index_config = self.trading_config
                detailed_distribution = self.get_ideal_distribution(index_config)
                if not detailed_distribution:
                    raise ValueError(f"No distribution found in historical index config: {index_config}")
            distribution = [
                asset
                for asset in detailed_distribution
                if asset[index_distribution.DISTRIBUTION_NAME] in traded_bases
            ]
            if removed_assets := [
                asset[index_distribution.DISTRIBUTION_NAME]
                for asset in detailed_distribution
                if asset not in distribution
            ]:
                self.logger.info(
                    f"Ignored {len(removed_assets)} assets {removed_assets} from configured "
                    f"distribution as absent from traded pairs."
                )
            return distribution
        else:
            # compute uniform distribution over traded assets
            return index_distribution.get_uniform_distribution([
                symbol.base
                for symbol in self.exchange_manager.exchange_config.traded_symbols
            ]) if self.exchange_manager else []

    def get_removed_coins_from_config(self, available_traded_bases) -> list:
        removed_coins = []
        if self.get_ideal_distribution(self.trading_config) and self.sell_unindexed_traded_coins:
            # only remove non indexed coins if an ideal distribution is set
            removed_coins = [
                coin
                for coin in available_traded_bases
                if coin not in self.indexed_coins
                and coin != self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
            ]
        if self.synchronization_policy == SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_AS_SOON_AS_POSSIBLE:
            # identify coins to sell from previous config
            if not (self.previous_trading_config and self.trading_config):
                return removed_coins
            current_coins = [
                asset[index_distribution.DISTRIBUTION_NAME]
                for asset in (self.get_ideal_distribution(self.trading_config) or [])
            ]
            ref_market = self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
            return list(set(removed_coins + [
                asset[index_distribution.DISTRIBUTION_NAME]
                for asset in self.previous_trading_config[IndexTradingModeProducer.INDEX_CONTENT]
                if asset[index_distribution.DISTRIBUTION_NAME] not in current_coins
                    and (
                        asset[index_distribution.DISTRIBUTION_NAME]
                        != self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
                    )
            ]))
        elif self.synchronization_policy == SynchronizationPolicy.SELL_REMOVED_INDEX_COINS_ON_RATIO_REBALANCE:
            # identify coins to sell from historical configs
            historical_configs = self.get_historical_configs(
                # use 0 a the initial config time as only relevant historical configs should be available
                0, self.exchange_manager.exchange.get_exchange_current_time()
            )
            if not (historical_configs and self.trading_config):
                return removed_coins
            current_coins = [
                asset[index_distribution.DISTRIBUTION_NAME]
                for asset in (self.get_ideal_distribution(self.trading_config) or [])
            ]
            ref_market = self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
            removed_coins_from_historical_configs = set()
            for historical_config in historical_configs:
                for asset in historical_config[IndexTradingModeProducer.INDEX_CONTENT]:
                    asset_name = asset[index_distribution.DISTRIBUTION_NAME]
                    if asset_name not in current_coins and asset_name != ref_market:
                        removed_coins_from_historical_configs.add(asset_name)
            return list(removed_coins_from_historical_configs.union(removed_coins))
        else:
            self.logger.error(f"Unknown synchronization policy: {self.synchronization_policy}")
            return []

    def get_target_ratio(self, currency) -> decimal.Decimal:
        if currency in self.ratio_per_asset:
            try:
                return (
                    decimal.Decimal(str(
                        self.ratio_per_asset[currency][index_distribution.DISTRIBUTION_VALUE]
                    )) / self.total_ratio_per_asset
                )
            except (decimal.DivisionByZero, decimal.InvalidOperation):
                pass
        return trading_constants.ZERO

    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        return True

    @classmethod
    def get_supported_exchange_types(cls) -> list:
        """
        :return: The list of supported exchange types
        """
        return [
            trading_enums.ExchangeTypes.SPOT,
        ]

    def get_current_state(self) -> tuple:
        return trading_enums.EvaluatorStates.NEUTRAL.name, f"Indexing {len(self.indexed_coins)} coins"

    async def single_exchange_process_optimize_initial_portfolio(
        self, sellable_assets: list, target_asset: str, tickers: dict
    ) -> list:
        return await trading_modes.convert_assets_to_target_asset(
            self, sellable_assets, target_asset, tickers
        )
