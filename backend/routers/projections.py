from fastapi import APIRouter
from database import db
from services.projector import project_growth, project_income, project_total_return
from datetime import date, timedelta

router = APIRouter(prefix="/api/projections", tags=["projections"])


def _get_portfolio_stats() -> dict:
    with db() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM positions").fetchall()]

    total_value = 0.0
    growth_value = 0.0
    income_value = 0.0

    for pos in rows:
        price = pos.get("last_price")
        units = pos.get("units", 0)
        val = units * price if price else units * pos.get("book_cost_per_unit", 0)
        total_value += val
        if pos.get("category") == "income":
            income_value += val
        else:
            growth_value += val

    # Annual dividend income: sum last 12 months received
    cutoff = (date.today() - timedelta(days=365)).isoformat()
    with db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount),0) as total FROM received_dividends WHERE pay_date >= ?",
            (cutoff,),
        ).fetchone()
    annual_income = float(row["total"]) if row else 0.0

    # If no received dividends, estimate from annual_yield or dividend events
    if annual_income == 0.0:
        for pos in rows:
            ay = pos.get("annual_yield")
            units = pos.get("units", 0)
            price = pos.get("last_price", 0)
            
            if ay is not None and price:
                annual_income += ay * (units * price)
            else:
                with db() as conn:
                    rows_de = conn.execute(
                        """SELECT amount_per_unit FROM dividend_events
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
                            
                    annual_income += amt * units

    return {
        "total_value": round(total_value, 2),
        "growth_value": round(growth_value, 2),
        "income_value": round(income_value, 2),
        "annual_income": round(annual_income, 2),
    }


@router.get("")
def get_projections(years: int = 20, income_years: int = 10):
    stats = _get_portfolio_stats()
    growth = project_growth(stats["total_value"], years=years)
    income = project_income(stats["annual_income"], years=income_years)
    total_return = project_total_return(
        current_value=stats["total_value"],
        annual_income=stats["annual_income"],
        years=years,
    )
    return {
        "stats": stats,
        "growth": growth,
        "income": income,
        "total_return": total_return,
    }
