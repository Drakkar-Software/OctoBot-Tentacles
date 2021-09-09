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
```

Where:
- `ORDER_TYPE` is the type of order (LIMIT or MARKET). Overrides the `Use market orders` parameter
- `VOLUME` is the volume of the order in quote asset (USDT for BTC/USDT)
- `PRICE` is the price of the limit order in base asset (BTC for BTC/USDT)

When not specified, orders volume and price are automatically computed based on the current 
asset price and holdings.

Additional data in the Trading View signal data will not be processed.

This Trading mode is not using any strategy or evaluator and won't create stop losses.
