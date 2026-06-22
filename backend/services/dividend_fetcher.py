"""
Dividend data: fetch from yfinance + OpenFIGI mapping.
Also provides frequency detection and 12-month projection.
"""
import yfinance as yf
import calendar as cal_module
from datetime import datetime, date
from typing import Optional
from services.price_fetcher import _openfigi_to_ticker


# ── Helpers ────────────────────────────────────────────────────────────────

def _safe_date(val) -> Optional[str]:
    if val is None:
        return None
    try:
        if hasattr(val, "date"):
            return val.date().isoformat()
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)
    except Exception:
        return None


def add_months(dt: date, n: int) -> date:
    month = (dt.month - 1 + n) % 12 + 1
    year = dt.year + (dt.month - 1 + n) // 12
    max_day = cal_module.monthrange(year, month)[1]
    return dt.replace(year=year, month=month, day=min(dt.day, max_day))


# ── Frequency detection ────────────────────────────────────────────────────

_FREQ_MONTHS = {"monthly": 1, "quarterly": 3, "semi-annual": 6, "annual": 12, "unknown": 12}
_FREQ_LABELS = {"monthly": "Monthly", "quarterly": "Quarterly",
                "semi-annual": "Semi-Annual", "annual": "Annual", "unknown": "Unknown"}


def detect_frequency(events: list[dict]) -> str:
    """Infer payment frequency from historical dividend_events."""
    dates = sorted([
        datetime.strptime(e["ex_date"], "%Y-%m-%d").date()
        for e in events if e.get("ex_date")
    ])
    if len(dates) < 2:
        return "unknown"
    gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
    avg = sum(gaps) / len(gaps)
    if avg <= 45:
        return "monthly"
    elif avg <= 120:
        return "quarterly"
    elif avg <= 240:
        return "semi-annual"
    else:
        return "annual"


# ── Projection ─────────────────────────────────────────────────────────────

def project_future_payments(
    position: dict,
    events: list[dict],
    frequency: str,
    horizon_months: int = 13,
) -> list[dict]:
    """
    Project expected dividend payments for the next horizon_months months.
    Uses the most recent historical event as the amount anchor.
    """
    if not events or frequency == "unknown":
        return []

    sorted_events = sorted(events, key=lambda e: e.get("ex_date") or "", reverse=True)
    recent = sorted_events[0]
    last_amount = recent.get("amount_per_unit") or 0
    last_date_str = recent.get("ex_date")

    if not last_date_str or not last_amount:
        return []

    # yfinance inconsistently returns GBp-listed dividends in raw pence instead of GBP.
    # A single payment > 20% of the GBP share price is impossible for any real dividend,
    # so amounts in that range must be pence and need dividing by 100.
    native_ccy = position.get("native_currency", "GBP")
    last_price_gbp = position.get("last_price")
    if native_ccy in ("GBp", "GBX"):
        if last_price_gbp and last_amount > last_price_gbp * 0.2:
            last_amount = last_amount / 100
        elif not last_price_gbp and last_amount > 1.0:
            last_amount = last_amount / 100

    try:
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
    except ValueError:
        return []

    interval = _FREQ_MONTHS[frequency]
    today = date.today()
    cutoff = add_months(today.replace(day=1), horizon_months)

    payments = []
    
    # If the most recent known event is actually in the future (upcoming), include it
    if last_date >= today and last_date <= cutoff:
        payments.append({
            "position_id": position["id"],
            "position_name": position["name"],
            "projected_date": last_date.isoformat(),
            "year_month": last_date.strftime("%Y-%m"),
            "amount_per_unit": last_amount,
            "projected_total": round(last_amount * position["units"], 2),
            "frequency": frequency,
            "frequency_label": _FREQ_LABELS[frequency],
            "is_projected": False,
        })

    next_date = add_months(last_date, interval)
    while next_date <= cutoff:
        if next_date >= today:
            payments.append({
                "position_id": position["id"],
                "position_name": position["name"],
                "projected_date": next_date.isoformat(),
                "year_month": next_date.strftime("%Y-%m"),
                "amount_per_unit": last_amount,
                "projected_total": round(last_amount * position["units"], 2),
                "frequency": frequency,
                "frequency_label": _FREQ_LABELS[frequency],
                "is_projected": True,
            })
        next_date = add_months(next_date, interval)

    return payments


# ── yfinance fetch ─────────────────────────────────────────────────────────

def fetch_yf_dividends(ticker: str) -> dict:
    result = {"historical": [], "upcoming": None, "annual_yield": None, "annual_rate": None}
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        divs = t.dividends
        if divs is not None and not divs.empty:
            for ts, amount in divs.items():
                result["historical"].append({
                    "ex_date": _safe_date(ts),
                    "amount_per_unit": round(float(amount), 6),
                })

        ex_ts = info.get("exDividendDate")
        last_div = info.get("lastDividendValue")  # per-payment only; dividendRate is annual
        if ex_ts:
            ex_date = (datetime.fromtimestamp(ex_ts).date().isoformat()
                       if isinstance(ex_ts, (int, float)) else _safe_date(ex_ts))
            result["upcoming"] = {
                "ex_date": ex_date,
                "pay_date": None,
                "amount_per_unit": round(float(last_div), 6) if last_div else None,
            }

        raw_yield = info.get("dividendYield")
        if raw_yield is not None and raw_yield > 0.25:
            # yfinance sometimes returns yield as a percentage (e.g. 6.25 for 6.25%)
            # instead of a decimal (0.0625) for GBp-listed UK stocks — divide back down.
            raw_yield = raw_yield / 100
        result["annual_yield"] = raw_yield
        result["annual_rate"] = info.get("dividendRate")

    except Exception:
        pass
    return result


_FUND_TYPES = {"investment_trust", "oeic", "unit_trust"}


def _parse_gilt_dividends(name: str, last_price_gbp: float | None) -> dict:
    import re
    from datetime import timedelta

    data = {"historical": [], "upcoming": None, "annual_yield": None, "annual_rate": None}
    
    match = re.search(r'([\d\.]+)%\s*.*(\d{2}/\d{2}/\d{4})', name)
    if not match:
        return data
        
    coupon = float(match.group(1)) / 100
    maturity_str = match.group(2)
    try:
        maturity_date = datetime.strptime(maturity_str, "%d/%m/%Y").date()
    except ValueError:
        return data

    if last_price_gbp:
        data["annual_yield"] = round(coupon / last_price_gbp, 6)
        
    data["annual_rate"] = coupon
    
    month1 = maturity_date.month
    month2 = month1 - 6 if month1 > 6 else month1 + 6
    day = maturity_date.day
    
    today = date.today()
    amount_per_payment = round(coupon / 2, 6)
    
    candidate_dates = []
    for yr in range(today.year - 2, today.year + 2):
        for m in (month1, month2):
            try:
                candidate_dates.append(date(yr, m, day))
            except ValueError:
                from calendar import monthrange
                candidate_dates.append(date(yr, m, monthrange(yr, m)[1]))
                
    candidate_dates.sort()
    
    for d in candidate_dates:
        if d < today:
            data["historical"].append({
                "ex_date": d.isoformat(),
                "amount_per_unit": amount_per_payment
            })
        elif d >= today and not data["upcoming"]:
            data["upcoming"] = {
                "ex_date": d.isoformat(),
                "pay_date": None,
                "amount_per_unit": amount_per_payment
            }
            
    return data


def _compute_yield_from_history(
    historical: list[dict],
    native_currency: str,
    last_price_gbp: float | None,
) -> float | None:
    """Derive annual yield from historical payment data.

    More reliable than yfinance dividendYield for UK fund types because we've
    already applied the GBp→GBP normalisation to the amounts.
    """
    if not historical or not last_price_gbp:
        return None
    freq = detect_frequency(historical)
    if freq == "unknown":
        return None
    sorted_hist = sorted(historical, key=lambda e: e.get("ex_date") or "")
    last_amount = sorted_hist[-1]["amount_per_unit"]
    # Apply GBp correction using the same threshold as project_future_payments
    if native_currency in ("GBp", "GBX"):
        if last_amount > last_price_gbp * 0.2:
            last_amount /= 100
    payments_per_year = 12 / _FREQ_MONTHS[freq]
    annual_div = last_amount * payments_per_year
    return round(annual_div / last_price_gbp, 6)


def fetch_dividends_for_position(
    ticker: str | None,
    isin: str | None,
    asset_type: str = "stock",
    native_currency: str = "GBP",
    last_price_gbp: float | None = None,
    position_name: str | None = None,
) -> dict:
    is_fund = asset_type in _FUND_TYPES

    if asset_type == "bond" and position_name and "UK Gov" in position_name:
        parsed = _parse_gilt_dividends(position_name, last_price_gbp)
        if parsed["historical"] or parsed["upcoming"]:
            return parsed

    # For funds: ISIN is the definitive identifier — try it first.
    # For equities: ticker first, ISIN as fallback.
    if is_fund:
        order = [("isin", isin), ("ticker", ticker)]
    else:
        order = [("ticker", ticker), ("isin", isin)]

    data: dict = {"historical": [], "upcoming": None, "annual_yield": None, "annual_rate": None}
    for src, val in order:
        if not val:
            continue
        if src == "isin":
            mapped = _openfigi_to_ticker(val)
            if not mapped:
                continue
            candidate = fetch_yf_dividends(mapped)
        else:
            candidate = fetch_yf_dividends(val)
        if candidate["historical"] or candidate["upcoming"]:
            data = candidate
            break

    # For fund types, always compute yield from actual payment history —
    # yfinance dividendYield is unreliable for UK investment trusts / OEICs.
    if is_fund and data["historical"]:
        computed = _compute_yield_from_history(
            data["historical"], native_currency, last_price_gbp
        )
        if computed is not None:
            data["annual_yield"] = computed

    # For equities, fall back to computed yield only when yfinance gave nothing.
    elif data["annual_yield"] is None and data["historical"]:
        computed = _compute_yield_from_history(
            data["historical"], native_currency, last_price_gbp
        )
        if computed is not None:
            data["annual_yield"] = computed

    return data
