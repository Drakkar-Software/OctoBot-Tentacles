#  Drakkar-Software OctoBot-Private-Tentacles
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
import time
import decimal
import typing

import octobot_commons.logging as logging
import octobot_trading.errors
import octobot_trading.exchanges as exchanges
import octobot_trading.exchanges.connectors.ccxt.enums as ccxt_enums
import octobot_trading.exchanges.connectors.ccxt.constants as ccxt_constants
import octobot_trading.exchanges.connectors.ccxt.ccxt_client_util as ccxt_client_util
import octobot_commons.constants as commons_constants
import octobot_trading.constants as constants
import octobot_trading.enums as trading_enums


def _kucoin_retrier(f):
    async def wrapper(*args, **kwargs):
        for i in range(0, Kucoin.FAKE_DDOS_ERROR_INSTANT_RETRY_COUNT):
            try:
                return await f(*args, **kwargs)
            except octobot_trading.errors.FailedRequest as e:
                if Kucoin.INSTANT_RETRY_ERROR_CODE in str(e):
                    # should retry instantly, error on kucoin side
                    # see https://github.com/Drakkar-Software/OctoBot/issues/2000
                    logging.get_logger(Kucoin.get_name()).debug(
                        f"{Kucoin.INSTANT_RETRY_ERROR_CODE} error on {f.__name__}(args={args} kwargs={kwargs}) "
                        f"request, retrying now. Attempt {i+1} / {Kucoin.FAKE_DDOS_ERROR_INSTANT_RETRY_COUNT}."
                    )
                else:
                    raise
        raise octobot_trading.errors.FailedRequest(
            f"Failed request after {Kucoin.FAKE_DDOS_ERROR_INSTANT_RETRY_COUNT} retries due "
            f"to {Kucoin.INSTANT_RETRY_ERROR_CODE} error code"
        )
    return wrapper


class Kucoin(exchanges.RestExchange):
    FAKE_DDOS_ERROR_INSTANT_RETRY_COUNT = 5
    INSTANT_RETRY_ERROR_CODE = "429000"
    FUTURES_CCXT_CLASS_NAME = "kucoinfutures"
    MAX_INCREASED_POSITION_QUANTITY_MULTIPLIER = decimal.Decimal("0.95")

    # set True when get_positions() is not returning empty positions and should use get_position() instead
    REQUIRES_SYMBOL_FOR_EMPTY_POSITION = True

    # get_my_recent_trades only covers the last 24h on kucoin
    ALLOW_TRADES_FROM_CLOSED_ORDERS = True  # set True when get_my_recent_trades should use get_closed_orders

    SUPPORTS_SET_MARGIN_TYPE = False  # set False when there is no API to switch between cross and isolated margin types

    # order that should be self-managed by OctoBot
    # can be overridden locally to match exchange support
    UNSUPPORTED_ORDERS = [
        trading_enums.TraderOrderType.STOP_LOSS,  # supported
        trading_enums.TraderOrderType.STOP_LOSS_LIMIT,
        trading_enums.TraderOrderType.TAKE_PROFIT,  # supported
        trading_enums.TraderOrderType.TAKE_PROFIT_LIMIT,
        trading_enums.TraderOrderType.TRAILING_STOP,
        trading_enums.TraderOrderType.TRAILING_STOP_LIMIT
    ]

    @classmethod
    def get_name(cls):
        return 'kucoin'

    def get_rest_name(self):
        if self.exchange_manager.is_future:
            return self.FUTURES_CCXT_CLASS_NAME
        return self.get_name()

    def get_adapter_class(self):
        return KucoinCCXTAdapter

    @classmethod
    def get_supported_exchange_types(cls) -> list:
        """
        :return: The list of supported exchange types
        """
        return [
            trading_enums.ExchangeTypes.SPOT,
            trading_enums.ExchangeTypes.FUTURE,
        ]

    def get_market_status(self, symbol, price_example=None, with_fixer=True):
        # on futures, market status gives limits in contracts, convert it to currency units
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer,
                                            remove_price_limits=True,
                                            adapt_for_contract_size=True)

    @_kucoin_retrier
    async def get_symbol_prices(self, symbol, time_frame, limit: int = 200, **kwargs: dict):
        if "since" in kwargs:
            # prevent ccxt from fillings the end param (not working when trying to get the 1st candle times)
            to_param = "to" if self.exchange_manager.is_future else "endAt"
            kwargs[to_param] = int(time.time() * 1000)
        return await super().get_symbol_prices(symbol=symbol, time_frame=time_frame, limit=limit, **kwargs)

    @_kucoin_retrier
    async def get_recent_trades(self, symbol, limit=50, **kwargs):
        # on ccxt kucoin recent trades are received in reverse order from exchange and therefore should never be
        # filtered by limit before reversing (or most recent trades are lost)
        recent_trades = await super().get_recent_trades(symbol, limit=None, **kwargs)
        return recent_trades[::-1][:limit] if recent_trades else []

    @_kucoin_retrier
    async def get_order_book(self, symbol, limit=20, **kwargs):
        # override default limit to be kucoin complient
        return super().get_order_book(symbol, limit=limit, **kwargs)

    def should_log_on_ddos_exception(self, exception) -> bool:
        """
        Override when necessary
        """
        return Kucoin.INSTANT_RETRY_ERROR_CODE not in str(exception)

    def get_order_additional_params(self, order) -> dict:
        params = {}
        if self.exchange_manager.is_future:
            contract = self.exchange_manager.exchange.get_pair_future_contract(order.symbol)
            params["leverage"] = float(contract.current_leverage)
            params["reduceOnly"] = order.reduce_only
            params["closeOrder"] = order.close_position
        return params

    async def _create_market_stop_loss_order(self, symbol, quantity, price, side, current_price, params=None) -> dict:
        params = params or {}
        params["stopLossPrice"] = price  # make ccxt understand that it's a stop loss
        order = await self.connector.client.create_order(symbol, "market", side, quantity, params=params)
        return order

    async def _update_balance(self, balance, currency, **kwargs):
        balance.update(await super().get_balance(code=currency, **kwargs))

    @_kucoin_retrier
    async def get_balance(self, **kwargs: dict):
        balance = {}
        if self.exchange_manager.is_future:
            # on futures, balance has to be fetched per currency
            # use gather to fetch everything at once (and not allow other requests to get in between)
            await asyncio.gather(*(
                self._update_balance(balance, currency, **kwargs)
                for currency in self.exchange_manager.exchange_config.get_all_traded_currencies()
            ))
            return balance
        return await super().get_balance(**kwargs)

    """
    Margin and leverage
    """

    async def set_symbol_leverage(self, symbol: str, leverage: float, **kwargs):
        """
        Set the symbol leverage
        :param symbol: the symbol
        :param leverage: the leverage
        :return: the update result
        """
        # leverage is set via orders on kucoin
        return None

    @_kucoin_retrier
    async def get_open_orders(self, symbol=None, since=None, limit=None, **kwargs) -> list:
        regular_orders = await super().get_open_orders(symbol=symbol, since=since, limit=limit, **kwargs)
        # add untriggered stop orders (different api endpoint)
        kwargs["stop"] = True
        stop_orders = await super().get_open_orders(symbol=symbol, since=since, limit=limit, **kwargs)
        return regular_orders + stop_orders

    @_kucoin_retrier
    async def get_order(self, order_id: str, symbol: str = None, **kwargs: dict) -> dict:
        return await super().get_order(order_id, symbol=symbol, **kwargs)

    @_kucoin_retrier
    async def create_order(self, order_type: trading_enums.TraderOrderType, symbol: str, quantity: decimal.Decimal,
                           price: decimal.Decimal = None, stop_price: decimal.Decimal = None,
                           side: trading_enums.TradeOrderSide = None, current_price: decimal.Decimal = None,
                           reduce_only: bool = False, params: dict = None) -> typing.Optional[dict]:
        if self.exchange_manager.is_future:
            # on futures exchange expects, quantity in contracts: convert quantity into contracts
            quantity = quantity / self.get_contract_size(symbol)
        return await super().create_order(order_type, symbol, quantity,
                                          price=price, stop_price=stop_price,
                                          side=side, current_price=current_price,
                                          reduce_only=reduce_only, params=params)

    async def get_position(self, symbol: str, **kwargs: dict) -> dict:
        """
        Get the current user symbol position list
        :param symbol: the position symbol
        :return: the user symbol position list
        """

        # todo remove when supported by ccxt
        @_kucoin_retrier
        async def fetch_position(client, symbol, params={}):
            market = client.market(symbol)
            market_id = market['id']
            request = {
                'symbol': market_id,
            }
            response = await client.futuresPrivateGetPosition(request)
            #
            #    {
            #        "code": "200000",
            #        "data": [
            #            {
            #                "id": "615ba79f83a3410001cde321",
            #                "symbol": "ETHUSDTM",
            #                "autoDeposit": False,
            #                "maintMarginReq": 0.005,
            #                "riskLimit": 1000000,
            #                "realLeverage": 18.61,
            #                "crossMode": False,
            #                "delevPercentage": 0.86,
            #                "openingTimestamp": 1638563515618,
            #                "currentTimestamp": 1638576872774,
            #                "currentQty": 2,
            #                "currentCost": 83.64200000,
            #                "currentComm": 0.05018520,
            #                "unrealisedCost": 83.64200000,
            #                "realisedGrossCost": 0.00000000,
            #                "realisedCost": 0.05018520,
            #                "isOpen": True,
            #                "markPrice": 4225.01,
            #                "markValue": 84.50020000,
            #                "posCost": 83.64200000,
            #                "posCross": 0.0000000000,
            #                "posInit": 3.63660870,
            #                "posComm": 0.05236717,
            #                "posLoss": 0.00000000,
            #                "posMargin": 3.68897586,
            #                "posMaint": 0.50637594,
            #                "maintMargin": 4.54717586,
            #                "realisedGrossPnl": 0.00000000,
            #                "realisedPnl": -0.05018520,
            #                "unrealisedPnl": 0.85820000,
            #                "unrealisedPnlPcnt": 0.0103,
            #                "unrealisedRoePcnt": 0.2360,
            #                "avgEntryPrice": 4182.10,
            #                "liquidationPrice": 4023.00,
            #                "bankruptPrice": 4000.25,
            #                "settleCurrency": "USDT",
            #                "isInverse": False
            #            }
            #        ]
            #    }
            #
            data = client.safe_value(response, 'data')
            return client.extend(client.parse_position(data, None), params)

        return self.connector.adapter.adapt_position(
            await fetch_position(self.connector.client, symbol, **kwargs)
        )

    async def set_symbol_partial_take_profit_stop_loss(self, symbol: str, inverse: bool,
                                                       tp_sl_mode: trading_enums.TakeProfitStopLossMode):
        """
        take profit / stop loss mode does not exist on kucoin
        """


class KucoinCCXTAdapter(exchanges.CCXTAdapter):
    # Funding
    KUCOIN_DEFAULT_FUNDING_TIME = 8 * commons_constants.HOURS_TO_SECONDS

    # POSITION
    KUCOIN_AUTO_DEPOSIT = "autoDeposit"

    # ORDER
    KUCOIN_LEVERAGE = "leverage"

    def fix_order(self, raw, symbol=None, **kwargs):
        raw_order_info = raw[ccxt_enums.ExchangePositionCCXTColumns.INFO.value]
        fixed = super().fix_order(raw, **kwargs)
        if self.connector.exchange_manager.is_future \
                and fixed[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] is not None:
            # amount is in contact, multiply by contract value to get the currency amount (displayed to the user)
            contract_size = self.connector.get_contract_size(symbol)
            fixed[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] = \
                fixed[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] * float(contract_size)
        if fixed[trading_enums.ExchangeConstantsOrderColumns.COST.value] is not None:
            fixed[trading_enums.ExchangeConstantsOrderColumns.COST.value] = \
                fixed[trading_enums.ExchangeConstantsOrderColumns.COST.value] * \
                float(raw_order_info.get(self.KUCOIN_LEVERAGE, 1))
        self._adapt_order_type(fixed)
        return fixed

    def _adapt_order_type(self, fixed):
        order_info = fixed[trading_enums.ExchangeConstantsOrderColumns.INFO.value]
        if trigger_direction := order_info.get("stop", None):
            updated_type = trading_enums.TradeOrderType.UNKNOWN.value
            """
            Stop Order Types (https://docs.kucoin.com/futures/#stop-orders)
            down: Triggers when the price reaches or goes below the stopPrice.
            up: Triggers when the price reaches or goes above the stopPrice.
            """
            side = fixed[trading_enums.ExchangeConstantsOrderColumns.SIDE.value]
            if side == trading_enums.TradeOrderSide.BUY.value:
                if trigger_direction == "up":
                    updated_type = trading_enums.TradeOrderType.STOP_LOSS.value
                elif trigger_direction == "down":
                    updated_type = trading_enums.TradeOrderType.TAKE_PROFIT.value
            else:
                if trigger_direction == "up":
                    updated_type = trading_enums.TradeOrderType.TAKE_PROFIT.value
                elif trigger_direction == "down":
                    updated_type = trading_enums.TradeOrderType.STOP_LOSS.value
            # stop loss are not tagged as such by ccxt, force it
            fixed[trading_enums.ExchangeConstantsOrderColumns.TYPE.value] = updated_type
        return fixed

    def parse_funding_rate(self, fixed, from_ticker=False, **kwargs):
        """
        Kucoin next funding time is not provided
        To obtain the last_funding_time :
        => timestamp(previous_funding_timestamp) + timestamp(KUCOIN_DEFAULT_FUNDING_TIME)
        """
        if from_ticker:
            # no funding info in ticker
            return {}
        funding_dict = super().parse_funding_rate(fixed, from_ticker=from_ticker, **kwargs)
        # from super().parse_funding_rate
        previous_funding_timestamp = fixed[trading_enums.ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value]
        fixed.update({
            trading_enums.ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value:
                previous_funding_timestamp + self.KUCOIN_DEFAULT_FUNDING_TIME,
        })
        return funding_dict

    def parse_position(self, fixed, **kwargs):
        raw_position_info = fixed[ccxt_enums.ExchangePositionCCXTColumns.INFO.value]
        parsed = super().parse_position(fixed, **kwargs)
        parsed[trading_enums.ExchangeConstantsPositionColumns.MARGIN_TYPE.value] = \
            trading_enums.MarginType(
                fixed.get(ccxt_enums.ExchangePositionCCXTColumns.MARGIN_MODE.value)
            )
        parsed[trading_enums.ExchangeConstantsPositionColumns.POSITION_MODE.value] = \
            trading_enums.PositionMode.HEDGE if raw_position_info[self.KUCOIN_AUTO_DEPOSIT] \
            else trading_enums.PositionMode.ONE_WAY
        parsed_leverage = self.safe_decimal(
            parsed, trading_enums.ExchangeConstantsPositionColumns.LEVERAGE.value, constants.ZERO
        )
        if parsed_leverage == constants.ZERO:
            # on kucoin, fetched empty position don't have a leverage value. Since it's required within OctoBot,
            # add it manually
            symbol = parsed[trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value]
            if self.connector.exchange_manager.exchange.has_pair_future_contract(symbol):
                parsed[trading_enums.ExchangeConstantsPositionColumns.LEVERAGE.value] = \
                    self.connector.exchange_manager.exchange.get_pair_future_contract(symbol).current_leverage
            else:
                parsed[trading_enums.ExchangeConstantsPositionColumns.LEVERAGE.value] = \
                    constants.DEFAULT_SYMBOL_LEVERAGE
        return parsed
