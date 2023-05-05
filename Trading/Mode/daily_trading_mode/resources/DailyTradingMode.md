The DailyTradingMode will consider every compatible strategy and evaluator and average their evaluation to create
each update.

It will create orders when its state changes to 
a state that is different from the previous one and that is not NEUTRAL.

A LONG state will trigger a buy order. A SHORT state will trigger a sell order. 

<div class="text-center">
    <iframe width="560" height="315" src="https://www.youtube.com/embed/yTE6NE690Ds?showinfo=0&amp;rel=0" 
    title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; 
    clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</div>

### Default mode
On Default mode, the DailyTradingMode will cancel previously created open orders 
and create new ones according to its new state. 
In this mode, both buy and sell orders will be exclusively created upon strategy and evaluator signals.

### Target profits mode
On Target profits mode, the DailyTradingMode will only listen for LONG signals 
(or position-increasing signals when trading futures). When such a signal is received, it will create an entry order 
that will be followed by a take profit (and possibly a stop-loss) when filled. In this mode, only entry signals are 
defined by your strategy and evaluator configuration as take profit and stop loss targets are defined in 
the Target profits mode configuration.  
*Using the DailyTradingMode in Target profits mode is compatible with PNL history.*

### About futures trading  
The **Target profits** mode is more adapted to futures trading.
