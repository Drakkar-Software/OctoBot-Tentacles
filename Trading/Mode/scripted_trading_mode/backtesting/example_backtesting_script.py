from tentacles.Evaluator.TA import *
import octobot_trading.api as api
import octobot_commons.enums as commons_enums
import time
from octobot_trading.modes.scripting_library import *


async def script(ctx, run_id):
    drawing = PlottedElements()
    # PNL:
    # 1. open position: consider position opening fee from PNL
    # 2. close position: consider closed amount + closing fee into PNL
    # what is a trade ?
    #   when position going to 0 (from long/short) => trade is closed
    async with DBReader.database(get_backtesting_db(ctx, run_id)) as reader:
        with drawing.part("backtesting_chart") as part:
            await plot_historical_portfolio_value(reader, part)
    return drawing


async def other_script(ctx: Context):

    set_script_name(ctx, "SimpleRSI")
    pair = ctx.traded_pair
    time_frame = "1h"
    await plot(
        ctx,
        "Candles",
        x=Time(ctx, pair, time_frame),
        open=Open(ctx, pair, time_frame),
        high=High(ctx, pair, time_frame),
        low=Low(ctx, pair, time_frame),
        close=Close(ctx, pair, time_frame),
        volume=Volume(ctx, pair, time_frame),
        kind="candlestick",
        chart=trading_enums.PlotCharts.MAIN_CHART.value
    )

    # TA initial variables
    candle_source = Close(ctx, pair, time_frame)
    if len(candle_source) > 14:
        rsi_data = ti.rsi(candle_source, 14)

        await plot(ctx, "RSI", Time(ctx, pair, time_frame), rsi_data)

        if rsi_data[-1] < 30:
            await market(
                ctx,
                amount="60%",
                side="buy",
                tag="marketIn"
            )
        if rsi_data[-1] > 70:
            await market(
                ctx,
                amount="60%",
                side="sell",
                tag="marketOut"
            )

    return









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
