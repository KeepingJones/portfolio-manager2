"""
FX rate service. All values converted to GBP base currency.
Supports: GBp (pence), USD, EUR, CHF, JPY, CAD, AUD, and any yfinance-supported pair.
"""
import yfinance as yf
import time
from typing import Optional

_CACHE: dict[str, tuple[Optional[float], float]] = {}  # currency -> (rate_or_None, fetched_at)
_TTL = 300        # 5-minute cache for successful fetches
_FAIL_TTL = 60    # 1-minute cache for failed fetches


def _fetch_rate(from_currency: str) -> Optional[float]:
    pair = f"{from_currency.upper()}GBP=X"
    try:
        t = yf.Ticker(pair)
        info = t.info or {}
        rate = info.get("regularMarketPrice") or info.get("previousClose")
        if rate:
            return float(rate)
    except Exception:
        pass
    return None


def rate_to_gbp(from_currency: str) -> Optional[float]:
    """Return rate to multiply native price by to get GBP price. None if unavailable."""
    if from_currency in ("GBP", "GBX_GBP"):
        return 1.0
    if from_currency in ("GBp", "GBX", "p"):
        return 0.01

    now = time.monotonic()
    cached = _CACHE.get(from_currency)
    if cached:
        rate, fetched_at = cached
        ttl = _FAIL_TTL if rate is None else _TTL
        if (now - fetched_at) < ttl:
            return rate

    r = _fetch_rate(from_currency)
    _CACHE[from_currency] = (r, now)
    return r


def to_gbp(amount: float, from_currency: str) -> tuple[Optional[float], Optional[float]]:
    """
    Convert amount in from_currency to GBP.
    Returns (gbp_amount, fx_rate_used), or (None, None) if rate is unavailable.
    """
    rate = rate_to_gbp(from_currency)
    if rate is None:
        return None, None
    return round(amount * rate, 6), rate


def format_native(price: float | None, currency: str | None) -> str:
    """Human-readable native price string, e.g. '930.50p', '$271.06', '£9.31'."""
    if price is None or currency is None:
        return "—"
    symbols = {"GBP": "£", "GBp": "", "USD": "$", "EUR": "€",
               "CHF": "CHF ", "JPY": "¥", "CAD": "C$", "AUD": "A$"}
    suffix = "p" if currency == "GBp" else ""
    prefix = symbols.get(currency, f"{currency} ")
    return f"{prefix}{price:,.4f}{suffix}".rstrip("0").rstrip(".")
