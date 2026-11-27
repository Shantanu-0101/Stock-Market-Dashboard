"""Volume bars coloured by the day's direction, with their moving average."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src import config
from src.charts.theme import apply_theme, empty_figure
from src.indicators import sma

__all__ = ["volume_chart"]


def volume_chart(
    df: pd.DataFrame,
    *,
    ticker: str = "",
    average_window: int = config.VOLUME_AVG_WINDOW,
    title: str | None = None,
    height: int = config.CHART_HEIGHT_SHORT,
) -> go.Figure:
    """Volume bars coloured by the day's direction, with the average line.

    Bars are green when the close finished at or above the open and red when
    it did not, which is what makes a volume panel informative: a tall red bar
    is distribution, a tall green bar is accumulation, and the same bar in one
    colour says only "busy".

    The average line prefers the enriched ``VOL_SMA_<window>`` column and
    computes it only when that column is missing, so a caller handing over a
    plain cleaned frame still gets the line without having to run ``enrich``.
    Ranges shorter than the window get the bars and a caption, not a line.
    """
    if df is None or df.empty or "Volume" not in df.columns:
        return empty_figure(
            "No volume data to plot for this selection.",
            title=title or f"{ticker} volume".strip(),
            height=height,
        )

    fig = go.Figure()

    if "Open" in df.columns and "Close" in df.columns:
        up_day = df["Close"] >= df["Open"]
        colors = [config.COLOR_UP if flag else config.COLOR_DOWN for flag in up_day]
    else:
        colors = [config.COLOR_NEUTRAL] * len(df)

    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["Volume"],
            name="Volume",
            marker_color=colors,
            marker_line_width=0,
            opacity=0.6,
            hovertemplate="Volume: %{y:,.0f}<extra></extra>",
        )
    )

    caption = None
    column = f"VOL_SMA_{average_window}"
    if len(df) >= average_window:
        average = (
            df[column]
            if column in df.columns
            else sma(df["Volume"].astype("float64"), average_window)
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=average,
                name=f"{average_window}-day average",
                line={"color": config.COLOR_NEUTRAL, "width": 1.8},
                hovertemplate=f"{average_window}-day avg: %{{y:,.0f}}<extra></extra>",
            )
        )
    else:
        caption = (
            f"{average_window}-day average volume needs {average_window} rows; "
            f"this range has {len(df)}."
        )

    fig.update_yaxes(title_text="Volume", tickformat="~s")
    return apply_theme(
        fig,
        title=title if title is not None else f"{ticker} volume".strip(),
        height=height,
        caption=caption,
    )
