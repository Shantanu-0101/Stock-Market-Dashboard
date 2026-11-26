"""Simple and exponential moving averages.

Both are the spec's formulas verbatim. Pure functions on a ``pd.Series`` with
no Streamlit or Plotly import, so the app, the notebook and the PDF generator
all call the same code.
"""

from __future__ import annotations

import pandas as pd

__all__ = ["sma", "ema"]


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average: the rolling mean of the last ``window`` values.

    The first ``window - 1`` values are ``NaN`` — there is no honest average
    over fewer rows than the window, and ``min_periods`` is deliberately left
    at its default so a short date range produces visible gaps rather than a
    quietly wrong line. Callers that cannot draw an all-NaN overlay check the
    row count first (see :func:`src.indicators.available_windows`).

    Raises
    ------
    ValueError
        If ``window`` is not a positive integer.
    """
    if window < 1:
        raise ValueError(f"SMA window must be at least 1, got {window}.")
    return series.rolling(window=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential moving average, ``adjust=False``.

    ``adjust=False`` is the recursive form every charting package uses
    (``y_t = a*x_t + (1-a)*y_{t-1}`` with ``a = 2/(span+1)``), and is what the
    spec asks for. Unlike :func:`sma` it produces a value from the first row,
    so an EMA overlay is never empty — it is just unreliable early on, since
    the first readings are dominated by a single price.

    Raises
    ------
    ValueError
        If ``span`` is less than 1.
    """
    if span < 1:
        raise ValueError(f"EMA span must be at least 1, got {span}.")
    return series.ewm(span=span, adjust=False).mean()
