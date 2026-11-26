"""Turning nullable numbers into the strings a KPI card shows.

Presentation only -- no maths, no fetching. It lives outside ``app.py``
because the PDF report has to print the same KPI row with the same rounding
and the same em dash for a missing value; two implementations would drift the
first time one of them was tweaked.

Every function accepts ``None`` and returns :data:`src.config.MISSING_VALUE_DISPLAY`
for it, so a caller never has to guard a field that Yahoo did not supply.
"""

from __future__ import annotations

import datetime as _dt
import math
from typing import Any

from src import config

__all__ = [
    "CURRENCY_SYMBOLS",
    "format_compact",
    "format_date",
    "format_money",
    "format_number",
    "format_percent",
    "format_volume",
    "currency_symbol",
    "title_case_name",
]

#: Symbols for the currencies this project's demo tickers actually trade in.
#: Anything else falls back to the ISO code, which is clearer than guessing.
CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",
    "INR": "Rs ",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
}

_MISSING = config.MISSING_VALUE_DISPLAY


def _is_missing(value: Any) -> bool:
    """``None``, ``NaN`` and infinities all mean "no value to show"."""
    if value is None:
        return True
    try:
        number = float(value)
    except (TypeError, ValueError):
        return True
    return math.isnan(number) or math.isinf(number)


def currency_symbol(currency: str | None) -> str:
    """``'USD'`` -> ``'$'``; an unknown or missing code -> the code plus a space."""
    if not currency:
        return ""
    return CURRENCY_SYMBOLS.get(currency.upper(), f"{currency.upper()} ")


def format_number(value: Any, decimals: int = 2) -> str:
    """Thousands-separated fixed-point, or an em dash."""
    if _is_missing(value):
        return _MISSING
    return f"{float(value):,.{decimals}f}"


def format_money(value: Any, currency: str | None = None, decimals: int = 2) -> str:
    """A price with its currency symbol: ``'$198.42'``, ``'Rs 1,402.30'``."""
    if _is_missing(value):
        return _MISSING
    return f"{currency_symbol(currency)}{float(value):,.{decimals}f}"


def format_compact(value: Any, currency: str | None = None) -> str:
    """Large money in the units people read it in: ``'$3.21T'``, ``'Rs 1.84B'``.

    Scales to K / M / B / T. Market caps and volumes are the only places this
    is used, and both are unreadable in full digits -- ``3214567890123`` tells
    a reader nothing that ``$3.21T`` does not tell them faster.

    Indian listings are quoted in crore locally, but mixing crore and trillion
    in one dashboard is worse than being consistently international, so every
    currency uses the same scale with its own symbol.
    """
    if _is_missing(value):
        return _MISSING

    number = float(value)
    sign = "-" if number < 0 else ""
    number = abs(number)
    symbol = currency_symbol(currency)

    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if number >= threshold:
            return f"{sign}{symbol}{number / threshold:,.2f}{suffix}"
    return f"{sign}{symbol}{number:,.2f}"


def format_volume(value: Any) -> str:
    """Share counts: compact, no currency, no decimals below a thousand."""
    if _is_missing(value):
        return _MISSING
    number = float(value)
    if abs(number) < 1_000:
        return f"{number:,.0f}"
    return format_compact(number)


def format_percent(value: Any, decimals: int = 2, signed: bool = True) -> str:
    """A *fraction* as a percentage: ``0.2412`` -> ``'+24.12%'``.

    Takes fractions, not percentages, because that is what every function in
    :mod:`src.indicators` returns. ``signed`` keeps the plus sign on gains,
    which is what a change figure wants and a volatility figure does not.
    """
    if _is_missing(value):
        return _MISSING
    number = float(value) * 100.0
    return f"{number:+.{decimals}f}%" if signed else f"{number:.{decimals}f}%"


def format_date(value: Any, fmt: str = "%d %b %Y") -> str:
    """A date or timestamp as ``'26 Nov 2026'``."""
    if value is None:
        return _MISSING
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.strftime(fmt)
    try:
        import pandas as pd

        stamp = pd.Timestamp(value)
    except Exception:
        return _MISSING
    if stamp is None or stamp is getattr(stamp, "NaT", object()):
        return _MISSING
    return stamp.strftime(fmt)


def title_case_name(name: str | None) -> str:
    """Company names in Title Case, never shouted.

    Yahoo returns a mix of ``'Apple Inc.'`` and ``'RELIANCE INDUSTRIES LTD'``.
    An all-caps heading reads as shouting next to the rest of the page, so a
    name that is entirely upper case is re-cased; one that already has mixed
    case is left exactly as it came, since ``'eBay'`` and ``'iShares'`` are
    correct as written and title-casing would damage them.
    """
    if not name:
        return ""
    text = str(name).strip()
    if text and text == text.upper():
        return text.title()
    return text
