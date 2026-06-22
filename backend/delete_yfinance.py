import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import DB_PATH

conn = sqlite3.connect(DB_PATH)
conn.execute("DELETE FROM dividend_events WHERE source='yfinance'")
conn.commit()
print("Deleted yfinance events")
conn.close()
