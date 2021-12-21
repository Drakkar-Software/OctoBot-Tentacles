from octobot_trading.modes.scripting_library import *


async def script(ctx):
    drawing = DisplayedElements()
    async with ctx.run_data() as run_data:
        with drawing.part("backtesting-run-overview") as part:
            await plot_historical_portfolio_value(run_data, part)
            await plot_cumulative_historical_pnl_value(run_data, part, x_as_trade_count=False, own_yaxis=True)
            await plot_historical_pnl_value(run_data, part, x_as_trade_count=False, own_yaxis=True)
        with drawing.part("backtesting-details", "value") as part:
            pnl = await backtesting_data(run_data, BacktestingMetadata.GAINS.value)
            pnl_p = await backtesting_data(run_data, BacktestingMetadata.PERCENT_GAINS.value)
            all_trades = await backtesting_data(run_data, DBTables.TRADES.value) or []
            paid_fees = total_paid_fees(all_trades)
            await display(part, "% gains", pnl_p)
            await display(part, "Gains", pnl)
            await display(part, "Trades", len(all_trades))
            await display(part, "paid fees", paid_fees)
        with drawing.part("list-of-trades-part", "table") as part:
            await plot_table(run_data, part, "SMA 1")
            await plot_table(run_data, part, "SMA 2")
            await plot_table(run_data, part, "21 EMA", cache_value="21 EMA")
            await plot_trades(run_data, part)
    return drawing
