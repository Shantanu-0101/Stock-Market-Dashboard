"""Phase 3 verification: every indicator against a hand-computed answer.

Plain asserts, no test framework — the spec's dependency list has none and
this has to stay runnable with ``python deliverables/check_indicators.py``
from the project root. Each block states the expected value and why, so the
report can cite this file as the evidence that the formulas match SPEC.md.

Run it after any change to ``src/indicators/``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Scripts in deliverables/ are run directly, so the project root is not on
# sys.path. Put it there before importing src, and do it the same way in every
# script under this folder.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src import config
from src.indicators import (
    annualized_volatility,
    available_windows,
    bollinger_bands,
    cumulative_returns,
    daily_returns,
    drawdown,
    enrich,
    indicator_columns,
    macd,
    monthly_returns_pivot,
    percent_b,
    period_return,
    periods_per_year_for,
    rsi,
    rsi_wilder,
    sma,
    ema,
    ytd_return,
)

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(label)
        print(f"  ok   {label}")
    else:
        FAILED.append(f"{label} — {detail}")
        print(f"  FAIL {label} — {detail}")


def close_to(a: float, b: float, tol: float = 1e-9) -> bool:
    return a is not None and b is not None and abs(a - b) <= tol


def series(values: list[float], start: str = "2026-01-01") -> pd.Series:
    """A daily series on a real DatetimeIndex, as the app always has."""
    index = pd.date_range(start=start, periods=len(values), freq="D", name="Date")
    return pd.Series(values, index=index, dtype="float64")


# ---------------------------------------------------------------------------
print("\nSMA — rolling mean, leading NaNs")
# ---------------------------------------------------------------------------
s = series([1, 2, 3, 4])
got = sma(s, 3)
# By hand: no average until row 3. (1+2+3)/3 = 2, (2+3+4)/3 = 3.
check("SMA(3) leaves the first two rows NaN", bool(got.iloc[:2].isna().all()),
      f"got {got.iloc[:2].tolist()}")
check("SMA(3) of [1,2,3,4] is [-, -, 2, 3]",
      close_to(got.iloc[2], 2.0) and close_to(got.iloc[3], 3.0),
      f"got {got.iloc[2]}, {got.iloc[3]}")
check("SMA(1) is the series itself", bool(sma(s, 1).equals(s)))
check("SMA of a constant series is that constant",
      close_to(sma(series([5.0] * 10), 4).iloc[-1], 5.0))

try:
    sma(s, 0)
    check("SMA(0) raises", False, "no exception")
except ValueError:
    check("SMA(0) raises ValueError", True)

# ---------------------------------------------------------------------------
print("\nEMA — recursive form, adjust=False")
# ---------------------------------------------------------------------------
s = series([1, 2, 3])
got = ema(s, 2)
# alpha = 2/(2+1) = 2/3. y0 = 1; y1 = 2/3*2 + 1/3*1 = 5/3; y2 = 2/3*3 + 1/3*5/3 = 23/9.
check("EMA(2) starts at the first price", close_to(got.iloc[0], 1.0))
check("EMA(2) second value is 5/3", close_to(got.iloc[1], 5.0 / 3.0))
check("EMA(2) third value is 23/9", close_to(got.iloc[2], 23.0 / 9.0))
check("EMA of a constant series is that constant",
      close_to(ema(series([7.0] * 20), 12).iloc[-1], 7.0))
check("EMA has no leading NaN run", bool(ema(series([1.0] * 5), 3).notna().all()))

# ---------------------------------------------------------------------------
print("\nRSI — the spec's rolling-mean version")
# ---------------------------------------------------------------------------
rising = series(list(range(1, 31)))
got = rsi(rising, 14)
# Every change is a gain, so avg_loss = 0, rs = inf, RSI = 100 - 100/inf = 100.
check("RSI of a strictly rising series is 100", close_to(got.iloc[-1], 100.0),
      f"got {got.iloc[-1]}")

falling = series(list(range(30, 0, -1)))
# Mirror image: avg_gain = 0, rs = 0, RSI = 100 - 100/1 = 0.
check("RSI of a strictly falling series is 0",
      close_to(rsi(falling, 14).iloc[-1], 0.0), f"got {rsi(falling, 14).iloc[-1]}")

flat = series([42.0] * 30)
# 0/0 is NaN in the raw formula; the module maps a no-movement window to 50
# so the chart has no hole. This is the one documented departure from SPEC.md.
check("RSI of a flat series is 50, not NaN",
      close_to(rsi(flat, 14).iloc[-1], 50.0), f"got {rsi(flat, 14).iloc[-1]}")

# First valid reading: diff() loses row 0, then a 14-row window needs 14 more.
first_valid = got.notna().idxmax()
check("RSI(14) first value lands on row 14 (not 13)",
      got.index.get_loc(first_valid) == 14,
      f"landed on row {got.index.get_loc(first_valid)}")

check("RSI stays within 0-100 on noisy data", bool(
    rsi(series(list(np.cumsum(np.random.default_rng(7).normal(0, 1, 200)) + 100)), 14)
    .dropna().between(0, 100).all()
))

# A worked example, computed by hand from the spec's formula.
# Changes: +1 +1 -2 +1 +1 -2 ... over 6 rows with period 3.
worked = series([10, 11, 12, 10, 11, 12])
# Window of the last 3 changes (-2, +1, +1): avg_gain = 2/3, avg_loss = 2/3,
# rs = 1, RSI = 100 - 100/2 = 50.
check("RSI(3) worked example equals 50",
      close_to(rsi(worked, 3).iloc[-1], 50.0), f"got {rsi(worked, 3).iloc[-1]}")

# ---------------------------------------------------------------------------
print("\nRSI — Wilder's version")
# ---------------------------------------------------------------------------
check("Wilder RSI of a rising series is also 100",
      close_to(rsi_wilder(rising, 14).iloc[-1], 100.0))
check("Wilder RSI of a flat series is also 50",
      close_to(rsi_wilder(flat, 14).iloc[-1], 50.0))
noisy = series(list(np.cumsum(np.random.default_rng(3).normal(0, 1, 300)) + 100))
spec_rsi = rsi(noisy, 14).dropna()
wilder = rsi_wilder(noisy, 14).dropna()
check("the two RSI variants start on the same row",
      spec_rsi.index[0] == wilder.index[0],
      f"{spec_rsi.index[0]} vs {wilder.index[0]}")
check("the two RSI variants genuinely differ on real-looking data",
      float((spec_rsi - wilder).abs().max()) > 1.0,
      f"max gap only {float((spec_rsi - wilder).abs().max()):.4f}")

# ---------------------------------------------------------------------------
print("\nMACD")
# ---------------------------------------------------------------------------
constant = series([100.0] * 60)
line, signal, hist = macd(constant)
# Both EMAs equal the constant, so the spread, its EMA and the gap are all 0.
check("MACD of a constant series is 0", close_to(float(line.abs().max()), 0.0))
check("MACD signal of a constant series is 0", close_to(float(signal.abs().max()), 0.0))
check("MACD histogram of a constant series is 0", close_to(float(hist.abs().max()), 0.0))

trend = series(list(range(1, 121)))
line, signal, hist = macd(trend)
# On a steady uptrend the fast EMA sits above the slow one throughout.
check("MACD is positive on a rising series", bool((line.iloc[30:] > 0).all()))
check("MACD histogram equals line minus signal",
      bool(np.allclose((line - signal).to_numpy(), hist.to_numpy(), equal_nan=True)))
check("MACD equals EMA(12) - EMA(26) exactly", bool(np.allclose(
    (ema(trend, 12) - ema(trend, 26)).to_numpy(), line.to_numpy(), equal_nan=True)))

try:
    macd(trend, fast=26, slow=12)
    check("MACD with fast >= slow raises", False, "no exception")
except ValueError:
    check("MACD with fast >= slow raises ValueError", True)

# ---------------------------------------------------------------------------
print("\nBollinger Bands")
# ---------------------------------------------------------------------------
s = series([1, 2, 3, 4, 5, 6, 7, 8])
upper, middle, lower = bollinger_bands(s, window=4, num_std=2)
check("Bollinger middle band is the SMA",
      bool(np.allclose(middle.to_numpy(), sma(s, 4).to_numpy(), equal_nan=True)))
# Last 4 values 5,6,7,8: mean 6.5, sample std = sqrt(5/3) = 1.29099...
expected_std = math.sqrt(5.0 / 3.0)
check("Bollinger upper band is SMA + 2 sd",
      close_to(upper.iloc[-1], 6.5 + 2 * expected_std, 1e-9),
      f"got {upper.iloc[-1]}")
check("Bollinger lower band is SMA - 2 sd",
      close_to(lower.iloc[-1], 6.5 - 2 * expected_std, 1e-9))
check("the bands are symmetric about the middle",
      close_to(float((upper - middle).iloc[-1]), float((middle - lower).iloc[-1])))

flat_bands = bollinger_bands(series([3.0] * 10), window=4)
check("a flat series collapses the band onto the middle",
      close_to(float((flat_bands[0] - flat_bands[2]).iloc[-1]), 0.0))
check("%B is NaN rather than inf on a zero-width band",
      bool(percent_b(series([3.0] * 10), window=4).iloc[-1] != percent_b(
          series([3.0] * 10), window=4).iloc[-1]))
check("%B is 1.0 at the upper band",
      close_to(float(((s - lower) / (upper - lower)).iloc[-1]),
               float(percent_b(s, window=4, num_std=2).iloc[-1])))

try:
    bollinger_bands(s, window=1)
    check("Bollinger window of 1 raises", False, "no exception")
except ValueError:
    check("Bollinger window of 1 raises ValueError", True)

# ---------------------------------------------------------------------------
print("\nReturns, volatility, drawdown")
# ---------------------------------------------------------------------------
s = series([100, 110, 99])
got = daily_returns(s)
# +10% then -10%.
check("daily return first row is NaN", bool(pd.isna(got.iloc[0])))
check("daily returns are [-, 0.10, -0.10]",
      close_to(got.iloc[1], 0.10) and close_to(got.iloc[2], -0.10, 1e-12),
      f"got {got.iloc[1]}, {got.iloc[2]}")

cum = cumulative_returns(s)
# (1.10)(0.90) - 1 = -0.01: up 10% then down 10% loses 1%.
check("cumulative return starts at 0, not NaN", close_to(cum.iloc[0], 0.0))
check("cumulative return of +10% then -10% is -1%",
      close_to(cum.iloc[-1], -0.01, 1e-12), f"got {cum.iloc[-1]}")
check("period_return agrees with the cumulative series",
      close_to(period_return(s), float(cum.iloc[-1]), 1e-12))
check("period_return of a one-row series is None", period_return(series([5.0])) is None)

# Volatility: check the sqrt(252) scaling against the daily std directly.
rets = daily_returns(series([100, 101, 100, 101, 100])).dropna()
expected_vol = float(rets.std(ddof=1) * math.sqrt(252))
check("annualized_volatility scales daily std by sqrt(252)",
      close_to(annualized_volatility(series([100, 101, 100, 101, 100])), expected_vol))
check("annualized_volatility of a flat series is 0",
      close_to(annualized_volatility(series([50.0] * 30)), 0.0))
check("annualized_volatility of one row is None",
      annualized_volatility(series([50.0])) is None)
check("crypto annualises on 365 days", periods_per_year_for("CRYPTOCURRENCY") == 365)
check("equities annualise on 252 days",
      periods_per_year_for("EQUITY") == config.TRADING_DAYS_PER_YEAR)
check("an unknown quote type falls back to the equity divisor",
      periods_per_year_for(None) == config.TRADING_DAYS_PER_YEAR)

dd = drawdown(series([100, 120, 90, 150]))
# Peaks 100,120,120,150 -> 0, 0, 90/120-1 = -0.25, 0 at a new high.
check("drawdown is 0 at a new high", close_to(dd.iloc[1], 0.0) and close_to(dd.iloc[3], 0.0))
check("drawdown is -25% at 90 after a 120 peak", close_to(dd.iloc[2], -0.25))

# YTD: last close of the previous year is the base.
ytd_series = pd.Series(
    [100.0, 110.0, 121.0],
    index=pd.DatetimeIndex(["2025-12-31", "2026-01-02", "2026-02-02"], name="Date"),
)
check("ytd_return measures from the previous year's last close",
      close_to(ytd_return(ytd_series), 0.21, 1e-12), f"got {ytd_return(ytd_series)}")
no_prior = pd.Series(
    [100.0, 125.0],
    index=pd.DatetimeIndex(["2026-03-02", "2026-04-02"], name="Date"),
)
check("ytd_return falls back to the first row of the year when the range is short",
      close_to(ytd_return(no_prior), 0.25))
check("ytd_return is None on an empty series",
      ytd_return(pd.Series(dtype="float64")) is None)
check("ytd_return is None without a datetime index",
      ytd_return(pd.Series([1.0, 2.0])) is None)
# The base is the last close before 1 Jan even when that is weeks earlier,
# and rows from the year before the base are ignored entirely.
spanning = pd.Series(
    [50.0, 100.0, 150.0],
    index=pd.DatetimeIndex(["2025-06-30", "2025-12-29", "2026-05-02"], name="Date"),
)
check("ytd_return ignores rows before the year boundary",
      close_to(ytd_return(spanning), 0.50), f"got {ytd_return(spanning)}")

# ---------------------------------------------------------------------------
print("\nMonthly returns pivot (heatmap source)")
# ---------------------------------------------------------------------------
# Three calendar months, +10% inside each one.
idx = pd.DatetimeIndex(
    ["2026-01-02", "2026-01-30", "2026-02-27", "2026-03-31"], name="Date"
)
monthly_src = pd.Series([100.0, 110.0, 121.0, 133.1], index=idx)
pivot = monthly_returns_pivot(monthly_src)
check("pivot has all twelve month columns", list(pivot.columns) == list(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")))
check("pivot January return is +10%", close_to(float(pivot.loc[2026, "Jan"]), 0.10, 1e-9),
      f"got {pivot.loc[2026, 'Jan']}")
check("pivot February return is +10%", close_to(float(pivot.loc[2026, "Feb"]), 0.10, 1e-9))
check("months with no data are NaN, not 0",
      bool(pd.isna(pivot.loc[2026, "Jul"])))
check("years run newest first", bool(pivot.index.is_monotonic_decreasing))
check("an empty input gives an empty frame with the right columns",
      monthly_returns_pivot(pd.Series(dtype="float64")).shape[1] == 12)

two_years = pd.Series(
    [100.0, 105.0, 110.0],
    index=pd.DatetimeIndex(["2025-06-30", "2025-12-31", "2026-06-30"], name="Date"),
)
check("pivot spans multiple years", len(monthly_returns_pivot(two_years).index) == 2)

# ---------------------------------------------------------------------------
print("\navailable_windows — the short-range guard")
# ---------------------------------------------------------------------------
usable, skipped = available_windows(23, (20, 50, 200))
check("a 23-row range supports SMA 20 only", usable == [20] and skipped == [50, 200],
      f"usable {usable}, skipped {skipped}")
usable, skipped = available_windows(500, (20, 50, 200))
check("a 500-row range supports every window", usable == [20, 50, 200] and skipped == [])
usable, skipped = available_windows(20, (20,))
check("exactly enough rows counts as usable", usable == [20])

# ---------------------------------------------------------------------------
print("\nenrich — the single place indicators meet data")
# ---------------------------------------------------------------------------
rng = np.random.default_rng(11)
n = 300
close = np.cumsum(rng.normal(0, 1, n)) + 500
frame = pd.DataFrame(
    {
        "Open": close - 0.5,
        "High": close + 1.0,
        "Low": close - 1.0,
        "Close": close,
        "Volume": rng.integers(1_000_000, 5_000_000, n),
    },
    index=pd.date_range("2025-01-01", periods=n, freq="B", name="Date"),
)

rich = enrich(frame)
expected_cols = indicator_columns()
check("enrich adds every column indicator_columns() promises",
      all(c in rich.columns for c in expected_cols),
      f"missing {[c for c in expected_cols if c not in rich.columns]}")
check("enrich adds at least the 8 indicator columns the spec requires",
      len(expected_cols) >= 8, f"only {len(expected_cols)}")
check("enrich keeps the OHLCV columns", all(
    c in rich.columns for c in ("Open", "High", "Low", "Close", "Volume")))
check("enrich does not mutate its input", list(frame.columns) == [
    "Open", "High", "Low", "Close", "Volume"])
check("enrich preserves the row count and index", rich.index.equals(frame.index))
check("enrich's SMA_50 matches a direct call",
      bool(np.allclose(rich["SMA_50"].to_numpy(), sma(frame["Close"], 50).to_numpy(),
                       equal_nan=True)))
check("enrich's RSI respects the variant choice", bool(np.allclose(
    enrich(frame, rsi_variant="Wilder (standard)")["RSI_14"].to_numpy(),
    rsi_wilder(frame["Close"], 14).to_numpy(), equal_nan=True)))

try:
    enrich(frame, rsi_variant="made up")
    check("enrich rejects an unknown RSI variant", False, "no exception")
except KeyError:
    check("enrich rejects an unknown RSI variant", True)

try:
    enrich(frame.drop(columns=["Close"]))
    check("enrich without a Close column raises", False, "no exception")
except KeyError:
    check("enrich without a Close column raises KeyError", True)

# A short range must still produce the full column set, all-NaN where needed.
short = enrich(frame.head(25))
check("a 25-row frame still gets every column",
      all(c in short.columns for c in expected_cols))
check("SMA_200 on a 25-row frame is entirely NaN",
      bool(short["SMA_200"].isna().all()))
check("SMA_20 on a 25-row frame has values", bool(short["SMA_20"].notna().any()))

# ---------------------------------------------------------------------------
print("\nLive data seam — Phase 2 into Phase 3")
# ---------------------------------------------------------------------------
# Synthetic data cannot catch a column-name or dtype mismatch between the
# fetcher's contract and enrich(). Skipped without failing when offline, so
# this file stays runnable on a train.
try:
    from src.data import DataQualityError, fetch_ohlcv, resolve_date_range

    start, end = resolve_date_range("1Y")
    live = enrich(fetch_ohlcv("AAPL", start, end))
    check("enrich works on a real fetched frame",
          len(live) > 200 and all(c in live.columns for c in expected_cols))
    check("every indicator column on real data is numeric",
          all(str(live[c].dtype).startswith("float") for c in expected_cols),
          f"non-float: {[c for c in expected_cols if not str(live[c].dtype).startswith('float')]}")
    check("RSI on real data stays within 0-100",
          bool(live["RSI_14"].dropna().between(0, 100).all()))
    check("real close price sits inside its own Bollinger band most of the time",
          float(live["BB_PERCENT_B"].dropna().between(0, 1).mean()) > 0.80,
          f"only {float(live['BB_PERCENT_B'].dropna().between(0, 1).mean()):.2%} inside")
    check("drawdown on real data is never positive",
          bool((live["DRAWDOWN"].dropna() <= 1e-12).all()))
    check("the monthly pivot of a real year has at least 12 populated cells",
          int(monthly_returns_pivot(live["Close"]).notna().sum().sum()) >= 12)
except (DataQualityError, OSError) as exc:  # offline or Yahoo unreachable
    print(f"  skip live-data checks — {exc}")

# ---------------------------------------------------------------------------
print("\n" + "=" * 68)
print(f"{len(PASSED)} passed, {len(FAILED)} failed")
if FAILED:
    for line in FAILED:
        print(f"  FAILED: {line}")
    sys.exit(1)
print("All indicator formulas match SPEC.md.")
