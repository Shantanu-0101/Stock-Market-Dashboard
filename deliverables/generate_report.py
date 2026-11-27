"""Write ``deliverables/Project_Report.pdf``.

The report reads the tables the export script wrote (``powerbi/data/``) and the
Power BI screenshots in ``deliverables/screenshots/``. It needs no network.
Run it from the project folder after the export::

    python -m src.export.powerbi_data
    python deliverables/generate_report.py

Sections: title page, contents, business understanding, project
understanding, architecture diagram, flowchart and final outcome.

Retake the screenshots whenever the report pages change: open the project in
Power BI Desktop, click Refresh, and save each page as the file named in
``PAGES`` below, cropped to the report page.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace
from PIL import Image

# Make ``src`` importable however the script is started.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import config
from src.export.powerbi_data import summary_window
from src.formatting import format_percent
from src.indicators import annualized_volatility, indicator_columns, period_return

DATA_DIR = ROOT / "powerbi" / "data"
SHOTS = ROOT / "deliverables" / "screenshots"
OUTPUT = ROOT / "deliverables" / "Project_Report.pdf"

TITLE = "Stock Market Dashboard"
AUTHOR = "Dr. Satyajit Pattnaik"

#: Screenshot file -> (report page name, what it shows).
PAGES = {
    "1_price.png": (
        "Price & Overlays",
        "KPI cards for the selected ticker, the close price with the overlays "
        "ticked in the Overlays slicer, and the written indicator summary.",
    ),
    "2_candlestick.png": (
        "Candlestick & Volume",
        "Daily open, high, low and close, drawn as lines because a true "
        "candlestick needs a custom visual; volume bars with the 20-day average.",
    ),
    "3_rsi_macd.png": (
        "RSI & MACD",
        "RSI with lines at 70 and 30, switchable between the spec formula and "
        "Wilder's; MACD line, signal line and histogram.",
    ),
    "4_compare.png": (
        "Compare Stocks",
        "The tickers ticked in the Compare slicer, each set to 100 on the first "
        "date they all traded.",
    ),
    "5_returns.png": (
        "Returns Analysis",
        "Monthly returns, the distribution of daily returns, and the correlation "
        "of daily returns between all tickers.",
    ),
}

# Colours (RGB).
INK = (15, 23, 42)
MUTED = (100, 116, 139)
RULE = (203, 213, 225)
FILL = (241, 245, 249)
ACCENT = (37, 99, 235)
BAND = (248, 250, 252)


def safe(text: str) -> str:
    """Make text printable with the PDF's built-in Windows-1252 fonts."""
    text = (
        text.replace("₹", "Rs ")
        .replace("−", "-")
        .replace("→", "->")
        .replace("±", "+/-")
    )
    return text.encode("cp1252", errors="replace").decode("cp1252")


# --------------------------------------------------------------------------
# PDF building blocks
# --------------------------------------------------------------------------


class Report(FPDF):
    """A4 report with a running header, page numbers and a few text helpers."""

    def header(self) -> None:
        if self.page_no() == 1:  # the title page has no header
            return
        self.set_font("Helvetica", size=8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"{TITLE} - Project Report")
        self.ln(9)

    def footer(self) -> None:
        if self.page_no() == 1:
            return
        self.set_y(-12)
        self.set_font("Helvetica", size=8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"Page {self.page_no()}", align="C")

    def heading(self, text: str, level: int = 0) -> None:
        """A section (level 0) or sub-section (level 1) title, listed in the contents."""
        if self.get_y() > self.h - 60:
            self.add_page()
        self.start_section(safe(text), level=level)
        self.ln(3 if level == 0 else 1)
        self.set_font("Helvetica", "B", 15 if level == 0 else 11.5)
        self.set_text_color(*INK)
        self.cell(0, 8 if level == 0 else 7, safe(text),
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if level == 0:
            self.set_draw_color(*ACCENT)
            self.set_line_width(0.6)
            self.line(self.l_margin, self.get_y(), self.l_margin + 18, self.get_y())
            self.ln(3)

    def para(self, text: str, size: float = 10, color=INK) -> None:
        self.set_font("Helvetica", size=size)
        self.set_text_color(*color)
        self.multi_cell(0, size * 0.5, safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def bullets(self, items: list[str]) -> None:
        self.set_font("Helvetica", size=10)
        self.set_text_color(*INK)
        for item in items:
            self.set_x(self.l_margin + 3)
            self.cell(4, 5, chr(149))  # bullet in Windows-1252
            self.multi_cell(0, 5, safe(item), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def grid(self, header: list[str], rows: list[list[str]], widths: list[float]) -> None:
        """A table with a shaded heading row and horizontal rules."""
        self.set_font("Helvetica", size=9.5)
        self.set_text_color(*INK)
        self.set_line_width(0.2)
        self.set_draw_color(*RULE)
        self.set_fill_color(255, 255, 255)  # a diagram may have left another fill
        with self.table(
            col_widths=widths,
            text_align="LEFT",
            line_height=5.5,
            first_row_as_headings=True,
            headings_style=FontFace(emphasis="BOLD", color=INK, fill_color=FILL),
            borders_layout="HORIZONTAL_LINES",
        ) as table:
            for values in [header, *rows]:
                row = table.row()
                for value in values:
                    row.cell(safe(value))
        self.ln(3)

    def box(self, x: float, y: float, w: float, h: float,
            title: str, detail: str = "", tag: str = "", dashed: bool = False) -> None:
        """A rounded diagram box: bold title, optional file tag and one detail line."""
        self.set_line_width(0.3)
        self.set_draw_color(*(MUTED if dashed else ACCENT))
        self.set_fill_color(*FILL)
        if dashed:
            self.set_dash_pattern(dash=1.2, gap=1)
        self.rect(x, y, w, h, style="DF", round_corners=True, corner_radius=2)
        self.set_dash_pattern()
        self.set_xy(x + 3, y + 2)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*INK)
        self.cell(w - 6, 5, safe(title))
        if tag:
            self.set_xy(x + 3, y + 2)
            self.set_font("Courier", size=7)
            self.set_text_color(*MUTED)
            self.cell(w - 6, 5, tag, align="R")
        if detail:
            self.set_xy(x + 3, y + 7.5)
            self.set_font("Helvetica", size=8)
            self.set_text_color(*INK)
            self.cell(w - 6, 4.5, safe(detail))

    def arrow(self, x1: float, y1: float, x2: float, y2: float) -> None:
        """A straight line from (x1, y1) with an arrowhead at (x2, y2)."""
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        ux, uy = (x2 - x1) / length, (y2 - y1) / length  # unit direction
        head, half = 2.2, 1.4
        bx, by = x2 - ux * head, y2 - uy * head  # base of the arrowhead
        self.set_draw_color(*MUTED)
        self.set_fill_color(*MUTED)
        self.set_line_width(0.3)
        self.line(x1, y1, bx, by)
        self.polygon(
            [(bx - uy * half, by + ux * half), (bx + uy * half, by - ux * half), (x2, y2)],
            style="F",
        )


def render_contents(pdf: Report, outline) -> None:
    """Draw the contents page from the sections recorded by ``heading``."""
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*INK)
    pdf.cell(0, 10, "Contents", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
    for section in outline:
        top = section.level == 0
        pdf.set_font("Helvetica", "B" if top else "", 11 if top else 10)
        pdf.set_text_color(*(INK if top else MUTED))
        indent = 0 if top else 8
        if top:
            pdf.ln(2)
        pdf.set_x(pdf.l_margin + indent)
        pdf.cell(pdf.epw - indent - 12, 7, section.name, link=pdf.add_link(page=section.page_number))
        pdf.cell(12, 7, str(section.page_number), align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)


# --------------------------------------------------------------------------
# Data for the outcome section
# --------------------------------------------------------------------------


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """The two tables Power BI imports, read from the export folder."""
    prices_path, tickers_path = DATA_DIR / "prices.csv", DATA_DIR / "tickers.csv"
    if not prices_path.is_file() or not tickers_path.is_file():
        raise SystemExit(
            "powerbi/data/ is empty. Run `python -m src.export.powerbi_data` first."
        )
    prices = pd.read_csv(prices_path, parse_dates=["Date"])
    tickers = pd.read_csv(tickers_path)
    return prices, tickers


def ticker_rows(prices: pd.DataFrame, tickers: pd.DataFrame) -> list[list[str]]:
    """One line per ticker: history length, last close, 1-year return and volatility."""
    rows = []
    for meta in tickers.itertuples(index=False):
        frame = prices.loc[prices["Ticker"] == meta.Ticker].set_index("Date")
        close = summary_window(frame)["Close"]  # the last year
        rows.append(
            [
                meta.Ticker,
                str(meta.Name),
                f"{len(frame):,}",
                f"{meta.CurrencySymbol}{close.iloc[-1]:,.2f}",
                format_percent(period_return(close)),
                format_percent(
                    annualized_volatility(close, periods=int(meta.PeriodsPerYear)),
                    signed=False,
                ),
            ]
        )
    return rows


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------


def title_page(pdf: Report, tickers: pd.DataFrame) -> None:
    pdf.add_page()
    pdf.ln(55)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*INK)
    pdf.cell(0, 13, TITLE, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", size=15)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 9, "Project Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(1)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 30, pdf.get_y())
    pdf.ln(8)
    pdf.para(
        "Technical analysis of stocks and crypto from free market data: Python "
        "fetches and calculates, Power BI presents an interactive dashboard.",
        size=11.5,
    )
    pdf.para(f"Tickers: {', '.join(tickers['Ticker'])}", size=10, color=MUTED)
    pdf.set_y(-60)
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, "Created by", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*INK)
    pdf.cell(0, 8, AUTHOR, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def business_understanding(pdf: Report) -> None:
    # No add_page(): the contents placeholder has already started a new page.
    pdf.heading("1. Business Understanding")
    pdf.heading("The problem", level=1)
    pdf.para(
        "Before acting on a stock, investors and analysts ask the same few "
        "questions: where is the price against its trend, is the move "
        "stretched, how volatile is it, and does it move with the rest of the "
        "portfolio? Answering them usually means several websites, a paid data "
        "feed or a spreadsheet rebuilt by hand. Each tool calculates indicators "
        "its own way, so the numbers do not always agree."
    )
    pdf.heading("What this project solves", level=1)
    pdf.bullets(
        [
            "One dashboard answers all five questions for any ticker: trend, "
            "momentum, volatility, performance and diversification.",
            "Free data with no API key, so anyone can run it.",
            "Every indicator is calculated once, from published formulas, so "
            "the dashboard, the CSV files and the PDF summaries agree.",
            "Several markets side by side: US and Indian equities in their own "
            "currencies, and crypto, which trades every day.",
        ]
    )
    pdf.heading("Who it is for", level=1)
    pdf.grid(
        ["User", "What they get"],
        [
            ["Retail investors", "A quick read of trend, momentum and risk for a "
             "stock they hold or follow"],
            ["Data and finance analysts", "Clean daily data with 20 indicator "
             "columns, ready for further analysis in CSV"],
            ["Portfolio reviewers", "Side-by-side performance and the "
             "correlation of daily returns across holdings"],
            ["Students and educators", "A worked, checked example of technical "
             "indicators built from scratch"],
        ],
        [48, 126],
    )
    pdf.para(
        "Scope: the dashboard describes what the indicators show. It does not "
        "recommend buying or selling. " + config.DISCLAIMER,
        size=9,
        color=MUTED,
    )


def project_understanding(pdf: Report) -> None:
    pdf.add_page()
    pdf.heading("2. Project Understanding")
    pdf.heading("How it works", level=1)
    pdf.bullets(
        [
            "An export script fetches five years of daily prices and company "
            "details for each ticker from Yahoo Finance.",
            "The data is cleaned: dates sorted, duplicates removed, holiday gaps "
            "filled, and every high checked against its low.",
            "Indicators are calculated in Python with pandas and added as "
            "columns: moving averages, RSI, MACD, Bollinger Bands, returns and "
            "volatility.",
            "The script writes two CSV tables for Power BI and a one-page PDF "
            "summary for each ticker.",
            "Power BI imports the CSV files. DAX measures work out only the "
            "figures that depend on the dates picked, such as period return and "
            "correlation. Slicers choose ticker, date range and overlays.",
        ]
    )
    pdf.heading("Tools and APIs", level=1)
    pdf.grid(
        ["Tool", "Used for"],
        [
            ["Yahoo Finance via yfinance", "Daily prices and company details; "
             "free, no API key"],
            ["pandas, numpy", "Cleaning and every indicator calculation"],
            ["Plotly, kaleido", "Charts for the PDF summaries and the notebook"],
            ["fpdf2", "PDF summaries and this report"],
            ["Power BI Desktop (DAX)", "Interactive dashboard: model, measures, "
             "five report pages"],
            ["Jupyter (ipykernel, nbclient)", "The executed walkthrough notebook"],
            ["Python 3.13, git and GitHub", "Language and version control"],
        ],
        [62, 112],
    )
    pdf.heading("Technical indicators", level=1)
    pdf.grid(
        ["Indicator", "Formula", "What it shows"],
        [
            ["SMA (20, 50, 200)", "Rolling mean of close", "Trend direction"],
            ["EMA (12, 26)", "Exponentially weighted mean", "Faster trend signal"],
            ["RSI (14)", "100 - 100 / (1 + avg gain / avg loss)",
             "Overbought (>70) / oversold (<30)"],
            ["MACD", "EMA 12 - EMA 26; signal = EMA 9 of MACD",
             "Momentum and crossovers"],
            ["Bollinger Bands", "SMA 20 +/- 2 standard deviations",
             "Volatility envelope"],
            ["Daily return", "(close - previous close) / previous close",
             "Daily % change"],
            ["Cumulative return", "(1 + daily return).cumprod() - 1",
             "Total return over the period"],
            ["Volatility", "Std of daily returns x sqrt(252)", "Annualised risk"],
        ],
        [36, 72, 66],
    )
    pdf.para(
        f"The export carries {len(indicator_columns()) + 1} indicator columns. "
        "Each formula is checked against hand-worked values in "
        "deliverables/check_indicators.py."
    )
    pdf.heading("Design decisions", level=1)
    pdf.bullets(
        [
            "Correlation uses daily returns, not prices. Two unrelated stocks "
            "that both rose over a year show a price correlation near 0.9.",
            "Comparison starts every ticker at 100 on the first date they all "
            "traded, because the US, Indian and crypto markets keep different "
            "calendars.",
            "Crypto volatility is annualised on 365 days. Using 252 understates "
            "it by about 23%.",
            "RSI is available both as the spec's rolling mean and as Wilder's "
            "standard smoothing, chosen by a slicer.",
        ]
    )


def architecture(pdf: Report) -> None:
    """Component diagram: source, Python package, outputs and Power BI."""
    pdf.add_page()
    pdf.heading("3. Architecture Diagram")
    pdf.para(
        "The Python package is the only place data is fetched or indicators are "
        "calculated. Power BI, the PDF summaries and the notebook all read its "
        "results, so they cannot disagree."
    )

    left, main_w = pdf.l_margin, 100.0  # main pipeline column
    side_x, side_w = left + 112, 62.0  # side column
    h, step = 14.0, 22.0  # box height, row spacing
    top = pdf.get_y() + 8
    row = [top + i * step for i in range(7)]

    def band(first: int, last: int, label: str) -> None:
        """A shaded group behind rows first..last, labelled at its top right."""
        y0, y1 = row[first] - 4, row[last] + h + 4
        pdf.set_fill_color(*BAND)
        pdf.set_draw_color(*RULE)
        pdf.set_line_width(0.2)
        pdf.rect(left - 4, y0, pdf.epw + 8, y1 - y0, style="DF")
        pdf.set_xy(left - 4, y0 + 0.5)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(pdf.epw + 6, 4, label.upper(), align="R")

    band(1, 3, "Python")
    band(4, 5, "Power BI Desktop")

    mid = left + main_w / 2
    side_mid = side_x + side_w / 2

    # Main pipeline, top to bottom.
    pdf.box(left, row[0], main_w, h, "Yahoo Finance", "Daily OHLCV and company details",
            "yfinance")
    pdf.box(left, row[1], main_w, h, "Data layer", "Fetch, then clean and validate",
            "src/data/")
    pdf.box(left, row[2], main_w, h, "Indicators", "enrich(): 19 indicator columns",
            "src/indicators/")
    pdf.box(left, row[3], main_w, h, "Export", "prices.csv, tickers.csv, PDF summaries",
            "src/export/")
    pdf.box(left, row[4], main_w, h, "Semantic model", "8 tables, relationships, DAX",
            "powerbi/")
    pdf.box(left, row[5], main_w, h, "Report", "5 pages, KPI cards, slicers",
            "powerbi/")
    pdf.box(left, row[6], main_w, h, "Analyst", "Explores tickers and date ranges")
    for i in range(6):
        pdf.arrow(mid, row[i] + h, mid, row[i + 1])

    # Side column: settings, charts and what uses the charts.
    pdf.box(side_x, row[1], side_w, h, "Settings", "Tickers, windows, colours",
            "config.py", dashed=True)
    pdf.box(side_x, row[2], side_w, h, "Charts", "8 Plotly chart types",
            "src/charts/")
    pdf.box(side_x, row[3], side_w, h, "Walkthroughs", "Script and notebook",
            "deliverables/")
    pdf.arrow(side_x, row[1] + h / 2, left + main_w, row[1] + h / 2)  # settings -> data
    pdf.arrow(left + main_w, row[2] + h / 2, side_x, row[2] + h / 2)  # indicators -> charts
    pdf.arrow(side_mid, row[2] + h, side_mid, row[3])  # charts -> walkthroughs
    pdf.arrow(side_x, row[2] + h - 2, left + main_w, row[3] + 2)  # charts -> PDF in export

    pdf.set_y(row[6] + h + 8)
    pdf.heading("Components", level=1)
    pdf.grid(
        ["Component", "Files", "Role"],
        [
            ["Settings", "src/config.py", "Tickers, indicator windows, presets, colours"],
            ["Data layer", "src/data/", "The only code that calls Yahoo; one cleaned "
             "frame shape"],
            ["Indicators", "src/indicators/", "Pure pandas formulas and enrich()"],
            ["Charts", "src/charts/", "Eight Plotly chart functions, one theme"],
            ["Export", "src/export/", "CSV tables, PDF summary, written commentary"],
            ["Power BI", "powerbi/", "Semantic model and report (PBIP project)"],
            ["Deliverables", "deliverables/", "Walkthroughs, checks, this report"],
        ],
        [30, 38, 106],
    )


def flowchart(pdf: Report) -> None:
    """The step-by-step process as numbered boxes and arrows."""
    pdf.add_page()
    pdf.heading("4. Flowchart")
    pdf.para(
        "One command runs steps 1 to 5. Opening the project in Power BI Desktop "
        "and clicking Refresh runs step 6."
    )
    steps = [
        ("1. Pick tickers", "Five demo tickers, or any list named on the command line",
         "python -m src.export.powerbi_data"),
        ("2. Fetch", "Five years of daily OHLCV and company details per ticker",
         "src/data/fetcher.py"),
        ("3. Clean", "Sort, de-duplicate, fill gaps, check high >= low",
         "src/data/cleaner.py"),
        ("4. Enrich", "SMA, EMA, RSI, MACD, Bollinger, returns, volatility",
         "src/indicators/"),
        ("5. Export", "prices.csv, tickers.csv and one PDF summary per ticker",
         "src/export/powerbi_data.py"),
        ("6. Refresh", "Power BI imports the CSV files; DAX handles the dates picked",
         "StockDashboard.pbip"),
        ("7. Explore", "Slicers for ticker, range, overlays and RSI formula",
         "five report pages"),
    ]
    width, h, gap = 130.0, 15.0, 7.0
    x = (pdf.w - width) / 2
    y = pdf.get_y() + 4
    for number, (name, detail, tag) in enumerate(steps):
        pdf.box(x, y, width, h, name, detail, tag)
        if number < len(steps) - 1:
            pdf.arrow(x + width / 2, y + h, x + width / 2, y + h + gap)
        y += h + gap
    pdf.set_y(y + 2)
    pdf.para(
        "If a ticker fails to load, the script reports it and carries on with "
        "the others; if none load, the existing files are left unchanged.",
        size=9,
        color=MUTED,
    )


def screenshot(pdf: Report, file: str, title: str, caption: str) -> None:
    """One report page: sub-heading, caption and the framed screenshot."""
    path = SHOTS / file
    width = 155.0
    height = 0.0
    if path.is_file():
        with Image.open(path) as image:
            height = width * image.height / image.width
        if pdf.get_y() + height + 30 > pdf.h - pdf.b_margin:  # keep them together
            pdf.add_page()
    pdf.heading(title, level=1)
    pdf.para(caption)
    if not path.is_file():
        pdf.para(f"[Screenshot {file} not found in deliverables/screenshots/.]")
        return
    x, y = (pdf.w - width) / 2, pdf.get_y()
    pdf.image(str(path), x=x, y=y, w=width)
    pdf.set_draw_color(*RULE)
    pdf.set_line_width(0.2)
    pdf.rect(x, y, width, height)
    pdf.set_y(y + height + 5)


def final_outcome(pdf: Report, prices: pd.DataFrame, tickers: pd.DataFrame) -> None:
    pdf.add_page()
    pdf.heading("5. Final Outcome")
    pdf.para(
        "The Power BI report, shown here for AAPL over one year with the default "
        "slicer settings."
    )
    for file, (title, caption) in PAGES.items():
        screenshot(pdf, file, f"Dashboard: {title}", caption)

    pdf.add_page()
    pdf.heading("Sample outputs", level=1)
    pdf.para(
        f"prices.csv: one row per ticker per trading day, {len(prices):,} rows "
        f"and {len(prices.columns)} columns: date, ticker, open, high, low, "
        "close, volume and these indicators:"
    )
    pdf.para(", ".join(c for c in prices.columns[7:]), size=8.5, color=MUTED)
    pdf.para(
        f"tickers.csv: one row per company ({len(tickers)} rows) with name, "
        "sector, currency, 52-week range, market cap, P/E, average volume and a "
        "written summary. The summary for AAPL:"
    )
    summary = tickers.loc[tickers["Ticker"] == "AAPL", "Summary"]
    if not summary.empty:
        pdf.set_x(pdf.l_margin + 4)
        pdf.set_fill_color(*FILL)
        pdf.set_font("Helvetica", "I", 9.5)
        pdf.set_text_color(*INK)
        pdf.multi_cell(pdf.epw - 8, 5, safe(summary.iloc[0]), fill=True,
                       padding=3, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)
    pdf.para(
        "The export also writes a one-page PDF summary per ticker with the KPI "
        "cards, a price chart, an RSI chart and the same summary."
    )

    pdf.heading("Results", level=1)
    pdf.para("The last year for each ticker, from the same CSV files Power BI imports:")
    pdf.grid(
        ["Ticker", "Name", "Rows (5y)", "Last close", "1y return", "Volatility"],
        ticker_rows(prices, tickers),
        [26, 50, 22, 28, 24, 24],
    )
    pdf.para(
        "Each ticker's year here ends on its own last trading day. In Power BI "
        "the 1Y range counts back from the newest date across all tickers, so "
        "a US stock's figures there can differ slightly from this table.",
        size=8.5,
        color=MUTED,
    )
    pdf.para("Delivered:")
    pdf.bullets(
        [
            "A Power BI report with five pages, KPI cards and slicers for "
            "ticker, date range, overlays and RSI formula.",
            "An export script that writes the CSV tables and a one-page PDF "
            "summary per ticker.",
            "A walkthrough script and an executed notebook that go from fetch "
            "to a combined HTML dashboard.",
            "Check scripts for the indicators, charts and export, with "
            "hand-worked answers.",
        ]
    )
    pdf.para(
        "Checked: the Power BI figures for price, daily change, YTD and period "
        "return, volatility, correlation, RSI and SMA were compared with the "
        "Python results for all five tickers and matched."
    )
    pdf.para("Known limits:")
    pdf.bullets(
        [
            "Data is as fresh as the last export run plus a Refresh in Power BI.",
            "Yahoo Finance is unofficial and can rate-limit or leave company "
            "fields empty; empty fields show as a dash.",
            "The candlestick page shows OHLC as lines; a true candlestick needs "
            "a Power BI custom visual.",
            "The indicators describe past prices. They are not a forecast and "
            "not investment advice.",
        ]
    )


def build(prices: pd.DataFrame, tickers: pd.DataFrame) -> Report:
    pdf = Report(format="A4")
    pdf.set_margins(18, 15, 18)
    pdf.set_auto_page_break(True, margin=18)
    pdf.set_title(f"{TITLE} - Project Report")
    pdf.set_author(AUTHOR)

    title_page(pdf, tickers)
    pdf.add_page()  # the contents page; drawn last, once page numbers are known
    pdf.insert_toc_placeholder(render_contents, pages=1, reset_page_indices=False)
    business_understanding(pdf)
    project_understanding(pdf)
    architecture(pdf)
    flowchart(pdf)
    final_outcome(pdf, prices, tickers)
    return pdf


def main() -> int:
    prices, tickers = load_data()
    missing = [f for f in PAGES if not (SHOTS / f).is_file()]
    for name in missing:
        print(f"Missing screenshot: {name}", file=sys.stderr)
    pdf = build(prices, tickers)
    pdf.output(str(OUTPUT))
    print(f"Wrote {OUTPUT.relative_to(ROOT).as_posix()} ({pdf.page_no()} pages)")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
