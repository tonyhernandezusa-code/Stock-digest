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
    ("Nasdaq-100", "^NDX"),
    ("Russell 2000", "^RUT"),
    ("US Dollar (DXY)", "DX-Y.NYB"),
    ("VIX (Volatility)", "^VIX"),
]

COMMODITIES = [
    ("Oil (WTI)", "CL=F"),
    ("Gold", "GC=F"),
    ("Silver", "SI=F"),
]

FRED_RATES = [
    ("Fed Funds Rate", "DFF"),
    ("2-Yr Treasury", "DGS2"),
    ("10-Yr Treasury", "DGS10"),
    ("30-Yr Mortgage", "MORTGAGE30US"),
    ("Natl Avg Savings (FDIC)", "SNDR"),
    ("Natl Avg Money Market (FDIC)", "MMNDR"),
    ("Natl Avg 12-Mo CD (FDIC)", "NDR12MCD"),
]

# Yield curve spreads from FRED (negative = inverted curve)
YIELD_CURVE = [
    ("10-Yr minus 2-Yr Spread", "T10Y2Y"),
    ("10-Yr minus 3-Mo Spread", "T10Y3M"),
    ("High-Yield Credit Spread", "BAMLH0A0HYM2"),
]

# Manually updated economic indicators (not freely available via API)
# Ask Claude to "update my PMI" after the 1st of each month
MANUAL_ECON = [
    ("ISM Manufacturing PMI", "53.3", "Jun 2026"),
]

# Rates from NerdWallet as of July 14, 2026 - verify before relying on them
BANK_RATES = [
    ("Forbright Bank (Savings)", "Up to 4.15%*"),
    ("CIT Bank Platinum (Savings)", "Up to 4.10%*"),
    ("Climate First Bank (Savings)", "4.01%"),
    ("Vio Bank (Savings)", "4.01%"),
    ("Peak Bank (Savings)", "4.01%"),
    ("Happen Bank (Savings)", "4.00%*"),
    ("E*TRADE Premium (Savings)", "4.00% promo*"),
    ("EverBank (Savings)", "3.90%"),
    ("Marcus by Goldman (Savings)", "3.40%"),
    ("Capital One 360 (Savings)", "3.00%"),
]

# Real estate: national indicators from FRED
RE_NATIONAL = [
    ("Mortgage Delinquency Rate", "DRSFRMACBS", "%"),
    ("Housing Starts (annualized)", "HOUST", "K"),
    ("Building Permits (annualized)", "PERMIT", "K"),
    ("New Home Sales (annualized)", "HSN1F", "K"),
    ("30-Yr Mortgage Rate", "MORTGAGE30US", "%"),
]

# All 50 states: FHFA House Price Index series on FRED follows pattern XXSTHPI
STATES = [
    ("Alabama", "AL"), ("Alaska", "AK"), ("Arizona", "AZ"), ("Arkansas", "AR"),
    ("California", "CA"), ("Colorado", "CO"), ("Connecticut", "CT"), ("Delaware", "DE"),
    ("Florida", "FL"), ("Georgia", "GA"), ("Hawaii", "HI"), ("Idaho", "ID"),
    ("Illinois", "IL"), ("Indiana", "IN"), ("Iowa", "IA"), ("Kansas", "KS"),
    ("Kentucky", "KY"), ("Louisiana", "LA"), ("Maine", "ME"), ("Maryland", "MD"),
    ("Massachusetts", "MA"), ("Michigan", "MI"), ("Minnesota", "MN"), ("Mississippi", "MS"),
    ("Missouri", "MO"), ("Montana", "MT"), ("Nebraska", "NE"), ("Nevada", "NV"),
    ("New Hampshire", "NH"), ("New Jersey", "NJ"), ("New Mexico", "NM"), ("New York", "NY"),
    ("North Carolina", "NC"), ("North Dakota", "ND"), ("Ohio", "OH"), ("Oklahoma", "OK"),
    ("Oregon", "OR"), ("Pennsylvania", "PA"), ("Rhode Island", "RI"), ("South Carolina", "SC"),
    ("South Dakota", "SD"), ("Tennessee", "TN"), ("Texas", "TX"), ("Utah", "UT"),
    ("Vermont", "VT"), ("Virginia", "VA"), ("Washington", "WA"), ("West Virginia", "WV"),
    ("Wisconsin", "WI"), ("Wyoming", "WY"),
]

# Top foreclosure states - ATTOM Q1 2026 U.S. Foreclosure Market Report
# "1 in X" = one foreclosure filing per X housing units (lower X = worse)
# Ask Claude to "update my foreclosure table" to refresh from the latest report
FORECLOSURE_STATES = [
    ("Indiana", "1 in 739"),
    ("South Carolina", "1 in 743"),
    ("Florida", "1 in 750"),
    ("Delaware", "1 in 757"),
    ("Illinois", "1 in 833"),
]

RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

NAV_HTML = """
<div style="margin-bottom:16px;">
  <a href="index.html" style="margin-right:16px;font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">Stocks &amp; Rates</a>
  <a href="realestate.html" style="font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">Real Estate</a>
</div>
"""

PAGE_CSS = """
body { font-family: -apple-system, sans-serif; background:#f7f7f5; color:#111; margin:0; padding:24px; }
h1 { font-size:20px; margin:0 0 4px; }
h2 { font-size:15px; margin:24px 0 10px; color:#333; }
.timestamp { color:#666; font-size:13px; margin:0 0 20px; }
.summary { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:8px; }
.row { display:flex; gap:12px; margin-bottom:8px; flex-wrap:wrap; }
.card { background:#fff; border-radius:10px; padding:14px; border:1px solid #e5e3dc; flex:1; min-width:130px; }
.label { font-size:12px; color:#666; margin:0 0 4px; }
.value { font-size:20px; font-weight:600; margin:0; }
.table-wrap { overflow-x:auto; }
table { width:100%; border-collapse:collapse; background:#fff; border-radius:10px; overflow:hidden; }
th { text-align:left; padding:8px 10px; background:#f0efe9; font-size:12px; color:#666; font-weight:600; white-space:nowrap; }
td { padding:8px 10px; border-top:1px solid #eee; font-size:13px; white-space:nowrap; }
.note { font-size:11px; color:#999; margin:6px 0 0; }
"""

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def fmt_big_number(n):
    if n is None:
        return "-"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "-"
    if n >= 1e12:
        return f"{n/1e12:.2f}T"
    if n >= 1e9:
        return f"{n/1e9:.2f}B"
    if n >= 1e6:
        return f"{n/1e6:.1f}M"
    if n >= 1e3:
        return f"{n/1e3:.0f}K"
    return f"{n:.0f}"

def fetch_stock(ticker):
    data = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
    if data.empty or len(data) < 20:
        return None
    close = data['Close']
    price = round(close.iloc[-1].item(), 2)
    prev = round(close.iloc[-2].item(), 2)
    pct = round((price - prev) / prev * 100, 2)
    rsi = round(compute_rsi(close).iloc[-1].item(), 2)

    high_52w = round(data['High'].max().item(), 2)
    low_52w = round(data['Low'].min().item(), 2)
    volume = data['Volume'].iloc[-1].item()
    avg_volume = data['Volume'].tail(63).mean().item()

    market_cap = None
    pe_ratio = None
    div_yield = None
    try:
        info = yf.Ticker(ticker).info
        market_cap = info.get("marketCap")
        pe_ratio = info.get("trailingPE")
        div_rate = info.get("dividendRate")
        if div_rate and price > 0:
            div_yield = div_rate / price * 100
    except Exception:
        pass

    return {
        "ticker": ticker, "price": price, "pct": pct, "rsi": rsi,
        "market_cap": market_cap, "pe": pe_ratio, "div_yield": div_yield,
        "volume": volume, "avg_volume": avg_volume,
        "high_52w": high_52w, "low_52w": low_52w,
    }

def fetch_simple_price(symbol):
    data = yf.download(symbol, period="5d", interval="1d", progress=False, auto_adjust=True)
    if data.empty:
        return None
    price = round(data['Close'].iloc[-1].item(), 2)
    prev = round(data['Close'].iloc[-2].item(), 2)
    pct = round((price - prev) / prev * 100, 2)
    return {"price": price, "pct": pct}

def fetch_fred(series_id, limit=1):
    """Fetch the most recent observation(s) for a FRED series, newest first."""
    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        resp = requests.get(url, params=params, timeout=15)
        obs = resp.json()["observations"]
        return [{"value": float(o["value"]), "date": o["date"]} for o in obs if o["value"] != "."]
    except Exception:
        return None

def fetch_fred_rate(series_id):
    obs = fetch_fred(series_id, limit=1)
    return obs[0] if obs else None

def fetch_fred_yoy(series_id):
    """Year-over-year % change for a monthly FRED series."""
    obs = fetch_fred(series_id, limit=13)
    if not obs or len(obs) < 13:
        return None
    latest, year_ago = obs[0], obs[12]
    yoy = (latest["value"] - year_ago["value"]) / year_ago["value"] * 100
    return {"display": f"{yoy:+.1f}% YoY", "date": latest["date"]}

def fetch_fred_mom(series_id):
    """Month-over-month % change for a monthly FRED series."""
    obs = fetch_fred(series_id, limit=2)
    if not obs or len(obs) < 2:
        return None
    latest, prev = obs[0], obs[1]
    mom = (latest["value"] - prev["value"]) / prev["value"] * 100
    return {"display": f"{mom:+.1f}% MoM", "date": latest["date"]}

def fetch_payrolls():
    """Monthly change in nonfarm payrolls (PAYEMS is in thousands)."""
    obs = fetch_fred("PAYEMS", limit=2)
    if not obs or len(obs) < 2:
        return None
    change = obs[0]["value"] - obs[1]["value"]
    return {"display": f"{change:+,.0f}K jobs", "date": obs[0]["date"]}

def fetch_state_hpi(abbr):
    """FHFA state house price index (quarterly). Returns latest value + 1yr change."""
    obs = fetch_fred(f"{abbr}STHPI", limit=5)
    if not obs or len(obs) < 5:
        return None
    latest = obs[0]
    year_ago = obs[4]
    yoy = (latest["value"] - year_ago["value"]) / year_ago["value"] * 100
    return {"yoy": round(yoy, 2), "date": latest["date"]}

# ------------------- FETCH EVERYTHING -------------------

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

curve_rows = []
for name, series_id in YIELD_CURVE:
    r = fetch_fred_rate(series_id)
    if r:
        curve_rows.append({"name": name, **r})

econ_rows = []
cpi = fetch_fred_yoy("CPIAUCSL")
if cpi:
    econ_rows.append({"name": "CPI (Inflation)", **cpi})
ppi = fetch_fred_yoy("PPIACO")
if ppi:
    econ_rows.append({"name": "PPI (Producer Prices)", **ppi})
payrolls = fetch_payrolls()
if payrolls:
    econ_rows.append({"name": "Nonfarm Payrolls", **payrolls})
retail = fetch_fred_mom("RSAFS")
if retail:
    econ_rows.append({"name": "Retail Sales", **retail})
for name, value, asof in MANUAL_ECON:
    econ_rows.append({"name": f"{name} (manual)", "display": value, "date": asof})

re_national_rows = []
for name, series_id, unit in RE_NATIONAL:
    r = fetch_fred_rate(series_id)
    if r:
        re_national_rows.append({"name": name, "unit": unit, **r})

state_rows = []
for state_name, abbr in STATES:
    r = fetch_state_hpi(abbr)
    if r:
        state_rows.append({"state": state_name, **r})
state_rows.sort(key=lambda x: -x["yoy"])

oversold_count = sum(1 for r in rows if r["rsi"] <= RSI_OVERSOLD)
overbought_count = sum(1 for r in rows if r["rsi"] >= RSI_OVERBOUGHT)
top_mover = max(rows, key=lambda r: abs(r["pct"])) if rows else None

# ------------------- HTML HELPERS -------------------

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

def vol_style(volume, avg_volume):
    try:
        if avg_volume and volume >= 2 * avg_volume:
            return "background:#ddebf7;color:#1f4e79;font-weight:600;"
    except Exception:
        pass
    return ""

def stock_table_rows(items):
    out = ""
    for r in items:
        pe_txt = f"{r['pe']:.1f}" if r['pe'] else "-"
        dy_txt = f"{r['div_yield']:.2f}%" if r['div_yield'] else "-"
        out += f"""
    <tr>
      <td style="font-weight:600;">{r['ticker']}</td>
      <td style="text-align:right;">${r['price']:.2f}</td>
      <td style="text-align:right;color:{pct_color(r['pct'])};">{r['pct']:+.2f}%</td>
      <td style="text-align:right;"><span style="padding:2px 8px;border-radius:6px;{rsi_style(r['rsi'])}">{r['rsi']:.2f}</span></td>
      <td style="text-align:right;">{fmt_big_number(r['market_cap'])}</td>
      <td style="text-align:right;">{pe_txt}</td>
      <td style="text-align:right;">{dy_txt}</td>
      <td style="text-align:right;"><span style="padding:2px 6px;border-radius:6px;{vol_style(r['volume'], r['avg_volume'])}">{fmt_big_number(r['volume'])}</span></td>
      <td style="text-align:right;">{fmt_big_number(r['avg_volume'])}</td>
      <td style="text-align:right;">${r['high_52w']:.2f}</td>
      <td style="text-align:right;">${r['low_52w']:.2f}</td>
    </tr>"""
    return out

def simple_cards(items, dollar=True):
    out = ""
    prefix = "$" if dollar else ""
    for i in items:
        out += f"""
    <div class="card">
      <p class="label">{i['name']}</p>
      <p class="value">{prefix}{i['price']:,.2f}</p>
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

def curve_cards(items):
    out = ""
    for i in items:
        color = "#c0392b" if i["value"] < 0 else "#1a8a3d"
        out += f"""
    <div class="card">
      <p class="label">{i['name']}</p>
      <p class="value" style="color:{color};">{i['value']:+.2f}%</p>
      <p style="margin:2px 0 0;font-size:11px;color:#999;">as of {i['date']}</p>
    </div>"""
    return out

def econ_cards(items):
    out = ""
    for i in items:
        out += f"""
    <div class="card">
      <p class="label">{i['name']}</p>
      <p class="value">{i['display']}</p>
      <p style="margin:2px 0 0;font-size:11px;color:#999;">as of {i['date']}</p>
    </div>"""
    return out

def re_national_cards(items):
    out = ""
    for i in items:
        if i["unit"] == "%":
            val = f"{i['value']:.2f}%"
        else:
            val = f"{i['value']:,.0f}K"
        out += f"""
    <div class="card">
      <p class="label">{i['name']}</p>
      <p class="value">{val}</p>
      <p style="margin:2px 0 0;font-size:11px;color:#999;">as of {i['date']}</p>
    </div>"""
    return out

def state_table_rows(items):
    out = ""
    for rank, s in enumerate(items, 1):
        out += f"""
    <tr>
      <td>{rank}</td>
      <td style="font-weight:600;">{s['state']}</td>
      <td style="text-align:right;color:{pct_color(s['yoy'])};">{s['yoy']:+.2f}%</td>
      <td style="text-align:right;color:#999;font-size:12px;">{s['date']}</td>
    </tr>"""
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

def foreclosure_rows(items):
    out = ""
    for name, val in items:
        out += f"""
    <tr>
      <td>{name}</td>
      <td style="text-align:right;">{val}</td>
    </tr>"""
    return out

timestamp = datetime.now().strftime('%Y-%m-%d %H:%M UTC')
top_mover_html = f"{top_mover['ticker']} ({top_mover['pct']:+.2f}%)" if top_mover else "-"

# ------------------- PAGE 1: STOCKS -------------------

stocks_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily Stock Digest</title>
<style>{PAGE_CSS}</style>
</head>
<body>
{NAV_HTML}
<h1>Daily Stock Digest</h1>
<p class="timestamp">Updated {timestamp}</p>

<div class="summary">
  <div class="card"><p class="label">Watchlist</p><p class="value">{len(rows)}</p></div>
  <div class="card"><p class="label">Oversold (RSI≤30)</p><p class="value" style="color:#c0392b;">{oversold_count}</p></div>
  <div class="card"><p class="label">Overbought (RSI≥70)</p><p class="value" style="color:#a5720b;">{overbought_count}</p></div>
  <div class="card"><p class="label">Top mover</p><p class="value">{top_mover_html}</p></div>
</div>

<h2>Interest Rates</h2>
<div class="row">{rate_cards(rate_rows)}</div>

<h2>Yield Curve &amp; Credit</h2>
<div class="row">{curve_cards(curve_rows)}</div>
<p class="note">Negative Treasury spread (red) = inverted yield curve, historically a recession warning. High-yield credit spread: under ~3.5% = calm, 5%+ = stress building, 8%+ = crisis territory. Source: FRED.</p>

<h2>Economic Indicators</h2>
<div class="row">{econ_cards(econ_rows)}</div>
<p class="note">CPI and PPI shown as year-over-year change. Retail sales month-over-month. PMI above 50 = manufacturing expansion (entered manually from ISM's monthly release).</p>

<h2>Market Indexes</h2>
<div class="row">{simple_cards(index_rows, dollar=False)}</div>

<h2>Commodities</h2>
<div class="row">{simple_cards(commodity_rows)}</div>

<h2>Top Savings Rates (updated manually)</h2>
<table>
<tr><th>Bank</th><th style="text-align:right;">APY</th></tr>
{bank_rate_rows(BANK_RATES)}
</table>
<p class="note">Bank rates are entered manually and may be out of date. Verify with each bank before making decisions.</p>

<h2>Watchlist</h2>
<div class="table-wrap">
<table>
<tr>
<th>Ticker</th>
<th style="text-align:right;">Price</th>
<th style="text-align:right;">Change</th>
<th style="text-align:right;">RSI</th>
<th style="text-align:right;">Mkt Cap</th>
<th style="text-align:right;">P/E</th>
<th style="text-align:right;">Div Yld</th>
<th style="text-align:right;">Volume</th>
<th style="text-align:right;">Avg Vol</th>
<th style="text-align:right;">52w High</th>
<th style="text-align:right;">52w Low</th>
</tr>
{stock_table_rows(rows)}
</table>
</div>
<p class="note">Volume highlighted in blue when today's volume is at least 2x the 3-month average. P/E and Div Yld are blank for ETFs and non-dividend payers.</p>

</body>
</html>"""

# ------------------- PAGE 2: REAL ESTATE -------------------

realestate_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Real Estate Dashboard</title>
<style>{PAGE_CSS}</style>
</head>
<body>
{NAV_HTML}
<h1>Real Estate Dashboard</h1>
<p class="timestamp">Updated {timestamp}</p>

<h2>National Housing Indicators</h2>
<div class="row">{re_national_cards(re_national_rows)}</div>
<p class="note">Housing starts, permits, and new home sales are seasonally adjusted annual rates in thousands. Source: Federal Reserve (FRED).</p>

<h2>House Price Change by State (1-Year, FHFA Index)</h2>
<div class="table-wrap">
<table>
<tr><th>Rank</th><th>State</th><th style="text-align:right;">1-Yr Change</th><th style="text-align:right;">Data as of</th></tr>
{state_table_rows(state_rows)}
</table>
</div>
<p class="note">Ranked fastest-appreciating to slowest. Based on the FHFA All-Transactions House Price Index (quarterly). Source: FRED.</p>

<h2>Top Foreclosure States (updated manually)</h2>
<table>
<tr><th>State</th><th style="text-align:right;">Foreclosure Rate</th></tr>
{foreclosure_rows(FORECLOSURE_STATES)}
</table>
<p class="note">Foreclosure data is compiled by private firms (e.g. ATTOM) and entered manually from their public monthly reports. May be out of date.</p>

</body>
</html>"""

with open("index.html", "w") as f:
    f.write(stocks_html)

with open("realestate.html", "w") as f:
    f.write(realestate_html)

print("index.html and realestate.html generated successfully")
