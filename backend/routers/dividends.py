from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import db
from services.dividend_fetcher import fetch_dividends_for_position, detect_frequency, project_future_payments, _FREQ_LABELS
from datetime import datetime, timezone, date

router = APIRouter(prefix="/api/dividends", tags=["dividends"])


class ReceivedDividendIn(BaseModel):
    position_id: int
    pay_date: str
    amount: float
    currency: str = "GBP"
    notes: Optional[str] = None


def _upsert_dividend_events(conn, position_id: int, position_currency: str, data: dict, now: str) -> int:
    """Insert upcoming + historical dividend events, skipping duplicates. Returns count inserted."""
    inserted = 0

    if data.get("upcoming") and data["upcoming"].get("ex_date"):
        u = data["upcoming"]
        if u.get("amount_per_unit") and not conn.execute(
            "SELECT id FROM dividend_events WHERE position_id=? AND ex_date=?",
            (position_id, u["ex_date"]),
        ).fetchone():
            conn.execute(
                """INSERT INTO dividend_events
                   (position_id,ex_date,pay_date,amount_per_unit,currency,div_type,source,created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (position_id, u["ex_date"], u.get("pay_date"), u["amount_per_unit"],
                 position_currency, "ordinary", "yfinance", now),
            )
            inserted += 1

    for h in data.get("historical", [])[-8:]:
        if not h.get("ex_date") or not h.get("amount_per_unit"):
            continue
        if not conn.execute(
            "SELECT id FROM dividend_events WHERE position_id=? AND ex_date=?",
            (position_id, h["ex_date"]),
        ).fetchone():
            conn.execute(
                """INSERT INTO dividend_events
                   (position_id,ex_date,pay_date,amount_per_unit,currency,div_type,source,created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (position_id, h["ex_date"], None, h["amount_per_unit"],
                 position_currency, "ordinary", "yfinance", now),
            )
            inserted += 1

    return inserted


@router.get("")
def list_dividend_events():
    with db() as conn:
        rows = conn.execute(
            """SELECT de.*, p.name as position_name, p.units
               FROM dividend_events de
               JOIN positions p ON p.id = de.position_id
               ORDER BY de.ex_date DESC NULLS LAST"""
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["projected_total"] = round(d["units"] * d["amount_per_unit"], 2) if d["amount_per_unit"] else None
        result.append(d)
    return result


@router.get("/upcoming")
def upcoming_dividends():
    today = date.today().isoformat()
    with db() as conn:
        rows = conn.execute(
            """SELECT de.*, p.name as position_name, p.units
               FROM dividend_events de
               JOIN positions p ON p.id = de.position_id
               WHERE de.ex_date >= ? OR de.pay_date >= ?
               ORDER BY de.ex_date ASC""",
            (today, today),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["projected_total"] = round(d["units"] * d["amount_per_unit"], 2) if d["amount_per_unit"] else None
        result.append(d)
    return result


@router.get("/received")
def list_received():
    with db() as conn:
        rows = conn.execute(
            """SELECT rd.*, p.name as position_name
               FROM received_dividends rd
               JOIN positions p ON p.id = rd.position_id
               ORDER BY rd.pay_date DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/received", status_code=201)
def log_received(body: ReceivedDividendIn):
    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO received_dividends (position_id,pay_date,amount,currency,notes,created_at) VALUES (?,?,?,?,?,?)",
            (body.position_id, body.pay_date, body.amount, body.currency, body.notes, now),
        )
        row = conn.execute(
            """SELECT rd.*, p.name as position_name FROM received_dividends rd
               JOIN positions p ON p.id=rd.position_id WHERE rd.id=?""",
            (cur.lastrowid,),
        ).fetchone()
    return dict(row)


@router.delete("/received/{div_id}", status_code=204)
def delete_received(div_id: int):
    with db() as conn:
        conn.execute("DELETE FROM received_dividends WHERE id=?", (div_id,))


@router.post("/fetch/{position_id}")
def fetch_dividends(position_id: int):
    with db() as conn:
        pos = conn.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone()
    if not pos:
        raise HTTPException(404, "Position not found")
    pos = dict(pos)

    data = fetch_dividends_for_position(
        ticker=pos.get("ticker"),
        isin=pos.get("isin"),
        asset_type=pos.get("asset_type", "stock"),
        native_currency=pos.get("native_currency") or "GBP",
        last_price_gbp=pos.get("last_price"),
        position_name=pos.get("name"),
    )
    now = datetime.now(timezone.utc).isoformat()

    with db() as conn:
        if data.get("annual_yield") is not None:
            conn.execute(
                "UPDATE positions SET annual_yield=? WHERE id=?",
                (data["annual_yield"], position_id),
            )
        inserted = _upsert_dividend_events(conn, position_id, pos["currency"], data, now)

    return {
        "inserted": inserted,
        "annual_yield": data.get("annual_yield"),
        "annual_rate": data.get("annual_rate"),
    }


@router.post("/fetch-all")
def fetch_all_dividends():
    with db() as conn:
        positions = [dict(r) for r in conn.execute("SELECT * FROM positions").fetchall()]

    now = datetime.now(timezone.utc).isoformat()
    total_inserted = 0
    fetched = 0
    failed = 0

    for pos in positions:
        try:
            data = fetch_dividends_for_position(
                ticker=pos.get("ticker"),
                isin=pos.get("isin"),
                asset_type=pos.get("asset_type", "stock"),
                native_currency=pos.get("native_currency") or "GBP",
                last_price_gbp=pos.get("last_price"),
                position_name=pos.get("name"),
            )
            with db() as conn:
                if data.get("annual_yield") is not None:
                    conn.execute(
                        "UPDATE positions SET annual_yield=? WHERE id=?",
                        (data["annual_yield"], pos["id"]),
                    )
                total_inserted += _upsert_dividend_events(conn, pos["id"], pos["currency"], data, now)
            fetched += 1
        except Exception:
            failed += 1

    return {"fetched": fetched, "failed": failed, "total_inserted": total_inserted}


@router.get("/calendar")
def dividend_calendar():
    with db() as conn:
        positions = [dict(r) for r in conn.execute("SELECT * FROM positions").fetchall()]
        all_events = [dict(r) for r in conn.execute(
            "SELECT de.*, p.units FROM dividend_events de JOIN positions p ON p.id=de.position_id"
        ).fetchall()]

    events_by_pos = {}
    for e in all_events:
        events_by_pos.setdefault(e["position_id"], []).append(e)

    calendar: dict = {}
    position_summaries = []

    for pos in positions:
        events = events_by_pos.get(pos["id"], [])
        if not events:
            # Fallback for positions (like OEICs) with manual yield but no events
            if pos.get("annual_yield") and pos.get("last_price"):
                from datetime import date
                today = date.today()
                yr = today.year
                # Synthesize 4 quarterly events
                amt = (pos["annual_yield"] * pos["last_price"]) / 4
                events = [
                    {"ex_date": f"{yr-1}-12-01", "amount_per_unit": amt},
                    {"ex_date": f"{yr}-03-01", "amount_per_unit": amt},
                    {"ex_date": f"{yr}-06-01", "amount_per_unit": amt},
                    {"ex_date": f"{yr}-09-01", "amount_per_unit": amt},
                ]
            else:
                continue
                
        frequency = detect_frequency(events)
        payments = project_future_payments(pos, events, frequency)
        position_summaries.append({
            "position_id": pos["id"],
            "position_name": pos["name"],
            "frequency": frequency,
            "frequency_label": _FREQ_LABELS.get(frequency, "Unknown"),
            "payment_count": len(payments),
        })
        for p in payments:
            ym = p["year_month"]
            if ym not in calendar:
                calendar[ym] = {"year_month": ym, "total": 0.0, "payments": []}
            calendar[ym]["total"] = round(calendar[ym]["total"] + p["projected_total"], 2)
            calendar[ym]["payments"].append(p)

    return {
        "months": sorted(calendar.values(), key=lambda m: m["year_month"]),
        "positions": position_summaries,
    }
