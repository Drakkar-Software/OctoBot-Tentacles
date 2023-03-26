DailyTradingMode reacts only the its state changes to 
a state that is different from the previous one and that is not NEUTRAL.

<div class="text-center">
    <iframe width="560" height="315" src="https://www.youtube.com/embed/yTE6NE690Ds?showinfo=0&amp;rel=0" 
    title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; 
    clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</div>

When triggered for a given symbol, it will cancel previously created (and unfilled) orders 
and create new ones according to its new state.

DailyTradingMode will consider every compatible strategy and average their evaluation to create
each state.

**About futures trading**  
DailyTradingMode can be used to trades futures however it has originally been 
with spot trading in mind. Other trading modes sur as the DipAnalyserTradingMode
are more suitable to trades futures unless the current evaluators and trading mode setup
are specifically designed for futures trading. This is **not** the case for the default 
configuration of this trading mode and evaluators.
