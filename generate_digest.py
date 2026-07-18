import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import requests
import html as html_escape_mod
from datetime import datetime, timedelta

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
    ("Copper", "HG=F"),
]

FRED_RATES = [
    ("Fed Funds Rate", "DFF"),
    ("2-Yr Treasury", "DGS2"),
    ("10-Yr Treasury", "DGS10"),
    ("30-Yr Mortgage", "MORTGAGE30US"),
    ("Natl Avg Savings (FDIC)", "SNDR"),
    ("Natl Avg Money Market (FDIC)", "MMNDR"),
    ("Natl Avg 12-Mo CD (FDIC)", "NDR12MCD"),
    ("Natl Avg Credit Card Rate", "TERMCBCCALLNS"),
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

# Hover definitions shown as tooltips on each card
DEFINITIONS = {
    "Watchlist": "Number of stocks being tracked in your watchlist table below.",
    "Oversold (RSI≤30)": "Stocks whose RSI is 30 or below - sold off hard and fast, sometimes due for a bounce.",
    "Overbought (RSI≥70)": "Stocks whose RSI is 70 or above - bought up hard and fast, sometimes due for a pullback.",
    "Top mover": "The stock in your watchlist with the biggest price move today, up or down.",
    "Fed Funds Rate": "The interest rate banks charge each other overnight, set by the Federal Reserve. The base rate that influences all other borrowing costs.",
    "2-Yr Treasury": "Yield on 2-year US government bonds. Reflects where markets expect Fed policy over the next couple of years.",
    "10-Yr Treasury": "Yield on 10-year US government bonds. The benchmark long-term rate that drives mortgages and stock valuations.",
    "30-Yr Mortgage": "Average rate on a 30-year fixed home loan in the US.",
    "Natl Avg Savings (FDIC)": "The national average interest rate paid on regular savings accounts, per the FDIC. Compare to the high-yield banks below.",
    "Natl Avg Money Market (FDIC)": "National average rate on money market deposit accounts, per the FDIC.",
    "Natl Avg 12-Mo CD (FDIC)": "National average rate on 12-month certificates of deposit, per the FDIC.",
    "Natl Avg Credit Card Rate": "Average interest rate US banks charge on credit card accounts, per the Federal Reserve. Updated quarterly.",
    "10-Yr minus 2-Yr Spread": "Long-term yield minus short-term yield. Negative (inverted) has historically preceded recessions.",
    "10-Yr minus 3-Mo Spread": "10-year yield minus 3-month yield. The Fed's preferred recession-signal version of the yield curve.",
    "High-Yield Credit Spread": "Extra yield junk bonds pay over Treasuries. Under ~3.5% = calm markets. 5%+ = credit stress building. 8%+ = crisis territory.",
    "CPI (Inflation)": "Consumer Price Index - how much prices consumers pay rose vs a year ago. The main inflation gauge.",
    "PPI (Producer Prices)": "Producer Price Index - how much prices businesses receive rose vs a year ago. Often leads consumer inflation.",
    "Nonfarm Payrolls": "Jobs added or lost in the US last month, excluding farm work. The headline monthly jobs number.",
    "Retail Sales": "Change in consumer retail spending vs the prior month. A gauge of consumer health.",
    "ISM Manufacturing PMI": "Survey of factory purchasing managers. Above 50 = manufacturing expanding, below 50 = contracting.",
    "Dow Jones": "Price-weighted index of 30 large US blue-chip companies.",
    "S&P 500": "The 500 largest US companies - the main benchmark for the overall US stock market.",
    "Nasdaq": "Index of all stocks on the Nasdaq exchange - heavily weighted toward technology.",
    "Nasdaq-100": "The 100 largest non-financial Nasdaq companies - big tech concentrated.",
    "Russell 2000": "Index of 2000 small-cap US companies. A gauge of smaller domestic businesses.",
    "US Dollar (DXY)": "Strength of the US dollar vs a basket of major currencies. Strong dollar pressures multinationals and commodities.",
    "VIX (Volatility)": "The market's fear gauge - expected S&P 500 volatility. Under 15 = calm, over 25 = fearful, over 35 = panic.",
    "Oil (WTI)": "West Texas Intermediate crude oil price per barrel - the US oil benchmark.",
    "Gold": "Gold price per troy ounce. Classic inflation hedge and safe-haven asset.",
    "Silver": "Silver price per troy ounce. Part precious metal, part industrial metal.",
    "Copper": "Copper price per pound. Nicknamed Dr. Copper - demand tracks construction and manufacturing, so it is watched as an economic health gauge.",
    "Mortgage Delinquency Rate": "Share of single-family mortgages 30+ days behind on payments. Rising delinquencies lead foreclosures.",
    "Housing Starts (annualized)": "New homes that began construction, as an annual pace in thousands. A gauge of builder confidence.",
    "Building Permits (annualized)": "Permits issued for future construction, annualized in thousands. A leading indicator for housing starts.",
    "New Home Sales (annualized)": "Newly built homes sold, as an annual pace in thousands.",
    "30-Yr Mortgage Rate": "Average rate on a 30-year fixed home loan in the US.",
}

def def_for(name):
    """Look up a tooltip definition, ignoring any (manual) suffix."""
    base = name.replace(" (manual)", "")
    return DEFINITIONS.get(base, "")

NAV_HTML = """
<div style="margin-bottom:16px;">
  <a href="index.html" style="margin-right:16px;font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">Stocks &amp; Rates</a>
  <a href="realestate.html" style="margin-right:16px;font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">Real Estate</a>
  <a href="calculators.html" style="font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">Calculators</a>
</div>
"""

PAGE_CSS = """
body { font-family: -apple-system, sans-serif; background:#f7f7f5; color:#111; margin:0; padding:24px; }
h1 { font-size:20px; margin:0 0 4px; }
h2 { font-size:15px; margin:24px 0 10px; color:#333; }
.timestamp { color:#666; font-size:13px; margin:0 0 20px; }
.summary { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:8px; }
.row { display:flex; gap:12px; margin-bottom:8px; flex-wrap:wrap; }
.card { background:#fff; border-radius:10px; padding:14px; border:1px solid #e5e3dc; flex:1; min-width:150px; cursor:help; }
.label { font-size:12px; color:#666; margin:0 0 4px; }
.value { font-size:20px; font-weight:600; margin:0; }
.sixmo { font-size:11px; color:#888; margin:4px 0 0; }
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

def sixmo_line(old, new, unit="", pt_label=False):
    """Build the '6 months ago' comparison line: amount change + (% change)."""
    if old is None or new is None:
        return ""
    try:
        delta = new - old
        color = "#1a8a3d" if delta > 0 else "#c0392b" if delta < 0 else "#888"
        amt_label = " pt" if pt_label else unit
        # Skip the % change when the base is near zero (it becomes meaningless)
        if abs(old) > 0.5:
            pct = delta / old * 100
            pct_txt = f" ({pct:+.1f}%)"
        else:
            pct_txt = ""
        return (f'<p class="sixmo">6 mo ago: {old:,.2f}{unit} &middot; '
                f'<span style="color:{color};">{delta:+,.2f}{amt_label}{pct_txt}</span></p>')
    except Exception:
        return ""

def fetch_news_tooltip(ticker):
    """Fetch up to 3 recent headlines for a ticker, formatted for a hover tooltip.
    Handles both old and new yfinance news formats. Returns '' if unavailable."""
    try:
        news = yf.Ticker(ticker).news
        if not news:
            return ""
        lines = []
        for item in news[:3]:
            title = None
            source = ""
            when = ""
            if isinstance(item, dict) and "content" in item and isinstance(item["content"], dict):
                c = item["content"]
                title = c.get("title")
                prov = c.get("provider") or {}
                source = prov.get("displayName") or ""
                pub = c.get("pubDate") or ""
                when = pub[:10] if isinstance(pub, str) else ""
            elif isinstance(item, dict):
                title = item.get("title")
                source = item.get("publisher") or ""
                ts = item.get("providerPublishTime")
                if ts:
                    try:
                        when = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
                    except Exception:
                        when = ""
            if title:
                suffix = " - ".join(x for x in [source, when] if x)
                lines.append(f"{title}" + (f" ({suffix})" if suffix else ""))
        if not lines:
            return ""
        text = "RECENT NEWS:\n" + "\n\n".join(lines)
        return html_escape_mod.escape(text, quote=True)
    except Exception:
        return ""

def fetch_stock(ticker):
    data = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
    if data.empty or len(data) < 20:
        return None
    close = data['Close']
    price = round(close.iloc[-1].item(), 2)
    prev = round(close.iloc[-2].item(), 2)
    pct = round((price - prev) / prev * 100, 2)
    rsi = round(compute_rsi(close).iloc[-1].item(), 2)

    # ~126 trading days = 6 months
    if len(close) > 126:
        price_6mo = close.iloc[-127].item()
    else:
        price_6mo = close.iloc[0].item()
    chg_6mo = round((price - price_6mo) / price_6mo * 100, 2)

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
        "ticker": ticker, "price": price, "pct": pct, "chg_6mo": chg_6mo, "rsi": rsi,
        "market_cap": market_cap, "pe": pe_ratio, "div_yield": div_yield,
        "volume": volume, "avg_volume": avg_volume,
        "high_52w": high_52w, "low_52w": low_52w,
        "news": fetch_news_tooltip(ticker),
    }

def fetch_simple_price(symbol):
    data = yf.download(symbol, period="6mo", interval="1d", progress=False, auto_adjust=True)
    if data.empty or len(data) < 2:
        return None
    close = data['Close']
    price = round(close.iloc[-1].item(), 2)
    prev = round(close.iloc[-2].item(), 2)
    pct = round((price - prev) / prev * 100, 2)
    old = round(close.iloc[0].item(), 2)
    return {"price": price, "pct": pct, "price_6mo": old}

def fetch_fred(series_id, limit=1, sort_order="desc", observation_start=None):
    """Fetch observations for a FRED series."""
    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": sort_order,
            "limit": limit,
        }
        if observation_start:
            params["observation_start"] = observation_start
        resp = requests.get(url, params=params, timeout=15)
        obs = resp.json()["observations"]
        return [{"value": float(o["value"]), "date": o["date"]} for o in obs if o["value"] != "."]
    except Exception:
        return None

def fetch_fred_rate(series_id):
    """Latest value plus the value from ~6 months ago."""
    obs = fetch_fred(series_id, limit=1)
    if not obs:
        return None
    result = obs[0]
    six_months_ago = (datetime.now() - timedelta(days=183)).strftime("%Y-%m-%d")
    old_obs = fetch_fred(series_id, limit=1, sort_order="asc", observation_start=six_months_ago)
    result = {**result, "value_6mo": old_obs[0]["value"] if old_obs else None}
    return result

def fetch_fred_yoy(series_id):
    """Year-over-year % change now, and what it was 6 months ago."""
    obs = fetch_fred(series_id, limit=19)
    if not obs or len(obs) < 13:
        return None
    yoy_now = (obs[0]["value"] - obs[12]["value"]) / obs[12]["value"] * 100
    yoy_6mo = None
    if len(obs) >= 19:
        yoy_6mo = (obs[6]["value"] - obs[18]["value"]) / obs[18]["value"] * 100
    return {"display": f"{yoy_now:+.1f}% YoY", "num": yoy_now, "num_6mo": yoy_6mo,
            "date": obs[0]["date"]}

def fetch_fred_mom(series_id):
    """Month-over-month % change now, and what it was 6 months ago."""
    obs = fetch_fred(series_id, limit=8)
    if not obs or len(obs) < 2:
        return None
    mom_now = (obs[0]["value"] - obs[1]["value"]) / obs[1]["value"] * 100
    mom_6mo = None
    if len(obs) >= 8:
        mom_6mo = (obs[6]["value"] - obs[7]["value"]) / obs[7]["value"] * 100
    return {"display": f"{mom_now:+.1f}% MoM", "num": mom_now, "num_6mo": mom_6mo,
            "date": obs[0]["date"]}

def fetch_payrolls():
    """Monthly change in nonfarm payrolls now vs 6 months ago (PAYEMS in thousands)."""
    obs = fetch_fred("PAYEMS", limit=8)
    if not obs or len(obs) < 2:
        return None
    chg_now = obs[0]["value"] - obs[1]["value"]
    chg_6mo = None
    if len(obs) >= 8:
        chg_6mo = obs[6]["value"] - obs[7]["value"]
    return {"display": f"{chg_now:+,.0f}K jobs", "num": chg_now, "num_6mo": chg_6mo,
            "date": obs[0]["date"]}

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
    econ_rows.append({"name": f"{name} (manual)", "display": value, "date": asof,
                      "num": None, "num_6mo": None})

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
      <td style="font-weight:600;"><a href="https://finance.yahoo.com/quote/{r['ticker']}" target="_blank" title="{r['news']}" style="color:#1f4e79;text-decoration:none;border-bottom:1px dotted #1f4e79;">{r['ticker']}</a></td>
      <td style="text-align:right;">${r['price']:.2f}</td>
      <td style="text-align:right;color:{pct_color(r['pct'])};">{r['pct']:+.2f}%</td>
      <td style="text-align:right;color:{pct_color(r['chg_6mo'])};">{r['chg_6mo']:+.2f}%</td>
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
        six = sixmo_line(i.get("price_6mo"), i["price"], unit="")
        out += f"""
    <div class="card" title="{def_for(i['name'])}">
      <p class="label">{i['name']}</p>
      <p class="value">{prefix}{i['price']:,.2f}</p>
      <p style="margin:2px 0 0;font-size:13px;color:{pct_color(i['pct'])};">{i['pct']:+.2f}% today</p>
      {six}
    </div>"""
    return out

def rate_cards(items):
    out = ""
    for i in items:
        six = sixmo_line(i.get("value_6mo"), i["value"], unit="%", pt_label=True)
        out += f"""
    <div class="card" title="{def_for(i['name'])}">
      <p class="label">{i['name']}</p>
      <p class="value">{i['value']:.2f}%</p>
      <p style="margin:2px 0 0;font-size:11px;color:#999;">as of {i['date']}</p>
      {six}
    </div>"""
    return out

def curve_cards(items):
    out = ""
    for i in items:
        color = "#c0392b" if i["value"] < 0 else "#1a8a3d"
        six = sixmo_line(i.get("value_6mo"), i["value"], unit="%", pt_label=True)
        out += f"""
    <div class="card" title="{def_for(i['name'])}">
      <p class="label">{i['name']}</p>
      <p class="value" style="color:{color};">{i['value']:+.2f}%</p>
      <p style="margin:2px 0 0;font-size:11px;color:#999;">as of {i['date']}</p>
      {six}
    </div>"""
    return out

def econ_cards(items):
    out = ""
    for i in items:
        six = ""
        if i.get("num") is not None and i.get("num_6mo") is not None:
            six = sixmo_line(i["num_6mo"], i["num"], unit="", pt_label=True)
        out += f"""
    <div class="card" title="{def_for(i['name'])}">
      <p class="label">{i['name']}</p>
      <p class="value">{i['display']}</p>
      <p style="margin:2px 0 0;font-size:11px;color:#999;">as of {i['date']}</p>
      {six}
    </div>"""
    return out

def re_national_cards(items):
    out = ""
    for i in items:
        if i["unit"] == "%":
            val = f"{i['value']:.2f}%"
            six = sixmo_line(i.get("value_6mo"), i["value"], unit="%", pt_label=True)
        else:
            val = f"{i['value']:,.0f}K"
            six = sixmo_line(i.get("value_6mo"), i["value"], unit="K")
        out += f"""
    <div class="card" title="{def_for(i['name'])}">
      <p class="label">{i['name']}</p>
      <p class="value">{val}</p>
      <p style="margin:2px 0 0;font-size:11px;color:#999;">as of {i['date']}</p>
      {six}
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
  <div class="card" title="{def_for('Watchlist')}"><p class="label">Watchlist</p><p class="value">{len(rows)}</p></div>
  <div class="card" title="{def_for('Oversold (RSI≤30)')}"><p class="label">Oversold (RSI≤30)</p><p class="value" style="color:#c0392b;">{oversold_count}</p></div>
  <div class="card" title="{def_for('Overbought (RSI≥70)')}"><p class="label">Overbought (RSI≥70)</p><p class="value" style="color:#a5720b;">{overbought_count}</p></div>
  <div class="card" title="{def_for('Top mover')}"><p class="label">Top mover</p><p class="value">{top_mover_html}</p></div>
</div>

<h2>Interest Rates</h2>
<div class="row">{rate_cards(rate_rows)}</div>

<h2>Yield Curve &amp; Credit</h2>
<div class="row">{curve_cards(curve_rows)}</div>
<p class="note">Negative Treasury spread (red) = inverted yield curve, historically a recession warning. High-yield credit spread: under ~3.5% = calm, 5%+ = stress building, 8%+ = crisis territory. Source: FRED.</p>

<h2>Economic Indicators</h2>
<div class="row">{econ_cards(econ_rows)}</div>
<p class="note">CPI and PPI shown as year-over-year change. Retail sales month-over-month. PMI above 50 = manufacturing expansion (entered manually from ISM's monthly release). "6 mo ago" compares each reading to the same measure six months earlier.</p>

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
<th title="Stock symbol">Ticker</th>
<th style="text-align:right;" title="Latest closing price">Price</th>
<th style="text-align:right;" title="Price change vs the previous trading day">Change</th>
<th style="text-align:right;" title="Price change over the past 6 months">6-Mo Chg</th>
<th style="text-align:right;" title="Relative Strength Index (0-100). Below 30 = oversold (red). Above 70 = overbought (yellow). Around 50 = neutral momentum.">RSI</th>
<th style="text-align:right;" title="Market capitalization - total value of all the company's shares. T=trillion, B=billion, M=million.">Mkt Cap</th>
<th style="text-align:right;" title="Price-to-earnings ratio - price divided by yearly profit per share. Higher = more expensive relative to earnings. Blank for ETFs and unprofitable companies.">P/E</th>
<th style="text-align:right;" title="Dividend yield - yearly dividends as a percent of the stock price. Blank if no dividend.">Div Yld</th>
<th style="text-align:right;" title="Shares traded today. Highlighted blue when at least 2x the 3-month average - a sign something is happening.">Volume</th>
<th style="text-align:right;" title="Average daily shares traded over the past 3 months">Avg Vol</th>
<th style="text-align:right;" title="Highest price in the past 52 weeks">52w High</th>
<th style="text-align:right;" title="Lowest price in the past 52 weeks">52w Low</th>
</tr>
{stock_table_rows(rows)}
</table>
</div>
<p class="note">Hover a ticker for its latest headlines; click it to open the full Yahoo Finance page with current news. Volume highlighted in blue when today's volume is at least 2x the 3-month average. P/E and Div Yld are blank for ETFs and non-dividend payers.</p>

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
<p class="note">Housing starts, permits, and new home sales are seasonally adjusted annual rates in thousands. "6 mo ago" compares to the reading six months earlier. Source: Federal Reserve (FRED).</p>

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

# ------------------- PAGE 3: CALCULATORS -------------------

CALC_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Financial Calculators</title>
<style>__CSS__
.calc { background:#fff; border-radius:10px; padding:18px; border:1px solid #e5e3dc; margin-bottom:20px; max-width:520px; }
.calc h3 { margin:0 0 12px; font-size:16px; }
.calc label { display:block; font-size:12px; color:#666; margin:10px 0 3px; }
.calc input { width:100%; padding:8px; font-size:14px; border:1px solid #ccc; border-radius:6px; box-sizing:border-box; }
.calc button { margin-top:14px; padding:10px 18px; font-size:14px; font-weight:600; color:#fff; background:#1f4e79; border:none; border-radius:6px; cursor:pointer; }
.calc button:hover { background:#163a5c; }
.result { margin-top:14px; padding:12px; background:#f0f6ec; border-radius:6px; font-size:14px; display:none; }
.result strong { font-size:17px; }
</style>
</head>
<body>
__NAV__
<h1>Financial Calculators</h1>
<p class="timestamp">These calculators run in your browser - nothing is saved or sent anywhere.</p>

<div class="calc">
<h3>Home Affordability - How Much Do I Qualify For?</h3>
<label>Your annual gross income ($ - before taxes)</label><input type="number" id="q_inc1" value="75000">
<label>Co-borrower annual gross income ($ - spouse/partner on the loan, 0 if single)</label><input type="number" id="q_inc2" value="0">
<label>Total monthly debt payments ($ - car loans, credit card minimums, student loans, child support. NOT groceries, utilities, or rent you will stop paying)</label><input type="number" id="q_debts" value="500">
<label>Down payment you have available ($)</label><input type="number" id="q_down" value="40000">
<label>Expected mortgage rate (% per year)</label><input type="number" id="q_rate" value="6.5" step="0.01">
<label>Loan term (years)</label><input type="number" id="q_years" value="30">
<label>Estimated property taxes + insurance + HOA ($ per month)</label><input type="number" id="q_tih" value="600">
<button onclick="calcQualify()">Calculate</button>
<div class="result" id="q_result"></div>
</div>

<div class="calc">
<h3>Mortgage Calculator</h3>
<label>Home price ($)</label><input type="number" id="m_price" value="400000">
<label>Down payment ($)</label><input type="number" id="m_down" value="80000">
<label>Interest rate (% per year)</label><input type="number" id="m_rate" value="6.5" step="0.01">
<label>Loan term (years)</label><input type="number" id="m_years" value="30">
<label>Estimated property taxes ($ per year)</label><input type="number" id="m_tax" value="4800">
<label>Estimated home insurance ($ per year)</label><input type="number" id="m_ins" value="2400">
<label>HOA dues ($ per month, 0 if none)</label><input type="number" id="m_hoa" value="0">
<label>Second mortgage / piggyback loan ($ - reduces the first mortgage, 0 if none)</label><input type="number" id="m_sec" value="0">
<label>Second mortgage rate (% per year)</label><input type="number" id="m_sec_rate" value="8.5" step="0.01">
<label>Second mortgage type</label>
<select id="m_sec_type" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="io" selected>Interest-only (principal due at payoff/refinance)</option>
<option value="am">Amortized (paid down monthly)</option>
</select>
<label>Second mortgage term (years, for amortized)</label><input type="number" id="m_sec_years" value="15">
<label>Home inspection ($ - paid upfront, typically $300-600)</label><input type="number" id="m_inspect" value="500">
<label>Buyer's agent commission (% of price - enter 0 if the seller covers it)</label><input type="number" id="m_comm" value="0" step="0.1">
<label>Other closing costs - title, escrow/closing agent, lender fees, recording (typically 2-4% of price)</label><input type="number" id="m_closing" value="3" step="0.1">
<label>Balloon payment (loan due early after N years)</label>
<select id="m_balloon" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="0" selected>No balloon - regular loan</option>
<option value="1">Balloon at year 1</option><option value="2">Balloon at year 2</option>
<option value="3">Balloon at year 3</option><option value="4">Balloon at year 4</option>
<option value="5">Balloon at year 5</option><option value="6">Balloon at year 6</option>
<option value="7">Balloon at year 7</option><option value="8">Balloon at year 8</option>
<option value="9">Balloon at year 9</option><option value="10">Balloon at year 10</option>
<option value="11">Balloon at year 11</option><option value="12">Balloon at year 12</option>
<option value="13">Balloon at year 13</option><option value="14">Balloon at year 14</option>
<option value="15">Balloon at year 15</option><option value="16">Balloon at year 16</option>
<option value="17">Balloon at year 17</option><option value="18">Balloon at year 18</option>
<option value="19">Balloon at year 19</option><option value="20">Balloon at year 20</option>
</select>
<button onclick="calcMortgage()">Calculate</button>
<div class="result" id="m_result"></div>
<div id="m_amort" style="margin-top:14px;"></div>
</div>

<div class="calc">
<h3>Auto Loan Calculator</h3>
<label>Vehicle price ($)</label><input type="number" id="a_price" value="35000">
<label>Down payment ($)</label><input type="number" id="a_down" value="3000">
<label>Trade-in value ($)</label><input type="number" id="a_trade" value="2000">
<label>Interest rate (% per year)</label><input type="number" id="a_rate" value="7.0" step="0.01">
<label>Loan term (months)</label><input type="number" id="a_months" value="60">
<button onclick="calcAuto()">Calculate</button>
<div class="result" id="a_result"></div>
</div>

<div class="calc">
<h3>Savings Calculator</h3>
<label>Starting amount ($)</label><input type="number" id="s_start" value="10000">
<label>Monthly contribution ($)</label><input type="number" id="s_monthly" value="500">
<label>Interest rate / APY (% per year)</label><input type="number" id="s_rate" value="4.0" step="0.01">
<label>Years</label><input type="number" id="s_years" value="10">
<label>Additional months</label><input type="number" id="s_months" value="0">
<button onclick="calcSavings()">Calculate</button>
<div class="result" id="s_result"></div>
</div>

<div class="calc">
<h3>Credit Card Payoff Calculator</h3>
<label>Current balance ($)</label><input type="number" id="c_balance" value="5000">
<label>APR (% per year)</label><input type="number" id="c_apr" value="24.99" step="0.01">
<label>Monthly payment ($)</label><input type="number" id="c_payment" value="200">
<label>New purchases per month ($ - 0 if you stop using the card)</label><input type="number" id="c_spend" value="0">
<label>Cash back on purchases (% - e.g. 2 or 3, applied as a credit to the balance)</label><input type="number" id="c_cashback" value="2" step="0.1">
<button onclick="calcCard()">Calculate</button>
<div class="result" id="c_result"></div>
</div>

<script>
function money(x) {
  return "$" + x.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
}
function show(id, html) {
  var el = document.getElementById(id);
  el.innerHTML = html;
  el.style.display = "block";
}
function calcQualify() {
  var gm = ((+document.getElementById("q_inc1").value || 0) + (+document.getElementById("q_inc2").value || 0)) / 12;
  var debts = (+document.getElementById("q_debts").value || 0);
  var down = (+document.getElementById("q_down").value || 0);
  var rate = (+document.getElementById("q_rate").value || 0) / 100 / 12;
  var n = (+document.getElementById("q_years").value || 30) * 12;
  var tih = (+document.getElementById("q_tih").value || 0);
  if (gm <= 0) { show("q_result", "Enter your income."); return; }

  function scenario(front_pct, back_pct) {
    var housing = Math.min(gm * front_pct, gm * back_pct - debts);
    var pi = housing - tih;
    if (pi <= 0) return null;
    var loan = rate > 0 ? pi * (1 - Math.pow(1 + rate, -n)) / rate : pi * n;
    return { housing: housing, pi: pi, loan: loan, price: loan + down };
  }

  var cons = scenario(0.28, 0.36);
  var aggr = scenario(0.31, 0.43);
  var html = "Gross monthly household income: <strong>" + money(gm) + "</strong><br><br>";
  if (!cons && !aggr) {
    show("q_result", html + "<strong>With these debts and costs, the standard ratios leave no room for a mortgage payment.</strong><br>Paying down monthly debts is the fastest way to raise what you qualify for.");
    return;
  }
  if (cons) {
    html += "<u>Conservative (28/36 rule - most lenders' comfort zone)</u><br>" +
      "Max home price: <strong>" + money(cons.price) + "</strong><br>" +
      "&nbsp;&nbsp;Max loan: " + money(cons.loan) + " + your " + money(down) + " down<br>" +
      "&nbsp;&nbsp;Monthly housing budget: " + money(cons.housing) + " (" + money(cons.pi) + " P&amp;I + " + money(tih) + " tax/ins/HOA)<br><br>";
  }
  if (aggr) {
    html += "<u>Upper limit (31/43 - FHA-style stretch)</u><br>" +
      "Max home price: <strong>" + money(aggr.price) + "</strong><br>" +
      "&nbsp;&nbsp;Max loan: " + money(aggr.loan) + " + your " + money(down) + " down<br>" +
      "&nbsp;&nbsp;Monthly housing budget: " + money(aggr.housing) + "<br><br>";
  }
  html += "<span style='font-size:11px;color:#888;'>This is an estimate, not a preapproval. Lenders also weigh credit score, employment history, and cash reserves - and qualifying for the upper number does not mean it is comfortable to live with. The first number uses the classic 28/36 rule: housing under 28% of gross income, all debts under 36%.</span>";
  show("q_result", html);
}
function calcMortgage() {
  var price = +document.getElementById("m_price").value;
  var down = +document.getElementById("m_down").value;
  var rate = +document.getElementById("m_rate").value / 100 / 12;
  var n = +document.getElementById("m_years").value * 12;
  var tax_m = (+document.getElementById("m_tax").value || 0) / 12;
  var ins_m = (+document.getElementById("m_ins").value || 0) / 12;
  var hoa_m = (+document.getElementById("m_hoa").value || 0);
  var sec_amt = (+document.getElementById("m_sec").value || 0);
  var sec_rate = (+document.getElementById("m_sec_rate").value || 0) / 100 / 12;
  var sec_type = document.getElementById("m_sec_type").value;
  var sec_n = (+document.getElementById("m_sec_years").value || 0) * 12;
  var inspect_amt = (+document.getElementById("m_inspect").value || 0);
  var loan = price - down - sec_amt;
  var sec_pmt = 0;
  if (sec_amt > 0) {
    if (sec_type === "io" || sec_n <= 0) {
      sec_pmt = sec_amt * sec_rate;
    } else {
      sec_pmt = sec_rate > 0 ? sec_amt * sec_rate / (1 - Math.pow(1 + sec_rate, -sec_n)) : sec_amt / sec_n;
    }
  }
  var comm_pct = (+document.getElementById("m_comm").value || 0);
  var closing_pct = (+document.getElementById("m_closing").value || 0);
  var comm_amt = price * comm_pct / 100;
  var closing_amt = price * closing_pct / 100;
  var cash_to_close = down + comm_amt + closing_amt + inspect_amt;
  var balloonY = +document.getElementById("m_balloon").value;
  if (loan <= 0 || n <= 0) { show("m_result", "Check your inputs."); return; }
  if (balloonY > 0 && balloonY * 12 >= n) { balloonY = 0; }
  var pmt = rate > 0 ? loan * rate / (1 - Math.pow(1 + rate, -n)) : loan / n;
  var full = pmt + sec_pmt + tax_m + ins_m + hoa_m;
  var total = pmt * n;
  var hoa_line = hoa_m > 0 ? "&nbsp;&nbsp;HOA dues: " + money(hoa_m) + " /mo<br>" : "";
  var sec_line = "";
  if (sec_amt > 0) {
    var sec_label = (sec_type === "io") ? "interest-only" : "amortized over " + (sec_n/12) + " yrs";
    sec_line = "&nbsp;&nbsp;2nd mortgage (" + sec_label + "): " + money(sec_pmt) + " /mo<br>";
  }
  var balloon_line = "";
  if (balloonY > 0) {
    var bb = loan, bint = 0;
    for (var bm = 0; bm < balloonY * 12; bm++) {
      var bi = bb * rate; bint += bi; bb -= (pmt - bi);
    }
    balloon_line = "<span style='color:#c0392b;font-weight:600;'>Balloon due at end of year " + balloonY + ": " + money(bb) + "</span><br>" +
                   "Interest paid before the balloon: " + money(bint) + "<br>";
    total = pmt * balloonY * 12 + bb;
  }
  show("m_result",
    "Total monthly payment: <strong>" + money(full) + "</strong><br>" +
    "&nbsp;&nbsp;1st mortgage principal &amp; interest: " + money(pmt) + "<br>" +
    sec_line +
    "&nbsp;&nbsp;Property taxes: " + money(tax_m) + " /mo<br>" +
    "&nbsp;&nbsp;Insurance: " + money(ins_m) + " /mo<br>" +
    hoa_line +
    balloon_line +
    "1st mortgage amount: " + money(loan) + (sec_amt > 0 ? "<br>2nd mortgage amount: " + money(sec_amt) : "") + "<br>" +
    (balloonY > 0 ? "" : "Total interest over the loan: " + money(total - loan) + "<br>") +
    "<br><u>Cash needed at closing: <strong>" + money(cash_to_close) + "</strong></u><br>" +
    "&nbsp;&nbsp;Down payment: " + money(down) + "<br>" +
    (comm_amt > 0 ? "&nbsp;&nbsp;Buyer's agent commission (" + comm_pct + "%): " + money(comm_amt) + "<br>" : "") +
    (closing_amt > 0 ? "&nbsp;&nbsp;Other closing costs (" + closing_pct + "%): " + money(closing_amt) + "<br>" : "") +
    (inspect_amt > 0 ? "&nbsp;&nbsp;Home inspection: " + money(inspect_amt) + "<br>" : "") +
    "<span style='font-size:11px;color:#888;'>Taxes, insurance, and HOA are estimates and usually rise over time. PMI (required below 20% down) is extra. With an interest-only second mortgage, the monthly payment never reduces its principal - the full amount remains due at payoff, sale, or refinance. Buyer-agent commission is negotiable and cannot usually be rolled into the loan - though sellers often agree to cover it, so ask. Every dollar paid in commission is a dollar unavailable for your down payment.</span>");

  // Yearly amortization schedule (principal & interest only)
  var bal = loan, t = "";
  t += "<h3 style='font-size:14px;margin:10px 0 8px;'>Amortization Schedule (yearly, 1st mortgage)</h3>";
  t += "<div class='table-wrap'><table><tr>";
  t += "<th>Year</th>";
  t += "<th style='text-align:right;'>Principal Paid</th>";
  t += "<th style='text-align:right;'>Interest Paid</th>";
  t += "<th style='text-align:right;'>Remaining Balance</th></tr>";
  var years_n = balloonY > 0 ? balloonY : Math.ceil(n / 12);
  for (var y = 1; y <= years_n; y++) {
    var prinY = 0, intY = 0;
    for (var m = 0; m < 12 && bal > 0.005; m++) {
      var im = bal * rate;
      var pr = Math.min(pmt - im, bal);
      intY += im;
      prinY += pr;
      bal -= pr;
    }
    t += "<tr><td>" + y + "</td>" +
         "<td style='text-align:right;'>" + money(prinY) + "</td>" +
         "<td style='text-align:right;'>" + money(intY) + "</td>" +
         "<td style='text-align:right;'>" + money(Math.max(bal, 0)) + "</td></tr>";
    if (bal <= 0.005) break;
  }
  if (balloonY > 0 && bal > 0.005) {
    t += "<tr style='background:#fbe0dd;'><td colspan='3' style='font-weight:600;'>Balloon payment due (end of year " + balloonY + ")</td>" +
         "<td style='text-align:right;font-weight:600;color:#c0392b;'>" + money(bal) + "</td></tr>";
  }
  t += "</table></div>";
  t += "<p class='note'>Shows how each year's payments split between principal and interest. Early years are mostly interest; the balance shrinks faster over time." +
       (balloonY > 0 ? " With a balloon, you make regular payments until the balloon year, then the entire remaining balance is due at once - typically refinanced or paid from a sale." : "") + "</p>";
  document.getElementById("m_amort").innerHTML = t;
}
function calcAuto() {
  var price = +document.getElementById("a_price").value;
  var down = (+document.getElementById("a_down").value || 0);
  var trade = (+document.getElementById("a_trade").value || 0);
  var rate = +document.getElementById("a_rate").value / 100 / 12;
  var n = +document.getElementById("a_months").value;
  var loan = price - down - trade;
  if (loan <= 0 || n <= 0) { show("a_result", "Check your inputs."); return; }
  var pmt = rate > 0 ? loan * rate / (1 - Math.pow(1 + rate, -n)) : loan / n;
  var total = pmt * n;
  show("a_result",
    "Monthly payment: <strong>" + money(pmt) + "</strong><br>" +
    "Loan amount: " + money(loan) + "<br>" +
    "&nbsp;&nbsp;Vehicle price: " + money(price) + "<br>" +
    (down > 0 ? "&nbsp;&nbsp;Down payment: -" + money(down) + "<br>" : "") +
    (trade > 0 ? "&nbsp;&nbsp;Trade-in: -" + money(trade) + "<br>" : "") +
    "Total paid: " + money(total) + "<br>" +
    "Total interest: " + money(total - loan) +
    "<br><span style='font-size:11px;color:#888;'>Taxes, title, and dealer fees are extra unless rolled into the loan. Trade-in assumes any old loan on it is already paid off.</span>");
}
function calcSavings() {
  var bal = +document.getElementById("s_start").value;
  var monthly = +document.getElementById("s_monthly").value;
  var rate = +document.getElementById("s_rate").value / 100 / 12;
  var n = (+document.getElementById("s_years").value || 0) * 12 + (+document.getElementById("s_months").value || 0);
  if (n <= 0) { show("s_result", "Check your inputs."); return; }
  var contributed = bal;
  for (var i = 0; i < n; i++) {
    bal = bal * (1 + rate) + monthly;
    contributed += monthly;
  }
  show("s_result",
    "Final balance: <strong>" + money(bal) + "</strong><br>" +
    "Total contributed: " + money(contributed) + "<br>" +
    "Interest earned: " + money(bal - contributed) +
    "<br><span style='font-size:11px;color:#888;'>Assumes monthly compounding and a constant rate.</span>");
}
function calcCard() {
  var bal = +document.getElementById("c_balance").value;
  var rate = +document.getElementById("c_apr").value / 100 / 12;
  var pmt = +document.getElementById("c_payment").value;
  var spend = (+document.getElementById("c_spend").value || 0);
  var cb_pct = (+document.getElementById("c_cashback").value || 0) / 100;
  if (bal <= 0 || pmt <= 0) { show("c_result", "Check your inputs."); return; }
  var months = 0, interest = 0, cashback = 0, b = bal;
  while (b > 0 && months < 1200) {
    var int_m = b * rate;
    interest += int_m;
    var cb_m = spend * cb_pct;
    cashback += cb_m;
    b = b + int_m + spend - pmt - cb_m;
    months++;
    if (months > 12 && b >= bal) {
      show("c_result", "<strong>That combination never pays it off.</strong><br>With " + money(spend) + "/mo of new purchases plus interest, and " + money(pmt) + "/mo in payments, the balance grows instead of shrinking. Raise the payment or cut the spending.");
      return;
    }
  }
  if (months >= 1200 && b > 0) {
    show("c_result", "<strong>That combination never pays it off</strong> (still a balance after 100 years). Raise the payment or cut the spending.");
    return;
  }
  var years = Math.floor(months / 12), rem = months % 12;
  var when = (years > 0 ? years + " yr " : "") + rem + " mo";
  show("c_result",
    "Time to pay off: <strong>" + when + "</strong> (" + months + " payments)<br>" +
    "Total interest paid: " + money(interest) + "<br>" +
    (cashback > 0 ? "Cash back earned (credited to balance): " + money(cashback) + "<br>" : "") +
    (spend > 0 ? "New purchases charged along the way: " + money(spend * months) + "<br>" : "") +
    "<span style='font-size:11px;color:#888;'>" + (spend > 0 ? "Cash back helps, but at " + (rate*1200).toFixed(1) + "% APR the interest on a carried balance far outweighs a " + (cb_pct*100).toFixed(1) + "% reward - rewards only truly pay when the balance is zero. " : "") + "Assumes cash back is applied as a statement credit each month.</span>");
}
</script>

</body>
</html>"""

calculators_html = (CALC_TEMPLATE
                    .replace("__CSS__", PAGE_CSS)
                    .replace("__NAV__", NAV_HTML))

with open("index.html", "w") as f:
    f.write(stocks_html)

with open("realestate.html", "w") as f:
    f.write(realestate_html)

with open("calculators.html", "w") as f:
    f.write(calculators_html)

print("index.html, realestate.html, and calculators.html generated successfully")
