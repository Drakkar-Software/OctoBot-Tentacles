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
#  You should have received a copy of the GNU Lesser General
#  License along with this library.
import json
import pytest
import mock

import octobot_evaluators.enums as evaluators_enums

import tentacles.Trading.Mode.index_trading_mode.ai_index_trading as ai_index_trading
import tentacles.Trading.Mode.index_trading_mode.index_distribution as index_distribution

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mode():
    """Create a minimal AIIndexTradingMode instance for testing."""
    # Mock the required dependencies
    mock_exchange_manager = mock.Mock()
    mock_exchange_manager.is_backtesting = True
    mock_exchange_manager.services_config = None

    # Create mode instance with minimal config
    config = {}
    mode = ai_index_trading.AIIndexTradingMode(config, mock_exchange_manager)

    # Set up basic attributes
    mode.trading_config = {}
    mode.fallback_distribution = None
    mode.risk_management = True
    mode.indexed_coins = ["BTC", "ETH"]

    return mode


@pytest.mark.parametrize(
    "response,expected_valid",
    [
        (
            """[{"name": "BTC", "percentage": 60.0, "explanation": "Good signals"}]""",
            True,
        ),
        (
            """[{"name": "BTC", "percentage": 150.0, "explanation": "Invalid"}]""",
            False,
        ),  # Invalid total
        (
            """[{"name": "INVALID", "percentage": 50.0, "explanation": "Bad asset"}]""",
            False,
        ),  # Invalid asset
        ("""[{"name": "BTC", "percentage": 50.0}]""", False),  # Missing explanation
    ],
)
async def test_parse_ai_response_validation(mode, response, expected_valid):
    """Test AI response parsing with different scenarios."""
    result = mode._parse_ai_response(response)
    if expected_valid:
        assert result is not None
        assert len(result) > 0
        assert "explanation" in result[0]
    else:
        assert result is None


@pytest.mark.parametrize(
    "distribution,available_assets,expected_valid",
    [
        ([{"name": "BTC", "value": 60.0, "explanation": "Good"}], ["BTC"], True),
        ([{"name": "BTC", "value": 60.0}], ["BTC"], False),  # Missing explanation
        (
            [{"name": "INVALID", "value": 100.0, "explanation": "Bad"}],
            ["BTC"],
            False,
        ),  # Invalid asset
        (
            [{"name": "BTC", "value": -10.0, "explanation": "Bad"}],
            ["BTC"],
            False,
        ),  # Invalid percentage
    ],
)
async def test_validate_distribution(
    mode, distribution, available_assets, expected_valid
):
    """Test distribution validation with various inputs."""
    is_valid = mode._validate_distribution(distribution, available_assets)
    assert is_valid == expected_valid


async def test_generate_ai_distribution_success(mode):
    """Test successful AI distribution generation."""
    mock_gpt_service = mock.Mock()
    mock_gpt_service.create_message.return_value = {"role": "user", "content": "test"}
    mock_gpt_service.get_completion.return_value = """[
        {"name": "BTC", "percentage": 60.0, "explanation": "Strong signals"},
        {"name": "ETH", "percentage": 40.0, "explanation": "Balanced position"}
    ]"""

    with mock.patch(
        "octobot_services.api.services.get_service",
        mock.AsyncMock(return_value=mock_gpt_service),
    ):
        with mock.patch.object(
            mode, "_prepare_strategy_descriptions", return_value={"test": "data"}
        ):
            with mock.patch.object(
                mode, "_get_current_portfolio_distribution", return_value={"BTC": 50.0}
            ):
                with mock.patch.object(
                    mode, "_get_available_assets", return_value=["BTC", "ETH"]
                ):
                    distribution = await mode._generate_ai_distribution()

                    assert len(distribution) == 2
                    assert distribution[0]["name"] == "BTC"
                    assert distribution[0]["percentage"] == 60.0
                    assert "explanation" in distribution[0]


async def test_generate_ai_distribution_fallback(mode):
    """Test fallback when GPT service unavailable."""
    with mock.patch(
        "octobot_services.api.services.get_service", mock.AsyncMock(return_value=None)
    ):
        with mock.patch.object(
            mode, "_get_fallback_distribution", return_value=[{"test": "fallback"}]
        ):
            distribution = await mode._generate_ai_distribution()
            assert distribution == [{"test": "fallback"}]


async def test_prepare_strategy_descriptions(mode):
    """Test strategy data preparation from evaluator matrix."""
    mock_evaluation = mock.Mock()
    mock_evaluation.eval_note = 0.8
    mock_evaluation.eval_note_description = "Strong bullish signal"
    mock_evaluation.cryptocurrency = "BTC"
    mock_evaluation.symbol = "BTC/USDT"

    with mock.patch(
        "octobot_evaluators.matrix.get_evaluations_by_evaluator_type",
        return_value={"TestEvaluator": {"BTC": mock_evaluation}},
    ):
        strategy_data = mode._prepare_strategy_descriptions()

        assert evaluators_enums.EvaluatorMatrixTypes.TA.value in strategy_data
        assert (
            "TestEvaluator"
            in strategy_data[evaluators_enums.EvaluatorMatrixTypes.TA.value]
        )


@pytest.mark.parametrize(
    "fallback_config,indexed_coins,expected_count",
    [
        ([{"name": "BTC", "value": 100}], ["BTC"], 1),  # Configured fallback
        (None, ["BTC", "ETH"], 2),  # Even distribution fallback
        (None, [], 0),  # No assets
    ],
)
async def test_get_fallback_distribution(
    mode, fallback_config, indexed_coins, expected_count
):
    """Test fallback distribution generation."""
    mode.fallback_distribution = fallback_config
    mode.indexed_coins = indexed_coins

    fallback = mode._get_fallback_distribution()
    if expected_count > 0:
        assert len(fallback) == expected_count
    else:
        assert fallback is None


async def test_get_ai_system_prompt_risk_management(mode):
    """Test AI system prompt includes risk management when enabled."""
    mode.risk_management = True
    prompt = mode._get_ai_system_prompt()
    assert "USD" in prompt

    mode.risk_management = False
    prompt = mode._get_ai_system_prompt()
    assert "USD" not in prompt
