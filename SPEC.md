# Stock Market Dashboard — Project Spec

A real-time stock market analytics dashboard that fetches live market data, computes technical indicators, and presents interactive visualizations. Users pick stocks, compare performance, and explore trends through a Streamlit web app.

---

## Workflow

```
User selects stock ticker(s) + date range
              │
              ▼
   ┌─────────────────────┐
   │  Fetch Data          │
   │  (yfinance API)      │
   │  OHLCV + company     │
   │  info + financials   │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  Transform           │
   │  - Clean nulls       │
   │  - Calculate SMAs    │
   │  - Calculate RSI     │
   │  - Calculate MACD    │
   │  - Daily returns     │
   │  - Bollinger Bands   │
   │  - Volume averages   │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  Visualize           │
   │  - Candlestick chart │
   │  - Price + overlays  │
   │  - Volume bars       │
   │  - RSI subplot       │
   │  - MACD subplot      │
   │  - Comparison chart  │
   │  - Returns heatmap   │
   │  - Correlation matrix│
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  Dashboard           │
   │  KPI cards + charts  │
   │  + tables + export   │
   └─────────────────────┘
```

---

## Tech Stack

| Component          | Tool                                |
|--------------------|-------------------------------------|
| Data fetching      | yfinance (free, no API key needed)  |
| Data processing    | pandas, numpy                       |
| Technical indicators | pandas + ta-lib (or manual calc)  |
| Visualization      | Plotly (interactive charts)         |
| UI                 | Streamlit                           |
| Export             | fpdf2 (PDF report), CSV download    |

**Zero API keys required.** yfinance pulls from Yahoo Finance for free.

---

## Project Structure

```
stock-market-dashboard/
├── app.py                              # Streamlit web application
├── src/
│   ├── config.py                       # App settings, defaults, ticker lists
│   ├── data/
│   │   ├── fetcher.py                  # yfinance data fetching + caching
│   │   └── cleaner.py                  # Null handling, type casting, validation
│   ├── indicators/
│   │   ├── moving_averages.py          # SMA, EMA calculations
│   │   ├── rsi.py                      # Relative Strength Index
│   │   ├── macd.py                     # MACD + signal line
│   │   ├── bollinger.py               # Bollinger Bands
│   │   └── returns.py                  # Daily/cumulative returns, volatility
│   ├── charts/
│   │   ├── candlestick.py             # OHLC candlestick chart
│   │   ├── price_chart.py             # Price line + SMA/EMA/Bollinger overlays
│   │   ├── volume_chart.py            # Volume bar chart with average line
│   │   ├── rsi_chart.py               # RSI with overbought/oversold zones
│   │   ├── macd_chart.py              # MACD + signal + histogram
│   │   ├── comparison.py              # Multi-stock normalized price comparison
│   │   ├── heatmap.py                 # Returns heatmap (monthly/weekly)
│   │   └── correlation.py             # Correlation matrix across stocks
│   └── export/
│       └── pdf_report.py              # Generate PDF summary report
├── deliverables/
│   ├── walkthrough.ipynb               # Jupyter notebook walkthrough
│   ├── walkthrough.py                  # Script version
│   ├── generate_report.py             # Project report generator
│   └── Project_Report.pdf             # Generated report
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Features

### 1. Stock Data Fetcher
- Fetch OHLCV (Open, High, Low, Close, Volume) data via yfinance
- Support any ticker: US stocks (AAPL, TSLA), Indian (RELIANCE.NS, TCS.NS), crypto (BTC-USD)
- Date range selector: 1W, 1M, 3M, 6M, 1Y, 5Y, custom
- Cache fetched data in session state to avoid re-fetching on every interaction
- Fetch company info: name, sector, market cap, P/E ratio, 52-week high/low

### 2. Technical Indicators (computed with pandas)
All indicators are calculated from scratch using pandas/numpy — no black-box libraries.

| Indicator | Formula | What it shows |
|-----------|---------|---------------|
| **SMA (20, 50, 200)** | Rolling mean of close prices | Trend direction |
| **EMA (12, 26)** | Exponentially weighted mean | Faster trend signal |
| **RSI (14)** | 100 - (100 / (1 + avg_gain/avg_loss)) | Overbought (>70) / oversold (<30) |
| **MACD** | EMA(12) - EMA(26), signal = EMA(9) of MACD | Momentum + crossovers |
| **Bollinger Bands** | SMA(20) +/- 2 * std(20) | Volatility envelope |
| **Daily Returns** | (close - prev_close) / prev_close | Daily % change |
| **Cumulative Returns** | (1 + daily_return).cumprod() - 1 | Total return over period |
| **Volatility** | Std of daily returns * sqrt(252) | Annualized risk |

### 3. Interactive Charts (Plotly)

| Chart | Description |
|-------|-------------|
| **Candlestick** | OHLC candles with volume subplot |
| **Price + Overlays** | Close price with SMA/EMA/Bollinger toggles |
| **Volume** | Bar chart with 20-day average line |
| **RSI** | Line chart with 70/30 reference bands |
| **MACD** | MACD line + signal line + histogram bars |
| **Multi-Stock Comparison** | Normalized prices (base 100) for 2-5 stocks |
| **Returns Heatmap** | Monthly returns as a colored grid |
| **Correlation Matrix** | Heatmap showing price correlation between stocks |

### 4. KPI Cards (top of dashboard)
- Current Price + daily change (green/red)
- 52-Week High / Low
- Market Cap
- P/E Ratio
- Average Volume
- YTD Return %

### 5. Export
- **CSV download** — cleaned data with all indicators as columns
- **PDF report** — 1-page summary: KPIs + price chart + RSI + recommendation text

---

## Streamlit UI Layout

```
┌──────────────────────────────────────────────────────────┐
│  Stock Market Dashboard                                   │
├───────────────┬──────────────────────────────────────────┤
│  Sidebar      │  Main Area                               │
│               │                                          │
│  Ticker input │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
│  [AAPL]       │  │Price│ │52W H│ │ P/E │ │ YTD │       │
│               │  │+1.2%│ │$198 │ │28.5 │ │+24% │       │
│  Date range   │  └─────┘ └─────┘ └─────┘ └─────┘       │
│  [1Y ▼]       │                                          │
│               │  Tab 1: Price & Overlays                 │
│  Indicators   │  ┌──────────────────────────────────┐   │
│  ☑ SMA 20     │  │  [Interactive Plotly chart]       │   │
│  ☑ SMA 50     │  │  Price + SMA + Bollinger          │   │
│  ☐ SMA 200    │  └──────────────────────────────────┘   │
│  ☑ Bollinger  │                                          │
│  ☑ EMA        │  Tab 2: Candlestick + Volume             │
│               │  Tab 3: RSI + MACD                       │
│  Compare      │  Tab 4: Compare Stocks                   │
│  [+ Add stock]│  Tab 5: Returns Analysis                 │
│               │                                          │
│  Export       │  ┌──────────────────────────────────┐   │
│  [CSV] [PDF]  │  │  Data table (expandable)         │   │
│               │  └──────────────────────────────────┘   │
└───────────────┴──────────────────────────────────────────┘
```

### Tab breakdown:

**Tab 1 — Price & Overlays:** Close price line chart. Toggle SMA(20/50/200), EMA(12/26), Bollinger Bands on/off from sidebar checkboxes. All overlaid on the same chart.

**Tab 2 — Candlestick + Volume:** Classic OHLC candlestick chart (green/red candles). Volume bars below as a subplot with 20-day average volume line.

**Tab 3 — RSI + MACD:** Two subplots stacked vertically. RSI with horizontal lines at 70 (overbought) and 30 (oversold). MACD with signal line and histogram.

**Tab 4 — Compare Stocks:** Add 2-5 tickers from sidebar. All normalized to base 100 at the start date. One line per stock, different colors.

**Tab 5 — Returns Analysis:** Monthly returns heatmap (rows = years, columns = months, color = return %). Correlation matrix if multiple stocks selected. Daily returns distribution histogram.

---

## Technical Indicator Implementations

### SMA (Simple Moving Average)
```python
def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()
```

### EMA (Exponential Moving Average)
```python
def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()
```

### RSI (Relative Strength Index)
```python
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
```

### MACD
```python
def macd(series: pd.Series):
    ema_12 = ema(series, 12)
    ema_26 = ema(series, 26)
    macd_line = ema_12 - ema_26
    signal_line = ema(macd_line, 9)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram
```

### Bollinger Bands
```python
def bollinger_bands(series: pd.Series, window: int = 20, num_std: int = 2):
    middle = sma(series, window)
    std = series.rolling(window=window).std()
    upper = middle + (num_std * std)
    lower = middle - (num_std * std)
    return upper, middle, lower
```

### Daily & Cumulative Returns
```python
def daily_returns(series: pd.Series) -> pd.Series:
    return series.pct_change()

def cumulative_returns(series: pd.Series) -> pd.Series:
    return (1 + daily_returns(series)).cumprod() - 1
```

---

## Sample Tickers for Demo

| Ticker | Name | Why |
|--------|------|-----|
| AAPL | Apple | Most recognizable, good trend data |
| TSLA | Tesla | High volatility, great for RSI/Bollinger demo |
| RELIANCE.NS | Reliance Industries | Indian market example |
| TCS.NS | TCS | Indian IT bellwether |
| BTC-USD | Bitcoin | Crypto support, extreme volatility |

---

## Deliverables

1. **Jupyter Notebook** (`walkthrough.ipynb`) — Step-by-step: fetch data → compute indicators → build each chart → combine into dashboard
2. **Python Script** (`walkthrough.py`) — Same flow as a runnable script
3. **Streamlit App** (`app.py`) — Full interactive dashboard
4. **Project Report** (`Project_Report.pdf`) — Business understanding, architecture, flowchart, screenshots, final outcome

---

## Dependencies

```
streamlit
yfinance
pandas
numpy
plotly
fpdf2
```

No API keys. Install and run:
```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## What Makes This a Strong DA Project

1. **Real data** — not a static CSV, actual live market data refreshed on every run
2. **Data transformation** — raw OHLCV → 8+ derived columns (indicators), all computed with pandas
3. **Multiple chart types** — candlestick, line, bar, heatmap, correlation matrix, histogram
4. **Interactive** — Plotly charts with hover, zoom, pan; Streamlit widgets for filtering
5. **Multi-stock comparison** — not just one stock, normalized comparison across tickers
6. **Export** — CSV for further analysis, PDF for reporting
7. **No API key barrier** — anyone can clone and run immediately
