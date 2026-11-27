"""Single source of truth for project defaults, indicator windows and colours.

Nothing in here imports pandas or plotly, so every other module
(and the walkthroughs, and the report generator) can read these constants cheaply.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Tickers
# --------------------------------------------------------------------------

DEFAULT_TICKER: str = "AAPL"

#: The demo set from SPEC.md — US equities, Indian equities (.NS) and crypto.
DEMO_TICKERS: tuple[str, ...] = (
    "AAPL",
    "TSLA",
    "RELIANCE.NS",
    "TCS.NS",
    "BTC-USD",
)

# --------------------------------------------------------------------------
# Indicator windows (all from the SPEC.md indicator table)
# --------------------------------------------------------------------------

SMA_WINDOWS: tuple[int, ...] = (20, 50, 200)
EMA_SPANS: tuple[int, ...] = (12, 26)

RSI_PERIOD: int = 14
RSI_OVERBOUGHT: int = 70
RSI_OVERSOLD: int = 30

MACD_FAST: int = 12
MACD_SLOW: int = 26
MACD_SIGNAL: int = 9

BOLLINGER_WINDOW: int = 20
BOLLINGER_NUM_STD: float = 2.0

VOLUME_AVG_WINDOW: int = 20

#: Trading days per year, used to annualise volatility.
TRADING_DAYS_PER_YEAR: int = 252

# --------------------------------------------------------------------------
# Power BI data export
# --------------------------------------------------------------------------

#: Calendar days of history written for every ticker: the longest preset.
HISTORY_DAYS: int = 365 * 5

#: Calendar days the PDF report and the written summary describe.
SUMMARY_DAYS: int = 365

#: Width of one bar in the daily-returns histogram, in percentage points.
RETURN_BIN_PERCENT: float = 0.5

# --------------------------------------------------------------------------
# Chart colours and theme
# --------------------------------------------------------------------------

COLOR_UP: str = "#16A34A"        # green — gains, bullish candles
COLOR_DOWN: str = "#DC2626"      # red — losses, bearish candles
COLOR_PRICE: str = "#2563EB"     # close-price line
COLOR_NEUTRAL: str = "#64748B"   # axes, reference lines, muted text
COLOR_BAND: str = "rgba(37, 99, 235, 0.12)"  # Bollinger / RSI band fill

#: Deterministic palette for multi-series charts (comparison, overlays).
#: Ordered so adjacent series stay distinguishable.
SERIES_PALETTE: tuple[str, ...] = (
    "#2563EB",
    "#EA580C",
    "#16A34A",
    "#9333EA",
    "#0891B2",
)

#: Per-overlay colours so SMA-50 is the same colour in the notebook and the PDF.
OVERLAY_COLORS: dict[str, str] = {
    "SMA_20": "#F59E0B",
    "SMA_50": "#8B5CF6",
    "SMA_200": "#0EA5E9",
    "EMA_12": "#EC4899",
    "EMA_26": "#14B8A6",
    "BB_UPPER": "#94A3B8",
    "BB_MIDDLE": "#64748B",
    "BB_LOWER": "#94A3B8",
}

PLOTLY_TEMPLATE: str = "plotly_white"
CHART_HEIGHT: int = 520
CHART_HEIGHT_SHORT: int = 300

# --------------------------------------------------------------------------
# Titles and wording
# --------------------------------------------------------------------------

APP_TITLE: str = "Stock Market Dashboard"
MISSING_VALUE_DISPLAY: str = "—"

#: Shown wherever the rules-based commentary appears (PDF, Power BI report).
DISCLAIMER: str = (
    "This dashboard is a mechanical summary of technical indicators computed "
    "from public market data. It is not investment advice."
)
