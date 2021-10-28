from tentacles.Evaluator.TA import *
from octobot_trading.modes.scripting_library import *


async def script(ctx: Context):
    if is_evaluation_higher_than(
            ctx,
            evaluator_class=RSIMomentumEvaluator,
            value=-1,
            time_frames=["1h"],
    ):
        price = Open(
            ctx,
            "BTC/USDT", "1h"
        )
        await market(
            ctx,
            amount="60%",
            side="buy",
            tag="marketIn"
        )
        await wait_for_price(
            ctx,
            offset=0,
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
        ctx.logger.info("RSI not high enough")
