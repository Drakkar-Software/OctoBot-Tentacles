from tentacles.Meta.Keywords import *


async def script(ctx):
    async with ctx.backtesting_results() as (run_data, run_display):
        with run_display.part("main-chart") as part:
            await plot_historical_pnl_value(run_data, part, include_unitary=False,
                                            x_as_trade_count=False, own_yaxis=True)
        with run_display.part("backtesting-run-overview") as part:
            await plot_historical_portfolio_value(run_data, part)
            await plot_historical_pnl_value(run_data, part, x_as_trade_count=False, own_yaxis=True)
            await plot_historical_funding_fees(run_data, part, own_yaxis=True)
            await plot_historical_wins_and_losses(run_data, part, own_yaxis=True, x_as_trade_count=False)
            await plot_historical_win_rates(run_data, part, own_yaxis=True, x_as_trade_count=False)
            await plot_best_case_growth(run_data, part, own_yaxis=True, x_as_trade_count=True)
        with run_display.part("backtesting-details", "value") as part:
            pnl = await backtesting_data(run_data, BacktestingMetadata.GAINS.value)
            pnl_p = await backtesting_data(run_data, BacktestingMetadata.PERCENT_GAINS.value)
            all_trades = await backtesting_data(run_data, DBTables.TRADES.value) or []
            paid_fees = await total_paid_fees(run_data, all_trades)
            await display(part, "% gains", pnl_p)
            await display(part, "Gains", pnl)
            await display(part, "Trades", len(all_trades))
            await display(part, "paid fees", paid_fees)
        with run_display.part("list-of-trades-part", "table") as part:
            await plot_trades(run_data, part)
            await plot_positions(run_data, part)
    return run_display
