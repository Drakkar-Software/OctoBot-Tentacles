Places a fixed amount of buy and sell orders at fixed intervals to profit from any market move. When an order is filled,
a mirror order is instantly created and generates profit when completed.

#### Default configuration
When left unspecified for a trading pair, the grid will be initialized with a spread
of 4% of the current price and an increment of 1% and a maximum of 10 buy and sell orders.

When enough funds are available, the default configuration will result in:
- 10 buy order covering 98% to 89% of the current price
- 10 sell orders going from 102% to 111% of the current price 

#### Trading pair configuration
You can customize the grid for each pair.

For each pair to trade,  enter the interval between each order, the number of initial orders to 
create and you are ready to go.

#### Profits
Profits will be made from price movements within the covered price area.  
It never "sells at a loss", but always at a profit, therefore OctoBot never cancels any orders when using the Grid Trading Mode.

To apply changes to the Grid Trading Mode settings, you will have to manually cancel orders and restart your OctoBot.  
This trading mode instantly places opposite side orders when an order is filled.

This trading mode has been made possible thanks to the support of PKBO & Calusari.
