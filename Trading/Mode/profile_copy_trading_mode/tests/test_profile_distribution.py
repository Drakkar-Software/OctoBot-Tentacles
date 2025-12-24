import decimal
import datetime
import pytest
import typing

import tentacles.Trading.Mode.profile_copy_trading_mode.profile_distribution as profile_distribution
import tentacles.Trading.Mode.index_trading_mode.index_distribution as index_distribution
import octobot_trading.enums as trading_enums

if typing.TYPE_CHECKING:
    import tentacles.Services.Services_feeds.exchange_service_feed as exchange_service_feed


class MockProfileData:
    def __init__(self, profile_id: str, positions: list):
        self.profile_id: str = profile_id
        self.positions: list[dict] = positions


def test_update_global_distribution_merges_overlapping_assets():
    distribution_per_exchange_profile = {
        "profile1": [
            {index_distribution.DISTRIBUTION_NAME: "BTC", index_distribution.DISTRIBUTION_VALUE: 50.0, index_distribution.DISTRIBUTION_PRICE: decimal.Decimal("50000")},
            {index_distribution.DISTRIBUTION_NAME: "ETH", index_distribution.DISTRIBUTION_VALUE: 30.0, index_distribution.DISTRIBUTION_PRICE: decimal.Decimal("3000")},
        ],
        "profile2": [
            {index_distribution.DISTRIBUTION_NAME: "BTC", index_distribution.DISTRIBUTION_VALUE: 40.0, index_distribution.DISTRIBUTION_PRICE: decimal.Decimal("51000")},
            {index_distribution.DISTRIBUTION_NAME: "SOL", index_distribution.DISTRIBUTION_VALUE: 60.0, index_distribution.DISTRIBUTION_PRICE: decimal.Decimal("100")},
        ],
    }
    per_exchange_profile_portfolio_ratio = decimal.Decimal("0.5")
    exchange_profile_ids = ["profile1", "profile2"]
    
    result = profile_distribution.update_global_distribution(
        distribution_per_exchange_profile,
        per_exchange_profile_portfolio_ratio,
        exchange_profile_ids
    )
    
    # BTC should be merged: (50.0 * 0.5) + (40.0 * 0.5) = 45.0
    assert result[profile_distribution.RATIO_PER_ASSET]["BTC"][index_distribution.DISTRIBUTION_VALUE] == decimal.Decimal("45.0")
    # ETH should be weighted: 30.0 * 0.5 = 15.0
    assert result[profile_distribution.RATIO_PER_ASSET]["ETH"][index_distribution.DISTRIBUTION_VALUE] == decimal.Decimal("15.0")
    # SOL should be weighted: 60.0 * 0.5 = 30.0
    assert result[profile_distribution.RATIO_PER_ASSET]["SOL"][index_distribution.DISTRIBUTION_VALUE] == decimal.Decimal("30.0")
    # Total should be 45.0 + 15.0 + 30.0 = 90.0
    assert result[profile_distribution.TOTAL_RATIO_PER_ASSET] == decimal.Decimal("90.0")
    assert set(result[profile_distribution.INDEXED_COINS]) == {"BTC", "ETH", "SOL"}
    # BTC price should be weighted average based on distribution values:
    # (50000 * 50.0 + 51000 * 40.0) / (50.0 + 40.0) = 50444.444...
    expected_btc_price = (decimal.Decimal("50000") * decimal.Decimal("50.0") + decimal.Decimal("51000") * decimal.Decimal("40.0")) / decimal.Decimal("90.0")
    assert expected_btc_price >= decimal.Decimal("50444") and expected_btc_price <= decimal.Decimal("50445")
    assert result[profile_distribution.INDEXED_COINS_PRICES]["BTC"] == expected_btc_price
    # ETH price should be real price (only in one profile): 3000
    assert result[profile_distribution.INDEXED_COINS_PRICES]["ETH"] == decimal.Decimal("3000")
    # SOL price should be real price (only in one profile): 100
    assert result[profile_distribution.INDEXED_COINS_PRICES]["SOL"] == decimal.Decimal("100")


def test_update_global_distribution_reference_market_ratio_calculation():
    distribution_per_exchange_profile = {
        "profile1": [
            {index_distribution.DISTRIBUTION_NAME: "BTC", index_distribution.DISTRIBUTION_VALUE: 100.0, index_distribution.DISTRIBUTION_PRICE: decimal.Decimal("50000")},
        ],
    }
    
    # Test case: 50% allocation per profile, 1 profile = 50% total, 50% reference market
    result = profile_distribution.update_global_distribution(
        distribution_per_exchange_profile,
        decimal.Decimal("0.5"),
        ["profile1"]
    )
    assert result[profile_distribution.REFERENCE_MARKET_RATIO] == decimal.Decimal("0.5")
    assert result[profile_distribution.INDEXED_COINS_PRICES]["BTC"] == decimal.Decimal("50000")
    
    # Test case: 100% allocation per profile, 1 profile = 100% total, 0% reference market
    result = profile_distribution.update_global_distribution(
        distribution_per_exchange_profile,
        decimal.Decimal("1.0"),
        ["profile1"]
    )
    assert result[profile_distribution.REFERENCE_MARKET_RATIO] == decimal.Decimal("0")
    assert result[profile_distribution.INDEXED_COINS_PRICES]["BTC"] == decimal.Decimal("50000")
    
    # Test case: 30% allocation per profile, 2 profiles = 60% total, 40% reference market
    result = profile_distribution.update_global_distribution(
        distribution_per_exchange_profile,
        decimal.Decimal("0.3"),
        ["profile1", "profile2"]
    )
    assert result[profile_distribution.REFERENCE_MARKET_RATIO] == decimal.Decimal("0.4")
    
    # Test case: Over-allocation (should cap at 0)
    result = profile_distribution.update_global_distribution(
        distribution_per_exchange_profile,
        decimal.Decimal("0.6"),
        ["profile1", "profile2"]
    )
    assert result[profile_distribution.REFERENCE_MARKET_RATIO] == decimal.Decimal("0")


def test_get_smoothed_distribution_from_profile_data_aggregates_same_symbols():
    profile_data: "exchange_service_feed.ExchangeProfile" = MockProfileData("profile1", [
        {
            trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value: "BTC/USDT",
            trading_enums.ExchangeConstantsPositionColumns.INITIAL_MARGIN.value: 100.0,
            trading_enums.ExchangeConstantsPositionColumns.ENTRY_PRICE.value: 50000.0,
        },
        {
            trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value: "BTC/USDT",
            trading_enums.ExchangeConstantsPositionColumns.INITIAL_MARGIN.value: 50.0,
            trading_enums.ExchangeConstantsPositionColumns.ENTRY_PRICE.value: 51000.0,
        },
        {
            trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value: "ETH/USDT",
            trading_enums.ExchangeConstantsPositionColumns.INITIAL_MARGIN.value: 50.0,
            trading_enums.ExchangeConstantsPositionColumns.ENTRY_PRICE.value: 3000.0,
        },
    ])
    
    started_at = datetime.datetime.now()
    result = profile_distribution.get_smoothed_distribution_from_profile_data(
        profile_data, new_position_only=False, started_at=started_at
    )
    
    # BTC should have aggregated margin: 100 + 50 = 150 out of 200 total (75%)
    # ETH should have 50 out of 200 total (25%)
    btc_dist = next((d for d in result if d[index_distribution.DISTRIBUTION_NAME] == "BTC/USDT"), None)
    eth_dist = next((d for d in result if d[index_distribution.DISTRIBUTION_NAME] == "ETH/USDT"), None)
    
    assert btc_dist is not None
    assert eth_dist is not None
    # BTC should have higher value than ETH due to aggregated margin
    assert btc_dist[index_distribution.DISTRIBUTION_VALUE] > eth_dist[index_distribution.DISTRIBUTION_VALUE]
    # Verify price information is included in the distribution
    # When multiple positions have the same symbol, the last price is used (51000.0)
    assert btc_dist[index_distribution.DISTRIBUTION_PRICE] == decimal.Decimal("51000.0")
    assert eth_dist[index_distribution.DISTRIBUTION_PRICE] == decimal.Decimal("3000.0")

    # without prices
    profile_data.positions[-1].pop(trading_enums.ExchangeConstantsPositionColumns.ENTRY_PRICE.value)
    result = profile_distribution.get_smoothed_distribution_from_profile_data(
        profile_data, new_position_only=False, started_at=started_at
    )
    
    btc_dist = next((d for d in result if d[index_distribution.DISTRIBUTION_NAME] == "BTC/USDT"), None)
    eth_dist = next((d for d in result if d[index_distribution.DISTRIBUTION_NAME] == "ETH/USDT"), None)
    
    assert btc_dist is not None
    assert eth_dist is not None
    # BTC should still have price from the second BTC position (51000.0)
    assert btc_dist[index_distribution.DISTRIBUTION_PRICE] == decimal.Decimal("51000.0")
    # ETH should have price as 0 (default value when missing)
    assert eth_dist[index_distribution.DISTRIBUTION_PRICE] == decimal.Decimal("0")


def test_update_global_distribution_merges_identical_assets_from_multiple_profiles():
    distribution_per_exchange_profile = {
        "profile1": [
            {index_distribution.DISTRIBUTION_NAME: "BTC", index_distribution.DISTRIBUTION_VALUE: 100.0, index_distribution.DISTRIBUTION_PRICE: decimal.Decimal("50000")},
        ],
        "profile2": [
            {index_distribution.DISTRIBUTION_NAME: "BTC", index_distribution.DISTRIBUTION_VALUE: 100.0, index_distribution.DISTRIBUTION_PRICE: decimal.Decimal("51000")},
        ],
    }
    
    # Both profiles have same asset with same value, each gets 40% portfolio allocation
    result = profile_distribution.update_global_distribution(
        distribution_per_exchange_profile,
        decimal.Decimal("0.4"),  # 40% per profile
        ["profile1", "profile2"]
    )
    
    # Both profiles contribute 100.0 * 0.4 = 40.0, merged = 80.0
    assert result[profile_distribution.RATIO_PER_ASSET]["BTC"][index_distribution.DISTRIBUTION_VALUE] == decimal.Decimal("80.0")
    assert result[profile_distribution.TOTAL_RATIO_PER_ASSET] == decimal.Decimal("80.0")
    # BTC price should be weighted average based on distribution values:
    # (50000 * 100.0 + 51000 * 100.0) / (100.0 + 100.0) = 50500
    expected_btc_price = (decimal.Decimal("50000") * decimal.Decimal("100.0") + decimal.Decimal("51000") * decimal.Decimal("100.0")) / decimal.Decimal("200.0")
    assert result[profile_distribution.INDEXED_COINS_PRICES]["BTC"] == expected_btc_price


def test_update_global_distribution_handles_missing_prices():
    distribution_per_exchange_profile = {
        "profile1": [
            {index_distribution.DISTRIBUTION_NAME: "BTC", index_distribution.DISTRIBUTION_VALUE: 50.0, index_distribution.DISTRIBUTION_PRICE: decimal.Decimal("50000")},
            {index_distribution.DISTRIBUTION_NAME: "ETH", index_distribution.DISTRIBUTION_VALUE: 30.0},  # No price
        ],
        "profile2": [
            {index_distribution.DISTRIBUTION_NAME: "BTC", index_distribution.DISTRIBUTION_VALUE: 40.0},  # No price
            {index_distribution.DISTRIBUTION_NAME: "SOL", index_distribution.DISTRIBUTION_VALUE: 60.0, index_distribution.DISTRIBUTION_PRICE: decimal.Decimal("100")},
        ],
    }
    per_exchange_profile_portfolio_ratio = decimal.Decimal("0.5")
    exchange_profile_ids = ["profile1", "profile2"]
    
    result = profile_distribution.update_global_distribution(
        distribution_per_exchange_profile,
        per_exchange_profile_portfolio_ratio,
        exchange_profile_ids
    )
    
    assert result[profile_distribution.INDEXED_COINS_PRICES]["BTC"] == decimal.Decimal("50000")
    # ETH: no price in any profile, so should not be in INDEXED_COINS_PRICES
    assert "ETH" not in result[profile_distribution.INDEXED_COINS_PRICES]
    assert result[profile_distribution.INDEXED_COINS_PRICES]["SOL"] == decimal.Decimal("100")

@pytest.mark.parametrize(
    "timestamp_offsets_and_symbols,expected_symbols",
    [
        # Filter positions: only those after started_at
        (
            [
                (-3600, "BTC/USDT"),  # 1 hour before - excluded
                (3600, "ETH/USDT"),   # 1 hour after - included
                (7200, "SOL/USDT"),   # 2 hours after - included
            ],
            ["ETH/USDT", "SOL/USDT"],
        ),
        # No matching positions: all before started_at
        (
            [
                (-3600, "BTC/USDT"),  # 1 hour before - excluded
                (-1800, "ETH/USDT"),  # 30 minutes before - excluded
            ],
            [],
        ),
        # Edge case: position exactly at started_at (should be excluded, as filter uses >)
        (
            [
                (0, "BTC/USDT"),      # Exactly at - excluded
                (1, "ETH/USDT"),      # 1 second after - included
            ],
            ["ETH/USDT"],
        ),
    ],
)
def test_get_positions_to_consider_filters_by_timestamp_when_new_position_only_true(timestamp_offsets_and_symbols, expected_symbols):
    """Test that positions are filtered by timestamp when new_position_only is True"""
    started_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
    profile_positions = [
        {
            trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value: symbol,
            trading_enums.ExchangeConstantsPositionColumns.TIMESTAMP.value: started_at.timestamp() + offset_seconds,
        }
        for offset_seconds, symbol in timestamp_offsets_and_symbols
    ]
    
    result = profile_distribution.get_positions_to_consider(
        profile_positions, new_position_only=True, started_at=started_at
    )
    
    result_symbols = [
        pos[trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value] for pos in result
    ]
    assert result_symbols == expected_symbols


@pytest.mark.parametrize(
    "new_position_only,expected_btc_present,expected_eth_present,btc_higher_than_eth",
    [
        (True, False, True, None),  # Only new positions (ETH) included
        (False, True, True, True),  # All positions included, BTC has higher margin
    ],
)
def test_get_smoothed_distribution_from_profile_data_respects_new_position_only(
    new_position_only, expected_btc_present, expected_eth_present, btc_higher_than_eth
):
    """Test that get_smoothed_distribution_from_profile_data respects new_position_only parameter"""
    started_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
    profile_data: "exchange_service_feed.ExchangeProfile" = MockProfileData("profile1", [
        {
            trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value: "BTC/USDT",
            trading_enums.ExchangeConstantsPositionColumns.INITIAL_MARGIN.value: 100.0,
            trading_enums.ExchangeConstantsPositionColumns.ENTRY_PRICE.value: 50000.0,
            trading_enums.ExchangeConstantsPositionColumns.TIMESTAMP.value: started_at.timestamp() - 3600,
        },
        {
            trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value: "ETH/USDT",
            trading_enums.ExchangeConstantsPositionColumns.INITIAL_MARGIN.value: 50.0,
            trading_enums.ExchangeConstantsPositionColumns.ENTRY_PRICE.value: 3000.0,
            trading_enums.ExchangeConstantsPositionColumns.TIMESTAMP.value: started_at.timestamp() + 3600,
        },
    ])
    
    result = profile_distribution.get_smoothed_distribution_from_profile_data(
        profile_data, new_position_only=new_position_only, started_at=started_at
    )
    
    btc_dist = next((d for d in result if d[index_distribution.DISTRIBUTION_NAME] == "BTC/USDT"), None)
    eth_dist = next((d for d in result if d[index_distribution.DISTRIBUTION_NAME] == "ETH/USDT"), None)
    
    assert (btc_dist is not None) == expected_btc_present
    assert (eth_dist is not None) == expected_eth_present
    
    if expected_eth_present:
        assert eth_dist[index_distribution.DISTRIBUTION_VALUE] > decimal.Decimal("0")
        assert eth_dist[index_distribution.DISTRIBUTION_PRICE] == decimal.Decimal("3000.0")
    
    if btc_higher_than_eth and btc_dist is not None and eth_dist is not None:
        assert btc_dist[index_distribution.DISTRIBUTION_VALUE] > eth_dist[index_distribution.DISTRIBUTION_VALUE]


@pytest.mark.parametrize(
    "new_position_only,expected_btc_present,expected_eth_present",
    [
        (True, False, True),   # Only new positions (ETH) included
        (False, True, True),  # All positions included
    ],
)
def test_update_distribution_based_on_profile_data_respects_new_position_only(
    new_position_only, expected_btc_present, expected_eth_present
):
    """Test that update_distribution_based_on_profile_data respects new_position_only parameter"""
    started_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
    profile_data: "exchange_service_feed.ExchangeProfile" = MockProfileData("profile1", [
        {
            trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value: "BTC/USDT",
            trading_enums.ExchangeConstantsPositionColumns.INITIAL_MARGIN.value: 100.0,
            trading_enums.ExchangeConstantsPositionColumns.ENTRY_PRICE.value: 50000.0,
            trading_enums.ExchangeConstantsPositionColumns.TIMESTAMP.value: started_at.timestamp() - 3600,
        },
        {
            trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value: "ETH/USDT",
            trading_enums.ExchangeConstantsPositionColumns.INITIAL_MARGIN.value: 50.0,
            trading_enums.ExchangeConstantsPositionColumns.ENTRY_PRICE.value: 3000.0,
            trading_enums.ExchangeConstantsPositionColumns.TIMESTAMP.value: started_at.timestamp() + 3600,
        },
    ])
    
    result = profile_distribution.update_distribution_based_on_profile_data(
        profile_data, {}, new_position_only=new_position_only, started_at=started_at
    )
    
    assert "profile1" in result
    distribution = result["profile1"]
    btc_dist = next((d for d in distribution if d[index_distribution.DISTRIBUTION_NAME] == "BTC/USDT"), None)
    eth_dist = next((d for d in distribution if d[index_distribution.DISTRIBUTION_NAME] == "ETH/USDT"), None)
    
    assert (btc_dist is not None) == expected_btc_present
    assert (eth_dist is not None) == expected_eth_present

def _position(symbol: str, collateral: float, unrealized_pnl: float, initial_margin: float = None, entry_price: float = 50000.0, mark_price: float = None) -> dict:
    m = {
        trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value: symbol,
        trading_enums.ExchangeConstantsPositionColumns.COLLATERAL.value: collateral,
        trading_enums.ExchangeConstantsPositionColumns.UNREALIZED_PNL.value: unrealized_pnl,
        trading_enums.ExchangeConstantsPositionColumns.INITIAL_MARGIN.value: initial_margin if initial_margin is not None else collateral,
        trading_enums.ExchangeConstantsPositionColumns.ENTRY_PRICE.value: entry_price,
    }
    if mark_price is not None:
        m[trading_enums.ExchangeConstantsPositionColumns.MARK_PRICE.value] = mark_price
    return m


@pytest.mark.parametrize(
    "min_unrealized_pnl_percent,max_unrealized_pnl_percent,positions,expected_symbols",
    [
        (None, None, [_position("A", 100.0, 5.0), _position("B", 100.0, 15.0)], ["A", "B"]),
        (0.1, None, [_position("A", 100.0, 10.0), _position("B", 100.0, 5.0)], ["A"]),
        (0.1, None, [_position("A", 0.0, 5.0)], ["A"]),
        (None, 0.1, [_position("A", 100.0, 5.0), _position("B", 100.0, 10.0), _position("C", 100.0, 15.0)], ["A", "B"]),
        (0.05, 0.15, [_position("A", 100.0, 5.0), _position("B", 100.0, 10.0), _position("C", 100.0, 15.0), _position("D", 100.0, 20.0)], ["A", "B", "C"]),
    ],
)
def test_get_positions_to_consider_min_max_unrealized_pnl_ratio(min_unrealized_pnl_percent, max_unrealized_pnl_percent, positions, expected_symbols):
    started_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
    result = profile_distribution.get_positions_to_consider(
        positions, new_position_only=False, started_at=started_at,
        min_unrealized_pnl_percent=min_unrealized_pnl_percent,
        max_unrealized_pnl_percent=max_unrealized_pnl_percent,
    )
    assert [p[trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value] for p in result] == expected_symbols


def test_get_smoothed_distribution_from_profile_data_respects_min_unrealized_pnl_ratio():
    """With min=0.1, only the 10% position is in the distribution; the 5% one is excluded."""
    profile_data = MockProfileData("p1", [
        _position("BTC/USDT", 100.0, 10.0),
        _position("ETH/USDT", 100.0, 5.0),
    ])
    started_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
    result = profile_distribution.get_smoothed_distribution_from_profile_data(
        profile_data, new_position_only=False, started_at=started_at,
        min_unrealized_pnl_percent=0.1,
    )
    symbols = [d[index_distribution.DISTRIBUTION_NAME] for d in result]
    assert "BTC/USDT" in symbols
    assert "ETH/USDT" not in symbols


def test_get_smoothed_distribution_from_profile_data_respects_max_unrealized_pnl_ratio():
    """With max=0.1, only 5% and 10% are in; 15% is excluded."""
    profile_data = MockProfileData("p1", [
        _position("BTC/USDT", 100.0, 5.0),
        _position("ETH/USDT", 100.0, 10.0),
        _position("SOL/USDT", 100.0, 15.0),
    ])
    started_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
    result = profile_distribution.get_smoothed_distribution_from_profile_data(
        profile_data, new_position_only=False, started_at=started_at,
        max_unrealized_pnl_percent=0.1,
    )
    symbols = [d[index_distribution.DISTRIBUTION_NAME] for d in result]
    assert "BTC/USDT" in symbols
    assert "ETH/USDT" in symbols
    assert "SOL/USDT" not in symbols


@pytest.mark.parametrize(
    "min_mark_price,max_mark_price,positions,expected_symbols",
    [
        (None, None, [_position("A", 100.0, 5.0, mark_price=100.0), _position("B", 100.0, 5.0, mark_price=200.0)], ["A", "B"]),
        (decimal.Decimal("150"), None, [_position("A", 100.0, 5.0, mark_price=100.0), _position("B", 100.0, 5.0, mark_price=200.0)], ["B"]),
        (None, decimal.Decimal("150"), [_position("A", 100.0, 5.0, mark_price=100.0), _position("B", 100.0, 5.0, mark_price=200.0)], ["A"]),
        (decimal.Decimal("150"), decimal.Decimal("250"), [_position("A", 100.0, 5.0, mark_price=100.0), _position("B", 100.0, 5.0, mark_price=200.0), _position("C", 100.0, 5.0, mark_price=300.0)], ["B"]),
    ],
)
def test_get_positions_to_consider_min_max_mark_price(min_mark_price, max_mark_price, positions, expected_symbols):
    started_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
    result = profile_distribution.get_positions_to_consider(
        positions, new_position_only=False, started_at=started_at,
        min_mark_price=min_mark_price, max_mark_price=max_mark_price,
    )
    assert [p[trading_enums.ExchangeConstantsPositionColumns.SYMBOL.value] for p in result] == expected_symbols


def test_get_smoothed_distribution_from_profile_data_respects_min_max_mark_price():
    """With min=150 and max=250, only the 200 mark_price position is in."""
    profile_data = MockProfileData("p1", [
        _position("BTC/USDT", 100.0, 5.0, mark_price=100.0),
        _position("ETH/USDT", 100.0, 5.0, mark_price=200.0),
        _position("SOL/USDT", 100.0, 5.0, mark_price=300.0),
    ])
    started_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
    result = profile_distribution.get_smoothed_distribution_from_profile_data(
        profile_data, new_position_only=False, started_at=started_at,
        min_mark_price=decimal.Decimal("150"), max_mark_price=decimal.Decimal("250"),
    )
    symbols = [d[index_distribution.DISTRIBUTION_NAME] for d in result]
    assert "BTC/USDT" not in symbols
    assert "ETH/USDT" in symbols
    assert "SOL/USDT" not in symbols

