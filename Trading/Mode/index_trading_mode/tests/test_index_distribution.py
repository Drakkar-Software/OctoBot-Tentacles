import decimal
import pytest

import tentacles.Trading.Mode.index_trading_mode.index_distribution as index_distribution


def test_get_uniform_distribution():
    assert index_distribution.get_uniform_distribution([]) == []
    assert index_distribution.get_uniform_distribution(["BTC", "1", "2", "3"]) == [
        {
            index_distribution.DISTRIBUTION_NAME: "BTC",
            index_distribution.DISTRIBUTION_VALUE: 25,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "1",
            index_distribution.DISTRIBUTION_VALUE: 25,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "2",
            index_distribution.DISTRIBUTION_VALUE: 25,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "3",
            index_distribution.DISTRIBUTION_VALUE: 25,
        }
    ]
    assert index_distribution.get_uniform_distribution(["BTC", "1", "2"]) == [
        {
            index_distribution.DISTRIBUTION_NAME: "BTC",
            index_distribution.DISTRIBUTION_VALUE: 33.3,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "1",
            index_distribution.DISTRIBUTION_VALUE: 33.3,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "2",
            index_distribution.DISTRIBUTION_VALUE: 33.3,
        },
    ]


def test_get_linear_distribution():
    with pytest.raises(ValueError):
        index_distribution.get_linear_distribution({})
    assert index_distribution.get_linear_distribution({
        "BTC": decimal.Decimal(122),
        "1": decimal.Decimal(12),
        "2": decimal.Decimal("0.4"),
        "3": decimal.Decimal(44)
    }) == [
        {
            index_distribution.DISTRIBUTION_NAME: "BTC",
            index_distribution.DISTRIBUTION_VALUE: 68.4,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "1",
            index_distribution.DISTRIBUTION_VALUE: 6.7,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "2",
            index_distribution.DISTRIBUTION_VALUE: 0.2,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "3",
            index_distribution.DISTRIBUTION_VALUE: 24.7,
        }
    ]
    assert index_distribution.get_linear_distribution({
        "BTC": decimal.Decimal(12332),
        "1": decimal.Decimal(12),
        "3": decimal.Decimal(433334)
    }) == [
        {
            index_distribution.DISTRIBUTION_NAME: "BTC",
            index_distribution.DISTRIBUTION_VALUE: 2.8,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "1",
            index_distribution.DISTRIBUTION_VALUE: 0,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "3",
            index_distribution.DISTRIBUTION_VALUE: 97.2,
        },
    ]


def test_get_smoothed_distribution():
    with pytest.raises(ValueError):
        index_distribution.get_smoothed_distribution({})
    assert index_distribution.get_smoothed_distribution({
        "BTC": decimal.Decimal(122),
        "1": decimal.Decimal(12),
        "2": decimal.Decimal("0.4"),
        "3": decimal.Decimal(44)
    }) == [
        {
            index_distribution.DISTRIBUTION_NAME: "BTC",
            index_distribution.DISTRIBUTION_VALUE: 43.1,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "1",
            index_distribution.DISTRIBUTION_VALUE: 19.9,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "2",
            index_distribution.DISTRIBUTION_VALUE: 6.4,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "3",
            index_distribution.DISTRIBUTION_VALUE: 30.7,
        }
    ]
    assert index_distribution.get_smoothed_distribution({
        "BTC": decimal.Decimal(12332),
        "1": decimal.Decimal(12),
        "3": decimal.Decimal(433334)
    }) == [
        {
            index_distribution.DISTRIBUTION_NAME: "BTC",
            index_distribution.DISTRIBUTION_VALUE: 22.9,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "1",
            index_distribution.DISTRIBUTION_VALUE: 2.3,
        },
        {
            index_distribution.DISTRIBUTION_NAME: "3",
            index_distribution.DISTRIBUTION_VALUE: 74.9,
        },
    ]
