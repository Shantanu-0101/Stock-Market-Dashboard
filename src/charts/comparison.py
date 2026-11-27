"""Several tickers rebased to a common start, so they can be compared."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd
import plotly.graph_objects as go

from src import config
from src.charts.theme import apply_theme, empty_figure

__all__ = ["comparison_chart", "first_common_date"]

#: Every series starts here, so a reading of 130 means "up 30% since the start".
BASE_VALUE: float = 100.0


def first_common_date(frames: Mapping[str, pd.DataFrame]) -> pd.Timestamp | None:
    """The earliest date on which *every* frame has a close price.

    This is the whole reason the comparison chart needs its own helper. Rebasing
    each series to its own first row looks right and is wrong: US markets,
    ``.NS`` tickers and crypto keep different calendars, so AAPL's first row
    may be a day that RELIANCE.NS did not trade, and crypto has rows on
    weekends that neither equity market has. Two series normalised to two
    different days are not comparable, and the error compounds over the range.

    Returns ``None`` when the frames share no date at all -- different
    holidays can leave a one-week window with no overlap.
    """
    common: pd.Index | None = None
    for frame in frames.values():
        if frame is None or frame.empty or "Close" not in frame.columns:
            continue
        dates = frame["Close"].dropna().index
        common = dates if common is None else common.intersection(dates)
    if common is None or len(common) == 0:
        return None
    return pd.Timestamp(common.min())


def comparison_chart(
    frames: Mapping[str, pd.DataFrame],
    *,
    normalise: bool = True,
    title: str | None = None,
    height: int = config.CHART_HEIGHT,
) -> go.Figure:
    """Overlay 2-5 tickers, by default rebased to 100 at the first common date.

    Parameters
    ----------
    frames:
        Symbol to cleaned (or enriched) frame, as
        :func:`src.data.fetcher.fetch_many` returns. Frames that are empty or
        have no ``Close`` are skipped rather than failing the whole chart --
        one dead symbol in a five-way comparison must not blank the chart.
    normalise:
        ``True`` plots percentage growth from a shared base, which is the only
        way a 250-dollar stock and a 90,000-dollar coin fit on one axis.
        ``False`` plots raw closes, useful only for tickers in the same
        currency and a similar price range.

    A single usable frame still draws: the chart is then just that ticker's
    growth.
    """
    usable = {
        symbol: frame
        for symbol, frame in frames.items()
        if frame is not None and not frame.empty and "Close" in frame.columns
        and not frame["Close"].dropna().empty
    }
    if not usable:
        return empty_figure(
            "Pick at least one ticker that returned data to compare.",
            title=title or "Comparison",
            height=height,
        )

    base_date = first_common_date(usable) if normalise else None
    if normalise and base_date is None:
        return empty_figure(
            "These tickers share no common trading day in this range -- "
            "widen the date range to compare them.",
            title=title or "Comparison",
            height=height,
        )

    fig = go.Figure()
    for position, (symbol, frame) in enumerate(sorted(usable.items())):
        close = frame["Close"].dropna()
        if normalise:
            base = float(close.loc[close.index >= base_date].iloc[0])
            if base == 0.0:
                continue
            values = close / base * BASE_VALUE
            hover = symbol + ": %{y:.1f}<extra></extra>"
        else:
            values = close
            hover = symbol + ": %{y:,.2f}<extra></extra>"

        fig.add_trace(
            go.Scatter(
                x=values.index,
                y=values,
                name=symbol,
                line={
                    "color": config.SERIES_PALETTE[
                        position % len(config.SERIES_PALETTE)
                    ],
                    "width": 1.8,
                },
                hovertemplate=hover,
            )
        )

    if normalise:
        fig.add_hline(
            y=BASE_VALUE,
            line={"color": config.COLOR_NEUTRAL, "width": 1, "dash": "dot"},
            opacity=0.6,
        )
        fig.update_yaxes(title_text=f"Indexed ({BASE_VALUE:.0f} = start)")
        caption = (
            f"All series set to {BASE_VALUE:.0f} on "
            f"{base_date:%d %b %Y}, the first day every ticker traded in this "
            "range. Currencies differ, so compare growth, not levels."
        )
    else:
        fig.update_yaxes(title_text="Close", tickformat=",.2f")
        caption = "Raw closing prices; tickers in different currencies are not comparable."

    return apply_theme(
        fig,
        title=title if title is not None else "Relative performance",
        height=height,
        caption=caption,
    )
