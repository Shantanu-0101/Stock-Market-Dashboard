"""Indicator maths, and the one function that applies all of it.

Import the individual formulas from here::

    from src.indicators import sma, rsi, macd, bollinger_bands

but reach for :func:`enrich` whenever a whole frame is wanted. The Power BI
export, the PDF reports and the walkthroughs all call it, so the derived
columns are produced in exactly one place and cannot drift between the
dashboard and the CSV behind it.
"""

from __future__ import annotations

import pandas as pd

from src import config
from src.indicators.bollinger import bandwidth, bollinger_bands, percent_b
from src.indicators.macd import macd
from src.indicators.moving_averages import ema, sma
from src.indicators.returns import (
    MONTH_LABELS,
    annualized_volatility,
    cumulative_returns,
    daily_returns,
    drawdown,
    monthly_returns_pivot,
    period_return,
    rolling_volatility,
    ytd_return,
)
from src.indicators.rsi import rsi, rsi_wilder

__all__ = [
    "MONTH_LABELS",
    "RSI_VARIANTS",
    "annualized_volatility",
    "available_windows",
    "bandwidth",
    "bollinger_bands",
    "cumulative_returns",
    "daily_returns",
    "drawdown",
    "ema",
    "enrich",
    "indicator_columns",
    "macd",
    "monthly_returns_pivot",
    "percent_b",
    "period_return",
    "periods_per_year_for",
    "rolling_volatility",
    "rsi",
    "rsi_wilder",
    "sma",
    "ytd_return",
]

#: Display name -> function, for decision 0.3 of the implementation plan.
#: The spec's version is first, and is the default everywhere.
RSI_VARIANTS = {
    "Spec (rolling mean)": rsi,
    "Wilder (standard)": rsi_wilder,
}

#: Trailing window for the rolling-volatility column, in rows (~1 month).
ROLLING_VOL_WINDOW: int = 21


def periods_per_year_for(quote_type: str | None) -> int:
    """How many trading periods a year this asset has, for annualising.

    Equities trade about 252 days a year; crypto trades every day. Using 252
    for ``BTC-USD`` understates its annualised volatility by roughly 23%, so
    the asset's ``quote_type`` from
    :func:`src.data.fetcher.fetch_company_info` picks the right divisor.
    Anything unrecognised gets the equity default.
    """
    if (quote_type or "").upper() == "CRYPTOCURRENCY":
        return 365
    return config.TRADING_DAYS_PER_YEAR


def available_windows(
    row_count: int,
    windows: tuple[int, ...] | list[int],
) -> tuple[list[int], list[int]]:
    """Split requested windows into those the data can support and those it cannot.

    SMA(200) over a one-month range is entirely ``NaN``. Plotting it adds an
    empty trace and a legend entry that makes the chart look broken, so the
    chart modules call this and caption what they skipped instead
    (``"SMA 200 needs 200 rows; this range has 23"``).

    Returns
    -------
    (usable, skipped)
        Both sorted ascending. A window is usable when the frame has at least
        that many rows.
    """
    usable = sorted(w for w in windows if row_count >= w)
    skipped = sorted(w for w in windows if row_count < w)
    return usable, skipped


def indicator_columns(
    sma_windows: tuple[int, ...] = config.SMA_WINDOWS,
    ema_spans: tuple[int, ...] = config.EMA_SPANS,
    rsi_period: int = config.RSI_PERIOD,
) -> list[str]:
    """The column names :func:`enrich` adds, in the order it adds them.

    Exported so the walkthroughs and the project report can list the
    columns without recomputing anything, and so a test can assert the
    spec's "at least 8 indicator columns" without hard-coding a list.
    """
    names = [f"SMA_{w}" for w in sma_windows]
    names += [f"EMA_{s}" for s in ema_spans]
    names += [
        f"RSI_{rsi_period}",
        "MACD",
        "MACD_SIGNAL",
        "MACD_HIST",
        "BB_UPPER",
        "BB_MIDDLE",
        "BB_LOWER",
        "BB_PERCENT_B",
        "BB_BANDWIDTH",
        "DAILY_RETURN",
        "CUM_RETURN",
        "DRAWDOWN",
        f"VOL_SMA_{config.VOLUME_AVG_WINDOW}",
        f"ROLL_VOL_{ROLLING_VOL_WINDOW}",
    ]
    return names


def enrich(
    df: pd.DataFrame,
    *,
    rsi_variant: str = "Spec (rolling mean)",
    sma_windows: tuple[int, ...] = config.SMA_WINDOWS,
    ema_spans: tuple[int, ...] = config.EMA_SPANS,
    rsi_period: int = config.RSI_PERIOD,
    periods_per_year: int = config.TRADING_DAYS_PER_YEAR,
) -> pd.DataFrame:
    """Return a copy of a clean OHLCV frame with every indicator as a column.

    This is the single place indicators are attached to data. It expects the
    contract :func:`src.data.cleaner.clean_ohlcv` guarantees — a ``Close``
    column with no NaNs on a sorted ``Date`` index — and adds the columns
    listed by :func:`indicator_columns`, which is at least 17 and comfortably
    past the eight the spec asks the CSV to carry.

    Columns whose window exceeds the row count are still added, full of
    ``NaN``. Dropping them would make the frame's shape depend on the date
    range, and the CSV user would silently lose a column; the charts ask
    :func:`available_windows` what to draw instead.

    Parameters
    ----------
    rsi_variant:
        A key of :data:`RSI_VARIANTS`. Unknown keys raise rather than
        silently falling back, so a typo in the caller is loud.
    periods_per_year:
        Annualisation divisor for the volatility column; see
        :func:`periods_per_year_for`.

    Raises
    ------
    KeyError
        If ``Close`` is absent, or ``rsi_variant`` is not a known variant.
    """
    if "Close" not in df.columns:
        raise KeyError(
            "enrich() needs a 'Close' column — pass a frame from clean_ohlcv()."
        )
    if rsi_variant not in RSI_VARIANTS:
        raise KeyError(
            f"Unknown RSI variant {rsi_variant!r}. "
            f"Choose one of {', '.join(RSI_VARIANTS)}."
        )

    out = df.copy()
    close = out["Close"]

    for window in sma_windows:
        out[f"SMA_{window}"] = sma(close, window)
    for span in ema_spans:
        out[f"EMA_{span}"] = ema(close, span)

    out[f"RSI_{rsi_period}"] = RSI_VARIANTS[rsi_variant](close, rsi_period)

    macd_line, signal_line, histogram = macd(close)
    out["MACD"] = macd_line
    out["MACD_SIGNAL"] = signal_line
    out["MACD_HIST"] = histogram

    upper, middle, lower = bollinger_bands(close)
    out["BB_UPPER"] = upper
    out["BB_MIDDLE"] = middle
    out["BB_LOWER"] = lower
    out["BB_PERCENT_B"] = percent_b(close)
    out["BB_BANDWIDTH"] = bandwidth(close)

    out["DAILY_RETURN"] = daily_returns(close)
    out["CUM_RETURN"] = cumulative_returns(close)
    out["DRAWDOWN"] = drawdown(close)

    if "Volume" in out.columns:
        out[f"VOL_SMA_{config.VOLUME_AVG_WINDOW}"] = sma(
            out["Volume"].astype("float64"), config.VOLUME_AVG_WINDOW
        )

    out[f"ROLL_VOL_{ROLLING_VOL_WINDOW}"] = rolling_volatility(
        close, window=ROLLING_VOL_WINDOW, periods=periods_per_year
    )

    return out
