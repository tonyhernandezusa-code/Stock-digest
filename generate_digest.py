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
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>__CSS__
.calc { background:#fff; border-radius:10px; padding:18px; border:1px solid #e5e3dc; margin-bottom:20px; max-width:520px; }
.calc h3 { margin:0 0 12px; font-size:16px; }
.calc label { display:block; font-size:12px; color:#666; margin:10px 0 3px; }
.calc input { width:100%; padding:8px; font-size:14px; border:1px solid #ccc; border-radius:6px; box-sizing:border-box; }
.calc button { margin-top:14px; padding:10px 18px; font-size:14px; font-weight:600; color:#fff; background:#1f4e79; border:none; border-radius:6px; cursor:pointer; }
.calc button:hover { background:#163a5c; }
.result { margin-top:14px; padding:12px; background:#f0f6ec; border-radius:6px; font-size:14px; display:none; }
.result strong { font-size:17px; }
.field-row { display:flex; align-items:flex-end; gap:8px; }
.field-row > div { flex:1; }
.suggest-btn { white-space:nowrap; padding:8px 10px; font-size:11px; font-weight:600; color:#1f4e79; background:#eef3f8; border:1px solid #cdddec; border-radius:6px; cursor:pointer; margin-bottom:0; }
.suggest-btn:hover { background:#ddebf7; }
.chart-wrap { max-width:280px; margin:16px auto 0; }
.chart-caption { text-align:center; font-size:11px; color:#888; margin-top:6px; }
.calc-tabs { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:20px; }
.calc-tab-btn { padding:10px 16px; border-radius:8px; border:1px solid #e5e3dc; background:#fff; cursor:pointer; font-size:13px; font-weight:600; color:#555; transition:background 0.2s,color 0.2s; }
.calc-tab-btn:hover { background:#f0efe9; }
.calc-tab-btn.active { background:#1f4e79; color:#fff; border-color:#1f4e79; }
.calc-panel { display:none; }
.calc-panel.active { display:block; }
.unit-row { display:flex; gap:6px; align-items:center; margin-bottom:8px; }
.unit-row input[type="text"] { flex:2; padding:8px; font-size:13px; border:1px solid #ccc; border-radius:6px; box-sizing:border-box; }
.unit-row input[type="number"] { flex:1; padding:8px; font-size:13px; border:1px solid #ccc; border-radius:6px; box-sizing:border-box; min-width:0; }
.unit-row .row-subtotal { flex:0 0 85px; font-size:11px; color:#666; text-align:right; }
.unit-row .row-remove { flex:0 0 auto; background:#fbe0dd; color:#c0392b; border:1px solid #f3c6c2; border-radius:6px; padding:6px 10px; font-size:11px; cursor:pointer; }
.unit-row .row-remove:hover { background:#f7cac5; }
.unit-totals { background:#f0f6ec; border-radius:6px; padding:10px 12px; font-size:13px; margin:8px 0 16px; }
</style>
</head>
<body>
__NAV__
<h1>Financial Calculators</h1>
<p class="timestamp">These calculators run in your browser - nothing is saved or sent anywhere.</p>

<div class="calc-tabs">
  <button type="button" class="calc-tab-btn active" onclick="showCalcTab('panel-afford', this)">Home Affordability</button>
  <button type="button" class="calc-tab-btn" onclick="showCalcTab('panel-mortgage', this)">Mortgage</button>
  <button type="button" class="calc-tab-btn" onclick="showCalcTab('panel-cre', this)">Real Estate Investment</button>
  <button type="button" class="calc-tab-btn" onclick="showCalcTab('panel-auto', this)">Auto Loan</button>
  <button type="button" class="calc-tab-btn" onclick="showCalcTab('panel-savings', this)">Savings</button>
  <button type="button" class="calc-tab-btn" onclick="showCalcTab('panel-card', this)">Credit Card Payoff</button>
  <button type="button" class="calc-tab-btn" onclick="showCalcTab('panel-bizval', this)">Business Valuation</button>
</div>

<div class="calc calc-panel active" id="panel-afford">
<h3>Home Affordability - How Much Do I Qualify For?</h3>
<label>Your annual gross income ($ - before taxes)</label><input type="number" id="q_inc1" value="75000">
<label>Co-borrower annual gross income ($ - spouse/partner on the loan, 0 if single)</label><input type="number" id="q_inc2" value="0">
<label>Total monthly debt payments ($ - car loans, credit card minimums, student loans, child support. NOT groceries, utilities, or rent you will stop paying)</label><input type="number" id="q_debts" value="500">
<label>Down payment you have available ($)</label><input type="number" id="q_down" value="40000">
<label>Expected mortgage rate (% per year)</label><input type="number" id="q_rate" value="6.5" step="0.01">
<label>Loan term (years)</label><input type="number" id="q_years" value="30">
<label>Estimated property taxes + insurance + HOA ($ per month)</label><input type="number" id="q_tih" value="600">
<div class="field-row">
  <div><label>Estimated monthly home maintenance ($ - national average, editable)</label><input type="number" id="q_maint" value="300"></div>
  <button type="button" class="suggest-btn" onclick="document.getElementById('q_maint').value=300;">Use Nat'l Avg ($300)</button>
</div>
<button onclick="calcQualify()">Calculate</button>
<div class="result" id="q_result"></div>
</div>

<div class="calc calc-panel" id="panel-mortgage">
<h3>Mortgage Calculator</h3>
<label>Home price ($)</label><input type="number" id="m_price" value="400000">
<label>Down payment ($)</label><input type="number" id="m_down" value="80000">
<label>Interest rate (% per year)</label><input type="number" id="m_rate" value="6.5" step="0.01">
<label>Loan term (years)</label><input type="number" id="m_years" value="30">
<label>Estimated property taxes ($ per year)</label><input type="number" id="m_tax" value="4800">
<label>Estimated home insurance ($ per year)</label><input type="number" id="m_ins" value="2400">
<label>HOA dues ($ per month, 0 if none)</label><input type="number" id="m_hoa" value="0">
<div class="field-row">
  <div><label>Estimated monthly home maintenance ($ - national average is ~1% of home price per year, editable)</label><input type="number" id="m_maint" value="333"></div>
  <button type="button" class="suggest-btn" onclick="recommendMortgageMaint()">Recalc (1%/yr)</button>
</div>
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
<label>Payment frequency</label>
<select id="m_freq" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="monthly" selected>Monthly (12 payments/year)</option>
<option value="biweekly">Biweekly - half payment every 2 weeks (26 half-payments = 13 full payments/year)</option>
</select>
<label>Extra principal per payment ($ - e.g. 100 extra each month, or 50 extra each biweekly payment; 0 for none)</label><input type="number" id="m_extra" value="0">
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
<div class="chart-wrap"><canvas id="m_chart"></canvas></div>
<p class="chart-caption" id="m_chart_caption"></p>
<div id="m_amort" style="margin-top:14px;"></div>
</div>

<div class="calc calc-panel" id="panel-cre">
<h3>Real Estate Investment Loan Calculator (DSCR)</h3>
<label>Property type (auto-fills typical down payment, rate, amortization, and loan term below - all remain editable)</label>
<select id="cre_type" onchange="applyCREDefaults()" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="res14" selected>1-4 units (residential investment loan)</option>
<option value="comm5">5+ units / commercial property</option>
</select>
<p class="chart-caption" id="cre_type_hint" style="text-align:left;margin:4px 0 12px;">1-4 unit properties qualify for residential-style financing (conventional or DSCR investment loans) - typically 30-year fixed with no balloon, and rates only modestly above a standard home mortgage.</p>
<label>Purchase price ($)</label><input type="number" id="cre_price" value="500000">
<label>Down payment (% - national average by property type, editable)</label><input type="number" id="cre_down_pct" value="25" step="0.5">
<label>Interest rate (% per year - national average by property type, editable)</label><input type="number" id="cre_rate" value="7.25" step="0.01">
<label>Amortization period (years - length used to calculate the payment)</label><input type="number" id="cre_amort" value="30">
<label>Loan term / balloon due (years - 0 for no balloon/fully amortizing, as is standard for 1-4 unit residential loans. Commercial loans on 5+ units commonly have a shorter 5, 7, or 10-yr term with a balloon due, even though the payment is calculated on a longer amortization.)</label><input type="number" id="cre_term" value="0">
<label>Closing costs (% of purchase price - typically 2-3% for residential, 2-5% for commercial)</label><input type="number" id="cre_closing" value="3" step="0.1">
<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Income &amp; Operating Expenses</h4>
<label>Rent roll (unit mix) - add a row for each unit type, enter how many units of that type and the monthly rent per unit</label>
<div id="cre_unit_rows"></div>
<button type="button" class="suggest-btn" onclick="addUnitRow()" style="margin-bottom:12px;">+ Add Unit Type</button>
<div class="unit-totals">
  Total units: <strong id="cre_total_units">0</strong> &nbsp;|&nbsp;
  Total monthly rent: <strong id="cre_total_monthly_rent">$0.00</strong> &nbsp;|&nbsp;
  Total annual rent: <strong id="cre_total_annual_rent">$0.00</strong>
</div>
<input type="hidden" id="cre_rent" value="0">
<input type="hidden" id="cre_total_units_hidden" value="0">
<div class="field-row">
  <div><label>Vacancy &amp; credit loss (% of gross rent - lenders commonly underwrite to ~5%, editable)</label><input type="number" id="cre_vacancy" value="5" step="0.1"></div>
  <button type="button" class="suggest-btn" onclick="document.getElementById('cre_vacancy').value=5;">Use Nat'l Avg (5%)</button>
</div>
<label>Annual property taxes ($)</label><input type="number" id="cre_tax" value="6000">
<label>Annual insurance ($)</label><input type="number" id="cre_ins" value="3000">
<div class="field-row">
  <div><label>Property management fee (% of collected rent - national average is ~8-10%, editable)</label><input type="number" id="cre_mgmt" value="8" step="0.1"></div>
  <button type="button" class="suggest-btn" onclick="document.getElementById('cre_mgmt').value=8;">Use Nat'l Avg (8%)</button>
</div>
<div class="field-row">
  <div><label>Maintenance &amp; capex reserves ($/mo - a common rule of thumb is ~7% of rent, editable)</label><input type="number" id="cre_maint" value="350"></div>
  <button type="button" class="suggest-btn" onclick="recommendCREMaint()">Use Nat'l Avg</button>
</div>
<label>Other monthly expenses ($ - utilities, HOA, etc. if landlord-paid, 0 if tenant pays all)</label><input type="number" id="cre_other" value="0">
<button onclick="calcCRE()">Calculate</button>
<div class="result" id="cre_result"></div>
<div class="chart-wrap"><canvas id="cre_chart"></canvas></div>
<p class="chart-caption" id="cre_chart_caption"></p>
</div>

<div class="calc calc-panel" id="panel-auto">
<h3>Auto Loan Calculator</h3>
<label>Vehicle type (auto-fills maintenance, fuel, depreciation, and EV-specific fields below with national averages - all remain editable)</label>
<select id="a_type" onchange="applyVehicleDefaults()" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="gas" selected>Gasoline</option>
<option value="diesel">Diesel</option>
<option value="hybrid">Hybrid</option>
<option value="electric">Electric (EV)</option>
</select>
<label>Vehicle price ($)</label><input type="number" id="a_price" value="35000">
<p class="chart-caption" id="a_price_premium_hint" style="text-align:left;margin:4px 0 0;"></p>
<label>Down payment ($)</label><input type="number" id="a_down" value="3000">
<label>Trade-in value ($)</label><input type="number" id="a_trade" value="2000">
<label>Sales tax (% - most states tax the price AFTER trade-in credit)</label><input type="number" id="a_tax" value="6.5" step="0.1">
<label>Dealer/doc/title fees ($)</label><input type="number" id="a_fees" value="800">
<label>Roll tax &amp; fees into the loan?</label>
<select id="a_roll" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="yes" selected>Yes - finance them (most common)</option>
<option value="no">No - I will pay them in cash</option>
</select>
<label>Interest rate (% per year)</label><input type="number" id="a_rate" value="7.0" step="0.01">
<label>Loan term (months)</label><input type="number" id="a_months" value="60">
<div class="field-row">
  <div><label id="a_maint_label">Estimated monthly maintenance ($ - national average by vehicle type, editable)</label><input type="number" id="a_maint" value="100"></div>
  <button type="button" class="suggest-btn" onclick="applyVehicleDefaults()">Use Nat'l Avg</button>
</div>
<div class="field-row">
  <div><label id="a_deprec_label">Estimated annual depreciation (% of price - national average by vehicle type, editable)</label><input type="number" id="a_deprec_rate" value="15" step="0.1"></div>
  <button type="button" class="suggest-btn" onclick="applyVehicleDefaults()">Use Nat'l Avg</button>
</div>
<div class="field-row">
  <div><label id="a_fuel_label">Monthly fuel/electricity cost ($ - national average by vehicle type, editable)</label><input type="number" id="a_fuel" value="150"></div>
  <button type="button" class="suggest-btn" onclick="applyVehicleDefaults()">Use Nat'l Avg</button>
</div>
<label>Monthly tolls ($ - 0 if none)</label><input type="number" id="a_tolls" value="0">
<label>Monthly parking ($ - 0 if none)</label><input type="number" id="a_parking" value="0">
<div class="field-row">
  <div><label>EV annual road-use / registration surcharge ($ - many states now charge EVs extra since they pay no gas tax; typically $50-$290/yr and rising. 0 if gas/diesel/hybrid or your state has none. Verify the current amount with your state DMV - Florida and others have changed this recently.)</label><input type="number" id="a_ev_fee" value="0"></div>
  <button type="button" class="suggest-btn" onclick="applyVehicleDefaults()">Use Nat'l Avg</button>
</div>
<div class="field-row">
  <div><label>Home charger installation ($ - one-time, if you'll charge at home. Typical Level 2 install runs $800-$3,000, more with a panel upgrade. The federal 30% (up to $1,000) tax credit for this expired 6/30/2026 - check your state or utility for any remaining rebates. 0 if not applicable.)</label><input type="number" id="a_charger" value="0"></div>
  <button type="button" class="suggest-btn" onclick="applyVehicleDefaults()">Use Nat'l Avg</button>
</div>
<div class="field-row">
  <div><label>Battery replacement reserve ($/mo - EV battery replacement runs $5,000-$22,000 out of warranty (mid-size EVs typically $12,000-$15,000), but a federal 8-yr/100,000-mile warranty covers most of a typical ownership period and only ~2.5% of EV owners ever pay this out of pocket. This is an optional contingency fund, not a guaranteed cost - 0 if you'd rather not set anything aside.)</label><input type="number" id="a_battery" value="0"></div>
  <button type="button" class="suggest-btn" onclick="applyVehicleDefaults()">Use Nat'l Avg</button>
</div>
<button onclick="calcAuto()">Calculate</button>
<div class="result" id="a_result"></div>
<div class="chart-wrap"><canvas id="a_chart"></canvas></div>
<p class="chart-caption" id="a_chart_caption"></p>
</div>

<div class="calc calc-panel" id="panel-savings">
<h3>Savings Calculator</h3>
<label>Starting amount ($)</label><input type="number" id="s_start" value="10000">
<label>Monthly contribution ($)</label><input type="number" id="s_monthly" value="500">
<label>Interest rate / APY (% per year)</label><input type="number" id="s_rate" value="4.0" step="0.01">
<label>Years</label><input type="number" id="s_years" value="10">
<label>Additional months</label><input type="number" id="s_months" value="0">
<button onclick="calcSavings()">Calculate</button>
<div class="result" id="s_result"></div>
</div>

<div class="calc calc-panel" id="panel-card">
<h3>Credit Card Payoff Calculator</h3>
<label>Current balance ($)</label><input type="number" id="c_balance" value="5000">
<label>APR (% per year)</label><input type="number" id="c_apr" value="24.99" step="0.01">
<label>Monthly payment ($)</label><input type="number" id="c_payment" value="200">
<label>New purchases per month ($ - 0 if you stop using the card)</label><input type="number" id="c_spend" value="0">
<label>Cash back on purchases (% - e.g. 2 or 3, applied as a credit to the balance)</label><input type="number" id="c_cashback" value="2" step="0.1">
<button onclick="calcCard()">Calculate</button>
<div class="result" id="c_result"></div>
<div class="chart-wrap"><canvas id="c_chart"></canvas></div>
<p class="chart-caption" id="c_chart_caption"></p>
<div id="c_table" style="margin-top:14px;"></div>
</div>

<div class="calc calc-panel" id="panel-bizval">
<h3>Business Valuation Calculator</h3>
<label>Business type (auto-fills typical SDE/EBITDA multiples below - all remain editable)</label>
<select id="bv_type" onchange="applyBizValDefaults()" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="retail" selected>Retail Store</option>
<option value="wholesale">Wholesale / Distribution</option>
<option value="restaurant">Restaurant / Food Service</option>
<option value="service">Service Business</option>
<option value="manufacturing">Light Manufacturing</option>
<option value="other">Other / General Small Business</option>
</select>
<p class="chart-caption" id="bv_type_hint" style="text-align:left;margin:4px 0 12px;">Retail businesses typically sell for 2.0-3.0x SDE - toward the lower end of Main Street multiples, since inventory/competition risk is priced in. Inventory is usually valued and sold separately, on top of this multiple.</p>
<label>Valuation method</label>
<select id="bv_method" onchange="applyBizValDefaults()" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="sde" selected>SDE Multiple (owner-operated, under ~$1M cash flow - most small businesses)</option>
<option value="ebitda">EBITDA Multiple (professionally managed, $1M+ cash flow)</option>
</select>
<label>Annual revenue ($ - for reference and sanity-check ratios)</label><input type="number" id="bv_revenue" value="800000">
<label>Net profit before owner compensation ($ - from tax return or P&amp;L)</label><input type="number" id="bv_netprofit" value="80000">
<label id="bv_ownersal_label">Owner's annual salary/compensation add-back ($ - SDE only; EBITDA assumes a market-rate manager instead)</label><input type="number" id="bv_ownersal" value="60000">
<label>Owner benefits &amp; perks add-back ($ - health insurance, vehicle, phone, meals, and other personal expenses run through the business)</label><input type="number" id="bv_perks" value="10000">
<label>Interest expense add-back ($)</label><input type="number" id="bv_interest" value="3000">
<label>Depreciation &amp; amortization add-back ($)</label><input type="number" id="bv_da" value="8000">
<label>One-time / non-recurring expenses add-back ($ - legal settlements, one-time repairs, etc.)</label><input type="number" id="bv_onetime" value="0">
<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Valuation Multiple &amp; Assets</h4>
<div class="field-row">
  <div><label>Low multiple (editable)</label><input type="number" id="bv_mult_low" value="2.0" step="0.1"></div>
  <div><label>Mid multiple (editable)</label><input type="number" id="bv_mult_mid" value="2.5" step="0.1"></div>
  <div><label>High multiple (editable)</label><input type="number" id="bv_mult_high" value="3.0" step="0.1"></div>
</div>
<label>Inventory at cost ($ - typically valued and sold separately, added on top of the multiple)</label><input type="number" id="bv_inventory" value="50000">
<label>FF&amp;E / equipment fair market value ($ - for reference; usually already included within the multiple, not added again)</label><input type="number" id="bv_ffe" value="40000">
<label>Liabilities the buyer would assume ($ - 0 for a typical asset sale/cash-free-debt-free deal)</label><input type="number" id="bv_liabilities" value="0">
<button onclick="calcBizVal()">Calculate</button>
<div class="result" id="bv_result"></div>
<div class="chart-wrap"><canvas id="bv_chart"></canvas></div>
<p class="chart-caption" id="bv_chart_caption"></p>
</div>

<script>
function money(x) {
  return "$" + x.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
}
function showCalcTab(panelId, btn) {
  document.querySelectorAll(".calc-panel").forEach(function(p) { p.classList.remove("active"); });
  document.querySelectorAll(".calc-tab-btn").forEach(function(b) { b.classList.remove("active"); });
  document.getElementById(panelId).classList.add("active");
  btn.classList.add("active");
}
function show(id, html) {
  var el = document.getElementById(id);
  el.innerHTML = html;
  el.style.display = "block";
}
var CHART_COLORS = ["#1f4e79", "#4e8cc7", "#7fb3e0", "#a5720b", "#e0b354", "#1a8a3d", "#8fd19e", "#c0392b"];
var chartInstances = {};
function drawPie(canvasId, captionId, labels, values, note) {
  var canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === "undefined") return;
  if (chartInstances[canvasId]) { chartInstances[canvasId].destroy(); }
  chartInstances[canvasId] = new Chart(canvas.getContext("2d"), {
    type: "pie",
    data: {
      labels: labels,
      datasets: [{ data: values, backgroundColor: CHART_COLORS.slice(0, values.length) }]
    },
    options: {
      plugins: {
        legend: { position: "bottom", labels: { font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              var total = ctx.dataset.data.reduce(function(a,b){return a+b;}, 0);
              var pct = total > 0 ? (ctx.parsed / total * 100).toFixed(1) : 0;
              return ctx.label + ": " + money(ctx.parsed) + " (" + pct + "%)";
            }
          }
        }
      }
    }
  });
  if (captionId) {
    var cap = document.getElementById(captionId);
    if (cap) cap.textContent = note || "";
  }
}
function recommendMortgageMaint() {
  var price = +document.getElementById("m_price").value || 0;
  document.getElementById("m_maint").value = Math.round(price * 0.01 / 12);
}
function recommendCREMaint() {
  var rent = +document.getElementById("cre_rent").value || 0;
  document.getElementById("cre_maint").value = Math.round(rent * 0.07);
}
var creUnitRowSeq = 0;
function addUnitRow(label, count, rent) {
  label = label !== undefined ? label : "";
  count = count !== undefined ? count : 1;
  rent = rent !== undefined ? rent : 1000;
  creUnitRowSeq++;
  var id = "cre_unit_row_" + creUnitRowSeq;
  var safeLabel = String(label).replace(/&/g, "&amp;").replace(/'/g, "&#39;");
  var html = "<div class='unit-row' id='" + id + "'>" +
    "<input type='text' placeholder='e.g. 2 Bed / 1 Bath' value='" + safeLabel + "' oninput='updateUnitTotals()'>" +
    "<input type='number' value='" + count + "' min='0' oninput='updateUnitTotals()' title='Number of units of this type'>" +
    "<input type='number' value='" + rent + "' min='0' oninput='updateUnitTotals()' title='Monthly rent per unit ($)'>" +
    "<span class='row-subtotal' id='" + id + "_sub'>$0.00/mo</span>" +
    "<button type='button' class='row-remove' onclick='removeUnitRow(&#39;" + id + "&#39;)'>Remove</button>" +
    "</div>";
  document.getElementById("cre_unit_rows").insertAdjacentHTML("beforeend", html);
  updateUnitTotals();
}
function removeUnitRow(id) {
  var el = document.getElementById(id);
  if (el) el.remove();
  updateUnitTotals();
}
function updateUnitTotals() {
  var rows = document.querySelectorAll("#cre_unit_rows .unit-row");
  var totalUnits = 0, totalMonthly = 0;
  rows.forEach(function(row) {
    var inputs = row.querySelectorAll("input");
    var count = +inputs[1].value || 0;
    var rentEach = +inputs[2].value || 0;
    var sub = count * rentEach;
    totalUnits += count;
    totalMonthly += sub;
    var subEl = document.getElementById(row.id + "_sub");
    if (subEl) subEl.textContent = money(sub) + "/mo";
  });
  document.getElementById("cre_total_units").textContent = totalUnits;
  document.getElementById("cre_total_monthly_rent").textContent = money(totalMonthly);
  document.getElementById("cre_total_annual_rent").textContent = money(totalMonthly * 12);
  document.getElementById("cre_rent").value = totalMonthly;
  document.getElementById("cre_total_units_hidden").value = totalUnits;
}
addUnitRow("1 Bed / 1 Bath", 2, 1000);
addUnitRow("2 Bed / 1 Bath", 1, 1300);
addUnitRow("2 Bed / 2 Bath", 1, 1700);
var CRE_DEFAULTS = {
  res14: { down: 25, rate: 7.25, amort: 30, term: 0,
           hint: "1-4 unit properties qualify for residential-style financing (conventional or DSCR investment loans) - typically 30-year fixed with no balloon, and rates only modestly above a standard home mortgage." },
  comm5: { down: 25, rate: 7.5,  amort: 25, term: 10,
           hint: "5+ unit properties require true commercial financing (agency, bank portfolio, or CMBS loans) - typically a shorter term (often 10 yrs) with a balloon due, even though payments are calculated on a longer amortization, and rates run somewhat higher than residential." }
};
function applyCREDefaults() {
  var type = document.getElementById("cre_type").value;
  var d = CRE_DEFAULTS[type] || CRE_DEFAULTS.res14;
  document.getElementById("cre_down_pct").value = d.down;
  document.getElementById("cre_rate").value = d.rate;
  document.getElementById("cre_amort").value = d.amort;
  document.getElementById("cre_term").value = d.term;
  document.getElementById("cre_type_hint").textContent = d.hint;
}
function calcCRE() {
  var propType = document.getElementById("cre_type").value;
  var totalUnits = +document.getElementById("cre_total_units_hidden").value || 0;
  var price = +document.getElementById("cre_price").value;
  var downPct = (+document.getElementById("cre_down_pct").value || 0) / 100;
  var rate = +document.getElementById("cre_rate").value / 100 / 12;
  var amortYears = +document.getElementById("cre_amort").value;
  var n = amortYears * 12;
  var termYears = +document.getElementById("cre_term").value || 0;
  var closingPct = (+document.getElementById("cre_closing").value || 0) / 100;
  var rent_m = +document.getElementById("cre_rent").value || 0;
  var vacancy_pct = (+document.getElementById("cre_vacancy").value || 0) / 100;
  var tax_m = (+document.getElementById("cre_tax").value || 0) / 12;
  var ins_m = (+document.getElementById("cre_ins").value || 0) / 12;
  var mgmt_pct = (+document.getElementById("cre_mgmt").value || 0) / 100;
  var maint_m = (+document.getElementById("cre_maint").value || 0);
  var other_m = (+document.getElementById("cre_other").value || 0);

  var down = price * downPct;
  var loan = price - down;
  var closing_amt = price * closingPct;
  var cash_to_close = down + closing_amt;

  if (loan <= 0 || n <= 0 || rent_m <= 0) { show("cre_result", "Check your inputs - purchase price, amortization, and rental income must all be greater than zero."); return; }

  var pmt = rate > 0 ? loan * rate / (1 - Math.pow(1 + rate, -n)) : loan / n;
  var annualDebtService = pmt * 12;

  var vacancy_loss_m = rent_m * vacancy_pct;
  var egi_m = rent_m - vacancy_loss_m;
  var mgmt_fee_m = egi_m * mgmt_pct;
  var totalOpex_m = tax_m + ins_m + mgmt_fee_m + maint_m + other_m;
  var noi_m = egi_m - totalOpex_m;
  var noi_annual = noi_m * 12;

  var dscr = annualDebtService > 0 ? noi_annual / annualDebtService : 0;
  var capRate = price > 0 ? (noi_annual / price) * 100 : 0;
  var monthlyCashFlow = noi_m - pmt;
  var annualCashFlow = monthlyCashFlow * 12;
  var cashOnCash = cash_to_close > 0 ? (annualCashFlow / cash_to_close) * 100 : 0;

  var balloonNote = "";
  if (termYears > 0 && termYears * 12 < n) {
    var bal = loan;
    for (var m = 0; m < termYears * 12; m++) {
      var interest = bal * rate;
      bal -= (pmt - interest);
    }
    balloonNote = "<span style='color:#c0392b;font-weight:600;'>Balloon payment due at year " + termYears + ": " + money(Math.max(bal, 0)) + "</span><br>";
  }

  var dscrColor = dscr >= 1.25 ? "#1a8a3d" : (dscr >= 1.0 ? "#a5720b" : "#c0392b");
  var dscrNote = dscr >= 1.25 ? "Comfortably meets most lenders' minimum (typically 1.20-1.25+)." :
                 dscr >= 1.0 ? "Covers the debt payment, but below many lenders' comfort threshold (1.20-1.25+) - a bigger down payment, lower rate, or higher rent may be needed to qualify." :
                 "Below 1.0 means the property's income does not cover the debt payment as structured - most commercial lenders will not approve this loan without changes.";

  show("cre_result",
    "Loan amount: <strong>" + money(loan) + "</strong> (" + (downPct*100).toFixed(1) + "% down = " + money(down) + ")<br>" +
    "Monthly P&amp;I payment: " + money(pmt) + " (amortized over " + amortYears + " yrs)<br>" +
    balloonNote +
    "<br><u>Debt Service Coverage Ratio (DSCR): <strong style='color:" + dscrColor + ";'>" + dscr.toFixed(2) + "</strong></u><br>" +
    "<span style='font-size:11px;color:#888;'>" + dscrNote + "</span><br><br>" +
    "Net Operating Income (annual): <strong>" + money(noi_annual) + "</strong><br>" +
    "&nbsp;&nbsp;Effective gross income (after " + (vacancy_pct*100).toFixed(1) + "% vacancy): " + money(egi_m) + "/mo<br>" +
    "&nbsp;&nbsp;Property taxes: " + money(tax_m) + "/mo<br>" +
    "&nbsp;&nbsp;Insurance: " + money(ins_m) + "/mo<br>" +
    "&nbsp;&nbsp;Property management (" + (mgmt_pct*100).toFixed(1) + "% of collected rent): " + money(mgmt_fee_m) + "/mo<br>" +
    "&nbsp;&nbsp;Maintenance/capex reserves: " + money(maint_m) + "/mo<br>" +
    (other_m > 0 ? "&nbsp;&nbsp;Other expenses: " + money(other_m) + "/mo<br>" : "") +
    "<br>Cap rate: <strong>" + capRate.toFixed(2) + "%</strong><br>" +
    (totalUnits > 0 ? "Price per unit: " + money(price / totalUnits) + " &nbsp;|&nbsp; Avg rent per unit: " + money(rent_m / totalUnits) + "/mo<br>" : "") +
    "Monthly cash flow (after debt service): <strong style='color:" + (monthlyCashFlow >= 0 ? "#1a8a3d" : "#c0392b") + ";'>" + money(monthlyCashFlow) + "</strong><br>" +
    "Cash-on-cash return: <strong>" + cashOnCash.toFixed(2) + "%</strong><br>" +
    "<br>Cash needed to close: <strong>" + money(cash_to_close) + "</strong> (" + money(down) + " down + " + money(closing_amt) + " closing costs)<br>" +
    "<span style='font-size:11px;color:#888;'>DSCR = annual NOI &divide; annual debt service; most DSCR/commercial lenders want 1.20-1.25 or higher. Cap rate = NOI &divide; purchase price, useful for comparing properties independent of financing. Cash-on-cash = annual pre-tax cash flow &divide; cash invested, the return on your actual out-of-pocket money. " +
    (propType === "res14" ? "For a 1-4 unit property financed with a conventional loan, lenders typically qualify you on your personal income/DTI rather than the property's DSCR alone - DSCR here is still a useful cash-flow health check, and it's the primary metric if you instead use a dedicated DSCR-loan program. " : "For a 5+ unit commercial property, DSCR is usually the primary underwriting metric lenders use to size the loan, rather than your personal income. ") +
    "Underwriting conventions vary by lender, property type, and market - treat these as estimates, not a preapproval.</span>");

  var chartLabels = ["Debt Service (P&I)", "Property Taxes", "Insurance", "Management", "Maintenance/Reserves", "Vacancy Loss"];
  var chartValues = [pmt, tax_m, ins_m, mgmt_fee_m, maint_m, vacancy_loss_m];
  if (other_m > 0) { chartLabels.push("Other"); chartValues.push(other_m); }
  var captionExtra = "";
  if (monthlyCashFlow > 0) {
    chartLabels.push("Net Cash Flow");
    chartValues.push(monthlyCashFlow);
  } else if (monthlyCashFlow < 0) {
    captionExtra = " (shortfall of " + money(-monthlyCashFlow) + "/mo not shown as a slice)";
  }
  drawPie("cre_chart", "cre_chart_caption", chartLabels, chartValues, "Where your " + money(rent_m) + "/mo gross rent goes" + captionExtra);
}
var VEHICLE_DEFAULTS = {
  gas:      { maint: 100, fuel: 150, deprec: 15, evFee: 0,   charger: 0,    battery: 0,   fuelLabel: "Fuel",
              premium: 0,    premiumNote: "" },
  diesel:   { maint: 150, fuel: 170, deprec: 10, evFee: 0,   charger: 0,    battery: 0,   fuelLabel: "Diesel fuel",
              premium: 6000, premiumNote: "Diesel trims (mostly trucks) typically run $4,000-$10,000 more than the gas version of the same model." },
  hybrid:   { maint: 70,  fuel: 90,  deprec: 14, evFee: 0,   charger: 0,    battery: 15,  fuelLabel: "Fuel",
              premium: 4300, premiumNote: "Hybrid trims average about $4,300 more than the gas version of the same model (range: $1,600-$13,000)." },
  electric: { maint: 40,  fuel: 45,  deprec: 18, evFee: 200, charger: 1500, battery: 125, fuelLabel: "Electricity",
              premium: 6000, premiumNote: "EVs typically run $3,000-$8,000+ more than a comparable gas model, though the gap has narrowed as the federal tax credit ended and used-EV prices have dropped." }
};
function applyVehicleDefaults() {
  var type = document.getElementById("a_type").value;
  var d = VEHICLE_DEFAULTS[type] || VEHICLE_DEFAULTS.gas;
  document.getElementById("a_maint").value = d.maint;
  document.getElementById("a_fuel").value = d.fuel;
  document.getElementById("a_deprec_rate").value = d.deprec;
  document.getElementById("a_ev_fee").value = d.evFee;
  document.getElementById("a_charger").value = d.charger;
  document.getElementById("a_battery").value = d.battery;
  document.getElementById("a_fuel_label").textContent = "Monthly " + d.fuelLabel.toLowerCase() + " cost ($ - national average for this vehicle type, editable)";
  updatePriceHint();
}
function updatePriceHint() {
  var type = document.getElementById("a_type").value;
  var d = VEHICLE_DEFAULTS[type] || VEHICLE_DEFAULTS.gas;
  var hint = document.getElementById("a_price_premium_hint");
  if (d.premium > 0) {
    hint.innerHTML = d.premiumNote + " <button type='button' class='suggest-btn' style='margin-top:4px;' onclick='addPricePremium(" + d.premium + ")'>Add ~" + money(d.premium).replace(".00","") + " premium to price</button>";
  } else {
    hint.innerHTML = "";
  }
}
function addPricePremium(amount) {
  var priceField = document.getElementById("a_price");
  priceField.value = (+priceField.value || 0) + amount;
}
function calcQualify() {
  var gm = ((+document.getElementById("q_inc1").value || 0) + (+document.getElementById("q_inc2").value || 0)) / 12;
  var debts = (+document.getElementById("q_debts").value || 0);
  var down = (+document.getElementById("q_down").value || 0);
  var rate = (+document.getElementById("q_rate").value || 0) / 100 / 12;
  var n = (+document.getElementById("q_years").value || 30) * 12;
  var tih = (+document.getElementById("q_tih").value || 0);
  var maint = (+document.getElementById("q_maint").value || 0);
  if (gm <= 0) { show("q_result", "Enter your income."); return; }

  function scenario(front_pct, back_pct) {
    var housing = Math.min(gm * front_pct, gm * back_pct - debts);
    var pi = housing - tih - maint;
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
      "&nbsp;&nbsp;Monthly housing budget: " + money(cons.housing) + " (" + money(cons.pi) + " P&amp;I + " + money(tih) + " tax/ins/HOA + " + money(maint) + " maintenance)<br><br>";
  }
  if (aggr) {
    html += "<u>Upper limit (31/43 - FHA-style stretch)</u><br>" +
      "Max home price: <strong>" + money(aggr.price) + "</strong><br>" +
      "&nbsp;&nbsp;Max loan: " + money(aggr.loan) + " + your " + money(down) + " down<br>" +
      "&nbsp;&nbsp;Monthly housing budget: " + money(aggr.housing) + "<br><br>";
  }
  html += "<span style='font-size:11px;color:#888;'>This is an estimate, not a preapproval. Lenders' 28/36 and 31/43 ratios do not actually count maintenance, but it is a real monthly cost - this calculator sets it aside first so the price you see is one you can genuinely afford to live in, not just qualify for. Lenders also weigh credit score, employment history, and cash reserves. The first number uses the classic 28/36 rule: housing under 28% of gross income, all debts under 36%.</span>";
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
  var maint_m = (+document.getElementById("m_maint").value || 0);
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
  var biweekly = document.getElementById("m_freq").value === "biweekly";
  var extra = (+document.getElementById("m_extra").value || 0);
  if (biweekly && balloonY > 0) { biweekly = false; }
  if (extra > 0 && balloonY > 0) { extra = 0; }
  if (loan <= 0 || n <= 0) { show("m_result", "Check your inputs."); return; }
  if (balloonY > 0 && balloonY * 12 >= n) { balloonY = 0; }
  var pmt = rate > 0 ? loan * rate / (1 - Math.pow(1 + rate, -n)) : loan / n;
  var full = pmt + sec_pmt + tax_m + ins_m + hoa_m + maint_m;
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
  var bw_line = "";
  var accel = (biweekly || extra > 0);
  if (accel) {
    var per_yr2 = biweekly ? 26 : 12;
    var r2 = (+document.getElementById("m_rate").value) / 100 / per_yr2;
    var base_pmt2 = biweekly ? pmt / 2 : pmt;
    var pay2 = base_pmt2 + extra;
    var bb2 = loan, ai_int = 0, periods = 0;
    while (bb2 > 0.005 && periods < per_yr2 * 60) {
      var ib = bb2 * r2;
      ai_int += ib;
      bb2 -= Math.min(pay2 - ib, bb2);
      periods++;
    }
    var ai_years = periods / per_yr2;
    var monthly_int = pmt * n - loan;
    var plan_label = biweekly
      ? (extra > 0 ? money(base_pmt2) + " + " + money(extra) + " extra principal every 2 weeks" : money(base_pmt2) + " every 2 weeks")
      : money(pmt) + " + " + money(extra) + " extra principal each month";
    bw_line = "<br><u>Accelerated plan: " + plan_label + "</u><br>" +
      "Paid off in: <strong>" + ai_years.toFixed(1) + " years</strong> instead of " + (n/12) + "<br>" +
      "Total interest: " + money(ai_int) + "<br>" +
      "<span style='color:#1a8a3d;font-weight:600;'>You save " + money(monthly_int - ai_int) + " in interest and " + ((n/12) - ai_years).toFixed(1) + " years</span><br>" +
      "<span style='font-size:11px;color:#888;'>" +
      (biweekly ? "Biweekly works because 26 half-payments = 13 full payments a year. Verify your lender applies payments immediately and charges no fee - otherwise just make extra principal payments yourself. " : "") +
      (extra > 0 ? "Make sure extra payments are marked APPLY TO PRINCIPAL - otherwise some lenders just credit them toward next month's payment, which saves you nothing." : "") +
      "</span><br>";
  }
  show("m_result",
    bw_line +
    "Total monthly payment: <strong>" + money(full) + "</strong><br>" +
    "&nbsp;&nbsp;1st mortgage principal &amp; interest: " + money(pmt) + "<br>" +
    sec_line +
    "&nbsp;&nbsp;Property taxes: " + money(tax_m) + " /mo<br>" +
    "&nbsp;&nbsp;Insurance: " + money(ins_m) + " /mo<br>" +
    hoa_line +
    "&nbsp;&nbsp;Estimated maintenance: " + money(maint_m) + " /mo<br>" +
    balloon_line +
    "1st mortgage amount: " + money(loan) + (sec_amt > 0 ? "<br>2nd mortgage amount: " + money(sec_amt) : "") + "<br>" +
    (balloonY > 0 ? "" : "Total interest over the loan: " + money(total - loan) + "<br>") +
    "<br><u>Cash needed at closing: <strong>" + money(cash_to_close) + "</strong></u><br>" +
    "&nbsp;&nbsp;Down payment: " + money(down) + "<br>" +
    (comm_amt > 0 ? "&nbsp;&nbsp;Buyer's agent commission (" + comm_pct + "%): " + money(comm_amt) + "<br>" : "") +
    (closing_amt > 0 ? "&nbsp;&nbsp;Other closing costs (" + closing_pct + "%): " + money(closing_amt) + "<br>" : "") +
    (inspect_amt > 0 ? "&nbsp;&nbsp;Home inspection: " + money(inspect_amt) + "<br>" : "") +
    "<span style='font-size:11px;color:#888;'>Taxes, insurance, and HOA are estimates and usually rise over time. PMI (required below 20% down) is extra. With an interest-only second mortgage, the monthly payment never reduces its principal - the full amount remains due at payoff, sale, or refinance. Buyer-agent commission is negotiable and cannot usually be rolled into the loan - though sellers often agree to cover it, so ask. Every dollar paid in commission is a dollar unavailable for your down payment.</span>");

  var chartLabels = ["Principal & Interest"];
  var chartValues = [pmt];
  if (sec_amt > 0) { chartLabels.push("2nd Mortgage"); chartValues.push(sec_pmt); }
  chartLabels.push("Property Tax"); chartValues.push(tax_m);
  chartLabels.push("Insurance"); chartValues.push(ins_m);
  if (hoa_m > 0) { chartLabels.push("HOA"); chartValues.push(hoa_m); }
  if (maint_m > 0) { chartLabels.push("Maintenance"); chartValues.push(maint_m); }
  drawPie("m_chart", "m_chart_caption", chartLabels, chartValues, "Where your " + money(full) + " total monthly payment goes");

  // Yearly amortization schedule (principal & interest only)
  var bal = loan, t = "";
  t += "<h3 style='font-size:14px;margin:10px 0 8px;'>Amortization Schedule (yearly, 1st mortgage" + (biweekly ? ", biweekly payments" : "") + (extra > 0 ? ", with extra principal" : "") + ")</h3>";
  t += "<div class='table-wrap'><table><tr>";
  t += "<th>Year</th>";
  t += "<th style='text-align:right;'>Principal Paid</th>";
  t += "<th style='text-align:right;'>Interest Paid</th>";
  t += "<th style='text-align:right;'>Remaining Balance</th></tr>";
  var per_year = biweekly ? 26 : 12;
  var per_rate = biweekly ? (+document.getElementById("m_rate").value) / 100 / 26 : rate;
  var per_pmt = (biweekly ? pmt / 2 : pmt) + extra;
  var years_n = balloonY > 0 ? balloonY : ((biweekly || extra > 0) ? 60 : Math.ceil(n / 12));
  for (var y = 1; y <= years_n; y++) {
    var prinY = 0, intY = 0;
    for (var m = 0; m < per_year && bal > 0.005; m++) {
      var im = bal * per_rate;
      var pr = Math.min(per_pmt - im, bal);
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
  var tax_pct = (+document.getElementById("a_tax").value || 0) / 100;
  var fees = (+document.getElementById("a_fees").value || 0);
  var roll = document.getElementById("a_roll").value === "yes";
  var rate = +document.getElementById("a_rate").value / 100 / 12;
  var n = +document.getElementById("a_months").value;
  var maint_m = (+document.getElementById("a_maint").value || 0);
  var deprec_rate = (+document.getElementById("a_deprec_rate").value || 0) / 100;
  var deprec_m = price * deprec_rate / 12;
  var vType = document.getElementById("a_type").value;
  var isEV = vType === "electric";
  var typeLabel = { gas: "gasoline", diesel: "diesel", hybrid: "hybrid", electric: "EV" }[vType] || "gasoline";
  var fuelLabel = (VEHICLE_DEFAULTS[vType] || VEHICLE_DEFAULTS.gas).fuelLabel;
  var fuel_m = (+document.getElementById("a_fuel").value || 0);
  var tolls_m = (+document.getElementById("a_tolls").value || 0);
  var parking_m = (+document.getElementById("a_parking").value || 0);
  var ev_fee_m = (+document.getElementById("a_ev_fee").value || 0) / 12;
  var charger_cost = (+document.getElementById("a_charger").value || 0);
  var battery_m = (+document.getElementById("a_battery").value || 0);
  var taxable = Math.max(price - trade, 0);
  var tax = taxable * tax_pct;
  var loan = price - down - trade + (roll ? tax + fees : 0);
  var cash_upfront = down + (roll ? 0 : tax + fees);
  var cash_upfront_display = cash_upfront + charger_cost;
  if (loan <= 0 || n <= 0) { show("a_result", "Check your inputs."); return; }
  var pmt = rate > 0 ? loan * rate / (1 - Math.pow(1 + rate, -n)) : loan / n;
  var total = pmt * n;
  var trueCost = pmt + maint_m + deprec_m + fuel_m + tolls_m + parking_m + ev_fee_m + battery_m;
  show("a_result",
    "Monthly payment: <strong>" + money(pmt) + "</strong><br>" +
    "Loan amount: " + money(loan) + "<br>" +
    "&nbsp;&nbsp;Vehicle price: " + money(price) + "<br>" +
    (trade > 0 ? "&nbsp;&nbsp;Trade-in: -" + money(trade) + "<br>" : "") +
    (down > 0 ? "&nbsp;&nbsp;Down payment: -" + money(down) + "<br>" : "") +
    (tax > 0 ? "&nbsp;&nbsp;Sales tax (" + (tax_pct*100).toFixed(1) + "% after trade-in credit): +" + money(tax) + (roll ? " (financed)" : " (paid in cash)") + "<br>" : "") +
    (fees > 0 ? "&nbsp;&nbsp;Dealer/doc/title fees: +" + money(fees) + (roll ? " (financed)" : " (paid in cash)") + "<br>" : "") +
    "Cash due upfront: " + money(cash_upfront_display) + "<br>" +
    (charger_cost > 0 ? "&nbsp;&nbsp;(includes " + money(charger_cost) + " home charger installation - the federal 30%/$1,000 tax credit for this expired 6/30/2026; check for state or utility rebates)<br>" : "") +
    "Total paid over the loan: " + money(total + cash_upfront - down) + "<br>" +
    "Total interest: " + money(total - loan) + "<br><br>" +
    "<u>Estimated true monthly cost of ownership: <strong>" + money(trueCost) + "</strong></u><br>" +
    "&nbsp;&nbsp;Loan payment: " + money(pmt) + "<br>" +
    "&nbsp;&nbsp;Maintenance (" + typeLabel + " national average): " + money(maint_m) + "<br>" +
    "&nbsp;&nbsp;Depreciation (" + (deprec_rate*100).toFixed(1) + "%/yr " + typeLabel + " national average): Monthly " + money(deprec_m) + "<br>" +
    "&nbsp;&nbsp;" + fuelLabel + ": Monthly " + money(fuel_m) + "<br>" +
    (tolls_m > 0 ? "&nbsp;&nbsp;Tolls: Monthly " + money(tolls_m) + "<br>" : "") +
    (parking_m > 0 ? "&nbsp;&nbsp;Parking: Monthly " + money(parking_m) + "<br>" : "") +
    (ev_fee_m > 0 ? "&nbsp;&nbsp;EV road-use/registration surcharge: Monthly " + money(ev_fee_m) + "<br>" : "") +
    (battery_m > 0 ? "&nbsp;&nbsp;Battery replacement reserve (optional contingency): Monthly " + money(battery_m) + "<br>" : "") +
    "<br><span style='font-size:11px;color:#888;'>Tax is calculated on the price after trade-in credit, as most states do - a real advantage of trading in vs selling privately. Financing tax and fees raises the payment and means paying interest on them. Trade-in assumes any old loan on it is already paid off. Depreciation isn't a cash outflow, but it's a real cost - it's value you lose whether or not you ever sell the car. " +
    (vType === "diesel" ? "Diesel engines typically cost 60-80% more to maintain than gas (DEF fluid, pricier oil changes and filters, costlier repairs) but often hold resale value better and can win out on fuel efficiency for high-mileage or towing use. " : "") +
    (vType === "hybrid" ? "Hybrids typically fall between gas and EVs on both maintenance and fuel cost - regenerative braking reduces brake wear, and better MPG lowers fuel spend, while still needing the routine service of a combustion engine. " : "") +
    (isEV ? "EVs typically cost 40-60% less to maintain than gas vehicles - no oil changes, spark plugs, or transmission service - though tires wear faster and the small 12V battery ($100-$250) eventually needs replacing. Note that EVs (excluding Tesla) have generally been depreciating faster than gas vehicles in the first few years (often 45-55% over 3 years vs. 35-45% for gas), even though they cost less to run - that's reflected in the higher default depreciation rate above. " : "") +
    (isEV ? "EVs typically cost far less to fuel than gas vehicles, but a growing number of states now charge EVs an extra annual registration/road-use fee (commonly $50-$290/yr) to make up for the gas tax they don't pay - Florida is among the states that have adjusted this in recent years, and the rules keep changing, so verify the current amount with your county tax collector or state DMV before relying on it. " : "") +
    (battery_m > 0 ? "The battery reserve is a personal contingency fund, not a bill you're guaranteed to pay - a federal law requires 8-year/100,000-mile battery warranties, and industry data shows only about 2.5% of EV owners ever pay for a replacement out of pocket. Think of it like an emergency fund line item, not a certain expense. " : "") +
    "</span>");

  var chartLabels = ["Loan Payment", "Maintenance", "Depreciation", fuelLabel];
  var chartValues = [pmt, maint_m, deprec_m, fuel_m];
  if (tolls_m > 0) { chartLabels.push("Tolls"); chartValues.push(tolls_m); }
  if (parking_m > 0) { chartLabels.push("Parking"); chartValues.push(parking_m); }
  if (ev_fee_m > 0) { chartLabels.push("EV Fee"); chartValues.push(ev_fee_m); }
  if (battery_m > 0) { chartLabels.push("Battery Reserve"); chartValues.push(battery_m); }
  drawPie("a_chart", "a_chart_caption", chartLabels, chartValues,
    "Estimated true monthly cost of ownership: " + money(trueCost));
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
  var schedule = [];
  while (b > 0 && months < 1200) {
    var beginBal = b;
    var int_m = b * rate;
    interest += int_m;
    var cb_m = spend * cb_pct;
    cashback += cb_m;
    var principal_m = pmt - int_m - spend + cb_m; // net balance reduction from this payment cycle
    b = b + int_m + spend - pmt - cb_m;
    months++;
    if (months <= 12) {
      schedule.push({
        month: months,
        begin: beginBal,
        payment: pmt,
        interest: int_m,
        principal: principal_m,
        end: Math.max(b, 0)
      });
    }
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

  // 12-month (or fewer, if paid off sooner) payment breakdown table
  var shownMonths = schedule.length;
  var sumInt = 0, sumPrin = 0;
  var t = "<h3 style='font-size:14px;margin:10px 0 8px;'>Monthly Breakdown (first " + shownMonths + " month" + (shownMonths === 1 ? "" : "s") + ")</h3>";
  t += "<div class='table-wrap'><table><tr>";
  t += "<th>Month</th><th style='text-align:right;'>Starting Balance</th><th style='text-align:right;'>Payment</th>";
  t += "<th style='text-align:right;'>Interest</th><th style='text-align:right;'>Principal</th><th style='text-align:right;'>Ending Balance</th></tr>";
  schedule.forEach(function(row) {
    sumInt += row.interest;
    sumPrin += row.principal;
    t += "<tr><td>" + row.month + "</td>" +
         "<td style='text-align:right;'>" + money(row.begin) + "</td>" +
         "<td style='text-align:right;'>" + money(row.payment) + "</td>" +
         "<td style='text-align:right;color:#c0392b;'>" + money(row.interest) + "</td>" +
         "<td style='text-align:right;color:#1a8a3d;'>" + money(row.principal) + "</td>" +
         "<td style='text-align:right;'>" + money(row.end) + "</td></tr>";
  });
  t += "</table></div>";
  t += "<p class='note'>Shows exactly how each payment splits between interest and principal, and how much your balance drops each month" +
       (shownMonths < 12 ? " (the card is fully paid off before reaching 12 months)." : " over the first 12 months.") + "</p>";
  document.getElementById("c_table").innerHTML = t;

  drawPie("c_chart", "c_chart_caption",
    ["Interest", "Principal"],
    [sumInt, sumPrin],
    "Split of your payments over the first " + shownMonths + " month" + (shownMonths === 1 ? "" : "s") + ": interest vs. principal");
}

var BIZVAL_DEFAULTS = {
  retail: {
    sde:    { low: 2.0, mid: 2.5, high: 3.0,
              hint: "Retail businesses typically sell for 2.0-3.0x SDE - toward the lower end of Main Street multiples, since inventory/competition risk is priced in. Inventory is usually valued and sold separately, on top of this multiple." },
    ebitda: { low: 3.0, mid: 4.0, high: 5.0,
              hint: "Larger, professionally managed retail operations (multi-location or $1M+ cash flow) typically trade at 3-5x EBITDA." }
  },
  wholesale: {
    sde:    { low: 3.0, mid: 3.75, high: 4.5,
              hint: "Wholesale/distribution businesses often command a premium over retail (roughly 3-4.5x SDE) due to B2B customer relationships and repeat/contract revenue - though inventory turns and customer concentration swing this a lot." },
    ebitda: { low: 4.0, mid: 5.5, high: 7.0,
              hint: "Larger distributors ($5M+ revenue, $1M+ EBITDA) typically trade at 5-7x EBITDA, with strategic/consolidator buyers paying toward the top of that range for route density and vendor exclusivity." }
  },
  restaurant: {
    sde:    { low: 1.5, mid: 2.0, high: 2.5,
              hint: "Restaurants are among the lower-multiple categories (roughly 1.5-2.5x SDE) due to high failure rates, thin margins, and heavy owner-dependence - strong multi-year financials and a long, transferable lease help push toward the high end." },
    ebitda: { low: 2.5, mid: 3.0, high: 3.5,
              hint: "Multi-unit or franchise restaurant groups with $1M+ cash flow typically trade at 2.5-3.5x EBITDA." }
  },
  service: {
    sde:    { low: 2.0, mid: 2.5, high: 3.0,
              hint: "Service businesses (contracting, professional services, etc.) typically sell for 2-3x SDE - recurring contracts, licensing/certifications, and low owner-dependence push toward the high end." },
    ebitda: { low: 3.0, mid: 4.0, high: 5.0,
              hint: "Larger service businesses with $1M+ cash flow and management depth typically trade at 3-5x EBITDA." }
  },
  manufacturing: {
    sde:    { low: 2.5, mid: 3.25, high: 4.0,
              hint: "Light manufacturing typically sells for 2.5-4x SDE - equipment/capital barriers to entry and specialized processes support a premium over general retail." },
    ebitda: { low: 3.5, mid: 4.5, high: 5.5,
              hint: "Larger manufacturers with $1M+ cash flow typically trade at 3.5-5.5x EBITDA, more if there's proprietary IP or a diversified customer base." }
  },
  other: {
    sde:    { low: 2.0, mid: 2.6, high: 3.5,
              hint: "The overall Main Street average across all industries is roughly 2.6-2.7x SDE (2026) - use this as a general starting point and adjust for your specific industry, growth, and risk profile." },
    ebitda: { low: 3.0, mid: 4.0, high: 5.0,
              hint: "Larger owner-independent businesses with $1M+ cash flow typically trade at 3-5x EBITDA as a general starting point." }
  }
};
function applyBizValDefaults() {
  var type = document.getElementById("bv_type").value;
  var method = document.getElementById("bv_method").value;
  var d = (BIZVAL_DEFAULTS[type] || BIZVAL_DEFAULTS.other)[method];
  document.getElementById("bv_mult_low").value = d.low;
  document.getElementById("bv_mult_mid").value = d.mid;
  document.getElementById("bv_mult_high").value = d.high;
  document.getElementById("bv_type_hint").textContent = d.hint;
  document.getElementById("bv_ownersal_label").style.opacity = method === "ebitda" ? "0.5" : "1";
}
function calcBizVal() {
  var method = document.getElementById("bv_method").value;
  var revenue = +document.getElementById("bv_revenue").value || 0;
  var netProfit = +document.getElementById("bv_netprofit").value || 0;
  var ownerSal = +document.getElementById("bv_ownersal").value || 0;
  var perks = +document.getElementById("bv_perks").value || 0;
  var interest = +document.getElementById("bv_interest").value || 0;
  var da = +document.getElementById("bv_da").value || 0;
  var onetime = +document.getElementById("bv_onetime").value || 0;

  var sde = netProfit + ownerSal + perks + interest + da + onetime;
  var ebitda = netProfit + interest + da + onetime;
  var cashFlow = method === "sde" ? sde : ebitda;
  var cashFlowLabel = method === "sde" ? "SDE" : "EBITDA";

  var multLow = +document.getElementById("bv_mult_low").value || 0;
  var multMid = +document.getElementById("bv_mult_mid").value || 0;
  var multHigh = +document.getElementById("bv_mult_high").value || 0;
  var inventory = +document.getElementById("bv_inventory").value || 0;
  var ffe = +document.getElementById("bv_ffe").value || 0;
  var liabilities = +document.getElementById("bv_liabilities").value || 0;

  if (cashFlow <= 0) {
    show("bv_result", "Check your inputs - net profit plus add-backs must be greater than zero to produce a valuation.");
    return;
  }

  var valLow = cashFlow * multLow;
  var valMid = cashFlow * multMid;
  var valHigh = cashFlow * multHigh;
  var totalLow = valLow + inventory - liabilities;
  var totalMid = valMid + inventory - liabilities;
  var totalHigh = valHigh + inventory - liabilities;

  var margin = revenue > 0 ? (cashFlow / revenue * 100) : 0;
  var revMultLow = revenue > 0 ? totalLow / revenue : 0;
  var revMultHigh = revenue > 0 ? totalHigh / revenue : 0;

  show("bv_result",
    cashFlowLabel + " (annual): <strong>" + money(cashFlow) + "</strong> (" + margin.toFixed(1) + "% of revenue)<br>" +
    (method === "sde" ? "&nbsp;&nbsp;EBITDA for reference: " + money(ebitda) + "<br>" : "&nbsp;&nbsp;SDE for reference: " + money(sde) + "<br>") +
    "<br><u>Estimated Business Value (before inventory)</u><br>" +
    "Low (" + multLow.toFixed(1) + "x): " + money(valLow) + " &nbsp;|&nbsp; Mid (" + multMid.toFixed(1) + "x): <strong>" + money(valMid) + "</strong> &nbsp;|&nbsp; High (" + multHigh.toFixed(1) + "x): " + money(valHigh) + "<br>" +
    (inventory > 0 ? "<br>+ Inventory at cost: " + money(inventory) + "<br>" : "") +
    (liabilities > 0 ? "- Liabilities assumed: " + money(liabilities) + "<br>" : "") +
    "<br><u>Total Estimated Value Range</u><br>" +
    "Low: " + money(totalLow) + " &nbsp;|&nbsp; Mid: <strong>" + money(totalMid) + "</strong> &nbsp;|&nbsp; High: " + money(totalHigh) + "<br>" +
    "<span style='font-size:11px;color:#888;'>Implied revenue multiple: " + revMultLow.toFixed(2) + "x-" + revMultHigh.toFixed(2) + "x of annual revenue (sanity check - Main Street businesses commonly sell for roughly 0.3x-1x revenue depending on margin).</span><br><br>" +
    (ffe > 0 ? "FF&amp;E/equipment (reference - usually already included within the multiple, not added again): " + money(ffe) + "<br><br>" : "") +
    "<span style='font-size:11px;color:#888;'>This is a starting-point estimate using the market (multiple) approach, the standard method for valuing small and mid-sized businesses. Actual sale price depends heavily on factors this calculator can't see: customer concentration, owner dependency, growth trend, lease terms, competitive moat, and buyer type. The overall Main Street average is roughly 2.6-2.7x SDE (2026) across all industries - your multiple should reflect where your business sits within its category's range. Verify add-backs carefully; inflated or undocumented add-backs are the most common source of valuation disputes. This is not a substitute for a professional business appraisal or a broker's opinion of value.</span>");

  var chartLabels = ["Net Profit"];
  var chartValues = [Math.max(netProfit, 0)];
  if (method === "sde") {
    if (ownerSal > 0) { chartLabels.push("Owner Salary"); chartValues.push(ownerSal); }
    if (perks > 0) { chartLabels.push("Owner Perks"); chartValues.push(perks); }
  }
  if (interest > 0) { chartLabels.push("Interest"); chartValues.push(interest); }
  if (da > 0) { chartLabels.push("D&A"); chartValues.push(da); }
  if (onetime > 0) { chartLabels.push("One-Time Items"); chartValues.push(onetime); }
  drawPie("bv_chart", "bv_chart_caption", chartLabels, chartValues, "Composition of " + cashFlowLabel + ": " + money(cashFlow));
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
