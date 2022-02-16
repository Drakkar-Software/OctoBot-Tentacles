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
import decimal

import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as exchanges
import octobot_commons.constants as commons_constants
import octobot_trading.constants as constants
import octobot_trading.errors


class Bybit(exchanges.SpotCCXTExchange, exchanges.FutureCCXTExchange):
    DESCRIPTION = ""

    BUY_STR = "Buy"
    SELL_STR = "Sell"

    LONG_STR = BUY_STR
    SHORT_STR = SELL_STR

    MARK_PRICE_IN_TICKER = True
    FUNDING_IN_TICKER = True

    # Position
    BYBIT_SIZE = "size"
    BYBIT_VALUE = "position_value"
    BYBIT_LEVERAGE = "leverage"
    BYBIT_INITIAL_MARGIN = "position_margin"
    BYBIT_STATUS = "position_status"
    BYBIT_LIQUIDATION_PRICE = "liq_price"
    BYBIT_BANKRUPTCY_PRICE = "bust_price"
    BYBIT_CLOSING_FEE = "occ_closing_fee"
    BYBIT_MODE = "mode"
    BYBIT_TIMESTAMP = "created_at"
    BYBIT_IS_ISOLATED = "is_isolated"
    BYBIT_UNREALISED_PNL = "unrealised_pnl"
    BYBIT_REALIZED_PNL = "cum_realised_pnl"
    BYBIT_ONE_WAY = "MergedSingle"
    BYBIT_HEDGE = "BothSide"
    BYBIT_ENTRY_PRICE = "entry_price"

    # Funding
    BYBIT_FUNDING_TIMESTAMP = "funding_rate_timestamp"
    BYBIT_DEFAULT_FUNDING_TIME = 8 * commons_constants.HOURS_TO_SECONDS

    @classmethod
    def get_name(cls) -> str:
        return 'bybit'

    @classmethod
    def is_supporting_exchange(cls, exchange_candidate_name) -> bool:
        return cls.get_name() == exchange_candidate_name

    async def get_symbol_prices(self, symbol, time_frame, limit: int = 200, **kwargs: dict):
        # Bybit return an error if there is no limit or since parameter
        try:
            return await self.connector.client.fetch_ohlcv(symbol, time_frame.value, limit=limit, params=kwargs)
        except Exception as e:
            raise octobot_trading.errors.FailedRequest(f"Failed to get_symbol_prices {e}")

    def get_default_type(self):
        return 'linear'

    async def get_positions(self) -> list:
        return self.parse_positions(await self.connector.client.fetch_positions())

    def parse_positions(self, positions) -> list:
        """
        CCXT is returning the position dict as {'data': {position data dict}}
        """
        return [self.parse_position(position.get('data')) for position in positions] if positions else []

    def parse_position(self, position_dict) -> dict:
        try:
            size = decimal.Decimal(position_dict.get(self.BYBIT_SIZE, 0))
            # if size == constants.ZERO:
            #     return {}  # Don't parse empty position

            symbol = self.get_pair_from_exchange(
                position_dict[trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value])
            side = self.parse_position_side(position_dict.get(trading_enums.ExchangePositionCCXTColumns.SIDE.value))
            return {
                trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value: symbol,
                trading_enums.ExchangeConstantsPositionColumns.TIMESTAMP.value:
                    self.parse_timestamp(position_dict, self.BYBIT_TIMESTAMP),
                trading_enums.ExchangeConstantsPositionColumns.SIDE.value: side,
                trading_enums.ExchangeConstantsPositionColumns.MARGIN_TYPE.value:
                    self._parse_position_margin_type(position_dict.get(self.BYBIT_IS_ISOLATED, True)),
                trading_enums.ExchangeConstantsPositionColumns.SIZE.value:
                    size if side is trading_enums.PositionSide.LONG else -size,
                trading_enums.ExchangeConstantsPositionColumns.INITIAL_MARGIN.value:
                    decimal.Decimal(position_dict.get(self.BYBIT_INITIAL_MARGIN, 0)),
                trading_enums.ExchangeConstantsPositionColumns.NOTIONAL.value:
                    decimal.Decimal(position_dict.get(self.BYBIT_VALUE, 0)),
                trading_enums.ExchangeConstantsPositionColumns.LEVERAGE.value:
                    decimal.Decimal(position_dict.get(self.BYBIT_LEVERAGE, 0)),
                trading_enums.ExchangeConstantsPositionColumns.UNREALIZED_PNL.value:
                    decimal.Decimal(position_dict.get(self.BYBIT_UNREALISED_PNL, 0)),
                trading_enums.ExchangeConstantsPositionColumns.REALISED_PNL.value:
                    decimal.Decimal(position_dict.get(self.BYBIT_REALIZED_PNL, 0)),
                trading_enums.ExchangeConstantsPositionColumns.LIQUIDATION_PRICE.value:
                    decimal.Decimal(position_dict.get(self.BYBIT_LIQUIDATION_PRICE, 0)),
                trading_enums.ExchangeConstantsPositionColumns.CLOSING_FEE.value:
                    decimal.Decimal(position_dict.get(self.BYBIT_CLOSING_FEE, 0)),
                trading_enums.ExchangeConstantsPositionColumns.BANKRUPTCY_PRICE.value:
                    decimal.Decimal(position_dict.get(self.BYBIT_BANKRUPTCY_PRICE, 0)),
                trading_enums.ExchangeConstantsPositionColumns.ENTRY_PRICE.value:
                    decimal.Decimal(position_dict.get(self.BYBIT_ENTRY_PRICE, 0)),
                trading_enums.ExchangeConstantsPositionColumns.CONTRACT_TYPE.value:
                    self._parse_position_contract_type(symbol),
                trading_enums.ExchangeConstantsPositionColumns.POSITION_MODE.value:
                    self._parse_position_mode(position_dict.get(self.BYBIT_MODE)),
            }
        except KeyError as e:
            self.logger.error(f"Fail to parse position dict ({e})")
        return position_dict

    def parse_funding(self, funding_dict, from_ticker=False):
        if from_ticker and constants.CCXT_INFO in funding_dict:
            funding_dict, old_funding_dict = funding_dict[constants.CCXT_INFO], funding_dict

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
                trading_enums.ExchangeConstantsFundingColumns.FUNDING_RATE.value: decimal.Decimal(
                    funding_dict.get(trading_enums.ExchangeConstantsFundingColumns.FUNDING_RATE.value, 0)),
                trading_enums.ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value: funding_next_timestamp
            })
        except KeyError as e:
            self.logger.error(f"Fail to parse funding dict ({e})")
        return funding_dict

    def parse_mark_price(self, mark_price_dict, from_ticker=False) -> dict:
        if from_ticker and constants.CCXT_INFO in mark_price_dict:
            mark_price_dict = mark_price_dict[constants.CCXT_INFO]

        try:
            mark_price_dict = {
                trading_enums.ExchangeConstantsMarkPriceColumns.MARK_PRICE.value:
                    decimal.Decimal(mark_price_dict.get(
                        trading_enums.ExchangeConstantsMarkPriceColumns.MARK_PRICE.value, 0))
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
        return trading_enums.TraderPositionType.ISOLATED \
            if position_is_isolated else trading_enums.TraderPositionType.CROSS

    def _parse_position_contract_type(self, position_pair):
        if self.is_linear_symbol(position_pair):
            return trading_enums.FutureContractType.LINEAR_PERPETUAL
        if self.is_inverse_symbol(position_pair):
            return trading_enums.FutureContractType.INVERSE_PERPETUAL
        return None

    def _parse_position_mode(self, raw_mode):
        if raw_mode == self.BYBIT_ONE_WAY:
            return trading_enums.PositionMode.ONE_WAY
        if raw_mode == self.BYBIT_HEDGE:
            return trading_enums.PositionMode.HEDGE
        return None

    def is_linear_symbol(self, symbol):
        return self._get_pair_market_type(symbol) == 'linear'

    def is_inverse_symbol(self, symbol):
        return self._get_pair_market_type(symbol) == 'inverse'

    def is_futures_symbol(self, symbol):
        return self._get_pair_market_type(symbol) == 'futures'
