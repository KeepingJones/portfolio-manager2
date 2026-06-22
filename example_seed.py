"""
Seed: imports an example portfolio for demonstration purposes.

Run from the portfolio-manager root:
  python example_seed.py
"""
import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "portfolio.db")
NOW = datetime.now(timezone.utc).isoformat()

# (name, isin, ticker, asset_type, units, book_cost_per_unit,
#  currency, t212_ticker, category, notes,
#  last_price, last_price_currency, last_price_source)

POSITIONS = [
    # UK Government Gilts
    (
        "UK Gov 4% Bds 22/10/2031", "GB00BPSNBF73", None,
        "bond", 10000.00, 1.0,
        "GBP", None, "income", "4% Treasury Gilt, maturity Oct 2031",
        0.97, "GBP", "pdf_import",
    ),
    (
        "UK Gov 4.5% Bds 07/06/2028", "GB00BMF9LG83", None,
        "bond", 10000.00, 1.0,
        "GBP", None, "income", "4.5% Treasury Gilt, maturity Jun 2028",
        1.0, "GBP", "pdf_import",
    ),

    # Bond / Credit Funds (OEICs)
    (
        "L&G Strategic Bond I GBP Dis", "GB00B87HPZ69", None,
        "oeic", 10000.0, 0.5,
        "GBP", None, "income", None,
        0.54, "GBP", "pdf_import",
    ),
    (
        "Man GLG Sterling Corp Bond Pro D Dis", "GB00BG5ZXZ00", None,
        "oeic", 10000.0, 1.0,
        "GBP", None, "income", None,
        1.03, "GBP", "pdf_import",
    ),

    # Investment Trusts
    (
        "BlackRock World Mining Trust Plc", "GB0005774855", "BRWM.L",
        "investment_trust", 1000.00, 5.0,
        "GBP", None, "income", None,
        5.84, "GBP", "pdf_import",
    ),
    (
        "JPMorgan Global Growth & Income Plc", "GB00BYZF5W92", "JGGI.L",
        "investment_trust", 1000.00, 5.0,
        "GBP", None, "income", None,
        5.92, "GBP", "pdf_import",
    ),

    # UK Equities
    (
        "Aviva Plc Ord", "GB00BPQY8M80", "AV.L",
        "stock", 1000.00, 4.0,
        "GBP", None, "income", None,
        4.22, "GBP", "pdf_import",
    ),
    (
        "HSBC Holdings Plc Ord", "GB0005405286", "HSBA.L",
        "stock", 1000.00, 5.0,
        "GBP", None, "income", None,
        6.22, "GBP", "pdf_import",
    ),
    (
        "Shell Plc Ord", "GB00BP6MXD84", "SHEL.L",
        "stock", 1000.00, 25.0,
        "GBP", None, "income", None,
        31.19, "GBP", "pdf_import",
    ),
]

INSERT_SQL = """
INSERT INTO positions
  (name, isin, ticker, asset_type, units, book_cost_per_unit,
   currency, t212_ticker, category, notes,
   last_price, last_price_currency, last_price_source, last_price_at,
   created_at, updated_at)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""


def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            isin TEXT,
            ticker TEXT,
            asset_type TEXT NOT NULL,
            units REAL NOT NULL DEFAULT 0,
            book_cost_per_unit REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'GBP',
            t212_ticker TEXT,
            category TEXT NOT NULL DEFAULT 'growth',
            notes TEXT,
            last_price REAL,
            last_price_currency TEXT,
            last_price_source TEXT,
            last_price_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS dividend_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            position_id INTEGER NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
            ex_date TEXT, pay_date TEXT,
            amount_per_unit REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'GBP',
            div_type TEXT NOT NULL DEFAULT 'ordinary',
            source TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS received_dividends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            position_id INTEGER NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
            pay_date TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'GBP',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)

    inserted = 0
    skipped = 0
    for row in POSITIONS:
        name = row[0]
        isin = row[1]
        existing = conn.execute(
            "SELECT id FROM positions WHERE isin=? OR (isin IS NULL AND name=?)",
            (isin, name),
        ).fetchone()
        if existing:
            print(f"  SKIP  {name}")
            skipped += 1
            continue

        conn.execute(INSERT_SQL, (
            row[0], row[1], row[2], row[3], row[4], row[5],
            row[6], row[7], row[8], row[9],
            row[10], row[11], row[12], NOW,
            NOW, NOW,
        ))
        print(f"  ADD   {name}")
        inserted += 1

    conn.commit()
    conn.close()
    print(f"\nDone: {inserted} inserted, {skipped} skipped.")
    if inserted:
        print("\nTip: start the server then hit Refresh Prices + Fetch All Dividends in the UI.")


if __name__ == "__main__":
    seed()
