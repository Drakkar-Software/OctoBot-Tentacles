TradingViewSignalsTradingMode is a trading mode configured to react on signals from [tradingview.com](https://www.tradingview.com/).

It takes signals with the following format:

```
EXCHANGE=BINANCE
SYMBOL=BTCUSD
SIGNAL=BUY
```

Additional order details can be added to the signal but are optional:

```
ORDER_TYPE=LIMIT
VOLUME=0.01
PRICE=42000
STOP_PRICE=25000
TAKE_PROFIT_PRICE=50000
REDUCE_ONLY=true
```

Where:
- `ORDER_TYPE` is the type of order (LIMIT or MARKET). Overrides the `Use market orders` parameter
- `VOLUME` is the volume of the order in base asset (BTC for BTC/USDT) it can a flat amount (ex: `0.1` to trade 0.1 BTC on BTC/USD), 
a % of the total portfolio value (ex: `2%`), a % of the available holdings (ex: `12a%`), a % of available holdings associated to the current traded symbol assets (`10s%`) 
or a % of available holdings associated to all configured trading pairs assets (`10t%`)
- `PRICE` is the price of the limit order in quote asset (USDT for BTC/USDT)
- `STOP_PRICE` is the price of the stop order to create. When increasing the position or buying in spot trading, the stop loss will automatically be created once the initial order is filled. When decreasing the position (or selling in spot) using a LIMIT `ORDER_TYPE`, the stop loss will be created instantly. *Orders crated this way are compatible with PNL history.*
- `TAKE_PROFIT_PRICE` is the price of the take profit order to create. When increasing the position or buying in spot trading, the take profit will automatically be created once the initial order is filled. When decreasing the position (or selling in spot) using a LIMIT `ORDER_TYPE`, the take profit will be created instantly. *Orders crated this way are compatible with PNL history.*
- `REDUCE_ONLY` when true, only reduce the current position (avoid accidental short position opening when reducing a long position). **Only used in futures trading**. Default is false

When not specified, orders volume and price are automatically computed based on the current 
asset price and holdings.

It also takes cancel order signal with the following format:
``` bash
EXCHANGE=binance
SYMBOL=ETHBTC
ORDER_TYPE=CANCEL
```

Additional cancel parameters are available:
- `PARAM_SIDE` is the side of the orders to cancel, it can be `buy` or `sell` to only cancel buy or sell orders.


Additional data in the Trading View signal data will not be processed.

This Trading mode is not using any strategy or evaluator and won't create stop losses.
