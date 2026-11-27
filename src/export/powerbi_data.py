"""Fetch, calculate and write the files the Power BI report imports.

Run it from the project folder, then click **Refresh** in Power BI Desktop::

    python -m src.export.powerbi_data

It writes ``powerbi/data/prices.csv`` (one row per ticker per day, with every
indicator), ``powerbi/data/tickers.csv`` (one row per company) and a one-page
PDF per ticker in ``reports/``. Add ``--no-pdf`` to skip the PDFs, or name
tickers to replace the configured list::

    python -m src.export.powerbi_data AAPL MSFT INFY.NS

Indicators are calculated here, over the whole history, and nowhere else.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.data.cleaner import DataQualityError
from src.data.fetcher import fetch_company_info, fetch_many, normalise_ticker
from src.export.commentary import commentary
from src.export.pdf_report import build_report
from src.formatting import (
    currency_symbol,
    format_compact,
    format_volume,
    title_case_name,
)
from src.indicators import enrich, periods_per_year_for, rsi_wilder
from src.kpis import kpi_summary

__all__ = ["build_tables", "main", "summary_window"]

_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = _ROOT / "powerbi" / "data"
REPORT_DIR = _ROOT / "reports"


def summary_window(df: pd.DataFrame) -> pd.DataFrame:
    """The last year of an enriched frame: what the PDF and summary describe.

    Sliced *after* enriching, so a 200-day average is already filled on the
    first row shown and agrees with the same date in Power BI.
    """
    start = df.index.max() - pd.Timedelta(days=config.SUMMARY_DAYS)
    return df.loc[df.index >= start]


def _price_rows(symbol: str, df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out[f"RSI_{config.RSI_PERIOD}_WILDER"] = rsi_wilder(out["Close"], config.RSI_PERIOD)
    # Lower edge of the histogram bucket, in percent: -0.3% falls in -0.5.
    width = config.RETURN_BIN_PERCENT
    out["RETURN_BIN"] = np.floor(out["DAILY_RETURN"] * 100.0 / width) * width
    out.insert(0, "Ticker", symbol)
    return out.reset_index()


def _ticker_row(symbol: str, info: dict, df: pd.DataFrame) -> dict:
    window = summary_window(df)
    currency = info.get("currency")

    high = info.get("week52_high")
    low = info.get("week52_low")
    range_source = "Yahoo"
    if high is None or low is None:
        high, low = float(window["High"].max()), float(window["Low"].min())
        range_source = "the last year of prices"

    return {
        "Ticker": symbol,
        "Name": title_case_name(info.get("name")) or symbol,
        "Sector": info.get("sector") or config.MISSING_VALUE_DISPLAY,
        "Exchange": info.get("exchange") or config.MISSING_VALUE_DISPLAY,
        "CurrencySymbol": currency_symbol(currency),
        "PeriodsPerYear": periods_per_year_for(info.get("quote_type")),
        "Week52High": high,
        "Week52Low": low,
        "RangeSource": range_source,
        # Text, because one column holds dollars and rupees and each needs its
        # own symbol.
        "MarketCapText": format_compact(info.get("market_cap"), currency),
        "PERatio": info.get("pe_ratio"),
        "AvgVolumeText": format_volume(info.get("avg_volume")),
        "DataTo": df.index.max().date().isoformat(),
        "Summary": commentary(window),
    }


def build_tables(
    frames: dict[str, pd.DataFrame],
    infos: dict[str, dict],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    """Turn clean price frames into ``(prices, tickers, enriched_by_symbol)``.

    Pure: no network and no files, so it can be checked on synthetic data.
    """
    enriched = {
        symbol: enrich(
            frame,
            periods_per_year=periods_per_year_for(
                infos.get(symbol, {}).get("quote_type")
            ),
        )
        for symbol, frame in frames.items()
    }
    prices = pd.concat(
        [_price_rows(s, df) for s, df in enriched.items()], ignore_index=True
    )
    tickers = pd.DataFrame(
        [_ticker_row(s, infos.get(s, {}), df) for s, df in enriched.items()]
    )
    return prices, tickers, enriched


def _write_csv(table: pd.DataFrame, path: Path) -> None:
    """Write via a temporary file, so Power BI never reads half a table."""
    temporary = path.with_suffix(".tmp")
    table.to_csv(temporary, index=False, date_format="%Y-%m-%d", encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tickers", nargs="*", default=list(config.DEMO_TICKERS))
    parser.add_argument("--no-pdf", action="store_true", help="skip the PDF reports")
    args = parser.parse_args(argv)

    symbols = [normalise_ticker(t) for t in args.tickers]
    end = _dt.date.today() + _dt.timedelta(days=1)  # yfinance excludes ``end``
    start = end - _dt.timedelta(days=config.HISTORY_DAYS)

    print(f"Fetching {', '.join(symbols)} from {start} ...")
    frames, errors = fetch_many(symbols, start, end)
    for symbol, message in errors.items():
        print(f"  skipped {symbol}: {message}", file=sys.stderr)
    if not frames:
        print("Nothing loaded; the existing files are unchanged.", file=sys.stderr)
        return 1

    infos = {symbol: fetch_company_info(symbol) for symbol in frames}
    prices, tickers, enriched = build_tables(frames, infos)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(prices, DATA_DIR / "prices.csv")
    _write_csv(tickers, DATA_DIR / "tickers.csv")
    print(f"Wrote {len(prices):,} price rows for {len(tickers)} tickers to {DATA_DIR}")

    if not args.no_pdf:
        REPORT_DIR.mkdir(exist_ok=True)
        for symbol, df in enriched.items():
            window = summary_window(df)
            pdf = build_report(
                symbol, infos[symbol], window, kpi_summary(window, infos[symbol]),
                rsi_variant="Spec (rolling mean)",
            )
            name = f"{symbol}_{window.index.max():%Y%m%d}_report.pdf"
            (REPORT_DIR / name).write_bytes(pdf)
        print(f"Wrote {len(enriched)} PDF reports to {REPORT_DIR}")

    # A skipped ticker is worth a non-zero exit even though the rest succeeded.
    return 2 if errors else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except DataQualityError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
