from fastapi import APIRouter
from database import db
from datetime import date, timedelta

router = APIRouter(tags=["summary"])


@router.get("/api/summary")
def get_summary():
    with db() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM positions").fetchall()]

    counts: dict = {}
    total_book = 0.0
    total_value = 0.0
    by_asset: dict = {}

    for pos in rows:
        price = pos.get("last_price")
        units = pos.get("units", 0)
        book = pos.get("book_cost_per_unit", 0)
        tb = units * book
        val = units * price if price else None
        atype = pos.get("asset_type", "stock")

        counts[atype] = counts.get(atype, 0) + 1
        total_book += tb
        if val is not None:
            total_value += val

        if atype not in by_asset:
            by_asset[atype] = {"book_cost": 0.0, "value": 0.0, "count": 0}
        by_asset[atype]["book_cost"] += tb
        if val is not None:
            by_asset[atype]["value"] += val
        by_asset[atype]["count"] += 1

    capital_growth = round(total_value - total_book, 2)
    capital_growth_pct = round((capital_growth / total_book * 100), 2) if total_book else 0.0

    cutoff = (date.today() - timedelta(days=365)).isoformat()
    with db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount),0) as total FROM received_dividends WHERE pay_date >= ?",
            (cutoff,),
        ).fetchone()
    income_ttm = float(row["total"]) if row else 0.0

    projected_income = 0.0
    for pos in rows:
        ay = pos.get("annual_yield")
        units = pos.get("units", 0)
        price = pos.get("last_price", 0)
        
        # Prefer the explicit annual yield for the most accurate 12m projection
        if ay is not None and price:
            projected_income += ay * (units * price)
        else:
            # Fallback for positions with no yield: query their historical events
            with db() as conn:
                rows_de = conn.execute(
                    """SELECT amount_per_unit, currency FROM dividend_events
                       WHERE position_id = ? AND ex_date >= ?""",
                    (pos["id"], cutoff),
                ).fetchall()
                
            for r in rows_de:
                amt = r["amount_per_unit"]
                native_ccy = pos.get("native_currency") or "GBP"
                
                if native_ccy in ("GBp", "GBX"):
                    if price and amt > price * 0.2:
                        amt = amt / 100
                    elif not price and amt > 1.0:
                        amt = amt / 100
                        
                projected_income += amt * units

    annual_income_est = income_ttm if income_ttm > 0 else round(projected_income, 2)

    return {
        "total_book_cost": round(total_book, 2),
        "total_current_value": round(total_value, 2),
        "capital_growth": capital_growth,
        "capital_growth_pct": capital_growth_pct,
        "income_ttm": round(income_ttm, 2),
        "projected_annual_income": round(projected_income, 2),
        "annual_dividend_income_est": annual_income_est,
        "positions_count": len(rows),
        "by_asset_type": {k: {
            "book_cost": round(v["book_cost"], 2),
            "value": round(v["value"], 2),
            "count": v["count"]
        } for k, v in by_asset.items()},
        "asset_counts": counts,
    }
