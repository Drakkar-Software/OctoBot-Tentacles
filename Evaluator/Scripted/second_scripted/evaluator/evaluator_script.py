from tentacles.Meta.Keywords import *


async def script(ctx):
    from tentacles.Evaluator.Scripted.second_scripted.scripted import SecondScriptedEvaluator
    set_script_name(ctx, "Second scripted eval")

    ema_length = await user_input(ctx, "EMA length", "int", 15)
    if ctx.config_name != "other_slow_ema":
        other_slow_second_script_triggered_eval = await evaluator_get_result(ctx, SecondScriptedEvaluator,
                                                                             config_name="other_slow_ema", trigger=True)

    set_minimum_candles(ctx, ema_length)
    candles_data = await user_select_candle(ctx)

    ema_data = ti.ema(candles_data, ema_length)
    await ctx.set_cached_value(ema_data[-1] * 10, "10x_ema")

    await plot(ctx, f"{ema_length} EMA", cache_value="v", chart=commons_enums.PlotCharts.MAIN_CHART.value)

    return ema_data[-1]
