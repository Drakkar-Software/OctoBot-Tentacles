DipAnalyserTradingMode is a trading mode adapted to **volatile markets**.

It will look for local market bottoms, weight them and buy these bottoms. It never sells except after a buy order is
filled.

When a **buy order is filled, sell orders will automatically be created at a higher price**
than this of the filled buy order. The number of sell orders created after each buy can be configured.

A higher risk will make larger buy orders.

Warning: Ensure **enough funds are available in your portfolio** for OctoBot to place the **initial buy orders**.

Sell orders are never cancelled by this strategy, therefore it is not advised to use it on
continued downtrends: funds might get locked in open sell orders.