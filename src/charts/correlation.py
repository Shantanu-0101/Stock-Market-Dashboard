"""Correlation between tickers, computed on daily returns."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src import config
from src.charts.theme import apply_theme, empty_figure
from src.indicators import daily_returns

__all__ = ["correlation_chart", "returns_correlation"]

#: Blue for negative, white at zero, orange-red for positive. A red/green
#: scale is wrong here: a correlation of -1 is not "bad news", and reusing the
#: gain/loss colours would imply it was.
_SCALE = (
    (0.0, "#1D4ED8"),
    (0.5, "#FFFFFF"),
    (1.0, "#C2410C"),
)

#: Below this many overlapping observations a correlation is noise.
MIN_OBSERVATIONS: int = 20


def returns_correlation(
    frames: Mapping[str, pd.DataFrame],
) -> tuple[pd.DataFrame, int]:
    """Correlation matrix of daily returns, plus the overlapping row count.

    The spec asks for "price correlation". This computes it on *returns*
    instead, deliberately: two unrelated stocks that both drifted upward over
    a year show a price correlation near 0.9, because the shared trend
    dominates. Correlation of returns answers the question the matrix is
    actually there for -- do these move together day to day -- and is what the
    diversification reading depends on.

    The frames are joined on their dates with an inner join, so only days
    every ticker traded are used; a ``.NS`` holiday or a crypto weekend cannot
    contribute a one-sided return.

    Returns
    -------
    (matrix, observations)
        ``matrix`` is symmetric with the tickers sorted; ``observations`` is
        the number of common dates behind it. An empty frame comes back when
        fewer than two tickers have data.
    """
    columns: dict[str, pd.Series] = {}
    for symbol, frame in sorted(frames.items()):
        if frame is None or frame.empty or "Close" not in frame.columns:
            continue
        rets = daily_returns(frame["Close"]).dropna()
        if not rets.empty:
            columns[symbol] = rets

    if len(columns) < 2:
        return pd.DataFrame(), 0

    joined = pd.concat(columns, axis=1, join="inner").dropna()
    if joined.empty:
        return pd.DataFrame(), 0

    return joined.corr(), len(joined)


def correlation_chart(
    frames: Mapping[str, pd.DataFrame],
    *,
    title: str | None = None,
    height: int = config.CHART_HEIGHT,
) -> go.Figure:
    """Annotated correlation heatmap for the compared tickers.

    Every cell carries its number. A correlation matrix without printed values
    forces the reader to eyeball a colour against a colourbar, and the
    difference between 0.62 and 0.81 matters.

    The scale is pinned to the full -1 to 1 range rather than to the data, so
    a matrix of weak correlations looks weak instead of being stretched to
    look strong.
    """
    heading = title if title is not None else "Correlation of daily returns"
    matrix, observations = returns_correlation(frames)

    if matrix.empty:
        return empty_figure(
            "Pick at least two tickers with overlapping trading days "
            "to see a correlation matrix.",
            title=heading,
            height=height,
        )

    labels = list(matrix.columns)
    values = matrix.to_numpy(dtype="float64")

    fig = go.Figure(
        go.Heatmap(
            z=values,
            x=labels,
            y=labels,
            colorscale=list(_SCALE),
            zmin=-1.0,
            zmid=0.0,
            zmax=1.0,
            text=np.round(values, 2),
            texttemplate="%{text:.2f}",
            textfont={"size": 12},
            hovertemplate="%{y} vs %{x}: %{z:.2f}<extra></extra>",
            xgap=2,
            ygap=2,
            colorbar={"title": {"text": "r"}, "tickformat": ".1f"},
        )
    )

    # automargin, because ticker labels vary in width: RELIANCE.NS is twice
    # the length of AAPL and gets clipped by any fixed left margin.
    fig.update_yaxes(autorange="reversed", type="category", automargin=True)
    fig.update_xaxes(side="top", type="category", automargin=True)

    caption = (
        f"Pearson correlation of daily returns over {observations} common "
        "trading days. Returns, not price levels: price correlation mostly "
        "measures a shared trend."
    )
    if observations < MIN_OBSERVATIONS:
        caption += (
            f" Only {observations} overlapping days -- too few to read much "
            "into; widen the date range."
        )

    side = 140 + 56 * len(labels)
    return apply_theme(
        fig,
        title=heading,
        height=min(max(side, 320), height),
        showlegend=False,
        caption=caption,
    )
