# Implementation Plan — Stock Market Dashboard

Derived from [SPEC.md](SPEC.md). Written 25 Nov 2026.

**Changed 27 Nov 2026:** the dashboard is a Power BI report instead of a Python web app. Phase 5 below describes the replacement; the earlier version is in git history.

---

## 0. Decisions to make before coding

These are the places where the spec is silent or where following it literally would cause a problem. My recommendation is in bold; say if you want a different call.

### 0.1 PDF report needs a 7th dependency

The spec says the PDF holds "KPIs + price chart + RSI". Plotly figures cannot be written to an image file by Plotly alone — `fig.write_image()` requires the **kaleido** engine, which is not in the spec's dependency list. Options:

| Option | Cost |
|---|---|
| **Add `kaleido` to requirements** (recommended) | One extra install (~60 MB). Charts in the PDF look identical to the dashboard. |
| Re-draw the two PDF charts in matplotlib | Another dependency anyway, plus duplicate chart code in two libraries. |
| PDF with KPIs and text only, no charts | Weakest deliverable; spec explicitly asks for charts. |

**Recommendation: add `kaleido`.** It stays a zero-API-key project.

### 0.2 Data refresh

Power BI imports CSV files written by `src/export/powerbi_data.py`. Python stays the only place indicators are calculated; DAX is used only for figures that depend on the dates selected in the report. Data is as fresh as the last script run plus a Refresh.

### 0.3 RSI formula: keep the spec's, label it

The spec's RSI uses a plain rolling mean of gains and losses. The industry-standard RSI (Wilder's) uses an exponential smoothing with `alpha = 1/period`, and gives visibly different values. **Build the spec's version as `rsi()` and add Wilder's as `rsi_wilder()`** exported as a second column and chosen by a slicer defaulting to the spec's. Costs ~6 lines and makes the indicator section defensible in the report.

### 0.4 Things the spec does not mention that I will handle

- **MultiIndex columns.** `yf.download()` with more than one ticker returns a two-level column index. The fetcher will flatten to a tidy single-ticker frame so every downstream module sees the same shape.
- **`.info` is slow and flaky.** The company-info call (sector, market cap, P/E) hits an unofficial endpoint that intermittently returns `{}` or rate-limits. The fetcher will try `fast_info` first, fall back to `.info`, and return `None` per missing field so KPI cards show "—" instead of crashing.
- **Crypto and `.NS` tickers.** `BTC-USD` has no P/E, sector or market cap; Indian tickers trade in INR. KPI cards will read the currency off the ticker metadata and degrade gracefully on missing fields.
- **Short date ranges.** SMA(200) over a 1-month range is all NaN. Charts will skip an overlay whose window exceeds the available rows and show a one-line caption saying why, rather than drawing an empty trace.
- **Bad ticker input.** An unknown symbol returns an empty frame, not an exception. The export script will report it and carry on with the other tickers.

---

## 1. Build order

Nine phases, each one runnable and checkable before the next. Phases 1–4 are the data core, 5–6 the dashboard and export, 7–9 the deliverables.

### Phase 1 — Scaffold

- `requirements.txt` — the spec's six plus `kaleido` (pending 0.1), each pinned to a known-good minor version.
- `.gitignore` — `__pycache__/`, `.venv/`, `deliverables/*.pdf` excluded only if generated (keep the committed report).
- `src/config.py` — defaults in one place: default ticker `AAPL`, the five demo tickers from the spec, date-range presets (`1W/1M/3M/6M/1Y/5Y/Custom`) as day offsets, indicator windows (SMA 20/50/200, EMA 12/26, RSI 14, MACD 12/26/9, Bollinger 20/2), chart colour constants, cache TTL.
- `src/` package `__init__.py` files.

Creates a `.venv` in the project folder and installs the requirements into it, so nothing touches your system Python.

**Check:** `python -c "import src.config"` works inside the venv.

### Phase 2 — Data layer

- `src/data/fetcher.py`
  - `fetch_ohlcv(ticker, start, end) -> pd.DataFrame` — single-ticker OHLCV, flattened columns, `DatetimeIndex` named `Date`, cached.
  - `fetch_many(tickers, start, end) -> dict[str, pd.DataFrame]` — for comparison and correlation tabs.
  - `fetch_company_info(ticker) -> dict` — name, sector, market cap, P/E, 52-week high/low, currency; every value nullable, cached with a longer TTL.
  - `resolve_date_range(preset, custom_start, custom_end) -> (start, end)`.
- `src/data/cleaner.py`
  - `clean_ohlcv(df)` — drop all-NaN rows, forward-fill interior gaps (holidays), cast numerics, sort by date, drop duplicate dates, validate that `High >= Low` and the frame is non-empty; raises a typed `DataQualityError` the app can catch.

**Check:** a throwaway script in the scratchpad fetches AAPL 1Y, RELIANCE.NS 6M and BTC-USD 3M, printing shape, dtypes and null counts for each.

### Phase 3 — Indicators

One module per indicator, exactly as the spec lays out, pure functions on a `pd.Series`:

- `moving_averages.py` — `sma(series, window)`, `ema(series, span)`
- `rsi.py` — `rsi(series, period=14)`, `rsi_wilder(series, period=14)`
- `macd.py` — `macd(series) -> (macd_line, signal, histogram)`
- `bollinger.py` — `bollinger_bands(series, window=20, num_std=2) -> (upper, middle, lower)`
- `returns.py` — `daily_returns`, `cumulative_returns`, `annualized_volatility(series, periods=252)`, `monthly_returns_pivot(series) -> DataFrame` (years × months, for the heatmap)

Plus `src/indicators/__init__.py` exposing `enrich(df) -> DataFrame` — takes a clean OHLCV frame and returns it with every indicator added as a column. That single function is what the CSV export, the data table and the notebook all use, so the 8+ derived columns the spec promises are produced in exactly one place.

**Check:** hand-computed assertions on a tiny synthetic series — SMA(3) of `[1,2,3,4]`, RSI of a strictly rising series = 100, MACD of a constant series = 0, Bollinger middle == SMA. Run as a plain `assert` script; no test framework dependency added.

### Phase 4 — Charts

One module per chart, each a pure `(data, options) -> plotly.graph_objects.Figure` with no UI imports, so the notebook and the PDF can reuse them:

- `candlestick.py` — OHLC candles, green/red, volume subplot below, shared x-axis, rangeslider off.
- `price_chart.py` — close line plus whichever of SMA 20/50/200, EMA 12/26, Bollinger the caller enables; Bollinger drawn as a filled band.
- `volume_chart.py` — volume bars coloured by up/down day, 20-day average volume line.
- `rsi_chart.py` — RSI line, shaded 70/30 bands, y-axis fixed 0–100.
- `macd_chart.py` — MACD line, signal line, histogram bars coloured by sign.
- `comparison.py` — 2–5 tickers normalised to 100 at the first common date (not each series' own first date — tickers have different trading calendars; this matters for `.NS` versus US versus crypto).
- `heatmap.py` — monthly returns grid, years as rows, diverging red/green colour scale centred on zero.
- `correlation.py` — correlation of daily returns (not raw prices; price correlation is dominated by shared trend and is close to meaningless), annotated heatmap.

A shared `src/charts/theme.py` holds the layout template so all eight charts look like one product.

**Check:** a script writes all eight figures to HTML in the scratchpad; I open them in the browser pane and look at each.

### Phase 5 — Power BI dashboard

- `src/export/powerbi_data.py` — fetch every configured ticker (5 years), `enrich()` it and write the CSV tables into `powerbi/data/`.
- `powerbi/StockDashboard.pbip` — semantic model (tables, relationships, DAX measures) and the five report pages in SPEC.md.
- Slicers for ticker, date range, overlays and RSI formula. KPI cards follow the selected ticker.
- Candlestick: the built-in visuals show open, high, low and close as lines; a true candlestick needs a custom visual added by hand.

**Check:** run the export, open the project in Power BI Desktop, refresh, compare the measures with the Python figures for the same dates, and look at all five pages.

### Phase 6 — Export

- CSV: the enriched frames written by the export script.
- `src/export/pdf_report.py` — `build_report(ticker, info, df, kpis) -> bytes`: title and date, KPI table, price-with-overlays chart, RSI chart, and a rules-based commentary paragraph (RSI zone, price versus SMA-50/200, MACD sign, volatility versus its own median). The commentary is labelled as a mechanical summary of indicators, **not investment advice**. The export script writes one PDF per ticker.

**Check:** generate the PDF for AAPL and open it.

### Phase 7 — Notebook and script walkthroughs

- `deliverables/walkthrough.py` — the whole flow top to bottom with printed output at each stage: fetch → clean → enrich → each chart → save figures.
- `deliverables/walkthrough.ipynb` — the same flow as narrated cells with inline charts. Built by converting the script and adding markdown, so the two never drift.

**Check:** run the script end to end; execute the notebook top to bottom with no errors.

### Phase 8 — Project report

`deliverables/generate_report.py` produces `Project_Report.pdf`: business understanding, architecture, the spec's flowchart, the indicator table, screenshots of the Power BI report, and the outcome. Screenshots go in `deliverables/screenshots/`.

### Phase 9 — README and final pass

`README.md`: what it is, a screenshot, install and run, project structure, indicator reference, sample tickers, and a short "known limits" section (Yahoo rate limits, `.info` gaps, indicators are not advice). Then a read-through of every module for dead code and docstring accuracy.

---

## 2. Order of work and what blocks what

```
Phase 1 (scaffold)
   └─> Phase 2 (data) ──> Phase 3 (indicators) ──> Phase 4 (charts)
                                                        │
                                                        ├─> Phase 5 (Power BI) ─> Phase 6 (export)
                                                        │                          │
                                                        └─> Phase 7 (walkthroughs) │
                                                                                   │
                                            Phase 8 (report) <────── screenshots ──┘
                                                   │
                                                   └─> Phase 9 (README)
```

Phases 2, 3 and 4 are a strict chain. Phase 7 needs only the charts, so it can be done alongside the app work.

## 3. What "done" looks like

- The Power BI project opens, refreshes, and shows populated KPI cards and five working pages.
- AAPL, TSLA, RELIANCE.NS, TCS.NS and BTC-USD all load; crypto and Indian tickers show no errors and no misleading blanks.
- CSV export contains OHLCV plus at least 8 indicator columns; PDF export opens with KPIs and two charts.
- Notebook runs clean from top to bottom.
- `Project_Report.pdf` exists with real screenshots.
- Every indicator formula matches the spec, verified by the Phase 3 assertions.

## 4. Known risks

| Risk | Handling |
|---|---|
| Yahoo Finance rate-limits or changes shape | All access is behind `fetcher.py`; caching keeps call volume low. One module to fix if the endpoint shifts. |
| `.info` returns empty for a valid ticker | `fast_info` first, nullable fields, "—" in the report. |
| `kaleido` install trouble on Windows/py3.13 | Fallback is a chart-free PDF (0.1), decided before Phase 6 rather than mid-build. |
| Power BI file paths differ between machines | One `DataFolder` parameter in the model. |
| Notebook and script drifting apart | Notebook generated from the script. |

## 5. Open questions for you

1. **Add `kaleido`** so the PDF can hold charts? (0.1)
2. **Should this folder be a git repo?** It is not one now. If you want commits and a PR flow I will `git init` first — your global workflow rules are about the Flowmatic repos and do not cover this folder, so I would rather ask than assume.
3. **Virtualenv location** — `.venv` inside this folder, or do you have an environment you want used?
