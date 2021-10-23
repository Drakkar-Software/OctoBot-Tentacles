#  Drakkar-Software OctoBot
#  Copyright (c) Drakkar-Software, All rights reserved.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.
import decimal

import octobot_commons.constants as commons_constants
import async_channel.constants as channel_constants
import octobot_commons.evaluators_util as evaluators_util
import octobot_commons.symbol_util as symbol_util
import octobot_evaluators.api as evaluators_api
import octobot_evaluators.matrix as matrix
import octobot_evaluators.enums as evaluators_enums
import octobot_trading.exchange_channel as exchanges_channel
import octobot_trading.modes as trading_modes
import octobot_trading.enums as trading_enums
import octobot_trading.constants as trading_constants
import octobot_trading.errors as trading_errors
import octobot_trading.personal_data as trading_personal_data
import tentacles.Evaluator.Strategies as Strategies

import tentacles.Evaluator.TA as tech_evaluators
from octobot_trading.modes.scripting_library import *

class ScriptedTradingMode(trading_modes.AbstractTradingMode):

    def get_current_state(self) -> (str, float):
        return super().get_current_state()[0] if self.producers[0].state is None else self.producers[0].state.name, \
               "N/A"

    async def create_producers(self) -> list:
        mode_producer = ScriptedTradingModeProducer(
            exchanges_channel.get_chan(trading_constants.MODE_CHANNEL, self.exchange_manager.id),
            self.config, self, self.exchange_manager)
        await mode_producer.run()
        return [mode_producer]

    async def create_consumers(self) -> list:
        # trading mode consumer
        mode_consumer = ScriptedTradingModeConsumer(self)
        await exchanges_channel.get_chan(trading_constants.MODE_CHANNEL, self.exchange_manager.id).new_consumer(
            consumer_instance=mode_consumer,
            trading_mode_name=self.get_name(),
            cryptocurrency=self.cryptocurrency if self.cryptocurrency else channel_constants.CHANNEL_WILDCARD,
            symbol=self.symbol if self.symbol else channel_constants.CHANNEL_WILDCARD,
            time_frame=self.time_frame if self.time_frame else channel_constants.CHANNEL_WILDCARD)
        return [mode_consumer]

    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        return False


class ScriptedTradingModeConsumer(trading_modes.AbstractTradingModeConsumer):
    def __init__(self, trading_mode):
        super().__init__(trading_mode)

    async def create_new_orders(self, symbol, final_note, state, **kwargs):
        self.logger.error("create_new_orders")


class ScriptedTradingModeProducer(trading_modes.AbstractTradingModeProducer):

    async def script(self):
        if is_evaluation_higher_than(
                evaluator_class=tech_evaluators.RSIMomentumEvaluator,
                value=-1,
                time_frames=["1h"],
                pairs=[self.traded_pair],
                currencies=[self.cryptocurrency],
                exchange_name=self.exchange_name,
                matrix_id=self.matrix_id
                ):

            price = Open(
                self.exchange_manager, # to remove
                "BTC/USDT", "1h"
            )
            await market(
                self.exchange_manager.trader,
                available_balance_percent=60,
                side="buy",
                symbol=self.traded_pair,
                tag="marketIn"
            )
            await price_delay(
                exchange_manager=self.exchange_manager,
                pair=self.traded_pair,
                offset=-20,
            )
            await trailling_market(
                self.exchange_manager.trader,
                available_balance_percent=40,
                side="buy",
                symbol=self.traded_pair,
                tag="tryLimitOut",
                min_offset_percent=5,
                max_offset_percent=0,
                slippage_limit=50,
                postonly=True,
            )
        else:
            self.logger.info("RSI not high enough")

    async def example_script(self):
        # if one eval returns buy => market in, no stop order

        # if evaluator_RSI > 70:
        #     if evaluator_MA "sell":
        #         market(sell)

        # lazy evaluator evaluations for performances

        if is_evaluation_higher_than(TA.RSIMomentumEvaluator, 70) and not has_open_position():
            if is_evaluation_equal_to(TA.DoubleMovingAverageTrendEvaluator, "sell"):
                # scenario 1: market entry
                # yes
                # market(amount=10)
                # market(amount_percent=10)
                # market(amount_position_percent=10)
                # market(amount_available_percent=10)
                # nope
                # market(amount="10%p")
                # market(amount=position_percent(10))

                # scenario 2: try limit entry

                # traillinglimit(position=50 % p, tag=tryLimitOut, minoffset=0, maxoffset=0, slippagelimit=50, postonly=true)

                # run while slippage is < 50
                # could also be timelimit etc
                order = await traillinglimit(
                    amount_position_percent=50,
                    tag="tryLimitOut",
                    min_offset=0,
                    max_offset=0,
                    slippage_limit=50,
                    postonly=True
                )

                if is_order_canceled(tag="tryLimitOut"):
                    # market(amount=market, size=ordertag.unfilled=tryLimitIn)
                    await market(
                        amount=get_order_unfilled_amount(tag="tryLimitOut")
                    )

                # place a SL order 0.5% below the entry (closes position to 0, short or long)
                # stop(position=0, offset=0.5%p)
                await stop(
                    position=0,
                    offset_position_percent=0.5,
                )

        if has_open_position():

            # wait for evaluator RSI_OB to flash a sell signal on 30m or 1h
            # and a current long trade is open and the tagged function tp1    # got executed

            if await wait_for_evaluation_higher_than(TA.RSIMomentumEvaluator, 70):
                # take profit: market out
                await market(
                    amount_position_percent=50,
                    tag="marketOut"
                )

                await wait_for_order_to_be_filled(tag="marketOut")

                await wait_for_evaluation(TA.RSIMomentumEvaluator, 30)

                await market(
                    amount_position_percent=0,
                    tag="marketOut"
                )



    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)
        self.traded_pair = trading_mode.symbol

    async def set_final_eval(self, matrix_id: str, cryptocurrency: str, symbol: str, time_frame):
        self.cryptocurrency = cryptocurrency
        self.matrix_id = matrix_id
        await self.script()


