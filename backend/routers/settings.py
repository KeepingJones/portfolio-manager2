from fastapi import APIRouter
from pydantic import BaseModel
from database import db

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsIn(BaseModel):
    cash_balance: float = 0.0


@router.get("")
def get_settings():
    with db() as conn:
        rows = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM portfolio_settings").fetchall()}
    return {"cash_balance": float(rows.get("cash_balance", 0))}


@router.put("")
def update_settings(body: SettingsIn):
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO portfolio_settings VALUES ('cash_balance', ?)", (str(body.cash_balance),))
    return {"cash_balance": body.cash_balance}
