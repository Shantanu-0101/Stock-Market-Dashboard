"""Phase 4 verification: build every chart and write it out as HTML.

Two things are checked, because a figure can be built without being right:

1. **Structure**, with plain asserts -- trace counts, the fixed RSI axis, the
   rangeslider being off, the comparison series all starting at 100 on the
   same date, the correlation matrix being computed on returns rather than
   prices. These fail loudly in CI or on a terminal.
2. **Appearance**, by writing each figure to an HTML file in a chosen output
   directory, to be opened and looked at. A chart that passes its asserts can
   still be unreadable.

Runs on synthetic data by default, so it needs no network::

    python deliverables/check_charts.py

Add ``--live`` to build the same charts from real Yahoo data for AAPL,
RELIANCE.NS and BTC-USD, and ``--out <dir>`` to choose where the HTML goes
(default: a ``chart_preview`` folder beside this script).

Run it after any change to ``src/charts/``.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Scripts in deliverables/ are run directly, so the project root is not on
# sys.path. Put it there before importing src, the same way check_indicators
# does.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src import config
from src.charts import (
    candlestick_chart,
    comparison_chart,
    correlation_chart,
    first_common_date,
    macd_chart,
    price_chart,
    returns_correlation,
    returns_distribution_chart,
    returns_heatmap,
    rsi_chart,
    volume_chart,
)
from src.indicators import enrich

_FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    """Record one assertion without stopping at the first failure."""
    if condition:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}{' -- ' + detail if detail else ''}")
        _FAILURES.append(label)


# --------------------------------------------------------------------------
# Synthetic data
# --------------------------------------------------------------------------


def synthetic_ohlcv(
    rows: int = 900,
    seed: int = 7,
    start: str = "2022-01-03",
    drift: float = 0.0004,
    vol: float = 0.016,
) -> pd.DataFrame:
    """A plausible OHLCV frame on business days, matching the cleaner's contract.

    A geometric random walk with a fixed seed: deterministic, long enough for
    SMA(200) and for the monthly heatmap to have three years of rows, and
    shaped exactly like what ``clean_ohlcv`` hands over (float OHLC, int
    volume, ``DatetimeIndex`` named ``Date``).
    """
    rng = np.random.default_rng(seed)
    index = pd.bdate_range(start=start, periods=rows, name="Date")

    steps = rng.normal(loc=drift, scale=vol, size=rows)
    close = 100.0 * np.exp(np.cumsum(steps))

    open_ = close * (1.0 + rng.normal(0.0, 0.004, rows))
    spread = np.abs(rng.normal(0.0, 0.008, rows)) + 0.002
    high = np.maximum(open_, close) * (1.0 + spread)
    low = np.minimum(open_, close) * (1.0 - spread)
    volume = rng.integers(2_000_000, 9_000_000, rows)

    return pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume.astype("int64"),
        },
        index=index,
    )


def live_frames() -> dict[str, pd.DataFrame]:
    """Real data for the three ticker shapes the spec cares about."""
    from src.data.cleaner import DataQualityError
    from src.data.fetcher import fetch_ohlcv

    end = _dt.date.today()
    wanted = {
        "AAPL": 365 * 3,
        "RELIANCE.NS": 365 * 3,
        "BTC-USD": 365 * 3,
    }
    frames: dict[str, pd.DataFrame] = {}
    for symbol, days in wanted.items():
        try:
            frames[symbol] = fetch_ohlcv(symbol, end - _dt.timedelta(days=days), end)
            print(f"  fetched {symbol}: {len(frames[symbol])} rows")
        except DataQualityError as exc:
            print(f"  skipped {symbol}: {exc}")
    return frames


# --------------------------------------------------------------------------
# Structural checks
# --------------------------------------------------------------------------


def check_price_chart(enriched: pd.DataFrame, out: Path) -> None:
    print("\nprice_chart")
    fig = price_chart(
        enriched,
        ticker="SYNTH",
        sma_windows=config.SMA_WINDOWS,
        ema_spans=config.EMA_SPANS,
        show_bollinger=True,
    )
    names = [trace.name for trace in fig.data]
    # 3 Bollinger + close + 3 SMA + 2 EMA
    check("draws every requested overlay", len(fig.data) == 9, f"got {names}")
    check("close is present", "Close" in names)
    check(
        "Bollinger is a filled band",
        any(getattr(trace, "fill", None) == "tonexty" for trace in fig.data),
    )
    check("no caption when every window fits", not fig.layout.annotations)
    write(fig, out, "01_price_overlays")

    # Short range: SMA 50/200 and EMA 26 cannot be computed.
    short = enriched.tail(23)
    fig_short = price_chart(
        short,
        ticker="SYNTH",
        sma_windows=config.SMA_WINDOWS,
        ema_spans=config.EMA_SPANS,
        show_bollinger=False,
    )
    short_names = [trace.name for trace in fig_short.data]
    check(
        "skips windows longer than the range",
        short_names == ["Close", "SMA 20", "EMA 12"],
        f"got {short_names}",
    )
    caption = " ".join(a.text for a in fig_short.layout.annotations)
    check("names what it skipped", "SMA" in caption and "200" in caption, caption)
    check("caption states the row count", "23" in caption, caption)
    write(fig_short, out, "02_price_short_range")

    empty = price_chart(enriched.iloc[0:0], ticker="SYNTH")
    check("empty frame gives an explanation, not a crash", len(empty.data) == 0)


def check_candlestick(enriched: pd.DataFrame, out: Path) -> None:
    print("\ncandlestick_chart")
    fig = candlestick_chart(enriched.tail(180), ticker="SYNTH")
    types = [trace.type for trace in fig.data]
    check("candles plus volume bars", types == ["candlestick", "bar"], f"got {types}")
    check(
        "rangeslider is off on both rows",
        not fig.layout.xaxis.rangeslider.visible
        and not fig.layout.xaxis2.rangeslider.visible,
    )
    check("up candles are the project green", fig.data[0].increasing.line.color == config.COLOR_UP)
    write(fig, out, "03_candlestick_volume")

    single = candlestick_chart(enriched.tail(180), ticker="SYNTH", show_volume=False)
    check("single panel for the PDF", len(single.data) == 1)
    write(single, out, "04_candlestick_only")


def check_volume(enriched: pd.DataFrame, out: Path) -> None:
    print("\nvolume_chart")
    fig = volume_chart(enriched.tail(180), ticker="SYNTH")
    check("bars plus average line", len(fig.data) == 2)
    colors = fig.data[0].marker.color
    check(
        "bars are coloured per day",
        isinstance(colors, (list, tuple)) and set(colors) <= {config.COLOR_UP, config.COLOR_DOWN},
    )
    write(fig, out, "05_volume")

    short = volume_chart(enriched.tail(9), ticker="SYNTH")
    check("short range drops the average line", len(short.data) == 1)
    check("and says why", bool(short.layout.annotations))

    raw = enriched.tail(180)[["Open", "High", "Low", "Close", "Volume"]]
    check(
        "works on an un-enriched frame",
        len(volume_chart(raw, ticker="SYNTH").data) == 2,
    )


def check_rsi(enriched: pd.DataFrame, out: Path) -> None:
    print("\nrsi_chart")
    fig = rsi_chart(enriched, ticker="SYNTH")
    check("one RSI line", len(fig.data) == 1)
    check(
        "y-axis pinned to 0-100",
        tuple(fig.layout.yaxis.range) == (0, 100),
        str(fig.layout.yaxis.range),
    )
    shapes = fig.layout.shapes
    check("two zones and three reference lines", len(shapes) == 5, f"got {len(shapes)}")
    write(fig, out, "06_rsi")

    # A short range in the app is a short *fetch*, so enrich runs on the few
    # rows and the RSI column is entirely NaN. Slicing after enrich would
    # leave real values behind and test nothing.
    short = rsi_chart(enrich(synthetic_ohlcv(rows=5)), ticker="SYNTH")
    check("too-short range explains itself", len(short.data) == 0)
    check(
        "and names the rows it needed",
        "needs" in " ".join(a.text for a in short.layout.annotations),
    )


def check_macd(enriched: pd.DataFrame, out: Path) -> None:
    print("\nmacd_chart")
    fig = macd_chart(enriched, ticker="SYNTH")
    types = [trace.type for trace in fig.data]
    check("histogram plus two lines", types == ["bar", "scatter", "scatter"], f"got {types}")
    bar_colors = set(fig.data[0].marker.color)
    check(
        "histogram coloured by sign",
        bar_colors <= {config.COLOR_UP, config.COLOR_DOWN} and len(bar_colors) == 2,
    )
    check("all three share one y-axis", all(getattr(t, "yaxis", None) in (None, "y") for t in fig.data))
    write(fig, out, "07_macd")


def check_comparison(frames: dict[str, pd.DataFrame], out: Path) -> None:
    print("\ncomparison_chart")
    fig = comparison_chart(frames)
    check("one line per ticker", len(fig.data) == len(frames), f"got {len(fig.data)}")

    base = first_common_date(frames)
    check("found a common base date", base is not None)
    starts = []
    for trace in fig.data:
        xs = pd.DatetimeIndex(trace.x)
        position = int(np.searchsorted(xs, base))
        starts.append(float(trace.y[position]))
    check(
        "every series is 100 on the same date",
        all(abs(value - 100.0) < 1e-9 for value in starts),
        f"got {starts}",
    )
    check("caption names the base date", f"{base:%d %b %Y}" in fig.layout.annotations[0].text)
    write(fig, out, "08_comparison")

    raw = comparison_chart(frames, normalise=False)
    check("raw mode plots actual closes", raw.data[0].y[0] != 100.0)

    one = comparison_chart({k: v for k, v in list(frames.items())[:1]})
    check("a single ticker still draws", len(one.data) == 1)
    check("no usable frame gives an explanation", len(comparison_chart({}).data) == 0)


def check_heatmap(enriched: pd.DataFrame, out: Path) -> None:
    print("\nreturns_heatmap")
    fig = returns_heatmap(enriched["Close"], ticker="SYNTH")
    heat = fig.data[0]
    check("twelve month columns", list(heat.x) == [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ])
    check("scale is symmetric about zero", heat.zmid == 0.0 and heat.zmin == -heat.zmax)
    check("most recent year on top", list(heat.y) == sorted(heat.y, reverse=True))
    write(fig, out, "09_monthly_heatmap")

    # Three days inside one calendar month is one partial month, and drawing
    # that single cell is right -- it is a real, if thin, monthly return.
    short = returns_heatmap(enriched["Close"].tail(3), ticker="SYNTH")
    check("a part-month still draws its one cell", len(short.data) == 1)
    check("with one year row", len(short.data[0].y) == 1)

    blank = returns_heatmap(enriched["Close"].iloc[0:0], ticker="SYNTH")
    check("no rows at all explains itself", len(blank.data) == 0)

    print("\nreturns_distribution_chart")
    dist = returns_distribution_chart(enriched["Close"], ticker="SYNTH")
    check("up and down days as separate traces", len(dist.data) == 2)
    check("x-axis is a percentage", dist.layout.xaxis.tickformat == ".1%")
    check("caption carries mean and sd", "standard deviation" in dist.layout.annotations[0].text)
    write(dist, out, "10_returns_distribution")


def check_correlation(frames: dict[str, pd.DataFrame], out: Path) -> None:
    print("\ncorrelation_chart")
    matrix, observations = returns_correlation(frames)
    check("square matrix over the tickers", matrix.shape == (len(frames), len(frames)))
    check("diagonal is 1", bool(np.allclose(np.diag(matrix.to_numpy()), 1.0)))
    check("counted the overlapping days", observations > 0)

    # The point of using returns: on these synthetic series, which share no
    # noise but all drift upward, price correlation is far higher than return
    # correlation. If this ever stops holding, the module's premise is wrong.
    prices = pd.concat(
        {symbol: frame["Close"] for symbol, frame in frames.items()}, axis=1, join="inner"
    ).corr()
    pair = matrix.columns[0], matrix.columns[1]
    check(
        "returns correlation is not the price correlation",
        abs(matrix.loc[pair]) < abs(prices.loc[pair]),
        f"returns {matrix.loc[pair]:.2f} vs prices {prices.loc[pair]:.2f}",
    )

    fig = correlation_chart(frames)
    heat = fig.data[0]
    check("scale pinned to -1..1", (heat.zmin, heat.zmax) == (-1.0, 1.0))
    check("cells are annotated", heat.texttemplate is not None)
    check("caption says it used returns", "daily returns" in fig.layout.annotations[0].text)
    write(fig, out, "11_correlation")

    single = correlation_chart({k: v for k, v in list(frames.items())[:1]})
    check("one ticker gives an explanation", len(single.data) == 0)


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def write(fig, out: Path, name: str) -> None:
    """Write one figure to ``out/name.html`` for a visual pass.

    ``include_plotlyjs="directory"`` drops one shared ``plotly.min.js`` beside
    the HTML instead of inlining ~3 MB per file or pointing at a CDN, so the
    whole folder opens and renders with no network.
    """
    path = out / f"{name}.html"
    fig.write_html(path, include_plotlyjs="directory", full_html=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="also build the charts from real Yahoo data (needs network)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "chart_preview",
        help="directory for the generated HTML",
    )
    args = parser.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    print(f"Writing figures to {out}")
    print("\nBuilding synthetic data")
    enriched = enrich(synthetic_ohlcv())
    print(f"  {len(enriched)} rows, {len(enriched.columns)} columns")

    frames = {
        "SYNTH-A": enrich(synthetic_ohlcv(seed=7)),
        "SYNTH-B": enrich(synthetic_ohlcv(seed=21, drift=0.0002, vol=0.022)),
        "SYNTH-C": enrich(synthetic_ohlcv(seed=99, drift=0.0006, vol=0.011)),
    }

    check_price_chart(enriched, out)
    check_candlestick(enriched, out)
    check_volume(enriched, out)
    check_rsi(enriched, out)
    check_macd(enriched, out)
    check_comparison(frames, out)
    check_heatmap(enriched, out)
    check_correlation(frames, out)

    if args.live:
        print("\nLive data")
        live = live_frames()
        if live:
            for symbol, frame in live.items():
                enriched_live = enrich(frame)
                slug = symbol.replace(".", "_").replace("-", "_").lower()
                write(
                    price_chart(
                        enriched_live,
                        ticker=symbol,
                        sma_windows=config.SMA_WINDOWS,
                        ema_spans=config.EMA_SPANS,
                        show_bollinger=True,
                    ),
                    out,
                    f"live_{slug}_price",
                )
                write(candlestick_chart(enriched_live, ticker=symbol), out, f"live_{slug}_candles")
                write(rsi_chart(enriched_live, ticker=symbol), out, f"live_{slug}_rsi")
                write(macd_chart(enriched_live, ticker=symbol), out, f"live_{slug}_macd")
                write(returns_heatmap(enriched_live["Close"], ticker=symbol), out, f"live_{slug}_heatmap")
            write(comparison_chart(live), out, "live_comparison")
            write(correlation_chart(live), out, "live_correlation")
            print(f"  wrote live figures for {', '.join(live)}")

    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} check(s) failed:")
        for label in _FAILURES:
            print(f"  - {label}")
        return 1

    print(f"All checks passed. Open the HTML files in {out} to review them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
