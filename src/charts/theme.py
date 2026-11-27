"""One layout template, applied by every chart in this package.

The eight chart modules are independent functions, but they have to look like
one product in the notebook and in the PDF. Everything shared — fonts,
margins, hover behaviour, grid colour, the empty-state figure and the "window
too long for this range" caption — lives here, so changing the look of the
charts is a one-file edit rather than eight.
"""

from __future__ import annotations

import plotly.graph_objects as go

from src import config

__all__ = [
    "TEMPLATE_NAME",
    "apply_theme",
    "empty_figure",
    "register_template",
    "skip_caption",
]

#: Name the template is registered under in Plotly's registry.
TEMPLATE_NAME: str = "stockdash"

_registered = False


def register_template() -> str:
    """Register the project template with Plotly and return its name.

    Idempotent, and called by :func:`apply_theme`, so no caller has to
    remember to do it. It extends ``plotly_white`` rather than starting from
    scratch: only the handful of properties we actually care about are
    overridden, and future Plotly improvements to the base template still
    arrive.
    """
    global _registered
    if _registered:
        return TEMPLATE_NAME

    import plotly.io as pio

    base = pio.templates[config.PLOTLY_TEMPLATE]
    template = base.to_plotly_json()
    template["layout"].update(
        {
            "font": {"family": "Inter, Segoe UI, system-ui, sans-serif", "size": 13},
            # Pinned to the top of the figure. Left to itself Plotly centres
            # the title in the top margin, where a legend wrapping in a narrow
            # window grows straight into it.
            "title": {
                "font": {"size": 18},
                "x": 0.0,
                "xanchor": "left",
                "yref": "container",
                "y": 1.0,
                "yanchor": "top",
                "pad": {"t": 10},
            },
            "margin": {"l": 56, "r": 24, "t": 56, "b": 44},
            "hovermode": "x unified",
            "hoverlabel": {"namelength": -1},
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "left",
                "x": 0.0,
                "title": {"text": ""},
                # Without this, a horizontal legend lists the traces in
                # reverse, putting "Close" in the middle of its own overlays.
                "traceorder": "normal",
            },
            "xaxis": {
                "showgrid": False,
                "showline": True,
                "linecolor": "#E2E8F0",
                "ticks": "outside",
                "tickcolor": "#E2E8F0",
            },
            "yaxis": {
                "gridcolor": "#EEF2F7",
                "zeroline": False,
                "showline": False,
                # Widen the margin for long tick labels ("60,500.00"), which
                # otherwise run into the axis title.
                "automargin": True,
                "title": {"standoff": 8},
            },
        }
    )

    pio.templates[TEMPLATE_NAME] = template
    _registered = True
    return TEMPLATE_NAME


def apply_theme(
    fig: go.Figure,
    *,
    title: str | None = None,
    height: int = config.CHART_HEIGHT,
    showlegend: bool = True,
    caption: str | None = None,
) -> go.Figure:
    """Apply the shared template to ``fig`` and return the same figure.

    Every chart function ends with this call. ``caption`` is drawn as a small
    muted annotation under the plot, which is where the "SMA 200 needs 200
    rows" notes and the correlation-method footnote go: that text belongs to
    the figure, not to the page around it, so it survives into the PDF and the
    exported HTML.
    """
    # The horizontal legend sits above the plot area and grows upward into the
    # title when it wraps, which it does as soon as the container is narrow --
    # a price chart with three overlays and a Bollinger band has six entries
    # and wraps in any half-width column. Budget a row of legend per four
    # traces, and give a 300px panel extra room on top of that, since it has
    # barely any plot area to give up.
    if showlegend and len(fig.data) > 0:
        legend_rows = -(-len(fig.data) // 4)  # ceil
        # Even a single legend row needs its own space under the title.
        top = 78 + 22 * (legend_rows - 1)
        if height <= config.CHART_HEIGHT_SHORT:
            top += 20
    else:
        top = 56
    bottom = 86 if caption else 44

    fig.update_layout(
        template=register_template(),
        height=height,
        showlegend=showlegend,
        margin={"t": top, "b": bottom},
    )
    if title is not None:
        fig.update_layout(title_text=title)

    if caption:
        # Annotation y is a fraction of the *plot area*, not of the figure, so
        # a fixed -0.16 lands 24px down on a tall chart and on top of the
        # x-axis title on a short one. Convert a fixed pixel offset instead,
        # clearing the tick labels and any axis title below them.
        plot_height = max(height - top - bottom, 1)
        fig.add_annotation(
            text=caption,
            xref="paper",
            yref="paper",
            x=0.0,
            y=-(62.0 / plot_height),
            xanchor="left",
            yanchor="top",
            showarrow=False,
            align="left",
            font={"size": 11, "color": config.COLOR_NEUTRAL},
        )
    return fig


def empty_figure(
    message: str,
    *,
    title: str | None = None,
    height: int = config.CHART_HEIGHT,
) -> go.Figure:
    """A themed figure holding nothing but a centred explanation.

    Returned instead of raising whenever a chart has no data to draw — a
    one-week range asked for a monthly heatmap, a single ticker asked for a
    correlation matrix. The caller can then render the result unconditionally and
    the user reads why the panel is blank, rather than seeing an empty set of
    axes or a traceback.
    """
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        align="center",
        font={"size": 13, "color": config.COLOR_NEUTRAL},
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return apply_theme(fig, title=title, height=height, showlegend=False)


def skip_caption(skipped: list[int], row_count: int, label: str) -> str:
    """Phrase the overlays that were left out because the range is too short.

    ``skip_caption([200], 23, "SMA")`` gives
    ``"SMA 200 needs 200 rows; this range has 23."`` Returns ``""`` when
    nothing was skipped, so callers can join several of these and pass the
    result straight to ``caption``.
    """
    if not skipped:
        return ""
    windows = ", ".join(str(w) for w in skipped)
    noun = "window" if len(skipped) == 1 else "windows"
    return (
        f"{label} {windows} {'needs' if len(skipped) == 1 else 'need'} more rows "
        f"than this range has ({row_count}); {noun} not drawn."
    )
