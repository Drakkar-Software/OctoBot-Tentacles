# AI Index Trading Mode

## Overview

The **AI Index Trading Mode** is an advanced trading mode that inherits from `IndexTradingMode` and uses artificial intelligence (GPT) to dynamically generate portfolio distributions based on strategy evaluation descriptions. This mode combines the robust rebalancing infrastructure of index trading with AI-driven decision making for optimal asset allocation.

## Key Features

- **AI-Driven Allocations**: Uses GPT models to analyze strategy signals and generate optimal portfolio weights
- **Strategy Integration**: Incorporates TA, Social, and Real-time evaluator signals
- **Detailed Explanations**: AI provides reasoning for each allocation decision
- **Risk Management**: Optional USD allocation for conservative positioning
- **Fallback Mechanisms**: Gracefully handles AI failures with configurable fallback distributions
- **Inherits IndexTradingMode**: Full rebalancing, order management, and portfolio optimization capabilities
- **Configurable AI Parameters**: Model selection, temperature, token limits, and strategy types

## Configuration

### Required Strategies
The mode requires AI strategy evaluators to function optimally:
- `LLMAIStrategyEvaluator`: Unified AI analysis combining TA, Social, and Real-Time signals through parallel sub-agents

### AI Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | string | "gpt-4" | GPT model to use (gpt-3.5-turbo, gpt-4, gpt-4-turbo) |
| `temperature` | float | 0.3 | AI creativity (0.0 = deterministic, 1.0 = very creative) |
| `max_tokens` | int | 2000 | Maximum tokens for AI response |
| `strategy_types` | array | ["TA", "SOCIAL"] | Evaluator types to include in analysis |
| `risk_management` | boolean | true | Enable USD allocation for conservative risk management |

### Index Trading Parameters (inherited)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `refresh_interval` | int | 1 | Days between rebalance checks |
| `rebalance_trigger_min_percent` | int | 5 | Minimum % deviation before rebalance |
| `fallback_distribution` | array | [] | Static distribution if AI fails (empty = even distribution) |

## How It Works

### 1. Strategy Signal Aggregation
The AI Index Trading Mode collects evaluation descriptions from configured strategy evaluators:
- Technical Analysis (TA) signals
- Social sentiment signals
- Real-time evaluation signals

### 2. AI Analysis
When a rebalance is triggered, the mode:
1. Prepares current portfolio distribution context
2. Aggregates strategy evaluation descriptions
3. Calls GPT service with specialized prompts
4. Parses AI-generated allocation recommendations

### 3. Distribution Generation
The AI generates allocations based on:
- **Signal Strength**: Prioritizes high-confidence signals
- **Consensus**: Favors agreements across strategies
- **Risk Management**: When enabled, may allocate to USD during uncertain market conditions
- **Diversification**: Maintains balanced exposure across assets
- **Market Context**: Considers current portfolio positions

### 4. Rebalancing Execution
Uses IndexTradingMode's proven rebalancing logic:
- Calculates required trades
- Manages sell/buy order sequencing
- Handles exchange constraints
- Ensures portfolio matches target allocations

## AI Decision Making

### Input Data
The AI receives:
- Current portfolio allocation percentages
- Available tradable assets
- Strategy evaluation descriptions with confidence levels
- Historical performance context (when available)

### Output Format
AI returns JSON with asset allocations and explanations:
```json
[
  {"name": "BTC", "percentage": 35.5, "explanation": "Strong bullish signals from technical analysis with high confidence"},
  {"name": "ETH", "percentage": 25.2, "explanation": "Moderate positive sentiment from social signals"},
  {"name": "ADA", "percentage": 15.1, "explanation": "Balanced allocation for diversification"},
  {"name": "DOT", "percentage": 24.2, "explanation": "Positive momentum indicators suggest increased weighting"}
]
```

### Validation
All AI outputs are validated for:
- Total allocation summing to 100%
- Assets being tradable on configured exchanges
- Reasonable percentage ranges (0-100%)
- No invalid or unavailable assets

## Fallback Mechanisms

### Primary Fallback
If AI generation fails:
1. Uses configured `fallback_distribution`
2. If no fallback configured, uses even distribution across all assets

### Error Scenarios
- **GPT Service Unavailable**: Falls back immediately
- **Invalid AI Response**: Logs error, uses fallback
- **No Strategy Signals**: Uses fallback distribution
- **Network/API Errors**: Retries once, then falls back

## Risk Management

### USD Allocation
When `risk_management` is enabled, the AI may allocate portions to USD (or the reference market currency) during:
- Uncertain market conditions
- Bearish signal consensus
- High volatility periods
- When strategy signals conflict significantly

### Conservative Positioning
The AI considers risk factors such as:
- Portfolio concentration limits
- Market volatility indicators
- Signal confidence levels
- Historical drawdown patterns (when available)

### Configuration Impact
- **Enabled**: AI may allocate 0-50% to USD for safety
- **Disabled**: AI focuses purely on signal-based allocations without risk hedging

## Usage Examples

### Basic Configuration
```json
{
  "trading_mode": "AIIndexTradingMode",
  "model": "gpt-4",
  "temperature": 0.3,
  "strategy_types": ["TA", "SOCIAL"],
  "risk_management": true,
  "refresh_interval": 1,
  "rebalance_trigger_min_percent": 5
}
```

### Conservative Configuration
```json
{
  "trading_mode": "AIIndexTradingMode",
  "model": "gpt-3.5-turbo",
  "temperature": 0.1,
  "strategy_types": ["TA"],
  "risk_management": true,
  "max_tokens": 1500,
  "refresh_interval": 2
}
```

### With Custom Fallback
```json
{
  "trading_mode": "AIIndexTradingMode",
  "fallback_distribution": [
    {"name": "BTC", "percentage": 40},
    {"name": "ETH", "percentage": 30},
    {"name": "ADA", "percentage": 20},
    {"name": "DOT", "percentage": 10}
  ]
}
```

## Testing

Use the tentacles-agent tools to test:
```bash
# Test with AI evaluators
python tentacle_trading_mode_tester.py --mode AIIndexTradingMode --evaluators ai_evaluators.json --symbol BTC/USDT --duration 120

# Test basic functionality
python tentacle_configuration_tester.py --config ai_index_config.json --validate
```

## Dependencies

- **GPTService**: Required for AI functionality
- **Strategy Evaluators**: AI evaluators recommended for optimal performance
- **IndexTradingMode**: Inherited functionality

## Troubleshooting

### Common Issues

**AI responses are invalid**
- Check GPT service configuration
- Verify API keys and connectivity
- Review AI parameter settings (lower temperature)

**No rebalancing occurs**
- Verify strategy evaluators are active
- Check rebalance trigger thresholds
- Ensure sufficient portfolio balance

**High API costs**
- Increase refresh_interval
- Use gpt-3.5-turbo instead of gpt-4
- Reduce max_tokens

### Logs to Check
- AI decision logs: `"AI generated distribution: {...}"`
- Fallback activations: `"using fallback distribution"`
- Validation errors: `"Distribution total X% is not close to 100%"`

## Future Enhancements

- **Historical Performance**: Include backtesting results in AI prompts
- **Risk Metrics**: Add volatility and correlation analysis
- **Multi-Timeframe**: Consider different timeframe signals
- **Custom Prompts**: Allow user-defined AI prompts
- **Ensemble Methods**: Combine multiple AI models