DipAnalyserTradingMode is a trading mode adapted to **volatile markets**.

It will look for local market bottoms, weight them and buy these bottoms. It never sells except after a buy order is
filled.

When a **buy order is filled, sell orders will automatically be created at a higher price**
than this of the filled buy order. The number of sell orders created after each buy can be configured.

A higher risk configuration will make larger buy orders when order size is not configured.

Warning: Ensure **enough funds are available in your portfolio** for OctoBot to place the **initial buy orders**.

Sell orders are never cancelled by this strategy unless stop losses are enabled, 
therefore it is not advised to use it on
continued downtrends without using stop losses: funds might get locked in open sell orders.

Limit buy orders might be automatically cancelled and replaced when a 
better buy opportunity is identified.

_This trading mode supports PNL history._
