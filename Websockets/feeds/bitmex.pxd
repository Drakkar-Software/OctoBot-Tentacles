# cython: language_level=3
#  Drakkar-Software OctoBot-Websockets
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
from octobot_websockets.feeds.feed cimport Feed

cdef class Bitmex(Feed):
    cdef dict ticker_constructors
    cdef dict candle_constructors

    cdef int partial_received

    cdef dict order_id # TODO remove
    cdef dict l3_book # TODO remove

    cpdef void _reset(self)

    # position
    #     {
    #        "table":"position",
    #        "action":"update",
    #        "data":[
    #           {
    #              "account":2,
    #              "symbol":"XBTUSD",
    #              "currency":"XBt",
    #              "deleveragePercentile":null,
    #              "rebalancedPnl":-2171150,
    #              "prevRealisedPnl":2172153,
    #              "execSellQty":2001,
    #              "execSellCost":172394155,
    #              "execQty":0,
    #              "execCost":-2259128,
    #              "execComm":87978,
    #              "currentTimestamp":"2017-04-04T22:16:38.547Z",
    #              "currentQty":0,
    #              "currentCost":-2259128,
    #              "currentComm":87978,
    #              "realisedCost":-2259128,
    #              "unrealisedCost":0,
    #              "grossExecCost":0,
    #              "isOpen":false,
    #              "markPrice":null,
    #              "markValue":0,
    #              "riskValue":0,
    #              "homeNotional":0,
    #              "foreignNotional":0,
    #              "posState":"",
    #              "posCost":0,
    #              "posCost2":0,
    #              "posInit":0,
    #              "posComm":0,
    #              "posMargin":0,
    #              "posMaint":0,
    #              "maintMargin":0,
    #              "realisedGrossPnl":2259128,
    #              "realisedPnl":2171150,
    #              "unrealisedGrossPnl":0,
    #              "unrealisedPnl":0,
    #              "unrealisedPnlPcnt":0,
    #              "unrealisedRoePcnt":0,
    #              "simpleQty":0,
    #              "simpleCost":0,
    #              "simpleValue":0,
    #              "simplePnl":0,
    #              "simplePnlPcnt":0,
    #              "avgCostPrice":null,
    #              "avgEntryPrice":null,
    #              "breakEvenPrice":null,
    #              "marginCallPrice":null,
    #              "liquidationPrice":null,
    #              "bankruptPrice":null,
    #              "timestamp":"2017-04-04T22:16:38.547Z"
    #           }
    #        ]
    #     }

    # order
    # {
    #    "table":"execution",
    #    "action":"insert",
    #    "data":[
    #       {
    #          "execID":"0193e879-cb6f-2891-d099-2c4eb40fee21",
    #          "orderID":"00000000-0000-0000-0000-000000000000",
    #          "clOrdID":"",
    #          "clOrdLinkID":"",
    #          "account":2,
    #          "symbol":"XBTUSD",
    #          "side":"Sell",
    #          "lastQty":1,
    #          "lastPx":1134.37,
    #          "underlyingLastPx":null,
    #          "lastMkt":"XBME",
    #          "lastLiquidityInd":"RemovedLiquidity",
    #          "simpleOrderQty":null,
    #          "orderQty":1,
    #          "price":1134.37,
    #          "displayQty":null,
    #          "stopPx":null,
    #          "pegOffsetValue":null,
    #          "pegPriceType":"",
    #          "currency":"USD",
    #          "settlCurrency":"XBt",
    #          "execType":"Trade",
    #          "ordType":"Limit",
    #          "timeInForce":"ImmediateOrCancel",
    #          "execInst":"",
    #          "contingencyType":"",
    #          "exDestination":"XBME",
    #          "ordStatus":"Filled",
    #          "triggered":"",
    #          "workingIndicator":false,
    #          "ordRejReason":"",
    #          "simpleLeavesQty":0,
    #          "leavesQty":0,
    #          "simpleCumQty":0.001,
    #          "cumQty":1,
    #          "avgPx":1134.37,
    #          "commission":0.00075,
    #          "tradePublishIndicator":"DoNotPublishTrade",
    #          "multiLegReportingType":"SingleSecurity",
    #          "text":"Liquidation",
    #          "trdMatchID":"7f4ab7f6-0006-3234-76f4-ae1385aad00f",
    #          "execCost":88155,
    #          "execComm":66,
    #          "homeNotional":-0.00088155,
    #          "foreignNotional":1,
    #          "transactTime":"2017-04-04T22:07:46.035Z",
    #          "timestamp":"2017-04-04T22:07:46.035Z"
    #       }
    #    ]
    # }

    # trade
    # trade msg example
    #
    # {
    #     'timestamp': '2018-05-19T12:25:26.632Z',
    #     'symbol': 'XBTUSD',
    #     'side': 'Buy',
    #     'size': 40,
    #     'price': 8335,
    #     'tickDirection': 'PlusTick',
    #     'trdMatchID': '5f4ecd49-f87f-41c0-06e3-4a9405b9cdde',
    #     'grossValue': 479920,
    #     'homeNotional': Decimal('0.0047992'),
    #     'foreignNotional': 40
    # }

    # funding
    # {'table': 'funding',
    #  'action': 'partial',
    #  'keys': ['timestamp', 'symbol'],
    #  'types': {
    #      'timestamp': 'timestamp',
    #      'symbol': 'symbol',
    #      'fundingInterval': 'timespan',
    #      'fundingRate': 'float',
    #      'fundingRateDaily': 'float'
    #     },
    #  'foreignKeys': {
    #      'symbol': 'instrument'
    #     },
    #  'attributes': {
    #      'timestamp': 'sorted',
    #      'symbol': 'grouped'
    #     },
    #  'filter': {'symbol': 'XBTUSD'},
    #  'data': [{
    #      'timestamp': '2018-08-21T20:00:00.000Z',
    #      'symbol': 'XBTUSD',
    #      'fundingInterval': '2000-01-01T08:00:00.000Z',
    #      'fundingRate': Decimal('-0.000561'),
    #      'fundingRateDaily': Decimal('-0.001683')
    #     }]
    # }
