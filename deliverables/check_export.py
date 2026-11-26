"""Phase 6 verification: the KPI summary, the commentary and the PDF report.

Runs on synthetic data, so it needs no network. Building the report with its
charts does need kaleido and a local Chrome::

    python deliverables/check_export.py

Add ``--out <file.pdf>`` to keep the report it builds and look at it.

Run it after any change to ``src/export/`` or ``src/kpis.py``.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import plotly.graph_objects as go

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.export.commentary import (
    commentary,
    macd_sentence,
    rsi_sentence,
    trend_sentence,
    volatility_sentence,
)
from src.export.pdf_report import build_report
from src.indicators import enrich, indicator_columns
from src.kpis import kpi_summary

_FAILURES: list[str] = []
_PASSES = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASSES
    if condition:
        _PASSES += 1
        print(f"  ok   {label}")
    else:
        _FAILURES.append(f"{label} -- {detail}")
        print(f"  FAIL {label} -- {detail}")


def frame(rows: int) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-01", periods=rows, name="Date")
    rng = np.random.default_rng(7)
    close = 100 * np.cumprod(1 + rng.normal(0.0005, 0.015, rows))
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": rng.integers(1_000, 9_000, rows),
        },
        index=index,
    )


def row(**values: float) -> pd.DataFrame:
    """Thirty identical rows, so a sentence can be tested on chosen values."""
    index = pd.bdate_range("2025-01-01", periods=30, name="Date")
    return pd.DataFrame(values, index=index)


def pages(pdf: bytes) -> int:
    return len(re.findall(rb"/Type /Page\b", pdf))


def images(pdf: bytes) -> int:
    """Chart images; the soft mask of a transparent image is not counted twice."""
    total = len(re.findall(rb"/Subtype /Image", pdf))
    return total - len(re.findall(rb"/SMask \d+ 0 R", pdf))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    print("\nCommentary rules")
    check("RSI above 70 is overbought", "overbought" in rsi_sentence(row(RSI_14=75.0)))
    check("RSI below 30 is oversold", "oversold" in rsi_sentence(row(RSI_14=25.0)))
    check("RSI of exactly 70 is neutral", "neutral" in rsi_sentence(row(RSI_14=70.0)))
    text = trend_sentence(row(Close=110.0, SMA_50=100.0, SMA_200=125.0))
    check("10% above SMA 50", "10.00% above its SMA 50" in text, text)
    check("12% below SMA 200", "12.00% below its SMA 200" in text, text)
    text = macd_sentence(row(MACD=1.0, MACD_SIGNAL=2.0))
    check("positive MACD under its signal", "positive" in text and "below" in text, text)
    text = macd_sentence(row(MACD=-1.0, MACD_SIGNAL=-2.0))
    check("negative MACD over its signal", "negative" in text and "above" in text, text)
    calm = row(ROLL_VOL_21=0.2)
    calm.iloc[-1, 0] = 0.1
    check("volatility under its median", "lower than" in volatility_sentence(calm))
    wild = row(ROLL_VOL_21=0.2)
    wild.iloc[-1, 0] = 0.3
    check("volatility over its median", "higher than" in volatility_sentence(wild))
    check(
        "volatility near its median",
        "in line with" in volatility_sentence(row(ROLL_VOL_21=0.2)),
    )

    short = enrich(frame(5))
    text = commentary(short)
    for needle in ("RSI(14) is unavailable", "SMA 50 is unavailable",
                   "SMA 200 is unavailable", "MACD is not summarised",
                   "Volatility is not compared"):
        check(f"5 rows: says '{needle}'", needle in text, text)
    check("5 rows: no 'nan' leaks into the text", "nan " not in text.lower(), text)

    long = enrich(frame(300))
    text = commentary(long).lower()
    check(
        "no buy, sell or hold wording",
        not re.search(r"\b(buy|sell|hold|recommend\w*)\b", text),
        text,
    )

    print("\nKPI summary")
    summary = kpi_summary(long, {})
    check("eight cards", len(summary.cards) == 8, str(len(summary.cards)))
    by_label = {card.label: card for card in summary.cards}
    check("missing P/E is an em dash", by_label["P/E"].value == "—")
    check("52-week fallback is labelled", "from this range" in summary.footnote)
    summary_info = kpi_summary(long, {"week52_high": 500.0, "week52_low": 1.0})
    check("52-week range from Yahoo when given", "from Yahoo" in summary_info.footnote)
    check(
        "CSV frame carries at least 8 indicator columns",
        len(set(indicator_columns()) & set(long.columns)) >= 8,
    )

    print("\nPDF report")
    info = {
        "name": "RELIANCE INDUSTRIES LTD ₹ 株",
        "currency": "INR",
        "market_cap": 1.9e13,
    }
    pdf = build_report("TEST.NS", info, long, kpi_summary(long, info))
    check("is a PDF", pdf.startswith(b"%PDF-"))
    check("one page", pages(pdf) == 1, f"{pages(pdf)} pages")
    check("two chart images", images(pdf) == 2, f"{images(pdf)} images")
    if args.out:
        args.out.write_bytes(pdf)

    pdf = build_report("T", {}, short, kpi_summary(short, {}))
    check("5-row range still makes one page", pages(pdf) == 1, f"{pages(pdf)} pages")

    logging.disable(logging.CRITICAL)  # the failure below is deliberate
    with mock.patch.object(go.Figure, "to_image", side_effect=RuntimeError("x")):
        pdf = build_report("T", {}, long, kpi_summary(long, {}))
    logging.disable(logging.NOTSET)
    check(
        "chart export failure still yields a report without images",
        pdf.startswith(b"%PDF-") and images(pdf) == 0 and pages(pdf) == 1,
    )

    try:
        build_report("T", {}, long.iloc[0:0], summary)
        check("empty frame is refused", False, "no error raised")
    except ValueError:
        check("empty frame is refused", True)

    print(f"\n{_PASSES} passed, {len(_FAILURES)} failed")
    for failure in _FAILURES:
        print(f"  {failure}")
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
