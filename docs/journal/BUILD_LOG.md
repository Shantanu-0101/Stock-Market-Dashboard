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
