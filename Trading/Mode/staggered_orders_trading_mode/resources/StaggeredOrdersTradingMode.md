StaggeredOrdersTrading is an advanced version of the GridTradingMode. 
It places a large amount of buy and sell orders at fixed intervals, covering the order book from
very low prices to very high prices in a grid like fashion.  
The range (defined by lower & upper bounds) is supposed to cover all conceivable prices for as
long as the user intends to run the strategy, and this for each traded pair.
That could be from -100x to +100x
(-99% to +10000%).

Profits will be made from price movements within the covered price area.  
It never "sells at a loss", but always at a profit, therefore OctoBot never cancels any orders when using the Staggered Orders Trading Mode.

*Description inspired from [Codaone/DEXBot/wiki/The-Staggered-Orders-strategy](https://github.com/Codaone/DEXBot/wiki/The-Staggered-Orders-strategy). The full documentation
is available there.*

To apply changes to the Staggered Orders Trading Mode settings, you will have to manually cancel orders and restart your OctoBot.  
This trading mode instantly places opposite side orders when an order is filled.  
OctoBot also performs a check every 3 days to ensure the grid healthy state and create missing grid orders if any.

Only works with independent bases and quotes : ETH/USDT and ADA/BTC can be activated together but ETH/USDT
and BTC/USDT can't be activated together for the same OctoBot instance since they are sharing the same symbol 
(here USDT).

Staggered modes can be used to specify the way to allocate funds: modes are neutral, mountain, valley, sell slope and buy slope.
