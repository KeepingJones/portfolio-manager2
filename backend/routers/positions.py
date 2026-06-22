from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import db
from datetime import datetime, timezone

router = APIRouter(prefix="/api/positions", tags=["positions"])


class PositionIn(BaseModel):
    name: str
    isin: Optional[str] = None
    ticker: Optional[str] = None
    asset_type: str
    units: float
    book_cost_per_unit: float
    currency: str = "GBP"             # book cost denomination
    native_currency: Optional[str] = None  # instrument trading currency (GBp, USD, EUR…)
    t212_ticker: Optional[str] = None
    category: str = "growth"
    notes: Optional[str] = None
    annual_yield: Optional[float] = None


def _row_to_dict(row) -> dict:
    d = dict(row)
    units = d.get("units", 0)
    book = d.get("book_cost_per_unit", 0)
    total_book = round(units * book, 2)
    d["total_book_cost"] = total_book

    gbp_price = d.get("last_price")
    if gbp_price is not None:
        current_value = round(units * gbp_price, 2)
        pnl = round(current_value - total_book, 2)
        pnl_pct = round((pnl / total_book * 100), 2) if total_book else 0.0
    else:
        current_value = pnl = pnl_pct = None

    d["current_value"] = current_value
    d["unrealised_pnl"] = pnl
    d["unrealised_pnl_pct"] = pnl_pct
    # Ensure these keys exist even if columns are absent (old DB)
    d.setdefault("native_price", None)
    d.setdefault("native_currency", None)
    d.setdefault("last_fx_rate", None)
    d.setdefault("last_price_at", None)
    d.setdefault("annual_yield", None)
    return d


@router.get("")
def list_positions():
    with db() as conn:
        rows = conn.execute("SELECT * FROM positions ORDER BY name").fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/{position_id}")
def get_position(position_id: int):
    with db() as conn:
        row = conn.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Position not found")
    return _row_to_dict(row)


@router.post("", status_code=201)
def create_position(body: PositionIn):
    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO positions
               (name,isin,ticker,asset_type,units,book_cost_per_unit,currency,
                native_currency,t212_ticker,category,notes,annual_yield,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (body.name, body.isin, body.ticker, body.asset_type, body.units,
             body.book_cost_per_unit, body.currency, body.native_currency,
             body.t212_ticker, body.category, body.notes, body.annual_yield, now, now),
        )
        row = conn.execute("SELECT * FROM positions WHERE id=?", (cur.lastrowid,)).fetchone()
    return _row_to_dict(row)


@router.put("/{position_id}")
def update_position(position_id: int, body: PositionIn):
    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        existing = conn.execute("SELECT id FROM positions WHERE id=?", (position_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Position not found")
        conn.execute(
            """UPDATE positions SET
               name=?,isin=?,ticker=?,asset_type=?,units=?,book_cost_per_unit=?,
               currency=?,native_currency=?,t212_ticker=?,category=?,notes=?,annual_yield=?,updated_at=?
               WHERE id=?""",
            (body.name, body.isin, body.ticker, body.asset_type, body.units,
             body.book_cost_per_unit, body.currency, body.native_currency,
             body.t212_ticker, body.category, body.notes, body.annual_yield, now, position_id),
        )
        row = conn.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone()
    return _row_to_dict(row)


@router.delete("/{position_id}", status_code=204)
def delete_position(position_id: int):
    with db() as conn:
        conn.execute("DELETE FROM positions WHERE id=?", (position_id,))


class ManualPriceIn(BaseModel):
    price: float
    currency: str = "GBP"


@router.post("/{position_id}/price")
def set_manual_price(position_id: int, body: ManualPriceIn):
    from services.fx import to_gbp
    with db() as conn:
        pos = conn.execute("SELECT id FROM positions WHERE id=?", (position_id,)).fetchone()
    if not pos:
        raise HTTPException(404, "Position not found")
    gbp_price, fx_rate = to_gbp(body.price, body.currency)
    if gbp_price is None:
        raise HTTPException(502, f"FX rate for {body.currency} is unavailable — try again shortly")
    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        conn.execute(
            """UPDATE positions SET
               last_price=?, native_price=?, native_currency=?,
               last_fx_rate=?, last_price_source=?, last_price_at=?, updated_at=?
               WHERE id=?""",
            (gbp_price, body.price, body.currency, fx_rate, "manual", now, now, position_id),
        )
    return {"status": "ok", "gbp_price": round(gbp_price, 6), "native_price": body.price,
            "native_currency": body.currency, "fx_rate": fx_rate}
