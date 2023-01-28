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
import time
import decimal

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
        for i in range(0, Kucoin.MAX_CANDLES_FETCH_INSTANT_RETRY):
            try:
                return await f(*args, **kwargs)
            except octobot_trading.errors.FailedRequest as e:
                if Kucoin.INSTANT_RETRY_ERROR_CODE in str(e):
                    # should retry instantly, error on kucoin side
                    # see https://github.com/Drakkar-Software/OctoBot/issues/2000
                    logging.get_logger(Kucoin.get_name()).debug(
                        f"{Kucoin.INSTANT_RETRY_ERROR_CODE} error on request, retrying now "
                        f"(attempt {i+1} / {Kucoin.MAX_CANDLES_FETCH_INSTANT_RETRY}).")
                else:
                    raise
        raise octobot_trading.errors.FailedRequest(
            f"Failed request after {Kucoin.MAX_CANDLES_FETCH_INSTANT_RETRY} retries due "
            f"to {Kucoin.INSTANT_RETRY_ERROR_CODE} error code"
        )
    return wrapper


class Kucoin(exchanges.RestExchange):
    MAX_CANDLES_FETCH_INSTANT_RETRY = 5
    INSTANT_RETRY_ERROR_CODE = "429000"
    FUTURES_CCXT_CLASS_NAME = "kucoinfutures"

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
        return self.get_fixed_market_status(symbol, price_example=price_example, with_fixer=with_fixer,
                                            remove_price_limits=True)

    @_kucoin_retrier
    async def get_symbol_prices(self, symbol, time_frame, limit: int = 200, **kwargs: dict):
        if "since" in kwargs:
            # prevent ccxt from fillings the end param (not working when trying to get the 1st candle times)
            kwargs["endAt"] = int(time.time() * 1000)
        return await super().get_symbol_prices(symbol=symbol, time_frame=time_frame, limit=limit, **kwargs)

    async def get_recent_trades(self, symbol, limit=50, **kwargs):
        # on ccxt kucoin recent trades are received in reverse order from exchange and therefore should never be
        # filtered by limit before reversing (or most recent trades are lost)
        recent_trades = await super().get_recent_trades(symbol, limit=None, **kwargs)
        return recent_trades[::-1][:limit] if recent_trades else []

    async def get_order_book(self, symbol, limit=20, **kwargs):
        # override default limit to be kucoin complient
        return super().get_order_book(symbol, limit=limit, **kwargs)

    def should_log_on_ddos_exception(self, exception) -> bool:
        """
        Override when necessary
        """
        return Kucoin.INSTANT_RETRY_ERROR_CODE not in str(exception)

    """
    Margin and leverage
    todo:
        fetch position (get closed positions)
    """

    async def get_position(self, symbol: str, **kwargs: dict) -> dict:
        """
        Get the current user symbol position list
        :param symbol: the position symbol
        :return: the user symbol position list
        """

        # todo remove when supported by ccxt
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

    async def get_positions(self, symbols=None, **kwargs: dict) -> list:
        if symbols is None:
            # return await super().get_positions(symbols=symbols, **kwargs)
            raise NotImplementedError
        # force get_position when symbols is set as ccxt get_positions is only returning open positions
        return [
            await self.get_position(symbol, **kwargs)
            for symbol in symbols
        ]



class KucoinCCXTAdapter(exchanges.CCXTAdapter):
    # Funding
    KUCOIN_DEFAULT_FUNDING_TIME = 8 * commons_constants.HOURS_TO_SECONDS

    # POSITION
    KUCOIN_AUTO_DEPOSIT = "autoDeposit"

    # ORDER
    KUCOIN_LEVERAGE = "leverage"

    def fix_order(self, raw, **kwargs):
        raw_order_info = raw[ccxt_enums.ExchangePositionCCXTColumns.INFO.value]
        fixed = super().fix_order(raw, **kwargs)
        # amount is in contact, multiply by contract value to get the currency amount (displayed to the user)
        symbol = fixed[trading_enums.ExchangeConstantsOrderColumns.SYMBOL.value]
        contract_size = ccxt_client_util.get_contract_size(self.connector.client, symbol)
        fixed[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] = \
            fixed[trading_enums.ExchangeConstantsOrderColumns.AMOUNT.value] * contract_size
        fixed[trading_enums.ExchangeConstantsOrderColumns.COST.value] = \
            fixed[trading_enums.ExchangeConstantsOrderColumns.COST.value] * \
            float(raw_order_info.get(self.KUCOIN_LEVERAGE, 1))
        return fixed

    def parse_funding_rate(self, fixed, from_ticker=False, **kwargs):
        try:
            """
            Kucoin next funding time is not provided
            To obtain the last_funding_time : 
            => timestamp(previous_funding_timestamp) + timestamp(KUCOIN_DEFAULT_FUNDING_TIME)
            """
            previous_funding_timestamp = self.get_uniformized_timestamp(
                fixed.get(ccxt_enums.ExchangeFundingCCXTColumns.PREVIOUS_FUNDING_TIMESTAMP.value, 0)
            )
            fixed.update({
                trading_enums.ExchangeConstantsFundingColumns.LAST_FUNDING_TIME.value: previous_funding_timestamp,
                trading_enums.ExchangeConstantsFundingColumns.FUNDING_RATE.value: decimal.Decimal(
                    str(fixed.get(ccxt_enums.ExchangeFundingCCXTColumns.PREVIOUS_FUNDING_RATE.value, 0))),
                trading_enums.ExchangeConstantsFundingColumns.NEXT_FUNDING_TIME.value:
                    previous_funding_timestamp + self.KUCOIN_DEFAULT_FUNDING_TIME,
                trading_enums.ExchangeConstantsFundingColumns.PREDICTED_FUNDING_RATE.value: decimal.Decimal(
                    str(fixed.get(ccxt_enums.ExchangeFundingCCXTColumns.FUNDING_RATE.value, 0))),
            })
        except KeyError as e:
            self.logger.error(f"Fail to parse funding dict ({e})")
        return fixed

    def parse_position(self, fixed, **kwargs):
        raw_position_info = fixed[ccxt_enums.ExchangePositionCCXTColumns.INFO.value]
        parsed = super().parse_position(fixed, **kwargs)
        parsed[trading_enums.ExchangeConstantsPositionColumns.MARGIN_TYPE.value] = \
            trading_enums.TraderPositionType(
                fixed.get(ccxt_enums.ExchangePositionCCXTColumns.MARGIN_MODE.value)
            )
        parsed[trading_enums.ExchangeConstantsPositionColumns.POSITION_MODE.value] = \
            trading_enums.PositionMode.HEDGE if raw_position_info[self.KUCOIN_AUTO_DEPOSIT] \
            else trading_enums.PositionMode.ONE_WAY
        return parsed
