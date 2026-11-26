"""Relative Strength Index, in both the spec's form and Wilder's original.

The two give visibly different numbers on the same series, so which one is on
screen is a sidebar choice (decision 0.3 of IMPLEMENTATION_PLAN.md) defaulting
to the spec's :func:`rsi`.
"""

from __future__ import annotations

import pandas as pd

from src import config

__all__ = ["rsi", "rsi_wilder"]

#: RSI of a window with no price movement at all. The formula gives 0/0 there,
#: and the convention is "neither overbought nor oversold" — the midpoint.
_FLAT_RSI: float = 50.0


def _gains_and_losses(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Split consecutive price changes into non-negative gains and losses.

    ``clip`` is used rather than the spec's ``delta.where(delta > 0, 0.0)``
    because ``where`` turns the leading ``NaN`` from ``diff()`` into a real
    ``0.0``. That fabricated zero gets averaged into the first window and
    understates the first RSI reading. ``clip`` keeps the ``NaN`` as ``NaN``,
    so the first RSI appears one row later — where it belongs — and is
    arithmetically identical to the spec everywhere else.
    """
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    return gain, loss


def _rs_to_rsi(avg_gain: pd.Series, avg_loss: pd.Series) -> pd.Series:
    """Turn average gain/loss into RSI, handling both degenerate cases.

    * ``avg_loss == 0`` with gains present: ``rs`` is infinite and RSI is 100.
      Division gives ``inf`` and the formula already lands on 100, so this
      needs no special casing — only the comment, because it looks like a bug.
    * ``avg_gain == avg_loss == 0`` (a perfectly flat window, common in a
      thinly traded stock or a stale feed): ``0/0`` is ``NaN``, which would
      put a hole in the middle of the chart. Those rows become
      :data:`_FLAT_RSI`.
    """
    rs = avg_gain / avg_loss
    out = 100.0 - (100.0 / (1.0 + rs))

    flat = (avg_gain == 0.0) & (avg_loss == 0.0)
    out = out.mask(flat, _FLAT_RSI)
    return out


def rsi(series: pd.Series, period: int = config.RSI_PERIOD) -> pd.Series:
    """RSI using a plain rolling mean of gains and losses — the spec's version.

    ``100 - 100 / (1 + avg_gain / avg_loss)`` where both averages are simple
    rolling means over ``period`` rows. Values run 0-100; above
    :data:`src.config.RSI_OVERBOUGHT` is conventionally read as overbought and
    below :data:`src.config.RSI_OVERSOLD` as oversold.

    Note that this is *not* the RSI a trading terminal shows — see
    :func:`rsi_wilder`. It reacts faster and swings wider, because an old
    price leaves a rolling window entirely instead of decaying out of it.

    Raises
    ------
    ValueError
        If ``period`` is less than 2 — a one-row window has no change to measure.
    """
    if period < 2:
        raise ValueError(f"RSI period must be at least 2, got {period}.")

    gain, loss = _gains_and_losses(series)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    return _rs_to_rsi(avg_gain, avg_loss)


def rsi_wilder(series: pd.Series, period: int = config.RSI_PERIOD) -> pd.Series:
    """RSI using Wilder's smoothing — what a trading platform actually plots.

    Identical to :func:`rsi` except the averages are exponentially smoothed
    with ``alpha = 1 / period`` instead of being rolling means, which is how
    J. Welles Wilder defined it in 1978. Offered alongside the spec's version
    so the indicator section of the report can be defended rather than
    explained away.
    """
    if period < 2:
        raise ValueError(f"RSI period must be at least 2, got {period}.")

    gain, loss = _gains_and_losses(series)
    # min_periods matches the rolling version, so both forms start on the
    # same row and can be compared directly.
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    return _rs_to_rsi(avg_gain, avg_loss)
