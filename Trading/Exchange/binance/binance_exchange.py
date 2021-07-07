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
import octobot_commons.constants as common_constants
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges


class Binance(exchanges.SpotCCXTExchange, exchanges.FutureCCXTExchange):
    DESCRIPTION = ""

    BUY_STR = "BUY"
    SELL_STR = "SELL"

    ACCOUNTS = {
        trading_enums.AccountTypes.CASH: 'cash',
        trading_enums.AccountTypes.FUTURE: 'future'
    }

    MARK_PRICE_IN_POSITION = True

    BINANCE_SYMBOL = "symbol"

    BINANCE_FUTURE_QUANTITY = "positionAmt"
    BINANCE_FUTURE_UNREALIZED_PNL = "unRealizedProfit"
    BINANCE_FUTURE_LIQUIDATION_PRICE = "liquidationPrice"
    BINANCE_FUTURE_VALUE = "liquidationPrice"

    BINANCE_MARGIN_TYPE = "marginType"
    BINANCE_MARGIN_TYPE_ISOLATED = "ISOLATED"
    BINANCE_MARGIN_TYPE_CROSSED = "CROSSED"

    BINANCE_FUNDING_RATE = "fundingRate"
    BINANCE_LAST_FUNDING_TIME = "fundingTime"
    BINANCE_FUNDING_DURATION = 8 * common_constants.HOURS_TO_SECONDS

    BINANCE_TIME = "time"
    BINANCE_MARK_PRICE = "markPrice"
    BINANCE_ENTRY_PRICE = "entryPrice"

    @classmethod
    def get_name(cls):
        return 'binance'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def get_balance(self, **kwargs):
        return await exchanges.SpotCCXTExchange.get_balance(self, **self._get_params(kwargs))

    async def get_my_recent_trades(self, symbol=None, since=None, limit=None, **kwargs):
        return self._uniformize_trades(await super().get_my_recent_trades(symbol=symbol,
                                                                          since=since,
                                                                          limit=limit,
                                                                          **kwargs))

    def _uniformize_trades(self, trades):
        for trade in trades:
            trade[trading_enums.ExchangeConstantsOrderColumns.STATUS.value] = trading_enums.OrderStatus.CLOSED.value
            trade[trading_enums.ExchangeConstantsOrderColumns.ID.value] = trade[
                trading_enums.ExchangeConstantsOrderColumns.ORDER.value]
            trade[trading_enums.ExchangeConstantsOrderColumns.TYPE.value] = trading_enums.TradeOrderType.MARKET.value \
                if trade["takerOrMaker"] == trading_enums.ExchangeConstantsMarketPropertyColumns.TAKER.value \
                else trading_enums.TradeOrderType.LIMIT.value
        return trades

    def _get_params(self, params):
        if params is None:
            params = {}
        params.update({'recvWindow': 60000})
        return params

    async def get_order(self, order_id, symbol=None, **kwargs):
        return await self._ensure_order_completeness(
            await super().get_order(order_id=order_id, symbol=symbol, **kwargs), symbol, **kwargs)

    async def create_order(self, order_type, symbol, quantity, price=None, stop_price=None, **kwargs):
        return await self._ensure_order_completeness(
            await super().create_order(order_type, symbol, quantity, price=price, stop_price=stop_price, **kwargs),
            symbol, **kwargs)

    async def get_closed_orders(self, symbol=None, since=None, limit=None, **kwargs):
        orders = await super().get_closed_orders(symbol=symbol, since=since, limit=limit, **kwargs)
        # closed orders are missing fees on binance: add them from trades
        trades = {
            trade[trading_enums.ExchangeConstantsOrderColumns.ORDER.value]: trade
            for trade in await super().get_my_recent_trades(symbol=symbol, since=since, limit=limit, **kwargs)
        }
        for order in orders:
            self._fill_order_missing_data(order, trades)
        return orders

    async def _ensure_order_completeness(self, order, symbol, **kwargs):
        if order and order[
            trading_enums.ExchangeConstantsOrderColumns.STATUS.value] == trading_enums.OrderStatus.CLOSED.value and \
                not order[trading_enums.ExchangeConstantsOrderColumns.FEE.value]:
            trades = {
                trade[trading_enums.ExchangeConstantsOrderColumns.ORDER.value]: trade
                for trade in await super().get_my_recent_trades(symbol=symbol, **kwargs)
            }
            self._fill_order_missing_data(order, trades)
        return order

    def _fill_order_missing_data(self, order, trades):
        order_id = order[trading_enums.ExchangeConstantsOrderColumns.ID.value]
        if not order[trading_enums.ExchangeConstantsOrderColumns.FEE.value] and order_id in trades:
            order[trading_enums.ExchangeConstantsOrderColumns.FEE.value] = \
                trades[order_id][trading_enums.ExchangeConstantsOrderColumns.FEE.value]

    async def get_open_positions(self) -> dict:
        return [
            self.parse_position(position)
            for position in await self.connector.client.fapiPrivate_get_positionrisk()
        ]

    async def get_funding_rate(self, symbol: str):
        return (await self.get_funding_rate_history(symbol=symbol, limit=1))[-1]

    async def get_funding_rate_history(self, symbol: str, limit: int = 100) -> list:
        return [
            self.parse_funding(funding_rate_dict)
            for funding_rate_dict in (await self.connector.client.fapiPublic_get_fundingrate(
                {self.BINANCE_SYMBOL: self.get_exchange_pair(symbol),
                 "limit": limit}))
        ]

    async def set_symbol_leverage(self, symbol: str, leverage: int):
        await self.connector.client.fapiPrivate_post_leverage(
            {self.BINANCE_SYMBOL: self.get_exchange_pair(symbol),
             "leverage": leverage})

    async def set_symbol_margin_type(self, symbol: str, isolated: bool):
        await self.connector.client.fapiPrivate_post_marginType(
            {
                self.BINANCE_SYMBOL: self.get_exchange_pair(symbol),
                self.BINANCE_MARGIN_TYPE: self.BINANCE_MARGIN_TYPE_ISOLATED
                if isolated else self.BINANCE_MARGIN_TYPE_CROSSED
            })

    def parse_position(self, position_dict):
        try:
            position_dict.update({
                trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value:
                    self.get_pair_from_exchange(
                        position_dict[trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value]),
                trading_enums.ExchangeConstantsPositionColumns.ID.value:
                    self.connector.client.safe_string(position_dict,
                                                      trading_enums.ExchangeConstantsPositionColumns.ID.value,
                                                      position_dict[
                                                          trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value]),
                trading_enums.ExchangeConstantsPositionColumns.QUANTITY.value:
                    self.connector.client.safe_float(position_dict, self.BINANCE_FUTURE_QUANTITY, 0),
                trading_enums.ExchangeConstantsPositionColumns.MARGIN_TYPE.value:
                    position_dict.get(self.BINANCE_MARGIN_TYPE, None),
                trading_enums.ExchangeConstantsPositionColumns.VALUE.value:
                    self.calculate_position_value(
                        self.connector.client.safe_float(
                            position_dict, trading_enums.ExchangeConstantsPositionColumns.QUANTITY.value, 0),
                        self.connector.client.safe_float(
                            position_dict, trading_enums.ExchangeConstantsPositionColumns.MARK_PRICE.value, 1)),
                trading_enums.ExchangeConstantsPositionColumns.MARGIN.value:
                # TODO
                    self.connector.client.safe_float(position_dict,
                                                     trading_enums.ExchangeConstantsPositionColumns.MARGIN.value,
                                                     0),
                trading_enums.ExchangeConstantsPositionColumns.UNREALISED_PNL.value:
                    self.connector.client.safe_float(position_dict, self.BINANCE_FUTURE_UNREALIZED_PNL, 0),
                trading_enums.ExchangeConstantsPositionColumns.REALISED_PNL.value:
                # TODO
                    self.connector.client.safe_float(position_dict,
                                                     trading_enums.ExchangeConstantsPositionColumns.REALISED_PNL.value,
                                                     0),
                trading_enums.ExchangeConstantsPositionColumns.LIQUIDATION_PRICE.value:
                    self.connector.client.safe_float(position_dict, self.BINANCE_FUTURE_LIQUIDATION_PRICE, 0),
                trading_enums.ExchangeConstantsPositionColumns.MARK_PRICE.value:
                    self.connector.client.safe_float(position_dict, self.BINANCE_MARK_PRICE, 0),
                trading_enums.ExchangeConstantsPositionColumns.ENTRY_PRICE.value:
                    self.connector.client.safe_float(position_dict, self.BINANCE_ENTRY_PRICE, 0),
                trading_enums.ExchangeConstantsPositionColumns.TIMESTAMP.value:
                # TODO
                    self.connector.get_uniform_timestamp(
                        self.connector.client.safe_float(position_dict,
                                                         trading_enums.ExchangeConstantsPositionColumns.TIMESTAMP.value,
                                                         self.connector.get_exchange_current_time())),
                trading_enums.ExchangeConstantsPositionColumns.STATUS.value:
                    self.parse_position_status(self.connector.client.safe_string(position_dict,
                                                                                 trading_enums.ExchangeConstantsPositionColumns.STATUS.value,
                                                                                 default_value=trading_enums.PositionStatus.OPEN.value)),
                trading_enums.ExchangeConstantsPositionColumns.SIDE.value:
                    self.parse_position_side(self.connector.client.safe_string(position_dict,
                                                                               trading_enums.ExchangeConstantsPositionColumns.SIDE.value,
                                                                               default_value=trading_enums.PositionSide.UNKNOWN.value)),
            })
        except KeyError as e:
            self.logger.error(f"Fail to parse position dict ({e})")
        return position_dict

    def parse_funding(self, funding_dict, from_ticker=False):
        try:
            last_funding_time = self.connector.get_uniform_timestamp(
                self.connector.client.safe_float(funding_dict, self.BINANCE_LAST_FUNDING_TIME))
            funding_dict = {
                trading_enums.ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value: last_funding_time,
                trading_enums.ExchangeConstantsFundingColumns.FUNDING_RATE.value:
                    self.connector.client.safe_float(funding_dict, self.BINANCE_FUNDING_RATE),
                trading_enums.ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value:
                    last_funding_time + self.BINANCE_FUNDING_DURATION
            }
        except KeyError as e:
            self.logger.error(f"Fail to parse funding dict ({e})")
        return funding_dict

    def parse_mark_price(self, mark_price_dict, from_ticker=False):
        try:
            mark_price_dict = {
                trading_enums.ExchangeConstantsMarkPriceColumns.MARK_PRICE.value:
                    self.connector.client.safe_float(mark_price_dict, self.BINANCE_MARK_PRICE, 0)
            }
        except KeyError as e:
            self.logger.error(f"Fail to parse mark_price dict ({e})")
        return mark_price_dict
