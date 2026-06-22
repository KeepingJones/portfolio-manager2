import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import DB_PATH

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("UPDATE positions SET purchase_date='2025-01-01T00:00:00Z' WHERE purchase_date IS NULL")
conn.commit()
print(f"Updated {cur.rowcount} positions with missing purchase dates.")
conn.close()
