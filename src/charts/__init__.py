"""Every chart in the dashboard, as pure ``(data, options) -> Figure`` functions.

The PDF generator and the notebook call the same functions and get the same
figure, so a chart cannot look one way in the report and another in the
walkthrough. The Power BI report draws its own visuals.

Each function takes already-computed data -- a frame from
:func:`src.indicators.enrich`, or a mapping of symbol to frame from
:func:`src.data.fetcher.fetch_many` -- and never fetches or recomputes an
indicator. When there is nothing to draw, they return a themed figure holding
an explanation rather than raising, so the caller can render the result
unconditionally.
"""

from __future__ import annotations

from src.charts.candlestick import candlestick_chart
from src.charts.comparison import comparison_chart, first_common_date
from src.charts.correlation import correlation_chart, returns_correlation
from src.charts.heatmap import returns_distribution_chart, returns_heatmap
from src.charts.macd_chart import macd_chart
from src.charts.price_chart import price_chart
from src.charts.rsi_chart import rsi_chart
from src.charts.theme import (
    TEMPLATE_NAME,
    apply_theme,
    empty_figure,
    register_template,
    skip_caption,
)
from src.charts.volume_chart import volume_chart

__all__ = [
    "TEMPLATE_NAME",
    "apply_theme",
    "candlestick_chart",
    "comparison_chart",
    "correlation_chart",
    "empty_figure",
    "first_common_date",
    "macd_chart",
    "price_chart",
    "register_template",
    "returns_correlation",
    "returns_distribution_chart",
    "returns_heatmap",
    "rsi_chart",
    "skip_caption",
    "volume_chart",
]
