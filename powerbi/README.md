# Power BI report

## Run it

1. From the project folder, write the data files:

   ```powershell
   .venv\Scripts\python.exe -m src.export.powerbi_data
   ```

2. Open `StockDashboard.pbip` in Power BI Desktop. If double-clicking does not
   open it, start Power BI Desktop and use **File > Open**.
3. Click **Refresh**.

## On another computer

The model reads the CSV files from a full folder path. Change it under
**Transform data > Edit parameters > DataFolder** to that computer's
`powerbi\data` folder.

## Other tickers

Name them after the command. They replace the default five:

```powershell
.venv\Scripts\python.exe -m src.export.powerbi_data AAPL MSFT INFY.NS
```

Then click **Refresh** and pick them in the slicers. The ticker slicers start on
AAPL, so keep it in the list or choose another ticker after refreshing.

## How the figures are worked out

- Indicators are calculated in Python over five years and imported as columns.
- DAX measures handle what depends on the selected dates: price and daily
  change, period and YTD return, volatility, base-100 comparison, monthly
  returns and correlation.
- The date presets count back from the newest date across all tickers.
- Correlation uses daily returns, matched on common dates for each pair.
- A part month at the start of a range includes that first day's return.
- The written summary on page 1 always describes the last year with the spec
  RSI, whatever the slicers say.

## Limits

- The second page shows open, high, low and close as lines. A candlestick needs
  a custom visual, added through **Insert > More visuals**.
- Bollinger Bands are drawn as two lines without shading.
- A newest-day row fetched before a market opens can repeat the previous close.
