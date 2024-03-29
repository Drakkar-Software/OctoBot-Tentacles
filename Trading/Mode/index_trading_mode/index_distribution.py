import decimal
import typing
import numpy

import octobot_trading.constants

DISTRIBUTION_NAME = "name"
DISTRIBUTION_VALUE = "value"
MAX_DISTRIBUTION_AFTER_COMMA_DIGITS = 1


def get_uniform_distribution(coins) -> typing.List:
    if not coins:
        return []
    ratio = float(
        round(
            octobot_trading.constants.ONE / decimal.Decimal(str(len(coins))) * octobot_trading.constants.ONE_HUNDRED,
            MAX_DISTRIBUTION_AFTER_COMMA_DIGITS
        )
    )
    if not ratio:
        return []
    return [
        {
            DISTRIBUTION_NAME: coin,
            DISTRIBUTION_VALUE: ratio
        }
        for coin in coins
    ]


def get_linear_distribution(weight_by_coin: dict[str, decimal.Decimal]) -> typing.List:
    total_weight = sum(weight for weight in weight_by_coin.values())
    if total_weight <= octobot_trading.constants.ZERO:
        raise ValueError(f"total weight is {total_weight}")
    return [
        {
            DISTRIBUTION_NAME: coin,
            DISTRIBUTION_VALUE: float(round(
                weight / total_weight * octobot_trading.constants.ONE_HUNDRED,
                MAX_DISTRIBUTION_AFTER_COMMA_DIGITS
            ))
        }
        for coin, weight in weight_by_coin.items()
    ]


def get_smoothed_distribution(weight_by_coin: dict[str, decimal.Decimal]) -> typing.List:
    return get_linear_distribution({
        coin: decimal.Decimal(str(numpy.cbrt(float(weight))))
        for coin, weight in weight_by_coin.items()
    })
