# Error log — Stock Market Dashboard

Newest entry last. Timestamps are IST.

## 26 Nov 2026, 08:20 — `fast_info` has no `fiftyTwoWeekHigh` key

**What happened.** Writing `fetch_company_info` I reached for `fast_info["fiftyTwoWeekHigh"]` / `["fiftyTwoWeekLow"]`, the names `.info` uses. yfinance 1.8.0's `FastInfo` raises `"'fiftyTwoWeekHigh' not valid key"`; the 52-week range is `yearHigh` / `yearLow` there, and average volume is `threeMonthAverageVolume` / `tenDayAverageVolume`, not `averageVolume`.

**Why it mattered.** Inside the `try/except Exception` that guards the fast path, a wrong key is not a crash — it silently abandons every remaining fast field and leaves the KPI row showing em dashes for a ticker that had the data. Caught only by printing `fast_info.keys()` against the live endpoint before writing the code.

**Fix.** The fast path reads `fast_info.keys()` once and looks up through a `fast_get` helper that returns `None` for an absent key, so a future key rename degrades one field instead of the whole block. `.info`'s own spellings are kept for the slow fallback, where they are correct.
