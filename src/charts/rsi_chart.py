"""RSI with the overbought and oversold zones."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src import config
from src.charts.theme import apply_theme, empty_figure

__all__ = ["rsi_chart"]


def rsi_chart(
    df: pd.DataFrame,
    *,
    ticker: str = "",
    period: int = config.RSI_PERIOD,
    title: str | None = None,
    height: int = config.CHART_HEIGHT_SHORT,
) -> go.Figure:
    """RSI line with shaded 70/30 zones on a fixed 0-100 axis.

    The y-axis range is pinned rather than autoscaled. RSI is bounded by
    definition, and an autoscaled axis makes a quiet stretch between 45 and 55
    look like violent swings -- the whole point of the indicator is where the
    value sits relative to 30 and 70, which only a fixed axis shows.

    The two thresholds are drawn as filled bands, not dashed lines, so
    "in overbought territory" is visible at a glance in a 300px panel.

    Reads the enriched ``RSI_<period>`` column; which variant it holds (the
    spec's rolling mean or Wilder's) was decided by ``enrich`` and is named in
    the caption so the chart cannot misreport its own contents.
    """
    column = f"RSI_{period}"
    if df is None or df.empty or column not in df.columns:
        return empty_figure(
            f"No {column} column to plot -- run enrich() on the frame first.",
            title=title or f"{ticker} RSI".strip(),
            height=height,
        )

    series = df[column]
    if series.dropna().empty:
        return empty_figure(
            f"RSI({period}) needs {period + 1} rows; this range has {len(df)}.",
            title=title or f"{ticker} RSI ({period})".strip(),
            height=height,
        )

    fig = go.Figure()

    # Zones first so the line draws over them.
    fig.add_hrect(
        y0=config.RSI_OVERBOUGHT,
        y1=100,
        fillcolor=config.COLOR_DOWN,
        opacity=0.08,
        line_width=0,
        layer="below",
    )
    fig.add_hrect(
        y0=0,
        y1=config.RSI_OVERSOLD,
        fillcolor=config.COLOR_UP,
        opacity=0.08,
        line_width=0,
        layer="below",
    )
    for level in (config.RSI_OVERSOLD, 50, config.RSI_OVERBOUGHT):
        fig.add_hline(
            y=level,
            line={
                "color": config.COLOR_NEUTRAL,
                "width": 1,
                "dash": "solid" if level == 50 else "dot",
            },
            opacity=0.45,
        )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=series,
            name=f"RSI {period}",
            line={"color": config.COLOR_PRICE, "width": 1.8},
            hovertemplate="RSI: %{y:.1f}<extra></extra>",
        )
    )

    fig.update_yaxes(
        title_text="RSI",
        range=[0, 100],
        tickvals=[0, config.RSI_OVERSOLD, 50, config.RSI_OVERBOUGHT, 100],
    )
    return apply_theme(
        fig,
        title=title if title is not None else f"{ticker} RSI ({period})".strip(),
        height=height,
        showlegend=False,
        caption=(
            f"Above {config.RSI_OVERBOUGHT} is conventionally read as overbought, "
            f"below {config.RSI_OVERSOLD} as oversold. Not a signal to act on."
        ),
    )
