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

import octobot_commons.constants as commons_constants
import octobot_commons.enums as commons_enums
import octobot_commons.symbols.symbol_util as symbol_util
import octobot_trading.constants as trading_constants
import octobot_trading.enums as trading_enums
import octobot_trading.errors as trading_errors
import octobot_trading.modes as trading_modes
import octobot_trading.personal_data as trading_personal_data


class IndexTradingModeConsumer(trading_modes.AbstractTradingModeConsumer):
    FILL_ORDER_TIMEOUT = 60

    async def create_new_orders(self, symbol, _, state, **kwargs):
        if state == trading_enums.EvaluatorStates.NEUTRAL.value:
            return await self._rebalance_portfolio()
        self.logger.error(f"Unknown index state: {state}")
        return []

    async def _rebalance_portfolio(self):
        self.logger.info(
            f"Triggering rebalance on [{self.exchange_manager.exchange_name}]."
        )
        # 1. sell indexed coins for reference market
        orders = await self._sell_indexed_coins_for_reference_market()
        # 2. split reference market into indexed coins
        orders += await self._split_reference_market_into_indexed_coins()
        return orders

    async def _sell_indexed_coins_for_reference_market(self) -> list:
        orders = await trading_modes.convert_assets_to_target_asset(
            self.trading_mode, self.trading_mode.indexed_coins,
            self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market, {}
        )
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

    async def _split_reference_market_into_indexed_coins(self):
        orders = []
        reference_market_available_holdings = \
            self.exchange_manager.exchange_personal_data.portfolio_manager.portfolio.get_currency_portfolio(
                self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
            ).available
        for coin in self.trading_mode.indexed_coins:
            orders.extend(await self._buy_coin(coin, reference_market_available_holdings))
        if not orders:
            raise trading_errors.MissingMinimalExchangeTradeVolume()
        return orders

    async def _buy_coin(self, coin, reference_market_available_holdings) -> list:
        symbol = symbol_util.merge_currencies(
            coin,
            self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
        )
        current_symbol_holding, current_market_holding, market_quantity, price, symbol_market = \
            await trading_personal_data.get_pre_order_data(
                self.exchange_manager, symbol=symbol, timeout=trading_constants.ORDER_DATA_FETCHING_TIMEOUT
            )
        # ideally use the expected reference_market_available_holdings ratio, fallback to available
        # holdings if necessary
        reference_market_to_allocate = min(
            self.trading_mode.get_target_ratio(coin) * reference_market_available_holdings,
            current_market_holding
        )
        ideal_quantity = reference_market_to_allocate / price
        quantity = trading_personal_data.decimal_adapt_order_quantity_because_fees(
            self.exchange_manager, symbol, trading_enums.TraderOrderType.BUY_MARKET, ideal_quantity,
            price, trading_enums.ExchangeConstantsMarketPropertyColumns.TAKER,
            trading_enums.TradeOrderSide.BUY, current_market_holding
        )
        created_orders = []
        orders_should_have_been_created = False
        for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
            quantity,
            price,
            symbol_market
        ):
            orders_should_have_been_created = True
            current_order = trading_personal_data.create_order_instance(
                trader=self.exchange_manager.trader,
                order_type=trading_enums.TraderOrderType.BUY_MARKET,
                symbol=symbol,
                current_price=order_price,
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
    REBALANCE_CAP_PERCENT = "rebalance_cap_percent"
    INDEX_CONTENT = "index_content"
    INDEXED_COIN_NAME = "name"
    INDEXED_COIN_RATIO = "ratio"
    MIN_INDEXED_COINS = 2

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
        current_time = self.exchange_manager.exchange.get_exchange_current_time()
        if (
            current_time - self._last_trigger_time
        ) >= self.trading_mode.refresh_interval_days * commons_constants.DAYS_TO_SECONDS:
            if len(self.trading_mode.indexed_coins) < self.MIN_INDEXED_COINS:
                self.logger.error(
                    f"At least {self.MIN_INDEXED_COINS} coins are required to maintain an index. Please "
                    f"select more trading pairs using "
                    f"{self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market} as "
                    f"quote currency."
                )
            else:
                await self.ensure_index()
            self.logger.debug(f"Next index check in {self.trading_mode.refresh_interval_days} days")
            self._last_trigger_time = current_time

    async def ensure_index(self):
        await self._wait_for_symbol_prices_and_profitability_init(self.CONFIG_INIT_TIMEOUT)
        self.logger.info(
            f"Ensuring Index on [{self.exchange_manager.exchange_name}] "
            f"{len(self.trading_mode.indexed_coins)} coins: {self.trading_mode.indexed_coins} with reference market: "
            f"{self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market}"
        )
        if self._should_rebalance():
            await self._trigger_rebalance()
        else:
            self.logger.info(
                f"[{self.exchange_manager.exchange_name}] is following the index: no rebalance is required."
            )

    async def _trigger_rebalance(self):
        self.logger.info(
            f"Triggering rebalance on [{self.exchange_manager.exchange_name}]."
        )
        await self.submit_trading_evaluation(
            cryptocurrency=None,
            symbol=None,    # todo check if ok to set None for signals
            time_frame=None,
            final_note=None,
            state=trading_enums.EvaluatorStates.NEUTRAL
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

    def _should_rebalance(self) -> bool:
        consumer = self.trading_mode.consumers[0]
        for coin in self.trading_mode.indexed_coins:
            coin_ratio = consumer.get_holdings_ratio(coin)
            target_ratio = self.trading_mode.get_target_ratio(coin)
            if (coin_ratio == trading_constants.ZERO and target_ratio > trading_constants.ZERO) or (
                not (
                    target_ratio - self.trading_mode.rebalance_cap_ratio
                    < coin_ratio
                    < target_ratio + self.trading_mode.rebalance_cap_ratio
                )
            ):
                self.logger.info(
                    f"{coin} is beyond the target ratio of {target_ratio * trading_constants.ONE_HUNDRED}%, "
                    f"ratio = {coin_ratio * trading_constants.ONE_HUNDRED}%. A rebalance is required"
                )
                return True
        return False

    def get_channels_registration(self):
        return [self.TOPIC_TO_CHANNEL_NAME[commons_enums.ActivationTopics.FULL_CANDLES.value]]


class IndexTradingMode(trading_modes.AbstractTradingMode):
    MODE_PRODUCER_CLASSES = [IndexTradingModeProducer]
    MODE_CONSUMER_CLASSES = [IndexTradingModeConsumer]
    SUPPORTS_INITIAL_PORTFOLIO_OPTIMIZATION = True
    SUPPORTS_HEALTH_CHECK = False

    def __init__(self, config, exchange_manager):
        super().__init__(config, exchange_manager)
        self.refresh_interval_days = 7
        self.rebalance_cap_ratio = decimal.Decimal("0.05")  #5%
        self.ratio_per_asset = {}
        self.total_ratio_per_asset = trading_constants.ZERO
        self.indexed_coins = []

    def init_user_inputs(self, inputs: dict) -> None:
        """
        Called right before starting the tentacle, should define all the tentacle's user inputs unless
        those are defined somewhere else.
        """
        self.refresh_interval_days = int(self.UI.user_input(
            IndexTradingModeProducer.REFRESH_INTERVAL, commons_enums.UserInputTypes.INT,
            self.refresh_interval_days, inputs,
            min_val=0,
            title="Trigger period: Days to wait between each rebalance.",
        ))
        self.rebalance_cap_ratio = decimal.Decimal(str(self.UI.user_input(
            IndexTradingModeProducer.REBALANCE_CAP_PERCENT, commons_enums.UserInputTypes.FLOAT,
            float(self.rebalance_cap_ratio * trading_constants.ONE_HUNDRED), inputs,
            min_val=0, max_val=100,
            title="Rebalance cap: maximum allowed percent holding of a coin beyond initial ratios before "
                  "triggering a rebalance.",
        ))) / trading_constants.ONE_HUNDRED
        self.ratio_per_asset = {
            asset[IndexTradingModeProducer.INDEXED_COIN_NAME]: asset
            for asset in self.trading_config[IndexTradingModeProducer.INDEX_CONTENT]
        }
        self.total_ratio_per_asset = decimal.Decimal(sum(
            asset[IndexTradingModeProducer.INDEXED_COIN_RATIO]
            for asset in self.ratio_per_asset.values()
        ))
        self.indexed_coins = self._get_filtered_traded_coins()

    def _get_filtered_traded_coins(self):
        if self.exchange_manager:
            return list(set(
                symbol.base
                for symbol in self.exchange_manager.exchange_config.traded_symbols
                if not self.ratio_per_asset or symbol.base in self.ratio_per_asset
                and symbol.quote == self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
            ))
        return []

    def get_target_ratio(self, currency) -> decimal.Decimal:
        if self.total_ratio_per_asset:
            if currency in self.ratio_per_asset:
                try:
                    return (
                        decimal.Decimal(str(
                            self.ratio_per_asset[currency][IndexTradingModeProducer.INDEXED_COIN_RATIO]
                        )) / self.total_ratio_per_asset
                    )
                except (decimal.DivisionByZero, decimal.InvalidOperation):
                    pass
            return trading_constants.ZERO
        return trading_constants.ONE / decimal.Decimal(len(self.indexed_coins))

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
        self, sellable_assets, target_asset: str, tickers: dict
    ) -> list:
        self.logger.info(f"Optimizing portfolio: selling {sellable_assets} to buy {target_asset}")
        return await trading_modes.convert_assets_to_target_asset(
            self, sellable_assets, target_asset, tickers
        )
