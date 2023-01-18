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
import octobot_trading.enums as enums
import octobot_trading.exchanges as exchanges
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges.connectors.ccxt.enums as ccxt_enums
import octobot_trading.constants as constants


class BinanceUsdM(exchanges.RestExchange):
    DESCRIPTION = ""

    MARK_PRICE_IN_TICKER = True
    FUNDING_IN_TICKER = True

    @classmethod
    def get_supported_exchange_types(cls) -> list:
        return [enums.ExchangeTypes.FUTURE]

    def get_adapter_class(self):
        return BinanceUsdMAdapter

    @classmethod
    def get_name(cls):
        return "binanceusdm"

    async def set_symbol_partial_take_profit_stop_loss(
        self, symbol: str, inverse: bool, tp_sl_mode: enums.TakeProfitStopLossMode
    ):
        # no partial tp / sl - use limit and stop market instead
        pass

    async def _create_market_stop_loss_order(
        self, symbol, quantity, price, side, current_price, params=None
    ) -> dict:
        params = params or {}
        params["reduceOnly"] = True
        return await super()._create_market_stop_loss_order(
            symbol=symbol,
            quantity=quantity,
            price=price,
            side=side,
            current_price=current_price,
            params=params,
        )

    async def _create_limit_stop_loss_order(
        self, symbol, quantity, price, stop_price, side, params=None
    ) -> dict:
        params = params or {}
        params["reduceOnly"] = True
        return await super()._create_limit_stop_loss_order(
            symbol=symbol,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            side=side,
            params=params,
        )

    async def _create_market_take_profit_order(
        self, symbol, quantity, price=None, side=None, params=None
    ) -> dict:
        raise NotImplementedError("_create_market_take_profit_order is not implemented")

    async def _create_limit_take_profit_order(
        self, symbol, quantity, price=None, side=None, params=None
    ) -> dict:
        raise NotImplementedError("_create_limit_take_profit_order is not implemented")

    async def _create_market_trailing_stop_order(
        self, symbol, quantity, price=None, side=None, params=None
    ) -> dict:
        raise NotImplementedError(
            "_create_market_trailing_stop_order is not implemented"
        )

    async def _create_limit_trailing_stop_order(
        self, symbol, quantity, price=None, side=None, params=None
    ) -> dict:
        raise NotImplementedError(
            "_create_limit_trailing_stop_order is not implemented"
        )


class BinanceUsdMAdapter(exchanges.CCXTAdapter):
    BINANCE_MODE = "hedged"
    POSITION_SIDE = "positionSide"

    def parse_position(self, fixed, **kwargs):
        # REALIZED_PNL, CLOSING_FEE, BANKRUPTCY_PRICE is not available in position
        try:
            raw_position_info = fixed.get(
                ccxt_enums.ExchangePositionCCXTColumns.INFO.value
            )
            size = decimal.Decimal(
                str(
                    fixed.get(ccxt_enums.ExchangePositionCCXTColumns.CONTRACTS.value, 0)
                )
            )
            # if size == constants.ZERO:
            #     return {}  # Don't parse empty position

            symbol = self.connector.get_pair_from_exchange(
                fixed[ccxt_enums.ExchangePositionCCXTColumns.SYMBOL.value]
            )
            raw_mode = fixed.get(self.BINANCE_MODE)
            if raw_mode is False:
                mode = trading_enums.PositionMode.ONE_WAY
            elif raw_mode is True:
                mode = trading_enums.PositionMode.HEDGE
            else:
                raise ValueError("cant detect the PositionMode")
            original_side = raw_position_info.get(self.POSITION_SIDE)
            try:
                side = trading_enums.PositionSide(original_side.lower())
            except ValueError:
                side = trading_enums.PositionSide.UNKNOWN
            unrealized_pnl = self.safe_decimal(
                fixed,
                ccxt_enums.ExchangePositionCCXTColumns.UNREALIZED_PNL.value,
                constants.ZERO,
            )
            liquidation_price = self.safe_decimal(
                fixed,
                ccxt_enums.ExchangePositionCCXTColumns.LIQUIDATION_PRICE.value,
                constants.ZERO,
            )
            entry_price = self.safe_decimal(
                fixed,
                ccxt_enums.ExchangePositionCCXTColumns.ENTRY_PRICE.value,
                constants.ZERO,
            )
            return {
                trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value: symbol,
                trading_enums.ExchangeConstantsPositionColumns.TIMESTAMP.value: self.connector.client.safe_value(
                    fixed, ccxt_enums.ExchangePositionCCXTColumns.TIMESTAMP.value, 0
                ),
                trading_enums.ExchangeConstantsPositionColumns.SIDE.value: side,
                trading_enums.ExchangeConstantsPositionColumns.MARGIN_TYPE.value: trading_enums.TraderPositionType(
                    fixed.get(ccxt_enums.ExchangePositionCCXTColumns.MARGIN_MODE.value)
                ),
                trading_enums.ExchangeConstantsPositionColumns.SIZE.value: size
                if original_side == trading_enums.PositionSide.LONG.value
                else -size,
                trading_enums.ExchangeConstantsPositionColumns.SINGLE_CONTRACT_VALUE.value: self.safe_decimal(
                    fixed,
                    ccxt_enums.ExchangePositionCCXTColumns.CONTRACT_SIZE.value,
                    constants.ONE,
                ),
                trading_enums.ExchangeConstantsPositionColumns.INITIAL_MARGIN.value: self.safe_decimal(
                    fixed,
                    ccxt_enums.ExchangePositionCCXTColumns.INITIAL_MARGIN.value,
                    constants.ZERO,
                ),
                trading_enums.ExchangeConstantsPositionColumns.VALUE.value: self.safe_decimal(
                    fixed,
                    ccxt_enums.ExchangePositionCCXTColumns.NOTIONAL.value,
                    constants.ZERO,
                ),
                trading_enums.ExchangeConstantsPositionColumns.LEVERAGE.value: self.safe_decimal(
                    fixed,
                    ccxt_enums.ExchangePositionCCXTColumns.LEVERAGE.value,
                    constants.ONE,
                ),
                trading_enums.ExchangeConstantsPositionColumns.UNREALIZED_PNL.value: unrealized_pnl,
                trading_enums.ExchangeConstantsPositionColumns.LIQUIDATION_PRICE.value: liquidation_price,
                trading_enums.ExchangeConstantsPositionColumns.ENTRY_PRICE.value: entry_price,
                trading_enums.ExchangeConstantsPositionColumns.CONTRACT_TYPE.value: self.connector.exchange_manager.exchange.get_contract_type(
                    symbol
                ),
                trading_enums.ExchangeConstantsPositionColumns.POSITION_MODE.value: mode,
            }
        except KeyError as e:
            self.logger.error(f"Fail to parse position dict ({e})")
        return fixed

    BINANCE_REDUCE_ONLY = "reduceOnly"
    BINANCE_TRIGGER_PRICE = "triggerPrice"

    def fix_order(self, raw, **kwargs):
        fixed = super().fix_order(raw, **kwargs)
        order_info = raw[trading_enums.ExchangeConstantsOrderColumns.INFO.value]
        # parse reduce_only if present
        fixed[
            trading_enums.ExchangeConstantsOrderColumns.REDUCE_ONLY.value
        ] = order_info.get(self.BINANCE_REDUCE_ONLY, False)
        # stop orders ise triggerPrice
        if not fixed.get(trading_enums.ExchangeConstantsOrderColumns.PRICE.value):
            fixed[trading_enums.ExchangeConstantsOrderColumns.PRICE.value] = fixed.get(
                self.BINANCE_TRIGGER_PRICE
            )
        self._adapt_order_type(fixed)

        return fixed

    def _adapt_order_type(self, fixed):
        if (
            fixed[trading_enums.ExchangeConstantsOrderColumns.REDUCE_ONLY.value]
            and trading_enums.TradeOrderType.STOP_MARKET.value
            == fixed[trading_enums.ExchangeConstantsOrderColumns.TYPE.value]
        ):
            # stop loss are not tagged as such by ccxt, force it
            fixed[
                trading_enums.ExchangeConstantsOrderColumns.TYPE.value
            ] = trading_enums.TradeOrderType.STOP_LOSS.value

        return fixed
