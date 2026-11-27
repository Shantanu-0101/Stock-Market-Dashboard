"""Bollinger Bands: a 20-period SMA with a +/- 2 standard deviation envelope."""

from __future__ import annotations

import pandas as pd

from src import config
from src.indicators.moving_averages import sma

__all__ = ["bollinger_bands", "percent_b", "bandwidth"]


def bollinger_bands(
    series: pd.Series,
    window: int = config.BOLLINGER_WINDOW,
    num_std: float = config.BOLLINGER_NUM_STD,
    ddof: int = 1,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return ``(upper, middle, lower)``.

    ``middle`` is the SMA over ``window``; the outer bands sit ``num_std``
    rolling standard deviations either side of it. The envelope widens when
    the market is volatile and pinches when it is quiet, which is the whole
    point of the indicator.

    ``ddof=1`` (the sample standard deviation) is pandas' default and what the
    spec's snippet produces, so it is the default here. Note that several
    trading terminals use ``ddof=0``, the population form, which makes their
    bands very slightly narrower; the parameter is exposed so a comparison
    against an outside chart can be made exactly rather than argued about.

    The first ``window - 1`` rows are ``NaN`` in all three series, so a range
    shorter than the window yields an empty band — the caller checks the row
    count rather than drawing nothing (see :func:`src.indicators.available_windows`).
    """
    if window < 2:
        raise ValueError(
            f"Bollinger window must be at least 2 for a standard deviation, got {window}."
        )

    middle = sma(series, window)
    deviation = series.rolling(window=window).std(ddof=ddof)

    upper = middle + num_std * deviation
    lower = middle - num_std * deviation

    return upper, middle, lower


def percent_b(
    series: pd.Series,
    window: int = config.BOLLINGER_WINDOW,
    num_std: float = config.BOLLINGER_NUM_STD,
) -> pd.Series:
    """Where price sits inside the band: 0 at the lower band, 1 at the upper.

    Values outside 0-1 mean price has broken out of the envelope. Carried as a
    column in the enriched frame because it answers "is this stock stretched?"
    in one number.

    A zero-width band (a perfectly flat window) would divide by zero; those
    rows come back as ``NaN`` rather than infinity.
    """
    upper, _middle, lower = bollinger_bands(series, window, num_std)
    span = upper - lower
    return (series - lower) / span.where(span != 0)


def bandwidth(
    series: pd.Series,
    window: int = config.BOLLINGER_WINDOW,
    num_std: float = config.BOLLINGER_NUM_STD,
) -> pd.Series:
    """Band width as a fraction of the middle band — a volatility reading.

    Rising bandwidth is an expanding, nervous market; a multi-month low is the
    "squeeze" that often precedes a sharp move. It is scale-free, so two
    tickers can be compared, where the raw band width in rupees and in
    dollars cannot.
    """
    upper, middle, lower = bollinger_bands(series, window, num_std)
    return (upper - lower) / middle.where(middle != 0)
