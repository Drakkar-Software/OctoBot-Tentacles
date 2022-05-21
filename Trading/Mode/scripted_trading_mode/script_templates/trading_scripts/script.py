from tentacles.Meta.Keywords import *


async def script(ctx: Context):
    # this is merely an example script, it will not work as is as it requires the bellow listed evaluators
    set_backtesting_iteration_timeout(ctx, 1500)
    await plot_candles(ctx)
    await _plot_current_position(ctx)
    await set_candles_history_size(ctx, 1000)
    await activate_managed_orders(ctx)
    await trigger_only_on_the_first_candle(ctx, False)
    # await user_select_emit_trading_signals(ctx, "example_strategy")

    nr_of_indicators = await user_input(ctx, "0. Number of Indicators combined together", "int", 2, 1)

    available_indicators = ["indicators_crossing", "indicator_oversold", "indicator_is_rising", "SFP",
                            "is_above_indicator", "dual_trend", "cheat_indicator"]
    selected_indicators = []
    for i in range(0, nr_of_indicators):
        selected_indicators.append(await user_input(ctx, f"{i + 1}. select indicator", "options",
                                                    "indicator_is_rising", options=available_indicators))

    side = "long"
    if ctx.exchange_manager.is_backtesting:
        for i in range(0, nr_of_indicators):
            selected_indicator = selected_indicators[i]
            buy_signal = None
            if selected_indicator == "SFP":
                try:
                    sell, buy_signal = await evaluator_get_result(ctx, tentacle_class=selected_indicator,
                                                                  trigger=True,
                                                                  config_name=f"{selected_indicator} {i + 1}")
                except ValueError:
                    pass
            else:
                buy_signal = await evaluator_get_result(ctx, tentacle_class=selected_indicator,
                                                        trigger=True, config_name=f"{selected_indicator} {i + 1}")
            if buy_signal is True:
                if i + 1 == nr_of_indicators:
                    await managed_order(ctx, trading_side=side)
            else:
                break

    else:  # live mode
        final_buy_signal = True
        for i in range(0, nr_of_indicators):
            selected_indicator = selected_indicators[i]
            buy_signal = None
            if selected_indicator == "SFP":
                try:
                    sell, buy_signal = await evaluator_get_result(ctx, tentacle_class=selected_indicator,
                                                                  trigger=True,
                                                                  config_name=f"{selected_indicator} {i + 1}")
                except ValueError:
                    pass
            else:

                buy_signal = await evaluator_get_result(ctx, tentacle_class=selected_indicator,
                                                        trigger=True, config_name=f"{selected_indicator} {i + 1}")
            if buy_signal is True and final_buy_signal:
                if i + 1 == nr_of_indicators:
                    await managed_order(ctx, side=side)
            else:
                final_buy_signal = False
    # set_initialized_evaluation(ctx)
    await _plot_orders(ctx)
    await emit_trading_signals(ctx)
    ctx.logger.info("trading script done")


async def _plot_current_position(ctx):
    enable_plot_position = await user_input(ctx, "plot open position", "boolean", False,
                                                        show_in_summary=False, show_in_optimizer=False)
    if enable_plot_position:
        try:
            current_pos = open_positions.open_position_size(ctx)
        except AttributeError:
            print("plot position error")
            current_pos = 0
        if ctx.exchange_manager.is_backtesting:
            await ctx.set_cached_value(value=float(current_pos), value_key="op")

            await plotting.plot(ctx, "current position", cache_value="op", chart="sub-chart",
                                color="blue", shift_to_open_candle_time=False)
        else:
            await ctx.set_cached_value(value=float(current_pos), value_key="l-os")

            await plotting.plot(ctx, "current position", cache_value="l-op", chart="sub-chart",
                                color="blue", shift_to_open_candle_time=False)


async def _plot_orders(ctx):
    plot_orders = await user_input(ctx, "plot orders (slows down backtests)", "boolean", False,
                                               show_in_summary=False, show_in_optimizer=False)

    if plot_orders:
        _open_orders = open_orders.get_open_orders(ctx)
        tp_list = []
        sl_list = []
        entry_list = []
        for order in _open_orders:
            if order.exchange_order_type.name == "STOP_LOSS":
                sl_list.append(float(order.origin_price))
            elif order.reduce_only is True:
                tp_list.append(float(order.origin_price))
            else:
                entry_list.append(float(order.origin_price))
        if ctx.exchange_manager.is_backtesting:
            if tp_list:
                await ctx.set_cached_value(value=tp_list, value_key="tp")
            if sl_list:
                await ctx.set_cached_value(value=sl_list, value_key="sl")
            if entry_list:
                await ctx.set_cached_value(value=entry_list, value_key="entry")
            try:
                await plot(ctx, "stop loss", cache_value="sl", mode="markers", chart="main-chart",
                                    color="yellow",
                                    shift_to_open_candle_time=False)
                await plot(ctx, "take profit", cache_value="tp", mode="markers", chart="main-chart",
                                    color="magenta",
                                    shift_to_open_candle_time=False)
                await plot(ctx, "entry", cache_value="entry", mode="markers", chart="main-chart", color="blue",
                                    shift_to_open_candle_time=False)
            except RuntimeError as e:
                ctx.logger.error(f"plot orders error ({e})")  # no cache
        else:
            if tp_list:
                await ctx.set_cached_value(value=tp_list, value_key="l-tp")
            if sl_list:
                await ctx.set_cached_value(value=sl_list, value_key="l-sl")
            if entry_list:
                await ctx.set_cached_value(value=entry_list, value_key="l-entry")
            await plot(ctx, "stop loss", cache_value="l-sl", mode="markers", chart="main-chart",
                                color="yellow",
                                shift_to_open_candle_time=False)
            await plot(ctx, "take profit", cache_value="l-tp", mode="markers", chart="main-chart",
                                color="magenta",
                                shift_to_open_candle_time=False)
            await plot(ctx, "entry", cache_value="l-entry", mode="markers", chart="main-chart",
                                color="blue",
                                shift_to_open_candle_time=False)
