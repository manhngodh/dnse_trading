#!/usr/bin/env python3
import pandas as pd
from vnstock import Vnstock
from datetime import datetime, timedelta
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Analyst")

# Stocks mentioned in the text
WATCHLIST = [
    'MBB', 'VCB', 'HDB', 'VPB', # Banks
    'GAS', 'BLX', 'GVR',        # State/Res 79
    'FOX', 'VEA', 'VGI',        # Concentrated
    'HCM',                      # Volume Spike
    'PVI', 'BVH'                # Insurance
]

def analyze_volume_profile(symbol):
    try:
        # Get last 60 days of data
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        
        # Use Vnstock V3 API
        stock = Vnstock().stock(symbol=symbol, source='VCI')
        df = stock.quote.history(start=start_date, end=end_date, interval='1D')
        
        if df is None or df.empty or len(df) < 20:
            return None

        # Normalize columns
        df.columns = [c.lower() for c in df.columns]
        
        # Get latest data
        latest = df.iloc[-1]
        
        # Calculate Metrics
        # 1. Average Volume (20 sessions)
        avg_vol_20 = df['volume'].tail(20).mean()
        curr_vol = latest['volume']
        vol_ratio = curr_vol / avg_vol_20 if avg_vol_20 > 0 else 0
        
        # 2. Price Change
        price_change = (latest['close'] - latest['open']) / latest['open'] * 100
        
        # 3. Volatility (High - Low)
        volatility = (latest['high'] - latest['low']) / latest['low'] * 100

        result = {
            "symbol": symbol,
            "price": latest['close'],
            "vol": int(curr_vol),
            "avg_vol": int(avg_vol_20),
            "ratio": round(vol_ratio, 2),
            "change": round(price_change, 2),
            "volatility": round(volatility, 2),
            "signal": "Neutral"
        }

        # --- PATTERN RECOGNITION ---
        
        # Pattern 1: "Cạn cung" (Accumulation/Tight) -> Low Vol + Low Volatility
        if vol_ratio < 0.6 and volatility < 1.5:
            result['signal'] = "DRY_UP (Cạn cung)"
            
        # Pattern 2: "Tiếng nói dòng tiền" (Spike) -> High Vol + Price Up
        elif vol_ratio > 1.5 and price_change > 0.5:
            result['signal'] = "VOLUME_SPIKE (Dòng tiền)"
            
        # Pattern 3: "Bò lên" (Sustained) -> Consistent Vol + Mild Up
        elif 0.8 <= vol_ratio <= 1.2 and price_change > 0:
            result['signal'] = "SUSTAINED (Bò lên)"

        return result

    except Exception:
        # logger.error(f"Error analyzing {symbol}: {e}")
        return None

def main():
    print(f"{'Symbol':<8} | {'Signal':<20} | {'Price':<8} | {'Vol Ratio':<10} | {'% Change':<10}")
    print("-" * 70)
    
    for symbol in WATCHLIST:
        res = analyze_volume_profile(symbol)
        if res:
            # Highlight signals
            signal_display = res['signal']
            if "SPIKE" in signal_display:
                signal_display = f"🔥 {signal_display}"
            elif "DRY" in signal_display:
                signal_display = f"🧊 {signal_display}"
                
            print(f"{res['symbol']:<8} | {signal_display:<20} | {res['price']:<8} | {res['ratio']:<10} | {res['change']:<10}")

if __name__ == "__main__":
    main()