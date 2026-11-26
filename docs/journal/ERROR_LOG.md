# Error log — Stock Market Dashboard

Newest entry last. Timestamps are IST.

## 26 Nov 2026, 08:20 — `fast_info` has no `fiftyTwoWeekHigh` key

**What happened.** Writing `fetch_company_info` I reached for `fast_info["fiftyTwoWeekHigh"]` / `["fiftyTwoWeekLow"]`, the names `.info` uses. yfinance 1.8.0's `FastInfo` raises `"'fiftyTwoWeekHigh' not valid key"`; the 52-week range is `yearHigh` / `yearLow` there, and average volume is `threeMonthAverageVolume` / `tenDayAverageVolume`, not `averageVolume`.

**Why it mattered.** Inside the `try/except Exception` that guards the fast path, a wrong key is not a crash — it silently abandons every remaining fast field and leaves the KPI row showing em dashes for a ticker that had the data. Caught only by printing `fast_info.keys()` against the live endpoint before writing the code.

**Fix.** The fast path reads `fast_info.keys()` once and looks up through a `fast_get` helper that returns `None` for an absent key, so a future key rename degrades one field instead of the whole block. `.info`'s own spellings are kept for the slow fallback, where they are correct.

## 26 Nov 2026, 09:25 — two of my own checks were not checking anything

**What happened.** The first run of `deliverables/check_indicators.py` reported 74 passes, but two of them were worthless. One ended in `... is None or True`, which passes unconditionally — written because the assertion depended on the current date and I patched around it instead of fixing it. Another built an `alternating` series that was never used, leaving a reader to think the volatility scaling was checked against it.

**Why it mattered.** A green check file is the evidence the project report cites for "every indicator formula matches the spec". A tautological assertion in it is worse than a missing one: it claims coverage that does not exist.

**Fix.** The date-dependent check was replaced with three real ones — `ytd_return` on an empty series, on a non-datetime index, and on a series spanning a year boundary where the base must be the last close before 1 January (50 → 150 across the boundary = +50%, with the pre-boundary row ignored). The dead variable is gone. Count went 74 → 82, all meaningful.

## 26 Nov 2026, 08:45 — two Phase 4 checks tested my test, not the chart

**What happened.** The first run of `deliverables/check_charts.py` reported
two failures: "too-short range explains itself" (RSI) and "a three-day range
explains itself" (heatmap). Neither was a bug in the charts.

The RSI check sliced `enriched.tail(5)` — a frame enriched over 900 rows and
*then* cut down, so its `RSI_14` column was full of real values computed from
history the chart was no longer being shown. In the app a short range is a
short fetch, so `enrich` runs on the few rows and the column is genuinely all
NaN. The check had constructed a state the app can never produce.

The heatmap check asserted that three days produce no grid. Three days inside
one calendar month are one real, if thin, monthly return, and drawing that
single cell is correct.

**Why it mattered.** Both would have been "fixed" by loosening the chart code
— adding a row-count guard to `rsi_chart` that the data layer already
enforces, or making `returns_heatmap` refuse part-months and so blank the
current month of every normal range. A failing check is not automatically a
failing module, and a check built on an impossible input is worse than no
check: it pushes the code toward handling cases that cannot occur.

**Fix.** The RSI check now enriches a 5-row frame, which is what a one-week
range actually gives, and additionally asserts the message names the rows it
needed. The heatmap check now asserts the part-month *does* draw its one cell
and one year row, with a separate check that a genuinely empty series gets the
explanation figure. 44 checks → 46, all meaningful.

## 26 Nov 2026, 08:48 — the caption annotation sat on the x-axis title

**What happened.** The returns histogram's caption ("899 trading days. Mean
−0.11% a day…") overlapped the "Daily return" axis title, and on the MACD
panel the legend overlapped the chart title. Both only visible by opening the
HTML; every structural assertion passed.

**Why it mattered.** Plotly annotation coordinates with `yref="paper"` are a
fraction of the **plot area**, not of the figure. `y=-0.16` is ~24px below the
axis on a 520px chart and ~10px on a 300px one, where the axis title needs 30.
One constant cannot serve both heights, and the 300px panels are exactly the
ones the spec puts two of on a tab.

**Fix.** `apply_theme` now derives the bottom margin and the annotation offset
from the figure height: a fixed 62px gap converted into paper units via the
computed plot height, and a taller top margin on short charts that carry a
legend. Also set `legend.traceorder="normal"` — a horizontal Plotly legend
otherwise lists traces in reverse, putting "Close" in the middle of its own
overlays — and `automargin=True` on both heatmap axes, since RELIANCE.NS is
twice the width of AAPL and was being clipped.
