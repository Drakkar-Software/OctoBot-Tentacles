# pylint: disable=missing-class-docstring,missing-function-docstring
#  Drakkar-Software OctoBot-Commons
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
import typing
import dataclasses

import octobot_commons.constants
import octobot_commons.errors
import octobot_commons.dsl_interpreter as dsl_interpreter
import octobot_trading.exchanges
import octobot_trading.exchange_data
import octobot_trading.api
import octobot_trading.constants

import tentacles.Meta.DSL_operators.exchange_operators.exchange_operator as exchange_operator


@dataclasses.dataclass
class ExchangeDataDependency(dsl_interpreter.InterpreterDependency):
    exchange_manager_id: str
    symbol: typing.Optional[str]
    time_frame: typing.Optional[str]
    data_source: str = octobot_trading.constants.OHLCV_CHANNEL

    def __hash__(self) -> int:
        return hash((self.exchange_manager_id, self.symbol, self.time_frame, self.data_source))


class OHLCVOperator(exchange_operator.ExchangeOperator):
    def __init__(self, *parameters: dsl_interpreter.OperatorParameterType, **kwargs: typing.Any):
        super().__init__(*parameters, **kwargs)
        self.value: dsl_interpreter_operator.ComputedOperatorParameterType = exchange_operator.UNINITIALIZED_VALUE # type: ignore

    @staticmethod
    def get_library() -> str:
        # this is a contextual operator, so it should not be included by default in the get_all_operators function return values
        return octobot_commons.constants.CONTEXTUAL_OPERATORS_LIBRARY

    @staticmethod
    def get_parameters() -> list[dsl_interpreter.OperatorParameter]:
        return [
            dsl_interpreter.OperatorParameter(name="symbol", description="the symbol to get the OHLCV data for", required=False, type=str),
            dsl_interpreter.OperatorParameter(name="time_frame", description="the time frame to get the OHLCV data for", required=False, type=str),
        ]

    def get_symbol_and_time_frame(self) -> typing.Tuple[typing.Optional[str], typing.Optional[str]]:
        if parameters := self.get_computed_parameters():
            symbol = parameters[0] if len(parameters) > 0 else None
            time_frame = parameters[1] if len(parameters) > 1 else None
            return (
                str(symbol) if symbol is not None else None,
                str(time_frame) if time_frame is not None else None
            )
        return None, None

    def compute(self) -> dsl_interpreter.ComputedOperatorParameterType:
        if self.value is exchange_operator.UNINITIALIZED_VALUE:
            raise octobot_commons.errors.DSLInterpreterError("{self.__class__.__name__} has not been initialized")
        return self.value


def create_ohlcv_operators(
    exchange_manager: typing.Optional[octobot_trading.exchanges.ExchangeManager],
    symbol: str,
    time_frame: str,
    candle_manager_by_time_frame_by_symbol: typing.Optional[
        typing.Dict[str, typing.Dict[str, octobot_trading.exchange_data.CandlesManager]]
    ] = None
) -> typing.List[type[OHLCVOperator]]:

    if exchange_manager is None and candle_manager_by_time_frame_by_symbol is None:
        raise octobot_commons.errors.InvalidParametersError("exchange_manager or candle_manager_by_time_frame_by_symbol must be provided")

    def _get_candle_manager(
        input_symbol: typing.Optional[str], input_time_frame: typing.Optional[str]
    ) -> octobot_trading.exchange_data.CandlesManager:
        _symbol = input_symbol or symbol
        _time_frame = input_time_frame or time_frame
        if candle_manager_by_time_frame_by_symbol is not None:
            return candle_manager_by_time_frame_by_symbol[_time_frame][_symbol]
        return octobot_trading.api.get_symbol_candles_manager(
            octobot_trading.api.get_symbol_data(
                exchange_manager, _symbol, allow_creation=False
            ), 
            _time_frame
        )

    def _get_dependencies() -> typing.List[ExchangeDataDependency]:
        return [
            ExchangeDataDependency(
                exchange_manager_id=octobot_trading.api.get_exchange_manager_id(exchange_manager),
                symbol=symbol,
                time_frame=time_frame
            )
        ]

    class _ClosePriceOperator(OHLCVOperator):
        @staticmethod
        def get_name() -> str:
            return "close"

        def get_dependencies(self) -> typing.List[dsl_interpreter.InterpreterDependency]:
            return super().get_dependencies() + _get_dependencies()

        async def pre_compute(self) -> None:
            await super().pre_compute()
            self.value = _get_candle_manager(*self.get_symbol_and_time_frame()).get_symbol_close_candles(-1)

    class _VolumePriceOperator(OHLCVOperator):
        @staticmethod
        def get_name() -> str:
            return "volume"

        def get_dependencies(self) -> typing.List[dsl_interpreter.InterpreterDependency]:
            return super().get_dependencies() + _get_dependencies()

        async def pre_compute(self) -> None:
            await super().pre_compute()
            self.value = _get_candle_manager(*self.get_symbol_and_time_frame()).get_symbol_volume_candles(-1)

    return [_ClosePriceOperator, _VolumePriceOperator]