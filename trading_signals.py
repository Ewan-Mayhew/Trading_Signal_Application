import os
import yfinance as yf
import pandas as pd
import time
import threading
import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime
import pytz  # For timezone conversion

# Global variables to track signals, portfolio, and profits
signals_list = []  # List to store signals
portfolio = {}     # Dictionary to track portfolio: symbol -> {'buy_price': price, 'current_price': price}
already_bought = set()  # To keep track of stocks already bought
realized_profits = 0  # Tally of realized profits

# Define the volume threshold for "high volume" stocks (adjust as needed)
VOLUME_THRESHOLD = 0  # Example: only include stocks with volume > 100,000

# Function to get stock symbols from the CSV files in the data directory
def get_stock_symbols_from_directory(data_dir):
    stock_symbols = []
    for filename in os.listdir(data_dir):
        if filename.endswith(".csv"):
            symbol = filename.split('.')[0]  # Extract the stock symbol from the filename
            stock_symbols.append(symbol)
    return stock_symbols

# Function to convert UTC to local time
def convert_utc_to_local(utc_timestamp):
    # Directly convert the timestamp to the local timezone if it's already tz-aware
    local_time = utc_timestamp.tz_convert('Europe/London')  # Change to your local timezone
    return local_time.strftime('%Y-%m-%d %H:%M:%S')

# Function to calculate Bollinger Bands, RSI, and shorter MACD
def calculate_indicators(data, period=60, dev_factor=2, macd_short=13, macd_long=26, macd_signal=4):
    # Bollinger Bands
    data['SMA'] = data['Close'].rolling(window=period).mean()
    data['STD'] = data['Close'].rolling(window=period).std()
    data['Upper Band'] = data['SMA'] + (dev_factor * data['STD'])
    data['Lower Band'] = data['SMA'] - (dev_factor * data['STD'])

    # Relative Strength Index (RSI)
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))

    # MACD Line: Difference between the 6-period and 13-period EMA (shorter MACD time frame)
    data['MACD Line'] = data['Close'].ewm(span=macd_short, adjust=False).mean() - data['Close'].ewm(span=macd_long, adjust=False).mean()

    # Signal Line: 4-period EMA of the MACD Line (shorter signal line)
    data['Signal Line'] = data['MACD Line'].ewm(span=macd_signal, adjust=False).mean()

    # MACD Histogram: Difference between MACD Line and Signal Line
    data['MACD Histogram'] = data['MACD Line'] - data['Signal Line']

# Function to determine the strength of the signal
def determine_signal_strength(criteria, signal_type):
    score = sum(criteria)  # Sum up the criteria that agree

    if signal_type == "buy":
        if score == 3:
            return "STRONG BUY"
        elif score == 2:
            return "MEDIUM BUY"
        else:
            return "LOW BUY"
    elif signal_type == "sell":
        if score == 3:
            return "STRONG SELL"
        elif score == 2:
            return "MEDIUM SELL"
        else:
            return "LOW SELL"
    return "NO SIGNAL"

# Function to provide a suggestion based on indicator value
def get_indicator_suggestion(indicator_type, value, lower_band=None, upper_band=None):
    if indicator_type == "RSI":
        if value < 30:
            return f"{value:.2f} (Buy)"
        elif value > 70:
            return f"{value:.2f} (Sell)"
        else:
            return f"{value:.2f} (Neutral)"
    elif indicator_type == "MACD":
        if value > 0.05:
            return f"{value:.2f} (Buy)"
        elif value < -0.05:
            return f"{value:.2f} (Sell)"
        else:
            return f"{value:.2f} (Neutral)"
    elif indicator_type == "Bollinger":
        if value < lower_band:
            return f"{value:.2f} (Buy)"
        elif value > upper_band:
            return f"{value:.2f} (Sell)"
        else:
            return f"{value:.2f} (Neutral)"
    return f"{value:.2f}"

# Function to handle buy and sell signals based on Bollinger Bands, RSI, and MACD
def generate_signals(data, symbol):
    latest = data.iloc[-1]
    upper_band = latest['Upper Band']
    lower_band = latest['Lower Band']
    middle_band = latest['SMA']
    price = latest['Close']
    volume = latest['Volume']  # Get the volume of trades
    rsi = latest['RSI']
    macd_line = latest['MACD Line']
    signal_line = latest['Signal Line']
    timestamp = latest.name  # Date and time of the latest data point

    # Convert timestamp to local timezone
    timestamp = convert_utc_to_local(timestamp)

    # Check if the stock meets the high volume threshold
    if volume < VOLUME_THRESHOLD or symbol in already_bought:
        return  # Skip stocks with low trading volume or already bought

    # Scoring based on Bollinger Bands
    if price < lower_band:
        bollinger_score = +3  # Strong buy signal
    elif price > upper_band:
        bollinger_score = -3  # Strong sell signal
    else:
        bollinger_score = 0  # Neutral

    # Scoring based on RSI
    if rsi < 30:
        rsi_score = +2  # Buy signal
    elif rsi > 70:
        rsi_score = -2  # Sell signal
    else:
        rsi_score = 0  # Neutral

    # Scoring based on MACD
    if macd_line - signal_line > 0.05:
        macd_score = +1  # Buy signal
    elif macd_line - signal_line < -0.05:
        macd_score = -1  # Sell signal
    else:
        macd_score = 0  # Neutral

    # Total score to determine overall signal strength
    total_score = bollinger_score + rsi_score + macd_score

    # Determine final signal strength based on total score
    if total_score > 0:
        if total_score >= 5:
            final_signal = "STRONG BUY"
        elif total_score >= 3:
            final_signal = "MEDIUM BUY"
        else:
            final_signal = "LOW BUY"
    elif total_score < 0:
        if total_score <= -5:
            final_signal = "STRONG SELL"
        elif total_score <= -3:
            final_signal = "MEDIUM SELL"
        else:
            final_signal = "LOW SELL"
    else:
        final_signal = "NEUTRAL"

    # Indicator suggestions
    rsi_suggestion = get_indicator_suggestion("RSI", rsi)
    macd_suggestion = get_indicator_suggestion("MACD", macd_line)
    bollinger_suggestion = get_indicator_suggestion("Bollinger", price, lower_band, upper_band)

    # Append all signals including neutral
    signal = {
        "type": final_signal,
        "symbol": symbol,
        "price": price,
        "volume": volume,
        "upper_band": upper_band,
        "middle_band": middle_band,
        "lower_band": lower_band,
        "rsi": rsi,
        "macd_line": macd_line,
        "signal_line": signal_line,
        "timestamp": timestamp,
        "rsi_suggestion": rsi_suggestion,
        "macd_suggestion": macd_suggestion,
        "bollinger_suggestion": bollinger_suggestion,
        "total_score": total_score
    }
    signals_list.append(signal)

# Function to stream minute-by-minute data and check for buy/sell signals
def stream_data(symbols, interval='1m'):
    while True:
        for symbol in symbols:
            try:
                # Download minute data for the last day without showing the progress bar
                data = yf.download(tickers=symbol, period="1d", interval=interval, progress=False)

                if not data.empty:
                    # Calculate Bollinger Bands, RSI (momentum indicator), and MACD
                    calculate_indicators(data)

                    # Generate Buy/Sell signals based on MACD and other indicators
                    generate_signals(data, symbol)

            except Exception as e:
                # Print error to track missing data or issues
                print(f"Error processing {symbol}: {e}")

        # Wait 60 seconds before fetching new data
        time.sleep(1)  # Adjusted to every minute

# Function to update the Buy signals and Sell signals in the GUI
def update_gui_signals(buy_frame, sell_frame, portfolio_frame, filter_strong, filter_medium, filter_low, time_label, profit_label):
    def refresh_signals():
        buy_frame.delete(1.0, tk.END)  # Clear buy signals text
        sell_frame.delete(1.0, tk.END)  # Clear sell signals text
        portfolio_frame.delete(1.0, tk.END)  # Clear portfolio text

        # Filter and sort buy signals by strength and volume
        buy_signals = [s for s in signals_list if "BUY" in s["type"] and s["symbol"] not in already_bought]
        buy_signals.sort(key=lambda x: (-1 if "STRONG" in x["type"] else 1, -x["volume"]))  # Strong first, higher volume first

        # Update Buy signals based on filter
        for signal in buy_signals:
            symbol = signal["symbol"]
            price = signal["price"]
            volume = signal["volume"]
            timestamp = signal["timestamp"]

            # Apply filters (only display selected types)
            if signal["type"] == "STRONG BUY" and not filter_strong.get():
                continue
            if signal["type"] == "MEDIUM BUY" and not filter_medium.get():
                continue
            if signal["type"] == "LOW BUY" and not filter_low.get():
                continue

            # Add Buy signal with indicator details and button to add to portfolio
            buy_frame.insert(tk.END, f"{signal['type']} for {symbol} at {price:.2f} (Vol: {volume})\n")
            buy_frame.insert(tk.END, f"RSI: {signal['rsi_suggestion']}, MACD: {signal['macd_suggestion']}, Bollinger Bands: {signal['bollinger_suggestion']}\n")
            buy_frame.insert(tk.END, f"Timestamp: {timestamp}\n\n")

            buy_button = tk.Button(buy_frame, text="Buy", bg="green", fg="white", command=lambda s=symbol, p=price: add_to_portfolio(s, p))
            buy_frame.window_create(tk.END, window=buy_button)
            buy_frame.insert(tk.END, "\n\n")

        # Filter and sort sell signals
        sell_signals = [s for s in signals_list if "SELL" in s["type"] and s["symbol"] in portfolio]
        sell_signals.sort(key=lambda x: (-1 if "STRONG" in x["type"] else 1, -x["volume"]))  # Strong first, higher volume first

        # Update Sell signals
        for signal in sell_signals:
            symbol = signal["symbol"]
            price = signal["price"]
            volume = signal["volume"]
            timestamp = signal["timestamp"]

            # Apply filters (only display selected types)
            if signal["type"] == "STRONG SELL" and not filter_strong.get():
                continue
            if signal["type"] == "MEDIUM SELL" and not filter_medium.get():
                continue
            if signal["type"] == "LOW SELL" and not filter_low.get():
                continue

            # Add Sell signal with indicator details and button to remove from portfolio
            sell_frame.insert(tk.END, f"{signal['type']} for {symbol} at {price:.2f} (Vol: {volume})\n")
            sell_frame.insert(tk.END, f"RSI: {signal['rsi_suggestion']}, MACD: {signal['macd_suggestion']}, Bollinger Bands: {signal['bollinger_suggestion']}\n")
            sell_frame.insert(tk.END, f"Timestamp: {timestamp}\n\n")

            sell_button = tk.Button(sell_frame, text="Sell", bg="red", fg="white", command=lambda s=symbol: remove_from_portfolio(s))
            sell_frame.window_create(tk.END, window=sell_button)
            sell_frame.insert(tk.END, "\n\n")

        # Display the current portfolio and realized profit tally
        portfolio_frame.insert(tk.END, "Current Portfolio:\n")
        for symbol, details in portfolio.items():
            current_price = details['current_price']
            buy_price = details['buy_price']
            portfolio_frame.insert(tk.END, f"{symbol} - Buy Price: {buy_price:.2f}, Current Price: {current_price:.2f}\n")
            sell_button = tk.Button(portfolio_frame, text="Sell", bg="red", fg="white", command=lambda s=symbol: sell_from_portfolio(s))
            portfolio_frame.window_create(tk.END, window=sell_button)
            portfolio_frame.insert(tk.END, "\n\n")

        # Update realized profits
        profit_label.config(text=f"Realized Profits: {realized_profits:.2f}")

        # Update refresh time
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        time_label.config(text=f"Last Refresh: {current_time}")

        # Call this function again after 1000ms (1 second)
        buy_frame.after(1000, refresh_signals)

    refresh_signals()  # Call the refresh function for the first time

# Function to add a stock to the portfolio
def add_to_portfolio(symbol, price):
    portfolio[symbol] = {'buy_price': price, 'current_price': price}  # Add stock to portfolio
    already_bought.add(symbol)  # Mark the stock as bought
    print(f"Added {symbol} to portfolio at {price:.2f}")

# Function to sell a stock from the portfolio and calculate realized profit
def sell_from_portfolio(symbol):
    global realized_profits
    if symbol in portfolio:
        buy_price = portfolio[symbol]['buy_price']
        current_price = portfolio[symbol]['current_price']
        profit = current_price - buy_price  # Calculate profit
        realized_profits += profit  # Update realized profits
        del portfolio[symbol]  # Remove stock from portfolio
        already_bought.remove(symbol)  # Remove from already bought set
        print(f"Sold {symbol}, Profit: {profit:.2f}")

# Function to remove a stock from the portfolio (used by sell signals)
def remove_from_portfolio(symbol):
    if symbol in portfolio:
        del portfolio[symbol]  # Remove stock from portfolio
        already_bought.remove(symbol)
        print(f"Sold {symbol}")

# Function to update current price of stocks in portfolio
def update_portfolio_prices():
    while True:
        for symbol in portfolio:
            try:
                # Get the current price from Yahoo Finance
                current_price = yf.download(tickers=symbol, period="1d", interval="1m", progress=False)['Close'].iloc[-1]
                portfolio[symbol]['current_price'] = current_price
            except Exception as e:
                print(f"Error updating {symbol}: {e}")
        time.sleep(1)  # Update prices every minute

# Function to clear the signals list
def clear_signals():
    signals_list.clear()
    print("Signals list cleared.")

# Function to create and start the Tkinter GUI
def start_gui():
    root = tk.Tk()
    root.title("Stock Signals")

    # Create frames for Buy and Sell signals
    buy_frame = tk.Text(root, wrap=tk.WORD, width=50, height=30, font=("Helvetica", 10))
    buy_frame.pack(side=tk.LEFT, padx=10, pady=10)

    sell_frame = tk.Text(root, wrap=tk.WORD, width=50, height=30, font=("Helvetica", 10))
    sell_frame.pack(side=tk.RIGHT, padx=10, pady=10)

    # Create frame for Current Portfolio
    portfolio_frame = tk.Text(root, wrap=tk.WORD, width=100, height=10, font=("Helvetica", 10))
    portfolio_frame.pack(side=tk.BOTTOM, padx=10, pady=10)

    # Create middle label for refresh time
    time_label = tk.Label(root, text="", font=("Helvetica", 12))
    time_label.pack(side=tk.TOP, pady=5)

    # Create profit label for realized profits
    profit_label = tk.Label(root, text=f"Realized Profits: {realized_profits:.2f}", font=("Helvetica", 12))
    profit_label.pack(side=tk.TOP, pady=5)

    # Create filter checkboxes for signals
    filter_frame = tk.Frame(root)
    filter_frame.pack(side=tk.TOP)

    filter_strong = tk.BooleanVar(value=True)
    filter_medium = tk.BooleanVar(value=True)
    filter_low = tk.BooleanVar(value=True)  # Now showing low signals by default

    tk.Checkbutton(filter_frame, text="Show Strong Signals", variable=filter_strong).pack(side=tk.LEFT)
    tk.Checkbutton(filter_frame, text="Show Medium Signals", variable=filter_medium).pack(side=tk.LEFT)
    tk.Checkbutton(filter_frame, text="Show Low Signals", variable=filter_low).pack(side=tk.LEFT)

    # Add Clear Signals Button
    clear_button = tk.Button(root, text="Clear Signals", bg="red", fg="white", command=clear_signals)
    clear_button.pack(side=tk.TOP, pady=10)

    # Start the signal updating thread
    gui_thread = threading.Thread(target=update_gui_signals, args=(buy_frame, sell_frame, portfolio_frame, filter_strong, filter_medium, filter_low, time_label, profit_label))
    gui_thread.daemon = True
    gui_thread.start()

    # Start the portfolio price updating thread
    portfolio_thread = threading.Thread(target=update_portfolio_prices)
    portfolio_thread.daemon = True
    portfolio_thread.start()

    # Start the Tkinter main loop
    root.mainloop()

# Main script
if __name__ == "__main__":
    # Directory where your CSV files are stored (adjust this to your actual directory)
    data_dir = r"C:\Quant Trading\data"  # Replace with your actual directory path

    # Get the list of stock symbols from the directory
    symbols = get_stock_symbols_from_directory(data_dir)

    if symbols:
        # Start the streaming data thread
        data_thread = threading.Thread(target=stream_data, args=(symbols,))
        data_thread.daemon = True
        data_thread.start()

        # Start the Tkinter GUI
        start_gui()

        # Keep the main thread alive
        while True:
            time.sleep(1)
    else:
        print("No symbols found in the directory.")
