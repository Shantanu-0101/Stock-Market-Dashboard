"""The KPI row as data, shared by the dashboard and the PDF report.

Both surfaces print the same eight cards. Deciding what goes in each -- which
source a figure comes from, what it falls back to -- happens here once, so the
report a user downloads cannot disagree with the page they downloaded it from.

No Streamlit import: the app draws these as metric cards, the PDF as a table.
"""

from __future__ import annotations

from typing import NamedTuple

import pandas as pd

from src.formatting import (
    format_compact,
    format_date,
    format_money,
    format_percent,
    format_volume,
)
from src.indicators import (
    annualized_volatility,
    period_return,
    periods_per_year_for,
    ytd_return,
)

__all__ = ["Kpi", "KpiSummary", "kpi_summary"]


class Kpi(NamedTuple):
    """One card: a label, its formatted value and an optional change figure."""

    label: str
    value: str
    delta: str | None = None


class KpiSummary(NamedTuple):
    """The eight cards plus the sentence that says what they were measured over."""

    cards: tuple[Kpi, ...]
    footnote: str


def kpi_summary(df: pd.DataFrame, info: dict) -> KpiSummary:
    """Build the KPI cards for a non-empty frame and its company info.

    Price and the daily change come from the fetched frame, not from
    ``info``: ``fast_info``'s ``lastPrice`` is a live quote that can disagree
    with the last row of a historical range the user chose, and a card that
    contradicts the chart below it is worse than one that is slightly stale.

    The 52-week range is the opposite case -- it is a property of the stock,
    not of the selected window, so it comes from ``info`` and falls back to
    the frame's own high/low only when Yahoo supplied nothing, labelled so
    the reader knows which they are looking at.
    """
    close = df["Close"]
    currency = info.get("currency")

    last = float(close.iloc[-1])
    previous = float(close.iloc[-2]) if len(close) > 1 else None
    change = (last / previous - 1.0) if previous else None

    high_52 = info.get("week52_high")
    low_52 = info.get("week52_low")
    range_source = "Yahoo"
    if high_52 is None or low_52 is None:
        high_52 = float(df["High"].max())
        low_52 = float(df["Low"].min())
        range_source = "this range"

    periods = periods_per_year_for(info.get("quote_type"))
    volatility = annualized_volatility(close, periods=periods)

    cards = (
        Kpi(
            "Price",
            format_money(last, currency),
            format_percent(change) if change is not None else None,
        ),
        Kpi("52w high", format_money(high_52, currency)),
        Kpi("52w low", format_money(low_52, currency)),
        Kpi("YTD return", format_percent(ytd_return(close))),
        Kpi("Market cap", format_compact(info.get("market_cap"), currency)),
        Kpi("P/E", format_money(info.get("pe_ratio"), None)),
        Kpi("Avg volume", format_volume(info.get("avg_volume"))),
        Kpi("Volatility", format_percent(volatility, signed=False)),
    )

    footnote = (
        f"{len(df)} trading days, {format_date(df.index.min())} to "
        f"{format_date(df.index.max())}. Period return "
        f"{format_percent(period_return(close))}. Volatility is annualised "
        f"over this range on {periods} periods a year; the 52-week range is "
        f"from {range_source}."
    )
    return KpiSummary(cards, footnote)
