import octobot_commons.constants as commons_constants
import octobot_commons.enums as commons_enums
from octobot_trading.modes.scripting_library import *


async def script(ctx: Context):
    set_script_name(ctx, "EMA Trend")

    ema_length = await user_input(ctx, "EMA length", "int", 15)
    data_source = await user_input(ctx, "data source", "options", "close", options=["open", "high", "low", "close"])
    # available_timeframes = ["1h", "4h"]  # todo keyword for list of available timeframes
    # ctx.time_frame = await user_input(ctx, "Time Frame", "options", "1h", options=available_timeframes) # todo why do we need ctx.timeframe?

    ema_title = str(ema_length) + " EMA"
    ema_rising_title = str(ema_length) + " EMA is rising"
    ema_falling_title = str(ema_length) + " EMA is falling"
    time_frame_seconds = commons_enums.TimeFramesMinutes[commons_enums.TimeFrames(ctx.time_frame)] * commons_constants.MINUTE_TO_SECONDS
    last_timestamp = ctx.trigger_cache_timestamp - time_frame_seconds

    ema_value, is_ema_value_missing = await ctx.get_cached_value(ema_title)
    values = await ctx.get_cached_values(ema_title, limit=50, tentacle_name="ScriptedEvaluator")
    ema_is_rising, ema_is_rising_missing = await ctx.get_cached_value(ema_rising_title)
    ema_is_falling, ema_is_falling_missing = await ctx.get_cached_value(ema_falling_title)
    previous_ema_value, is_previous_ema_value_missing = await ctx.get_cached_value(ema_title, cache_key=last_timestamp)
    super_complicated_value, is_complicated_value_missing = await ctx.get_cached_value()

    if is_complicated_value_missing or is_ema_value_missing or is_previous_ema_value_missing:
        pair = ctx.symbol
        if is_ema_value_missing or is_previous_ema_value_missing:
            candle_source = None
            if data_source == "close":
                candle_source = Close(ctx, pair, ctx.time_frame, ema_length + 1)
            elif data_source == "open":
                candle_source = Open(ctx, pair, ctx.time_frame, ema_length + 1)
            elif data_source == "high":
                candle_source = High(ctx, pair, ctx.time_frame, ema_length + 1)
            elif data_source == "low":
                candle_source = Low(ctx, pair, ctx.time_frame)

            if len(candle_source) > ema_length:  # can we remove that somehow?
                ema_data = ti.ema(candle_source, ema_length)
                ema_value = ema_data[-1]
                previous_ema_value = ema_data[-2]
                await ctx.set_cached_value(ema_value, ema_title)
                await ctx.set_cached_value(previous_ema_value, ema_title, cache_key=last_timestamp)
        if ema_is_rising_missing and ema_value and previous_ema_value:
            ema_is_rising = previous_ema_value < ema_value
            plot_location_low = Low(ctx, pair, ctx.time_frame)[-1] - 20
            await ctx.set_cached_value(ema_is_rising, ema_rising_title, y=plot_location_low)
        if ema_is_falling_missing and ema_value and previous_ema_value:
            ema_is_falling = previous_ema_value > ema_value
            plot_location_high = High(ctx, pair, ctx.time_frame)[-1] + 20
            await ctx.set_cached_value(ema_is_falling, ema_falling_title, y=plot_location_high)

        super_complicated_value = 0.5 if ema_is_rising else -0.5

    await plot(ctx, ema_title, cache_value=ema_title, chart=trading_enums.PlotCharts.MAIN_CHART.value)
    await plot(ctx, ema_rising_title, condition=True, cache_value=ema_rising_title,
               chart=trading_enums.PlotCharts.MAIN_CHART.value, kind="markers")
    await plot(ctx, ema_falling_title, condition=True, cache_value=ema_falling_title,
               chart=trading_enums.PlotCharts.MAIN_CHART.value, kind="markers")

    return super_complicated_value
