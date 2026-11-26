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
