import yfinance as yf
import pandas as pd
from datetime import datetime

# ---------------------------------------------------------
# TICKERS: Stocks + Major Indexes
# ---------------------------------------------------------
tickers = [
    # Your stocks
    "AAPL", "MSFT", "TSLA", "NVDA", "AMZN",

    # Major U.S. Indexes
    "^DJI",   # Dow Jones Industrial Average
    "^GSPC",  # S&P 500
    "^IXIC",  # Nasdaq Composite
    "^RUT",   # Russell 2000 (Small Cap)
    "^VIX"    # Volatility Index
]

# ---------------------------------------------------------
# RSI Calculation
# ---------------------------------------------------------
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ---------------------------------------------------------
# Fetch Data + Build Digest
# ---------------------------------------------------------
rows = []

for ticker in tickers:
    data = yf.download(ticker, period="3mo", interval="1d", progress=False)

    if data.empty:
        continue

    close = data["Close"]
    rsi = compute_rsi(close).iloc[-1]

    latest_close = close.iloc[-1]
    prev_close = close.iloc[-2]
    change = latest_close - prev_close
    pct_change = (change / prev_close) * 100

    rows.append({
        "Ticker": ticker,
        "Price": round(latest_close, 2),
        "Change": round(change, 2),
        "PctChange": round(pct_change, 2),
        "RSI": round(rsi, 2)
    })

df = pd.DataFrame(rows)

# ---------------------------------------------------------
# Color Coding for RSI
# ---------------------------------------------------------
def rsi_color(rsi):
    if rsi < 30:
        return "green"      # Oversold
    elif rsi > 70:
        return "red"        # Overbought
    else:
        return "black"      # Neutral

# ---------------------------------------------------------
# Build HTML Dashboard (f-string FIXES KeyError)
# ---------------------------------------------------------
timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

html = f"""
<html>
<head>
<title>Daily Stock Digest</title>
<style>
body {{ font-family: Arial; padding: 20px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
th {{ background-color: #f2f2f2; }}
</style>
</head>
<body>
<h2>Daily Stock Digest</h2>
<p>Updated {timestamp} UTC</p>
<table>
<tr>
<th>Ticker</th>
<th>Price</th>
<th>Change</th>
<th>% Change</th>
<th>RSI</th>
</tr>
"""

for _, row in df.iterrows():
    html += f"""
    <tr>
        <td>{row['Ticker']}</td>
        <td>{row['Price']}</td>
        <td>{row['Change']}</td>
        <td>{row['PctChange']}%</td>
        <td style="color:{rsi_color(row['RSI'])};">{row['RSI']}</td>
    </tr>
    """

html += """
</table>
</body>
</html>
"""

# ---------------------------------------------------------
# Save HTML
# ---------------------------------------------------------
with open("index.html", "w") as f:
    f.write(html)
