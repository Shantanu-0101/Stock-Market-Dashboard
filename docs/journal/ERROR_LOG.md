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
