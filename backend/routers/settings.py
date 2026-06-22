from fastapi import APIRouter
from pydantic import BaseModel
from database import db

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsIn(BaseModel):
    cash_balance: float = 0.0
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    t212_api_key: str = ""
    t212_api_secret: str = ""
    t212_environment: str = "live"


@router.get("")
def get_settings():
    with db() as conn:
        rows = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM portfolio_settings").fetchall()}
    return {
        "cash_balance": float(rows.get("cash_balance", 0)),
        "ollama_url": rows.get("ollama_url", "http://localhost:11434"),
        "ollama_model": rows.get("ollama_model", "llama3"),
        "t212_api_key": rows.get("t212_api_key", ""),
        "t212_api_secret": rows.get("t212_api_secret", ""),
        "t212_environment": rows.get("t212_environment", "live"),
    }


@router.put("")
def update_settings(body: SettingsIn):
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO portfolio_settings VALUES ('cash_balance', ?)", (str(body.cash_balance),))
        conn.execute("INSERT OR REPLACE INTO portfolio_settings VALUES ('ollama_url', ?)", (body.ollama_url,))
        conn.execute("INSERT OR REPLACE INTO portfolio_settings VALUES ('ollama_model', ?)", (body.ollama_model,))
        conn.execute("INSERT OR REPLACE INTO portfolio_settings VALUES ('t212_api_key', ?)", (body.t212_api_key,))
        conn.execute("INSERT OR REPLACE INTO portfolio_settings VALUES ('t212_api_secret', ?)", (body.t212_api_secret,))
        conn.execute("INSERT OR REPLACE INTO portfolio_settings VALUES ('t212_environment', ?)", (body.t212_environment,))
    return {
        "cash_balance": body.cash_balance,
        "ollama_url": body.ollama_url,
        "ollama_model": body.ollama_model,
        "t212_api_key": body.t212_api_key,
        "t212_api_secret": body.t212_api_secret,
        "t212_environment": body.t212_environment,
    }
