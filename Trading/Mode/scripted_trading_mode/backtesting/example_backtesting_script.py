from tentacles.Evaluator.TA import *
import octobot_trading.api as api
import octobot_commons.enums as commons_enums
import time
from octobot_trading.modes.scripting_library import *


async def backtest_test_script():

    # load 

    # calculate backtesting metrics per trade
    realized_pnl(entry, texit, positionsize, fees, ordertype)
        # https://help.bybit.com/hc/en-us/articles/900000404726-P-L-calculations-Inverse-Contracts-#h_7ec0530a-2556-4cb4-848d-047678361cc8

    # backup current script within backtesting data folder

    # calculate backtesting metrics per iteration
    realized_pnl(entry, texit, positionsize, fees, ordertype)

    # change variables from trading script and rerun backtest

    # plot backtesting data
    reader = DBReader("scriptedTradingMode.json")

    drawing = PlottedElements()
    with drawing.part("main-chart") as part:
        order_times = []
        order_prices = []
        for order in reader.select("orders", reader.search().state == "closed"):
            order_times.append(order["time"])
            order_prices.append(order["price"])
        part.plot(
            kind="markers",
            x=order_times,
            y=order_prices,
            title="Orders")


    return drawing
