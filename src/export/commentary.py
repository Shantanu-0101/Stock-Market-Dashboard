"""Rules-based sentences describing where the indicators currently sit.

Every sentence is a fixed template filled from the last row of an enriched
frame. It describes; it never recommends. The spec asks for "recommendation
text", and the implementation plan narrows that to a mechanical summary: no
buy, sell or hold wording appears here, and the PDF says so beside it.

An indicator the range is too short to support gets a sentence saying that,
rather than being left out -- a missing line would read as "nothing to report".
"""

from __future__ import annotations

import pandas as pd

from src import config
from src.formatting import format_percent
from src.indicators import ROLLING_VOL_WINDOW

__all__ = [
    "MIN_VOL_READINGS",
    "VOL_TOLERANCE",
    "commentary",
    "macd_sentence",
    "rsi_sentence",
    "trend_sentence",
    "volatility_sentence",
]

#: Rolling-volatility readings needed before their median is a yardstick.
MIN_VOL_READINGS: int = 21

#: Within this fraction of the median, volatility is "in line with" it.
VOL_TOLERANCE: float = 0.10


def _last(df: pd.DataFrame, column: str) -> float | None:
    """The value on the final row, or ``None`` if absent or ``NaN``.

    Deliberately the final row and not the last non-null value: an older
    reading presented as the current one would be wrong.
    """
    if column not in df.columns or df.empty:
        return None
    value = df[column].iloc[-1]
    return None if pd.isna(value) else float(value)


def rsi_sentence(df: pd.DataFrame, period: int = config.RSI_PERIOD) -> str:
    """Which zone the latest RSI falls in."""
    value = _last(df, f"RSI_{period}")
    if value is None:
        return (
            f"RSI({period}) is unavailable: it needs {period + 1} rows and this "
            f"range has {len(df)}."
        )
    if value > config.RSI_OVERBOUGHT:
        zone = (
            f"above {config.RSI_OVERBOUGHT}, the zone conventionally read as "
            "overbought"
        )
    elif value < config.RSI_OVERSOLD:
        zone = (
            f"below {config.RSI_OVERSOLD}, the zone conventionally read as "
            "oversold"
        )
    else:
        zone = (
            f"between {config.RSI_OVERSOLD} and {config.RSI_OVERBOUGHT}, the "
            "neutral zone"
        )
    return f"RSI({period}) is {value:.1f}, {zone}."


def trend_sentence(df: pd.DataFrame) -> str:
    """The latest close against its 50-day and 200-day averages."""
    close = _last(df, "Close")
    if close is None:
        return "No closing price is available to compare with the averages."

    compared: list[str] = []
    missing: list[str] = []
    for window in (50, 200):
        average = _last(df, f"SMA_{window}")
        if average is None or average == 0.0:
            missing.append(
                f"SMA {window} is unavailable: it needs {window} rows and this "
                f"range has {len(df)}."
            )
            continue
        gap = close / average - 1.0
        if gap == 0.0:
            compared.append(f"level with its SMA {window}")
        else:
            side = "above" if gap > 0 else "below"
            compared.append(
                f"{format_percent(abs(gap), signed=False)} {side} its SMA {window}"
            )

    sentences = []
    if compared:
        sentences.append(f"The last close is {' and '.join(compared)}.")
    sentences.extend(missing)
    return " ".join(sentences)


def macd_sentence(df: pd.DataFrame) -> str:
    """The sign of the MACD line and its position against the signal line."""
    line = _last(df, "MACD")
    signal = _last(df, "MACD_SIGNAL")
    # The exponential means produce numbers from the first row, but a 26-period
    # average of a handful of prices is not the indicator it is labelled as.
    if line is None or signal is None or len(df) < config.MACD_SLOW:
        return (
            f"MACD is not summarised: it needs at least {config.MACD_SLOW} rows "
            f"and this range has {len(df)}."
        )

    if line > 0:
        sign = "positive (the 12-period EMA is above the 26-period EMA)"
    elif line < 0:
        sign = "negative (the 12-period EMA is below the 26-period EMA)"
    else:
        sign = "zero"

    if line > signal:
        position = "above"
    elif line < signal:
        position = "below"
    else:
        position = "level with"
    return f"The MACD line is {sign} and {position} its signal line."


def volatility_sentence(df: pd.DataFrame) -> str:
    """The latest rolling volatility against its own median over the range."""
    column = f"ROLL_VOL_{ROLLING_VOL_WINDOW}"
    current = _last(df, column)
    readings = df[column].dropna() if column in df.columns else pd.Series(dtype=float)
    if current is None or len(readings) < MIN_VOL_READINGS:
        needed = ROLLING_VOL_WINDOW + MIN_VOL_READINGS
        return (
            f"Volatility is not compared with its median: that needs {needed} "
            f"rows and this range has {len(df)}."
        )

    median = float(readings.median())
    if abs(current - median) <= VOL_TOLERANCE * median:
        verdict = "in line with"
    elif current > median:
        verdict = "higher than"
    else:
        verdict = "lower than"
    return (
        f"{ROLLING_VOL_WINDOW}-day annualised volatility is "
        f"{format_percent(current, signed=False)}, {verdict} its median of "
        f"{format_percent(median, signed=False)} over this range."
    )


def commentary(df: pd.DataFrame) -> str:
    """The four sentences as one paragraph."""
    return " ".join(
        (
            rsi_sentence(df),
            trend_sentence(df),
            macd_sentence(df),
            volatility_sentence(df),
        )
    )
