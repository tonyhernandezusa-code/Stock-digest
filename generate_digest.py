import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import requests
from datetime import datetime

FRED_API_KEY = "d6150924a7a201d4e891d082f7123818"

WATCHLIST = ["AAPL", "GOOGL", "VTI", "QCOM", "TSM", "META", "TSLA", "MSFT", "INTC", "NVDA", "AMD", "ORCL", "DRIV", "ARTY", "ROBO", "SHOP", "SNPS", "VHT", "CRDO", "RMBS", "SDY", "VYM", "IVE", "AVGO", "JNJ", "AMZN", "BMY", "MRVL", "SCHD", "SPY", "WM", "RSG", "IDU", "MKC", "MRK", "ADM", "GIS", "BRK-B", "LLY", "VOO", "QQQ", "TQQQ", "SQQQ", "SDS", "CSCO", "WMT", "DE", "PEP", "KO", "V", "MA", "CMI", "CAT", "UNP", "CSX", "NSC", "PLTR", "DELL", "MU", "SNDK", "LMT", "AMGN", "ABBV", "RTX", "IONQ", "KEEL", "JCI", "HONA", "HON"]

INDEXES = [
    ("Dow Jones", "^DJI"),
    ("S&P 500", "^GSPC"),
    ("Nasdaq", "^IXIC"),
    ("Russell 2000", "^RUT"),
    ("VIX (Volatility)", "^VIX"),
]

COMMODITIES = [
    ("Oil (WTI)", "CL=F"),
    ("Gold", "GC=F"),
    ("Silver", "SI=F"),
]

# FRED series IDs for interest rates
FRED_RATES = [
    ("Fed Funds Rate", "DFF"),
    ("2-Yr Treasury", "DGS2"),
    ("10-Yr Treasury", "DGS10"),
    ("30-Yr Mortgage", "MORTGAGE30US"),
]

# Curated bank rates - UPDATE THESE MANUALLY (rates as of July 2026, verify before relying on them)
BANK_RATES = [
    ("CIT Bank (Savings)", "TBD"),
    ("Marcus by Goldman (Savings)", "TBD"),
    ("Ally Bank (Savings)", "TBD"),
    ("Discover (Savings)", "TBD"),
    ("SoFi (Savings)", "TBD"),
    ("Synchrony (Savings)", "TBD"),
    ("Capital One 360 (Savings)", "TBD"),
    ("American Express (Savings)", "TBD"),
    ("Barclays (Savings)", "TBD"),
    ("Bread Savings (Savings)", "TBD"),
]

RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def fetch_stock(ticker):
    data = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True)
    if data.empty:
        return None
    price = round(data['Close'].iloc[-1].item(), 2)
    prev = round(data['Close'].iloc[-2].item(), 2)
    pct = round((price - prev) / prev * 100, 2)
    rsi = round(compute_rsi(data['Close']).iloc[-1].item(), 2)
    return {"ticker": ticker, "price": price, "pct": pct, "rsi": rsi}

def fetch_simple_price(symbol):
    data = yf.download(symbol, period="5d", interval="1d", progress=False, auto_adjust=True)
    if data.empty:
        return None
    price = round(data['Close'].iloc[-1].item(), 2)
    prev = round(data['Close'].iloc[-2].item(), 2)
    pct = round((price - prev) / prev * 100, 2)
    return {"price": price, "pct": pct}

def fetch_fred_rate(series_id):
    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        }
        resp = requests.get(url, params=params, timeout=15)
        obs = resp.json()["observations"][0]
        return {"value": float(obs["value"]), "date": obs["date"]}
    except Exception:
        return None

rows = []
for t in WATCHLIST:
    r = fetch_stock(t)
    if r:
        rows.append(r)

index_rows = []
for name, symbol in INDEXES:
    r = fetch_simple_price(symbol)
    if r:
        index_rows.append({"name": name, **r})

commodity_rows = []
for name, symbol in COMMODITIES:
    r = fetch_simple_price(symbol)
    if r:
        commodity_rows.append({"name": name, **r})

rate_rows = []
for name, series_id in FRED_RATES:
    r = fetch_fred_rate(series_id)
    if r:
        rate_rows.append({"name": name, **r})

oversold_count = sum(1 for r in rows if r["rsi"] <= RSI_OVERSOLD)
overbought_count = sum(1 for r in rows if r["rsi"] >= RSI_OVERBOUGHT)
top_mover = max(rows, key=lambda r: abs(r["pct"])) if rows else None

def pct_color(pct):
    if pct > 0:
        return "#1a8a3d"
    if pct < 0:
        return "#c0392b"
    return "#666"

def rsi_style(rsi):
    if rsi <= RSI_OVERSOLD:
        return "background:#fbe0dd;color:#c0392b;font-weight:600;"
    if rsi >= RSI_OVERBOUGHT:
        return "background:#fdf1d0;color:#a5720b;font-weight:600;"
    return ""

def stock_table_rows(items):
    out = ""
    for r in items:
        out += f"""
    <tr>
      <td style="font-weight:600;">{r['ticker']}</td>
      <td style="text-align:right;">${r['price']:.2f}</td>
      <td style="text-align:right;color:{pct_color(r['pct'])};">{r['pct']:+.2f}%</td>
      <td style="text-align:right;"><span style="padding:2px 8px;border-radius:6px;{rsi_style(r['rsi'])}">{r['rsi']:.2f}</span></td>
    </tr>"""
    return out

def simple_cards(items):
    out = ""
    for i in items:
        out += f"""
    <div class="card">
      <p class="label">{i['name']}</p>
      <p class="value">${i['price']:,.2f}</p>
      <p style="margin:2px 0 0;font-size:13px;color:{pct_color(i['pct'])};">{i['pct']:+.2f}%</p>
    </div>"""
    return out

def rate_cards(items):
    out = ""
    for i in items:
        out += f"""
    <div class="card">
      <p class="label">{i['name']}</p>
      <p class="value">{i['value']:.2f}%</p>
      <p style="margin:2px 0 0;font-size:11px;color:#999;">as of {i['date']}</p>
    </div>"""
    return out

def bank_rate_rows(items):
    out = ""
    for name, rate in items:
        out += f"""
    <tr>
      <td>{name}</td>
      <td style="text-align:right;font-weight:600;">{rate}</td>
    </tr>"""
    return out

table_rows_html = stock_table_rows(rows)
index_cards_html = simple_cards(index_rows)
commodity_cards_html = simple_cards(commodity_rows)
rate_cards_html = rate_cards(rate_rows)
bank_rates_html = bank_rate_rows(BANK_RATES)
top_mover_html = f"{top_mover['ticker']} ({top_mover['pct']:+.2f}%)" if top_mover else "-"

html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily Stock Digest</title>
<style>
body {{ font-family: -apple-system, sans-serif; background:#f7f7f5; color:#111; margin:0; padding:24px; }}
h1 {{ font-size:20px; margin:0 0 4px; }}
h2 {{ font-size:15px; margin:24px 0 10px; color:#333; }}
.timestamp {{ color:#666; font-size:13px; margin:0 0 20px; }}
.summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:8px; }}
.row {{ display:flex; gap:12px; margin-bottom:8px; flex-wrap:wrap; }}
.card {{ background:#fff; border-radius:10px; padding:14px; border:1px solid #e5e3dc; flex:1; min-width:130px; }}
.label {{ font-size:12px; color:#666; margin:0 0 4px; }}
.value {{ font-size:20px; font-weight:600; margin:0; }}
table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:10px; overflow:hidden; }}
th {{ text-align:left; padding:8px 10px; background:#f0efe9; font-size:12px; color:#666; font-weight:600; }}
td {{ padding:8px 10px; border-top:1px solid #eee; font-size:13px; }}
.note {{ font-size:11px; color:#999; margin:6px 0 0; }}
</style>
</head>
<body>
<h1>Daily Stock Digest</h1>
<p class="timestamp">Updated {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</p>

<div class="summary">
  <div class="card"><p class="label">Watchlist</p><p class="value">{len(rows)}</p></div>
  <div class="card"><p class="label">Oversold (RSI≤30)</p><p class="value" style="color:#c0392b;">{oversold_count}</p></div>
  <div class="card"><p class="label">Overbought (RSI≥70)</p><p class="value" style="color:#a5720b;">{overbought_count}</p></div>
  <div class="card"><p class="label">Top mover</p><p class="value">{top_mover_html}</p></div>
</div>

<h2>Interest Rates</h2>
<div class="row">{rate_cards_html}</div>

<h2>Market Indexes</h2>
<div class="row">{index_cards_html}</div>

<h2>Commodities</h2>
<div class="row">{commodity_cards_html}</div>

<h2>Top Savings Rates (updated manually)</h2>
<table>
<tr><th>Bank</th><th style="text-align:right;">APY</th></tr>
{bank_rates_html}
</table>
<p class="note">Bank rates are entered manually and may be out of date. Verify with each bank before making decisions.</p>

<h2>Watchlist</h2>
<table>
<tr><th>Ticker</th><th style="text-align:right;">Price</th><th style="text-align:right;">Change</th><th style="text-align:right;">RSI</th></tr>
{table_rows_html}
</table>

</body>
</html>"""

with open("index.html", "w") as f:
    f.write(html)

print("index.html generated successfully")
