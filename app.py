"""Stock Market Dashboard -- the Streamlit entry point.

This module orchestrates and nothing else. It reads widget values, calls the
data layer, hands the result to :func:`src.indicators.enrich`, passes frames
to the chart functions and lays the results out. There is no indicator
arithmetic and no figure construction here: anything that computes a number
lives in ``src/indicators/``, anything that draws lives in ``src/charts/``,
and anything that formats one for display lives in ``src/formatting.py`` --
so the notebook and the PDF report produce identical output from the same
calls.

Run it with::

    streamlit run app.py
"""

from __future__ import annotations

import datetime as _dt

import pandas as pd
import streamlit as st

from src import config
from src.charts import (
    candlestick_chart,
    comparison_chart,
    correlation_chart,
    macd_chart,
    price_chart,
    returns_distribution_chart,
    returns_heatmap,
    rsi_chart,
    volume_chart,
)
from src.data.cleaner import DataQualityError
from src.data.fetcher import (
    fetch_company_info,
    fetch_many,
    fetch_ohlcv,
    normalise_ticker,
    resolve_date_range,
)
from src.formatting import (
    format_compact,
    format_date,
    format_money,
    format_percent,
    format_volume,
    title_case_name,
)
from src.indicators import (
    RSI_VARIANTS,
    annualized_volatility,
    enrich,
    indicator_columns,
    period_return,
    periods_per_year_for,
    ytd_return,
)

st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=config.APP_ICON,
    layout="wide",
)

#: Figures are rendered at the container's width, and with ``theme=None``.
#:
#: Streamlit's default ``theme="streamlit"`` overwrites a figure's template
#: with its own -- colours, fonts, legend placement and margins -- which would
#: mean the chart in the dashboard and the identical call in the PDF or the
#: notebook come out looking different. ``None`` keeps the template
#: ``src.charts.theme`` registered, which is the whole point of having one.
_CHART_KWARGS = {"use_container_width": True, "theme": None}


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------


def sidebar() -> dict:
    """Draw every control and return the selections as a plain dict.

    Returning a dict rather than reading ``st.session_state`` from the body
    keeps the widget layer in one place: the rest of the file never has to
    know which widget a value came from.
    """
    with st.sidebar:
        st.header(config.APP_TITLE)

        ticker = normalise_ticker(
            st.text_input(
                "Ticker",
                value=config.DEFAULT_TICKER,
                help=(
                    "US symbols as they are (AAPL). Indian listings need the "
                    ".NS suffix (RELIANCE.NS). Crypto is a pair (BTC-USD)."
                ),
            )
        )
        st.caption("Try: " + ", ".join(config.DEMO_TICKERS))

        st.divider()
        st.subheader("Date range")
        preset = st.selectbox(
            "Preset",
            options=list(config.DATE_PRESETS),
            index=list(config.DATE_PRESETS).index(config.DEFAULT_PRESET),
        )
        custom_start = custom_end = None
        if preset == "Custom":
            today = _dt.date.today()
            custom_start = st.date_input(
                "Start", value=today - _dt.timedelta(days=365), max_value=today
            )
            custom_end = st.date_input("End", value=today, max_value=today)

        st.divider()
        st.subheader("Overlays")
        sma_windows = tuple(
            window
            for window in config.SMA_WINDOWS
            # SMA 20 and 50 on by default; 200 is off because it is blank on
            # anything shorter than a year and would look broken to a first
            # time visitor landing on a 1M range.
            if st.checkbox(f"SMA {window}", value=window in (20, 50))
        )
        ema_spans = tuple(
            span
            for span in config.EMA_SPANS
            if st.checkbox(f"EMA {span}", value=False)
        )
        show_bollinger = st.checkbox("Bollinger Bands", value=True)

        st.divider()
        st.subheader("Indicator settings")
        rsi_variant = st.selectbox(
            "RSI formula",
            options=list(RSI_VARIANTS),
            index=0,
            help=(
                "The spec's RSI averages gains and losses with a rolling "
                "mean. Wilder's original smooths them exponentially and is "
                "what most charting sites show; the two differ visibly."
            ),
        )

        st.divider()
        st.subheader("Compare")
        compare = st.multiselect(
            "Other tickers",
            options=list(config.DEMO_TICKERS),
            default=[t for t in ("TSLA", "RELIANCE.NS") if t != ticker],
            max_selections=config.MAX_COMPARE_TICKERS - 1,
            help=(
                f"Up to {config.MAX_COMPARE_TICKERS} series are compared, "
                "including the ticker above."
            ),
        )

    return {
        "ticker": ticker,
        "preset": preset,
        "custom_start": custom_start,
        "custom_end": custom_end,
        "sma_windows": sma_windows,
        "ema_spans": ema_spans,
        "show_bollinger": show_bollinger,
        "rsi_variant": rsi_variant,
        "compare": compare,
    }


# --------------------------------------------------------------------------
# KPI row
# --------------------------------------------------------------------------


def kpi_row(df: pd.DataFrame, info: dict) -> None:
    """The seven cards across the top of the page.

    Price and the daily change come from the fetched frame, not from
    ``info``: ``fast_info``'s ``lastPrice`` is a live quote that can disagree
    with the last row of a historical range the user chose, and a card that
    contradicts the chart below it is worse than one that is slightly stale.

    The 52-week range is the opposite case -- it is a property of the stock,
    not of the selected window, so it comes from ``info`` and falls back to
    the frame's own high/low only when Yahoo supplied nothing, labelled so
    the reader knows which they are looking at.
    """
    close = df["Close"]
    currency = info.get("currency")

    last = float(close.iloc[-1])
    previous = float(close.iloc[-2]) if len(close) > 1 else None
    change = (last / previous - 1.0) if previous else None

    high_52 = info.get("week52_high")
    low_52 = info.get("week52_low")
    range_source = "Yahoo"
    if high_52 is None or low_52 is None:
        high_52 = float(df["High"].max())
        low_52 = float(df["Low"].min())
        range_source = "this range"

    periods = periods_per_year_for(info.get("quote_type"))
    volatility = annualized_volatility(close, periods=periods)

    cards = (
        ("Price", format_money(last, currency), format_percent(change) if change is not None else None),
        ("52w high", format_money(high_52, currency), None),
        ("52w low", format_money(low_52, currency), None),
        ("YTD return", format_percent(ytd_return(close)), None),
        ("Market cap", format_compact(info.get("market_cap"), currency), None),
        ("P/E", format_money(info.get("pe_ratio"), None), None),
        ("Avg volume", format_volume(info.get("avg_volume")), None),
        ("Volatility", format_percent(volatility, signed=False), None),
    )
    # Four to a row, not all eight across: a metric value is ellipsised rather
    # than wrapped, so eight columns turn "$3.21T" into "$3...". Two rows of
    # four stay readable down to a narrow window.
    for start in (0, 4):
        for column, (label, value, delta) in zip(st.columns(4), cards[start : start + 4]):
            column.metric(label, value, delta)

    st.caption(
        f"{len(df)} trading days, {format_date(df.index.min())} to "
        f"{format_date(df.index.max())}. Period return "
        f"{format_percent(period_return(close))}. Volatility is annualised "
        f"over this range on {periods} periods a year; the 52-week range is "
        f"from {range_source}."
    )


# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------


def tab_price(df: pd.DataFrame, choices: dict) -> None:
    st.plotly_chart(
        price_chart(
            df,
            ticker=choices["ticker"],
            sma_windows=choices["sma_windows"],
            ema_spans=choices["ema_spans"],
            show_bollinger=choices["show_bollinger"],
        ),
        **_CHART_KWARGS,
    )
    if not (choices["sma_windows"] or choices["ema_spans"] or choices["show_bollinger"]):
        st.info("No overlays selected -- turn one on in the sidebar.")


def tab_candles(df: pd.DataFrame, choices: dict) -> None:
    st.plotly_chart(
        candlestick_chart(df, ticker=choices["ticker"]),
        **_CHART_KWARGS,
    )
    st.plotly_chart(
        volume_chart(df, ticker=choices["ticker"]),
        **_CHART_KWARGS,
    )


def tab_momentum(df: pd.DataFrame, choices: dict) -> None:
    st.plotly_chart(rsi_chart(df, ticker=choices["ticker"]), **_CHART_KWARGS)
    st.plotly_chart(macd_chart(df, ticker=choices["ticker"]), **_CHART_KWARGS)


def tab_compare(frames: dict[str, pd.DataFrame], errors: dict[str, str]) -> None:
    for symbol, message in errors.items():
        st.warning(f"{symbol}: {message}")

    if len(frames) < config.MIN_COMPARE_TICKERS:
        st.info(
            f"Pick at least {config.MIN_COMPARE_TICKERS - 1} other ticker in "
            "the sidebar to compare against."
        )
    st.plotly_chart(comparison_chart(frames), **_CHART_KWARGS)


def tab_returns(df: pd.DataFrame, frames: dict[str, pd.DataFrame], choices: dict) -> None:
    st.plotly_chart(
        returns_heatmap(df["Close"], ticker=choices["ticker"]),
        **_CHART_KWARGS,
    )
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            returns_distribution_chart(df["Close"], ticker=choices["ticker"]),
            **_CHART_KWARGS,
        )
    with right:
        st.plotly_chart(correlation_chart(frames), **_CHART_KWARGS)


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------


def main() -> None:
    choices = sidebar()
    ticker = choices["ticker"]

    if not ticker:
        st.info("Enter a ticker in the sidebar to begin.")
        return

    try:
        start, end = resolve_date_range(
            choices["preset"], choices["custom_start"], choices["custom_end"]
        )
    except DataQualityError as exc:
        st.error(str(exc))
        return

    try:
        with st.spinner(f"Fetching {ticker}..."):
            raw = fetch_ohlcv(ticker, start, end)
    except DataQualityError as exc:
        st.error(str(exc))
        st.caption("Known-good symbols: " + ", ".join(config.DEMO_TICKERS))
        return

    info = fetch_company_info(ticker)
    df = enrich(
        raw,
        rsi_variant=choices["rsi_variant"],
        periods_per_year=periods_per_year_for(info.get("quote_type")),
    )

    heading = title_case_name(info.get("name")) or ticker
    st.title(f"{heading} ({ticker})")
    details = [part for part in (info.get("sector"), info.get("exchange")) if part]
    if details:
        st.caption(" | ".join(details))

    kpi_row(df, info)
    st.divider()

    # The comparison set always includes the main ticker, so Tab 4 shows the
    # stock the rest of the page is about rather than only its peers.
    compare_symbols = [ticker, *[s for s in choices["compare"] if s != ticker]]
    with st.spinner("Fetching comparison tickers..."):
        frames, errors = fetch_many(compare_symbols, start, end)

    tabs = st.tabs(
        [
            "Price & Overlays",
            "Candlestick + Volume",
            "RSI + MACD",
            "Compare Stocks",
            "Returns Analysis",
        ]
    )
    with tabs[0]:
        tab_price(df, choices)
    with tabs[1]:
        tab_candles(df, choices)
    with tabs[2]:
        tab_momentum(df, choices)
    with tabs[3]:
        tab_compare(frames, errors)
    with tabs[4]:
        tab_returns(df, frames, choices)

    st.divider()
    with st.expander(f"Data table -- {len(df)} rows, {len(df.columns)} columns"):
        st.caption(
            "OHLCV plus "
            f"{len(indicator_columns())} indicator columns, exactly as the "
            "CSV download contains them."
        )
        st.dataframe(df, use_container_width=True)

    export_sidebar(df, ticker)
    st.caption(config.DISCLAIMER)


def export_sidebar(df: pd.DataFrame, ticker: str) -> None:
    """The download buttons, drawn once the frame exists.

    They are added to the sidebar from here rather than from :func:`sidebar`
    because the CSV cannot be built before the data is fetched, and a button
    that is present but dead until a later rerun is worse than one that
    appears with its payload ready.
    """
    with st.sidebar:
        st.divider()
        st.subheader("Export")
        st.download_button(
            "Download CSV",
            data=df.to_csv().encode("utf-8"),
            file_name=f"{ticker}_{df.index.min():%Y%m%d}_{df.index.max():%Y%m%d}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.button(
            "Download PDF report",
            disabled=True,
            help="Arrives with the PDF generator in Phase 6.",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
