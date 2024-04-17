The Index trading mode splits and maintains your portfolio distributed between the traded currencies. It enables 
to maintain a crypto index based on your choice of coins.

To know more, checkout the 
<a target="_blank" rel="noopener" href="https://www.octobot.cloud/en/guides/octobot-trading-modes/index-trading-mode?utm_source=octobot&utm_medium=dk&utm_campaign=regular_open_source_content&utm_content=IndexTradingModeDocs">
full Index trading mode guide</a>.

### Content of the Index
The Index is defined by the selected traded pairs against your reference market in the 
profile configuration section.  
Example:
- Your reference market is USDT
- Your traded pairs are BTC/USDT, ETH/USDT, SOL/USDT, ADA/USDT
Then your index will be made of 25% BTC, 25% ETH, 25% SOL and 25% ADA. Each coin's holding % will be computed 
against USDT and checked on a regular basis.

When starting the Index trading mode with a new configuration, or if your current portfolio doesn't reflect
the target of the index, your portfolio will automatically be adapted to reproduce the index at the best
accuracy possible.

### Index rebalance
An Index rebalance is the event when OctoBot is sending orders to the exchange to adapt the content of
your portfolio in order to reproduce the configuration of your Index.  
Once your Index trading mode has started, OctoBot will maintain the index content by 
automatically checking the content of your portfolio of a regular basis and will trigger a rebalance
if necessary.

Your portfolio content is checked every configured `Trigger period` days. If during an index check, 
your OctoBot detects that your portfolio content doesn't comply with your index configuration, it will
trigger a rebalance.

### Rebalance cap
When checking for rebalance, the Index trading mode also uses your `Rebalance cap` configuration before
considering your portfolio out of synch with your index configuration.
The Rebalance cap is an allowed percent of allocation that will avoid triggering a rebalance as long as any
coin holding is still within the ideal holding % plus or minus the rebalance cap.  
Example:
An index on 3 coins with a 33.33% target on each coin and a Rebalance cap of 5% will trigger a rebalance if 
the holding if any of those 3 coins takes more than 38.33% or less than 28.33% of the portfolio

### Minimum funds
To use the Index Trading Mode, the minimum required funds are twice the minimum exchange order amount for every 
traded coin. This means that when trading 3 coins on Binance, at least 3 times $5 x2, which is $30 is required.  
Please note that this is the bare minimum, it's better to have at least twice this amount. If the minimum is reached, 
the Index Trading Mode will stop updating its portfolio according to the index until the value of the portfolio 
raises back above the required minimum.


Warning: When your index Rebalance cap is higher or equal to the target holdings of each coin, no rebalance 
will be triggered if your holdings of a coin become very low, rebalances will only be triggered when holdings are 
getting to high.  
Example:
An index on 10 coins uses a 10% target on each coin. Using a Rebalance cap of 11% will only trigger a 
rebalance if any of those 3 coins takes more than 21% of the portfolio (the other side: 10-11 = -1% is incoherent). 

Please note that if the % held of a coin is 0%, then a rebalance will always trigger, ignoring the Rebalance cap.


