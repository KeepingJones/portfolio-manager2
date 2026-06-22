import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import DB_PATH

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT p.ticker, de.ex_date, de.amount_per_unit FROM dividend_events de JOIN positions p ON p.id = de.position_id WHERE p.ticker IN ('UU.L', 'SSE.L')").fetchall()
for r in rows:
    print(r['ticker'], r['ex_date'], r['amount_per_unit'])
conn.close()
