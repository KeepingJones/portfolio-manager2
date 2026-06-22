import base64
import httpx
from typing import Optional
from config import T212_API_KEY, T212_API_SECRET, T212_BASE_URL


def _auth_header() -> str:
    if T212_API_SECRET:
        encoded = base64.b64encode(f"{T212_API_KEY}:{T212_API_SECRET}".encode()).decode()
        return f"Basic {encoded}"
    return T212_API_KEY


class T212Client:
    def __init__(self):
        self._http = httpx.Client(
            base_url=T212_BASE_URL,
            headers={"Authorization": _auth_header()},
            timeout=30.0,
        )

    def _get(self, path: str, params: dict = None) -> dict | list:
        r = self._http.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def get_portfolio(self) -> list[dict]:
        data = self._get("/equity/portfolio")
        return data if isinstance(data, list) else data.get("items", [])

    def get_position(self, ticker: str) -> Optional[dict]:
        try:
            return self._get(f"/equity/portfolio/{ticker}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    def get_instruments(self) -> list[dict]:
        data = self._get("/equity/metadata/instruments")
        return data if isinstance(data, list) else []

    def get_dividend_history(self, limit: int = 200) -> list[dict]:
        items = []
        cursor = None
        while True:
            params = {"limit": min(limit, 50)}
            if cursor:
                params["cursor"] = cursor
            data = self._get("/equity/history/dividends", params=params)
            batch = data.get("items", []) if isinstance(data, dict) else data
            items.extend(batch)
            cursor = data.get("nextCursor") if isinstance(data, dict) else None
            if not cursor or len(items) >= limit:
                break
        return items[:limit]

    def close(self):
        self._http.close()
