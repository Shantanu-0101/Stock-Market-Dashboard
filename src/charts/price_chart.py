"""Tab 1: close price with any combination of SMA, EMA and Bollinger overlays."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src import config
from src.charts.theme import apply_theme, empty_figure, skip_caption
from src.indicators import available_windows

__all__ = ["price_chart"]


def _hover(name: str) -> str:
    return name + ": %{y:,.2f}<extra></extra>"


def price_chart(
    df: pd.DataFrame,
    *,
    ticker: str = "",
    sma_windows: tuple[int, ...] | list[int] = (),
    ema_spans: tuple[int, ...] | list[int] = (),
    show_bollinger: bool = False,
    title: str | None = None,
    height: int = config.CHART_HEIGHT,
) -> go.Figure:
    """Close-price line plus the overlays the caller asked for.

    Expects an enriched frame -- the overlay columns (``SMA_20``, ``EMA_12``,
    ``BB_UPPER`` ...) are read, never recomputed, so the line on the chart and
    the number in the CSV are the same number by construction.

    Overlays whose window is longer than the frame are dropped and named in
    the figure's caption instead of being drawn as an invisible all-``NaN``
    trace with a misleading legend entry. A requested overlay whose column is
    simply absent is skipped silently: that is the caller passing a window
    ``enrich`` was not run with, not a data problem to explain to the user.

    Bollinger bands are drawn as one filled region between the two edges with
    the middle band on top, so the band reads as a channel rather than as
    three more lines competing with the moving averages.
    """
    if df is None or df.empty or "Close" not in df.columns:
        return empty_figure(
            "No price data to plot for this selection.",
            title=title or f"{ticker} price".strip(),
            height=height,
        )

    rows = len(df)
    usable_sma, skipped_sma = available_windows(rows, list(sma_windows))
    usable_ema, skipped_ema = available_windows(rows, list(ema_spans))

    fig = go.Figure()

    # Bollinger needs the same guard as the moving averages: over fewer rows
    # than its window every band value is NaN, and the three legend entries
    # would promise a band that is not on the chart.
    bollinger_possible = (
        show_bollinger
        and {"BB_UPPER", "BB_LOWER"} <= set(df.columns)
        and not df["BB_UPPER"].dropna().empty
    )
    bollinger_skipped = show_bollinger and not bollinger_possible

    if bollinger_possible:
        band_label = (
            f"Bollinger ({config.BOLLINGER_WINDOW}, "
            f"{config.BOLLINGER_NUM_STD:g} sd)"
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["BB_UPPER"],
                name=band_label,
                line={"color": config.OVERLAY_COLORS["BB_UPPER"], "width": 1},
                hovertemplate=_hover("BB upper"),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["BB_LOWER"],
                name="Bollinger lower",
                line={"color": config.OVERLAY_COLORS["BB_LOWER"], "width": 1},
                fill="tonexty",
                fillcolor=config.COLOR_BAND,
                hovertemplate=_hover("BB lower"),
                showlegend=False,
            )
        )
        if "BB_MIDDLE" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["BB_MIDDLE"],
                    name=f"Bollinger middle (SMA {config.BOLLINGER_WINDOW})",
                    line={
                        "color": config.OVERLAY_COLORS["BB_MIDDLE"],
                        "width": 1,
                        "dash": "dot",
                    },
                    hovertemplate=_hover("BB middle"),
                )
            )

    # Close goes in after the filled band so the fill cannot sit on top of it,
    # and before the moving averages so the overlays stay readable above it.
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["Close"],
            name="Close",
            line={"color": config.COLOR_PRICE, "width": 2},
            hovertemplate=_hover("Close"),
        )
    )

    for window in usable_sma:
        column = f"SMA_{window}"
        if column not in df.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[column],
                name=f"SMA {window}",
                line={
                    "color": config.OVERLAY_COLORS.get(column, config.COLOR_NEUTRAL),
                    "width": 1.4,
                },
                hovertemplate=_hover(f"SMA {window}"),
            )
        )

    for span in usable_ema:
        column = f"EMA_{span}"
        if column not in df.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[column],
                name=f"EMA {span}",
                line={
                    "color": config.OVERLAY_COLORS.get(column, config.COLOR_NEUTRAL),
                    "width": 1.4,
                    "dash": "dash",
                },
                hovertemplate=_hover(f"EMA {span}"),
            )
        )

    caption = " ".join(
        part
        for part in (
            skip_caption(skipped_sma, rows, "SMA"),
            skip_caption(skipped_ema, rows, "EMA"),
            (
                f"Bollinger needs {config.BOLLINGER_WINDOW} rows; this range "
                f"has {rows}; band not drawn."
                if bollinger_skipped
                else ""
            ),
        )
        if part
    )

    fig.update_yaxes(title_text="Price", tickformat=",.2f")
    return apply_theme(
        fig,
        title=title if title is not None else f"{ticker} close price".strip(),
        height=height,
        caption=caption or None,
    )
