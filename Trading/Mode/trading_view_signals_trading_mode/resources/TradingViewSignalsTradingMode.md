TradingViewSignalsTradingMode is a trading mode configured to react on signals from [tradingview.com](https://www.tradingview.com/).

It takes signals with the following format:

```
EXCHANGE=BINANCE
SYMBOL=BTCUSD
SIGNAL=SELL
```

Additional data in the Trading View signal data will not be processed.

This Trading mode is not using any strategy or evaluator and won't create stop losses.
