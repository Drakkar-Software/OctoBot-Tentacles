## ProfileCopyTradingMode

The Profile Copy Trading mode automatically copies the trading positions of one or more exchange profiles (such as Polymarket trader profiles) to your own account. It monitors the selected profiles in real-time and replicates their portfolio distribution, allowing you to mirror successful traders' strategies automatically.

This trading mode is particularly useful for prediction markets like Polymarket, where you can follow top traders and automatically copy their positions with your own capital allocation.

### How to Get Started

1. **Configure your exchange**: Add and configure your exchange (e.g., Polymarket) in your OctoBot profile. Make sure your exchange credentials are properly set up.

2. **Find exchange profile IDs**: You need to identify the profile IDs you want to copy. For Polymarket, these are typically found in the profile URL or leaderboard. For example, a Polymarket profile URL might be `https://polymarket.com/profile/0x1234...`, where `0x1234...` is the profile ID.

3. **Configure portfolio allocation**: Set how much of your portfolio should be allocated to copying each profile. Ensure the total allocation doesn't exceed 100% of your portfolio.

4. **Start trading**: Once configured, OctoBot will start monitoring the selected profiles and automatically adjust your portfolio to match their positions.

### Configuration Parameters

#### Exchange Profile IDs (`exchange_profile_ids`)

A list of exchange profile identifiers to copy. Each profile ID should be a valid identifier on the target exchange.

**Example**: To copy two Polymarket profiles, you would enter:
- `0x1234567890abcdef1234567890abcdef12345678`
- `0xabcdefabcdefabcdefabcdefabcdefabcdefabcd`

You can copy multiple profiles simultaneously. The portfolio allocation will be split among all profiles according to `per_exchange_profile_portfolio_ratio`. Profile IDs are exchange-specific (e.g., Polymarket uses Ethereum addresses).

#### Per Exchange Profile Portfolio Ratio (`per_exchange_profile_portfolio_ratio`)

The percentage of your total portfolio value to allocate to copying each exchange profile. This value is applied to each profile in the `exchange_profile_ids` list.

**Example**: If you have 2 profiles and set this to 30%, each profile gets 30% of your portfolio (total: 60%). If you have 1 profile and set this to 50%, that profile gets 50% of your portfolio.

**Important**: The total allocation (number of profiles × per profile ratio) must not exceed 100%. OctoBot will validate this and prevent invalid configurations.

**Example validation**:
- 3 profiles × 35% each = 105% → **Invalid** (exceeds 100%)
- 3 profiles × 30% each = 90% → **Valid**
- 2 profiles × 50% each = 100% → **Valid**

#### New Position Only (`new_position_only`)

When enabled, only positions opened after OctoBot started will be considered for copying. Existing positions in the tracked profiles are ignored.

**Use cases**:
- Set to `true` to only copy new trades made by the profile after you start following them
- Set to `false` to copy the entire current portfolio of the profile, including positions they opened before you started following

#### Unrealized PnL Percent (`min_unrealized_pnl_percent` and `max_unrealized_pnl_percent`)

Filter positions based on their unrealized profit/loss ratio relative to their collateral. Values are expressed as decimal ratios (0.1 = 10%).

**Minimum Unrealized PnL Percent** (`min_unrealized_pnl_percent`): Only copy positions that have at least this unrealized profit/loss ratio. For example, set to `0.05` to filter out losing positions and only copy positions with at least 5% unrealized profit, or set to `0.1` to copy only positions with at least 10% unrealized profit.

**Maximum Unrealized PnL Percent** (`max_unrealized_pnl_percent`): Only copy positions that have at most this unrealized profit/loss ratio. For example, set to `0.5` to avoid copying positions with more than 50% unrealized profit (might be too risky), or set to `0.2` to cap at 20% unrealized profit and limit exposure to highly profitable positions.

Set either parameter to `None` to disable that filter.

#### Mark Price (`min_mark_price` and `max_mark_price`)

Filter positions based on their mark price (current market price). Useful for filtering positions by price range.

**Minimum Mark Price** (`min_mark_price`): Only copy positions with a mark price greater than or equal to this value. For example, set to `0.5` to focus on higher-value markets and only copy positions in markets priced at $0.50 or higher, or set to `0.1` to filter out very cheap positions.

**Maximum Mark Price** (`max_mark_price`): Only copy positions with a mark price less than or equal to this value. For example, set to `0.8` to focus on lower-value markets and only copy positions in markets priced at $0.80 or lower, or set to `0.9` to filter out positions near certainty.

Set either parameter to `None` to disable that filter.

### Portfolio Allocation Validation

OctoBot automatically validates that your portfolio allocation is feasible:
- Total allocation = `per_exchange_profile_portfolio_ratio` × number of profiles
- This total must be ≤ 100%
- If validation fails, OctoBot will raise an error and prevent starting the trading mode

**Example validation**:
- 3 profiles × 35% each = 105% → **Invalid** (exceeds 100%)
- 3 profiles × 30% each = 90% → **Valid**
- 2 profiles × 50% each = 100% → **Valid**

### Troubleshooting

**Issue**: "Distribution for all exchange profiles are not yet available"
- **Solution**: Wait for the Exchange Service Feed to provide data from all configured profiles. This is normal on startup.

**Issue**: "Total portfolio allocation exceeds 100%"
- **Solution**: Reduce `per_exchange_profile_portfolio_ratio` or reduce the number of profiles in `exchange_profile_ids`.

**Issue**: "Impossible to find the Exchange service feed"
- **Solution**: Ensure the Exchange Service Feed tentacle is installed and enabled in your OctoBot configuration.

**Note**: Since Profile Copy Trading mode extends the Index Trading Mode, it also supports Index Trading Mode parameters such as `refresh_interval` and `rebalance_trigger_min_percent` for controlling portfolio rebalancing behavior.

_This trading mode supports backtesting and is compatible with PNL history._
