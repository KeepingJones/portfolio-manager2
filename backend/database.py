import sqlite3
from contextlib import contextmanager
from config import DB_PATH

_ALLOWED_MIGRATIONS: list[tuple[str, str]] = [
    ("native_currency", "TEXT"),
    ("native_price", "REAL"),
    ("last_fx_rate", "REAL"),
    ("annual_yield", "REAL"),
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                isin TEXT,
                ticker TEXT,
                asset_type TEXT NOT NULL CHECK(asset_type IN ('stock','bond','oeic','unit_trust','investment_trust')),
                units REAL NOT NULL DEFAULT 0,
                book_cost_per_unit REAL NOT NULL DEFAULT 0,
                currency TEXT NOT NULL DEFAULT 'GBP',
                native_currency TEXT,
                t212_ticker TEXT,
                category TEXT NOT NULL DEFAULT 'growth',
                notes TEXT,
                last_price REAL,
                native_price REAL,
                last_fx_rate REAL,
                last_price_currency TEXT,
                last_price_source TEXT,
                last_price_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS dividend_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
                ex_date TEXT,
                pay_date TEXT,
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

            CREATE TABLE IF NOT EXISTS portfolio_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_dividend_events_position
                ON dividend_events(position_id);
            CREATE INDEX IF NOT EXISTS idx_received_dividends_position
                ON received_dividends(position_id);
            CREATE INDEX IF NOT EXISTS idx_dividend_events_ex_date
                ON dividend_events(ex_date);
        """)

        # Migrate existing databases — only columns from the allowlist
        existing_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(positions)").fetchall()
        }
        for col, col_type in _ALLOWED_MIGRATIONS:
            if col not in existing_cols:
                # col and col_type are validated against the allowlist above
                conn.execute(f"ALTER TABLE positions ADD COLUMN {col} {col_type}")
