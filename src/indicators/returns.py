"""Returns, volatility and the monthly-returns grid behind the heatmap."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import config

__all__ = [
    "MONTH_LABELS",
    "annualized_volatility",
    "cumulative_returns",
    "daily_returns",
    "drawdown",
    "monthly_returns_pivot",
    "period_return",
    "rolling_volatility",
    "ytd_return",
]

#: Column order for the monthly heatmap, so January is always leftmost.
MONTH_LABELS: tuple[str, ...] = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def daily_returns(series: pd.Series) -> pd.Series:
    """Simple period-over-period return: ``(close - prev_close) / prev_close``.

    ``fill_method=None`` is passed explicitly. Older pandas forward-filled
    before differencing, which invents a zero return across a gap; the data
    layer has already decided how gaps are handled, and this module must not
    quietly re-decide it.

    The first row is always ``NaN`` — there is no previous close.
    """
    return series.pct_change(fill_method=None)


def cumulative_returns(series: pd.Series) -> pd.Series:
    """Total return since the first row, compounded: ``(1+r).cumprod() - 1``.

    ``0.25`` means up 25% over the window. The leading ``NaN`` from
    :func:`daily_returns` is treated as a zero first step, so the series
    starts at ``0.0`` on the first date instead of ``NaN`` — otherwise every
    cumulative line would begin one row after the price line it is compared to.
    """
    return (1.0 + daily_returns(series).fillna(0.0)).cumprod() - 1.0


def period_return(series: pd.Series) -> float | None:
    """Total return from the first to the last value, as a fraction.

    Returns ``None`` rather than ``NaN`` when the series is too short or the
    starting price is zero, so a KPI card can test ``is None`` and print an
    em dash.
    """
    clean = series.dropna()
    if len(clean) < 2:
        return None
    first = float(clean.iloc[0])
    if first == 0.0:
        return None
    return float(clean.iloc[-1]) / first - 1.0


def ytd_return(series: pd.Series) -> float | None:
    """Return since the last close of the previous calendar year.

    The spec's KPI row asks for "YTD Return %". Measuring from 1 January is
    wrong twice over: 1 January is a market holiday, and the fetched range may
    start mid-year. This takes the last close at or before the year boundary
    as the base and falls back to the first available row of the current year
    when the range does not reach back that far — in which case the number is
    a partial year, which the caller should label.

    Returns ``None`` when the frame holds no rows in the current year.
    """
    clean = series.dropna()
    if clean.empty or not isinstance(clean.index, pd.DatetimeIndex):
        return None

    year = clean.index.max().year
    boundary = pd.Timestamp(year=year, month=1, day=1)

    base_candidates = clean.loc[clean.index < boundary]
    this_year = clean.loc[clean.index >= boundary]
    if this_year.empty:
        return None

    base = float(base_candidates.iloc[-1]) if not base_candidates.empty else float(
        this_year.iloc[0]
    )
    if base == 0.0:
        return None
    return float(this_year.iloc[-1]) / base - 1.0


def annualized_volatility(
    series: pd.Series,
    periods: int = config.TRADING_DAYS_PER_YEAR,
) -> float | None:
    """Annualised volatility: ``std(daily returns) * sqrt(periods)``.

    ``0.32`` means roughly 32% a year. The spec's formula, with one caveat
    worth stating in the report: ``periods=252`` is the trading-day count for
    an equity market, and crypto trades 365 days a year. Passing 252 for
    ``BTC-USD`` understates its volatility by about 23%, so the caller sets
    ``periods`` from the asset type rather than taking the default blindly.

    Returns ``None`` for a series with fewer than two usable returns.
    """
    rets = daily_returns(series).dropna()
    if len(rets) < 2:
        return None
    value = float(rets.std(ddof=1) * np.sqrt(periods))
    return value if np.isfinite(value) else None


def rolling_volatility(
    series: pd.Series,
    window: int = 21,
    periods: int = config.TRADING_DAYS_PER_YEAR,
) -> pd.Series:
    """Annualised volatility over a trailing ``window`` of returns.

    The 21-row default is about one trading month. Carried as a column so the
    PDF commentary can say whether the stock is currently calmer or wilder
    than its own median, which is far more useful than an absolute percentage
    the reader has no yardstick for.
    """
    rets = daily_returns(series)
    return rets.rolling(window=window).std(ddof=1) * np.sqrt(periods)


def drawdown(series: pd.Series) -> pd.Series:
    """Fractional fall from the running peak: ``0`` at a new high, ``-0.2`` 20% below it.

    Included because "down 18% from its high" is how a reader actually thinks
    about risk, where annualised volatility is an abstraction.
    """
    clean = series.astype("float64")
    running_peak = clean.cummax()
    return clean / running_peak.where(running_peak != 0) - 1.0


def monthly_returns_pivot(series: pd.Series) -> pd.DataFrame:
    """Monthly returns as a years x months grid for the heatmap.

    Each cell is the return across that calendar month, compounded from the
    daily returns inside it — not the simple first-to-last price ratio, which
    would silently ignore a gap in the middle of the month.

    Rows are years (descending, so the most recent year is the top row of the
    heatmap), columns are the twelve :data:`MONTH_LABELS` in calendar order.
    Months with no trading data are ``NaN`` and render as a blank cell, which
    is correct for a part-finished year — a zero there would read as "flat".

    An empty or non-datetime-indexed input gives an empty frame with the right
    columns, so the chart code has one shape to handle.
    """
    empty = pd.DataFrame(columns=list(MONTH_LABELS), dtype="float64")

    clean = series.dropna()
    if clean.empty or not isinstance(clean.index, pd.DatetimeIndex):
        return empty

    rets = daily_returns(clean).fillna(0.0)
    # Compound within each calendar month: (1+r1)(1+r2)... - 1
    monthly = rets.resample("ME").apply(lambda window: (1.0 + window).prod() - 1.0)
    monthly = monthly.dropna()
    if monthly.empty:
        return empty

    grid = pd.DataFrame(
        {
            "Year": monthly.index.year,
            "Month": monthly.index.month,
            "Return": monthly.to_numpy(dtype="float64"),
        }
    )
    pivot = grid.pivot_table(
        index="Year", columns="Month", values="Return", aggfunc="first"
    )

    # Reindex to all twelve months so every row is the same width, then label.
    pivot = pivot.reindex(columns=range(1, 13))
    pivot.columns = list(MONTH_LABELS)
    pivot = pivot.sort_index(ascending=False)
    pivot.index.name = "Year"
    return pivot
