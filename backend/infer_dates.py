import sqlite3
import os
import yfinance as yf
import pandas as pd
from datetime import datetime
import sys

# Add the backend dir to path so we can import modules if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.price_fetcher import _openfigi_to_ticker

def get_db_conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def infer_dates():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'portfolio.db')
    conn = get_db_conn(db_path)
    
    # Add purchase_date column if it doesn't exist
    try:
        conn.execute("ALTER TABLE positions ADD COLUMN purchase_date TEXT")
        conn.commit()
        print("Added purchase_date column.")
    except sqlite3.OperationalError:
        print("purchase_date column already exists.")

    positions = [dict(r) for r in conn.execute("SELECT * FROM positions WHERE purchase_date IS NULL").fetchall()]
    print(f"Found {len(positions)} positions to infer dates for.")

    fx_cache = {}

    def get_fx_history(currency):
        if currency in fx_cache:
            return fx_cache[currency]
        if currency == "GBP" or currency == "GBp" or currency == "GBX":
            return None
        
        # yfinance uses symbols like GBPUSD=X for GBP to USD
        # If we need native to GBP (e.g. USD to GBP), we use USDGBP=X
        symbol = f"{currency}GBP=X"
        print(f"Fetching FX history for {symbol}...")
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="max")
            fx_cache[currency] = hist
            return hist
        except Exception as e:
            print(f"Error fetching FX for {symbol}: {e}")
            return None

    for pos in positions:
        book_cost = pos["book_cost_per_unit"]
        if not book_cost:
            continue
            
        ticker = pos.get("ticker")
        if not ticker and pos.get("isin"):
            ticker = _openfigi_to_ticker(pos["isin"])
            
        if not ticker:
            print(f"[{pos['name']}] No ticker available to fetch history.")
            continue
            
        if " " in ticker:
            print(f"[{pos['name']}] Ticker contains spaces, skipping: {ticker}")
            continue
            
        print(f"[{pos['name']}] Fetching history for {ticker}...")
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="max")
            if hist.empty:
                print(f"[{pos['name']}] No historical data.")
                continue
                
            native_ccy = pos.get("native_currency") or "GBP"
            
            # Align FX data if needed
            fx_hist = get_fx_history(native_ccy)
            
            # created_at is something like "2024-03-22 14:00:00"
            created_at_dt = datetime.fromisoformat(pos["created_at"].replace("Z", "")).replace(tzinfo=None)
            
            best_date = None
            min_diff = float("inf")
            
            for date, row in hist.iterrows():
                # Make date naive
                date_naive = date.replace(tzinfo=None)
                # Must be before created_at
                if date_naive >= created_at_dt:
                    continue
                    
                price = row["Close"]
                if pd.isna(price):
                    continue
                    
                # Convert to GBP
                if native_ccy in ("GBp", "GBX"):
                    price_gbp = price / 100.0
                elif fx_hist is not None:
                    # Get closest FX rate
                    try:
                        # FX history dates might be timezone-aware
                        fx_date = date
                        if hasattr(fx_hist.index, "tz") and fx_hist.index.tz is not None:
                            fx_date = date.tz_localize(fx_hist.index.tz)
                            
                        # Use bfill/ffill or just nearest
                        fx_idx = fx_hist.index.get_indexer([fx_date], method="nearest")[0]
                        fx_rate = fx_hist.iloc[fx_idx]["Close"]
                        price_gbp = price * fx_rate
                    except Exception:
                        price_gbp = price # fallback, highly inaccurate
                else:
                    price_gbp = price
                    
                diff = abs(price_gbp - book_cost)
                diff_pct = diff / book_cost if book_cost else float('inf')
                
                # 5% threshold
                if diff_pct <= 0.05:
                    if diff < min_diff:
                        min_diff = diff
                        best_date = date
            
            if best_date:
                inferred = best_date.strftime("%Y-%m-%d")
                print(f"[{pos['name']}] Inferred Date: {inferred} (Price ~ {book_cost})")
                conn.execute("UPDATE positions SET purchase_date = ? WHERE id = ?", (inferred, pos["id"]))
                conn.commit()
            else:
                print(f"[{pos['name']}] No date found within 5% threshold.")
                
        except Exception as e:
            print(f"[{pos['name']}] Error: {e}")

if __name__ == "__main__":
    infer_dates()
