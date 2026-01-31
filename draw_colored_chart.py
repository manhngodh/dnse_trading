import sys
# Force plotext to think we are in a TTY to enable colors
sys.stdout.isatty = lambda: True

import plotext as plt
from vnstock import Vnstock
from datetime import datetime, timedelta

def draw_terminal_chart():
    symbol = 'VND'
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    
    try:
        stock = Vnstock().stock(symbol=symbol, source='VCI')
        df = stock.quote.history(start=start_date, end=end_date, interval='5m')
        
        if df is None or df.empty:
            print("No data found.")
            return

        cols = {c.lower(): c for c in df.columns}
        
        # Take last 60 for clarity
        df = df.tail(60)
        
        dates = df[cols['time']].astype(str).tolist()
        opens = df[cols['open']].tolist()
        closes = df[cols['close']].tolist()
        highs = df[cols['high']].tolist()
        lows = df[cols['low']].tolist()
        
        # Convert to timestamps for plotting
        timestamps = [datetime.strptime(d, '%Y-%m-%d %H:%M:%S').timestamp() for d in dates]
        # Format labels for X-axis (HH:MM)
        labels = [datetime.strptime(d, '%Y-%m-%d %H:%M:%S').strftime('%H:%M') for d in dates]
        
        plt.clf()
        plt.title(f"{symbol} 5-Minute Chart")
        
        # Enable date form for output
        plt.date_form(output_form='%H:%M')
        
        data = {
            "Open": opens,
            "Close": closes,
            "High": highs,
            "Low": lows
        }
        
        # Plot candlestick with custom colors: [Up Color, Down Color]
        # Note: plotext uses the first color for 'Bull' (Up) and second for 'Bear' (Down) usually
        plt.candlestick(timestamps, data, colors=['green', 'red'])
        
        # Set X-axis labels to readable time manually to ensure clarity
        tick_indices = range(0, len(timestamps), 10)
        plt.xticks([timestamps[i] for i in tick_indices], [labels[i] for i in tick_indices])
        
        plt.show()
        
    except Exception as e:
        print(f"Error drawing chart: {e}")

if __name__ == "__main__":
    draw_terminal_chart()
