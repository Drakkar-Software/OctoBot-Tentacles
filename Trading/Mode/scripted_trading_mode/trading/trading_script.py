from tentacles.Evaluator.TA import *
from octobot_trading.modes.scripting_library import *


def crossover(val1, val2):
    # true if val1 just got over val2
    return val1[-1] > val2[-1] and val1[-2] < val2[-2]


async def script(ctx: Context):
    pass
    set_script_name(ctx, "SimpleRSI with 40/60")
    #
    rsi_length = await user_input(ctx, "rsi_length", "int", 11)
    percent_volume = await user_input(ctx, "% volume", "float", 10.4, min_val=1, max_val=100)
    use_stop_loss = await user_input(ctx, "use_stop_loss", "boolean", False)
    data_source = await user_input(ctx, "data source", "options", "close", options=["open", "high", "low", "close"])
    #
    percent_volume = 30
    pair = ctx.traded_pair
    ctx.time_frame = "1h"
    await plot_candles(ctx, pair, ctx.time_frame)
    #
    # # TA initial variables
    candle_source = Close(ctx, pair, ctx.time_frame, 36)
    # if data_source == "open":
    #     candle_source = Open(ctx, pair, time_frame)
    # if data_source == "high":
    #     candle_source = High(ctx, pair, time_frame)
    # if data_source == "low":
    #     candle_source = Low(ctx, pair, time_frame)
    if len(candle_source) > 35:
        sma1 = ti.sma(candle_source, 15)
        sma2 = ti.sma(candle_source, 35)

        t = Time(ctx, pair, ctx.time_frame, limit=1 if ctx.writer.are_data_initialized else -1)
        await plot(ctx, "SMA 1", t, sma1)
        # await plot(ctx, "SMA 2", t, sma2)

        # ema_is_rising = ti.ema(candle_source, 5)[:-1] < ti.ema(candle_source, 5)[1:]
        # high = High(ctx, pair, ctx.time_frame) + 10
        # await plot(ctx, "ema_is_rising", condition=ema_is_rising, y=high,
        #            chart=trading_enums.PlotCharts.MAIN_CHART.value, kind="markers")

        # await plot(ctx, "RSI * 1200", Time(ctx, pair, time_frame), rsi_data * 1200)
        # await plot(ctx, "source price", Time(ctx, pair, time_frame), candle_source)

        # if rsi_data[-1] < 50:
        if crossover(sma1, sma2):
            await market(
                ctx,
                amount=f"{percent_volume}%",
                side="buy",
                tag="marketIn"
            )
        # if rsi_data[-1] > 50:
        if crossover(sma2, sma1):
            await market(
                ctx,
                amount=f"{percent_volume}%",
                side="sell",
                tag="marketOut"
            )

    ctx.logger.info("script done")
