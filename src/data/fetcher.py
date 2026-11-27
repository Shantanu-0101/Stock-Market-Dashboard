"""The only place in the project that talks to Yahoo Finance.

Every network call lives behind one of the public functions here, so if
the endpoint changes shape this is the single module to fix. Nothing is
cached: each script run fetches what it needs once.

Prices come back **auto-adjusted** (splits and dividends applied), because
every indicator in the spec is computed on a single continuous price series
and an unadjusted series puts a false gap at each split.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Iterable

import pandas as pd
import yfinance as yf

from src.data.cleaner import DataQualityError, clean_ohlcv

__all__ = [
    "fetch_ohlcv",
    "fetch_many",
    "fetch_company_info",
    "normalise_ticker",
]


# --------------------------------------------------------------------------
# Prices
# --------------------------------------------------------------------------

def _download(ticker: str, start: _dt.date, end: _dt.date) -> pd.DataFrame | None:
    """One raw yfinance call, with network failures turned into a clean error."""
    try:
        return yf.download(
            ticker,
            start=start,
            end=end,
            interval="1d",
            auto_adjust=True,
            actions=False,
            progress=False,
            multi_level_index=False,
            threads=False,
        )
    except Exception as exc:  # yfinance raises a wide variety of transport errors
        raise DataQualityError(
            f"Could not reach Yahoo Finance for {ticker}: {exc}. "
            "Check the connection and try again."
        ) from exc


def fetch_ohlcv(ticker: str, start: _dt.date, end: _dt.date) -> pd.DataFrame:
    """Daily OHLCV for one ticker, cleaned and ready for the indicators.

    Parameters
    ----------
    ticker:
        A Yahoo symbol: ``AAPL``, ``RELIANCE.NS``, ``BTC-USD``. Whitespace is
        stripped and the symbol upper-cased, since users type ``aapl``.
    start, end:
        ``end`` is exclusive, matching yfinance, so pass the day after the
        last date wanted.

    Returns
    -------
    pandas.DataFrame
        Columns ``Open, High, Low, Close, Volume`` on a ``Date`` index, as
        guaranteed by :func:`src.data.cleaner.clean_ohlcv`.

    Raises
    ------
    DataQualityError
        Bad symbol, empty range, unreachable endpoint, or unusable response.
    """
    symbol = normalise_ticker(ticker)
    if not symbol:
        raise DataQualityError("Enter a ticker symbol to load, for example AAPL.")

    raw = _download(symbol, start, end)
    return clean_ohlcv(raw, ticker=symbol)


def fetch_many(
    tickers: Iterable[str],
    start: _dt.date,
    end: _dt.date,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Fetch several tickers, for the export and the comparison charts.

    Each symbol is fetched through :func:`fetch_ohlcv` rather than in one
    batched download, so one failure is reported against its own symbol.

    Returns
    -------
    (frames, errors)
        ``frames`` maps symbol to a cleaned frame for everything that loaded;
        ``errors`` maps symbol to a user-readable reason for everything that
        did not. Callers report the errors and use the frames — a single bad
        symbol must not stop the others from loading.
    """
    frames: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}

    seen: set[str] = set()
    for raw_ticker in tickers:
        symbol = normalise_ticker(raw_ticker)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        try:
            frames[symbol] = fetch_ohlcv(symbol, start, end)
        except DataQualityError as exc:
            errors[symbol] = str(exc)

    return frames, errors


def normalise_ticker(ticker: str) -> str:
    """Upper-case and strip a user-typed symbol (``' aapl '`` -> ``'AAPL'``)."""
    return str(ticker or "").strip().upper()


# --------------------------------------------------------------------------
# Company metadata
# --------------------------------------------------------------------------

#: Keys the KPI row needs. Every one is nullable: crypto has no sector or P/E,
#: and ``.info`` intermittently answers ``{}`` for perfectly valid symbols.
_INFO_FIELDS: tuple[str, ...] = (
    "symbol",
    "name",
    "sector",
    "industry",
    "currency",
    "quote_type",
    "exchange",
    "market_cap",
    "pe_ratio",
    "last_price",
    "previous_close",
    "week52_high",
    "week52_low",
    "avg_volume",
)


def _empty_info(symbol: str) -> dict[str, Any]:
    info: dict[str, Any] = dict.fromkeys(_INFO_FIELDS)
    info["symbol"] = symbol
    return info


def _as_number(value: Any) -> float | None:
    """Coerce a Yahoo field to a float, mapping junk and zero-ish to ``None``.

    Yahoo uses ``0``, ``'Infinity'`` and the string ``'None'`` as stand-ins for
    "missing" depending on the field, and a zero market cap or P/E is never a
    real value, so all of those become ``None`` and render as an em dash.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return number or None


def fetch_company_info(ticker: str) -> dict[str, Any]:
    """Name, sector, market cap, P/E, 52-week range and currency for a ticker.

    ``fast_info`` is tried first: it is a small, reliable quote endpoint and
    covers most of the KPI row. ``.info`` is a slow, unofficial, frequently
    rate-limited scrape, so it is consulted only for the fields ``fast_info``
    does not carry (long name, sector, industry, trailing P/E) and its failure
    is swallowed.

    Every value may be ``None``. This function never raises for a bad ticker —
    a missing KPI card is not a reason to drop a ticker that still has prices.
    """
    symbol = normalise_ticker(ticker)
    info = _empty_info(symbol)
    if not symbol:
        return info

    try:
        handle = yf.Ticker(symbol)
    except Exception:  # pragma: no cover - construction is normally offline
        return info

    # --- fast path -------------------------------------------------------
    try:
        fast = handle.fast_info
        available = set(fast.keys())

        def fast_get(key: str) -> Any:
            return fast[key] if key in available else None

        info["currency"] = fast_get("currency") or None
        info["quote_type"] = fast_get("quoteType") or None
        info["exchange"] = fast_get("exchange") or None
        info["market_cap"] = _as_number(fast_get("marketCap"))
        info["last_price"] = _as_number(fast_get("lastPrice"))
        info["previous_close"] = _as_number(
            fast_get("previousClose") or fast_get("regularMarketPreviousClose")
        )
        info["week52_high"] = _as_number(fast_get("yearHigh"))
        info["week52_low"] = _as_number(fast_get("yearLow"))
        info["avg_volume"] = _as_number(
            fast_get("threeMonthAverageVolume") or fast_get("tenDayAverageVolume")
        )
    except Exception:
        pass  # leave the fast fields as None and try .info below

    # --- slow path, best effort -----------------------------------------
    try:
        slow = handle.info or {}
    except Exception:
        slow = {}

    if slow:
        info["name"] = slow.get("longName") or slow.get("shortName") or info["name"]
        info["sector"] = slow.get("sector") or info["sector"]
        info["industry"] = slow.get("industry") or info["industry"]
        info["currency"] = info["currency"] or slow.get("currency")
        info["quote_type"] = info["quote_type"] or slow.get("quoteType")
        info["exchange"] = info["exchange"] or slow.get("exchange")
        info["pe_ratio"] = _as_number(
            slow.get("trailingPE") or slow.get("forwardPE")
        )
        info["market_cap"] = info["market_cap"] or _as_number(slow.get("marketCap"))
        info["week52_high"] = info["week52_high"] or _as_number(
            slow.get("fiftyTwoWeekHigh")
        )
        info["week52_low"] = info["week52_low"] or _as_number(
            slow.get("fiftyTwoWeekLow")
        )
        info["avg_volume"] = info["avg_volume"] or _as_number(
            slow.get("averageVolume") or slow.get("averageDailyVolume10Day")
        )

    info["name"] = info["name"] or symbol
    return info
