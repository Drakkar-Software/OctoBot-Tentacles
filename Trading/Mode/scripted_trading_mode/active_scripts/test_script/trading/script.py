from tentacles.Evaluator.TA import *
from octobot_trading.modes.scripting_library import *


async def script(ctx: Context):
    writer = DBWriter("scriptedTradingMode.json")
    if is_evaluation_higher_than(
            ctx,
            evaluator_class=RSIMomentumEvaluator,
            value=-1,
            time_frames=["1h"],
    ):
        writer.log("evaluations", {"value": "higher than -1"})
        price = Open(
            ctx,
            "BTC/USDT", "1h"
        )
        writer.log("prices", {"value": price[-1], "time": Time(ctx, ctx.traded_pair, "1h")[-1]})
        orders = await market(
            ctx,
            amount="60%",
            side="buy",
            tag="marketIn"
        )
        log_orders(writer, orders)
        await wait_for_price(
            ctx,
            offset=0,
        )
        orders = await trailling_market(
            ctx,
            amount="40%",
            side="buy",
            tag="tryLimitOut",
            min_offset=5,  # TODO use "5%"
            max_offset=0,
            slippage_limit=50,
            postonly=True,
        )
        log_orders(writer, orders)
    else:
        ctx.logger.info("RSI not high enough")
