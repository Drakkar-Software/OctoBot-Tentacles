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
import math

import octobot_commons.errors
import octobot_commons.dsl_interpreter as dsl_interpreter


class MinOperator(dsl_interpreter.CallOperator):
    MIN_PARAMS = 1

    @staticmethod
    def get_name() -> str:
        return "min"

    def compute(self) -> dsl_interpreter.ComputedOperatorParameterType:
        operands = self.get_computed_parameters()
        return min(operands)


class MaxOperator(dsl_interpreter.CallOperator):
    MIN_PARAMS = 1

    @staticmethod
    def get_name() -> str:
        return "max"

    def compute(self) -> dsl_interpreter.ComputedOperatorParameterType:
        operands = self.get_computed_parameters()
        return max(operands)


class MeanOperator(dsl_interpreter.CallOperator):
    MIN_PARAMS = 1

    @staticmethod
    def get_name() -> str:
        return "mean"

    def compute(self) -> dsl_interpreter.ComputedOperatorParameterType:
        operands = self.get_computed_parameters()
        # Ensure all operands are numeric
        numeric_operands = []
        for operand in operands:
            if isinstance(operand, (int, float)):
                numeric_operands.append(operand)
            else:
                raise octobot_commons.errors.InvalidParametersError(
                    f"mean() requires numeric arguments, got {type(operand).__name__}"
                )
        return sum(numeric_operands) / len(numeric_operands)


class SqrtOperator(dsl_interpreter.CallOperator):
    MIN_PARAMS = 1
    MAX_PARAMS = 1

    @staticmethod
    def get_name() -> str:
        return "sqrt"

    def compute(self) -> dsl_interpreter.ComputedOperatorParameterType:
        computed_parameters = self.get_computed_parameters()
        operand = computed_parameters[0]
        if isinstance(operand, (int, float)):
            return math.sqrt(operand)
        raise octobot_commons.errors.InvalidParametersError(
            f"sqrt() requires a numeric argument, got {type(operand).__name__}"
        )


class AbsOperator(dsl_interpreter.CallOperator):
    MIN_PARAMS = 1
    MAX_PARAMS = 1

    @staticmethod
    def get_name() -> str:
        return "abs"

    def compute(self) -> dsl_interpreter.ComputedOperatorParameterType:
        computed_parameters = self.get_computed_parameters()
        operand = computed_parameters[0]
        return abs(operand)


class RoundOperator(dsl_interpreter.CallOperator):
    @staticmethod
    def get_name() -> str:
        return "round"

    @staticmethod
    def get_parameters() -> list[dsl_interpreter.OperatorParameter]:
        return [
            dsl_interpreter.OperatorParameter(name="value", description="the value to round", required=True, type=list),
            dsl_interpreter.OperatorParameter(name="digits", description="the number of digits to round to", required=False, type=int),
        ]

    def compute(self) -> dsl_interpreter.ComputedOperatorParameterType:
        computed_parameters = self.get_computed_parameters()
        operand = computed_parameters[0]
        digits = int(computed_parameters[1]) if len(computed_parameters) == 2 else 0
        if isinstance(operand, (int, float)):
            return round(operand, digits)
        raise octobot_commons.errors.InvalidParametersError(
            f"round() requires a numeric argument, got {type(operand).__name__}"
        )


class FloorOperator(dsl_interpreter.CallOperator):
    MIN_PARAMS = 1
    MAX_PARAMS = 1

    @staticmethod
    def get_name() -> str:
        return "floor"

    def compute(self) -> dsl_interpreter.ComputedOperatorParameterType:
        computed_parameters = self.get_computed_parameters()
        operand = computed_parameters[0]
        if isinstance(operand, (int, float)):
            return math.floor(operand)
        raise octobot_commons.errors.InvalidParametersError(
            f"floor() requires a numeric argument, got {type(operand).__name__}"
        )


class CeilOperator(dsl_interpreter.CallOperator):
    MIN_PARAMS = 1
    MAX_PARAMS = 1

    @staticmethod
    def get_name() -> str:
        return "ceil"

    def compute(self) -> dsl_interpreter.ComputedOperatorParameterType:
        computed_parameters = self.get_computed_parameters()
        operand = computed_parameters[0]
        if isinstance(operand, (int, float)):
            return math.ceil(operand)
        raise octobot_commons.errors.InvalidParametersError(
            f"ceil() requires a numeric argument, got {type(operand).__name__}"
        )
