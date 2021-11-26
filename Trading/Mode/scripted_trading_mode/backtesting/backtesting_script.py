from tentacles.Evaluator.TA import *
import octobot_trading.api as api
import octobot_commons.enums as commons_enums
import time
from octobot_trading.modes.scripting_library import *


async def script(ctx):
    drawing = DisplayedElements()
    async with ctx.run_data() as run_data:
        with drawing.part("backtesting-chart") as part:
            await plot_historical_portfolio_value(run_data, part)
            await plot_historical_pnl_value(run_data, part, x_as_trade_count=False, own_yaxis=True)
        with drawing.part("list-of-trades-part", "table") as part:
            await plot_table(run_data, part, "SMA 1")
            await plot_table(run_data, part, "SMA 2")
            await plot_trades(run_data, part)
    return drawing
