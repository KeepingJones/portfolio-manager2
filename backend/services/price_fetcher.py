"""
Price fetch cascade — returns native price + currency (NOT yet converted to GBP).
FX conversion happens in the refresh router via services.fx.
Cascade:
  1. yfinance with ticker
  2. OpenFIGI ISIN → ticker → yfinance
  3. T212 live position
  4. FT Markets scrape (ISIN, for OEICs/trusts)
  5. Trustnet scrape (ISIN, fallback)
"""
import httpx
import yfinance as yf
from bs4 import BeautifulSoup
from typing import Optional


def _yf_price(ticker: str) -> Optional[dict]:
    """Returns native price + currency as reported by yfinance."""
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("navPrice")
            or info.get("previousClose")
        )
        if not price:
            hist = t.history(period="2d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
        if price:
            currency = info.get("currency", "GBP")
            return {
                "native_price": round(float(price), 6),
                "native_currency": currency,
                "source": "yfinance",
            }
    except Exception:
        pass
    return None


def _openfigi_to_ticker(isin: str) -> Optional[str]:
    """Convert ISIN to yfinance-compatible ticker via OpenFIGI."""
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                "https://api.openfigi.com/v3/mapping",
                json=[{"idType": "ID_ISIN", "idValue": isin, "exchCode": "LN"}],
                headers={"Content-Type": "application/json"},
            )
            data = r.json()
            if data and data[0].get("data"):
                raw = data[0]["data"][0].get("ticker", "")
                if raw:
                    return f"{raw}.L"
            # Fallback: any exchange
            r = client.post(
                "https://api.openfigi.com/v3/mapping",
                json=[{"idType": "ID_ISIN", "idValue": isin}],
                headers={"Content-Type": "application/json"},
            )
            data = r.json()
            if data and data[0].get("data"):
                return data[0]["data"][0].get("ticker")
    except Exception:
        pass
    return None


def _ft_markets_price(isin: str) -> Optional[dict]:
    """Scrape FT Markets for fund/OEIC/trust prices. Returns GBP price."""
    try:
        url = f"https://markets.ft.com/data/funds/tearsheet/summary?s={isin}:GBP"
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            r = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return None
            soup = BeautifulSoup(r.text, "html.parser")

            # Find the Price list-item — FT labels it "Price (GBX)" for pence-quoted
            # funds or "Price (GBP)" for pound-quoted ones. Read the label first,
            # then fall back to value-text heuristics.
            label_ccy = None
            for li in soup.select("li"):
                lbl = li.select_one("span.mod-ui-data-list__label")
                val = li.select_one("span.mod-ui-data-list__value")
                if lbl and val and "Price" in lbl.text:
                    lbl_text = lbl.text
                    if "GBX" in lbl_text:
                        label_ccy = "GBp"
                    elif "GBP" in lbl_text:
                        label_ccy = "GBP"
                    el = val
                    break
            else:
                el = (
                    soup.select_one("span.mod-ui-data-list__value")
                    or soup.select_one(".mod-tearsheet-simple-overview__key-value")
                )

            if el:
                raw = el.text.strip().replace(",", "")
                # Currency precedence: FT label > explicit £ symbol > explicit p suffix > bare decimal
                if label_ccy:
                    native_ccy = label_ccy
                elif "£" in raw:
                    native_ccy = "GBP"
                elif raw.rstrip().endswith("p"):
                    native_ccy = "GBp"
                else:
                    native_ccy = "GBP"
                price = float(raw.replace("p", "").replace("£", "").strip())
                return {"native_price": round(price, 6), "native_currency": native_ccy, "source": "ft_markets"}
    except Exception:
        pass
    return None


def _trustnet_price(isin: str) -> Optional[dict]:
    """Scrape Trustnet for fund prices. Returns GBP price."""
    try:
        url = f"https://www.trustnet.com/fund/{isin}/factsheet"
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            r = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return None
            soup = BeautifulSoup(r.text, "html.parser")
            el = soup.select_one(".price") or soup.select_one("[data-price]")
            if el:
                raw = el.text.strip().replace(",", "")
                native_ccy = "GBP" if "£" in raw else "GBp"
                price = float(raw.replace("p", "").replace("£", "").strip())
                return {"native_price": round(price, 6), "native_currency": native_ccy, "source": "trustnet"}
    except Exception:
        pass
    return None


def fetch_price(
    ticker: str | None,
    isin: str | None,
    asset_type: str,
    t212_client=None,
    t212_ticker: str | None = None,
    hint_native_currency: str | None = None,
) -> Optional[dict]:
    """
    Returns {"native_price": float, "native_currency": str, "source": str} or None.
    Caller is responsible for FX conversion to GBP.
    """
    # 1. yfinance with provided ticker
    if ticker:
        result = _yf_price(ticker)
        if result:
            return result

    # 2. T212 live price
    if t212_client and t212_ticker:
        try:
            pos = t212_client.get_position(t212_ticker)
            if pos and pos.get("currentPrice"):
                return {
                    "native_price": float(pos["currentPrice"]),
                    "native_currency": hint_native_currency or "GBP",
                    "source": "t212",
                }
        except Exception:
            pass

    # 3. OpenFIGI ISIN → ticker → yfinance
    if isin:
        mapped_ticker = _openfigi_to_ticker(isin)
        if mapped_ticker:
            result = _yf_price(mapped_ticker)
            if result:
                return result

    # 4. FT Markets scrape (good for UK OEICs/trusts)
    if isin and asset_type in ("oeic", "unit_trust", "investment_trust", "bond"):
        result = _ft_markets_price(isin)
        if result:
            return result

    # 5. Trustnet fallback
    if isin:
        result = _trustnet_price(isin)
        if result:
            return result

    return None
