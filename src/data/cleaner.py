"""Validation and tidying of raw OHLCV frames.

Everything downstream of this module (indicators, charts, exports) is allowed
to assume the contract :func:`clean_ohlcv` enforces:

* a sorted, unique, timezone-naive ``DatetimeIndex`` named ``Date``
* exactly the columns ``Open, High, Low, Close, Volume``, all float/int64
* no NaNs in ``Close``
* ``High >= Low`` on every row
* at least one row

Anything that cannot be made to satisfy that raises :class:`DataQualityError`,
which the app catches and turns into a readable error panel. No module here
imports streamlit, so the cleaner is usable from the notebook and the scripts.
"""

from __future__ import annotations

import pandas as pd

__all__ = ["DataQualityError", "OHLCV_COLUMNS", "clean_ohlcv"]

#: Canonical column order for every price frame in the project.
OHLCV_COLUMNS: tuple[str, ...] = ("Open", "High", "Low", "Close", "Volume")


class DataQualityError(ValueError):
    """Raised when a fetched frame cannot be made usable.

    Carries a message written for the end user, not for a log file, because
    the Streamlit app surfaces ``str(exc)`` directly.
    """


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse a yfinance MultiIndex column frame to single-level names.

    ``yf.download()`` returns two-level columns (field, ticker) whenever more
    than one ticker is requested, and historically did so even for one ticker.
    We keep the level that carries the OHLCV field names and drop the other.
    """
    if not isinstance(df.columns, pd.MultiIndex):
        return df

    wanted = {c.lower() for c in OHLCV_COLUMNS}
    for level in range(df.columns.nlevels):
        values = {str(v).lower() for v in df.columns.get_level_values(level)}
        if wanted & values:
            flat = df.copy()
            flat.columns = [str(v) for v in df.columns.get_level_values(level)]
            return flat

    # No level looked like OHLCV; fall back to joining the levels so the
    # caller gets a comprehensible error from the column check below.
    flat = df.copy()
    flat.columns = ["_".join(str(p) for p in tup).strip("_") for tup in df.columns]
    return flat


def _normalise_index(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Return the frame with a sorted, unique, tz-naive ``Date`` index."""
    out = df.copy()

    if not isinstance(out.index, pd.DatetimeIndex):
        if "Date" in out.columns:
            out = out.set_index("Date")
        try:
            out.index = pd.to_datetime(out.index)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise DataQualityError(
                f"{ticker}: the price data has no usable date index."
            ) from exc

    # Crypto and some exchanges come back tz-aware; mixing tz-aware and naive
    # indices breaks joins in the comparison tab, so everything is made naive.
    if out.index.tz is not None:
        out.index = out.index.tz_localize(None)

    out.index = out.index.normalize()
    out.index.name = "Date"
    out = out.sort_index()
    # Keep the last reading for a repeated date: later rows are the revised ones.
    out = out[~out.index.duplicated(keep="last")]
    return out


def clean_ohlcv(df: pd.DataFrame | None, ticker: str = "the selected ticker") -> pd.DataFrame:
    """Validate and tidy one ticker's OHLCV frame.

    Parameters
    ----------
    df:
        Raw frame as returned by :func:`src.data.fetcher.fetch_ohlcv`. ``None``
        and empty frames are treated as "no data", not as programmer errors,
        because an unknown symbol is exactly what Yahoo answers with.
    ticker:
        Used only in error messages.

    Returns
    -------
    pandas.DataFrame
        A new frame satisfying the module contract. The input is never mutated.

    Raises
    ------
    DataQualityError
        If the frame is empty, is missing a required column, or has no row
        left with a usable close price.
    """
    if df is None or len(df) == 0:
        raise DataQualityError(
            f"No price data came back for {ticker}. Check the symbol "
            "(Indian stocks need a .NS suffix, crypto looks like BTC-USD) "
            "and the date range."
        )

    out = _flatten_columns(df)
    out = _normalise_index(out, ticker)

    missing = [c for c in OHLCV_COLUMNS if c not in out.columns]
    if missing:
        raise DataQualityError(
            f"{ticker}: the price data is missing {', '.join(missing)}. "
            "This usually means Yahoo returned a partial response — try again."
        )

    out = out.loc[:, list(OHLCV_COLUMNS)]

    for col in OHLCV_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    # Rows where every price is missing are non-trading artefacts; drop them
    # before filling, so a holiday at the edge of the range is not invented.
    out = out.dropna(how="all", subset=list(OHLCV_COLUMNS))
    if out.empty:
        raise DataQualityError(
            f"{ticker}: every row of the returned price data was empty."
        )

    # Interior gaps (half-days, feed hiccups) are carried forward; a leading
    # gap has nothing to carry, so those rows are dropped by the Close check.
    out[["Open", "High", "Low", "Close"]] = out[
        ["Open", "High", "Low", "Close"]
    ].ffill()
    out["Volume"] = out["Volume"].fillna(0)

    out = out.dropna(subset=["Close"])
    if out.empty:
        raise DataQualityError(
            f"{ticker}: no row in the returned data has a closing price."
        )

    # High/Low inversions do occur in Yahoo's adjusted data. Swapping is
    # safer than dropping the row, which would leave a hole in the series.
    inverted = out["High"] < out["Low"]
    if inverted.any():
        highs = out.loc[inverted, "High"].copy()
        out.loc[inverted, "High"] = out.loc[inverted, "Low"]
        out.loc[inverted, "Low"] = highs

    out["Volume"] = out["Volume"].clip(lower=0).astype("int64")
    for col in ("Open", "High", "Low", "Close"):
        out[col] = out[col].astype("float64")

    return out
