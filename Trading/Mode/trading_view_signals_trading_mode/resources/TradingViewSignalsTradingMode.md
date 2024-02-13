TradingViewSignalsTradingMode is a trading mode configured to automate orders creation on the 
exchange of your choice by following signals from 
[TradingView](https://www.tradingview.com/) indicators or strategies.

To know more, checkout the 
<a target="_blank" rel="noopener" href="https://www.octobot.cloud/en/guides/octobot-trading-modes/tradingview-trading-mode?utm_source=octobot&utm_medium=dk&utm_campaign=regular_open_source_content&utm_content=TradingViewSignalsTradingModeDocs">
full TradingView trading mode guide</a>.

### Alert format cheatsheet
Basic signals have the following format:

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
- `ORDER_TYPE` is the type of order (LIMIT, MARKET or STOP). Overrides the `Use market orders` parameter
- `VOLUME` is the volume of the order in base asset (BTC for BTC/USDT) it can a flat amount (ex: `0.1` to trade 0.1 BTC on BTC/USD), 
a % of the total portfolio value (ex: `2%`), a % of the available holdings (ex: `12a%`), a % of available holdings associated to the current traded symbol assets (`10s%`) 
or a % of available holdings associated to all configured trading pairs assets (`10t%`). It follows the <a target="_blank" rel="noopener" href="https://www.octobot.cloud/en/guides/octobot-trading-modes/order-amount-syntax?utm_source=octobot&utm_medium=dk&utm_campaign=regular_open_source_content&utm_content=TradingViewSignalsTradingModeDocs">
orders amount syntax</a>.
- `PRICE` is the price of the limit order in quote asset (USDT for BTC/USDT)
- `STOP_PRICE` is the price of the stop order to create. When increasing the position or buying in spot trading, the stop loss will automatically be created once the initial order is filled. When decreasing the position (or selling in spot) using a LIMIT `ORDER_TYPE`, the stop loss will be created instantly. *Orders crated this way are compatible with PNL history.*
- `TAKE_PROFIT_PRICE` is the price of the take profit order to create. When increasing the position or buying in spot trading, the take profit will automatically be created once the initial order is filled. When decreasing the position (or selling in spot) using a LIMIT `ORDER_TYPE`, the take profit will be created instantly. *Orders crated this way are compatible with PNL history.*
- `REDUCE_ONLY` when true, only reduce the current position (avoid accidental short position opening when reducing a long position). **Only used in futures trading**. Default is false
- `TAG` is an identifier to give to the orders to create.

When not specified, orders volume and price are automatically computed based on the current 
asset price and holdings.

Orders can be cancelled using the following format:
``` bash
EXCHANGE=binance
SYMBOL=ETHBTC
SIGNAL=CANCEL
```

Additional cancel parameters:
- `PARAM_SIDE` is the side of the orders to cancel, it can be `buy` or `sell` to only cancel buy or sell orders.
  - `TAG` is the tag of the order(s) to cancel. It can be used to only cancel orders that have been created with a specific tag.

Find the full TradingView alerts format on
<a target="_blank" rel="noopener" href="https://www.octobot.cloud/en/guides/octobot-interfaces/tradingview/alert-format?utm_source=octobot&utm_medium=dk&utm_campaign=regular_open_source_content&utm_content=TradingViewSignalsTradingModeDocs">
the TradingView alerts format guide</a>.

