from tentacles.Evaluator.TA import *
import octobot_trading.api as api
import octobot_commons.enums as commons_enums
import time
from octobot_trading.modes.scripting_library import *


async def script(ctx):
    drawing = DisplayedElements()
    async with ctx.run_data() as run_data:
        with drawing.part("backtesting-run-overview") as part:
            await plot_historical_portfolio_value(run_data, part)
            await plot_historical_pnl_value(run_data, part, x_as_trade_count=False, own_yaxis=True)
        with drawing.part("backtesting-details", "value") as part:
            pnl = await backtesting_data(run_data, "p&l")
            pnl_p = await backtesting_data(run_data, "p&l%")
            all_orders = await backtesting_data(run_data, "orders")
            await display(part, "% P&L", pnl_p)
            await display(part, "P&L", pnl)
            await display(part, "Orders", len(all_orders))
            await display(part, "paid fees", sum(order["fees_amount"] for order in all_orders))
        with drawing.part("list-of-trades-part", "table") as part:
            await plot_table(run_data, part, "SMA 1")
            await plot_table(run_data, part, "SMA 2")
            await plot_table(run_data, part, "RSI", cache_value="rsi")
            await plot_trades(run_data, part)
    return drawing
