Places a large amount of buy and sell orders at fixed intervals, covering the order book from
very low prices to very high prices.

The range (specified in configuration) is supposed to cover all conceivable prices for as
long as the user intends to run the strategy, and this for each traded pair.
That could be from -100x to +100x
(-99% to +10000%).\nProfits will be made from price movements. 

It never "sells at a loss", but always at a profit.

Description from [Codaone/DEXBot/wiki/The-Staggered-Orders-strategy](https://github.com/Codaone/DEXBot/wiki/The-Staggered-Orders-strategy). Full documentation
available there.

In order to never sell at a loss, When using this trading mode, OctoBot never cancels any orders.

To change the staggered orders mode settings, you will have to manually cancel orders and restart the strategy.
This trading mode instantly places opposite side orders when an order is filled and checks the current orders every 
6 hours to replace any missing one.

Only works with independent bases and quotes : ETH/USDT and ADA/BTC can be activated together but ETH/USDT
and BTC/USDT are not working together for the same OctoBot instance (same quote).

Staggered modes are neutral, mountain, valley, sell slope and buy slope.
