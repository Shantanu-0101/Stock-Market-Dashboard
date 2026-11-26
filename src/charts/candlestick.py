"""Tab 2 (upper panel): OHLC candles with volume in a shared-x subplot."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src import config
from src.charts.theme import apply_theme, empty_figure

__all__ = ["candlestick_chart"]

#: The candle panel gets three quarters of the height, volume the rest.
_ROW_HEIGHTS = (0.74, 0.26)


def candlestick_chart(
    df: pd.DataFrame,
    *,
    ticker: str = "",
    show_volume: bool = True,
    title: str | None = None,
    height: int = config.CHART_HEIGHT,
) -> go.Figure:
    """Green/red OHLC candles, optionally over a volume subplot.

    The range slider is switched off deliberately. Plotly draws it by default
    on candlestick charts, where it costs around 60px of vertical space and
    duplicates zoom that the modebar and scroll already provide; on a two-row
    figure it also detaches from the subplot it is meant to control.

    ``show_volume=False`` returns the single-panel version, which is what the
    PDF uses: at page width the volume strip is too short to read.
    """
    required = {"Open", "High", "Low", "Close"}
    if df is None or df.empty or not required <= set(df.columns):
        return empty_figure(
            "No OHLC data to plot for this selection.",
            title=title or f"{ticker} candlestick".strip(),
            height=height,
        )

    has_volume = show_volume and "Volume" in df.columns

    if has_volume:
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            row_heights=list(_ROW_HEIGHTS),
        )
    else:
        fig = go.Figure()

    candles = go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name=ticker or "OHLC",
        increasing_line_color=config.COLOR_UP,
        increasing_fillcolor=config.COLOR_UP,
        decreasing_line_color=config.COLOR_DOWN,
        decreasing_fillcolor=config.COLOR_DOWN,
        line={"width": 1},
        showlegend=False,
    )

    if has_volume:
        fig.add_trace(candles, row=1, col=1)
        up_day = df["Close"] >= df["Open"]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["Volume"],
                name="Volume",
                marker_color=[
                    config.COLOR_UP if flag else config.COLOR_DOWN for flag in up_day
                ],
                marker_line_width=0,
                opacity=0.55,
                hovertemplate="Volume: %{y:,.0f}<extra></extra>",
                showlegend=False,
            ),
            row=2,
            col=1,
        )
        fig.update_yaxes(title_text="Price", tickformat=",.2f", row=1, col=1)
        fig.update_yaxes(title_text="Volume", tickformat="~s", row=2, col=1)
        fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
        fig.update_xaxes(rangeslider_visible=False, row=2, col=1)
    else:
        fig.add_trace(candles)
        fig.update_yaxes(title_text="Price", tickformat=",.2f")
        fig.update_xaxes(rangeslider_visible=False)

    return apply_theme(
        fig,
        title=title if title is not None else f"{ticker} candlestick".strip(),
        height=height,
        showlegend=False,
    )
