# cython: language_level=3
#  Drakkar-Software OctoBot-Trading
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
#  Lesser General License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.
from octobot_trading.producers.abstract_mode_producer cimport AbstractTradingModeProducer

from octobot_trading.consumers.abstract_mode_consumer cimport AbstractTradingModeConsumer

from octobot_trading.modes.abstract_trading_mode cimport AbstractTradingMode


cdef class DailyTradingMode(AbstractTradingMode):
    pass


cdef class DailyTradingModeConsumer(AbstractTradingModeConsumer):
    cdef public float MAX_SUM_RESULT

    cdef public float STOP_LOSS_ORDER_MAX_PERCENT
    cdef public float STOP_LOSS_ORDER_MIN_PERCENT
    cdef public float STOP_LOSS_ORDER_ATTENUATION

    cdef public float QUANTITY_MIN_PERCENT
    cdef public float QUANTITY_MAX_PERCENT
    cdef public float QUANTITY_ATTENUATION

    cdef public float QUANTITY_MARKET_MIN_PERCENT
    cdef public float QUANTITY_MARKET_MAX_PERCENT
    cdef public float QUANTITY_BUY_MARKET_ATTENUATION
    cdef public float QUANTITY_MARKET_ATTENUATION

    cdef public float BUY_LIMIT_ORDER_MAX_PERCENT
    cdef public float BUY_LIMIT_ORDER_MIN_PERCENT
    cdef public float SELL_LIMIT_ORDER_MIN_PERCENT
    cdef public float SELL_LIMIT_ORDER_MAX_PERCENT
    cdef public float LIMIT_ORDER_ATTENUATION

    cdef public float QUANTITY_RISK_WEIGHT
    cdef public float MAX_QUANTITY_RATIO
    cdef public float MIN_QUANTITY_RATIO
    cdef public float DELTA_RATIO

    cdef public float SELL_MULTIPLIER
    cdef public float FULL_SELL_MIN_RATIO

    cpdef __get_limit_price_from_risk(self, object eval_note)
    cpdef __get_stop_price_from_risk(self)
    cpdef __get_buy_limit_quantity_from_risk(self, object eval_note, float quantity, str quote)
    cpdef __get_market_quantity_from_risk(self, object eval_note, float quantity, str quote, bint selling=*)

cdef class DailyTradingModeProducer(AbstractTradingModeProducer):
    cdef public object state

    cdef public float VERY_LONG_THRESHOLD
    cdef public float LONG_THRESHOLD
    cdef public float NEUTRAL_THRESHOLD
    cdef public float SHORT_THRESHOLD
    cdef public float RISK_THRESHOLD

    cpdef float __get_delta_risk(self)
