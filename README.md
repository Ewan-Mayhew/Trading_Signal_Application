This is a python powered day trading signal GUI.

Stocks get ranked based on a number of technical indicators, and a signal is generated. If a stock is in the portfolio, and a sell signal arises, the sell signal is displayed in the right hand display to make getting out of positions obvious.

![image](https://github.com/user-attachments/assets/cc4bb4a3-2eb6-450e-bf1f-5f8444aecc85)

Over the coming weeks I am going to build in live portfolio tracking with T212, and also build a longer term CAPM alpha ranking strategy to support my intraday trading activities.

To run this, populate a folder within a 'quant trading' directory (or name of your choice), with a 'data' directory. Within the data directory store csv files with the name of the stocks that you want the algorithm to produce signals for. This allows for integration between backtesting and live trading.

For example:

![image](https://github.com/user-attachments/assets/bf9c2b02-44f3-41c8-b52f-448c8653e431)

After that just run the code and a GUI interface will pop up which can be used (at the moment buy and sell signals are not sent to an exchange, and are just logged in the 'portfolio' dicitonary). Trades need to be manually inputted with your brokerage.
