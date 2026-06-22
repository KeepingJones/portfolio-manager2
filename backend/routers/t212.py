from fastapi import APIRouter, HTTPException
from database import db
from services.t212_client import T212Client
from datetime import datetime, timezone

router = APIRouter(prefix="/api/t212", tags=["t212"])


@router.get("/preview")
def preview_t212():
    """Preview T212 portfolio without importing."""
    try:
        client = T212Client()
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
    """Import T212 positions into portfolio. Skips already-imported tickers."""
    try:
        client = T212Client()
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
    skipped = []

    with db() as conn:
        for pos in positions:
            ticker = pos.get("ticker")
            inst = instruments.get(ticker, {})
            isin = inst.get("isin")
            name = inst.get("name", ticker)
            asset_type = _T212_TYPE_MAP.get(inst.get("type", "STOCK"), "stock")
            currency = inst.get("currencyCode", "GBP")
            units = pos.get("quantity", 0)
            avg_price = pos.get("averagePrice", 0)
            current_price = pos.get("currentPrice")

            existing = conn.execute(
                "SELECT id FROM positions WHERE t212_ticker=?", (ticker,)
            ).fetchone()
            if existing:
                skipped.append({"ticker": ticker, "name": name})
                continue

            cur = conn.execute(
                """INSERT INTO positions
                   (name,isin,ticker,asset_type,units,book_cost_per_unit,currency,
                    t212_ticker,category,last_price,last_price_currency,last_price_source,
                    last_price_at,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (name, isin, None, asset_type, units, avg_price, currency,
                 ticker, "growth", current_price, currency, "t212", now, now, now),
            )
            imported.append({"id": cur.lastrowid, "ticker": ticker, "name": name})

    return {
        "imported": len(imported),
        "skipped": len(skipped),
        "positions": imported,
        "already_existed": skipped,
    }
