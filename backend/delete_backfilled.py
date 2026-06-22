import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import DB_PATH

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("DELETE FROM received_dividends WHERE notes='Auto-backfilled'")
conn.commit()
print(f"Deleted {cur.rowcount} backfilled dividends.")
conn.close()
