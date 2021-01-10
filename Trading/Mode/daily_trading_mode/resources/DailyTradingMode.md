DailyTradingMode is a **low risk versatile trading mode** that reacts only the its state changes to 
a state that is different from the previous one and that is not NEUTRAL.

When triggered for a given symbol, it will cancel previously created (and unfilled) orders 
and create new ones according to its new state.

DailyTradingMode will consider every compatible strategy and average their evaluation to create
each state.
