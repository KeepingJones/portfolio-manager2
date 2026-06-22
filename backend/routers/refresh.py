from fastapi import APIRouter, HTTPException
from database import db
from services.price_fetcher import fetch_price
from services.fx import to_gbp
from services.t212_client import T212Client
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

router = APIRouter(prefix="/api/refresh", tags=["refresh"])


def _do_refresh(row: dict, t212=None) -> dict:
    result = fetch_price(
        ticker=row.get("ticker"),
        isin=row.get("isin"),
        asset_type=row.get("asset_type", "stock"),
        t212_client=t212,
        t212_ticker=row.get("t212_ticker"),
        hint_native_currency=row.get("native_currency") or row.get("currency"),
    )
    if result:
        native_price = result["native_price"]
        native_currency = result["native_currency"]
        gbp_price, fx_rate = to_gbp(native_price, native_currency)
        if gbp_price is None:
            return {"id": row["id"], "name": row["name"], "status": "fx_error",
                    "native_currency": native_currency}
        now = datetime.now(timezone.utc).isoformat()
        with db() as conn:
            conn.execute(
                """UPDATE positions SET
                   last_price=?, native_price=?, native_currency=?,
                   last_fx_rate=?, last_price_currency='GBP',
                   last_price_source=?, last_price_at=?, updated_at=?
                   WHERE id=?""",
                (gbp_price, native_price, native_currency, fx_rate,
                 result["source"], now, now, row["id"]),
            )
        return {
            "id": row["id"],
            "name": row["name"],
            "native_price": native_price,
            "native_currency": native_currency,
            "gbp_price": gbp_price,
            "fx_rate": fx_rate,
            "source": result["source"],
            "status": "ok",
        }
    return {"id": row["id"], "name": row["name"], "status": "not_found"}


def _make_t212() -> T212Client | None:
    try:
        from config import T212_API_KEY
        if T212_API_KEY:
            return T212Client()
    except Exception:
        pass
    return None


@router.post("")
def refresh_all():
    with db() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM positions").fetchall()]

    t212 = _make_t212()

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_do_refresh, row, t212): row for row in rows}
        results = [f.result() for f in as_completed(futures)]

    if t212:
        t212.close()

    ok = sum(1 for r in results if r["status"] == "ok")
    return {"refreshed": ok, "failed": len(results) - ok, "results": results}


@router.post("/{position_id}")
def refresh_one(position_id: int):
    with db() as conn:
        row = conn.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Position not found")

    t212 = None
    if dict(row).get("t212_ticker"):
        t212 = _make_t212()

    result = _do_refresh(dict(row), t212)
    if t212:
        t212.close()
    return result
