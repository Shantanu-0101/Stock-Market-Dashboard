"""Tab 3 (lower panel): MACD line, signal line and the histogram."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src import config
from src.charts.theme import apply_theme, empty_figure

__all__ = ["macd_chart"]

_COLUMNS = ("MACD", "MACD_SIGNAL", "MACD_HIST")


def macd_chart(
    df: pd.DataFrame,
    *,
    ticker: str = "",
    title: str | None = None,
    height: int = config.CHART_HEIGHT_SHORT,
) -> go.Figure:
    """MACD and signal lines over a histogram coloured by sign.

    All three series share one y-axis on purpose: the histogram *is* the gap
    between the two lines, and putting it on a secondary axis would let it
    disagree visually with the lines it is derived from. They are in the same
    units, so one axis is also honest.

    Histogram bars above zero are green and below zero red, which reads as
    "the fast average is pulling away from the slow one" without the viewer
    having to compare two lines pixel by pixel.

    Reads the enriched ``MACD``, ``MACD_SIGNAL`` and ``MACD_HIST`` columns.
    """
    if df is None or df.empty or not set(_COLUMNS) <= set(df.columns):
        return empty_figure(
            "No MACD columns to plot -- run enrich() on the frame first.",
            title=title or f"{ticker} MACD".strip(),
            height=height,
        )

    if df["MACD_SIGNAL"].dropna().empty:
        needed = config.MACD_SLOW + config.MACD_SIGNAL
        return empty_figure(
            f"MACD({config.MACD_FAST}, {config.MACD_SLOW}, {config.MACD_SIGNAL}) "
            f"needs about {needed} rows; this range has {len(df)}.",
            title=title or f"{ticker} MACD".strip(),
            height=height,
        )

    histogram = df["MACD_HIST"]
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df.index,
            y=histogram,
            name="Histogram",
            marker_color=[
                config.COLOR_DOWN if value < 0 else config.COLOR_UP
                for value in histogram.fillna(0.0)
            ],
            marker_line_width=0,
            opacity=0.5,
            hovertemplate="Histogram: %{y:,.3f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MACD"],
            name=f"MACD ({config.MACD_FAST}, {config.MACD_SLOW})",
            line={"color": config.COLOR_PRICE, "width": 1.8},
            hovertemplate="MACD: %{y:,.3f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MACD_SIGNAL"],
            name=f"Signal ({config.MACD_SIGNAL})",
            line={"color": config.OVERLAY_COLORS["SMA_20"], "width": 1.6},
            hovertemplate="Signal: %{y:,.3f}<extra></extra>",
        )
    )

    fig.add_hline(
        y=0,
        line={"color": config.COLOR_NEUTRAL, "width": 1},
        opacity=0.6,
    )

    fig.update_yaxes(title_text="MACD", tickformat=",.2f")
    return apply_theme(
        fig,
        title=title if title is not None else f"{ticker} MACD".strip(),
        height=height,
    )
