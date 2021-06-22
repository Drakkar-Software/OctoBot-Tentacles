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
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges
import octobot_commons.constants as commons_constants
import octobot_trading.constants as trading_constants


class Bybit(exchanges.FutureCCXTExchange):
    DESCRIPTION = ""

    BUY_STR = "Buy"
    SELL_STR = "Sell"

    MARK_PRICE_IN_TICKER = True
    FUNDING_IN_TICKER = True

    # Spot keys
    BYBIT_KLINE_TIMESTAMP = "open_time"

    BYBIT_SYMBOL = "symbol"

    # Position
    BYBIT_SIZE = "size"
    BYBIT_VALUE = "position_value"
    BYBIT_MARGIN = "position_margin"
    BYBIT_STATUS = "position_status"
    BYBIT_LIQUIDATION_PRICE = "liq_price"
    BYBIT_TIMESTAMP = "created_at"
    BYBIT_IS_ISOLATED = "is_isolated"

    # Funding
    BYBIT_FUNDING_TIMESTAMP = "funding_rate_timestamp"
    BYBIT_DEFAULT_FUNDING_TIME = 8 * commons_constants.HOURS_TO_SECONDS

    @classmethod
    def get_name(cls):
        return 'bybit'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def initialize_impl(self):
        await super().initialize_impl()

        # temporary patch defaultMarketType to linear
        self.connector.client.options['defaultType'] = 'linear'

    async def get_open_positions(self) -> list:
        return self.parse_positions(await self.connector.client.fetch_positions())

    async def set_symbol_leverage(self, symbol: str, leverage: int):
        # TODO returned error during implementation tests
        await self.connector.client.user_post_leverage_save(
            {
                self.BYBIT_SYMBOL: self.get_exchange_pair(symbol),
                "leverage": leverage
            })

    async def get_symbol_leverage(self, symbol: str):
        # TODO returned error during implementation tests
        user_leverage = await self.connector.client.user_get_leverage()
        return user_leverage["result"][symbol] if symbol in user_leverage["result"] else None

    async def set_symbol_margin_type(self, symbol: str, isolated: bool):
        # TODO add check if leverage is > 0 when isolated = True
        if not isolated:
            await self.set_symbol_leverage(symbol, 0)

    # async def get_kline_price(self, symbol, time_frame):
    #     try:
    #         await self.connector.client.public_get_kline_list(
    #             {
    #                 "symbol": self.get_exchange_pair(symbol),
    #                 "interval": "",
    #                 "from": "",
    #                 "limit": 1
    #              })
    #     except BaseError as e:
    #         self.logger.error(f"Failed to get_kline_price {e}")
    #         return None

    def parse_positions(self, positions) -> list:
        """
        CCXT is returning the position dict as {'data': {position data dict}}
        """
        return [self.parse_position(position.get('data')) for position in positions]

    def parse_position(self, position_dict) -> dict:
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
                    self.connector.client.safe_float(position_dict, self.BYBIT_SIZE, 0),
                trading_enums.ExchangeConstantsPositionColumns.MARGIN_TYPE.value:
                    self._parse_position_margin_type(position_dict.get(self.BYBIT_IS_ISOLATED, True)),
                trading_enums.ExchangeConstantsPositionColumns.VALUE.value:
                    self.connector.client.safe_float(position_dict, self.BYBIT_VALUE, 0),
                trading_enums.ExchangeConstantsPositionColumns.MARGIN.value:
                    self.connector.client.safe_float(position_dict, self.BYBIT_MARGIN, 0),
                trading_enums.ExchangeConstantsPositionColumns.UNREALISED_PNL.value:
                # TODO currently resets the unrealised PNL on position update with WS
                    self.connector.client.safe_float(position_dict,
                                                     trading_enums.ExchangeConstantsPositionColumns.UNREALISED_PNL.value,
                                                     0),
                trading_enums.ExchangeConstantsPositionColumns.LIQUIDATION_PRICE.value:
                    self.connector.client.safe_float(position_dict, self.BYBIT_LIQUIDATION_PRICE, 0),
                trading_enums.ExchangeConstantsPositionColumns.TIMESTAMP.value:
                    self.parse_timestamp(position_dict, self.BYBIT_TIMESTAMP),
                trading_enums.ExchangeConstantsPositionColumns.STATUS.value:
                    self.parse_position_status(self.connector.client.safe_string(
                        position_dict,
                        trading_enums.ExchangeConstantsPositionColumns.STATUS.value,
                        default_value=trading_enums.PositionStatus.OPEN.value)),
                trading_enums.ExchangeConstantsPositionColumns.SIDE.value:
                    self.parse_position_side(self.connector.client.safe_string(
                        position_dict,
                        trading_enums.ExchangeConstantsPositionColumns.SIDE.value,
                        default_value=trading_enums.PositionSide.UNKNOWN.value)),
                trading_enums.ExchangeConstantsPositionColumns.MARK_PRICE.value:
                    self.connector.client.safe_float(position_dict,
                                                     trading_enums.ExchangeConstantsPositionColumns.MARK_PRICE.value, 0)
            })
        except KeyError as e:
            self.logger.error(f"Fail to parse position dict ({e})")
        return position_dict

    def parse_funding(self, funding_dict, from_ticker=False):
        if from_ticker and trading_constants.CCXT_INFO in funding_dict:
            funding_dict, old_funding_dict = funding_dict[trading_constants.CCXT_INFO], funding_dict

        try:
            """
            Bybit last funding time is not provided
            To obtain the last_funding_time : 
            => timestamp(next_funding_time) - timestamp(BYBIT_DEFAULT_FUNDING_TIME)
            """
            funding_next_timestamp = self.parse_timestamp(
                funding_dict, trading_enums.ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value)
            funding_dict.update({
                trading_enums.ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value:
                    funding_next_timestamp - self.BYBIT_DEFAULT_FUNDING_TIME,
                trading_enums.ExchangeConstantsFundingColumns.FUNDING_RATE.value: self.connector.client.safe_float(
                    funding_dict, trading_enums.ExchangeConstantsFundingColumns.FUNDING_RATE.value),
                trading_enums.ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value: funding_next_timestamp
            })
        except KeyError as e:
            self.logger.error(f"Fail to parse funding dict ({e})")
        return funding_dict

    def parse_mark_price(self, mark_price_dict, from_ticker=False) -> dict:
        if from_ticker and trading_constants.CCXT_INFO in mark_price_dict:
            mark_price_dict = mark_price_dict[trading_constants.CCXT_INFO]

        try:
            mark_price_dict = {
                trading_enums.ExchangeConstantsMarkPriceColumns.MARK_PRICE.value:
                    self.connector.client.safe_float(mark_price_dict,
                                                     trading_enums.ExchangeConstantsMarkPriceColumns.MARK_PRICE.value,
                                                     0)
            }
        except KeyError as e:
            self.logger.error(f"Fail to parse mark price dict ({e})")

        return mark_price_dict

    def parse_position_status(self, status):
        statuses = {
            'Normal': 'open',
            'Liq': 'liquidating',
            'Adl': 'auto_deleveraging',
        }
        return trading_enums.PositionStatus(self.connector.client.safe_string(statuses, status, status))

    def _parse_position_margin_type(self, position_is_isolated):
        return trading_enums.TraderPositionType.ISOLATED.value \
            if position_is_isolated else trading_enums.TraderPositionType.CROSS.value
