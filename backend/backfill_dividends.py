import os
import sys
import sqlite3
import yfinance as yf
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import DB_PATH

def backfill_dividends():
    print("Starting dividend backfill process...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    positions = [dict(r) for r in conn.execute("SELECT * FROM positions").fetchall()]
    
    for pos in positions:
        ticker = pos["ticker"]
        t212_ticker = pos["t212_ticker"]
        isin = pos["isin"]
        pos_id = pos["id"]
        units = pos["units"]
        purchase_date_str = pos["purchase_date"]
        status = pos.get("status", "open")
        sell_date_str = pos.get("sell_date") if status == "closed" else None

        search_ticker = ticker or t212_ticker
        
        if not search_ticker or not purchase_date_str:
            print(f"Skipping {pos['name']}: Missing ticker or purchase date.")
            continue
            
        try:
            clean_str = purchase_date_str.split(".")[0].replace("Z", "")
            purchase_dt = datetime.fromisoformat(clean_str).replace(tzinfo=None)
        except Exception as e:
            print(f"Skipping {pos['name']}: Invalid purchase date format {purchase_date_str}")
            continue
            
        sell_dt = None
        if sell_date_str:
            try:
                s_clean_str = sell_date_str.split(".")[0].replace("Z", "")
                sell_dt = datetime.fromisoformat(s_clean_str).replace(tzinfo=None)
            except Exception as e:
                pass
                
        print(f"Fetching full dividend history for {search_ticker}...")
        try:
            tk = yf.Ticker(search_ticker)
            divs = tk.dividends
            if divs.empty:
                print(f"  No dividends found for {search_ticker}")
                continue
                
            inserted_count = 0
            for idx, amount in divs.items():
                ex_date = idx.replace(tzinfo=None)
                
                # Check if ex_date is after purchase date and before sell date (if applicable)
                if ex_date >= purchase_dt:
                    if sell_dt and ex_date > sell_dt:
                        continue # Dividend was after we sold
                        
                    # Check if we already logged this dividend
                    existing = conn.execute(
                        "SELECT id FROM received_dividends WHERE position_id = ? AND date(pay_date) = date(?)",
                        (pos_id, ex_date.isoformat())
                    ).fetchone()
                    
                    if not existing:
                        # Insert the backfilled dividend
                        total_amount = float(amount) * units
                        native_ccy = pos["native_currency"] or "GBP"
                        
                        # Convert GBp to GBP if needed
                        if native_ccy in ("GBp", "GBX"):
                            total_amount = total_amount / 100.0
                            
                        conn.execute(
                            """INSERT INTO received_dividends 
                               (position_id, amount, pay_date, notes)
                               VALUES (?, ?, ?, 'Auto-backfilled')""",
                            (pos_id, total_amount, ex_date.isoformat())
                        )
                        inserted_count += 1
                        
            conn.commit()
            print(f"  Inserted {inserted_count} historical dividends for {pos['name']}")
            
        except Exception as e:
            print(f"  Failed fetching dividends for {search_ticker}: {e}")

    conn.close()
    print("Dividend backfill complete.")

if __name__ == "__main__":
    backfill_dividends()
