from fastapi import APIRouter, HTTPException
from database import db
from services.t212_client import T212Client
from datetime import datetime, timezone

router = APIRouter(prefix="/api/t212", tags=["t212"])


@router.get("/preview")
def preview_t212():
    """Preview T212 portfolio without importing."""
    with db() as conn:
        api_key_row = conn.execute("SELECT value FROM portfolio_settings WHERE key='t212_api_key'").fetchone()
        api_secret_row = conn.execute("SELECT value FROM portfolio_settings WHERE key='t212_api_secret'").fetchone()
        api_key = api_key_row["value"] if api_key_row else None
        api_secret = api_secret_row["value"] if api_secret_row else None
        
    if not api_key:
        raise HTTPException(400, "Trading 212 API key not configured for this portfolio")
        
    try:
        client = T212Client(api_key=api_key, api_secret=api_secret)
        positions = client.get_portfolio()
        instruments = {i["ticker"]: i for i in client.get_instruments()}
        client.close()
    except Exception as e:
        raise HTTPException(502, f"T212 API error: {e}")

    result = []
    for pos in positions:
        inst = instruments.get(pos.get("ticker"), {})
        result.append({
            "ticker": pos.get("ticker"),
            "name": inst.get("name", pos.get("ticker")),
            "isin": inst.get("isin"),
            "quantity": pos.get("quantity"),
            "averagePrice": pos.get("averagePrice"),
            "currentPrice": pos.get("currentPrice"),
            "ppl": pos.get("ppl"),
            "currency": inst.get("currencyCode", "GBP"),
            "type": inst.get("type", "STOCK"),
        })
    return result


@router.post("/import")
def import_from_t212():
    """Sync T212 positions into portfolio. Adds new, updates existing, and marks missing as closed."""
    with db() as conn:
        api_key_row = conn.execute("SELECT value FROM portfolio_settings WHERE key='t212_api_key'").fetchone()
        api_secret_row = conn.execute("SELECT value FROM portfolio_settings WHERE key='t212_api_secret'").fetchone()
        api_key = api_key_row["value"] if api_key_row else None
        api_secret = api_secret_row["value"] if api_secret_row else None
        
    if not api_key:
        raise HTTPException(400, "Trading 212 API key not configured for this portfolio")

    try:
        client = T212Client(api_key=api_key, api_secret=api_secret)
        positions = client.get_portfolio()
        instruments = {i["ticker"]: i for i in client.get_instruments()}
        client.close()
    except Exception as e:
        raise HTTPException(502, f"T212 API error: {e}")

    _T212_TYPE_MAP = {
        "STOCK": "stock",
        "ETF": "stock",
        "BOND": "bond",
        "FUND": "oeic",
        "CRYPTO": "stock",
    }

    now = datetime.now(timezone.utc).isoformat()
    imported = []
    updated = []
    closed = []
    skipped = []

    with db() as conn:
        # Get all existing active T212 positions
        existing_t212 = conn.execute(
            "SELECT id, t212_ticker FROM positions WHERE status='open' AND t212_ticker IS NOT NULL"
        ).fetchall()
        
        active_t212_tickers = {r["t212_ticker"]: r["id"] for r in existing_t212}
        seen_t212_tickers = set()

        for pos in positions:
            ticker = pos.get("ticker")
            if not ticker: continue
            
            seen_t212_tickers.add(ticker)
            inst = instruments.get(ticker, {})
            isin = inst.get("isin")
            name = inst.get("name", ticker)
            asset_type = _T212_TYPE_MAP.get(inst.get("type", "STOCK"), "stock")
            currency = inst.get("currencyCode", "GBP")
            units = pos.get("quantity", 0)
            avg_price = pos.get("averagePrice", 0)
            current_price = pos.get("currentPrice")

            if ticker in active_t212_tickers:
                # Update existing
                pid = active_t212_tickers[ticker]
                conn.execute(
                    """UPDATE positions 
                       SET units=?, book_cost_per_unit=?, last_price=?, last_price_currency=?, 
                           last_price_source=?, last_price_at=?, updated_at=?
                       WHERE id=?""",
                    (units, avg_price, current_price, currency, "t212", now, now, pid)
                )
                updated.append({"id": pid, "ticker": ticker, "name": name})
            else:
                # Need to check if there's a closed one we should re-open, or just insert new
                # For simplicity, always insert new
                cur = conn.execute(
                    """INSERT INTO positions
                       (name,isin,ticker,asset_type,units,book_cost_per_unit,currency,
                        t212_ticker,category,last_price,last_price_currency,last_price_source,
                        last_price_at,created_at,updated_at,status)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (name, isin, None, asset_type, units, avg_price, currency,
                     ticker, "growth", current_price, currency, "t212", now, now, now, "open"),
                )
                imported.append({"id": cur.lastrowid, "ticker": ticker, "name": name})
                
        # Mark missing as closed
        for t_ticker, pid in active_t212_tickers.items():
            if t_ticker not in seen_t212_tickers:
                conn.execute(
                    "UPDATE positions SET status='closed', updated_at=? WHERE id=?",
                    (now, pid)
                )
                closed.append({"id": pid, "ticker": t_ticker})

    return {
        "imported": len(imported),
        "updated": len(updated),
        "closed": len(closed),
        "positions": imported,
        "already_existed": skipped,
    }
