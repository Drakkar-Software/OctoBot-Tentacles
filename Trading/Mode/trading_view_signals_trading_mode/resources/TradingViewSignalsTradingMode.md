TradingViewSignalsTradingMode is a trading mode configured to react on signals from [tradingview.com](https://www.tradingview.com/).

It takes signals with the following format:

```
EXCHANGE=BINANCE
SYMBOL=BTCUSD
SIGNAL=SELL
```

Additional order details can be added to the signal but are optional:

```
ORDER_TYPE=LIMIT
VOLUME=0.01
PRICE=42000
STOP_PRICE=25000
REDUCE_ONLY=true
```

Where:
- `ORDER_TYPE` is the type of order (LIMIT or MARKET). Overrides the `Use market orders` parameter
- `VOLUME` is the volume of the order in base asset (BTC for BTC/USDT) it can a flat amount (ex: `0.1` to trade 0.1 BTC on BTC/USD), a % of the total portfolio value (ex: `2%`) or a % of the available holdings (ex: `12a%`)
- `PRICE` is the price of the limit order in quote asset (USDT for BTC/USDT)
- `STOP_PRICE` is the price of the stop order to create (also requires the `PRICE` to be set to link it with a limit order)
- `REDUCE_ONLY` when true, only reduce the current position (avoid accidental short position opening when reducing a long position). ****Only used in futures trading. Default is false

When not specified, orders volume and price are automatically computed based on the current 
asset price and holdings.

Additional data in the Trading View signal data will not be processed.

This Trading mode is not using any strategy or evaluator and won't create stop losses.
