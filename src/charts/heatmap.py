"""Tab 5: the monthly-returns grid, and the daily-returns distribution.

The histogram lives here rather than in a ninth module because the spec puts
both on the Returns Analysis tab and both answer the same question -- how this
stock's returns are distributed -- one by calendar month, one by magnitude.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src import config
from src.charts.theme import apply_theme, empty_figure
from src.indicators import daily_returns, monthly_returns_pivot

__all__ = ["returns_distribution_chart", "returns_heatmap"]

#: Red at a loss, white at zero, green at a gain. Built by hand rather than
#: taken from Plotly's RdYlGn so the two ends match COLOR_DOWN / COLOR_UP and
#: the grid looks like the rest of the dashboard.
_DIVERGING_SCALE = (
    (0.0, "#B91C1C"),
    (0.25, "#F87171"),
    (0.5, "#FFFFFF"),
    (0.75, "#4ADE80"),
    (1.0, "#15803D"),
)


def returns_heatmap(
    series: pd.Series,
    *,
    ticker: str = "",
    title: str | None = None,
    height: int = config.CHART_HEIGHT,
) -> go.Figure:
    """Monthly returns as a years-by-months grid.

    Takes the ``Close`` series, not the frame, because that is all it needs
    and it keeps the function usable on any price series.

    The colour scale is symmetric about zero and its range is set from the
    largest absolute return in the grid, so white always means "flat". Letting
    Plotly autoscale would put white wherever the midpoint of the data happens
    to fall -- in a year of steady gains, a mediocre month would be coloured
    as a loss.

    Empty months stay blank rather than being drawn as zero: a part-finished
    year has no December, and a green-tinted zero would read as "flat month".
    """
    pivot = monthly_returns_pivot(series)
    heading = title if title is not None else f"{ticker} monthly returns".strip()

    if pivot.empty:
        return empty_figure(
            "This range is too short to hold a full calendar month of returns.",
            title=heading,
            height=height,
        )

    values = pivot.to_numpy(dtype="float64")
    finite = values[np.isfinite(values)]
    limit = float(np.max(np.abs(finite))) if finite.size else 0.01
    limit = max(limit, 0.01)

    text = np.where(
        np.isfinite(values),
        np.vectorize(lambda v: f"{v * 100:.1f}" if np.isfinite(v) else "")(values),
        "",
    )

    fig = go.Figure(
        go.Heatmap(
            z=values,
            x=list(pivot.columns),
            y=[str(year) for year in pivot.index],
            colorscale=list(_DIVERGING_SCALE),
            zmid=0.0,
            zmin=-limit,
            zmax=limit,
            text=text,
            texttemplate="%{text}",
            textfont={"size": 11},
            hovertemplate="%{y} %{x}: %{z:.2%}<extra></extra>",
            xgap=2,
            ygap=2,
            colorbar={"title": {"text": "Return"}, "tickformat": ".0%"},
        )
    )

    fig.update_yaxes(
        title_text="", autorange="reversed", type="category", automargin=True
    )
    fig.update_xaxes(title_text="", side="top", automargin=True)
    return apply_theme(
        fig,
        title=heading,
        height=max(height, 120 + 48 * len(pivot.index)),
        showlegend=False,
        caption=(
            "Cells are percent return, compounded from that month's daily "
            "returns. Blank means the month has no trading data in this range."
        ),
    )


def returns_distribution_chart(
    series: pd.Series,
    *,
    ticker: str = "",
    bins: int = 60,
    title: str | None = None,
    height: int = config.CHART_HEIGHT_SHORT,
) -> go.Figure:
    """Histogram of daily returns, with the mean marked.

    Bars are coloured by sign -- the split at zero is the first thing anyone
    reads off a returns distribution -- and the mean is drawn as a dashed line
    because for a daily series it sits very close to zero and a reader should
    see how close.

    The caption carries the two numbers the shape does not show: the mean and
    the standard deviation of the daily return, both in percent.
    """
    heading = title if title is not None else f"{ticker} daily returns".strip()

    rets = daily_returns(series).dropna() if series is not None else pd.Series(dtype="float64")
    if len(rets) < 2:
        return empty_figure(
            "Not enough rows in this range to show a returns distribution.",
            title=heading,
            height=height,
        )

    positive = rets[rets >= 0]
    negative = rets[rets < 0]

    fig = go.Figure()
    # One bin width shared by both traces, so the two colours tile instead of
    # overlapping on a boundary bin.
    width = float(rets.max() - rets.min()) / max(bins, 1) or None
    for part, color, name in (
        (negative, config.COLOR_DOWN, "Down days"),
        (positive, config.COLOR_UP, "Up days"),
    ):
        if part.empty:
            continue
        fig.add_trace(
            go.Histogram(
                x=part,
                name=name,
                marker_color=color,
                marker_line_width=0,
                opacity=0.75,
                xbins={"size": width} if width else None,
                hovertemplate="%{x:.2%}: %{y} days<extra></extra>",
            )
        )

    mean = float(rets.mean())
    std = float(rets.std(ddof=1))
    fig.add_vline(
        x=mean,
        line={"color": config.COLOR_NEUTRAL, "width": 1.5, "dash": "dash"},
        opacity=0.8,
    )

    fig.update_layout(barmode="overlay", bargap=0.02)
    fig.update_xaxes(title_text="Daily return", tickformat=".1%")
    fig.update_yaxes(title_text="Days")
    return apply_theme(
        fig,
        title=heading,
        height=height,
        caption=(
            f"{len(rets)} trading days. Mean {mean * 100:.2f}% a day, "
            f"standard deviation {std * 100:.2f}%. Dashed line is the mean."
        ),
    )
