# Build log — Stock Market Dashboard

Newest entry last. Timestamps are IST.

## 26 Nov 2026, 08:30 — Phase 2: data layer

Built the two modules Phase 2 of [IMPLEMENTATION_PLAN.md](../../IMPLEMENTATION_PLAN.md) calls for.

**`src/data/cleaner.py`**
- `DataQualityError(ValueError)` — one typed error with end-user wording, because the app shows `str(exc)` verbatim.
- `clean_ohlcv(df, ticker)` enforces the contract everything downstream relies on: flattened columns, sorted/unique/tz-naive `Date` index, exactly `Open, High, Low, Close, Volume`, float64 prices, int64 volume, no NaN close, `High >= Low`, at least one row.
- Decisions inside it: interior OHLC gaps are forward-filled while missing volume becomes 0 (never forward-filled — a carried-over volume is a fabricated trade count); High/Low inversions are swapped rather than dropped, so the series keeps no hole; duplicate dates keep the last row, since a repeat is Yahoo's revision.

**`src/data/fetcher.py`** — the only module that talks to Yahoo.
- `fetch_ohlcv(ticker, start, end)` — one cleaned single-ticker frame, `auto_adjust=True` so splits do not leave a false gap in the indicators.
- `fetch_many(tickers, start, end)` — returns `(frames, errors)`, **not** the bare dict the plan sketched. One bad symbol in a five-way comparison must not blank the whole tab, and the tab cannot report what it does not receive. Fetches per ticker rather than batching, so each symbol gets its own cache entry.
- `fetch_company_info(ticker)` — `fast_info` first for the quote fields, `.info` only for long name / sector / industry / trailing P/E, every field nullable, never raises. A missing KPI card must not fail a page that still has prices.
- `resolve_date_range(preset, custom_start, custom_end)` — adds one day to the end, since yfinance treats `end` as exclusive and the user means "include today".
- `normalise_ticker` — strip and upper-case, because people type `aapl`.
- Caching is `@st.cache_data(ttl=...)` wrapped in `_cache()`, which degrades to a no-op when there is no Streamlit runtime, so the notebook and plain scripts import these unchanged (decision 0.2 of the plan).

**Check (ran live against Yahoo, 26 Nov 2026):** AAPL 1Y → 251 rows, RELIANCE.NS 6M → 123 rows (INR, 24 Nov holiday absent as expected), BTC-USD 3M → 91 rows. All three: zero nulls, correct dtypes, monotonic unique index, `High >= Low` everywhere. Crypto returns `sector`/`pe_ratio` as `None` and does not crash. `fetch_many(["AAPL","tsla","AAPL","NOTATICKER123"])` loaded 2 frames, de-duplicated the repeat, and reported the bad symbol in `errors`. All five `resolve_date_range` failure modes raise `DataQualityError`.

Not done in this phase: indicators, charts, app — Phases 3 to 5.

## 26 Nov 2026, 09:40 — Phase 3: indicators

Five formula modules plus the `enrich()` seam, per Phase 3 of the plan. All pure functions on a `pd.Series`, no Streamlit or Plotly import anywhere, so the app, the notebook and the PDF generator share one implementation.

- **`moving_averages.py`** — `sma`, `ema`. `min_periods` left at its default so a short range shows visible gaps rather than a quietly wrong line.
- **`rsi.py`** — `rsi` (the spec's rolling mean) and `rsi_wilder` (exponential, `alpha = 1/period`), selected through `RSI_VARIANTS` and defaulting to the spec's, per decision 0.3. Both share one gain/loss split and one RS→RSI conversion.
- **`macd.py`** — `macd` returning line, signal and histogram; raises if `fast >= slow`, which would invert every signal.
- **`bollinger.py`** — `bollinger_bands` plus `percent_b` (where price sits in the envelope) and `bandwidth` (scale-free volatility, so a reading in rupees and one in dollars can be compared). `ddof` exposed, defaulting to pandas' sample std as the spec's snippet produces.
- **`returns.py`** — `daily_returns`, `cumulative_returns`, `annualized_volatility`, `monthly_returns_pivot` as the plan asked, plus `period_return`, `ytd_return`, `rolling_volatility` and `drawdown` that the KPI row and the PDF commentary need.
- **`__init__.py`** — `enrich(df)` adds all **19** indicator columns (the spec asks the CSV to carry at least 8), `indicator_columns()` names them without recomputing, `available_windows()` is the short-range guard, `periods_per_year_for()` picks the annualisation divisor.

Three judgment calls worth recording:

1. **RSI gains/losses use `clip`, not the spec's `delta.where(delta > 0, 0.0)`.** `where` converts `diff()`'s leading `NaN` into a real `0.0`, which gets averaged into the first window and understates the first RSI reading. `clip` keeps the `NaN`, so RSI(14) first appears on row 14 instead of row 13 — asserted in the check file. Arithmetically identical everywhere else.
2. **A flat window returns RSI 50, not `NaN`.** The raw formula gives 0/0. The departure is one `mask()` call, documented in the docstring, and it keeps a hole out of the middle of the chart for a thinly traded stock.
3. **Crypto annualises on 365 days, not 252.** `periods_per_year_for(quote_type)` reads the asset type from `fetch_company_info`. Using 252 for `BTC-USD` understates its annualised volatility by roughly 23%.

Also: `enrich` adds every column even when the window exceeds the row count, filling with `NaN`. Dropping them would make the frame's shape depend on the date range and silently cost the CSV user a column; the charts ask `available_windows()` what is safe to draw.

**Check:** `deliverables/check_indicators.py` — **82 hand-computed assertions, all passing**. SMA(3) of [1,2,3,4] = [-,-,2,3]; EMA(2) of [1,2,3] = [1, 5/3, 23/9] from the recursion; RSI 100 on a rising series, 0 on a falling one, 50 on a flat one, 50 on a worked 3-period example; MACD identically 0 on a constant series and histogram == line - signal; Bollinger middle == SMA with bands at +/- 2 sample sd (sqrt(5/3) checked by hand); +10% then -10% compounding to -1%; drawdown -25%; the monthly pivot's cells and blank-vs-zero behaviour. The last block runs the whole thing against a live AAPL year, which is the only way to catch a dtype or column-name mismatch at the Phase 2/Phase 3 seam; it skips rather than fails when offline.

Not done in this phase: charts, app, export — Phases 4 to 6.

## 26 Nov 2026, 08:50 — Phase 4: charts

Eight chart modules plus a shared theme, per Phase 4 of the plan. Every one is
a pure `(data, options) -> plotly.graph_objects.Figure`; there is no Streamlit
import anywhere in `src/charts/`, so `app.py`, the PDF generator and the
notebook all call the same functions and cannot drift.

- **`theme.py`** — registers one Plotly template (`stockdash`) extending
  `plotly_white`, and `apply_theme()`, which every chart ends with. Also
  `empty_figure()` and `skip_caption()`.
- **`price_chart.py`** — close line plus any of SMA 20/50/200, EMA 12/26 and
  Bollinger, the band drawn as one filled region rather than three competing
  lines.
- **`candlestick.py`** — candles over a volume subplot on a shared x-axis,
  rangeslider off. `show_volume=False` gives the single panel the PDF needs.
- **`volume_chart.py`** — bars coloured by the day's direction with the
  20-day average line.
- **`rsi_chart.py`** — RSI on a fixed 0–100 axis with shaded 70/30 zones.
- **`macd_chart.py`** — line, signal and sign-coloured histogram, all on one
  y-axis.
- **`comparison.py`** — 2–5 tickers rebased to 100, plus `first_common_date()`.
- **`heatmap.py`** — the monthly-returns grid and the daily-returns histogram.
- **`correlation.py`** — annotated matrix, plus `returns_correlation()`.

Five judgment calls worth recording:

1. **Charts read indicator columns, they never recompute.** `price_chart` and
   `macd_chart` take the enriched frame's `SMA_50`, `MACD_HIST` and so on, so
   the line on screen and the number in the exported CSV are the same number
   by construction.
2. **Comparison rebases to the first *common* date**, found by intersecting
   every ticker's index. Rebasing each series to its own first row looks right
   and is wrong: US markets, `.NS` and crypto keep different calendars, so
   AAPL's first row may be a day RELIANCE.NS did not trade, and the error
   compounds across the range.
3. **The correlation matrix is computed on returns, not prices**, departing
   from the spec's wording. Two unrelated stocks that both drifted up over a
   year show a price correlation near 0.9 because the shared trend dominates.
   The check file asserts the difference rather than just asserting it runs.
4. **Nothing raises when there is no data to draw.** Every chart returns a
   themed figure carrying an explanation — "these tickers share no common
   trading day in this range" — so the app renders results unconditionally
   and the user reads why a panel is blank.
5. **The returns histogram lives in `heatmap.py`** rather than a ninth module.
   The spec puts both on the Returns Analysis tab and both answer the same
   question — how the returns are distributed — one by calendar month, one by
   magnitude.

The fixed y-axis on RSI and the fixed −1..1 scale on the correlation matrix
are the same decision twice: both quantities are bounded by definition, and
autoscaling makes a quiet series look violent and a weak correlation look
strong.

**Check:** `deliverables/check_charts.py` — **46 structural assertions, all
passing**, then every figure written to HTML and opened in the browser. The
assertions cover trace counts and types, the RSI axis range, the rangeslider
being off on both candlestick rows, the short-range skip captions naming the
window and the row count, every comparison series sitting at exactly 100 on
the shared base date, the histogram being coloured by sign, and the
returns-vs-price correlation difference. `--live` reruns the lot against real
Yahoo data; today that was AAPL (753 rows), RELIANCE.NS (739) and BTC-USD
(1094), all three rendering with no crashes and no empty traces.

The visual pass found four layout faults the assertions could not: a
horizontal legend listing traces in reverse, so "Close" sat in the middle of
its own overlays; the legend overlapping the title on 300px panels; the
caption annotation landing on top of the x-axis title, because Plotly's
annotation `y` is a fraction of the plot area and a fixed −0.16 means
different pixel offsets at different heights; and RELIANCE.NS clipped off the
correlation matrix's y-axis. All four fixed in `theme.py` and the two heatmap
modules. The preview HTML goes to `deliverables/chart_preview/`, now
gitignored.

Not done in this phase: the app, export and deliverables — Phases 5 to 9.

## 26 Nov 2026, 08:59 — Phase 5: Streamlit app

`app.py`, plus `src/formatting.py` and a pinned `.streamlit/config.toml`. The
app orchestrates and nothing else: it reads widgets, calls the data layer,
hands the frame to `enrich()`, passes it to the chart functions and lays the
results out. No indicator arithmetic and no figure construction in this file.

- **Sidebar** — ticker with a demo-symbol caption, date preset plus custom
  pickers, per-window SMA/EMA checkboxes, Bollinger toggle, the RSI variant
  selectbox from decision 0.3, a compare multiselect capped so the total
  stays at five, and the export buttons.
- **KPI row** — eight cards: price with its daily change, 52-week high and
  low, YTD return, market cap, P/E, average volume and annualised volatility.
- **Five tabs** exactly as the spec's wireframe lays them out, then an
  expandable data table of the enriched frame.
- **`src/formatting.py`** — `format_money`, `format_compact`, `format_percent`,
  `format_volume`, `title_case_name`. Presentation only, outside `app.py`
  because the Phase 6 PDF must print the same KPI row with the same rounding
  and the same em dash for a missing value.

Four judgment calls worth recording:

1. **Charts are rendered with `theme=None`.** Streamlit's default
   `theme="streamlit"` overwrites a figure's template — colours, fonts,
   legend placement, margins — so the dashboard and the PDF would show
   visibly different charts from the same call. `None` keeps the template
   `src/charts/theme.py` registers, which is the entire reason it exists.
2. **The page is pinned to the light base** in `.streamlit/config.toml`. The
   charts are built on `plotly_white`; on a dark OS theme Streamlit would
   otherwise put white charts on a near-black page.
3. **Price and the daily change come from the fetched frame, not from
   `info`.** `fast_info`'s `lastPrice` is a live quote that disagrees with
   the last row of a historical range the user picked, and a card that
   contradicts the chart under it is worse than one that is slightly stale.
   The 52-week range is the opposite — a property of the stock, not of the
   window — so it comes from `info`, falls back to the frame's own high/low,
   and the caption says which of the two is on screen.
4. **The comparison set always includes the main ticker**, so Tab 4 shows the
   stock the rest of the page is about rather than only its peers.

The PDF button is present but disabled, with a help note pointing at Phase 6.
A button that is visible and dead until a later phase is worse than one that
says why it is dead.

**Check (ran the real app, not just a typecheck):** `streamlit run app.py`,
then every tab clicked through in the browser at 1440x900.

- AAPL 1Y: all eight KPIs populated, five tabs rendering, 251 rows and 24
  columns in the data table.
- AAPL 1W: SMA 20/50 and the Bollinger band correctly skipped with captions
  naming the rows needed; the correlation matrix carries its "only 4
  overlapping days" warning.
- BTC-USD: P/E renders as an em dash, volatility annualises on 365 periods
  rather than 252, seven rows in a week because crypto trades weekends.
- `NOTATICKER123`: the error panel with the ticker-format hint, no traceback,
  no half-drawn page. The only entry in the server log is yfinance's expected
  404 for that symbol.

Not done in this phase: the PDF generator, notebook, project report and
README — Phases 6 to 9.

## 26 Nov 2026, 09:28 — Phase 6: export

The PDF report, and the sidebar button that was disabled in Phase 5.

- **`src/export/pdf_report.py`** — `build_report(ticker, info, df, kpis)`
  returns a one-page A4 PDF: heading, the eight KPI cards, price with SMA
  50/200 and Bollinger, RSI, the indicator summary and the disclaimer.
- **`src/export/commentary.py`** — the rules-based sentences: RSI zone, close
  against SMA 50/200, MACD sign and signal position, 21-day volatility against
  its own median (within 10% counts as "in line"). It describes and never says
  buy, sell or hold. A range too short for an indicator says so.
- **`src/kpis.py`** — the KPI logic moved out of `app.py`, so the page and the
  PDF print the same cards from one function.
- **`app.py`** — the PDF button passes a callable to `st.download_button`, so
  the few seconds of chart export are paid on click, not on every rerun.
- **CSV** — already wired in Phase 5; confirmed 251 rows with the 19
  indicator columns for AAPL 1Y.

Judgment calls:

1. **Built-in PDF fonts with Windows-1252**, not an embedded Unicode font,
   so the report depends on no font file. The rupee sign prints as "Rs ";
   characters outside the code page print as "?".
2. **A failed chart export does not fail the report.** kaleido needs a local
   Chrome; without it each chart is replaced by a line saying why.
3. **The PDF chart overlays are fixed** (SMA 50/200, Bollinger) rather than
   following the sidebar, because they are what the summary talks about. The
   RSI variant does follow the sidebar and is named on the page.

**Check:** `deliverables/check_export.py`, 28 assertions passing;
`check_charts.py` passing. Live reports generated and read for AAPL 1Y,
RELIANCE.NS 1Y and BTC-USD 1W, one page each. In the running app, both export
buttons appear and every tab's legend clears its title at 1440 wide. The
button callables were run from `app.main()` on a worker thread; the browser
download click itself was not exercised.
