import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import requests
import json
import html as html_escape_mod
from datetime import datetime, timedelta

FRED_API_KEY = "d6150924a7a201d4e891d082f7123818"

WATCHLIST = ["AAPL", "GOOGL", "VTI", "QCOM", "TSM", "META", "TSLA", "MSFT", "INTC", "NVDA", "AMD", "ORCL", "DRIV", "ARTY", "ROBO", "SHOP", "SNPS", "VHT", "CRDO", "RMBS", "SDY", "VYM", "IVE", "AVGO", "JNJ", "AMZN", "BMY", "MRVL", "SCHD", "SPY", "WM", "RSG", "IDU", "MKC", "MRK", "ADM", "GIS", "BRK-B", "LLY", "VOO", "QQQ", "TQQQ", "SQQQ", "SDS", "CSCO", "WMT", "DE", "PEP", "KO", "V", "MA", "CMI", "CAT", "UNP", "CSX", "NSC", "PLTR", "DELL", "MU", "SNDK", "LMT", "AMGN", "ABBV", "RTX", "IONQ", "KEEL", "JCI", "HONA", "HON"]

INDEXES = [
    # US
    ("Dow Jones", "^DJI"),
    ("S&P 500", "^GSPC"),
    ("Nasdaq Composite", "^IXIC"),
    ("Nasdaq-100", "^NDX"),
    ("Russell 2000", "^RUT"),
    ("Russell 1000", "^RUI"),
    ("S&P MidCap 400", "^MID"),
    ("US Dollar (DXY)", "DX-Y.NYB"),
    ("VIX (Volatility)", "^VIX"),
    # Europe
    ("FTSE 100 (UK)", "^FTSE"),
    ("DAX (Germany)", "^GDAXI"),
    ("CAC 40 (France)", "^FCHI"),
    ("Euro Stoxx 50", "^STOXX50E"),
    ("IBEX 35 (Spain)", "^IBEX"),
    ("FTSE MIB (Italy)", "FTSEMIB.MI"),
    # Asia-Pacific
    ("Nikkei 225 (Japan)", "^N225"),
    ("Hang Seng (Hong Kong)", "^HSI"),
    ("Shanghai Composite (China)", "000001.SS"),
    ("Sensex (India)", "^BSESN"),
    ("Nifty 50 (India)", "^NSEI"),
    ("KOSPI (South Korea)", "^KS11"),
    ("ASX 200 (Australia)", "^AXJO"),
    ("Taiwan Weighted", "^TWII"),
    # Americas
    ("TSX Composite (Canada)", "^GSPTSE"),
    ("Bovespa (Brazil)", "^BVSP"),
    ("IPC (Mexico)", "^MXX"),
    # More Europe / Nordics
    ("SMI (Switzerland)", "^SSMI"),
    ("AEX (Netherlands)", "^AEX"),
    ("OMX Stockholm 30 (Sweden)", "^OMX"),
    ("BEL 20 (Belgium)", "^BFX"),
    ("ATX (Austria)", "^ATX"),
    ("ISEQ (Ireland)", "^ISEQ"),
    # More Asia-Pacific
    ("Straits Times (Singapore)", "^STI"),
    ("KLCI (Malaysia)", "^KLSE"),
    ("Jakarta Composite (Indonesia)", "^JKSE"),
    ("NZX 50 (New Zealand)", "^NZ50"),
    # Other
    ("JSE Top 40 (South Africa)", "^J203.JO"),
]

# Stock index FUTURES - different from the spot indices above: these trade nearly 24 hours
# and reflect where traders expect the index to open, unlike the cash index which only prices
# during market hours.
INDEX_FUTURES = [
    ("S&P 500 Futures (E-mini)", "ES=F"),
    ("Dow Futures (E-mini)", "YM=F"),
    ("Nasdaq-100 Futures (E-mini)", "NQ=F"),
    ("Russell 2000 Futures (E-mini)", "RTY=F"),
    ("Nikkei 225 Futures", "NIY=F"),
]


COMMODITIES = [
    # Energy
    ("Oil (WTI)", "CL=F"),
    ("Oil (Brent)", "BZ=F"),
    ("Natural Gas", "NG=F"),
    ("Heating Oil", "HO=F"),
    ("RBOB Gasoline", "RB=F"),
    # Metals
    ("Gold", "GC=F"),
    ("Silver", "SI=F"),
    ("Copper", "HG=F"),
    ("Platinum", "PL=F"),
    ("Palladium", "PA=F"),
    # Agriculture
    ("Corn", "ZC=F"),
    ("Wheat", "ZW=F"),
    ("Soybeans", "ZS=F"),
    ("Soybean Oil", "ZL=F"),
    ("Coffee", "KC=F"),
    ("Cotton", "CT=F"),
    ("Sugar", "SB=F"),
    ("Cocoa", "CC=F"),
    ("Live Cattle", "LE=F"),
    ("Lean Hogs", "HE=F"),
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

# Major world currencies vs USD - Federal Reserve H.10 daily rates via FRED.
# This is the complete set of individual currency pairs FRED publishes (23) - confirmed directly
# against FRED's own H.10 release page. (FRED's "26" total also includes 3 broad trade-weighted
# dollar indices, which are composite baskets, not individual currencies, so not included here.)
# "usd_per" = value is USD per 1 unit of that currency (rate rises when that currency strengthens).
# "per_usd" = value is that currency per 1 USD (rate rises when USD strengthens).
CURRENCY_SERIES = [
    ("Euro", "EUR", "DEXUSEU", "usd_per"),
    ("British Pound", "GBP", "DEXUSUK", "usd_per"),
    ("Australian Dollar", "AUD", "DEXUSAL", "usd_per"),
    ("New Zealand Dollar", "NZD", "DEXUSNZ", "usd_per"),
    ("Japanese Yen", "JPY", "DEXJPUS", "per_usd"),
    ("Chinese Yuan", "CNY", "DEXCHUS", "per_usd"),
    ("Canadian Dollar", "CAD", "DEXCAUS", "per_usd"),
    ("Mexican Peso", "MXN", "DEXMXUS", "per_usd"),
    ("Swiss Franc", "CHF", "DEXSZUS", "per_usd"),
    ("Hong Kong Dollar", "HKD", "DEXHKUS", "per_usd"),
    ("South Korean Won", "KRW", "DEXKOUS", "per_usd"),
    ("Indian Rupee", "INR", "DEXINUS", "per_usd"),
    ("Brazilian Real", "BRL", "DEXBZUS", "per_usd"),
    ("Malaysian Ringgit", "MYR", "DEXMAUS", "per_usd"),
    ("Thai Baht", "THB", "DEXTHUS", "per_usd"),
    ("Taiwan Dollar", "TWD", "DEXTAUS", "per_usd"),
    ("South African Rand", "ZAR", "DEXSFUS", "per_usd"),
    ("Singapore Dollar", "SGD", "DEXSIUS", "per_usd"),
    ("Swedish Krona", "SEK", "DEXSDUS", "per_usd"),
    ("Norwegian Krone", "NOK", "DEXNOUS", "per_usd"),
    ("Danish Krone", "DKK", "DEXDNUS", "per_usd"),
    ("Sri Lankan Rupee", "LKR", "DEXSLUS", "per_usd"),
    ("Venezuelan Bolivar", "VES", "DEXVZUS", "per_usd"),
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

# South Florida tri-county foreclosure activity - ATTOM Q1 2026 data
# Filings = properties with a foreclosure filing in the quarter; Rate = "1 in X" housing units (lower X = worse)
# YoY = year-over-year change in filings
# No free API exists for county-level foreclosure stats (ATTOM's data is licensed) - this is refreshed
# manually each quarter. Ask Claude to "update my tri-county foreclosure data" to refresh from the latest report.
TRICOUNTY_FORECLOSURES = [
    ("Broward", "1,232", "1 in 703", "+24.6%"),
    ("Palm Beach", "926", "1 in 777", "+34.2%"),
    ("Miami-Dade", "1,010", "n/a", "+1.7%"),
]
TRICOUNTY_ASOF = "Q1 2026"

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
  <a href="calculators.html" style="margin-right:16px;font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">Calculators</a>
  <a href="search.html" style="margin-right:16px;font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">Property Search</a>
  <a href="stocksearch.html" style="margin-right:16px;font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">Stock Search</a>
  <a href="propertymanager.html" style="font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">Property Manager</a>
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

def fetch_all_us_tickers():
    """SEC's official, free, comprehensive list of all SEC-registered tickers.
    Format is a JSON object keyed by index number: {"0": {"cik_str":..,"ticker":..,"title":..}, ...}
    SEC requires a descriptive User-Agent identifying the requester on all requests."""
    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {"User-Agent": "USA Tools Inc Stock Portal contact@usatoolsinc.com"}
        resp = requests.get(url, headers=headers, timeout=30)
        data = resp.json()
        tickers = []
        for entry in data.values():
            tickers.append({"ticker": entry.get("ticker", ""), "name": entry.get("title", "")})
        return tickers
    except Exception as e:
        print(f"Warning: could not fetch SEC ticker list ({e}) - stocksearch.html will use an empty list")
        return []

# ------------------- FETCH EVERYTHING -------------------

all_us_tickers = fetch_all_us_tickers()

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

futures_rows = []
for name, symbol in INDEX_FUTURES:
    r = fetch_simple_price(symbol)
    if r:
        futures_rows.append({"name": name, **r})

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

currency_rows = []
for name, code, series_id, direction in CURRENCY_SERIES:
    r = fetch_fred_rate(series_id)
    if r:
        currency_rows.append({"name": name, "code": code, "direction": direction, **r})

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

def currency_cards(items):
    out = ""
    for i in items:
        if i["direction"] == "usd_per":
            val = f"1 {i['code']} = ${i['value']:.4f}"
        else:
            val = f"1 USD = {i['value']:.4f} {i['code']}"
        six = sixmo_line(i.get("value_6mo"), i["value"], unit="")
        out += f"""
    <div class="card" title="{i['name']} ({i['code']}) vs US Dollar, Federal Reserve H.10 daily rate">
      <p class="label">{i['name']} ({i['code']})</p>
      <p class="value" style="font-size:16px;">{val}</p>
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

def tricounty_foreclosure_rows(items):
    out = ""
    for county, filings, rate, yoy in items:
        yoy_num_str = yoy.replace("%", "").replace("+", "")
        try:
            yoy_color = "#c0392b" if float(yoy_num_str) > 0 else "#1a8a3d"
        except ValueError:
            yoy_color = "#666"
        out += f"""
    <tr>
      <td style="font-weight:600;">{county}</td>
      <td style="text-align:right;">{filings}</td>
      <td style="text-align:right;">{rate}</td>
      <td style="text-align:right;color:{yoy_color};">{yoy}</td>
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

<h2>Index Futures</h2>
<div class="row">{simple_cards(futures_rows, dollar=False)}</div>
<p class="note">Stock index futures trade nearly 24 hours a day, including outside regular market hours - often what's behind "futures point to a lower/higher open" headlines. Not directly comparable to the cash index level above since futures prices include financing costs and dividend expectations.</p>

<h2>Commodities</h2>
<div class="row">{simple_cards(commodity_rows)}</div>

<h2>Currency Exchange Rates</h2>
<div class="row">{currency_cards(currency_rows)}</div>
<p class="note">Federal Reserve H.10 daily noon buying rates vs the US Dollar - all 23 individual currency pairs the Fed publishes daily. "USD per" currencies (Euro, Pound, Australian Dollar, New Zealand Dollar) rise when that currency strengthens against the dollar; "per USD" currencies rise when the dollar strengthens. "6 mo ago" compares to the reading six months earlier. Source: Federal Reserve (FRED).</p>

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

<h2>South Florida Foreclosure Activity - Miami-Dade, Broward &amp; Palm Beach (updated manually, {TRICOUNTY_ASOF})</h2>
<table>
<tr><th>County</th><th style="text-align:right;">Filings</th><th style="text-align:right;">Rate</th><th style="text-align:right;">YoY Change</th></tr>
{tricounty_foreclosure_rows(TRICOUNTY_FORECLOSURES)}
</table>
<p class="note">"Filings" = properties with a foreclosure filing during the quarter. "Rate" is 1-in-X housing units (lower X = worse); Miami-Dade's county-specific rate wasn't broken out in the source used and is shown as n/a rather than estimated. No free API exists for county-level foreclosure data (ATTOM's underlying data is licensed) - this table is refreshed manually each quarter from ATTOM's public reports. Ask Claude to "update my tri-county foreclosure data" to refresh it.</p>

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

@media (max-width: 600px) {
  body { padding:12px; }
  .calc { padding:14px; max-width:100%; }
  .calc input, .calc select, select, .unit-row input {
    font-size:16px !important;
    padding:10px !important;
  }
  .calc button { width:100%; padding:13px 18px; }
  .calc-tabs { gap:6px; }
  .calc-tab-btn { flex:1 1 auto; text-align:center; font-size:12px; padding:10px 8px; }
  .field-row { flex-direction:column; align-items:stretch; gap:4px; }
  .suggest-btn { width:100%; margin-top:2px; padding:11px 10px; }
  .unit-row { flex-wrap:wrap; }
  .unit-row input[type="text"] { flex:1 1 100%; }
  .unit-row input[type="number"] { flex:1 1 auto; min-width:70px; }
  .unit-row .row-subtotal { flex:1 1 auto; text-align:left; margin-top:2px; }
  .unit-row .row-remove { flex:0 0 auto; margin-top:2px; }
  table { font-size:12px; }
  th, td { padding:6px 8px; }
  .chart-wrap { max-width:220px; }
  .summary, .row { gap:8px; }
  .card { min-width:130px; padding:12px; }
}
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
  <button type="button" class="calc-tab-btn" onclick="showCalcTab('panel-lease', this)">Car Lease</button>
  <button type="button" class="calc-tab-btn" onclick="showCalcTab('panel-boat', this)">Boat Financing</button>
  <button type="button" class="calc-tab-btn" onclick="showCalcTab('panel-rv', this)">RV Financing</button>
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
<label>Annual revenue ($ - for reference and sanity-check ratios)</label><input type="number" id="bv_revenue" value="800000" oninput="updateComputedNetProfitDisplay()">

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Optional: Build Net Profit from Revenue &amp; Expenses</h4>
<p class="chart-caption" style="text-align:left;margin:0 0 8px;">Skip this section if you already know your net profit before owner compensation - just enter it directly below. Otherwise, fill in your expenses here and click "Use This Net Profit." Normal operating costs like rent, utilities, and other employees' wages stay deducted here - they are NOT added back to SDE/EBITDA, since a buyer will keep paying them too.</p>
<label>Cost of goods sold / COGS ($/yr - inventory or materials cost, if applicable)</label><input type="number" id="bv_cogs" value="400000" oninput="updateComputedNetProfitDisplay()">
<label>Rent ($/yr)</label><input type="number" id="bv_rent" value="60000" oninput="updateComputedNetProfitDisplay()">
<label>Utilities ($/yr)</label><input type="number" id="bv_utilities" value="12000" oninput="updateComputedNetProfitDisplay()">
<label>Advertising / marketing ($/yr)</label><input type="number" id="bv_advertising" value="15000" oninput="updateComputedNetProfitDisplay()">
<label>Other employees' salaries &amp; wages ($/yr - not the owner's)</label><input type="number" id="bv_othersalaries" value="180000" oninput="updateComputedNetProfitDisplay()">
<label>Insurance ($/yr)</label><input type="number" id="bv_insurance" value="8000" oninput="updateComputedNetProfitDisplay()">
<label>Licenses &amp; permits ($/yr)</label><input type="number" id="bv_licenses" value="2000" oninput="updateComputedNetProfitDisplay()">
<label>Other operating expenses ($/yr)</label><input type="number" id="bv_otheropex" value="13000" oninput="updateComputedNetProfitDisplay()">
<div class="unit-totals">
  Computed net profit before owner comp: <strong id="bv_computed_netprofit">$0.00</strong>
  <button type="button" class="suggest-btn" onclick="useComputedNetProfit()" style="margin-left:10px;">Use This Net Profit &uarr;</button>
</div>

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

<label>FF&amp;E / equipment schedule ($ - list each item included in the sale, e.g. forklift, shelving, POS system)</label>
<div id="bv_ffe_rows"></div>
<button type="button" class="suggest-btn" onclick="addFfeRow()" style="margin-bottom:12px;">+ Add Item</button>
<div class="unit-totals">
  Total FF&amp;E/equipment value: <strong id="bv_ffe_total">$0.00</strong>
  <span style="font-size:11px;color:#888;display:block;margin-top:4px;">Usually already reflected within the SDE/EBITDA multiple, not added again on top - shown here mainly as a reference schedule buyers and lenders typically ask for.</span>
</div>
<input type="hidden" id="bv_ffe" value="0">

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Signage, Website &amp; Other Intangibles</h4>
<label>Value of signage, website, domain name, social media following, customer list, non-compete, etc. ($ - added on top of the business value)</label><input type="number" id="bv_intangibles" value="0">

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Lease (if applicable)</h4>
<label>Remaining lease term (years, 0 if none/owned real estate)</label><input type="number" id="bv_lease_years" value="0" step="0.5">
<label>Is the lease transferable/assignable to a buyer?</label>
<select id="bv_lease_transferable" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="yes" selected>Yes</option>
<option value="no">No</option>
</select>
<label>Current rent under the lease ($/mo)</label><input type="number" id="bv_lease_rent" value="0">
<label>Estimated current market rent for comparable space ($/mo)</label><input type="number" id="bv_lease_market_rent" value="0">
<p class="chart-caption" style="text-align:left;margin:4px 0 0;">If your rent is below current market rent, the lease itself has value to a buyer (a "below-market lease"). If it's at or above market, the lease adds no value here. Capped at 5 years of benefit since projecting further out gets unreliable.</p>

<label>Liabilities the buyer would assume ($ - 0 for a typical asset sale/cash-free-debt-free deal)</label><input type="number" id="bv_liabilities" value="0">
<button onclick="calcBizVal()">Calculate</button>
<div class="result" id="bv_result"></div>
<div class="chart-wrap"><canvas id="bv_chart"></canvas></div>
<p class="chart-caption" id="bv_chart_caption"></p>
</div>

<div class="calc calc-panel" id="panel-lease">
<h3>Car Lease Calculator</h3>
<label>Vehicle type (auto-fills typical residual value % and driving-cost estimates below - all remain editable)</label>
<select id="ls_type" onchange="applyLeaseDefaults()" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="gas" selected>Gasoline</option>
<option value="diesel">Diesel</option>
<option value="hybrid">Hybrid</option>
<option value="electric">Electric (EV)</option>
</select>
<label>MSRP ($ - used to calculate the residual value)</label><input type="number" id="ls_msrp" value="40000">
<label>Negotiated price / capitalized cost ($ - before fees; this is the part you can negotiate)</label><input type="number" id="ls_capcost" value="38000">
<label>Down payment / cap cost reduction ($)</label><input type="number" id="ls_down" value="2000">
<label>Trade-in equity applied ($)</label><input type="number" id="ls_trade" value="0">
<label>Manufacturer lease cash / rebate ($)</label><input type="number" id="ls_rebate" value="0">
<label>Acquisition fee ($ - typically $595-$995, usually rolled into the lease)</label><input type="number" id="ls_acqfee" value="795">
<label>Roll acquisition fee into the lease?</label>
<select id="ls_acqfee_roll" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="yes" selected>Yes - roll it in (most common)</option>
<option value="no">No - pay it at signing</option>
</select>
<div class="field-row">
  <div><label id="ls_residual_label">Residual value (% of MSRP at lease end - national average for this vehicle type, editable)</label><input type="number" id="ls_residual_pct" value="55" step="0.5"></div>
  <button type="button" class="suggest-btn" onclick="applyLeaseDefaults()">Use Nat'l Avg</button>
</div>
<p class="chart-caption" id="ls_residual_hint" style="text-align:left;margin:4px 0 12px;">Gasoline vehicles typically retain 45-60% of MSRP after a 36-month lease; 55% is a reasonable starting point.</p>
<label>Lease term (months - 36 is most common)</label><input type="number" id="ls_term" value="36">
<label>Money factor (e.g. 0.00200 - the lease's "interest rate," shown in this unusual decimal format; the calculator converts it to an equivalent APR for you)</label><input type="number" id="ls_moneyfactor" value="0.00200" step="0.00005">
<label>Sales tax rate (% - this calculator assumes tax on the monthly payment, the method most states use)</label><input type="number" id="ls_tax" value="6.5" step="0.1">
<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Mileage &amp; End-of-Lease</h4>
<label>Annual mileage allowance (miles - 10,000-12,000 is typical)</label><input type="number" id="ls_mileage_allow" value="12000">
<label>Your estimated actual annual mileage (miles - to project any overage cost)</label><input type="number" id="ls_mileage_actual" value="12000">
<label>Overage fee ($ per mile over the allowance - typically $0.15-$0.30)</label><input type="number" id="ls_overage_fee" value="0.25" step="0.01">
<label>Disposition fee ($ - due at lease end if you don't buy the car, typically $350-$500)</label><input type="number" id="ls_dispo_fee" value="395">
<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Estimated Driving Costs (optional, for a fuller monthly picture)</h4>
<div class="field-row">
  <div><label id="ls_fuel_label">Monthly fuel/electricity cost ($ - national average for this vehicle type, editable)</label><input type="number" id="ls_fuel" value="150"></div>
  <button type="button" class="suggest-btn" onclick="applyLeaseDefaults()">Use Nat'l Avg</button>
</div>
<div class="field-row">
  <div><label id="ls_maint_label">Monthly maintenance ($ - national average for this vehicle type, editable)</label><input type="number" id="ls_maint" value="100"></div>
  <button type="button" class="suggest-btn" onclick="applyLeaseDefaults()">Use Nat'l Avg</button>
</div>
<button onclick="calcLease()">Calculate</button>
<div class="result" id="ls_result"></div>
<div class="chart-wrap"><canvas id="ls_chart"></canvas></div>
<p class="chart-caption" id="ls_chart_caption"></p>
</div>

<div class="calc calc-panel" id="panel-boat">
<h3>Boat Financing Calculator</h3>
<label>Boat price ($)</label><input type="number" id="bt_price" value="150000">
<label>Boat length (feet - drives the dockage fee estimate below)</label><input type="number" id="bt_length" value="30">
<label>Down payment ($ - typically 10-20%)</label><input type="number" id="bt_down" value="30000">
<label>Trade-in value ($ - 0 if none)</label><input type="number" id="bt_trade" value="0">
<label>Sales tax (%)</label><input type="number" id="bt_tax" value="6.5" step="0.1">
<label>Dealer / documentation fees ($)</label><input type="number" id="bt_fees" value="500">
<label>Roll tax &amp; fees into the loan?</label>
<select id="bt_roll" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="yes" selected>Yes - finance them (most common)</option>
<option value="no">No - I will pay them in cash</option>
</select>
<label>Interest rate (% per year - marine loans typically run 1-3 points above auto loans; 2026 average is roughly 7-10%)</label><input type="number" id="bt_rate" value="8.0" step="0.01">
<label>Loan term (years - boat loans commonly run 5-20 years, longer than auto loans)</label><input type="number" id="bt_years" value="15">
<label>Estimated annual depreciation (% of price - new boats often lose 10-15% in year 1; 10%/yr is a reasonable blended long-run average, editable)</label><input type="number" id="bt_deprec_rate" value="10" step="0.5">

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Storage / Dockage</h4>
<label>Storage type (auto-fills a typical dockage fee below - all remain editable)</label>
<select id="bt_storage" onchange="applyBoatStorageDefaults()" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="wetslip" selected>Wet slip (marina, priced per foot)</option>
<option value="drystack">Dry stack storage (indoor rack storage)</option>
<option value="trailer">Trailer / driveway storage</option>
</select>
<div class="field-row">
  <div><label id="bt_dockage_label">Wet slip fee ($/foot/month - national average is roughly $30-50/ft, editable)</label><input type="number" id="bt_dockage_rate" value="35" step="1"></div>
  <button type="button" class="suggest-btn" onclick="applyBoatStorageDefaults()">Use Nat'l Avg</button>
</div>
<p class="chart-caption" id="bt_storage_hint" style="text-align:left;margin:4px 0 12px;">Wet slips are typically priced per foot of boat length - a 30ft boat at $35/ft runs about $1,050/month, though location (especially waterfront real estate markets) swings this a lot.</p>

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Insurance &amp; Maintenance</h4>
<div class="field-row">
  <div><label>Insurance (%/yr of boat value - national average is roughly 1-2%, editable)</label><input type="number" id="bt_insurance_pct" value="1.5" step="0.1"></div>
  <button type="button" class="suggest-btn" onclick="document.getElementById('bt_insurance_pct').value=1.5;">Use Nat'l Avg (1.5%)</button>
</div>
<div class="field-row">
  <div><label>Maintenance (%/yr of boat value - the industry "10% rule": budget roughly 10% of the boat's value annually for upkeep, editable)</label><input type="number" id="bt_maint_pct" value="10" step="0.5"></div>
  <button type="button" class="suggest-btn" onclick="document.getElementById('bt_maint_pct').value=10;">Use 10% Rule</button>
</div>
<label>Engine type (affects the engine reserve estimate below)</label>
<select id="bt_engine_type" onchange="applyBoatEngineDefaults()" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="outboard" selected>Outboard</option>
<option value="inboard">Inboard / Sterndrive</option>
</select>
<div class="field-row">
  <div><label id="bt_engine_reserve_label">Major engine repair/replacement reserve ($/mo - optional contingency fund, editable)</label><input type="number" id="bt_engine_reserve" value="138"></div>
  <button type="button" class="suggest-btn" onclick="applyBoatEngineDefaults()">Use Nat'l Avg</button>
</div>
<p class="chart-caption" id="bt_engine_hint" style="text-align:left;margin:4px 0 12px;">A new outboard replacement typically runs $8,000-$25,000; this reserve spreads a mid-range estimate over about 10 years. Optional contingency, not a guaranteed cost - 0 if you'd rather not set anything aside.</p>

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Fuel</h4>
<label>Engine horsepower (HP)</label><input type="number" id="bt_hp" value="300">
<label>Fuel type</label>
<select id="bt_fuel_type" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="gas" selected>Gasoline</option>
<option value="diesel">Diesel</option>
</select>
<label>Estimated hours used per year</label><input type="number" id="bt_hours" value="60">
<label>Fuel price ($/gallon)</label><input type="number" id="bt_fuel_price" value="4.50" step="0.01">
<p class="chart-caption" style="text-align:left;margin:4px 0 12px;">Fuel burn uses the industry-standard estimate: gasoline engines burn about HP &times; 0.1 gallons/hour, diesel about HP &times; 0.055 gallons/hour, both at a 75% average throttle factor.</p>

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Other Annual Costs</h4>
<label>Towing membership - e.g. TowBoatUS ($/yr, national average is roughly $215)</label><input type="number" id="bt_towing" value="215">
<label>Yacht club / marina membership dues ($/yr, 0 if none)</label><input type="number" id="bt_club" value="0">
<label>Winterization / haul-out &amp; spring commissioning ($/yr, 0 in year-round warm climates)</label><input type="number" id="bt_winterize" value="0">
<label>Registration / licensing fees ($/yr)</label><input type="number" id="bt_registration" value="150">
<label>Your gross annual household income ($ - optional, for the "10% rule" affordability sanity check)</label><input type="number" id="bt_income" value="0">

<button onclick="calcBoat()">Calculate</button>
<div class="result" id="bt_result"></div>
<div class="chart-wrap"><canvas id="bt_chart"></canvas></div>
<p class="chart-caption" id="bt_chart_caption"></p>
</div>

<div class="calc calc-panel" id="panel-rv">
<h3>RV Financing Calculator</h3>
<label>RV type (auto-fills typical loan term, insurance, maintenance, depreciation, and fuel economy below - all remain editable)</label>
<select id="rv_type" onchange="applyRVDefaults()" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="travel_trailer" selected>Travel Trailer (towable)</option>
<option value="fifth_wheel">Fifth Wheel (towable)</option>
<option value="classB">Class B - Camper Van (motorized)</option>
<option value="classC">Class C Motorhome (motorized)</option>
<option value="classA_gas">Class A Motorhome - Gas (motorized)</option>
<option value="classA_diesel">Class A Motorhome - Diesel Pusher (motorized)</option>
</select>
<p class="chart-caption" id="rv_type_hint" style="text-align:left;margin:4px 0 12px;">Travel trailers are towable (no engine of their own), the most affordable RV type to insure and maintain, and typically depreciate somewhat less steeply than motorized RVs.</p>
<label>RV price ($)</label><input type="number" id="rv_price" value="45000">
<label>Down payment ($ - typically 10-20%)</label><input type="number" id="rv_down" value="6000">
<label>Trade-in value ($ - 0 if none)</label><input type="number" id="rv_trade" value="0">
<label>Sales tax (%)</label><input type="number" id="rv_tax" value="6.5" step="0.1">
<label>Dealer / documentation fees ($)</label><input type="number" id="rv_fees" value="500">
<label>Roll tax &amp; fees into the loan?</label>
<select id="rv_roll" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="yes" selected>Yes - finance them (most common)</option>
<option value="no">No - I will pay them in cash</option>
</select>
<label>Interest rate (% per year - 2026 RV loans typically run roughly 7-10%)</label><input type="number" id="rv_rate" value="7.5" step="0.01">
<label>Loan term (years - national average by RV type, editable)</label><input type="number" id="rv_years" value="12">
<label>Estimated annual depreciation (% of price - national average by RV type, editable; new RVs commonly lose 20-30% in year 1 alone)</label><input type="number" id="rv_deprec_rate" value="15" step="0.5">

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Storage (When Not in Use)</h4>
<label>Storage type</label>
<select id="rv_storage" onchange="applyRVStorageDefaults()" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="home" selected>Home / driveway (free)</option>
<option value="outdoor">Outdoor storage lot</option>
<option value="indoor">Indoor storage</option>
</select>
<label>Storage fee ($/month, editable)</label><input type="number" id="rv_storage_fee" value="0">

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Insurance &amp; Maintenance</h4>
<div class="field-row">
  <div><label id="rv_insurance_label">Insurance (%/yr of RV value - national average by type, editable)</label><input type="number" id="rv_insurance_pct" value="1.3" step="0.1"></div>
  <button type="button" class="suggest-btn" onclick="applyRVDefaults()">Use Nat'l Avg</button>
</div>
<div class="field-row">
  <div><label id="rv_maint_label">Maintenance (%/yr of RV value - national average by type, editable)</label><input type="number" id="rv_maint_pct" value="3" step="0.5"></div>
  <button type="button" class="suggest-btn" onclick="applyRVDefaults()">Use Nat'l Avg</button>
</div>

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Fuel (Motorized RVs Only)</h4>
<p class="chart-caption" id="rv_fuel_note" style="text-align:left;margin:0 0 8px;">Towable RVs have no engine of their own - fuel costs apply to your tow vehicle, not included here.</p>
<label id="rv_mpg_label">Fuel economy (MPG - national average by type, editable)</label><input type="number" id="rv_mpg" value="8" step="0.5">
<label>Miles driven per year</label><input type="number" id="rv_miles" value="5000">
<label>Fuel price ($/gallon)</label><input type="number" id="rv_fuel_price" value="3.75" step="0.01">

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Camping &amp; Other Annual Costs</h4>
<label>Nights camped/traveled per year</label><input type="number" id="rv_nights" value="20">
<label>Average campground fee ($/night)</label><input type="number" id="rv_camp_fee" value="45">
<label>Propane &amp; generator fuel ($/month)</label><input type="number" id="rv_propane" value="30">
<label>Roadside assistance / RV club membership ($/yr - e.g. Good Sam, Coach-Net)</label><input type="number" id="rv_roadside" value="120">
<label>Registration / licensing fees ($/yr)</label><input type="number" id="rv_registration" value="200">
<label>Your gross annual household income ($ - optional, for an affordability sanity check)</label><input type="number" id="rv_income" value="0">

<button onclick="calcRV()">Calculate</button>
<div class="result" id="rv_result"></div>
<div class="chart-wrap"><canvas id="rv_chart"></canvas></div>
<p class="chart-caption" id="rv_chart_caption"></p>
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
function updateComputedNetProfitDisplay() {
  var revenue = +document.getElementById("bv_revenue").value || 0;
  var cogs = +document.getElementById("bv_cogs").value || 0;
  var rent = +document.getElementById("bv_rent").value || 0;
  var utilities = +document.getElementById("bv_utilities").value || 0;
  var advertising = +document.getElementById("bv_advertising").value || 0;
  var othersal = +document.getElementById("bv_othersalaries").value || 0;
  var insurance = +document.getElementById("bv_insurance").value || 0;
  var licenses = +document.getElementById("bv_licenses").value || 0;
  var otheropex = +document.getElementById("bv_otheropex").value || 0;
  var computed = revenue - cogs - rent - utilities - advertising - othersal - insurance - licenses - otheropex;
  document.getElementById("bv_computed_netprofit").textContent = money(computed);
  return computed;
}
function useComputedNetProfit() {
  var computed = updateComputedNetProfitDisplay();
  document.getElementById("bv_netprofit").value = Math.round(computed);
}
var bvFfeRowSeq = 0;
function addFfeRow(label, value) {
  label = label !== undefined ? label : "";
  value = value !== undefined ? value : 1000;
  bvFfeRowSeq++;
  var id = "bv_ffe_row_" + bvFfeRowSeq;
  var safeLabel = String(label).replace(/&/g, "&amp;").replace(/'/g, "&#39;");
  var html = "<div class='unit-row' id='" + id + "'>" +
    "<input type='text' placeholder='e.g. Forklift' value='" + safeLabel + "' oninput='updateFfeTotals()'>" +
    "<input type='number' value='" + value + "' min='0' oninput='updateFfeTotals()' title='Fair market value ($)'>" +
    "<span class='row-subtotal' id='" + id + "_sub'></span>" +
    "<button type='button' class='row-remove' onclick='removeFfeRow(&#39;" + id + "&#39;)'>Remove</button>" +
    "</div>";
  document.getElementById("bv_ffe_rows").insertAdjacentHTML("beforeend", html);
  updateFfeTotals();
}
function removeFfeRow(id) {
  var el = document.getElementById(id);
  if (el) el.remove();
  updateFfeTotals();
}
function updateFfeTotals() {
  var rows = document.querySelectorAll("#bv_ffe_rows .unit-row");
  var total = 0;
  rows.forEach(function(row) {
    var inputs = row.querySelectorAll("input");
    var val = +inputs[1].value || 0;
    total += val;
    var subEl = document.getElementById(row.id + "_sub");
    if (subEl) subEl.textContent = money(val);
  });
  document.getElementById("bv_ffe_total").textContent = money(total);
  document.getElementById("bv_ffe").value = total;
}
addFfeRow("Shelving / Fixtures", 15000);
addFfeRow("POS System", 5000);
addFfeRow("Forklift", 12000);
updateComputedNetProfitDisplay();
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
  var intangibles = +document.getElementById("bv_intangibles").value || 0;
  var liabilities = +document.getElementById("bv_liabilities").value || 0;

  var leaseYears = +document.getElementById("bv_lease_years").value || 0;
  var leaseTransferable = document.getElementById("bv_lease_transferable").value === "yes";
  var leaseRent = +document.getElementById("bv_lease_rent").value || 0;
  var leaseMarketRent = +document.getElementById("bv_lease_market_rent").value || 0;
  var leaseBenefitYears = Math.min(leaseYears, 5);
  var leaseValue = 0;
  if (leaseTransferable && leaseYears > 0 && leaseMarketRent > 0) {
    leaseValue = (leaseMarketRent - leaseRent) * 12 * leaseBenefitYears;
  }

  if (cashFlow <= 0) {
    show("bv_result", "Check your inputs - net profit plus add-backs must be greater than zero to produce a valuation.");
    return;
  }

  var valLow = cashFlow * multLow;
  var valMid = cashFlow * multMid;
  var valHigh = cashFlow * multHigh;
  var extras = inventory + intangibles + leaseValue - liabilities;
  var totalLow = valLow + extras;
  var totalMid = valMid + extras;
  var totalHigh = valHigh + extras;

  var margin = revenue > 0 ? (cashFlow / revenue * 100) : 0;
  var revMultLow = revenue > 0 ? totalLow / revenue : 0;
  var revMultHigh = revenue > 0 ? totalHigh / revenue : 0;

  var leaseLine = "";
  if (leaseYears > 0) {
    if (!leaseTransferable) {
      leaseLine = "Lease: non-transferable, so no lease value added for a buyer.<br>";
    } else if (leaseMarketRent <= 0) {
      leaseLine = "Lease: enter an estimated market rent to value a below/above-market lease.<br>";
    } else if (leaseValue > 0) {
      leaseLine = "+ Below-market lease value (" + money(leaseMarketRent - leaseRent) + "/mo &times; 12 &times; " + leaseBenefitYears.toFixed(1) + " yrs, capped at 5 yrs): " + money(leaseValue) + "<br>";
    } else if (leaseValue < 0) {
      leaseLine = "- Above-market lease discount (" + money(leaseRent - leaseMarketRent) + "/mo over market &times; 12 &times; " + leaseBenefitYears.toFixed(1) + " yrs, capped at 5 yrs): " + money(-leaseValue) + "<br>";
    } else {
      leaseLine = "Lease: at market rate, no added value.<br>";
    }
  }

  show("bv_result",
    cashFlowLabel + " (annual): <strong>" + money(cashFlow) + "</strong> (" + margin.toFixed(1) + "% of revenue)<br>" +
    (method === "sde" ? "&nbsp;&nbsp;EBITDA for reference: " + money(ebitda) + "<br>" : "&nbsp;&nbsp;SDE for reference: " + money(sde) + "<br>") +
    "<br><u>Estimated Business Value (before inventory/intangibles/lease)</u><br>" +
    "Low (" + multLow.toFixed(1) + "x): " + money(valLow) + " &nbsp;|&nbsp; Mid (" + multMid.toFixed(1) + "x): <strong>" + money(valMid) + "</strong> &nbsp;|&nbsp; High (" + multHigh.toFixed(1) + "x): " + money(valHigh) + "<br>" +
    "<br>" +
    (inventory > 0 ? "+ Inventory at cost: " + money(inventory) + "<br>" : "") +
    (intangibles > 0 ? "+ Signage/website/intangibles: " + money(intangibles) + "<br>" : "") +
    leaseLine +
    (liabilities > 0 ? "- Liabilities assumed: " + money(liabilities) + "<br>" : "") +
    "<br><u>Total Estimated Value Range</u><br>" +
    "Low: " + money(totalLow) + " &nbsp;|&nbsp; Mid: <strong>" + money(totalMid) + "</strong> &nbsp;|&nbsp; High: " + money(totalHigh) + "<br>" +
    "<span style='font-size:11px;color:#888;'>Implied revenue multiple: " + revMultLow.toFixed(2) + "x-" + revMultHigh.toFixed(2) + "x of annual revenue (sanity check - Main Street businesses commonly sell for roughly 0.3x-1x revenue depending on margin).</span><br><br>" +
    (ffe > 0 ? "FF&amp;E/equipment schedule (reference - usually already included within the multiple, not added again): " + money(ffe) + "<br><br>" : "") +
    "<span style='font-size:11px;color:#888;'>This is a starting-point estimate using the market (multiple) approach, the standard method for valuing small and mid-sized businesses. Actual sale price depends heavily on factors this calculator can't see: customer concentration, owner dependency, growth trend, lease terms, competitive moat, and buyer type. The overall Main Street average is roughly 2.6-2.7x SDE (2026) across all industries - your multiple should reflect where your business sits within its category's range. Verify add-backs carefully; inflated or undocumented add-backs are the most common source of valuation disputes. The lease value estimate is a simplified, undiscounted rule of thumb, not a formal appraisal of leasehold value. This is not a substitute for a professional business appraisal or a broker's opinion of value.</span>");

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

var LEASE_RESIDUAL_DEFAULTS = {
  gas:      { residual: 55, hint: "Gasoline vehicles typically retain 45-60% of MSRP after a 36-month lease; 55% is a reasonable starting point." },
  diesel:   { residual: 58, hint: "Diesel vehicles (mostly trucks) tend to hold value well due to strong used-truck demand, often residualizing 55-65% at 36 months." },
  hybrid:   { residual: 56, hint: "Hybrids often residualize similarly to, or slightly better than, gas equivalents given steady demand for fuel efficiency." },
  electric: { residual: 52, hint: "EV residuals have historically been weaker and more volatile than gas, though they've stabilized in 2026 as used-EV values leveled off - strong models (e.g. Hyundai Ioniq 6, Kia EV6) now post 58-62%, while others lag well below 50%. Verify your specific model's residual with the leasing company." }
};
function applyLeaseDefaults() {
  var type = document.getElementById("ls_type").value;
  var r = LEASE_RESIDUAL_DEFAULTS[type] || LEASE_RESIDUAL_DEFAULTS.gas;
  document.getElementById("ls_residual_pct").value = r.residual;
  document.getElementById("ls_residual_hint").textContent = r.hint;
  var vd = (typeof VEHICLE_DEFAULTS !== "undefined" && VEHICLE_DEFAULTS[type]) ? VEHICLE_DEFAULTS[type] : { fuel: 150, maint: 100, fuelLabel: "Fuel" };
  document.getElementById("ls_fuel").value = vd.fuel;
  document.getElementById("ls_maint").value = vd.maint;
  document.getElementById("ls_fuel_label").textContent = "Monthly " + vd.fuelLabel.toLowerCase() + " cost ($ - national average for this vehicle type, editable)";
}
function calcLease() {
  var msrp = +document.getElementById("ls_msrp").value || 0;
  var capCost = +document.getElementById("ls_capcost").value || 0;
  var down = +document.getElementById("ls_down").value || 0;
  var trade = +document.getElementById("ls_trade").value || 0;
  var rebate = +document.getElementById("ls_rebate").value || 0;
  var acqFee = +document.getElementById("ls_acqfee").value || 0;
  var rollAcqFee = document.getElementById("ls_acqfee_roll").value === "yes";
  var residualPct = (+document.getElementById("ls_residual_pct").value || 0) / 100;
  var term = +document.getElementById("ls_term").value || 0;
  var moneyFactor = +document.getElementById("ls_moneyfactor").value || 0;
  var taxRate = (+document.getElementById("ls_tax").value || 0) / 100;
  var mileageAllow = +document.getElementById("ls_mileage_allow").value || 0;
  var mileageActual = +document.getElementById("ls_mileage_actual").value || 0;
  var overageFee = +document.getElementById("ls_overage_fee").value || 0;
  var dispoFee = +document.getElementById("ls_dispo_fee").value || 0;
  var fuel_m = +document.getElementById("ls_fuel").value || 0;
  var maint_m = +document.getElementById("ls_maint").value || 0;

  if (capCost <= 0 || term <= 0 || msrp <= 0) {
    show("ls_result", "Check your inputs - MSRP, capitalized cost, and lease term must all be greater than zero.");
    return;
  }

  var residualValue = msrp * residualPct;
  var capReductions = down + trade + rebate;
  var adjustedCapCost = capCost + (rollAcqFee ? acqFee : 0) - capReductions;

  var deprFee = (adjustedCapCost - residualValue) / term;
  var rentCharge = (adjustedCapCost + residualValue) * moneyFactor;
  var basePayment = deprFee + rentCharge;
  var taxAmount = basePayment * taxRate;
  var totalPayment = basePayment + taxAmount;
  var apr = moneyFactor * 2400;

  var cashDueAtSigning = down + (rollAcqFee ? 0 : acqFee) + totalPayment;
  var totalOfPayments = totalPayment * term;
  var totalLeaseCost = totalOfPayments + cashDueAtSigning - totalPayment;

  var termYears = term / 12;
  var mileageOverageMiles = Math.max(mileageActual - mileageAllow, 0) * termYears;
  var mileageOverageCost = mileageOverageMiles * overageFee;

  var onePctBenchmark = msrp * 0.01;
  var benchmarkNote = basePayment <= onePctBenchmark * 1.05
    ? "At or below the rough 1%-of-MSRP rule of thumb for a competitive lease payment."
    : "Above the rough 1%-of-MSRP rule of thumb (" + money(onePctBenchmark) + "/mo) for a competitive lease payment - worth shopping around or negotiating the cap cost.";

  var trueMonthlyCost = totalPayment + fuel_m + maint_m;

  show("ls_result",
    "Residual value: <strong>" + money(residualValue) + "</strong> (" + (residualPct*100).toFixed(1) + "% of " + money(msrp) + " MSRP)<br>" +
    "Adjusted capitalized cost: " + money(adjustedCapCost) + "<br>" +
    "<br><u>Monthly Payment</u><br>" +
    "&nbsp;&nbsp;Depreciation fee: " + money(deprFee) + "/mo<br>" +
    "&nbsp;&nbsp;Rent charge (finance fee): " + money(rentCharge) + "/mo<br>" +
    "&nbsp;&nbsp;Sales tax (" + (taxRate*100).toFixed(1) + "%): " + money(taxAmount) + "/mo<br>" +
    "Total monthly payment: <strong>" + money(totalPayment) + "</strong><br>" +
    "<span style='font-size:11px;color:#888;'>Equivalent APR: " + apr.toFixed(2) + "% (money factor &times; 2400). " + benchmarkNote + "</span><br>" +
    "<br><u>Cash Due at Signing (estimate)</u><br>" +
    "Down payment: " + money(down) + (rollAcqFee ? "" : " + acquisition fee: " + money(acqFee)) + " + first month's payment: " + money(totalPayment) + " = <strong>" + money(cashDueAtSigning) + "</strong><br>" +
    "<br><u>Total Cost Over the Lease</u><br>" +
    "Total of " + term + " monthly payments: " + money(totalOfPayments) + "<br>" +
    "Plus due at signing (excluding the 1st month already counted above): " + money(cashDueAtSigning - totalPayment) + "<br>" +
    "Total estimated lease cost: <strong>" + money(totalLeaseCost) + "</strong><br>" +
    "<br><u>Mileage &amp; End of Lease</u><br>" +
    (mileageOverageMiles > 0
      ? "<span style='color:#c0392b;'>Projected mileage overage: " + Math.round(mileageOverageMiles) + " miles &times; " + money(overageFee) + "/mi = " + money(mileageOverageCost) + " due at lease end</span><br>"
      : "Your estimated mileage is within the allowance - no projected overage.<br>") +
    "Disposition fee (if not buying the car): " + money(dispoFee) + "<br>" +
    "Approximate buyout price if you purchase at lease end: residual (" + money(residualValue) + ") plus any purchase-option fee your contract specifies<br>" +
    "<br><u>Estimated True Monthly Cost of Driving</u><br>" +
    "Lease payment + fuel/electricity + maintenance: <strong>" + money(trueMonthlyCost) + "</strong><br>" +
    "<span style='font-size:11px;color:#888;'>This is a standard lease payment estimate (depreciation + rent charge + tax), the same formula lenders use. Actual dealer quotes can vary based on lender-specific fees, regional taxes taxed on the full cap cost instead of the payment, and manufacturer-subsidized (subvented) money factors or residuals that beat the market rate. Always get the money factor and residual in writing before signing - a low advertised payment can hide a high money factor offset by a large down payment.</span>");

  var chartLabels = ["Depreciation Fee", "Rent Charge (Finance Fee)"];
  var chartValues = [deprFee, rentCharge];
  if (taxAmount > 0) { chartLabels.push("Tax"); chartValues.push(taxAmount); }
  drawPie("ls_chart", "ls_chart_caption", chartLabels, chartValues, "Where your " + money(totalPayment) + "/mo lease payment goes");
}

var BOAT_STORAGE_DEFAULTS = {
  wetslip: { rate: 35, label: "Wet slip fee ($/foot/month - national average is roughly $30-50/ft, editable)",
             hint: "Wet slips are typically priced per foot of boat length - a 30ft boat at $35/ft runs about $1,050/month, though location (especially waterfront real estate markets) swings this a lot." },
  drystack: { rate: 275, label: "Dry stack storage fee ($/month, flat rate - national average is roughly $150-400/month, editable)",
              hint: "Dry stack (indoor rack) storage is usually a flat monthly rate rather than priced per foot, and often includes launch/retrieval service." },
  trailer: { rate: 75, label: "Trailer / driveway storage cost ($/month, flat rate - national average is roughly $50-100/month, editable)",
             hint: "Trailering your own boat is the cheapest storage option, though it adds tow-vehicle wear and launch/retrieval time." }
};
function applyBoatStorageDefaults() {
  var type = document.getElementById("bt_storage").value;
  var d = BOAT_STORAGE_DEFAULTS[type] || BOAT_STORAGE_DEFAULTS.wetslip;
  document.getElementById("bt_dockage_rate").value = d.rate;
  document.getElementById("bt_dockage_label").textContent = d.label;
  document.getElementById("bt_storage_hint").textContent = d.hint;
}
var BOAT_ENGINE_DEFAULTS = {
  outboard: { reserve: 138, hint: "A new outboard replacement typically runs $8,000-$25,000; this reserve spreads a mid-range estimate over about 10 years. Optional contingency, not a guaranteed cost - 0 if you'd rather not set anything aside." },
  inboard:  { reserve: 83,  hint: "An inboard/sterndrive overhaul typically runs $5,000-$15,000; this reserve spreads a mid-range estimate over about 10 years. Optional contingency, not a guaranteed cost - 0 if you'd rather not set anything aside." }
};
function applyBoatEngineDefaults() {
  var type = document.getElementById("bt_engine_type").value;
  var d = BOAT_ENGINE_DEFAULTS[type] || BOAT_ENGINE_DEFAULTS.outboard;
  document.getElementById("bt_engine_reserve").value = d.reserve;
  document.getElementById("bt_engine_hint").textContent = d.hint;
}
function calcBoat() {
  var price = +document.getElementById("bt_price").value;
  var length = +document.getElementById("bt_length").value || 0;
  var down = +document.getElementById("bt_down").value || 0;
  var trade = +document.getElementById("bt_trade").value || 0;
  var taxPct = (+document.getElementById("bt_tax").value || 0) / 100;
  var fees = +document.getElementById("bt_fees").value || 0;
  var roll = document.getElementById("bt_roll").value === "yes";
  var rate = +document.getElementById("bt_rate").value / 100 / 12;
  var n = (+document.getElementById("bt_years").value || 0) * 12;
  var deprecRate = (+document.getElementById("bt_deprec_rate").value || 0) / 100;

  var storageType = document.getElementById("bt_storage").value;
  var dockageRate = +document.getElementById("bt_dockage_rate").value || 0;
  var dockage_m = storageType === "wetslip" ? dockageRate * length : dockageRate;

  var insurancePct = (+document.getElementById("bt_insurance_pct").value || 0) / 100;
  var maintPct = (+document.getElementById("bt_maint_pct").value || 0) / 100;
  var engineReserve_m = +document.getElementById("bt_engine_reserve").value || 0;
  var insurance_m = price * insurancePct / 12;
  var maint_m = price * maintPct / 12;
  var deprec_m = price * deprecRate / 12;

  var hp = +document.getElementById("bt_hp").value || 0;
  var fuelType = document.getElementById("bt_fuel_type").value;
  var hours = +document.getElementById("bt_hours").value || 0;
  var fuelPrice = +document.getElementById("bt_fuel_price").value || 0;
  var gph = fuelType === "diesel" ? hp * 0.055 : hp * 0.1;
  var annualGallons = gph * 0.75 * hours;
  var fuel_m = (annualGallons * fuelPrice) / 12;

  var towing_m = (+document.getElementById("bt_towing").value || 0) / 12;
  var club_m = (+document.getElementById("bt_club").value || 0) / 12;
  var winterize_m = (+document.getElementById("bt_winterize").value || 0) / 12;
  var registration_m = (+document.getElementById("bt_registration").value || 0) / 12;
  var income = +document.getElementById("bt_income").value || 0;

  var taxable = Math.max(price - trade, 0);
  var tax = taxable * taxPct;
  var loan = price - down - trade + (roll ? tax + fees : 0);
  var cashUpfront = down + (roll ? 0 : tax + fees);

  if (loan <= 0 || n <= 0) { show("bt_result", "Check your inputs."); return; }
  var pmt = rate > 0 ? loan * rate / (1 - Math.pow(1 + rate, -n)) : loan / n;
  var totalLoanPaid = pmt * n;

  var trueCost = pmt + dockage_m + insurance_m + maint_m + engineReserve_m + fuel_m + towing_m + club_m + winterize_m + registration_m + deprec_m;
  var annualCost = trueCost * 12;

  var incomeNote = "";
  if (income > 0) {
    var pctOfIncome = (annualCost / income) * 100;
    incomeNote = "<br><span style='font-size:11px;color:#888;'>All-in annual boating cost is " + pctOfIncome.toFixed(1) + "% of your household income. The commonly cited affordability guideline is to keep total boating costs under roughly 10% of gross household income.</span>";
  }

  show("bt_result",
    "Monthly loan payment: <strong>" + money(pmt) + "</strong><br>" +
    "Loan amount: " + money(loan) + "<br>" +
    "&nbsp;&nbsp;Boat price: " + money(price) + "<br>" +
    (trade > 0 ? "&nbsp;&nbsp;Trade-in: -" + money(trade) + "<br>" : "") +
    (down > 0 ? "&nbsp;&nbsp;Down payment: -" + money(down) + "<br>" : "") +
    (tax > 0 ? "&nbsp;&nbsp;Sales tax (" + (taxPct*100).toFixed(1) + "%): +" + money(tax) + (roll ? " (financed)" : " (paid in cash)") + "<br>" : "") +
    (fees > 0 ? "&nbsp;&nbsp;Dealer/doc fees: +" + money(fees) + (roll ? " (financed)" : " (paid in cash)") + "<br>" : "") +
    "Cash due upfront: " + money(cashUpfront) + "<br>" +
    "Total interest over the loan: " + money(totalLoanPaid - loan) + "<br>" +
    "<br><u>Estimated True Monthly Cost of Ownership: <strong>" + money(trueCost) + "</strong></u><br>" +
    "&nbsp;&nbsp;Loan payment: " + money(pmt) + "<br>" +
    "&nbsp;&nbsp;Dockage/storage: " + money(dockage_m) + (storageType === "wetslip" ? " (" + length + "ft &times; " + money(dockageRate) + "/ft)" : "") + "<br>" +
    "&nbsp;&nbsp;Insurance: " + money(insurance_m) + "<br>" +
    "&nbsp;&nbsp;Maintenance: " + money(maint_m) + "<br>" +
    (engineReserve_m > 0 ? "&nbsp;&nbsp;Engine reserve: " + money(engineReserve_m) + "<br>" : "") +
    "&nbsp;&nbsp;Fuel (" + Math.round(annualGallons) + " gal/yr est.): " + money(fuel_m) + "<br>" +
    "&nbsp;&nbsp;Towing membership: " + money(towing_m) + "<br>" +
    (club_m > 0 ? "&nbsp;&nbsp;Club/marina dues: " + money(club_m) + "<br>" : "") +
    (winterize_m > 0 ? "&nbsp;&nbsp;Winterization: " + money(winterize_m) + "<br>" : "") +
    "&nbsp;&nbsp;Registration: " + money(registration_m) + "<br>" +
    "&nbsp;&nbsp;Depreciation (non-cash, for reference): " + money(deprec_m) + "<br>" +
    "<br>Annual all-in cost: <strong>" + money(annualCost) + "</strong>" + incomeNote +
    "<br><br><span style='font-size:11px;color:#888;'>Industry rule of thumb: total boating costs commonly run 2-3x the loan payment alone once dockage, insurance, maintenance, and fuel are added - this is normal, not a sign something's wrong with your numbers. The 10% maintenance rule and 1-2% insurance rule are broad averages; actual costs vary a lot by boat age, engine type, and how hard the boat is used. This is an estimate, not a substitute for actual quotes from your marina, insurer, and mechanic.</span>");

  var chartLabels = ["Loan Payment", "Dockage/Storage", "Insurance", "Maintenance"];
  var chartValues = [pmt, dockage_m, insurance_m, maint_m];
  if (engineReserve_m > 0) { chartLabels.push("Engine Reserve"); chartValues.push(engineReserve_m); }
  chartLabels.push("Fuel"); chartValues.push(fuel_m);
  var otherFixed_m = towing_m + club_m + winterize_m + registration_m;
  if (otherFixed_m > 0) { chartLabels.push("Other Fees"); chartValues.push(otherFixed_m); }
  chartLabels.push("Depreciation"); chartValues.push(deprec_m);
  drawPie("bt_chart", "bt_chart_caption", chartLabels, chartValues, "True monthly cost of ownership: " + money(trueCost));
}

var RV_TYPE_DEFAULTS = {
  travel_trailer: { motorized: false, insurance: 1.3, maint: 3.0,  deprec: 15, years: 12, mpg: null,
    hint: "Travel trailers are towable (no engine of their own), the most affordable RV type to insure and maintain, and typically depreciate somewhat less steeply than motorized RVs." },
  fifth_wheel: { motorized: false, insurance: 1.1, maint: 3.5,  deprec: 15, years: 15, mpg: null,
    hint: "Fifth wheels are also towable and generally cheaper to insure and maintain than motorhomes, though larger and pricier than a typical travel trailer, needing a pickup with a bed-mounted hitch." },
  classB: { motorized: true, insurance: 1.1, maint: 4.0, deprec: 18, years: 10, mpg: 18, fuelPrice: 3.75,
    hint: "Class B camper vans are built on a van chassis - better fuel economy than larger motorhomes, moderate insurance and maintenance costs, but a smaller price tag also means less room to spread depreciation." },
  classC: { motorized: true, insurance: 1.2, maint: 4.5, deprec: 18, years: 15, mpg: 10, fuelPrice: 3.75,
    hint: "Class C motorhomes (built on a truck/van cutaway chassis) sit between Class B and Class A on cost, insurance, and fuel economy." },
  classA_gas: { motorized: true, insurance: 0.8, maint: 5.0, deprec: 20, years: 15, mpg: 7, fuelPrice: 3.75,
    hint: "Class A gas motorhomes are large, comfortable, and driveable, but among the least fuel-efficient RVs and among the steepest depreciators." },
  classA_diesel: { motorized: true, insurance: 1.3, maint: 6.0, deprec: 18, years: 20, mpg: 9, fuelPrice: 4.10,
    hint: "Class A diesel pushers ('diesel pushers') cost the most to insure and maintain due to their complex engines and high values, but tend to hold value somewhat better than gas Class A models and get better fuel economy." }
};
function applyRVDefaults() {
  var type = document.getElementById("rv_type").value;
  var d = RV_TYPE_DEFAULTS[type] || RV_TYPE_DEFAULTS.travel_trailer;
  document.getElementById("rv_insurance_pct").value = d.insurance;
  document.getElementById("rv_maint_pct").value = d.maint;
  document.getElementById("rv_deprec_rate").value = d.deprec;
  document.getElementById("rv_years").value = d.years;
  document.getElementById("rv_type_hint").textContent = d.hint;
  if (d.motorized) {
    document.getElementById("rv_mpg").value = d.mpg;
    document.getElementById("rv_fuel_price").value = d.fuelPrice;
    document.getElementById("rv_fuel_note").textContent = "Motorized RV - fuel cost is estimated from the MPG and miles below.";
  } else {
    document.getElementById("rv_fuel_note").textContent = "Towable RVs have no engine of their own - fuel costs apply to your tow vehicle, not included here.";
  }
}
var RV_STORAGE_DEFAULTS = { home: 0, outdoor: 100, indoor: 225 };
function applyRVStorageDefaults() {
  var type = document.getElementById("rv_storage").value;
  document.getElementById("rv_storage_fee").value = RV_STORAGE_DEFAULTS[type] !== undefined ? RV_STORAGE_DEFAULTS[type] : 0;
}
function calcRV() {
  var type = document.getElementById("rv_type").value;
  var typeDefaults = RV_TYPE_DEFAULTS[type] || RV_TYPE_DEFAULTS.travel_trailer;
  var isMotorized = typeDefaults.motorized;
  var price = +document.getElementById("rv_price").value;
  var down = +document.getElementById("rv_down").value || 0;
  var trade = +document.getElementById("rv_trade").value || 0;
  var taxPct = (+document.getElementById("rv_tax").value || 0) / 100;
  var fees = +document.getElementById("rv_fees").value || 0;
  var roll = document.getElementById("rv_roll").value === "yes";
  var rate = +document.getElementById("rv_rate").value / 100 / 12;
  var n = (+document.getElementById("rv_years").value || 0) * 12;
  var deprecRate = (+document.getElementById("rv_deprec_rate").value || 0) / 100;

  var storageFee_m = +document.getElementById("rv_storage_fee").value || 0;
  var insurancePct = (+document.getElementById("rv_insurance_pct").value || 0) / 100;
  var maintPct = (+document.getElementById("rv_maint_pct").value || 0) / 100;
  var insurance_m = price * insurancePct / 12;
  var maint_m = price * maintPct / 12;
  var deprec_m = price * deprecRate / 12;

  var mpg = +document.getElementById("rv_mpg").value || 0;
  var miles = +document.getElementById("rv_miles").value || 0;
  var fuelPrice = +document.getElementById("rv_fuel_price").value || 0;
  var fuel_m = (isMotorized && mpg > 0) ? (miles / mpg * fuelPrice) / 12 : 0;

  var nights = +document.getElementById("rv_nights").value || 0;
  var campFee = +document.getElementById("rv_camp_fee").value || 0;
  var camping_m = (nights * campFee) / 12;
  var propane_m = +document.getElementById("rv_propane").value || 0;
  var roadside_m = (+document.getElementById("rv_roadside").value || 0) / 12;
  var registration_m = (+document.getElementById("rv_registration").value || 0) / 12;
  var income = +document.getElementById("rv_income").value || 0;

  var taxable = Math.max(price - trade, 0);
  var tax = taxable * taxPct;
  var loan = price - down - trade + (roll ? tax + fees : 0);
  var cashUpfront = down + (roll ? 0 : tax + fees);

  if (loan <= 0 || n <= 0) { show("rv_result", "Check your inputs."); return; }
  var pmt = rate > 0 ? loan * rate / (1 - Math.pow(1 + rate, -n)) : loan / n;
  var totalLoanPaid = pmt * n;

  var trueCost = pmt + storageFee_m + insurance_m + maint_m + fuel_m + camping_m + propane_m + roadside_m + registration_m + deprec_m;
  var annualCost = trueCost * 12;

  var incomeNote = "";
  if (income > 0) {
    var pctOfIncome = (annualCost / income) * 100;
    incomeNote = "<br><span style='font-size:11px;color:#888;'>All-in annual RV cost is " + pctOfIncome.toFixed(1) + "% of your household income. A common budgeting guideline is to keep total recreational-vehicle costs under roughly 10-15% of gross household income.</span>";
  }

  show("rv_result",
    "Monthly loan payment: <strong>" + money(pmt) + "</strong><br>" +
    "Loan amount: " + money(loan) + "<br>" +
    "&nbsp;&nbsp;RV price: " + money(price) + "<br>" +
    (trade > 0 ? "&nbsp;&nbsp;Trade-in: -" + money(trade) + "<br>" : "") +
    (down > 0 ? "&nbsp;&nbsp;Down payment: -" + money(down) + "<br>" : "") +
    (tax > 0 ? "&nbsp;&nbsp;Sales tax (" + (taxPct*100).toFixed(1) + "%): +" + money(tax) + (roll ? " (financed)" : " (paid in cash)") + "<br>" : "") +
    (fees > 0 ? "&nbsp;&nbsp;Dealer/doc fees: +" + money(fees) + (roll ? " (financed)" : " (paid in cash)") + "<br>" : "") +
    "Cash due upfront: " + money(cashUpfront) + "<br>" +
    "Total interest over the loan: " + money(totalLoanPaid - loan) + "<br>" +
    "<br><u>Estimated True Monthly Cost of Ownership: <strong>" + money(trueCost) + "</strong></u><br>" +
    "&nbsp;&nbsp;Loan payment: " + money(pmt) + "<br>" +
    (storageFee_m > 0 ? "&nbsp;&nbsp;Storage: " + money(storageFee_m) + "<br>" : "") +
    "&nbsp;&nbsp;Insurance: " + money(insurance_m) + "<br>" +
    "&nbsp;&nbsp;Maintenance: " + money(maint_m) + "<br>" +
    (isMotorized ? "&nbsp;&nbsp;Fuel (" + Math.round(miles/Math.max(mpg,0.01)) + " gal/yr est.): " + money(fuel_m) + "<br>" : "&nbsp;&nbsp;Fuel: not applicable (towable RV - see your tow vehicle's costs separately)<br>") +
    "&nbsp;&nbsp;Campground fees (" + nights + " nights/yr): " + money(camping_m) + "<br>" +
    "&nbsp;&nbsp;Propane/generator: " + money(propane_m) + "<br>" +
    "&nbsp;&nbsp;Roadside assistance/club: " + money(roadside_m) + "<br>" +
    "&nbsp;&nbsp;Registration: " + money(registration_m) + "<br>" +
    "&nbsp;&nbsp;Depreciation (non-cash, for reference): " + money(deprec_m) + "<br>" +
    "<br>Annual all-in cost: <strong>" + money(annualCost) + "</strong>" + incomeNote +
    "<br><br><span style='font-size:11px;color:#888;'>New RVs commonly lose 20-30% of value in the first year alone, more than most cars or boats - this calculator uses a blended annual rate rather than that steeper first-year hit, so treat year one as likely worse than shown. Insurance, maintenance, and depreciation percentages are broad industry averages and vary a lot by specific make, model, age, and condition. This is an estimate, not a substitute for actual quotes from your dealer, insurer, and RV service center.</span>");

  var chartLabels = ["Loan Payment"];
  var chartValues = [pmt];
  if (storageFee_m > 0) { chartLabels.push("Storage"); chartValues.push(storageFee_m); }
  chartLabels.push("Insurance"); chartValues.push(insurance_m);
  chartLabels.push("Maintenance"); chartValues.push(maint_m);
  if (fuel_m > 0) { chartLabels.push("Fuel"); chartValues.push(fuel_m); }
  if (camping_m > 0) { chartLabels.push("Campground Fees"); chartValues.push(camping_m); }
  var otherFixed_m = propane_m + roadside_m + registration_m;
  if (otherFixed_m > 0) { chartLabels.push("Other Fees"); chartValues.push(otherFixed_m); }
  chartLabels.push("Depreciation"); chartValues.push(deprec_m);
  drawPie("rv_chart", "rv_chart_caption", chartLabels, chartValues, "True monthly cost of ownership: " + money(trueCost));
}
</script>

</body>
</html>"""

calculators_html = (CALC_TEMPLATE
                    .replace("__CSS__", PAGE_CSS)
                    .replace("__NAV__", NAV_HTML))

# ------------------- PAGE 4: PROPERTY / FORECLOSURE SEARCH -------------------

SEARCH_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Property &amp; Foreclosure Search</title>
<style>__CSS__
.calc { background:#fff; border-radius:10px; padding:18px; border:1px solid #e5e3dc; margin-bottom:20px; max-width:640px; }
.calc h3 { margin:0 0 12px; font-size:16px; }
.calc label { display:block; font-size:12px; color:#666; margin:10px 0 3px; }
.calc input, .calc select { width:100%; padding:8px; font-size:14px; border:1px solid #ccc; border-radius:6px; box-sizing:border-box; }
.calc button { margin-top:14px; padding:10px 18px; font-size:14px; font-weight:600; color:#fff; background:#1f4e79; border:none; border-radius:6px; cursor:pointer; }
.calc button:hover { background:#163a5c; }
.result { margin-top:14px; padding:12px; background:#f0f6ec; border-radius:6px; font-size:14px; display:none; }
.result strong { font-size:15px; }
.calc-tabs { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:20px; }
.calc-tab-btn { padding:10px 16px; border-radius:8px; border:1px solid #e5e3dc; background:#fff; cursor:pointer; font-size:13px; font-weight:600; color:#555; }
.calc-tab-btn:hover { background:#f0efe9; }
.calc-tab-btn.active { background:#1f4e79; color:#fff; border-color:#1f4e79; }
.calc-panel { display:none; }
.calc-panel.active { display:block; }
.setup-banner { background:#fef3c7; border:2px solid #f59e0b; padding:15px; border-radius:10px; margin-bottom:20px; font-size:13px; color:#78350f; }
.setup-banner code { background:#fde68a; padding:2px 5px; border-radius:3px; }
@media (max-width: 600px) {
  body { padding:12px; }
  .calc { padding:14px; max-width:100%; }
  .calc input, .calc select { font-size:16px !important; padding:10px !important; }
  .calc button { width:100%; }
  .calc-tab-btn { flex:1 1 auto; text-align:center; font-size:12px; padding:10px 8px; }
}
</style>
</head>
<body>
__NAV__
<h1>Property &amp; Foreclosure Search</h1>
<p class="timestamp">Live lookups powered by ATTOM Data, via a Cloudflare Worker proxy.</p>

<div class="setup-banner" id="setup-banner">
  <strong>One-time setup:</strong> replace <code>WORKER_URL</code> near the top of this page's script with your own deployed Cloudflare Worker URL (looks like <code>https://attom-proxy.YOUR-SUBDOMAIN.workers.dev</code>) before this will return real results.
</div>

<div class="calc-tabs">
  <button type="button" class="calc-tab-btn active" onclick="showSearchTab('panel-propsearch', this)">Property Search</button>
  <button type="button" class="calc-tab-btn" onclick="showSearchTab('panel-forsearch', this)">Foreclosure Search</button>
</div>

<div class="calc calc-panel active" id="panel-propsearch">
<h3>Property Search</h3>
<label>Full street address (e.g. "123 Main St, Miami, FL 33101")</label>
<input type="text" id="ps_address" placeholder="Street, City, State ZIP">
<button onclick="searchProperty()">Search</button>
<div id="ps_recent" style="margin-top:10px;font-size:12px;"></div>
<div class="result" id="ps_result"></div>
</div>

<div class="calc calc-panel" id="panel-forsearch">
<h3>Foreclosure Search</h3>
<p class="note">This tab isn't wired up yet - ATTOM's foreclosure/preforeclosure data is a separate "Premium Property" product that isn't included in the standard trial. Contact ATTOM (datacustomercare@attomdata.com) to check pricing and enable it on your account; once you have access and the correct endpoint, this section fills in the same way Property Search did.</p>
<label>County</label>
<select id="fs_county">
<option value="miami-dade">Miami-Dade</option>
<option value="broward">Broward</option>
<option value="palm-beach">Palm Beach</option>
</select>
<button onclick="searchForeclosures()">Search</button>
<div class="result" id="fs_result"></div>
</div>

<script>
// Replace this with your own deployed Cloudflare Worker URL (see setup banner above).
var WORKER_URL = "https://attom-proxy.tonyhernandezusa.workers.dev";
if (WORKER_URL.indexOf("YOUR-SUBDOMAIN") === -1) {
  var setupBanner = document.getElementById("setup-banner");
  if (setupBanner) { setupBanner.style.display = "none"; }
}

function showSearchTab(panelId, btn) {
  document.querySelectorAll(".calc-panel").forEach(function(p) { p.classList.remove("active"); });
  document.querySelectorAll(".calc-tab-btn").forEach(function(b) { b.classList.remove("active"); });
  document.getElementById(panelId).classList.add("active");
  btn.classList.add("active");
}

function showResult(id, html) {
  var el = document.getElementById(id);
  el.innerHTML = html;
  el.style.display = "block";
}

function loadRecentSearches() {
  var recentEl = document.getElementById("ps_recent");
  var recent = [];
  try { recent = JSON.parse(localStorage.getItem("recentPropertySearches") || "[]"); } catch (e) { recent = []; }
  if (!recent.length) { recentEl.innerHTML = ""; return; }
  recentEl.innerHTML = "<span style='color:#888;'>Recent:</span> " + recent.map(function(a) {
    return "<a href='#' data-addr='" + a.replace(/'/g, "&#39;") + "' style='color:#1f4e79;margin-right:10px;'>" + a + "</a>";
  }).join("");
  recentEl.querySelectorAll("a").forEach(function(el) {
    el.addEventListener("click", function(e) {
      e.preventDefault();
      var a = el.getAttribute("data-addr");
      document.getElementById("ps_address").value = a;
      searchProperty();
    });
  });
}
function saveRecentSearch(address) {
  var recent = [];
  try { recent = JSON.parse(localStorage.getItem("recentPropertySearches") || "[]"); } catch (e) { recent = []; }
  recent = recent.filter(function(a) { return a.toLowerCase() !== address.toLowerCase(); });
  recent.unshift(address);
  recent = recent.slice(0, 5);
  localStorage.setItem("recentPropertySearches", JSON.stringify(recent));
  loadRecentSearches();
}
loadRecentSearches();

async function searchProperty() {
  var address = document.getElementById("ps_address").value.trim();
  if (!address) { showResult("ps_result", "Enter an address to search."); return; }
  showResult("ps_result", "Searching...");

  try {
    var resp = await fetch(WORKER_URL + "/property-search?address=" + encodeURIComponent(address));
    var data = await resp.json();

    if (data.error) {
      showResult("ps_result", "<strong style='color:#c0392b;'>Error:</strong> " + data.error);
      return;
    }

    var prop = data.property && data.property[0];
    if (!prop) {
      showResult("ps_result", "No property found for that address. Check the spelling/format and try again.");
      return;
    }
    saveRecentSearch(address);

    var addr = prop.address || {};
    var loc = prop.location || {};
    var area = prop.area || {};
    var lot = prop.lot || {};
    var summary = prop.summary || {};
    var utilities = prop.utilities || {};
    var building = prop.building || {};
    var rooms = building.rooms || {};
    var size = building.size || {};
    var interior = building.interior || {};
    var construction = building.construction || {};
    var bldgSummary = building.summary || {};
    var assessment = prop.assessment || {};
    var assessed = assessment.assessed || {};
    var market = assessment.market || {};
    var tax = assessment.tax || {};
    var owner = assessment.owner || {};
    var mortgage = (assessment.mortgage || {}).FirstConcurrent || {};
    var sale = prop.sale || {};
    var saleAmount = sale.amount || {};
    var fullHistory = prop.fullSalesHistory;
    var schoolsRawProp = data.schoolsRaw && data.schoolsRaw.property && data.schoolsRaw.property[0];
    var schoolDistrict = schoolsRawProp ? (schoolsRawProp.schoolDistrict || {}) : {};
    var schoolsList = schoolsRawProp ? schoolsRawProp.school : null;
    var avm = prop.avmDetail || {};
    var avmAmount = avm.amount || {};
    var compsRaw = data.compsRaw;
    var compsError = data.compsError;

    function row(label, value) {
      return value !== undefined && value !== null && value !== "" ? "<strong>" + label + ":</strong> " + value + "<br>" : "";
    }
    function money(n) {
      return (n !== undefined && n !== null && n !== "") ? "$" + Number(n).toLocaleString() : null;
    }

    var mapEmbed = "";
    if (loc.latitude && loc.longitude) {
      mapEmbed = "<iframe src='https://maps.google.com/maps?q=" + loc.latitude + "," + loc.longitude +
        "&z=19&t=k&output=embed' style='width:100%;height:260px;border:0;border-radius:8px;margin-bottom:14px;' loading='lazy'></iframe>";
    }

    var historyHtml = "";
    if (fullHistory && fullHistory.length) {
      historyHtml = "<h4 style='font-size:13px;margin:14px 0 6px;'>Sales History</h4><div class='table-wrap'><table><tr><th>Date</th><th style='text-align:right;'>Amount</th><th>Type</th><th>Buyer/Seller</th></tr>";
      fullHistory.forEach(function(h) {
        var hAmt = h.amount || {};
        historyHtml += "<tr><td>" + (h.saleTransDate || h.saleSearchDate || "N/A") + "</td>" +
          "<td style='text-align:right;'>" + (money(hAmt.saleAmt) || "N/A") + "</td>" +
          "<td>" + (hAmt.saleTransType || "N/A") + "</td>" +
          "<td>" + (h.sellerName || "N/A") + "</td></tr>";
      });
      historyHtml += "</table></div>";
    } else if (saleAmount.saleAmt) {
      historyHtml = "<h4 style='font-size:13px;margin:14px 0 6px;'>Sales History</h4>" +
        row("Most recent sale", (money(saleAmount.saleAmt) || "N/A") + (sale.saleSearchDate ? " on " + sale.saleSearchDate : "")) +
        "<span style='font-size:11px;color:#888;'>Full multi-year history unavailable for this property/account tier - showing most recent sale only.</span>";
    }

    var schoolsHtml = "";
    if (schoolDistrict.districtname || (schoolsList && schoolsList.length)) {
      schoolsHtml = "<h4 style='font-size:13px;margin:14px 0 6px;'>Schools</h4>";
      if (schoolDistrict.districtname) {
        schoolsHtml += "District: " + schoolDistrict.districtname + "<br><br>";
      }
      if (Array.isArray(schoolsList) && schoolsList.length) {
        schoolsHtml += "<div class='table-wrap'><table><tr><th>School</th><th>Grades</th><th>Rating</th><th>Type</th><th style='text-align:right;'>Distance</th></tr>";
        schoolsList.forEach(function(s) {
          schoolsHtml += "<tr><td>" + (s.InstitutionName || "N/A") + "</td>" +
            "<td>" + (s.lowAssignedGrade || "N/A") + "-" + (s.highAssignedGrade || "N/A") + "</td>" +
            "<td>" + (s.schoolRating || "N/A") + "</td>" +
            "<td>" + (s.Filetypetext || "N/A") + "</td>" +
            "<td style='text-align:right;'>" + (s.distance !== undefined ? s.distance + " mi" : "N/A") + "</td></tr>";
        });
        schoolsHtml += "</table></div>";
      }
      schoolsHtml += "<span style='font-size:11px;color:#888;'>School ratings from GreatSchools via ATTOM. Assigned schools reflect attendance boundaries, which can change - verify with the district for enrollment decisions.</span>";
    }

    var avmHtml = "";
    if (avmAmount.value) {
      avmHtml = "<h4 style='font-size:13px;margin:14px 0 6px;'>Automated Valuation (AVM)</h4>" +
        row("Estimated value", money(avmAmount.value)) +
        row("Value range", (money(avmAmount.low) || "N/A") + " - " + (money(avmAmount.high) || "N/A")) +
        row("Confidence score", avmAmount.scr ? avmAmount.scr + "/100" : null) +
        row("As of", avm.eventDate) +
        "<span style='font-size:11px;color:#888;'>An algorithmic estimate, not an appraisal - treat the range, not just the point value, as the honest answer. Confidence score reflects how much comparable data was available.</span>";
    }

    var compsHtml = "";
    var compsList = null;
    try {
      compsList = compsRaw.RESPONSE_GROUP.RESPONSE.RESPONSE_DATA.PROPERTY_INFORMATION_RESPONSE_ext.SUBJECT_PROPERTY_ext.PROPERTY;
    } catch (e) { compsList = null; }
    if (Array.isArray(compsList) && compsList.length) {
      var comps = compsList
        .map(function(p) { return p.COMPARABLE_PROPERTY_ext; })
        .filter(function(c) { return c; });
      if (comps.length) {
        compsHtml = "<h4 style='font-size:13px;margin:14px 0 6px;'>Comparable Sales (" + comps.length + " found)</h4><div class='table-wrap'><table><tr><th>Address</th><th style='text-align:right;'>Distance</th><th style='text-align:right;'>Sale Price</th><th>Sale Date</th><th>Beds/Baths</th><th style='text-align:right;'>Sq Ft</th></tr>";
        comps.forEach(function(c) {
          var sh = c.SALES_HISTORY || {};
          var st = c.STRUCTURE || {};
          var addrStr = (c["@_StreetAddress"] || "N/A") + ", " + (c["@_City"] || "");
          var dist = c["@DistanceFromSubjectPropertyMilesCount"] ? (+c["@DistanceFromSubjectPropertyMilesCount"]).toFixed(2) + " mi" : "N/A";
          compsHtml += "<tr><td>" + addrStr + "</td><td style='text-align:right;'>" + dist + "</td>" +
            "<td style='text-align:right;'>" + (money(sh["@PropertySalesAmount"]) || "N/A") + "</td>" +
            "<td>" + (sh["@TransferDate_ext"] ? sh["@TransferDate_ext"].slice(0, 10) : "N/A") + "</td>" +
            "<td>" + (st["@TotalBedroomCount"] || "N/A") + " / " + (st["@TotalBathroomCount"] || "N/A") + "</td>" +
            "<td style='text-align:right;'>" + (st["@GrossLivingAreaSquareFeetCount"] || "N/A") + "</td></tr>";
        });
        compsHtml += "</table></div>";
      }
    }
    if (!compsHtml && compsError) {
      compsHtml = "<h4 style='font-size:13px;margin:14px 0 6px;'>Comparable Sales</h4><span style='font-size:11px;color:#888;'>Not available right now (" + compsError + "). This is an experimental integration - if you'd like it working, send Claude the raw response your Worker is getting from the comps endpoint and it can be corrected.</span>";
    }

    showResult("ps_result",
      mapEmbed +
      "<strong style='font-size:16px;'>" + (addr.oneLine || addr.line1 || address) + "</strong><br>" +
      "<a href='https://www.zillow.com/homes/" + encodeURIComponent((addr.oneLine || address).replace(/,/g, '')).replace(/%20/g, '-') + "_rb/' target='_blank' style='color:#1f4e79;font-size:12px;'>View on Zillow</a> &nbsp;|&nbsp; " +
      "<a href='https://www.realtor.com/realestateandhomes-search/" + encodeURIComponent((addr.oneLine || address).replace(/,/g, '')).replace(/%20/g, '-') + "' target='_blank' style='color:#1f4e79;font-size:12px;'>View on Realtor.com</a>" +
      "<br><br>" +

      "<h4 style='font-size:13px;margin:0 0 6px;'>Property Details</h4>" +
      row("Type", summary.propType || summary.propClass) +
      row("Land use", summary.propLandUse) +
      row("Year built", summary.yearBuilt) +
      row("Stories", bldgSummary.levels) +
      row("Construction", construction.constructionType) +
      row("Wall type", construction.wallType) +
      row("Flooring", interior.floors) +
      row("View", bldgSummary.view) +
      row("Zoning", lot.zoningType) +
      row("Legal description", summary.legal1) +

      "<h4 style='font-size:13px;margin:14px 0 6px;'>Building</h4>" +
      row("Bedrooms", rooms.beds) +
      row("Bathrooms (full / total)", (rooms.bathsFull || "N/A") + " / " + (rooms.bathsTotal || "N/A")) +
      row("Living area", size.livingSize ? size.livingSize + " sq ft" : null) +
      row("Universal size", size.universalSize ? size.universalSize + " sq ft" : null) +

      "<h4 style='font-size:13px;margin:14px 0 6px;'>Lot</h4>" +
      row("Lot size", lot.lotSize1 ? lot.lotSize1 + " acres (" + (lot.lotSize2 || "N/A") + " sq ft)" : null) +
      row("Frontage / Depth", (lot.frontage || "N/A") + " ft / " + (lot.depth || "N/A") + " ft") +
      row("Subdivision", area.subdName) +
      row("County", area.countrySecSubd) +

      "<h4 style='font-size:13px;margin:14px 0 6px;'>Assessment &amp; Tax</h4>" +
      row("Assessed total value", money(assessed.assdTtlValue)) +
      row("Assessed land value", money(assessed.assdLandValue)) +
      row("Assessed improvement value", money(assessed.assdImprValue)) +
      row("Market total value", money(market.mktTtlValue)) +
      row("Annual property tax", tax.taxAmt ? money(tax.taxAmt) + " (" + (tax.taxYear || "N/A") + ")" : null) +

      "<h4 style='font-size:13px;margin:14px 0 6px;'>Ownership</h4>" +
      row("Owner", (owner.owner1 || {}).fullName) +
      row("Owner type", owner.type) +
      row("Mailing address", owner.mailingAddressOneLine) +
      row("Absentee owner", owner.absenteeOwnerStatus === "A" ? "Yes" : (owner.absenteeOwnerStatus ? "No" : null)) +

      (mortgage.amount ? "<h4 style='font-size:13px;margin:14px 0 6px;'>Most Recent Mortgage</h4>" +
        row("Lender", mortgage.lenderLastName) +
        row("Amount", money(mortgage.amount)) +
        row("Recorded", mortgage.date) +
        row("Term (years)", mortgage.term) +
        row("Due date", mortgage.dueDate) : "") +

      historyHtml +
      avmHtml +
      compsHtml +
      schoolsHtml +

      "<br><span style='font-size:11px;color:#888;'>Data from ATTOM public records. Satellite image via Google Maps, based on the property's coordinates - not an MLS listing photo. Field availability varies by property and county recorder data quality.</span>");
  } catch (err) {
    showResult("ps_result", "<strong style='color:#c0392b;'>Could not reach the search service.</strong> Confirm WORKER_URL is set to your deployed Cloudflare Worker, and that the Worker is running.");
  }
}

async function searchForeclosures() {
  var county = document.getElementById("fs_county").value;
  showResult("fs_result", "Searching...");
  try {
    var resp = await fetch(WORKER_URL + "/foreclosure-search?county=" + encodeURIComponent(county));
    var data = await resp.json();
    showResult("fs_result", data.error ? ("<strong style='color:#c0392b;'>" + data.error + "</strong>") : JSON.stringify(data));
  } catch (err) {
    showResult("fs_result", "<strong style='color:#c0392b;'>Could not reach the search service.</strong>");
  }
}
</script>

</body>
</html>"""

search_html = (SEARCH_TEMPLATE
               .replace("__CSS__", PAGE_CSS)
               .replace("__NAV__", NAV_HTML))

# ------------------- PAGE 5: STOCK SEARCH -------------------

STOCKSEARCH_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stock Search</title>
<style>__CSS__
.calc { background:#fff; border-radius:10px; padding:18px; border:1px solid #e5e3dc; margin-bottom:20px; max-width:640px; }
.calc h3 { margin:0 0 12px; font-size:16px; }
.calc label { display:block; font-size:12px; color:#666; margin:10px 0 3px; }
.calc input { width:100%; padding:8px; font-size:14px; border:1px solid #ccc; border-radius:6px; box-sizing:border-box; }
.calc button { margin-top:14px; padding:10px 18px; font-size:14px; font-weight:600; color:#fff; background:#1f4e79; border:none; border-radius:6px; cursor:pointer; }
.calc button:hover { background:#163a5c; }
.result { margin-top:14px; padding:12px; background:#f0f6ec; border-radius:6px; font-size:14px; display:none; }
.setup-banner { background:#fef3c7; border:2px solid #f59e0b; padding:15px; border-radius:10px; margin-bottom:20px; font-size:13px; color:#78350f; }
.setup-banner code { background:#fde68a; padding:2px 5px; border-radius:3px; }
.ss-dropdown { position:relative; }
.ss-matches { position:absolute; top:100%; left:0; right:0; background:#fff; border:1px solid #ccc; border-top:none; border-radius:0 0 6px 6px; max-height:260px; overflow-y:auto; z-index:10; display:none; }
.ss-match-item { padding:8px 10px; cursor:pointer; font-size:13px; border-bottom:1px solid #eee; }
.ss-match-item:hover { background:#f0f6ec; }
.ss-match-item .ticker { font-weight:600; color:#1f4e79; }
@media (max-width: 600px) {
  body { padding:12px; }
  .calc { padding:14px; max-width:100%; }
  .calc input { font-size:16px !important; padding:10px !important; }
  .calc button { width:100%; }
}
</style>
</head>
<body>
__NAV__
<h1>Stock Search</h1>
<p class="timestamp">Search any U.S. publicly traded company - live data via Finnhub, through a Cloudflare Worker proxy.</p>

<div class="setup-banner" id="setup-banner">
  <strong>One-time setup:</strong> replace <code>WORKER_URL</code> near the top of this page's script with your deployed Finnhub Worker URL (looks like <code>https://finnhub-proxy.YOUR-SUBDOMAIN.workers.dev</code>).
</div>

<div class="calc">
<h3>Search by Ticker or Company Name</h3>
<div class="ss-dropdown">
<label>Start typing a ticker or company name</label>
<input type="text" id="ss_query" placeholder="e.g. AAPL or Apple" autocomplete="off">
<div class="ss-matches" id="ss_matches"></div>
</div>
<p class="note" id="ss_ticker_count">Loading company list...</p>
<div id="ss_recent" style="margin-top:6px;font-size:12px;"></div>
</div>

<div class="result" id="ss_result"></div>

<script>
// Replace this with your own deployed Finnhub Cloudflare Worker URL (see setup banner above).
var WORKER_URL = "https://finnhub-proxy.tonyhernandezusa.workers.dev";

if (WORKER_URL.indexOf("YOUR-SUBDOMAIN") === -1) {
  var setupBanner = document.getElementById("setup-banner");
  if (setupBanner) { setupBanner.style.display = "none"; }
}

var ALL_TICKERS = [];
fetch("tickers.json").then(function(r) { return r.json(); }).then(function(data) {
  ALL_TICKERS = data;
  document.getElementById("ss_ticker_count").textContent = ALL_TICKERS.length.toLocaleString() + " companies loaded from SEC's official list.";
}).catch(function() {
  document.getElementById("ss_ticker_count").textContent = "Could not load the company list (tickers.json). Try refreshing the page.";
});

function money(x) {
  if (x === undefined || x === null || x === "") return "N/A";
  return "$" + Number(x).toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
}
function bigNumber(n) {
  if (n === undefined || n === null || n === "") return "N/A";
  n = Number(n);
  if (n >= 1e6) return "$" + (n / 1e3).toFixed(2) + "B"; // Finnhub marketCap is already in millions
  return "$" + n.toFixed(1) + "M";
}

document.getElementById("ss_query").addEventListener("input", function() {
  var q = this.value.trim().toUpperCase();
  var matchesEl = document.getElementById("ss_matches");
  if (!q || q.length < 1) { matchesEl.style.display = "none"; return; }

  var matches = ALL_TICKERS.filter(function(t) {
    return t.ticker.toUpperCase().indexOf(q) === 0 || t.name.toUpperCase().indexOf(q) !== -1;
  }).slice(0, 15);

  if (!matches.length) { matchesEl.style.display = "none"; return; }

  matchesEl.innerHTML = matches.map(function(t) {
    return "<div class='ss-match-item' data-ticker='" + t.ticker + "'><span class='ticker'>" + t.ticker + "</span> - " + t.name + "</div>";
  }).join("");
  matchesEl.style.display = "block";

  matchesEl.querySelectorAll(".ss-match-item").forEach(function(el) {
    el.addEventListener("click", function() {
      document.getElementById("ss_query").value = el.getAttribute("data-ticker");
      matchesEl.style.display = "none";
      lookupStock(el.getAttribute("data-ticker"));
    });
  });
});

document.getElementById("ss_query").addEventListener("keydown", function(e) {
  if (e.key === "Enter") {
    document.getElementById("ss_matches").style.display = "none";
    lookupStock(this.value.trim().toUpperCase());
  }
});

function showResult(html) {
  var el = document.getElementById("ss_result");
  el.innerHTML = html;
  el.style.display = "block";
}

function loadRecentStockSearches() {
  var recentEl = document.getElementById("ss_recent");
  var recent = [];
  try { recent = JSON.parse(localStorage.getItem("recentStockSearches") || "[]"); } catch (e) { recent = []; }
  if (!recent.length) { recentEl.innerHTML = ""; return; }
  recentEl.innerHTML = "<span style='color:#888;'>Recent:</span> " + recent.map(function(t) {
    return "<a href='#' data-ticker='" + t + "' style='color:#1f4e79;margin-right:10px;font-weight:600;'>" + t + "</a>";
  }).join("");
  recentEl.querySelectorAll("a").forEach(function(el) {
    el.addEventListener("click", function(e) {
      e.preventDefault();
      var t = el.getAttribute("data-ticker");
      document.getElementById("ss_query").value = t;
      lookupStock(t);
    });
  });
}
function saveRecentStockSearch(symbol) {
  var recent = [];
  try { recent = JSON.parse(localStorage.getItem("recentStockSearches") || "[]"); } catch (e) { recent = []; }
  recent = recent.filter(function(t) { return t !== symbol; });
  recent.unshift(symbol);
  recent = recent.slice(0, 8);
  localStorage.setItem("recentStockSearches", JSON.stringify(recent));
  loadRecentStockSearches();
}
loadRecentStockSearches();

async function lookupStock(symbol) {
  if (!symbol) return;
  showResult("Looking up " + symbol + "...");
  try {
    var resp = await fetch(WORKER_URL + "/stock-profile?symbol=" + encodeURIComponent(symbol));
    var data = await resp.json();

    if (data.error) {
      showResult("<strong style='color:#c0392b;'>" + data.error + "</strong>");
      return;
    }

    var p = data.profile || {};
    saveRecentStockSearch(symbol);
    var q = data.quote || {};
    var m = (data.metric && data.metric.metric) || {};
    var news = data.news || [];
    var financials = (data.financials && data.financials.data) || [];

    var changeColor = (q.d || 0) >= 0 ? "#1a8a3d" : "#c0392b";

    var newsHtml = "";
    if (Array.isArray(news) && news.length) {
      newsHtml = "<h4 style='font-size:13px;margin:14px 0 6px;'>Recent News</h4><ul style='margin:0;padding-left:18px;font-size:13px;'>";
      news.slice(0, 5).forEach(function(n) {
        newsHtml += "<li style='margin-bottom:6px;'><a href='" + n.url + "' target='_blank' style='color:#1f4e79;'>" + n.headline + "</a> <span style='color:#999;font-size:11px;'>(" + (n.source || "") + ")</span></li>";
      });
      newsHtml += "</ul>";
    }

    function fin(n) {
      return (n !== undefined && n !== null) ? "$" + Number(n).toLocaleString() : "N/A";
    }
    function statementTable(title, items) {
      if (!items || !items.length) return "";
      var html = "<h5 style='font-size:12px;margin:10px 0 4px;color:#555;'>" + title + "</h5><div class='table-wrap'><table>";
      items.forEach(function(row) {
        html += "<tr><td>" + row.label + "</td><td style='text-align:right;'>" + fin(row.value) + "</td></tr>";
      });
      html += "</table></div>";
      return html;
    }

    var financialsHtml = "";
    if (financials.length && financials[0].report) {
      var latest = financials[0];
      var rpt = latest.report;
      financialsHtml = "<h4 style='font-size:13px;margin:14px 0 6px;'>Financial Statements (" + latest.form + ", FY" + latest.year + ", filed " + (latest.filedDate || "").slice(0, 10) + ")</h4>" +
        statementTable("Income Statement", rpt.ic) +
        statementTable("Balance Sheet", rpt.bs) +
        statementTable("Cash Flow", rpt.cf) +
        "<span style='font-size:11px;color:#888;'>From SEC filings via Finnhub. " + financials.length + " year" + (financials.length === 1 ? "" : "s") + " of history available.</span>";
    }

    showResult(
      "<div style='display:flex;align-items:center;gap:10px;margin-bottom:10px;'>" +
      (p.logo ? "<img src='" + p.logo + "' style='width:40px;height:40px;border-radius:6px;' onerror='this.style.display=&#39;none&#39;'>" : "") +
      "<div><strong style='font-size:16px;'>" + (p.name || symbol) + " (" + symbol + ")</strong><br>" +
      "<span style='font-size:12px;color:#666;'>" + (p.finnhubIndustry || "") + (p.exchange ? " &middot; " + p.exchange : "") + "</span></div></div>" +

      "<div style='font-size:22px;font-weight:700;'>" + money(q.c) + " <span style='font-size:14px;font-weight:600;color:" + changeColor + ";'>" +
      (q.d >= 0 ? "+" : "") + (q.d !== undefined ? q.d.toFixed(2) : "N/A") + " (" + (q.dp !== undefined ? q.dp.toFixed(2) : "N/A") + "%)</span></div>" +
      "<span style='font-size:11px;color:#888;'>Day range: " + money(q.l) + " - " + money(q.h) + " &middot; Prev close: " + money(q.pc) + "</span>" +

      "<h4 style='font-size:13px;margin:14px 0 6px;'>Key Stats</h4>" +
      "Market cap: " + bigNumber(p.marketCapitalization) + "<br>" +
      "Shares outstanding: " + (p.shareOutstanding ? (p.shareOutstanding).toLocaleString() + "M" : "N/A") + "<br>" +
      "P/E (TTM): " + (m.peBasicExclExtraTTM !== undefined ? m.peBasicExclExtraTTM.toFixed(2) : "N/A") + "<br>" +
      "EPS (TTM): " + (m.epsBasicExclExtraItemsTTM !== undefined ? money(m.epsBasicExclExtraItemsTTM) : "N/A") + "<br>" +
      "Beta: " + (m.beta !== undefined ? m.beta.toFixed(2) : "N/A") + "<br>" +
      "Dividend yield: " + (m.dividendYieldIndicatedAnnual !== undefined ? m.dividendYieldIndicatedAnnual.toFixed(2) + "%" : "N/A") + "<br>" +
      "52-week high/low: " + (m["52WeekHigh"] !== undefined ? money(m["52WeekHigh"]) : "N/A") + " / " + (m["52WeekLow"] !== undefined ? money(m["52WeekLow"]) : "N/A") + "<br>" +
      "ROE (TTM): " + (m.roeTTM !== undefined ? (m.roeTTM * 100).toFixed(1) + "%" : "N/A") + " &nbsp;|&nbsp; ROA (TTM): " + (m.roaTTM !== undefined ? (m.roaTTM * 100).toFixed(1) + "%" : "N/A") + "<br>" +
      "Debt/Equity: " + (m.totalDebtToEquity !== undefined ? m.totalDebtToEquity.toFixed(2) : "N/A") + " &nbsp;|&nbsp; Quick ratio: " + (m.quickRatio !== undefined ? m.quickRatio.toFixed(2) : "N/A") + "<br>" +

      "<div style='margin-top:10px;'><a href='https://finance.yahoo.com/quote/" + symbol + "' target='_blank' style='color:#1f4e79;font-size:13px;'>View on Yahoo Finance &rarr;</a></div>" +

      newsHtml +
      financialsHtml +

      "<button onclick='getAiSummary(&#39;" + symbol + "&#39;)' style='margin-top:14px;'>Generate AI Summary</button>" +
      "<div id='ss_ai_summary' style='margin-top:10px;font-size:13px;'></div>" +

      "<br><span style='font-size:11px;color:#888;'>Data from Finnhub.</span>"
    );
  } catch (err) {
    showResult("<strong style='color:#c0392b;'>Could not reach the search service.</strong> Confirm WORKER_URL is set to your deployed Finnhub Worker, and that the Worker is running.");
  }
}

async function getAiSummary(symbol) {
  var el = document.getElementById("ss_ai_summary");
  el.textContent = "Generating...";
  try {
    var resp = await fetch(WORKER_URL + "/ai-summary?symbol=" + encodeURIComponent(symbol));
    var data = await resp.json();
    el.innerHTML = data.error ? ("<span style='color:#c0392b;'>" + data.error + "</span>") : ("<em>" + data.summary + "</em>");
  } catch (err) {
    el.innerHTML = "<span style='color:#c0392b;'>Could not reach the AI summary service.</span>";
  }
}
</script>

</body>
</html>"""

stocksearch_html = (STOCKSEARCH_TEMPLATE
                     .replace("__CSS__", PAGE_CSS)
                     .replace("__NAV__", NAV_HTML))

tickers_json = json.dumps(all_us_tickers)

# ------------------- PAGE 6: PROPERTY MANAGER -------------------

PROPERTYMANAGER_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Property Manager</title>
<script src="https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.14.1/firebase-auth-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.14.1/firebase-firestore-compat.js"></script>
<style>__CSS__
.calc { background:#fff; border-radius:10px; padding:18px; border:1px solid #e5e3dc; margin-bottom:20px; max-width:640px; }
.calc h3 { margin:0 0 12px; font-size:16px; }
.calc label { display:block; font-size:12px; color:#666; margin:10px 0 3px; }
.calc input { width:100%; padding:8px; font-size:14px; border:1px solid #ccc; border-radius:6px; box-sizing:border-box; }
.calc button { margin-top:14px; padding:10px 18px; font-size:14px; font-weight:600; color:#fff; background:#1f4e79; border:none; border-radius:6px; cursor:pointer; }
.calc button:hover { background:#163a5c; }
.calc button.secondary { background:#888; }
.calc button.secondary:hover { background:#666; }
.result { margin-top:14px; padding:12px; background:#f0f6ec; border-radius:6px; font-size:14px; }
.err { color:#c0392b; font-size:13px; margin-top:8px; }
.property-card { background:#fff; border:1px solid #e5e3dc; border-radius:8px; padding:14px; margin-bottom:10px; }
.property-card h4 { margin:0 0 6px; font-size:15px; }
@media (max-width: 600px) {
  body { padding:12px; }
  .calc { padding:14px; max-width:100%; }
  .calc input { font-size:16px !important; padding:10px !important; }
  .calc button { width:100%; }
}
</style>
</head>
<body>
__NAV__
<h1>Property Manager</h1>
<p class="timestamp">Track your rental properties, units, rent, and expenses in one place.</p>

<div class="calc" id="auth-panel">
<h3 id="auth-title">Log In</h3>
<label>Email</label>
<input type="email" id="auth-email">
<label>Password</label>
<input type="password" id="auth-password">
<button onclick="doLogin()">Log In</button>
<button class="secondary" onclick="doSignup()">Create Account</button>
<div class="err" id="auth-error"></div>
</div>

<div id="dashboard" style="display:none;">
  <div class="calc">
    <span id="welcome-msg"></span> &nbsp;
    <button class="secondary" onclick="doLogout()" style="margin-top:0;">Log Out</button>
  </div>

  <div class="calc">
    <h3>Add a Property</h3>
    <label>Street Address</label>
    <input type="text" id="p-address" placeholder="123 Main St">
    <label>City</label>
    <input type="text" id="p-city">
    <label>State</label>
    <input type="text" id="p-state" placeholder="FL">
    <label>ZIP</label>
    <input type="text" id="p-zip">
    <label>Number of Units</label>
    <input type="number" id="p-units" value="1" min="1">
    <label>Purchase Price (optional)</label>
    <input type="number" id="p-price">
    <button onclick="addProperty()">Add Property</button>
    <div class="err" id="add-error"></div>
  </div>

  <h3>Your Properties</h3>
  <div id="property-list"></div>

  <div id="property-detail" style="display:none;">
    <div class="calc">
      <a href="#" id="back-to-properties" style="font-size:13px;color:#1f4e79;">&larr; Back to Properties</a>
      <h3 id="detail-address" style="margin-top:8px;"></h3>
      <div id="detail-summary" style="font-size:14px;"></div>
    </div>

    <div class="calc">
      <h3>Units</h3>
      <p class="note">Add units in a batch by type (e.g. 10 x "1 Bed / 1 Bath"), then rename each one's unit number below.</p>
      <label>Unit Type</label>
      <input type="text" id="u-type" placeholder="1 Bed / 1 Bath">
      <label>How Many of This Type</label>
      <input type="number" id="u-count" value="1" min="1">
      <label>Rent per Unit</label>
      <input type="number" id="u-rent">
      <button onclick="addUnitBatch()">Add Units</button>
      <div class="err" id="unit-error"></div>
      <div id="unit-list" style="margin-top:12px;"></div>
    </div>

    <div class="calc">
      <h3>Expenses</h3>
      <label>Category</label>
      <input type="text" id="e-category" placeholder="Property tax, insurance, repairs, etc.">
      <label>Amount</label>
      <input type="number" id="e-amount">
      <label>Date</label>
      <input type="date" id="e-date">
      <button onclick="addExpense()">Add Expense</button>
      <div class="err" id="expense-error"></div>
      <div id="expense-list" style="margin-top:12px;"></div>
    </div>
  </div>
</div>

<script>
var firebaseConfig = {
  apiKey: "AIzaSyDjpFZwtHQ5HxYLTyMzO0XFDMZqq1CwFV8",
  authDomain: "property-manager-9455a.firebaseapp.com",
  projectId: "property-manager-9455a",
  storageBucket: "property-manager-9455a.firebasestorage.app",
  messagingSenderId: "986237651798",
  appId: "1:986237651798:web:f42e0af8fce40b180064f7"
};
firebase.initializeApp(firebaseConfig);
var auth = firebase.auth();
var db = firebase.firestore();

function showError(elId, message) {
  document.getElementById(elId).textContent = message;
}

function doSignup() {
  var email = document.getElementById("auth-email").value.trim();
  var password = document.getElementById("auth-password").value;
  showError("auth-error", "");
  auth.createUserWithEmailAndPassword(email, password).catch(function(err) {
    showError("auth-error", err.message);
  });
}

function doLogin() {
  var email = document.getElementById("auth-email").value.trim();
  var password = document.getElementById("auth-password").value;
  showError("auth-error", "");
  auth.signInWithEmailAndPassword(email, password).catch(function(err) {
    showError("auth-error", err.message);
  });
}

function doLogout() {
  auth.signOut();
}

auth.onAuthStateChanged(function(user) {
  if (user) {
    document.getElementById("auth-panel").style.display = "none";
    document.getElementById("dashboard").style.display = "block";
    document.getElementById("welcome-msg").textContent = "Logged in as " + user.email;
    loadProperties(user.uid);
  } else {
    document.getElementById("auth-panel").style.display = "block";
    document.getElementById("dashboard").style.display = "none";
  }
});

function addProperty() {
  var user = auth.currentUser;
  if (!user) return;
  var address = document.getElementById("p-address").value.trim();
  var city = document.getElementById("p-city").value.trim();
  var state = document.getElementById("p-state").value.trim();
  var zip = document.getElementById("p-zip").value.trim();
  var units = parseInt(document.getElementById("p-units").value, 10) || 1;
  var price = document.getElementById("p-price").value ? parseFloat(document.getElementById("p-price").value) : null;

  showError("add-error", "");
  if (!address) { showError("add-error", "Enter a street address."); return; }

  db.collection("properties").add({
    ownerId: user.uid,
    address: address,
    city: city,
    state: state,
    zip: zip,
    units: units,
    purchasePrice: price,
    createdAt: firebase.firestore.FieldValue.serverTimestamp()
  }).then(function() {
    document.getElementById("p-address").value = "";
    document.getElementById("p-city").value = "";
    document.getElementById("p-state").value = "";
    document.getElementById("p-zip").value = "";
    document.getElementById("p-units").value = "1";
    document.getElementById("p-price").value = "";
  }).catch(function(err) {
    showError("add-error", err.message);
  });
}

function loadProperties(uid) {
  db.collection("properties").where("ownerId", "==", uid).onSnapshot(function(snapshot) {
    var listEl = document.getElementById("property-list");
    if (snapshot.empty) {
      listEl.innerHTML = "<p class='note'>No properties yet - add one above.</p>";
      return;
    }
    var html = "";
    snapshot.forEach(function(doc) {
      var p = doc.data();
      html += "<div class='property-card'>" +
        "<h4>" + p.address + "</h4>" +
        (p.city || p.state || p.zip ? "<span style='font-size:13px;color:#666;'>" + [p.city, p.state, p.zip].filter(Boolean).join(", ") + "</span><br>" : "") +
        "Units: " + p.units +
        (p.purchasePrice ? " &nbsp;|&nbsp; Purchase price: $" + Number(p.purchasePrice).toLocaleString() : "") +
        "<br><button style='margin-top:8px;padding:6px 12px;font-size:12px;' data-view-id='" + doc.id + "' data-view-address='" + p.address.replace(/'/g, "&#39;") + "'>Manage Units &amp; Expenses</button> " +
        "<button class='secondary' style='margin-top:8px;padding:6px 12px;font-size:12px;' data-id='" + doc.id + "'>Delete</button>" +
        "</div>";
    });
    listEl.innerHTML = html;
    listEl.querySelectorAll("button[data-view-id]").forEach(function(btn) {
      btn.addEventListener("click", function() {
        openPropertyDetail(btn.getAttribute("data-view-id"), btn.getAttribute("data-view-address"));
      });
    });
    listEl.querySelectorAll("button[data-id]").forEach(function(btn) {
      btn.addEventListener("click", function() {
        if (confirm("Delete this property?")) {
          db.collection("properties").doc(btn.getAttribute("data-id")).delete();
        }
      });
    });
  });
}

var currentPropertyId = null;
var unitsUnsub = null;
var expensesUnsub = null;
var currentUnits = [];
var currentExpenses = [];

function openPropertyDetail(propertyId, address) {
  currentPropertyId = propertyId;
  document.getElementById("property-list").parentElement.querySelector("h3").style.display = "none";
  document.getElementById("property-list").style.display = "none";
  document.getElementById("property-detail").style.display = "block";
  document.getElementById("detail-address").textContent = address;

  if (unitsUnsub) unitsUnsub();
  if (expensesUnsub) expensesUnsub();

  unitsUnsub = db.collection("properties").doc(propertyId).collection("entries")
    .where("type", "==", "unit").onSnapshot(function(snapshot) {
      currentUnits = [];
      snapshot.forEach(function(doc) { currentUnits.push({ id: doc.id, ...doc.data() }); });
      renderUnits();
      renderSummary();
    });

  expensesUnsub = db.collection("properties").doc(propertyId).collection("entries")
    .where("type", "==", "expense").onSnapshot(function(snapshot) {
      currentExpenses = [];
      snapshot.forEach(function(doc) { currentExpenses.push({ id: doc.id, ...doc.data() }); });
      renderExpenses();
      renderSummary();
    });
}

document.getElementById("back-to-properties").addEventListener("click", function(e) {
  e.preventDefault();
  if (unitsUnsub) { unitsUnsub(); unitsUnsub = null; }
  if (expensesUnsub) { expensesUnsub(); expensesUnsub = null; }
  currentPropertyId = null;
  document.getElementById("property-detail").style.display = "none";
  document.getElementById("property-list").style.display = "block";
  document.getElementById("property-list").parentElement.querySelector("h3").style.display = "block";
});

function addUnitBatch() {
  if (!currentPropertyId) return;
  var unitType = document.getElementById("u-type").value.trim();
  var count = parseInt(document.getElementById("u-count").value, 10) || 0;
  var rent = parseFloat(document.getElementById("u-rent").value) || 0;
  showError("unit-error", "");
  if (!unitType) { showError("unit-error", "Enter a unit type, e.g. '1 Bed / 1 Bath'."); return; }
  if (count < 1) { showError("unit-error", "Enter how many units of this type to add."); return; }

  var maxSort = currentUnits.reduce(function(max, u) { return Math.max(max, u.sortOrder || 0); }, 0);

  var batch = db.batch();
  var entriesRef = db.collection("properties").doc(currentPropertyId).collection("entries");
  for (var i = 1; i <= count; i++) {
    var docRef = entriesRef.doc();
    batch.set(docRef, {
      type: "unit",
      unitType: unitType,
      unitNumber: "",
      rent: rent,
      occupied: true,
      sortOrder: maxSort + i,
      leaseType: "month-to-month",
      leaseTermMonths: null,
      moveInDate: "",
      leaseEndDate: "",
      securityDeposit: 0,
      firstMonthDeposit: 0,
      lastMonthDeposit: 0,
      noDeposit: false,
      createdAt: firebase.firestore.FieldValue.serverTimestamp()
    });
  }
  batch.commit().then(function() {
    document.getElementById("u-type").value = "";
    document.getElementById("u-count").value = "1";
    document.getElementById("u-rent").value = "";
  }).catch(function(err) { showError("unit-error", err.message); });
}

function unitDocRef(unitId) {
  return db.collection("properties").doc(currentPropertyId).collection("entries").doc(unitId);
}

function updateUnitField(unitId, field, value) {
  var update = {};
  update[field] = value;
  unitDocRef(unitId).update(update);
}

function toggleUnitOccupied(unitId, occupied) {
  updateUnitField(unitId, "occupied", occupied);
}

function moveUnit(unitId, direction) {
  var sorted = currentUnits.slice().sort(function(a, b) { return (a.sortOrder || 0) - (b.sortOrder || 0); });
  var idx = sorted.findIndex(function(u) { return u.id === unitId; });
  var swapIdx = idx + direction;
  if (swapIdx < 0 || swapIdx >= sorted.length) return;

  var a = sorted[idx], b = sorted[swapIdx];
  var aOrder = a.sortOrder || 0, bOrder = b.sortOrder || 0;
  var batch = db.batch();
  batch.update(unitDocRef(a.id), { sortOrder: bOrder });
  batch.update(unitDocRef(b.id), { sortOrder: aOrder });
  batch.commit();
}

var openDetailPanels = {};

function toggleDetailPanel(unitId) {
  openDetailPanels[unitId] = !openDetailPanels[unitId];
  renderUnits();
}

function saveLeaseDetails(unitId) {
  var noDeposit = document.getElementById("nd-" + unitId).checked;
  updateUnitField(unitId, "moveInDate", document.getElementById("mi-" + unitId).value);
  updateUnitField(unitId, "leaseType", document.getElementById("lt-" + unitId).value);
  updateUnitField(unitId, "leaseTermMonths", parseInt(document.getElementById("term-" + unitId).value, 10) || null);
  updateUnitField(unitId, "leaseEndDate", document.getElementById("le-" + unitId).value);
  updateUnitField(unitId, "noDeposit", noDeposit);
  updateUnitField(unitId, "securityDeposit", noDeposit ? 0 : (parseFloat(document.getElementById("sd-" + unitId).value) || 0));
  updateUnitField(unitId, "firstMonthDeposit", noDeposit ? 0 : (parseFloat(document.getElementById("fm-" + unitId).value) || 0));
  updateUnitField(unitId, "lastMonthDeposit", noDeposit ? 0 : (parseFloat(document.getElementById("lm-" + unitId).value) || 0));
}

function renderUnits() {
  var el = document.getElementById("unit-list");
  if (!currentUnits.length) { el.innerHTML = "<p class='note'>No units yet.</p>"; return; }
  var sorted = currentUnits.slice().sort(function(a, b) { return (a.sortOrder || 0) - (b.sortOrder || 0); });
  var html = "<div class='table-wrap'><table><tr><th></th><th>Type</th><th>Unit #</th><th style='text-align:right;'>Rent</th><th>Occupied</th><th>Lease</th><th></th></tr>";
  sorted.forEach(function(u, i) {
    var esc = function(s) { return (s || "").toString().replace(/'/g, "&#39;"); };
    html += "<tr><td style='white-space:nowrap;'>" +
      "<button class='secondary' style='margin:0;padding:2px 6px;font-size:11px;' data-move-up='" + u.id + "'" + (i === 0 ? " disabled" : "") + ">&uarr;</button> " +
      "<button class='secondary' style='margin:0;padding:2px 6px;font-size:11px;' data-move-down='" + u.id + "'" + (i === sorted.length - 1 ? " disabled" : "") + ">&darr;</button></td>" +
      "<td>" + (u.unitType || "N/A") + "</td>" +
      "<td><input type='text' value='" + esc(u.unitNumber !== undefined ? u.unitNumber : u.label) + "' placeholder='e.g. 204' data-field-id='" + u.id + "' data-field='unitNumber' style='width:90px;padding:4px;font-size:12px;'></td>" +
      "<td><input type='number' value='" + Number(u.rent || 0) + "' data-field-id='" + u.id + "' data-field='rent' style='width:80px;padding:4px;font-size:12px;text-align:right;'></td>" +
      "<td><input type='checkbox' data-occ-id='" + u.id + "' " + (u.occupied ? "checked" : "") + " style='width:auto;'></td>" +
      "<td><button style='margin:0;padding:4px 8px;font-size:11px;' data-toggle-detail='" + u.id + "'>" + (openDetailPanels[u.id] ? "Hide" : "Details") + "</button></td>" +
      "<td><button class='secondary' style='margin:0;padding:4px 10px;font-size:11px;' data-unit-id='" + u.id + "'>Delete</button></td></tr>";

    if (openDetailPanels[u.id]) {
      html += "<tr><td colspan='7'><div style='background:#f7f6f2;padding:12px;border-radius:6px;'>" +
        "<div style='display:flex;flex-wrap:wrap;gap:14px;'>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>Move-In Date</label><input type='date' id='mi-" + u.id + "' value='" + esc(u.moveInDate) + "' style='padding:6px;font-size:12px;'></div>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>Lease Type</label><select id='lt-" + u.id + "' style='padding:6px;font-size:12px;'>" +
          "<option value='month-to-month'" + (u.leaseType === "month-to-month" ? " selected" : "") + ">Month-to-Month</option>" +
          "<option value='lease'" + (u.leaseType === "lease" ? " selected" : "") + ">Fixed-Term Lease</option>" +
        "</select></div>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>Term (months)</label><input type='number' id='term-" + u.id + "' value='" + (u.leaseTermMonths || "") + "' style='width:70px;padding:6px;font-size:12px;'></div>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>Lease End Date</label><input type='date' id='le-" + u.id + "' value='" + esc(u.leaseEndDate) + "' style='padding:6px;font-size:12px;'></div>" +
        "</div>" +
        "<div style='margin-top:10px;display:flex;flex-wrap:wrap;gap:14px;align-items:end;'>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>Security Deposit</label><input type='number' id='sd-" + u.id + "' value='" + Number(u.securityDeposit || 0) + "' style='width:90px;padding:6px;font-size:12px;'></div>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>1st Month Collected</label><input type='number' id='fm-" + u.id + "' value='" + Number(u.firstMonthDeposit || 0) + "' style='width:90px;padding:6px;font-size:12px;'></div>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>Last Month Collected</label><input type='number' id='lm-" + u.id + "' value='" + Number(u.lastMonthDeposit || 0) + "' style='width:90px;padding:6px;font-size:12px;'></div>" +
        "<div><label style='font-size:12px;'><input type='checkbox' id='nd-" + u.id + "' " + (u.noDeposit ? "checked" : "") + " style='width:auto;'> No deposit collected</label></div>" +
        "</div>" +
        "<button data-save-detail='" + u.id + "' style='margin-top:12px;'>Save Lease Details</button>" +
        "</div></td></tr>";
    }
  });
  html += "</table></div>";
  el.innerHTML = html;

  el.querySelectorAll("input[data-field]").forEach(function(input) {
    input.addEventListener("blur", function() {
      var field = input.getAttribute("data-field");
      var value = field === "rent" ? (parseFloat(input.value) || 0) : input.value.trim();
      updateUnitField(input.getAttribute("data-field-id"), field, value);
    });
  });
  el.querySelectorAll("input[data-occ-id]").forEach(function(input) {
    input.addEventListener("change", function() {
      toggleUnitOccupied(input.getAttribute("data-occ-id"), input.checked);
    });
  });
  el.querySelectorAll("button[data-move-up]").forEach(function(btn) {
    btn.addEventListener("click", function() { moveUnit(btn.getAttribute("data-move-up"), -1); });
  });
  el.querySelectorAll("button[data-move-down]").forEach(function(btn) {
    btn.addEventListener("click", function() { moveUnit(btn.getAttribute("data-move-down"), 1); });
  });
  el.querySelectorAll("button[data-toggle-detail]").forEach(function(btn) {
    btn.addEventListener("click", function() { toggleDetailPanel(btn.getAttribute("data-toggle-detail")); });
  });
  el.querySelectorAll("button[data-save-detail]").forEach(function(btn) {
    btn.addEventListener("click", function() { saveLeaseDetails(btn.getAttribute("data-save-detail")); });
  });
  el.querySelectorAll("button[data-unit-id]").forEach(function(btn) {
    btn.addEventListener("click", function() {
      db.collection("properties").doc(currentPropertyId).collection("entries").doc(btn.getAttribute("data-unit-id")).delete();
    });
  });
}

function addExpense() {
  if (!currentPropertyId) return;
  var category = document.getElementById("e-category").value.trim();
  var amount = parseFloat(document.getElementById("e-amount").value) || 0;
  var date = document.getElementById("e-date").value;
  showError("expense-error", "");
  if (!category) { showError("expense-error", "Enter a category."); return; }
  if (!date) { showError("expense-error", "Select a date."); return; }

  db.collection("properties").doc(currentPropertyId).collection("entries").add({
    type: "expense", category: category, amount: amount, date: date,
    createdAt: firebase.firestore.FieldValue.serverTimestamp()
  }).then(function() {
    document.getElementById("e-category").value = "";
    document.getElementById("e-amount").value = "";
    document.getElementById("e-date").value = "";
  }).catch(function(err) { showError("expense-error", err.message); });
}

function renderExpenses() {
  var el = document.getElementById("expense-list");
  if (!currentExpenses.length) { el.innerHTML = "<p class='note'>No expenses logged yet.</p>"; return; }
  var sorted = currentExpenses.slice().sort(function(a, b) { return (b.date || "").localeCompare(a.date || ""); });
  var html = "<div class='table-wrap'><table><tr><th>Date</th><th>Category</th><th style='text-align:right;'>Amount</th><th></th></tr>";
  sorted.forEach(function(e) {
    html += "<tr><td>" + e.date + "</td><td>" + e.category + "</td><td style='text-align:right;'>$" + Number(e.amount).toLocaleString() + "</td>" +
      "<td><button class='secondary' style='margin:0;padding:4px 10px;font-size:11px;' data-exp-id='" + e.id + "'>Delete</button></td></tr>";
  });
  html += "</table></div>";
  el.innerHTML = html;
  el.querySelectorAll("button[data-exp-id]").forEach(function(btn) {
    btn.addEventListener("click", function() {
      db.collection("properties").doc(currentPropertyId).collection("entries").doc(btn.getAttribute("data-exp-id")).delete();
    });
  });
}

function renderSummary() {
  var occupiedUnits = currentUnits.filter(function(u) { return u.occupied; });
  var totalMonthlyRent = occupiedUnits.reduce(function(sum, u) { return sum + Number(u.rent || 0); }, 0);
  var vacantCount = currentUnits.length - occupiedUnits.length;

  var now = new Date();
  var thisMonth = now.toISOString().slice(0, 7); // YYYY-MM
  var thisMonthExpenses = currentExpenses.filter(function(e) { return (e.date || "").slice(0, 7) === thisMonth; });
  var totalThisMonthExpenses = thisMonthExpenses.reduce(function(sum, e) { return sum + Number(e.amount || 0); }, 0);
  var totalAllExpenses = currentExpenses.reduce(function(sum, e) { return sum + Number(e.amount || 0); }, 0);

  var cashFlow = totalMonthlyRent - totalThisMonthExpenses;
  var cashFlowColor = cashFlow >= 0 ? "#1a8a3d" : "#c0392b";

  document.getElementById("detail-summary").innerHTML =
    "Units: " + currentUnits.length + " total &middot; " + occupiedUnits.length + " occupied &middot; " + vacantCount + " vacant<br>" +
    "Total monthly rent (occupied units): <strong>$" + totalMonthlyRent.toLocaleString() + "</strong><br>" +
    "Expenses this month: $" + totalThisMonthExpenses.toLocaleString() + " &middot; All-time logged expenses: $" + totalAllExpenses.toLocaleString() + "<br>" +
    "<span style='color:" + cashFlowColor + ";font-weight:600;'>Estimated monthly cash flow: $" + cashFlow.toLocaleString() + "</span>" +
    "<br><span style='font-size:11px;color:#888;'>Cash flow is rent from occupied units minus this calendar month's logged expenses - a simple estimate, not a full P&amp;L.</span>";
}
</script>

</body>
</html>"""

propertymanager_html = (PROPERTYMANAGER_TEMPLATE
                        .replace("__CSS__", PAGE_CSS)
                        .replace("__NAV__", NAV_HTML))

with open("index.html", "w") as f:
    f.write(stocks_html)

with open("realestate.html", "w") as f:
    f.write(realestate_html)

with open("calculators.html", "w") as f:
    f.write(calculators_html)

with open("search.html", "w") as f:
    f.write(search_html)

with open("stocksearch.html", "w") as f:
    f.write(stocksearch_html)

with open("tickers.json", "w") as f:
    f.write(tickers_json)

with open("propertymanager.html", "w") as f:
    f.write(propertymanager_html)

print("index.html, realestate.html, calculators.html, search.html, stocksearch.html, tickers.json, and propertymanager.html generated successfully")
