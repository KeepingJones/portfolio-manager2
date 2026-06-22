# Portfolio Manager

A self-hosted UK investment portfolio tracker with live pricing, dividend tracking, income projections, and export to Excel/PDF. Built for income-focused UK portfolios holding gilts, OEICs, investment trusts, and equities.

---

## Quick Start

```
start.bat
```

That's it. The script creates a virtualenv, installs dependencies, and opens `http://localhost:8080` in your browser. On subsequent runs it skips the install step.

To populate the app with some example holdings so you can test it out:

```
python example_seed.py
```

Then open the app, go to **Holdings → Refresh Prices**, then **Income → Fetch All Dividends**.

---

## Project Layout

```
portfolio-manager/
├── start.bat                   # one-click launch
├── example_seed.py             # imports example portfolio data
├── .env                        # secrets (not committed)
├── .env.example                # template
├── portfolio.db                # SQLite database (auto-created)
│
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── database.py             # connection helper + init_db()
│   ├── config.py               # reads .env
│   ├── requirements.txt
│   │
│   ├── routers/
│   │   ├── positions.py        # CRUD for holdings
│   │   ├── refresh.py          # live price fetching
│   │   ├── dividends.py        # dividend events + calendar
│   │   ├── projections.py      # 10–20 year projection models
│   │   ├── summary.py          # dashboard totals
│   │   ├── settings.py         # cash balance + settings
│   │   ├── export.py           # Excel + PDF export
│   │   └── t212.py             # Trading 212 import
│   │
│   └── services/
│       ├── price_fetcher.py    # 5-step price cascade
│       ├── fx.py               # FX rates to GBP (cached)
│       ├── dividend_fetcher.py # yfinance dividend history + projections
│       └── projector.py        # growth / income / total-return math
│
└── frontend/
    ├── index.html
    ├── css/style.css
    └── js/
        ├── app.js              # UI logic (navigation, charts, modals)
        └── api.js              # fetch() wrappers for every endpoint
```

---

## Features

### Holdings
- Add positions manually or import from Trading 212
- Asset types: `stock`, `bond`, `oeic`, `unit_trust`, `investment_trust`
- Category tag per position: `growth` or `income`
- Stores book cost per unit, ISIN, yfinance ticker, T212 ticker, and free-text notes
- Sortable, filterable table with unrealised P&L and dividend yield columns
- Set a manual price override when automatic fetch fails

### Live Pricing
- **Refresh Prices** button fetches live prices for all 35 positions in parallel (8 threads)
- Per-position refresh button (⟳) in the holdings table
- **Auto-refresh** dropdown in the top bar: Off / 5m / 10m / 30m / 1h (persisted in localStorage)
- **Price staleness indicator**: last-updated cell turns amber if >24 h old, red if >48 h old
- Live "Updated Xm Xs ago · next in Xm Xs" countdown in the header

**Price fetch cascade** (tried in order until one succeeds):
1. **yfinance** — by ticker (e.g. `SHEL.L`, `AV.L`)
2. **T212 live position** — if the position has a `t212_ticker`
3. **OpenFIGI** — maps ISIN → exchange ticker → yfinance (covers LSE stocks with no stored ticker)
4. **FT Markets scrape** — `markets.ft.com/data/funds` by ISIN (best for OEICs, gilts, investment trusts with no yfinance ticker)
5. **Trustnet scrape** — fallback for funds not found on FT Markets

All native prices (GBp pence, USD, EUR, etc.) are converted to GBP via a 5-minute-cached yfinance FX rate. GBp → GBP is a fixed ÷100 (no external call needed).

### Dividends
- **Fetch dividends per position** (₤ button) or **Fetch All Dividends** in bulk
- Pulls historical ex-dates and amounts from yfinance; maps ISIN → ticker via OpenFIGI for funds with no direct ticker
- Detects payment frequency automatically: monthly / quarterly / semi-annual / annual
- Fixes a yfinance quirk: GBp-quoted stocks sometimes return dividend amounts in raw pence — divides by 100 when the amount is >20% of the share price in GBP
- Projects the next 13 months of payments from the most recent historical amount
- **12-Month Income Calendar** — table + bar chart of projected monthly income
- **Received Dividends** log — manually record actual payments received, with history and 12-month total
- Dividend yield stored per position, shown in the holdings table

### Dashboard
- Total portfolio value vs book cost
- Unrealised capital gain/loss (£ and %)
- Income received (trailing 12 months)
- Projected annual income
- Portfolio value vs book cost split card
- Yield on cost and yield on market value
- Asset class allocation doughnut chart
- Capital growth vs dividend income bar chart

### Projections (10–20 year)
Three tabs, each with a Chart.js line/bar chart:
- **Capital Growth** — 4 CAGR scenarios (3%, 5%, 7%, 10%) over 20 years
- **Income Projection** — flat / 3% growth / 5% growth over 10 years
- **Total Return** — reinvested dividends vs cash-out, both over 20 years at 5% growth + 3% income growth

### Export
- **Excel** (`/api/export/report.xlsx`) — holdings table + summary sheet
- **PDF** (`/api/export/report.pdf`) — formatted A4 portfolio report with an automatically generated AI Executive Summary.

### AI Portfolio Insights
- **Local AI Analysis** — Deep, contextual analysis of your portfolio's performance, risk, and dividend sustainability.
- Powered entirely by your local **Ollama** instance so your financial data never leaves your machine.
- Generates a markdown report directly in the browser with no external API calls required.

### Trading 212 Import
- **Import T212** button pulls all open positions from the T212 API
- Deduplicates by `t212_ticker` so re-importing is safe
- Maps T212 asset types: `STOCK/ETF` → `stock`, `BOND` → `bond`, `FUND` → `oeic`

---

## Configuration

Copy `.env.example` to `.env` and fill in your T212 API key if you want the Trading 212 import:

```
# .env
T212_MODE=demo            # "demo" or "live"
T212_DEMO_API_KEY=        # from T212 app → Settings → API
T212_LIVE_API_KEY=        # only needed when T212_MODE=live
```

T212 integration is entirely optional. All other features work without it.

### Local AI Setup (Ollama)
To enable the **AI Insights** tab and the AI-generated PDF summaries, you must have [Ollama](https://ollama.com/) running on your local machine.

1. Download and install Ollama.
2. Run `ollama run llama3` (or any other model like `phi3` or `mistral`) in your terminal to download the model.
3. Open the app **Settings** tab and ensure the Ollama URL is correct (usually `http://localhost:11434`) and the model matches what you downloaded.
4. Note: On Windows, you might need to set `OLLAMA_ORIGINS="*"` in your environment variables if you experience CORS issues (though the backend proxy handles this out-of-the-box).

---

## Database Schema

SQLite file at `portfolio.db` (project root). All timestamps are UTC ISO-8601 strings.

### `positions`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | auto-increment |
| `name` | TEXT NOT NULL | display name |
| `isin` | TEXT | 12-character ISIN |
| `ticker` | TEXT | yfinance ticker (e.g. `AV.L`, `SHEL.L`) |
| `asset_type` | TEXT NOT NULL | `stock` / `bond` / `oeic` / `unit_trust` / `investment_trust` |
| `units` | REAL | shares / nominal face value (gilts) / fund units |
| `book_cost_per_unit` | REAL | average cost in GBP |
| `currency` | TEXT | denomination of book cost (almost always `GBP`) |
| `native_currency` | TEXT | instrument trading currency (`GBP`, `GBp`, `USD`, `EUR`, …) |
| `t212_ticker` | TEXT | T212 internal ticker (e.g. `LLOY_L_EQ`) |
| `category` | TEXT | `growth` or `income` |
| `notes` | TEXT | free text |
| `last_price` | REAL | most recent price **in GBP** |
| `native_price` | REAL | price in the instrument's own currency |
| `last_fx_rate` | REAL | rate used to convert native → GBP |
| `last_price_currency` | TEXT | always `GBP` after a successful refresh |
| `last_price_source` | TEXT | `yfinance` / `ft_markets` / `t212` / `manual` / `pdf_import` |
| `last_price_at` | TEXT | UTC timestamp of last price update |
| `annual_yield` | REAL | dividend yield as a decimal (e.g. `0.0625` = 6.25%) |
| `created_at` / `updated_at` | TEXT | UTC timestamps |

**Gilts note**: `units` = nominal face value in GBP (e.g. £14,976). `last_price` = clean price ÷ 100 (e.g. 97.55 → `0.9755`). Market value = `units × last_price`.

### `dividend_events`

Stores each known ex-date and per-unit amount. Used for the calendar and yield calculation.

| Column | Notes |
|---|---|
| `position_id` | FK → `positions.id` (CASCADE DELETE) |
| `ex_date` | ISO date string |
| `pay_date` | ISO date string (may be NULL) |
| `amount_per_unit` | in GBP (pence normalisation applied before storing) |
| `currency` | inherited from position's `currency` |
| `div_type` | `ordinary` (default) |
| `source` | `yfinance` |

### `received_dividends`

Manually logged actual dividend receipts.

| Column | Notes |
|---|---|
| `position_id` | FK → `positions.id` (CASCADE DELETE) |
| `pay_date` | ISO date string |
| `amount` | total GBP amount received |
| `currency` | usually `GBP` |
| `notes` | optional |

### `portfolio_settings`

Key-value store. Currently used for:

| Key | Value |
|---|---|
| `cash_balance` | cash held outside invested positions (GBP, shown on dashboard) |

---

## API Reference

All routes are prefixed `/api/`. The FastAPI auto-docs are at `http://localhost:8080/docs`.

### Positions

| Method | Path | Description |
|---|---|---|
| GET | `/api/positions` | List all positions with computed fields (P&L, current value, yield) |
| GET | `/api/positions/{id}` | Single position |
| POST | `/api/positions` | Create position |
| PUT | `/api/positions/{id}` | Update position |
| DELETE | `/api/positions/{id}` | Delete position (cascades to dividends) |
| POST | `/api/positions/{id}/price` | Set manual price (body: `{price, currency}`) |

Computed fields returned by GET (not stored in DB):

- `total_book_cost` = `units × book_cost_per_unit`
- `current_value` = `units × last_price`
- `unrealised_pnl` = `current_value − total_book_cost`
- `unrealised_pnl_pct` = `unrealised_pnl / total_book_cost × 100`

### Prices

| Method | Path | Description |
|---|---|---|
| POST | `/api/refresh` | Refresh all positions (parallel, 8 threads) |
| POST | `/api/refresh/{id}` | Refresh single position |

Response includes `status: "ok"` / `"not_found"` / `"fx_error"` per position.

### Dividends

| Method | Path | Description |
|---|---|---|
| GET | `/api/dividends` | All stored dividend events |
| GET | `/api/dividends/upcoming` | Events with ex_date or pay_date ≥ today |
| GET | `/api/dividends/received` | Manually logged receipts |
| POST | `/api/dividends/received` | Log a received dividend |
| DELETE | `/api/dividends/received/{id}` | Remove a receipt |
| POST | `/api/dividends/fetch/{id}` | Fetch dividends for one position from yfinance |
| POST | `/api/dividends/fetch-all` | Fetch dividends for all positions |
| GET | `/api/dividends/calendar` | 12-month projected income calendar |

### Other

| Method | Path | Description |
|---|---|---|
| GET | `/api/summary` | Dashboard totals (book cost, value, P&L, income TTM, projected income, by-asset breakdown) |
| GET | `/api/settings` | Get settings (cash_balance) |
| PUT | `/api/settings` | Update settings |
| GET | `/api/projections` | 20-year growth + 10-year income + total-return projections |
| GET | `/api/export/report.xlsx` | Download Excel report |
| GET | `/api/export/report.pdf` | Download PDF report |
| GET | `/api/t212/preview` | Preview T212 portfolio without importing |
| POST | `/api/t212/import` | Import T212 positions |

---

## Known Limitations and Quirks

### Gilt pricing
UK gilts have no reliable free yfinance ticker. After seeding, gilts keep their PDF prices (`pdf_import` source) until manually overridden. FT Markets scraping via ISIN sometimes works but is not guaranteed.

### OEIC pricing
OEICs (e.g. Artemis, JO Hambro, Man GLG, Premier Miton) have no LSE ticker. The FT Markets scraper fetches by ISIN. FT Markets displays some fund prices as bare decimals (e.g. `2.4800`) in GBP and others in pence with a `p` suffix (e.g. `416.86p`). The scraper distinguishes these:
- `£X.XX` → GBP
- `X.XXp` → GBp (pence → ÷100 for GBP)
- `X.XX` (bare decimal, no suffix) → GBP

### yfinance dividend pence quirk
For GBp-quoted UK stocks, yfinance sometimes returns dividend amounts in raw pence instead of pounds. The dividend fetcher detects this: if `amount_per_unit > last_price_gbp × 0.2`, the amount is divided by 100 before storing.

### yfinance yield percentage quirk
Some UK stocks return `dividendYield` as a percentage (e.g. `6.25` for 6.25%) rather than a decimal (`0.0625`). Values >0.25 are divided by 100.

### FX caching
Exchange rates are cached for 5 minutes on success, 1 minute on failure. A rate unavailable error (`fx_error`) does not write to the database — the previous price is preserved.

### T212 currency hint
The `hint_native_currency` parameter passes the position's stored `native_currency` to the T212 price path, so instruments with non-GBP currencies (e.g. USD stocks) are correctly labelled rather than defaulting to GBP.

---

## Example Portfolio

The `example_seed.py` script adds a few demonstration positions to show how the app handles different asset types. It is idempotent — running it twice skips existing positions.

Positions by type:

| Type | Count | Examples |
|---|---|---|
| UK Gilts (`bond`) | 2 | 4% 2031, 4.5% 2028 |
| Bond/Credit OEICs | 2 | L&G Strategic Bond, Man GLG |
| Investment Trusts | 2 | BRWM, JGGI |
| UK Equities | 3 | Shell, HSBC, Aviva |

Run **Refresh Prices** after seeding to pull the latest live market data.
