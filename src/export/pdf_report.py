"""The one-page PDF summary: KPIs, two charts and a mechanical commentary.

The charts are the same functions the walkthroughs call, exported to PNG
through kaleido, and the KPI table is the :class:`~src.kpis.KpiSummary` built
for the same frame. Nothing here computes an indicator.

kaleido drives a locally installed Chrome (or Chromium). Where that is missing
the report is still produced, with a line in place of each chart saying why.
"""

from __future__ import annotations

import datetime as _dt
import io
import logging

import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from src import config
from src.charts import price_chart, rsi_chart
from src.export.commentary import commentary
from src.formatting import format_date, title_case_name
from src.kpis import KpiSummary

__all__ = ["build_report"]

_LOG = logging.getLogger(__name__)

_MARGIN: float = 12.0
_KPI_COLUMNS: int = 4

#: Chart size in CSS pixels. The width sets how large the 13px chart text
#: prints once the image is scaled to the page; the scale sets sharpness.
_CHART_WIDTH_PX: int = 900
_PRICE_HEIGHT_PX: int = 400
_RSI_HEIGHT_PX: int = 270
_CHART_SCALE: int = 2

_INK = (15, 23, 42)
_MUTED = (100, 116, 139)
_RULE = (226, 232, 240)


def _safe(text: str) -> str:
    """Make ``text`` printable with the PDF's built-in Windows-1252 fonts.

    Embedding a Unicode font would tie the report to a file on this machine.
    The built-in fonts cover the em dash and the currency symbols the project
    uses; the rupee sign is spelled out and anything else becomes ``?``.
    """
    text = text.replace("₹", "Rs ").replace("−", "-")
    return text.encode("cp1252", errors="replace").decode("cp1252")


def _paragraph(
    pdf: FPDF,
    text: str,
    *,
    size: float,
    style: str = "",
    colour: tuple[int, int, int] = _INK,
    line_height: float = 4.6,
) -> None:
    pdf.set_font("Helvetica", style, size)
    pdf.set_text_color(*colour)
    pdf.multi_cell(
        0, line_height, _safe(text), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )


def _header(pdf: FPDF, ticker: str, info: dict, generated: _dt.date, last: object) -> None:
    name = title_case_name(info.get("name"))
    heading = f"{name} ({ticker})" if name else ticker
    _paragraph(pdf, heading, size=17, style="B", line_height=8)

    details = [part for part in (info.get("sector"), info.get("exchange")) if part]
    details.append(f"Report generated {format_date(generated)}")
    details.append(f"Data to {format_date(last)}")
    _paragraph(pdf, "  |  ".join(details), size=9, colour=_MUTED)
    pdf.ln(2)


def _kpi_table(pdf: FPDF, kpis: KpiSummary) -> None:
    """The cards as a ruled grid, four across."""
    width = pdf.epw / _KPI_COLUMNS
    pdf.set_draw_color(*_RULE)
    top = pdf.get_y()

    for index, card in enumerate(kpis.cards):
        row, column = divmod(index, _KPI_COLUMNS)
        x = pdf.l_margin + column * width
        y = top + row * 13
        pdf.rect(x, y, width, 13)

        pdf.set_xy(x + 1, y + 1.5)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(width - 2, 4, _safe(card.label))

        value = card.value
        if card.delta:
            value = f"{value}  ({card.delta})"
        pdf.set_xy(x + 1, y + 6.5)
        pdf.set_text_color(*_INK)
        # A rupee price with its change is long; shrink to fit, never clip.
        size = 11.0
        pdf.set_font("Helvetica", "B", size)
        while pdf.get_string_width(_safe(value)) > width - 4 and size > 6:
            size -= 0.5
            pdf.set_font("Helvetica", "B", size)
        pdf.cell(width - 2, 5, _safe(value))

    rows = -(-len(kpis.cards) // _KPI_COLUMNS)  # ceil
    pdf.set_xy(pdf.l_margin, top + rows * 13 + 1)
    _paragraph(pdf, kpis.footnote, size=7.5, colour=_MUTED, line_height=3.6)
    pdf.ln(2)


def _chart(pdf: FPDF, figure: go.Figure, height_px: int, label: str) -> None:
    """Place ``figure`` at full page width, or say why it is not there."""
    try:
        png = figure.to_image(
            format="png",
            width=_CHART_WIDTH_PX,
            height=height_px,
            scale=_CHART_SCALE,
        )
    except Exception:  # kaleido raises many types; none should lose the report
        _LOG.exception("Static export of the %s chart failed", label)
        _paragraph(
            pdf,
            f"The {label} chart could not be rendered. Chart export needs "
            "kaleido and a local Chrome or Chromium install.",
            size=9,
            style="I",
            colour=_MUTED,
        )
        pdf.ln(2)
        return

    pdf.image(
        io.BytesIO(png),
        x=pdf.l_margin,
        w=pdf.epw,
        h=pdf.epw * height_px / _CHART_WIDTH_PX,
    )
    pdf.ln(2)


def build_report(
    ticker: str,
    info: dict,
    df: pd.DataFrame,
    kpis: KpiSummary,
    *,
    rsi_variant: str | None = None,
    generated: _dt.date | None = None,
) -> bytes:
    """Build the summary report and return it as PDF bytes.

    Parameters
    ----------
    ticker:
        The symbol, printed in the heading.
    info:
        The result of :func:`src.data.fetcher.fetch_company_info`; every field
        may be missing.
    df:
        A non-empty frame from :func:`src.indicators.enrich`.
    kpis:
        The result of :func:`src.kpis.kpi_summary` for the same frame.
    rsi_variant:
        The formula ``df`` was enriched with, named under the commentary so a
        reader comparing against another site knows which RSI this is.
    generated:
        The date printed on the report; today if omitted.

    Raises
    ------
    ValueError
        If ``df`` has no rows.
    """
    if df is None or df.empty:
        raise ValueError("Cannot build a report from an empty data frame.")

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.core_fonts_encoding = "windows-1252"
    pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)
    pdf.set_auto_page_break(True, margin=_MARGIN)
    pdf.set_title(_safe(f"{ticker} summary report"))
    pdf.set_creator(config.APP_TITLE)
    pdf.add_page()

    _header(pdf, ticker, info, generated or _dt.date.today(), df.index.max())
    _kpi_table(pdf, kpis)

    _chart(
        pdf,
        price_chart(
            df,
            ticker=ticker,
            sma_windows=(50, 200),
            show_bollinger=True,
            height=_PRICE_HEIGHT_PX,
        ),
        _PRICE_HEIGHT_PX,
        "price",
    )
    _chart(
        pdf,
        rsi_chart(df, ticker=ticker, height=_RSI_HEIGHT_PX),
        _RSI_HEIGHT_PX,
        "RSI",
    )

    _paragraph(pdf, "Indicator summary", size=11, style="B", line_height=6)
    _paragraph(pdf, commentary(df), size=9.5)
    if rsi_variant:
        _paragraph(pdf, f"RSI formula: {rsi_variant}.", size=8, colour=_MUTED)
    pdf.ln(2)
    _paragraph(
        pdf,
        config.DISCLAIMER,
        size=8.5,
        style="B",
        line_height=4,
    )

    return bytes(pdf.output())
