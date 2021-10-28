from tentacles.Evaluator.TA import *
import octobot_trading.api as api
import octobot_commons.enums as commons_enums
from octobot_trading.modes.scripting_library import *


async def backtest_test_script():

    pair = "BTC/USDT"
    time_frame = "1h"
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

    drawing = PlottedElements()
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

    with drawing.part("sub-chart") as part:
        part.plot(
            kind="scatter",
            x=Time(ctx, pair, time_frame),
            y=rsi_data,
            title="RSI")


    return drawing


        # backtesting_results.plot(kind='bubble3d',x=time,y=pnl,z=winrate,size=confluence_count,text='text',categories='categories',
        #                         title='Cufflinks - Bubble 3D Chart',colorscale='set1',
        #                         width=.5,opacity=.9)
        #
        # backtesting_results.plot(kind='surface',theme='solar',colorscale='brbg',title='Cufflinks - Surface Plot',
        #                              margin=(0,0,0,0))
