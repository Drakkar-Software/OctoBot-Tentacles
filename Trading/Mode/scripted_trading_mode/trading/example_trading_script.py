from tentacles.Evaluator.TA import *
from octobot_trading.modes.scripting_library import *


async def script(ctx: Context):
    # init and vars
    pair = "BTC/USDT"
    if ctx.traded_pair != pair:
        return
    time_frame = "4h"
    ctx.time_frame = time_frame
    plot(
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
    rsi_data = ti.rsi(candle_source, 14)

    plot(ctx, "RSI", Time(ctx, pair, time_frame), rsi_data)

    # draw true and falses on ema rising
    ema_is_rising = ti.ema(candle_source, 5)[:-1] < ti.ema(candle_source, 5)[1:]
    high = High(ctx, pair, time_frame) + 10
    plot(ctx, "ema_is_rising", condition=ema_is_rising, y=high,
         chart=trading_enums.PlotCharts.MAIN_CHART.value, kind="markers")
    ema_is_rising = ti.ema(candle_source, 5)[-2] < ti.ema(candle_source, 5)[-1]
    # plot_shape(ctx, "ema_is_rising", ema_is_rising, candle_source[-1] + 2,
    #            chart=trading_enums.PlotCharts.MAIN_CHART.value)


    # buy Signal
    # todo should return a list of true/false
    rsi_is_oversold = rsi_data < 30
    buy_signals = rsi_is_oversold

    if buy_signals is True:
        # log initial buy signal to backtesting db
        store_message(ctx, "Oversold")
        # writer.log("evaluations", {"value": "Oversold"})



        # Filters
        ema_is_rising = ti.ema(candle_source, 5)[-2] < ti.ema(candle_source, 5)[-1]
        filters = ema_is_rising

        if filters is True:
            # log if filter passed to backtesting db with timestamp to same row as buy signal
            # writer.log("evaluations", {"value": "Oversold"})
            store_message(ctx, "Oversold")

            #delays
            delays = True
            if delays is True:
                # log if and when delay passed to backtesting db with timestamp to same row as buy signal
                store_message(ctx, "Oversold")

                # todo simulate trades based on list and store them to backtesting db
                # if live trading is enabled only execute life results
                # entry execution
                await market(
                    ctx,
                    amount="60%",
                    side="buy",
                    tag="marketIn"
                )

                await wait_for_price(
                    ctx,
                    offset=0,

                # exit execution
                )
                await trailling_market(
                    ctx,
                    amount="40%",
                    side="buy",
                    tag="tryLimitOut",
                    min_offset=5,  # TODO use "5%"
                    max_offset=0,
                    slippage_limit=50,
                    postonly=True,
                )

    else:
        ctx.logger.info("nope")


    # todo : replace by reading orders from db
    # order_times = []
    # order_prices = []
    # for order in reader.select("orders", reader.search().state == "closed"):
    #     order_times.append(order["time"])
    #     order_prices.append(order["price"])
    # part.plot(
    #     kind="markers",
    #     x=order_times,
    #     y=order_prices,
    #     title="Orders")
    # return drawing









        ctx.logger.info("RSI not high enough")
