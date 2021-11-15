from tentacles.Evaluator.TA import *
import octobot_trading.api as api
import octobot_commons.enums as commons_enums
import time
from octobot_trading.modes.scripting_library import *


async def script(ctx, run_id):
    drawing = DisplayedElements()
    async with DBReader.database(get_backtesting_db(ctx, run_id)) as reader:
        with drawing.part("backtesting-chart") as part:
            await plot_historical_portfolio_value(reader, part)
            await plot_historical_pnl_value(reader, part, x_as_trade_count=False, own_yaxis=True)
        with drawing.part("list-of-trades-part", "table") as part:
            await plot_table(reader, part, "SMA 1")
            await plot_table(reader, part, "SMA 2")
            await plot_trades(reader, part)
    return drawing
