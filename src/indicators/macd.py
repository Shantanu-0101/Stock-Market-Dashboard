"""MACD: the 12/26 EMA spread, its 9-period signal line, and the histogram."""

from __future__ import annotations

import pandas as pd

from src import config
from src.indicators.moving_averages import ema

__all__ = ["macd"]


def macd(
    series: pd.Series,
    fast: int = config.MACD_FAST,
    slow: int = config.MACD_SLOW,
    signal: int = config.MACD_SIGNAL,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return ``(macd_line, signal_line, histogram)``.

    * ``macd_line`` = EMA(``fast``) - EMA(``slow``). Above zero means the fast
      average is above the slow one: upward momentum.
    * ``signal_line`` = EMA(``signal``) of the MACD line. Crossings of the two
      are the conventional entry/exit markers.
    * ``histogram`` = ``macd_line - signal_line``, drawn as bars coloured by
      sign so a crossover is visible as the bars flipping through zero.

    All three share the input's index. Because :func:`~src.indicators.moving_averages.ema`
    uses ``adjust=False``, every series has a value from the first row rather
    than a ``NaN`` run — early values are mathematically defined but carry
    little information, which is worth knowing before reading a crossover in
    the first few weeks of a short date range.

    Raises
    ------
    ValueError
        If ``fast`` is not strictly less than ``slow``; the spread would be
        inverted and every signal would read backwards.
    """
    if fast >= slow:
        raise ValueError(
            f"MACD needs fast < slow, got fast={fast}, slow={slow}."
        )

    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram
