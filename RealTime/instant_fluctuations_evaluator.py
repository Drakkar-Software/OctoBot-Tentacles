"""
CryptoBot Package

$package_description: {
    "name": "instant_fluctuations_evaluator",
    "type": "RealTime",
    "version": "1.0.0",
    "requirements": []
}
"""
import math

from config.cst import *
from evaluator.RealTime.realtime_evaluator import RealTimeTAEvaluator

"""
Idea moves are lasting approx 12min:
Check the last 12 candles and compute mean closing prices as well as mean volume with a gradually narrower interval to 
compute the strength or weakness of the move
"""
class InstantFluctuationsEvaluator(RealTimeTAEvaluator):
    def __init__(self, exchange, symbol):
        super().__init__(exchange, symbol)
        self.something_is_happening = False

        self.average_prices = {}
        self.last_price = 0

        # Volume
        self.average_volumes = {}
        self.last_volume = 0

        # Constants
        self.VOLUME_HAPPENING_THRESHOLD = 4
        self.PRICE_HAPPENING_THRESHOLD = 0.01
        self.candle_segments = [10, 8, 6, 5, 4, 3, 2, 1]

    def _refresh_data(self):
        self.update()

    def eval_impl(self):
        self.evaluate_volume_fluctuations()
        if self.something_is_happening:
            self.notify_evaluator_thread_managers(self.__class__.__name__)
            self.something_is_happening = False
        else:
            self.eval_note = START_PENDING_EVAL_NOTE

    def evaluate_volume_fluctuations(self):
        volume_trigger = 0
        price_trigger = 0

        for segment in self.candle_segments:
            # check volume fluctuation
            if self.last_volume > self.VOLUME_HAPPENING_THRESHOLD * self.average_volumes[segment]:
                volume_trigger += 1
                self.something_is_happening = True

            # check price fluctuation
            segment_average_price = self.average_prices[segment]
            if self.last_price > (1 + self.PRICE_HAPPENING_THRESHOLD) * segment_average_price:
                price_trigger += 1
                self.something_is_happening = True

            elif self.last_price < (1 - self.PRICE_HAPPENING_THRESHOLD) * segment_average_price:
                price_trigger -= 1
                self.something_is_happening = True

        average_volume_trigger = min(1, volume_trigger/len(self.candle_segments) + 0.2)
        average_price_trigger = price_trigger/len(self.candle_segments)

        if average_price_trigger < 0:
            # math.cos(1-x) between 0 and 1 starts around 0.5 and smoothly goes up to 1
            self.eval_note = -1*math.cos(1-(-1*average_price_trigger*average_volume_trigger))
        elif average_price_trigger > 0:
            self.eval_note = math.cos(1-average_price_trigger*average_volume_trigger)
        else:
            # no price info => high volume but no price move, can't say anything
            self.something_is_happening = False

    def update(self):
        candles_data = self.exchange.get_symbol_prices(self.symbol, self.specific_config[CONFIG_TIME_FRAME],
                                                       self.candle_segments[0])
        for segment in self.candle_segments:
            self.average_volumes[segment] = candles_data[PriceStrings.STR_PRICE_VOL.value][-segment:].mean()
            self.average_prices[segment] = candles_data[PriceStrings.STR_PRICE_CLOSE.value][-segment:].mean()

        self.last_volume = candles_data[PriceStrings.STR_PRICE_VOL.value].tail(1).values[0]
        self.last_price = candles_data[PriceStrings.STR_PRICE_CLOSE.value].tail(1).values[0]

