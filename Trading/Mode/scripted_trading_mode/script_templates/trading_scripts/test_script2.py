from tentacles.Evaluator.TA import *
import octobot_trading.api as api
from tentacles.Meta.Keywords import *


async def backtest_test_script():

    reader = DBReader("scriptedTradingMode.json")
    pair = "BTC/USDT"
    time_frame = "4h"
    exchange = "binance"
    exchange_ids = api.get_exchange_ids()
    exchange_manager = None
    for exchange_id in exchange_ids:
        try:
            exchange_manager = api.get_exchange_manager_from_exchange_name_and_id(exchange, exchange_id)
        except KeyError:
            pass
    if exchange_manager is None:
        raise RuntimeError("Exchange manager not found")

    ctx = Context.minimal(
        exchange_manager
    )

    drawing = DisplayedElements()
    rsi_data = ti.rsi(Close(ctx, pair, time_frame), 14)
    with drawing.part("main-chart") as part:
        part.plot(
            kind="candlestick",
            x=Time(ctx, pair, time_frame),
            open=Open(ctx, pair, time_frame),
            high=High(ctx, pair, time_frame),
            low=Low(ctx, pair, time_frame),
            close=Close(ctx, pair, time_frame),
            volume=Volume(ctx, pair, time_frame),
            title="Candles")
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

    with drawing.part("sub-chart") as part:
        part.plot(
            kind="scatter",
            x=Time(ctx, pair, time_frame),
            y=rsi_data,
            title="RSI")

    return drawing
