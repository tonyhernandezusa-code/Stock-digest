import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
from datetime import datetime

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
