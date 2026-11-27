# %% [markdown]
# # Stock Market Dashboard: walkthrough
#
# This walkthrough runs the whole pipeline from top to bottom:
#
# 1. **Fetch** five years of daily prices from Yahoo Finance
# 2. **Clean** the data
# 3. **Enrich** it with technical indicators
# 4. **Chart** each indicator
# 5. **Combine** the charts and KPI cards into one dashboard page
#
# Every step calls the same functions in `src/` that build the Power BI data
# and the PDF summaries, so the numbers here match the dashboard.
#
# It needs an internet connection (Yahoo Finance is free and needs no API key)
# and takes under a minute. Run it as a script from the project folder:
#
# ```
# python deliverables/walkthrough.py
# ```
#
# The notebook `walkthrough.ipynb` is generated from this script by
# `build_notebook.py`. Edit the script, then rebuild the notebook.

# %% [markdown]
# ## Setup
#
# Imports, the tickers to analyse, and a helper that saves each chart.

# %%
import datetime as dt
import html
import sys
from pathlib import Path

# Find the project folder (the one holding src/config.py), so the imports below
# work from the script, from Jupyter, and from any folder inside the project.
_start = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
ROOT = next(
    (p for p in (_start, *_start.parents) if (p / "src" / "config.py").is_file()),
    None,
)
if ROOT is None:
    raise SystemExit("Run this from inside the project folder.")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# A Windows console that cannot print the rupee sign should not stop the run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

import pandas as pd
import plotly.io as pio

from src import charts, config
from src.data.cleaner import clean_ohlcv
from src.data.fetcher import fetch_company_info, fetch_many
from src.export.commentary import commentary
from src.export.powerbi_data import summary_window
from src.indicators import (
    annualized_volatility,
    enrich,
    indicator_columns,
    periods_per_year_for,
)
from src.kpis import kpi_summary

# The main ticker gets the full analysis; the others join the comparison.
TICKER = config.DEFAULT_TICKER
COMPARE = list(config.DEMO_TICKERS)

# Charts and the combined dashboard are written here (ignored by git).
OUTPUT_DIR = ROOT / "deliverables" / "walkthrough_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# In Jupyter, show each chart twice over: interactive where the viewer supports
# Plotly, and as a still image where it does not (GitHub, for example).
IN_NOTEBOOK = "get_ipython" in globals()
if IN_NOTEBOOK:
    pio.renderers.default = "plotly_mimetype+png"
    pio.renderers["png"].width = 1000

FIGURES = {}  # name -> figure, collected for the dashboard in step 5


def show(name, figure):
    """Save a figure as HTML, keep it for the dashboard, and show it in Jupyter."""
    FIGURES[name] = figure
    path = OUTPUT_DIR / f"{name}.html"
    figure.write_html(path, include_plotlyjs="directory")
    print(f"Saved {path.relative_to(ROOT).as_posix()}")
    if IN_NOTEBOOK:
        figure.show()


print(f"Main ticker: {TICKER}")
print(f"Comparison:  {', '.join(COMPARE)}")

# %% [markdown]
# ## 1. Fetch
#
# Five years of daily open, high, low, close and volume (OHLCV) for each
# ticker, plus company details for the main one. A symbol that fails to load
# is reported, and the others carry on.

# %%
# yfinance treats the end date as exclusive, so add a day to include today.
end = dt.date.today() + dt.timedelta(days=1)
start = end - dt.timedelta(days=config.HISTORY_DAYS)

# The main ticker first, then the rest of the comparison set without repeats.
symbols = list(dict.fromkeys([TICKER, *COMPARE]))
frames, errors = fetch_many(symbols, start, end)

for symbol, message in errors.items():
    print(f"Skipped {symbol}: {message}")
if TICKER not in frames:
    raise SystemExit(f"{TICKER} did not load, so there is nothing to walk through.")

# Row counts differ by market: crypto trades every day, and the US and
# Indian exchanges keep different holidays.
for symbol, frame in frames.items():
    print(
        f"{symbol:<12} {len(frame):>5} rows  "
        f"{frame.index.min():%d %b %Y} to {frame.index.max():%d %b %Y}"
    )

# Company details. Any field Yahoo leaves empty shows as a dash.
info = fetch_company_info(TICKER)
print()
for field in ("name", "sector", "exchange", "currency", "market_cap", "pe_ratio"):
    value = info.get(field)
    print(f"{field:<11} {value if value is not None else config.MISSING_VALUE_DISPLAY}")

# %% [markdown]
# ## 2. Clean
#
# `fetch_many` has already cleaned what it returned. To show what cleaning
# does, here is a small **made-up** frame with the faults it handles:
#
# - dates out of order (sorted)
# - a repeated date (the later row wins)
# - missing prices (carried forward from the day before)
# - missing volume (set to 0, since a carried-over volume would be invented)
# - a high below its low (swapped)

# %%
messy = pd.DataFrame(
    {
        "Open": [102.0, 100.0, None, 103.0, 104.0],
        "High": [103.0, 99.0, None, 105.0, 106.0],  # 5 Jan: high below low
        "Low": [101.0, 101.0, None, 102.0, 103.0],
        "Close": [102.5, 100.5, 103.0, 104.0, 105.0],
        "Volume": [1200, 1000, None, 1500, 1600],
    },
    index=pd.to_datetime(
        # Out of order, and 8 Jan appears twice.
        ["2026-01-06", "2026-01-05", "2026-01-07", "2026-01-08", "2026-01-08"]
    ),
)
print("Before:")
print(messy.to_string())
print("\nAfter:")
print(clean_ohlcv(messy, "the example").to_string())

# %%
# The real data after cleaning: no gaps, prices as decimals, volume as whole
# numbers.
main = frames[TICKER]
print(f"{TICKER}: {int(main.isna().sum().sum())} missing values after cleaning")
print(main.dtypes.to_string())
print()
print(main.tail().round(2).to_string())

# %% [markdown]
# ## 3. Enrich
#
# `enrich` adds every indicator as a column, calculated from scratch with
# pandas:
#
# | Indicator | Formula |
# |---|---|
# | SMA 20, 50, 200 | rolling mean of the close |
# | EMA 12, 26 | exponentially weighted mean |
# | RSI 14 | 100 − 100 / (1 + average gain / average loss) |
# | MACD | EMA 12 − EMA 26; the signal line is the EMA 9 of that |
# | Bollinger Bands | SMA 20 ± 2 standard deviations |
# | Returns | daily change, and the same compounded |
# | Volatility | standard deviation of daily returns, annualised |
#
# It runs on the full five years, so a 200-day average is already filled at
# the start of the one-year view used by the charts.

# %%
# Crypto trades 365 days a year and stocks about 252; this sets how volatility
# is annualised.
periods = periods_per_year_for(info.get("quote_type"))
enriched = enrich(main, periods_per_year=periods)

# The last year of the enriched data, used by the charts below.
year = summary_window(enriched)

added = indicator_columns()
print(f"{len(added)} indicator columns added: {', '.join(added)}")
print()
print(year[["Close", "SMA_50", "SMA_200", "RSI_14", "MACD"]].tail().round(2).to_string())

# %%
# Volatility over the year, and the written summary the dashboard shows.
volatility = annualized_volatility(year["Close"], periods=periods)
print(f"Annualised volatility over the last year: {volatility:.1%}")
print()
print(commentary(year))
print()
print(config.DISCLAIMER)

# %% [markdown]
# ## 4. Charts
#
# Eight chart types. Each is a function in `src/charts/` that takes data and
# returns a Plotly figure.
#
# ### Candlestick and volume
# Green days closed at or above their open, red days below it.

# %%
show("candlestick", charts.candlestick_chart(year, ticker=TICKER))

# %% [markdown]
# ### Price with overlays
# The moving averages show the trend. The shaded Bollinger band widens when the
# price is more volatile.

# %%
show(
    "price",
    charts.price_chart(
        year,
        ticker=TICKER,
        sma_windows=config.SMA_WINDOWS,
        ema_spans=config.EMA_SPANS,
        show_bollinger=True,
    ),
)

# %% [markdown]
# ### Volume
# Daily volume against its 20-day average.

# %%
show("volume", charts.volume_chart(year, ticker=TICKER))

# %% [markdown]
# ### RSI
# Above 70 is conventionally called overbought, and below 30 oversold.

# %%
show("rsi", charts.rsi_chart(year, ticker=TICKER))

# %% [markdown]
# ### MACD
# The histogram is the gap between the MACD line and its signal line.

# %%
show("macd", charts.macd_chart(year, ticker=TICKER))

# %% [markdown]
# ### Comparison
# Every ticker starts at 100 on the first day they all traded, so growth can be
# compared across currencies.

# %%
# The last year of each ticker's prices.
last_year = {symbol: summary_window(frame) for symbol, frame in frames.items()}
show("comparison", charts.comparison_chart(last_year))

# %% [markdown]
# ### Monthly returns
# One cell per calendar month over the full five years. The first and last
# months may be part months.

# %%
show("monthly_returns", charts.returns_heatmap(main["Close"], ticker=TICKER))

# %% [markdown]
# ### Daily returns distribution
# How often each size of daily move happened over the last year.

# %%
show(
    "returns_distribution",
    charts.returns_distribution_chart(year["Close"], ticker=TICKER),
)

# %% [markdown]
# ### Correlation
# Correlation of daily **returns**, over the days every ticker traded. Prices
# that merely drift upwards together would look related when they are not.

# %%
matrix, observations = charts.returns_correlation(last_year)
print(f"{observations} common trading days")
print(matrix.round(2).to_string())
show("correlation", charts.correlation_chart(last_year))

# %% [markdown]
# ## 5. Combine into a dashboard
#
# The KPI cards, the written summary and every chart above on one HTML page.
# The interactive version, with slicers, is the Power BI report in `powerbi/`.

# %%
# The same KPI cards the PDF summaries print.
kpis = kpi_summary(year, info)
for card in kpis.cards:
    change = f"  ({card.delta})" if card.delta else ""
    print(f"{card.label:<11} {card.value}{change}")
print()
print(kpis.footnote)

# Build the page: a grid of cards, then each chart in the order shown above.
cards = "".join(
    '<div class="card">'
    f"<small>{html.escape(card.label)}</small>"
    f"<b>{html.escape(card.value)}</b>"
    f"<span>{html.escape(card.delta or '')}</span>"
    "</div>"
    for card in kpis.cards
)
panels = "".join(
    pio.to_html(figure, full_html=False, include_plotlyjs=False)
    for figure in FIGURES.values()
)
title = html.escape(f"{info.get('name') or TICKER} ({TICKER})")

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="plotly.min.js"></script>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 1100px; margin: 24px auto;
         padding: 0 16px; background: #fff; color: #0f172a; }}
  .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
  .card {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; }}
  .card small, .card b, .card span {{ display: block; }}
  .card b {{ font-size: 20px; }}
  p {{ color: #475569; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="cards">{cards}</div>
<p>{html.escape(kpis.footnote)}</p>
<p>{html.escape(commentary(year))}</p>
{panels}
<p>{html.escape(config.DISCLAIMER)}</p>
</body>
</html>
"""

# plotly.min.js was written beside the chart files by show(), so the page
# works offline.
dashboard = OUTPUT_DIR / "dashboard.html"
dashboard.write_text(page, encoding="utf-8")
print(f"\nDashboard: {dashboard.relative_to(ROOT).as_posix()} ({len(FIGURES)} charts)")
