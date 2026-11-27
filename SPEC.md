# Stock Market Dashboard — Project Spec

A real-time stock market analytics dashboard that fetches live market data, computes technical indicators, and presents interactive visualizations. Python fetches and calculates; users pick stocks, compare performance and explore trends in a Power BI report.

---

## Workflow

```
Configured ticker list + 5 years of history
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
   │  Export CSV          │
   │  prices, tickers,    │
   │  summary tables      │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  Visualize (Power BI)│
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
| Dashboard          | Power BI Desktop (PBIP project)     |
| Static charts      | Plotly (PDF report and notebook)    |
| Export             | fpdf2 + kaleido (PDF), CSV files    |

**Zero API keys required.** yfinance pulls from Yahoo Finance for free.

---

## Project Structure

```
stock-market-dashboard/
├── powerbi/
│   ├── StockDashboard.pbip             # Power BI project (open this)
│   ├── StockDashboard.SemanticModel/   # Tables, relationships, DAX measures
│   ├── StockDashboard.Report/          # Report pages and visuals
│   └── data/                           # CSV files written by the export script
├── src/
│   ├── config.py                       # Settings, defaults, ticker lists
│   ├── data/
│   │   ├── fetcher.py                  # yfinance data fetching
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
│       └── powerbi_data.py            # Write the CSV tables Power BI imports
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
- Date range selector in the report: 1W, 1M, 3M, 6M, 1Y, 5Y, custom
- The export script fetches 5 years for every configured ticker; Refresh in Power BI loads it
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

### 3. Interactive Charts (Power BI)

| Chart | Description |
|-------|-------------|
| **Candlestick** | Daily open, high, low and close with a volume chart (a true candlestick needs a Power BI custom visual) |
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
- **CSV files** — cleaned data with all indicators as columns, written by `python -m src.export.powerbi_data`
- **PDF report** — 1-page summary: KPIs + price chart + RSI + mechanical indicator summary, written by the same script

---

## Power BI Report Layout

Every page carries a ticker slicer and a date-range slicer.

| Page | Contents |
|------|----------|
| **Price & Overlays** | KPI cards, close price line with SMA(20/50/200), EMA(12/26) and Bollinger Bands, switched by an overlay slicer |
| **Candlestick & Volume** | Daily open, high, low, close; volume bars with the 20-day average |
| **RSI & MACD** | RSI with lines at 70 and 30; MACD with signal line and histogram |
| **Compare Stocks** | Selected tickers normalised to base 100 at the first common date |
| **Returns Analysis** | Monthly returns matrix, correlation matrix of daily returns, daily returns histogram |

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
3. **Power BI Report** (`powerbi/StockDashboard.pbip`) — Full interactive dashboard
4. **Project Report** (`Project_Report.pdf`) — Business understanding, architecture, flowchart, screenshots, final outcome

---

## Dependencies

```
yfinance
pandas
numpy
plotly
fpdf2
kaleido
```

Power BI Desktop (Windows, free) is also required.

No API keys. Install and run:
```bash
pip install -r requirements.txt
python -m src.export.powerbi_data
```
Then open `powerbi/StockDashboard.pbip` and click **Refresh**.

---

## What Makes This a Strong DA Project

1. **Real data** — not a static CSV, actual live market data refreshed on every run
2. **Data transformation** — raw OHLCV → 8+ derived columns (indicators), all computed with pandas
3. **Multiple chart types** — candlestick, line, bar, heatmap, correlation matrix, histogram
4. **Interactive** — Power BI visuals with hover and cross-filtering; slicers for ticker and date range
5. **Multi-stock comparison** — not just one stock, normalized comparison across tickers
6. **Export** — CSV for further analysis, PDF for reporting
7. **No API key barrier** — anyone can clone and run immediately
