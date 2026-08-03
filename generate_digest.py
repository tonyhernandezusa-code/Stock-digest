import warnings
warnings.filterwarnings("ignore")

import os
import re
import yfinance as yf
import requests
import json
import html as html_escape_mod
from datetime import datetime, timedelta

FRED_API_KEY = "d6150924a7a201d4e891d082f7123818"

# As of May 12, 2026, the Census Bureau requires a registered API key for ACS5 queries -
# get a free one at https://api.census.gov/data/key_signup.html (instant, no approval wait)
# and paste it here. Without this, the County Investment Map's population data will fail
# to load and every county will show as "no data" (gray).
CENSUS_API_KEY = "4eff88d2eade5014bcf016d85d4a09f309872025"

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

# Sector SPDR ETFs used for the Sector Momentum vs. Macro Divergence gauge (see
# compute_sector_divergence() below for methodology).
SECTOR_ETFS = [
    ("Technology", "XLK"),
    ("Financials", "XLF"),
    ("Energy", "XLE"),
    ("Industrials", "XLI"),
    ("Consumer Staples", "XLP"),
    ("Consumer Discretionary", "XLY"),
    ("Utilities", "XLU"),
    ("Healthcare", "XLV"),
    ("Materials", "XLB"),
    ("Real Estate", "XLRE"),
    ("Communication Services", "XLC"),
]

# Illustrative sector sensitivity weights (-1.0 to +1.0) to four macro factors, used by
# compute_sector_divergence() to build a "Macro Fit Score" for each sector. These reflect
# commonly cited, textbook sector characteristics (e.g. REITs/utilities are rate-sensitive,
# energy tracks oil, staples/utilities are defensive during volatility spikes) - they are a
# transparent, editable set of assumptions, NOT statistically fitted to historical data, and
# are disclosed as such wherever this gauge is displayed.
#   rate:  sensitivity to a rise in the 10-Year Treasury yield (negative = hurt by rising rates)
#   oil:   sensitivity to a rise in WTI crude oil prices
#   vix:   sensitivity to a rise in the VIX (negative = sells off in risk-off; positive = defensive)
#   infl:  sensitivity to a rise in CPI month-over-month inflation
SECTOR_MACRO_SENSITIVITIES = {
    "XLK":  {"rate": -1.0, "oil": -0.2, "vix": -0.8, "infl": -0.5},
    "XLF":  {"rate": +0.8, "oil":  0.0, "vix": -0.4, "infl": -0.2},
    "XLE":  {"rate": -0.2, "oil": +1.0, "vix": -0.2, "infl": +0.3},
    "XLI":  {"rate": -0.3, "oil": +0.3, "vix": -0.5, "infl": -0.2},
    "XLP":  {"rate": -0.1, "oil": -0.1, "vix": +0.6, "infl": -0.3},
    "XLY":  {"rate": -0.6, "oil": -0.3, "vix": -0.6, "infl": -0.5},
    "XLU":  {"rate": -0.7, "oil": -0.1, "vix": +0.5, "infl": -0.2},
    "XLV":  {"rate": -0.2, "oil":  0.0, "vix": +0.4, "infl": -0.1},
    "XLB":  {"rate": -0.3, "oil": +0.4, "vix": -0.4, "infl": +0.2},
    "XLRE": {"rate": -0.9, "oil":  0.0, "vix": -0.3, "infl": -0.2},
    "XLC":  {"rate": -0.6, "oil": -0.1, "vix": -0.6, "infl": -0.3},
}
CRYPTO = [
    ("Bitcoin", "BTC-USD"),
    ("Ethereum", "ETH-USD"),
    ("Tether", "USDT-USD"),
    ("BNB", "BNB-USD"),
    ("Solana", "SOL-USD"),
    ("XRP", "XRP-USD"),
    ("USD Coin", "USDC-USD"),
    ("Cardano", "ADA-USD"),
    ("Dogecoin", "DOGE-USD"),
    ("TRON", "TRX-USD"),
    ("Avalanche", "AVAX-USD"),
    ("Chainlink", "LINK-USD"),
    ("Polkadot", "DOT-USD"),
    ("Litecoin", "LTC-USD"),
    ("Shiba Inu", "SHIB-USD"),
    ("Bitcoin Cash", "BCH-USD"),
    ("Stellar", "XLM-USD"),
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

# Federal Reserve longer-run policy targets, used by the Fed Policy Targets gauge below.
# Inflation targets are the Fed's official, fixed policy goal (2% since the January 2012
# statement, reaffirmed since). Unemployment, GDP growth, and the federal funds rate are NOT
# fixed targets - they are the MEDIAN of individual FOMC members' own quarterly forecasts,
# published in the Summary of Economic Projections (SEP), and they move release to release
# (e.g. the longer-run GDP growth projection moved from 1.8% to 2.0% in the June 2026 SEP).
# Ask Claude to "update my Fed targets" after each new SEP release (~8x/year, alongside FOMC
# meetings) - source: federalreserve.gov/monetarypolicy/fomcprojtabl.htm
FED_TARGETS_ASOF = "June 2026 SEP"
FED_LONGER_RUN_TARGETS = {
    "cpi_inflation": 2.0,        # Official FOMC longer-run inflation goal (fixed policy target)
    "core_pce_inflation": 2.0,   # Same goal in PCE terms - the Fed's preferred inflation gauge
    "unemployment": 4.2,         # FOMC SEP longer-run median projection
    "gdp_growth": 2.0,           # FOMC SEP longer-run median projection
    "fed_funds_neutral": 3.0,    # FOMC SEP longer-run median projection (the "neutral rate")
}

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

# Top marginal state individual income tax rates (2025, Tax Foundation) - used only to give a
# rough illustration of income tax savings from real estate deductions in the Tax Savings
# Estimator on the Calculators and Property Manager pages. This is each state's TOP marginal
# rate; actual liability depends on total income, filing status, and state-specific rules
# (local/county taxes, surtaxes, and phaseouts are not included). Washington taxes capital
# gains only (not rental income), so it's listed as 0 here. Not tax advice.
STATE_TOP_MARGINAL_RATES = [
    ("AL", "Alabama", 5.00), ("AK", "Alaska", 0), ("AZ", "Arizona", 2.50), ("AR", "Arkansas", 3.90),
    ("CA", "California", 13.30), ("CO", "Colorado", 4.40), ("CT", "Connecticut", 6.99),
    ("DE", "Delaware", 6.60), ("FL", "Florida", 0), ("GA", "Georgia", 5.39), ("HI", "Hawaii", 11.00),
    ("ID", "Idaho", 5.695), ("IL", "Illinois", 4.95), ("IN", "Indiana", 3.00), ("IA", "Iowa", 3.80),
    ("KS", "Kansas", 5.58), ("KY", "Kentucky", 4.00), ("LA", "Louisiana", 3.00), ("ME", "Maine", 7.15),
    ("MD", "Maryland", 5.75), ("MA", "Massachusetts", 5.00), ("MI", "Michigan", 4.25),
    ("MN", "Minnesota", 9.85), ("MS", "Mississippi", 4.40), ("MO", "Missouri", 4.70),
    ("MT", "Montana", 5.90), ("NE", "Nebraska", 5.20), ("NV", "Nevada", 0),
    ("NH", "New Hampshire", 0), ("NJ", "New Jersey", 10.75), ("NM", "New Mexico", 5.90),
    ("NY", "New York", 10.90), ("NC", "North Carolina", 4.25), ("ND", "North Dakota", 2.50),
    ("OH", "Ohio", 3.50), ("OK", "Oklahoma", 4.75), ("OR", "Oregon", 9.90),
    ("PA", "Pennsylvania", 3.07), ("RI", "Rhode Island", 5.99), ("SC", "South Carolina", 6.20),
    ("SD", "South Dakota", 0), ("TN", "Tennessee", 0), ("TX", "Texas", 0), ("UT", "Utah", 4.55),
    ("VT", "Vermont", 8.75), ("VA", "Virginia", 5.75), ("WA", "Washington", 0),
    ("WV", "West Virginia", 4.82), ("WI", "Wisconsin", 7.65), ("WY", "Wyoming", 0),
    ("DC", "Washington DC", 10.75),
]

STATE_TAX_JS_TABLE = "{" + ",".join(
    '"{}":{}'.format(code, rate) for code, name, rate in STATE_TOP_MARGINAL_RATES
) + "}"

STATE_TAX_OPTIONS_HTML = "\n".join(
    '<option value="{}"{}>{} ({}%)</option>'.format(code, ' selected' if code == "FL" else '', name, ("%g" % rate))
    for code, name, rate in STATE_TOP_MARGINAL_RATES
)

STATE_NAME_TO_ABBR_JS = "{" + ",".join(
    '"{}":"{}"'.format(name.upper(), code) for code, name, rate in STATE_TOP_MARGINAL_RATES
) + ',"D.C.":"DC","DISTRICT OF COLUMBIA":"DC"}'

STATE_TAX_JS_HELPER = """
// Top marginal state individual income tax rates (2025, Tax Foundation) - illustration only.
var STATE_TOP_MARGINAL_RATE = __STATE_TAX_TABLE__;
var STATE_NAME_TO_ABBR = __STATE_NAME_TO_ABBR__;
function getStateTopMarginalRate(stateInput) {
  var s = (stateInput || "").trim().toUpperCase();
  if (!s) return null;
  if (STATE_TOP_MARGINAL_RATE.hasOwnProperty(s)) return STATE_TOP_MARGINAL_RATE[s];
  if (STATE_NAME_TO_ABBR.hasOwnProperty(s)) return STATE_TOP_MARGINAL_RATE[STATE_NAME_TO_ABBR[s]];
  return null;
}
""".replace("__STATE_TAX_TABLE__", STATE_TAX_JS_TABLE).replace("__STATE_NAME_TO_ABBR__", STATE_NAME_TO_ABBR_JS)

# Shared itemize-vs-standard-deduction tax savings logic, used by the Mortgage, Home
# Affordability, Boat Financing, and RV Financing calculators (personal residence / qualified
# second home mortgage interest + property tax deductions). 2025 figures: standard deduction
# per Rev. Proc. 2024-40 as amended by OBBBA; SALT cap of $40,000 (2025) per OBBBA Sec. 70120,
# phasing down above $500,000 MAGI (not modeled here - flat cap used, noted in the disclaimer);
# $750,000 acquisition debt cap for loans originated after 12/15/2017 ($1,000,000 grandfathered
# for earlier loans) per the Tax Cuts and Jobs Act.
PERSONAL_ITEMIZE_JS_HELPER = """
var STANDARD_DEDUCTION_2025 = {single:15750, mfj:31500, mfs:15750, hoh:23625};
var SALT_CAP_2025 = 40000;
// Simple first-year interest estimate for a standard fixed-rate amortizing loan - used only for
// the tax savings estimators below, not for the main payment calculations elsewhere on this page.
function estimateFirstYearInterest(loanAmount, ratePct, termYears) {
  if (!loanAmount || loanAmount <= 0 || !termYears || termYears <= 0) return 0;
  var n = termYears * 12;
  var monthlyRate = (ratePct || 0) / 100 / 12;
  var pmt = calculateMonthlyPI(loanAmount, ratePct, termYears);
  var balance = loanAmount;
  var interestPaid = 0;
  for (var i = 0; i < 12 && i < n; i++) {
    var interestPortion = balance * monthlyRate;
    interestPaid += interestPortion;
    balance = Math.max(0, balance - (pmt - interestPortion));
  }
  return interestPaid;
}
function computeItemizedTaxSavings(o) {
  var debtCap = o.isPre2018Loan ? 1000000 : 750000;
  var deductibleInterest = (o.loanAmount > debtCap && o.loanAmount > 0) ? o.annualInterest * (debtCap / o.loanAmount) : o.annualInterest;
  var deductiblePropertyTax = Math.min(o.annualPropertyTax || 0, SALT_CAP_2025);
  var totalItemized = deductibleInterest + deductiblePropertyTax + (o.otherItemized || 0);
  var standardDeduction = STANDARD_DEDUCTION_2025[o.filingStatus] || STANDARD_DEDUCTION_2025.single;
  var itemizedBenefit = Math.max(0, totalItemized - standardDeduction);
  var combinedRatePct = (o.fedRatePct || 0) + (o.stateRatePct || 0);
  var taxSavings = itemizedBenefit * (combinedRatePct / 100);
  return { deductibleInterest: deductibleInterest, deductiblePropertyTax: deductiblePropertyTax,
    totalItemized: totalItemized, standardDeduction: standardDeduction,
    itemizedBenefit: itemizedBenefit, combinedRatePct: combinedRatePct, taxSavings: taxSavings, debtCap: debtCap };
}
function itemizeSavingsHtml(r, o) {
  return "<br><u>Estimated Income Tax Savings (Itemized Deductions)</u><br>" +
    "&nbsp;&nbsp;Mortgage interest (capped at $" + r.debtCap.toLocaleString() + " acquisition debt): " + money(r.deductibleInterest) + "/yr<br>" +
    "&nbsp;&nbsp;Property tax (SALT-capped at $40,000 combined with other state/local taxes): " + money(r.deductiblePropertyTax) + "/yr<br>" +
    ((o.otherItemized || 0) > 0 ? "&nbsp;&nbsp;Other itemized deductions you entered: " + money(o.otherItemized) + "/yr<br>" : "") +
    "&nbsp;&nbsp;Total itemized: " + money(r.totalItemized) + "/yr vs. standard deduction: " + money(r.standardDeduction) + "/yr<br>" +
    (r.itemizedBenefit > 0 ?
      "Amount itemizing beats the standard deduction by: <strong>" + money(r.itemizedBenefit) + "/yr</strong><br>" +
      "Estimated tax savings from itemizing: <strong style='color:#1a8a3d;'>" + money(r.taxSavings) + "/yr</strong> (" + money(r.taxSavings/12) + "/mo)<br>"
      : "<span style='color:#a5720b;'>Your itemized total (" + money(r.totalItemized) + ") doesn't exceed the standard deduction (" + money(r.standardDeduction) + "), so these deductions alone wouldn't reduce your taxes below the standard deduction - no additional tax savings shown.</span><br>") +
    "<span style='font-size:11px;color:#888;'>Estimate only, not tax advice. Mortgage interest is only deductible if you itemize, and only on acquisition debt used to buy, build, or substantially improve the home (not cash-out refinance proceeds used for other purposes). The $40,000 SALT cap (2025) is shared across ALL state/local property AND income taxes combined, phases down for income above $500,000 MAGI, and is modeled here as a flat cap - if you have other state/local taxes, your real deductible room may be lower. The $750,000/$1,000,000 acquisition debt caps apply combined across your primary home and any second home/qualifying boat or RV. Consult a CPA before relying on this for a purchase decision.</span>";
}
"""

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

# Treasury yields, corporate bond yields, and credit spreads - Federal Reserve via FRED.
# All series percent, daily. Same fetch_fred_rate() infrastructure already used above.
TREASURY_YIELDS = [
    ("3-Month Treasury", "DGS3MO"),
    ("1-Year Treasury", "DGS1"),
    ("2-Year Treasury", "DGS2"),
    ("5-Year Treasury", "DGS5"),
    ("10-Year Treasury", "DGS10"),
    ("30-Year Treasury", "DGS30"),
]

CORPORATE_BOND_SERIES = [
    ("Aaa Corporate Bond Yield", "DAAA"),
    ("Baa Corporate Bond Yield", "DBAA"),
    ("Aaa Spread over 10-Yr Treasury", "AAA10Y"),
    ("Baa Spread over 10-Yr Treasury", "BAA10Y"),
]

# Real estate: national indicators from FRED
RE_NATIONAL = [
    ("Mortgage Delinquency Rate", "DRSFRMACBS", "%"),
    ("Housing Starts (annualized)", "HOUST", "K"),
    ("Building Permits (annualized)", "PERMIT", "K"),
    ("New Home Sales (annualized)", "HSN1F", "K"),
    ("New Homes For Sale", "HNFSEPUSSA", "K"),
    ("Months of New-Home Supply", "MSACSR", "mo"),
    ("Homes Under Construction", "UNDCONTSA", "K"),
    ("Housing Completions", "COMPUTSA", "K"),
    ("30-Yr Mortgage Rate", "MORTGAGE30US", "%"),
    ("Homeownership Rate", "RSAHORUSQ156S", "%"),
    ("Rental Vacancy Rate", "RRVRUSQ156N", "%"),
    ("Homeowner Vacancy Rate", "RHVRUSQ156N", "%"),
]

# International housing: verified free data only. Each entry is (country name, nominal BIS
# series ID, real/inflation-adjusted BIS series ID). Sourced from the Bank for International
# Settlements' Residential Property Price database via FRED - the same free, no-key-cost
# infrastructure already used for every other FRED series on this site, just a different
# country code. Deliberately limited to countries actually verified to have this data -
# Bahamas, Dominican Republic, and Turks & Caicos were researched and found to have no genuine
# free official house price index (confirmed directly: a commercial real-estate-data company
# explicitly states Bahamas "does not publish official house price statistics"; what circulates
# publicly for the other two traces back to private brokerage reports, not government data).
# Argentina has some BIS data but it's Buenos Aires-only, narrow property type, and USD-
# denominated - left out for now given those caveats, not included here.
INTERNATIONAL_HOUSING = [
    ("Mexico", "QMXN628BIS", "QMXR628BIS"),
    ("Colombia", "QCON628BIS", "QCOR628BIS"),
]

# Consumer debt indicators - each tuple includes a conversion factor to normalize to Billions
# of Dollars for display, since FRED reports these in different native units: TOTALSL is in
# Millions (divide by 1000), CCLACBM027SBOG is already in Billions (factor of 1) - verified
# directly against each series' actual FRED page before including, not assumed.
CONSUMER_DEBT = [
    ("Total Consumer Credit (non-mortgage)", "TOTALSL", "$B", 1 / 1000),
    ("Credit Card Balances", "CCLACBM027SBOG", "$B", 1),
    ("Credit Card Delinquency Rate", "DRCCLACBS", "%", 1),
    ("Mortgage Delinquency Rate (Consumer)", "DRSFRMACBS", "%", 1),
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
    "Watchlist": "The stocks you've added to track.\nCounts how many tickers are currently in your watchlist table below.\nThe list itself is something you maintain - not a published data series.",
    "Oversold (RSI≤30)": "A Relative Strength Index reading of 30 or below.\nRSI measures how fast and how far a stock's price has moved recently; a low reading means it has sold off hard and fast and is sometimes due for a bounce.\nRSI is a technical indicator calculated directly from each stock's own price history, not published by any government or index agency.",
    "Overbought (RSI≥70)": "A Relative Strength Index reading of 70 or above.\nRSI measures how fast and how far a stock's price has moved recently; a high reading means it has been bought up hard and fast and is sometimes due for a pullback.\nRSI is a technical indicator calculated directly from each stock's own price history, not published by any government or index agency.",
    "Top mover": "The stock in your watchlist with the largest price move today.\nMeasures today's percentage change, up or down, across everything you're tracking.\nCalculated directly from live market price data, not a published economic series.",
    "Fed Funds Rate": "The interest rate banks charge each other for overnight loans of reserves.\nIt's the base rate the Federal Reserve uses to influence borrowing costs throughout the economy - mortgages, credit cards, and business loans all key off it.\nThe target range is set by the Federal Open Market Committee (FOMC); the actual effective rate is calculated and published daily by the Federal Reserve Bank of New York.",
    "2-Yr Treasury": "The yield on a 2-year US government bond.\nIt reflects where bond markets expect the Fed to set interest rate policy over the next couple of years.\nYields are set by Treasury auctions and tracked daily by the Federal Reserve (H.15 release).",
    "10-Yr Treasury": "The yield on a 10-year US government bond.\nIt's the benchmark long-term interest rate that drives mortgage rates and stock valuations across the economy.\nYields are set by Treasury auctions and tracked daily by the Federal Reserve (H.15 release).",
    "30-Yr Mortgage": "The average interest rate on a 30-year fixed-rate US home loan.\nIt measures the typical borrowing cost for a conventional home purchase.\nPublished weekly by Freddie Mac's Primary Mortgage Market Survey.",
    "Natl Avg Savings (FDIC)": "The national average interest rate paid on standard savings accounts.\nIt measures what a typical bank (not the high-yield outliers) pays depositors.\nPublished monthly by the FDIC.",
    "Natl Avg Money Market (FDIC)": "The national average interest rate paid on money market deposit accounts.\nIt measures typical bank money-market yields, distinct from money market mutual funds.\nPublished monthly by the FDIC.",
    "Natl Avg 12-Mo CD (FDIC)": "The national average interest rate on 12-month certificates of deposit.\nIt measures the typical yield for locking up savings for a year.\nPublished monthly by the FDIC.",
    "Natl Avg Credit Card Rate": "The average interest rate US banks charge on credit card balances.\nIt measures the typical cost of carrying a credit card balance nationally.\nPublished quarterly by the Federal Reserve (G.19 Consumer Credit release).",
    "10-Yr minus 2-Yr Spread": "The 10-year Treasury yield minus the 2-year Treasury yield.\nA negative (inverted) spread has historically preceded US recessions, since it means short-term rates exceed long-term rates.\nCalculated from Treasury yields tracked by the Federal Reserve (H.15 release).",
    "10-Yr minus 3-Mo Spread": "The 10-year Treasury yield minus the 3-month Treasury yield.\nThis version of the yield curve is the one the Federal Reserve's own research has cited as its preferred recession-signal spread.\nCalculated from Treasury yields tracked by the Federal Reserve (H.15 release).",
    "High-Yield Credit Spread": "The extra yield 'junk' (below-investment-grade) corporate bonds pay over comparable Treasuries.\nIt measures how much extra compensation investors demand for credit risk; under ~3.5% is calm, 5%+ signals building stress, 8%+ is crisis territory.\nCalculated by ICE Data Indices and published via the Federal Reserve's FRED database.",
    "CPI (Inflation)": "The Consumer Price Index, year-over-year change.\nIt measures how much the prices consumers actually pay for a broad basket of goods and services rose over the past 12 months - the most widely cited inflation gauge.\nCalculated and published monthly by the U.S. Bureau of Labor Statistics (BLS).",
    "PPI (Producer Prices)": "The Producer Price Index, year-over-year change.\nIt measures how much prices businesses receive for their output rose over the past 12 months, and often leads consumer inflation since higher input costs get passed downstream.\nCalculated and published monthly by the U.S. Bureau of Labor Statistics (BLS).",
    "Nonfarm Payrolls": "The change in US jobs last month, excluding farm work.\nIt's the headline monthly measure of hiring or layoffs across the economy.\nCalculated and published monthly by the U.S. Bureau of Labor Statistics (BLS), as part of the Employment Situation report.",
    "Retail Sales": "The month-over-month change in consumer retail spending.\nIt's a timely gauge of consumer financial health and spending momentum.\nCalculated and published monthly by the U.S. Census Bureau.",
    "ISM Manufacturing PMI": "The Institute for Supply Management's Manufacturing Purchasing Managers' Index.\nIt surveys factory purchasing managers on output, orders, and employment; a reading above 50 means manufacturing is expanding, below 50 means it's contracting.\nCalculated and published monthly by the Institute for Supply Management (ISM).",
    "Dow Jones": "The Dow Jones Industrial Average.\nA price-weighted index of 30 large US blue-chip companies, tracking the health of major established industry.\nCalculated and maintained by S&P Dow Jones Indices.",
    "S&P 500": "The Standard & Poor's 500 index.\nThe 500 largest publicly traded US companies by market value - the main benchmark for the overall US stock market.\nCalculated and maintained by S&P Dow Jones Indices.",
    "Nasdaq": "The Nasdaq Composite index.\nTracks essentially every stock listed on the Nasdaq exchange, heavily weighted toward technology companies.\nCalculated and maintained by Nasdaq, Inc.",
    "Nasdaq-100": "The Nasdaq-100 index.\nThe 100 largest non-financial companies listed on Nasdaq - a concentrated read on big tech.\nCalculated and maintained by Nasdaq, Inc.",
    "Russell 2000": "The Russell 2000 index.\nTracks 2,000 smaller-capitalization US companies, used as a gauge of smaller domestic businesses rather than multinational giants.\nCalculated and maintained by FTSE Russell.",
    "US Dollar (DXY)": "The US Dollar Index.\nMeasures the strength of the US dollar against a basket of major foreign currencies; a strong dollar tends to pressure multinational earnings and commodity prices.\nCalculated and maintained by ICE (Intercontinental Exchange).",
    "VIX (Volatility)": "The CBOE Volatility Index, the market's 'fear gauge.'\nIt measures the options market's expectation of S&P 500 volatility over the next 30 days; under 15 is calm, over 25 is fearful, over 35 is panic-level.\nCalculated and published in real time by Cboe Global Markets.",
    "Oil (WTI)": "West Texas Intermediate crude oil, price per barrel.\nThe primary US benchmark price for crude oil, used to price much of the domestic energy market.\nPriced and traded on the NYMEX exchange, operated by CME Group.",
    "Gold": "Gold, price per troy ounce.\nA classic inflation hedge and safe-haven asset that investors often turn to during economic or geopolitical stress.\nPriced and traded on the COMEX exchange (CME Group), with a benchmark also set via the LBMA.",
    "Silver": "Silver, price per troy ounce.\nPart precious metal (safe-haven demand) and part industrial metal (electronics, solar), so it responds to both investment demand and manufacturing activity.\nPriced and traded on the COMEX exchange, operated by CME Group.",
    "Copper": "Copper, price per pound.\nNicknamed 'Dr. Copper' because demand tracks construction and manufacturing activity closely, making it a widely watched economic health gauge.\nPriced and traded on the COMEX exchange, operated by CME Group.",
    "Mortgage Delinquency Rate": "The share of single-family mortgages 30+ days past due on payments.\nRising delinquencies are an early-warning sign that can lead to foreclosures down the line.\nReported by the Mortgage Bankers Association (MBA) and tracked via the Federal Reserve's FRED database.",
    "Housing Starts (annualized)": "New homes that began construction, expressed as an annualized pace in thousands of units.\nIt's a direct read on homebuilder activity and confidence.\nCalculated and published monthly by the U.S. Census Bureau, jointly with HUD.",
    "Building Permits (annualized)": "Permits issued for future home construction, annualized in thousands of units.\nA leading indicator for housing starts, since permits are typically pulled before construction begins.\nCalculated and published monthly by the U.S. Census Bureau, jointly with HUD.",
    "New Home Sales (annualized)": "Newly built single-family homes sold, annualized in thousands of units.\nMeasures actual buyer demand for new construction, as opposed to starts/permits which measure builder activity.\nCalculated and published monthly by the U.S. Census Bureau, jointly with HUD.",
    "New Homes For Sale": "The number of new single-family homes on the market and not yet sold, in thousands of units.\nMeasures how much new-construction inventory is sitting available for buyers right now - the numerator behind Months of New-Home Supply.\nCalculated and published monthly by the U.S. Census Bureau, jointly with HUD.",
    "Months of New-Home Supply": "How many months it would take to sell through all new homes currently for sale, at the current sales pace.\nA rising figure means new-home inventory is building up relative to sales (a cooling market); a falling figure means new homes are selling faster than they're being listed (a tightening market). Historically, 4-6 months is considered a roughly balanced market.\nCalculated and published monthly by the U.S. Census Bureau, jointly with HUD.",
    "Homes Under Construction": "New privately-owned housing units that have been started but not yet finished, annualized in thousands of units.\nMeasures the pipeline of housing supply that's actively being built right now - between Housing Starts (ground broken) and Housing Completions (ready for occupancy).\nCalculated and published monthly by the U.S. Census Bureau, jointly with HUD.",
    "Housing Completions": "New privately-owned housing units finished and ready for occupancy, annualized in thousands of units.\nMeasures new supply actually hitting the market, the final step after Housing Starts and Homes Under Construction - a leading indicator for how much new inventory buyers and renters will soon have to choose from.\nCalculated and published monthly by the U.S. Census Bureau, jointly with HUD.",
    "30-Yr Mortgage Rate": "The average interest rate on a 30-year fixed-rate US home loan.\nIt measures the typical borrowing cost for a conventional home purchase.\nPublished weekly by Freddie Mac's Primary Mortgage Market Survey.",
    "Homeownership Rate": "The share of occupied housing units that are owned (rather than rented) by their occupants.\nA broad gauge of housing affordability and access - it tends to fall when home prices or mortgage rates rise faster than incomes.\nCalculated and published quarterly by the U.S. Census Bureau's Housing Vacancies and Homeownership survey.",
    "Rental Vacancy Rate": "The share of rental housing units that are vacant and available for rent.\nA rising rate signals softer demand or oversupply in rental markets (downward pressure on rents); a falling rate signals a tightening market.\nCalculated and published quarterly by the U.S. Census Bureau's Housing Vacancies and Homeownership survey.",
    "Homeowner Vacancy Rate": "The share of owner-occupied-eligible housing units that are vacant and for sale.\nA rising rate can signal softening demand for home purchases; a falling rate signals tighter for-sale inventory.\nCalculated and published quarterly by the U.S. Census Bureau's Housing Vacancies and Homeownership survey.",
    "International Residential Property Prices": "Year-over-year home price growth for a country, shown both as a nominal figure and adjusted for inflation (the inflation-adjusted version is often called the real figure).\nUnlike US-only figures, these come from each country's own national data source as compiled by an international body, so methodology and coverage can vary - for example, Colombia's figure covers 8 major cities rather than the whole country.\nCalculated and published quarterly by the Bank for International Settlements' Residential Property Price database, using each country's own central bank or statistics agency as the underlying source.",
    "CPI Inflation (YoY)": "The Consumer Price Index, year-over-year change.\nIt measures how much prices consumers actually pay for a broad basket of goods and services rose over the past 12 months - the most widely cited inflation gauge, and the one compared here to the Fed's 2% target.\nCalculated and published monthly by the U.S. Bureau of Labor Statistics (BLS).",
    "Core PCE Inflation (YoY)": "Core Personal Consumption Expenditures Price Index, year-over-year change.\nIt measures inflation in consumer spending but excludes food and energy, since those categories are volatile and can distort the underlying trend.\nCalculated and published monthly by the Bureau of Economic Analysis (BEA), and it's the Federal Reserve's own preferred inflation gauge for setting monetary policy.",
    "Unemployment Rate": "The share of the labor force that is jobless and actively looking for work.\nIt measures labor-market slack; the Fed watches it alongside inflation as part of its dual mandate (maximum employment and stable prices).\nCalculated and published monthly by the U.S. Bureau of Labor Statistics (BLS), based on the Current Population Survey.",
    "Real GDP Growth (YoY)": "Real Gross Domestic Product, year-over-year change, adjusted for inflation.\nIt measures the total growth of everything the US economy produces, stripped of price changes so it reflects actual output growth.\nCalculated and published quarterly by the Bureau of Economic Analysis (BEA).",
    "Effective Fed Funds Rate": "The actual (as opposed to targeted) overnight rate banks charge each other for reserves.\nIt shows where the Fed Funds rate is really trading within the FOMC's announced target range, compared here to the Fed's own longer-run 'neutral rate' estimate.\nCalculated and published daily by the Federal Reserve Bank of New York.",
    "Nasdaq Composite": "Tracks essentially every stock listed on the Nasdaq exchange, heavily weighted toward technology.\nA broader read on the Nasdaq market than the Nasdaq-100, since it includes smaller and mid-sized companies too.\nCalculated and maintained by Nasdaq, Inc.",
    "Russell 1000": "Tracks the largest 1,000 US companies by market capitalization.\nIt's the large-cap complement to the Russell 2000's small-caps, together making up most of the US stock market's total value.\nCalculated and maintained by FTSE Russell.",
    "S&P MidCap 400": "Tracks 400 mid-sized US companies.\nIt fills the gap between large-cap indexes like the S&P 500 and small-cap indexes like the Russell 2000, gauging the health of the market's middle tier.\nCalculated and maintained by S&P Dow Jones Indices.",
    "FTSE 100 (UK)": "The 100 largest companies listed on the London Stock Exchange by market value.\nTracks the health of the UK's largest public companies, many of which are large multinationals earning most revenue abroad.\nCalculated and maintained by FTSE Russell.",
    "DAX (Germany)": "Germany's blue-chip index of 40 major companies listed on the Frankfurt Stock Exchange.\nTracks the health of Germany's largest public companies - Europe's biggest economy.\nCalculated and maintained by Deutsche Börse (via its STOXX subsidiary).",
    "CAC 40 (France)": "France's benchmark index of the 40 largest companies listed on Euronext Paris.\nTracks the health of France's largest public companies.\nCalculated and maintained by Euronext.",
    "Euro Stoxx 50": "An index of 50 large-cap companies spanning multiple eurozone countries.\nTracks the broader eurozone blue-chip market as a whole, rather than any single country's exchange.\nCalculated and maintained by STOXX, a Deutsche Börse Group company.",
    "IBEX 35 (Spain)": "Spain's benchmark index of the 35 most liquid stocks on the Madrid exchange.\nTracks the health of Spain's largest public companies.\nCalculated and maintained by BME (Bolsas y Mercados Españoles), part of SIX Group.",
    "FTSE MIB (Italy)": "Italy's benchmark index of roughly the 40 most-traded companies on the Milan exchange.\nTracks the health of Italy's largest public companies.\nCalculated and maintained by FTSE Russell in partnership with Borsa Italiana.",
    "Nikkei 225 (Japan)": "Japan's most widely quoted stock index, tracking 225 large companies on the Tokyo Stock Exchange.\nIt's price-weighted (like the Dow), and tracks the health of Japan's largest public companies.\nCalculated and published by Nikkei Inc.",
    "Hang Seng (Hong Kong)": "Hong Kong's benchmark index of major companies listed on the Hong Kong Stock Exchange.\nTracks large-cap Hong Kong-listed stocks, many with significant mainland Chinese business ties.\nCalculated and maintained by Hang Seng Indexes Company.",
    "Shanghai Composite (China)": "Tracks all stocks listed on the Shanghai Stock Exchange.\nThe broadest widely cited gauge of mainland Chinese equities.\nCalculated and maintained by the Shanghai Stock Exchange.",
    "Sensex (India)": "India's benchmark index of the 30 largest, most actively traded companies on the Bombay Stock Exchange.\nTracks the health of India's largest public companies.\nCalculated and maintained by BSE Ltd. (the Bombay Stock Exchange).",
    "Nifty 50 (India)": "India's other major benchmark index, tracking the 50 largest companies on the National Stock Exchange of India.\nPlays a similar role to the Sensex, but on a different exchange with a different constituent list.\nCalculated and maintained by NSE Indices Limited.",
    "KOSPI (South Korea)": "South Korea's benchmark index of all common stocks listed on the Korea Exchange.\nTracks the health of South Korea's public equity market, heavily weighted toward tech and semiconductor exporters.\nCalculated and maintained by the Korea Exchange (KRX).",
    "ASX 200 (Australia)": "Australia's benchmark index of the 200 largest companies on the Australian Securities Exchange.\nTracks the health of Australia's largest public companies, heavily weighted toward mining and banks.\nCalculated and maintained by S&P Dow Jones Indices.",
    "Taiwan Weighted": "Taiwan's benchmark index tracking all listed common shares on the Taiwan Stock Exchange.\nHeavily weighted toward semiconductor manufacturers, making it a closely watched gauge for the global chip supply chain.\nCalculated and maintained by the Taiwan Stock Exchange.",
    "TSX Composite (Canada)": "Canada's benchmark index tracking the largest companies on the Toronto Stock Exchange.\nTracks the health of Canada's largest public companies, heavily weighted toward financials and energy/mining.\nCalculated and maintained by TMX Group.",
    "Bovespa (Brazil)": "Brazil's benchmark index tracking the most actively traded stocks on B3, Brazil's main exchange.\nTracks the health of Brazil's largest public companies.\nCalculated and maintained by B3 S.A.",
    "IPC (Mexico)": "Mexico's benchmark index tracking the largest, most liquid stocks on the Mexican Stock Exchange (BMV).\nTracks the health of Mexico's largest public companies.\nCalculated and maintained by S&P Dow Jones Indices in partnership with the BMV.",
    "SMI (Switzerland)": "Switzerland's benchmark index of its 20 largest, most liquid stocks.\nTracks the health of Switzerland's largest public companies.\nCalculated and maintained by SIX Swiss Exchange.",
    "AEX (Netherlands)": "The Netherlands' benchmark index of the largest companies on Euronext Amsterdam.\nTracks the health of the Netherlands' largest public companies.\nCalculated and maintained by Euronext.",
    "OMX Stockholm 30 (Sweden)": "Sweden's benchmark index of the 30 most-traded stocks on the Stockholm exchange.\nTracks the health of Sweden's largest public companies.\nCalculated and maintained by Nasdaq, which operates the Stockholm exchange.",
    "BEL 20 (Belgium)": "Belgium's benchmark index of the 20 largest companies on Euronext Brussels.\nTracks the health of Belgium's largest public companies.\nCalculated and maintained by Euronext.",
    "ATX (Austria)": "Austria's benchmark index tracking the largest companies on the Vienna Stock Exchange.\nTracks the health of Austria's largest public companies.\nCalculated and maintained by Wiener Börse (the Vienna Stock Exchange).",
    "ISEQ (Ireland)": "Ireland's benchmark index tracking companies listed on Euronext Dublin.\nTracks the health of Ireland's largest public companies.\nCalculated and maintained by Euronext.",
    "Straits Times (Singapore)": "Singapore's benchmark index of the 30 largest companies on the Singapore Exchange.\nTracks the health of Singapore's largest public companies, a major regional financial hub.\nCalculated and maintained by the Singapore Exchange (SGX) in partnership with FTSE Russell.",
    "KLCI (Malaysia)": "Malaysia's benchmark index of the 30 largest companies on Bursa Malaysia.\nTracks the health of Malaysia's largest public companies.\nCalculated and maintained by FTSE Russell in partnership with Bursa Malaysia.",
    "Jakarta Composite (Indonesia)": "Indonesia's benchmark index tracking all common shares on the Indonesia Stock Exchange.\nTracks the broad health of Indonesia's public equity market.\nCalculated and maintained by the Indonesia Stock Exchange.",
    "NZX 50 (New Zealand)": "New Zealand's benchmark index of the 50 largest companies on the NZX exchange.\nTracks the health of New Zealand's largest public companies.\nCalculated and maintained by NZX Limited.",
    "JSE Top 40 (South Africa)": "South Africa's benchmark index of the 40 largest companies on the Johannesburg Stock Exchange.\nTracks the health of South Africa's largest public companies, heavily weighted toward mining and resources.\nCalculated and maintained by the JSE, in partnership with FTSE Russell.",
    "S&P 500 Futures (E-mini)": "A futures contract tracking the S&P 500 index, tradable nearly 24 hours a day.\nSince it trades outside normal stock market hours, it shows where traders expect the S&P 500 to open - a preview of sentiment before the cash market opens.\nTraded on the CME (Chicago Mercantile Exchange).",
    "Dow Futures (E-mini)": "A futures contract tracking the Dow Jones Industrial Average, tradable nearly 24 hours a day.\nSince it trades outside normal stock market hours, it shows where traders expect the Dow to open.\nTraded on the CBOT (Chicago Board of Trade), part of CME Group.",
    "Nasdaq-100 Futures (E-mini)": "A futures contract tracking the Nasdaq-100 index, tradable nearly 24 hours a day.\nSince it trades outside normal stock market hours, it shows where traders expect tech-heavy Nasdaq-100 stocks to open.\nTraded on the CME (Chicago Mercantile Exchange).",
    "Russell 2000 Futures (E-mini)": "A futures contract tracking the Russell 2000 small-cap index, tradable nearly 24 hours a day.\nSince it trades outside normal stock market hours, it shows where traders expect small-cap stocks to open.\nTraded on the ICE (Intercontinental Exchange).",
    "Nikkei 225 Futures": "A futures contract tracking Japan's Nikkei 225 index.\nSince Japanese markets open while US markets are closed, this gives US investors an overnight read on how Japanese equities are trading.\nTraded on the Osaka Exchange, CME, and SGX (Singapore Exchange), depending on the contract.",
    "Oil (Brent)": "Brent crude oil, price per barrel.\nThe primary international benchmark for oil prices (as opposed to WTI, the US benchmark) - most oil outside the Americas is priced off Brent.\nPriced and traded on ICE (Intercontinental Exchange).",
    "Natural Gas": "Natural gas, price per million British thermal units (MMBtu).\nA key input cost for heating, electricity generation, and industrial use - prices swing heavily with weather and storage levels.\nPriced and traded on the NYMEX exchange, operated by CME Group.",
    "Heating Oil": "Heating oil, price per gallon.\nA refined petroleum product used for home heating and as a proxy for diesel/distillate fuel costs.\nPriced and traded on the NYMEX exchange, operated by CME Group.",
    "RBOB Gasoline": "RBOB (Reformulated Blendstock for Oxygenate Blending) gasoline, price per gallon.\nThe wholesale gasoline benchmark used to price fuel before retail markup and taxes - a leading indicator for pump prices.\nPriced and traded on the NYMEX exchange, operated by CME Group.",
    "Platinum": "Platinum, price per troy ounce.\nUsed heavily in catalytic converters and jewelry, so it responds to both industrial (especially auto) demand and precious-metal investment demand.\nPriced and traded on the NYMEX exchange, operated by CME Group.",
    "Palladium": "Palladium, price per troy ounce.\nUsed primarily in catalytic converters for gasoline engines, making it closely tied to auto production and emissions regulations.\nPriced and traded on the NYMEX exchange, operated by CME Group.",
    "Corn": "Corn, price per bushel.\nA major agricultural commodity used for food, animal feed, and ethanol - prices are sensitive to weather, planting reports, and biofuel demand.\nPriced and traded on the CBOT (Chicago Board of Trade), part of CME Group.",
    "Wheat": "Wheat, price per bushel.\nA staple food-grain commodity; prices are sensitive to global harvests and geopolitical disruptions in major growing regions.\nPriced and traded on the CBOT (Chicago Board of Trade), part of CME Group.",
    "Soybeans": "Soybeans, price per bushel.\nA major crop used for animal feed, cooking oil, and food products; US-China trade relations have historically been a significant price driver.\nPriced and traded on the CBOT (Chicago Board of Trade), part of CME Group.",
    "Soybean Oil": "Soybean oil, price per pound.\nA processed soybean product used in cooking oil and, increasingly, biodiesel production.\nPriced and traded on the CBOT (Chicago Board of Trade), part of CME Group.",
    "Coffee": "Coffee (Arabica), price per pound.\nA tropical soft commodity heavily influenced by weather in major growing regions like Brazil and Vietnam.\nPriced and traded on ICE (Intercontinental Exchange).",
    "Cotton": "Cotton, price per pound.\nA key input for the textile industry, sensitive to both agricultural conditions and global apparel demand.\nPriced and traded on ICE (Intercontinental Exchange).",
    "Sugar": "Sugar, price per pound.\nA soft commodity used in food and, in some countries, ethanol production; supply is concentrated among a handful of major producing nations.\nPriced and traded on ICE (Intercontinental Exchange).",
    "Cocoa": "Cocoa, price per metric ton.\nThe raw input for chocolate production, with supply concentrated in a small number of West African countries, making it prone to sharp price swings.\nPriced and traded on ICE (Intercontinental Exchange).",
    "Live Cattle": "Live cattle, price per pound.\nTracks prices for cattle ready for slaughter, a key input cost for the beef industry.\nPriced and traded on the CME (Chicago Mercantile Exchange).",
    "Lean Hogs": "Lean hogs, price per pound.\nTracks prices for hogs ready for slaughter, a key input cost for the pork industry.\nPriced and traded on the CME (Chicago Mercantile Exchange).",
    "Total Consumer Credit (non-mortgage)": "Total outstanding consumer credit, revolving (credit cards) and non-revolving (auto loans, student loans), excluding home mortgages.\nMeasures how much US households owe outside of housing debt - a gauge of consumer borrowing and financial stress.\nCalculated and published monthly by the Federal Reserve (G.19 Consumer Credit release).",
    "Credit Card Balances": "Total outstanding credit card debt held by US consumers.\nA subset of total consumer credit specifically covering revolving debt, which typically carries the highest average interest rates.\nCalculated and published by the Federal Reserve, tracked via FRED.",
    "Credit Card Delinquency Rate": "The share of credit card balances 30+ days past due.\nA leading indicator of consumer financial stress - rising delinquencies often precede pullbacks in consumer spending or tighter lending standards.\nCalculated and published quarterly by the Federal Reserve.",
    "Mortgage Delinquency Rate (Consumer)": "The share of single-family mortgages 30+ days past due, shown here alongside other consumer debt metrics rather than the housing-specific section.\nSame underlying data as the Mortgage Delinquency Rate shown elsewhere on this site.\nCalculated and published by the Federal Reserve, tracked via FRED.",
    "Bitcoin": "The original and largest cryptocurrency by market value.\nA decentralized digital currency not issued by any government or central bank, often described as 'digital gold' due to its capped 21 million coin supply.\nTracked via public blockchain data; price shown here reflects trading on major exchanges via Yahoo Finance.",
    "Ethereum": "The second-largest cryptocurrency by market value.\nUnlike Bitcoin, its blockchain runs programmable 'smart contracts,' making it the base layer for most decentralized finance (DeFi) applications.\nTracked via public blockchain data; price shown here reflects trading on major exchanges via Yahoo Finance.",
    "Tether": "A 'stablecoin' designed to hold a constant value of $1 USD, issued by Tether Limited.\nBacked by reserves the company says it holds in cash and cash equivalents; used mainly as a stable trading pair on crypto exchanges rather than as a speculative investment.\nPrice tracked via major exchanges through Yahoo Finance.",
    "BNB": "The native token of the Binance exchange and its associated blockchain.\nUsed to pay reduced trading fees on Binance and as the 'gas' token for transactions on the BNB Chain blockchain.\nPrice tracked via major exchanges through Yahoo Finance.",
    "Solana": "A blockchain designed for high transaction speed and low fees, positioning itself as an alternative to Ethereum for decentralized applications.\nIts native token (SOL) is used to pay transaction fees on the network.\nPrice tracked via major exchanges through Yahoo Finance.",
    "XRP": "The native token of the XRP Ledger, a blockchain created by Ripple Labs designed for fast, low-cost cross-border payments.\nIts price and use have been closely tied to Ripple's ongoing relationships with banks and payment providers.\nPrice tracked via major exchanges through Yahoo Finance.",
    "USD Coin": "A 'stablecoin' designed to hold a constant value of $1 USD, issued by Circle.\nBacked by cash and short-term US Treasury holdings, with regular attestations of its reserves; used mainly as a stable trading pair rather than a speculative investment.\nPrice tracked via major exchanges through Yahoo Finance.",
    "Cardano": "A blockchain platform for smart contracts and decentralized applications, notable for its academic, peer-reviewed approach to development.\nIts native token (ADA) is used to pay transaction fees on the network.\nPrice tracked via major exchanges through Yahoo Finance.",
    "Dogecoin": "Originally created in 2013 as a joke based on the 'Doge' internet meme.\nIt has since become one of the largest cryptocurrencies by market value despite having no specific technical purpose beyond simple payments.\nPrice tracked via major exchanges through Yahoo Finance.",
    "TRON": "A blockchain platform focused on content-sharing and decentralized applications, also widely used as a low-fee network for transferring stablecoins like Tether.\nIts native token is TRX.\nPrice tracked via major exchanges through Yahoo Finance.",
    "Avalanche": "A blockchain platform designed for fast transaction finality and high throughput, used for decentralized finance and custom blockchain deployments.\nIts native token (AVAX) is used to pay network fees.\nPrice tracked via major exchanges through Yahoo Finance.",
    "Chainlink": "A network that supplies external, real-world data (like asset prices) to blockchains, which can't natively access outside information on their own.\nIts native token (LINK) is used to pay for these data services.\nPrice tracked via major exchanges through Yahoo Finance.",
    "Polkadot": "A blockchain platform designed to let multiple separate blockchains ('parachains') communicate and share security with one another.\nIts native token (DOT) is used for network governance and securing parachain slots.\nPrice tracked via major exchanges through Yahoo Finance.",
    "Litecoin": "One of the earliest Bitcoin-derived cryptocurrencies, created in 2011 with faster block times and a larger total coin supply than Bitcoin.\nOften described as 'silver to Bitcoin's gold.'\nPrice tracked via major exchanges through Yahoo Finance.",
    "Shiba Inu": "A token created in 2020 as a Dogecoin-inspired 'meme coin,' with no specific technical purpose.\nIts price has historically been driven largely by social media attention and speculative trading rather than underlying utility.\nPrice tracked via major exchanges through Yahoo Finance.",
    "Bitcoin Cash": "A cryptocurrency created in 2017 when a group of Bitcoin developers disagreed over how to scale the network and split off ('forked') their own blockchain with larger block sizes.\nDesigned as a more payments-focused alternative to Bitcoin.\nPrice tracked via major exchanges through Yahoo Finance.",
    "Stellar": "A blockchain platform designed for fast, low-cost cross-border payments and asset transfers, with a particular focus on connecting financial institutions in developing markets.\nIts native token is XLM (Lumens).\nPrice tracked via major exchanges through Yahoo Finance.",
    "Euro": "The official currency of the eurozone - the 20 European Union member states that have adopted it, including Germany, France, Italy, and Spain.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "British Pound": "The official currency of the United Kingdom.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Australian Dollar": "The official currency of Australia.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "New Zealand Dollar": "The official currency of New Zealand.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Japanese Yen": "The official currency of Japan.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Chinese Yuan": "The official currency of mainland China, also called the renminbi.\nIts exchange rate is managed within a band set by China's central bank, rather than freely floating like most other currencies on this page.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Canadian Dollar": "The official currency of Canada.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Mexican Peso": "The official currency of Mexico.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Swiss Franc": "The official currency of Switzerland, often sought as a safe-haven currency during periods of global market stress.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Hong Kong Dollar": "The official currency of Hong Kong, which operates under a currency board system pegging it to the US dollar within a tight band.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "South Korean Won": "The official currency of South Korea.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Indian Rupee": "The official currency of India.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Brazilian Real": "The official currency of Brazil.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Malaysian Ringgit": "The official currency of Malaysia.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Thai Baht": "The official currency of Thailand.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Taiwan Dollar": "The official currency of Taiwan.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "South African Rand": "The official currency of South Africa.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Singapore Dollar": "The official currency of Singapore.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Swedish Krona": "The official currency of Sweden.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Norwegian Krone": "The official currency of Norway.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Danish Krone": "The official currency of Denmark, pegged to the Euro within a narrow band as part of the European Exchange Rate Mechanism.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Sri Lankan Rupee": "The official currency of Sri Lanka.\nExchange rate shown here is against the US dollar.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "Venezuelan Bolivar": "The official currency of Venezuela, which has experienced extreme hyperinflation in recent years.\nThis makes historical comparisons of its exchange rate of limited use.\nPublished daily by the Federal Reserve (H.10 foreign exchange release).",
    "3-Month Treasury": "Yield on a US government bond maturing in 3 months.\nReflects near-term interest rate expectations and is closely tied to the Fed's current policy rate.\nCalculated and published daily by the Federal Reserve (H.15 release).",
    "1-Year Treasury": "Yield on a US government bond maturing in 1 year.\nReflects market expectations for Fed policy over the coming year.\nCalculated and published daily by the Federal Reserve (H.15 release).",
    "2-Year Treasury": "Yield on a US government bond maturing in 2 years.\nA widely watched gauge of near/medium-term Fed policy expectations.\nCalculated and published daily by the Federal Reserve (H.15 release).",
    "5-Year Treasury": "Yield on a US government bond maturing in 5 years.\nBridges short-term policy expectations and longer-term growth/inflation expectations.\nCalculated and published daily by the Federal Reserve (H.15 release).",
    "10-Year Treasury": "Yield on a US government bond maturing in 10 years.\nThe benchmark long-term rate that heavily influences mortgage rates and stock valuations.\nCalculated and published daily by the Federal Reserve (H.15 release).",
    "30-Year Treasury": "Yield on a US government bond maturing in 30 years.\nThe longest-dated widely tracked Treasury yield, reflecting very long-term growth and inflation expectations.\nCalculated and published daily by the Federal Reserve (H.15 release).",
    "Aaa Corporate Bond Yield": "The average yield on US corporate bonds rated Aaa by Moody's - the highest possible credit rating, indicating the lowest default risk among corporate borrowers.\nA benchmark for the cheapest corporate borrowing costs available.\nCalculated by Moody's; tracked via the Federal Reserve's FRED database.",
    "Baa Corporate Bond Yield": "The average yield on US corporate bonds rated Baa by Moody's - the lowest investment-grade rating, one step above 'junk' status.\nWidely used as a gauge of borrowing costs for more moderately-rated companies.\nCalculated by Moody's; tracked via the Federal Reserve's FRED database.",
    "Aaa Spread over 10-Yr Treasury": "The extra yield Aaa-rated corporate bonds pay over the 10-Year Treasury.\nMeasures the minimum credit risk premium investors demand even for the safest corporate borrowers.\nCalculated from Moody's and Federal Reserve data, tracked via FRED.",
    "Baa Spread over 10-Yr Treasury": "The extra yield Baa-rated corporate bonds pay over the 10-Year Treasury.\nA widely watched gauge of overall corporate credit risk appetite - a widening spread often signals rising recession or default fears.\nCalculated from Moody's and Federal Reserve data, tracked via FRED.",
    "State Home Price Index (FHFA)": "The percent change in home prices over the past year for a given US state.\nMeasures regional housing market strength using repeat sales and refinance data on the same homes over time, rather than raw median sale prices (which can be skewed by what happened to be sold that period).\nCalculated and published quarterly by the Federal Housing Finance Agency (FHFA).",
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
  <a href="propertymanager.html" style="margin-right:16px;font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">Property Manager</a>
  <a href="portfolio.html" style="margin-right:16px;font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">My Portfolio</a>
  <a href="investment-map.html" style="margin-right:16px;font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">Investment Map</a>
  <a href="insights.html" style="margin-right:16px;font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">Market Insights</a>
  <a href="glossary.html" style="margin-right:16px;font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">Glossary</a>
  <a href="educators.html" style="font-size:14px;color:#1f4e79;text-decoration:none;font-weight:600;">For Educators &amp; Students</a>
</div>
"""

FOOTER_HTML = """
<hr style="margin:32px 0 16px;border:none;border-top:1px solid var(--card-border);">
<div style="font-size:12px;color:var(--text-faint);padding-bottom:20px;">
  <a href="terms.html" style="margin-right:14px;color:var(--text-faint);text-decoration:underline;">Terms of Service</a>
  <a href="privacy.html" style="margin-right:14px;color:var(--text-faint);text-decoration:underline;">Privacy Policy</a>
  <a href="refund-policy.html" style="color:var(--text-faint);text-decoration:underline;">Cancellation &amp; Refund Policy</a>
  <p style="margin:8px 0 0;">&copy; 2026 Winners Stock LLC. Stock Digest is provided for informational and educational purposes only and is not financial, investment, legal, or tax advice.</p>
</div>
"""

PAGE_CSS = """
:root {
  --bg: #f7f7f5;
  --text: #111;
  --text-secondary: #666;
  --text-muted: #888;
  --text-faint: #999;
  --card-bg: #fff;
  --card-border: #e5e3dc;
  --table-header-bg: #f0efe9;
  --table-row-border: #eee;
}
body { font-family: -apple-system, sans-serif; background:var(--bg); color:var(--text); margin:0; padding:24px; }
h1 { font-size:20px; margin:0 0 4px; color:var(--text); }
h2 { font-size:15px; margin:24px 0 10px; color:var(--text-secondary); }
.timestamp { color:var(--text-secondary); font-size:13px; margin:0 0 20px; }
.summary { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:8px; }
.row { display:flex; gap:12px; margin-bottom:8px; flex-wrap:wrap; }
.card { background:var(--card-bg); border-radius:10px; padding:14px; border:1px solid var(--card-border); flex:1; min-width:150px; cursor:help; }
.label { font-size:12px; color:var(--text-secondary); margin:0 0 4px; }
.value { font-size:20px; font-weight:600; margin:0; color:var(--text); }
.sixmo { font-size:11px; color:var(--text-muted); margin:4px 0 0; }
.table-wrap { overflow-x:auto; }
table { width:100%; border-collapse:collapse; background:var(--card-bg); border-radius:10px; overflow:hidden; }
th { text-align:left; padding:8px 10px; background:var(--table-header-bg); font-size:12px; color:var(--text-secondary); font-weight:600; white-space:nowrap; }
td { padding:8px 10px; border-top:1px solid var(--table-row-border); font-size:13px; white-space:nowrap; color:var(--text); }
.note { font-size:11px; color:var(--text-faint); margin:6px 0 0; }
"""

# Reusable across every page (not just Stocks & Rates) - site-wide dark mode using a single
# shared localStorage key, so toggling on any one page applies everywhere. Covers both the
# shared PAGE_CSS elements (via the --variables it already defines) and the common page-specific
# patterns (calculator boxes, inputs/selects, tabs, tables) that use hardcoded light colors.
DARK_MODE_CSS = """
body.dark-mode {
  --bg: #0d0d0d;
  --text: #e8e8e8;
  --text-secondary: #b0b0b0;
  --text-muted: #909090;
  --text-faint: #787878;
  --card-bg: #1a1a1a;
  --card-border: #333;
  --table-header-bg: #222;
  --table-row-border: #2a2a2a;
}
#theme-toggle {
  position: fixed; top: 16px; right: 16px; z-index: 1000;
  padding: 8px 14px; font-size: 13px; font-weight: 600;
  background: var(--card-bg); color: var(--text); border: 1px solid var(--card-border);
  border-radius: 20px; cursor: pointer;
}
body.dark-mode .calc, body.dark-mode .calc-wide { background: var(--card-bg); border-color: var(--card-border); color: var(--text); }
body.dark-mode .result { background: #16281a; color: var(--text); }
body.dark-mode input, body.dark-mode select, body.dark-mode textarea {
  background: var(--card-bg); color: var(--text); border-color: var(--card-border);
}
body.dark-mode .calc-tab-btn { background: var(--card-bg); color: var(--text); border-color: var(--card-border); }
body.dark-mode .calc-tab-btn.active { background: #1f4e79; color: #fff; }
body.dark-mode label { color: var(--text-secondary); }
body.dark-mode table { background: var(--card-bg); }
body.dark-mode th { background: var(--table-header-bg); color: var(--text); }
body.dark-mode td { color: var(--text); border-color: var(--table-row-border); }
body.dark-mode .suggest-btn { background: #1a2f42; color: #9cc4e0; border-color: #2a4258; }
"""

DARK_MODE_BUTTON = '<button id="theme-toggle" onclick="toggleTheme()">&#9680; Dark Mode</button>\n'

DARK_MODE_JS = """
(function() {
  var saved = localStorage.getItem('siteDarkMode');
  if (saved === 'dark') {
    document.addEventListener('DOMContentLoaded', function() {
      document.body.classList.add('dark-mode');
      var btn = document.getElementById('theme-toggle');
      if (btn) btn.innerHTML = '&#9728; Light Mode';
    });
  }
})();
function toggleTheme() {
  var isDark = document.body.classList.toggle('dark-mode');
  localStorage.setItem('siteDarkMode', isDark ? 'dark' : 'light');
  var btn = document.getElementById('theme-toggle');
  if (btn) btn.innerHTML = isDark ? '&#9728; Light Mode' : '&#9680; Dark Mode';
}
"""

# Site-wide Learning Mode toggle, using the same shared-localStorage-key pattern as Dark Mode
# above, so toggling it on any page carries over to every other page. Matches index.html's
# inline implementation exactly (same button id, class names, and localStorage key) so state
# stays in sync regardless of which page it was toggled on.
LEARNING_MODE_CSS = """
.learning-mode-only { display: none; }
body.learning-mode .learning-mode-only { display: block; }
tr.learning-mode-only { display: none; }
body.learning-mode tr.learning-mode-only { display: table-row; }
.beginner-box { background: #eef6f0; border:1px solid #cfe8d6; border-radius:10px; padding:14px 16px; margin-bottom:16px; }
.beginner-box h3 { margin:0 0 8px; font-size:14px; }
.beginner-box ul { margin:0; padding-left:18px; font-size:13px; line-height:1.6; }
body.dark-mode .beginner-box { background:#132a1a; border-color:#1e4a2c; }
"""

LEARNING_MODE_BUTTON = '<button id="learning-mode-toggle" onclick="toggleLearningMode()">&#127891; Learning Mode: Off</button>\n'

LEARNING_MODE_JS = """
(function() {
  var savedLearning = localStorage.getItem('siteLearningMode');
  if (savedLearning === 'on') {
    document.addEventListener('DOMContentLoaded', function() {
      document.body.classList.add('learning-mode');
      var btn = document.getElementById('learning-mode-toggle');
      if (btn) btn.innerHTML = '&#127891; Learning Mode: On';
    });
  }
})();
function toggleLearningMode() {
  var isOn = document.body.classList.toggle('learning-mode');
  localStorage.setItem('siteLearningMode', isOn ? 'on' : 'off');
  var btn = document.getElementById('learning-mode-toggle');
  if (btn) btn.innerHTML = isOn ? '&#127891; Learning Mode: On' : '&#127891; Learning Mode: Off';
}
"""

# Site-wide bar/line sparkline toggle, using the same shared-localStorage-key pattern as Dark
# Mode and Learning Mode above. Previously this only existed inline on the stocks page (the only
# page that used it when it was first built) - extracted here so any other page with sparklines
# (e.g. Real Estate) gets the exact same toggle button and behavior, not a page missing it
# entirely. Renamed the localStorage key from the old page-specific "stocksPageChartMode" to
# "siteChartMode" to match the siteDarkMode/siteLearningMode naming convention, now that this is
# genuinely a site-wide preference rather than a stocks-page-only one.
CHART_MODE_CSS = """
#chart-mode-toggle {
  position: fixed; top: 56px; right: 16px; z-index: 1000;
  padding: 8px 14px; font-size: 13px; font-weight: 600;
  background: var(--card-bg); color: var(--text); border: 1px solid var(--card-border);
  border-radius: 20px; cursor: pointer;
}
.sparkline { display: block; margin-top: 6px; }
"""

CHART_MODE_BUTTON = '<button id="chart-mode-toggle" onclick="toggleAllSparklineType()">&#128202; View as Bars</button>\n'

CHART_MODE_JS = """
function renderSparklineAsMode(svg, mode) {
  var values = svg.getAttribute('data-values').split(',').map(Number).filter(function(v) { return !isNaN(v); });
  svg.setAttribute('data-mode', mode);
  var width = parseFloat(svg.getAttribute('width'));
  var height = parseFloat(svg.getAttribute('height'));
  var n = values.length;
  if (n < 2) return; // not enough valid data to draw anything meaningful
  var lo = Math.min.apply(null, values);
  var hi = Math.max.apply(null, values);
  var span = hi - lo;
  var color = values[n - 1] > values[0] ? '#1a8a3d' : values[n - 1] < values[0] ? '#c0392b' : '#999';
  var content;
  if (mode === 'line') {
    var points = values.map(function(v, i) {
      var x = (n === 1) ? width / 2 : (i / (n - 1)) * (width - 4) + 2;
      var y = span === 0 ? height / 2 : height - 2 - ((v - lo) / span) * (height - 4);
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    content = '<polyline points="' + points + '" fill="none" stroke="' + color +
      '" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>';
  } else {
    var slotWidth = (width - 4) / n;
    var barWidth = slotWidth * 0.7;
    content = values.map(function(v, i) {
      var barHeight = span === 0 ? 2 : ((v - lo) / span) * (height - 6) + 1;
      var x = 2 + i * slotWidth + (slotWidth - barWidth) / 2;
      var y = height - 2 - barHeight;
      return '<rect x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + barWidth.toFixed(1) +
        '" height="' + barHeight.toFixed(1) + '" fill="' + color + '"/>';
    }).join('');
  }
  svg.innerHTML = content;
}
function toggleSparklineType(svg) {
  var mode = svg.getAttribute('data-mode') === 'bar' ? 'line' : 'bar';
  renderSparklineAsMode(svg, mode);
}
function setAllSparklineType(mode) {
  document.querySelectorAll('svg.sparkline').forEach(function(svg) {
    renderSparklineAsMode(svg, mode);
  });
  localStorage.setItem('siteChartMode', mode);
  var btn = document.getElementById('chart-mode-toggle');
  if (btn) btn.innerHTML = mode === 'bar' ? '&#128200; View as Lines' : '&#128202; View as Bars';
}
function toggleAllSparklineType() {
  var current = (document.querySelector('svg.sparkline') || {}).getAttribute
    ? document.querySelector('svg.sparkline').getAttribute('data-mode') : 'line';
  setAllSparklineType(current === 'bar' ? 'line' : 'bar');
}
(function() {
  var savedChartMode = localStorage.getItem('siteChartMode');
  if (savedChartMode === 'bar') {
    document.addEventListener('DOMContentLoaded', function() {
      setAllSparklineType('bar');
    });
  }
})();
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

def ai_insight_button(name, value, unit="", pct=None, six_mo=None, history=None):
    """Small button + collapsible area for the click-to-get-AI-interpretation feature.
    Embeds the card's data as attributes so the click handler can send it to the Worker."""
    name_esc = str(name).replace("'", "&#39;")
    history_str = ",".join(str(v) for v in history) if history else ""
    pct_str = "" if pct is None else str(pct)
    six_mo_str = "" if six_mo is None else str(six_mo)
    return (
        f"<button onclick='showAIInsight(this)' data-name='{name_esc}' data-value='{value}' "
        f"data-unit='{unit}' data-pct='{pct_str}' data-sixmo='{six_mo_str}' data-history='{history_str}' "
        f"style='margin-top:6px;padding:3px 8px;font-size:10px;background:#f0efe9;color:#666;"
        f"border:1px solid #ddd;border-radius:10px;cursor:pointer;'>&#129302; AI Insight</button>"
        f"<div class='ai-insight-area' style='display:none;margin-top:4px;'></div>"
    )

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
        # Sub-penny dollar values (e.g. Shiba Inu) need more than 2 decimals or they'd show as $0.00
        decimals = 8 if (unit == "" and not pt_label and abs(new) < 0.01) else 2
        return (f'<p class="sixmo">6 mo ago: {old:,.{decimals}f}{unit} &middot; '
                f'<span style="color:{color};">{delta:+,.{decimals}f}{amt_label}{pct_txt}</span></p>')
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

def downsample_series(values, max_points=20):
    """Evenly sample a list of values down to at most max_points, keeping first and last."""
    values = list(values)
    if len(values) <= max_points:
        return values
    step = (len(values) - 1) / (max_points - 1)
    indices = [round(i * step) for i in range(max_points)]
    return [values[i] for i in indices]

def call_anthropic_market_alert(snapshot_text):
    """Calls Claude directly (server-side, once per digest run) to synthesize an overall market
    condition score and explanation from a snapshot of today's key data. Returns
    {"score": int, "explanation": str} or None if the key isn't configured or the call fails -
    callers should treat None as "skip this section," not crash the whole digest generation."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Warning: ANTHROPIC_API_KEY not set - skipping market alert generation")
        return None

    prompt = ("You are a market conditions summarizer for a personal investor dashboard. Based on today's data below, "
        "synthesize an overall market condition score from -100 (severe risk - multiple serious warning signs) to +100 "
        "(strongly favorable - broadly positive conditions), with 0 being neutral/mixed. Today's data: " + snapshot_text + ". "
        "Respond in exactly this format with nothing else before or after: "
        "SCORE: [a single integer from -100 to 100]\nEXPLANATION: [4-6 sentences explaining the score, citing the specific "
        "data points that matter most and why caution or optimism is warranted. Plain prose only, no markdown formatting.]")

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]},
            timeout=30
        )
        data = resp.json()
        content = data.get("content", [])
        text = content[0].get("text", "") if content else ""
        if not text:
            print(f"Warning: empty/unexpected response from Anthropic API for market alert: {data}")
            return None
        score_match = re.search(r"SCORE:\s*(-?\d+)", text, re.IGNORECASE)
        explanation_match = re.search(r"EXPLANATION:\s*([\s\S]+)", text, re.IGNORECASE)
        if not score_match or not explanation_match:
            print(f"Warning: could not parse market alert response: {text}")
            return None
        score = max(-100, min(100, int(score_match.group(1))))
        return {"score": score, "explanation": explanation_match.group(1).strip()}
    except Exception as e:
        print(f"Warning: market alert generation failed ({e})")
        return None

def load_alert_history(filepath, max_days=400):
    """Loads a market alert history JSON file (a list of {"date": "YYYY-MM-DD", "score": int}
    entries). Returns an empty list if the file doesn't exist yet (e.g. the very first run)."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r") as f:
            history = json.load(f)
        return history[-max_days:]
    except Exception as e:
        print(f"Warning: could not read history file {filepath} ({e}) - starting fresh")
        return []

def save_alert_history(filepath, history):
    """Saves the history list back to disk, so the GitHub Actions workflow can commit it."""
    with open(filepath, "w") as f:
        json.dump(history, f)

def append_to_history(history, score, explanation):
    """Adds today's score and explanation, replacing any existing entry for today (so re-runs
    on the same day don't create duplicate entries). Explanation is stored too, not just the
    score, so a later run that skips the API call can still display a full result."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    history = [h for h in history if h.get("date") != today_str]
    history.append({"date": today_str, "score": score, "explanation": explanation})
    return history

def get_todays_entry(history):
    """Returns today's history entry if one already exists, so the workflow (which runs every
    15 minutes for fresh stock prices) doesn't call the AI 96 times a day for the same answer -
    only the first run of each calendar day actually generates a new market alert."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    return next((h for h in history if h.get("date") == today_str), None)

def news_feed_html(articles, title):
    """Renders a headline + brief teaser + link-to-source list - never full article text."""
    if not articles:
        return (f'<div class="card" style="max-width:100%;margin-bottom:16px;">'
                f'<p class="label" style="font-size:14px;font-weight:600;color:#333;">{title}</p>'
                f'<span style="font-size:12px;color:#888;">Not available right now - the news feed was skipped or failed on this run.</span>'
                f'</div>')
    items_html = ""
    for a in articles:
        source_line = f"{a['source']} &middot; {a['published']}" if a['source'] else a['published']
        desc_html = ""
        if a["description"]:
            escaped_desc = html_escape_mod.escape(a["description"])
            desc_html = f'<p style="margin:4px 0 0;font-size:12px;color:#555;">{escaped_desc}</p>'
        items_html += (
            f'<div style="padding:10px 0;border-top:1px solid #eee;">'
            f'<a href="{html_escape_mod.escape(a["url"])}" target="_blank" rel="noopener" '
            f'style="color:#1f4e79;font-weight:600;text-decoration:none;font-size:14px;">{html_escape_mod.escape(a["title"])}</a>'
            f'{desc_html}'
            f'<p style="margin:4px 0 0;font-size:11px;color:#999;">{source_line}</p>'
            f'</div>'
        )
    return (f'<div class="card" style="max-width:100%;margin-bottom:16px;">'
            f'<p class="label" style="font-size:14px;font-weight:600;color:#333;">{title}</p>'
            f'{items_html}'
            f'</div>')

def gauge_svg(score, width=320, height=90):
    """Server-side rendered horizontal market alert gauge - same visual design as the gauge
    already used for the live per-visit version, just generated in Python instead of JS."""
    track_y, track_height = 45, 24
    def x_for(s):
        return 10 + ((s + 100) / 200) * (width - 20)
    needle_x = x_for(score)
    zones = [(-100, -50, "#b91c1c"), (-50, -15, "#f87171"), (-15, 15, "#d1d5db"),
              (15, 50, "#86efac"), (50, 100, "#15803d")]
    zones_svg = "".join(
        f'<rect x="{x_for(f):.1f}" y="{track_y}" width="{x_for(t) - x_for(f):.1f}" height="{track_height}" fill="{c}"/>'
        for f, t, c in zones
    )
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
            f'{zones_svg}'
            f'<line x1="{x_for(0)}" y1="{track_y - 4}" x2="{x_for(0)}" y2="{track_y + track_height + 4}" stroke="#555" stroke-width="1.5"/>'
            f'<polygon points="{needle_x - 8},{track_y - 12} {needle_x + 8},{track_y - 12} {needle_x},{track_y - 1}" fill="#111"/>'
            f'<text x="10" y="{track_y + track_height + 20}" font-size="11" fill="#888">-100 Severe Risk</text>'
            f'<text x="{width / 2}" y="{track_y + track_height + 20}" font-size="11" fill="#888" text-anchor="middle">0</text>'
            f'<text x="{width - 10}" y="{track_y + track_height + 20}" font-size="11" fill="#888" text-anchor="end">+100 Strong</text>'
            f'</svg>')

def alert_history_chart_svg(history, days, width=280, height=60):
    """Small line chart of the score history over the last N days - used for the
    daily/weekly/monthly/yearly views, each just a different slice of the same history file.
    Labels the first and last score values directly on the line, and returns a date-range
    caption underneath so the chart isn't just a shape with no numbers attached to it."""
    recent = history[-days:] if len(history) > days else history
    values = [h["score"] for h in recent]
    if len(values) < 2:
        return "<span style='font-size:11px;color:#888;'>Not enough history yet for this view.</span>"
    lo, hi = min(values + [-10]), max(values + [10])  # keep a reasonable range even if scores are all similar
    span = hi - lo
    n = len(values)
    def x_for(i):
        return round(i / (n - 1) * (width - 4) + 2, 1)
    def y_for(v):
        return round(height - 2 - ((v - lo) / span) * (height - 4), 1) if span else round(height / 2, 1)
    points = " ".join(f"{x_for(i)},{y_for(v)}" for i, v in enumerate(values))
    start_val, end_val = values[0], values[-1]
    color = "#1a8a3d" if end_val > start_val else "#c0392b" if end_val < start_val else "#999"
    start_y, end_y = y_for(start_val), y_for(end_val)
    # Flip label above/below the point depending on where it sits, so text doesn't run off the edge.
    start_label_y = start_y - 6 if start_y > 12 else start_y + 14
    end_label_y = end_y - 6 if end_y > 12 else end_y + 14
    start_date = recent[0]["date"]
    end_date = recent[-1]["date"]
    svg = (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
           f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
           f'<circle cx="{x_for(0)}" cy="{start_y}" r="2.5" fill="#999"/>'
           f'<text x="{x_for(0)}" y="{start_label_y}" font-size="10" fill="#888" text-anchor="start">{start_val:+d}</text>'
           f'<circle cx="{x_for(n - 1)}" cy="{end_y}" r="2.5" fill="{color}"/>'
           f'<text x="{x_for(n - 1)}" y="{end_label_y}" font-size="10" fill="{color}" font-weight="600" text-anchor="end">{end_val:+d}</text>'
           f'</svg>')
    return (f'<div>{svg}'
            f'<p style="font-size:10px;color:#999;margin:2px 0 0;">{start_date} &rarr; {end_date}</p>'
            f'</div>')

def render_market_alert_section(score_data, history, title):
    """Builds the full HTML block for a market alert gauge: the gauge itself, score, explanation,
    and four historical views (daily/weekly/monthly/yearly) from the accumulated history file."""
    if score_data is None:
        return (f'<div class="card" style="max-width:100%;margin-bottom:16px;">'
                f'<p class="label" style="font-size:14px;font-weight:600;color:#333;">{title}</p>'
                f'<span style="font-size:12px;color:#888;">Not available today - AI market alert generation was skipped or failed. Check the GitHub Actions log for details.</span>'
                f'</div>')
    score = score_data["score"]
    explanation = score_data["explanation"]
    score_color = "#b91c1c" if score <= -50 else "#f87171" if score <= -15 else "#15803d" if score >= 50 else "#4ade80" if score >= 15 else "#6b7280"

    views = [("Daily (30d)", 30), ("Weekly (90d)", 90), ("Monthly (365d)", 365), ("Yearly (all)", len(history) or 1)]
    history_html = "<div style='display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;'>"
    for label, days in views:
        chart = alert_history_chart_svg(history, days)
        history_html += f"<div><p style='font-size:11px;color:#666;margin:0 0 2px;'>{label}</p>{chart}</div>"
    history_html += "</div>"

    return (f'<div class="card" style="max-width:100%;margin-bottom:16px;">'
            f'<p class="label" style="font-size:14px;font-weight:600;color:#333;">{title}</p>'
            f'<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">'
            f'{gauge_svg(score)}'
            f'<div style="font-size:28px;font-weight:700;color:{score_color};">{"+" if score > 0 else ""}{score}</div>'
            f'</div>'
            f'<p style="font-size:12px;line-height:1.5;margin:8px 0 0;max-width:700px;">{explanation}</p>'
            f'<span style="font-size:10px;color:#999;">AI-generated market synthesis - not personalized financial advice. Updated once daily.</span>'
            f'{history_html}'
            f'</div>')

def sparkline_svg(values, width=80, height=24):
    """Render a small inline SVG sparkline from a list of numeric values.
    Color reflects the overall trend: green if the series ends higher than it started,
    red if lower, gray if flat or if there isn't enough data to draw a meaningful line.
    Clickable - toggles between line and bar view via toggleSparklineType() in the page JS."""
    # v == v is False only for NaN - filters out both None and NaN, since NaN passes
    # 'is not None' but corrupts min/max/span math, producing invalid SVG coordinates.
    values = [v for v in values if v is not None and v == v]
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo
    n = len(values)
    def x_for(i):
        return round(i / (n - 1) * (width - 4) + 2, 1)
    def y_for(v):
        if span == 0:
            return round(height / 2, 1)
        # Invert since SVG y-axis grows downward, but higher values should appear higher on screen
        return round(height - 2 - ((v - lo) / span) * (height - 4), 1)
    points = " ".join(f"{x_for(i)},{y_for(v)}" for i, v in enumerate(values))
    color = "#1a8a3d" if values[-1] > values[0] else "#c0392b" if values[-1] < values[0] else "#999"
    values_attr = ",".join(str(v) for v in values)
    return (f'<svg class="sparkline" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'xmlns="http://www.w3.org/2000/svg" data-values="{values_attr}" data-mode="line" '
            f'onclick="toggleSparklineType(this)" style="cursor:pointer;" title="Click to toggle bar/line view">'
            f'<polyline points="{points}" fill="none" '
            f'stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>')

def fetch_simple_price(symbol):
    data = yf.download(symbol, period="6mo", interval="1d", progress=False, auto_adjust=True)
    if data.empty or len(data) < 2:
        return None
    # .squeeze() guarantees a 1-D Series even if yfinance returns Close as a 1-column DataFrame
    # for this particular symbol (which happens for some tickers) - without it, iterating over
    # an accidental DataFrame yields column names (strings), not values.
    close = data['Close'].squeeze()
    price_raw = close.iloc[-1].item()
    prev_raw = close.iloc[-2].item()
    old_raw = close.iloc[0].item()
    if prev_raw == 0:
        return None  # genuinely no valid prior price to compare against - skip rather than crash
    pct = round((price_raw - prev_raw) / prev_raw * 100, 2)
    # Use extra decimal places for sub-penny assets (e.g. Shiba Inu) so the price doesn't just show as $0.00
    decimals = 2 if price_raw >= 0.01 else 8
    price = round(price_raw, decimals)
    old = round(old_raw, decimals)
    history = downsample_series(close.tolist())
    return {"price": price, "pct": pct, "price_6mo": old, "history": history}

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

def fetch_currents_news(category, limit=8):
    """Fetches recent headlines from Currents API (free tier, commercial use permitted per
    their published terms - verified before building this). Returns only headline, a brief
    description, publish date, and a link back to the original source - never full article
    text, consistent with standard news-aggregation copyright practice regardless of the API's
    own terms. Returns an empty list (not an error) if the key isn't configured or the call
    fails, so a missing/failed news feed never breaks the rest of the digest."""
    api_key = os.environ.get("CURRENTS_API_KEY")
    if not api_key:
        print("Warning: CURRENTS_API_KEY not set - skipping news feed for category:", category)
        return []
    try:
        resp = requests.get(
            "https://api.currentsapi.services/v1/latest-news",
            params={"apiKey": api_key, "category": category, "language": "en"},
            timeout=15
        )
        data = resp.json()
        articles = data.get("news", [])
        results = []
        for a in articles[:limit]:
            title = a.get("title", "").strip()
            if not title:
                continue
            description = (a.get("description") or "").strip()
            # Keep the description brief - a headline-and-teaser format, not a full summary
            if len(description) > 160:
                description = description[:157].rsplit(" ", 1)[0] + "..."
            results.append({
                "title": title,
                "description": description,
                "url": a.get("url", ""),
                "published": (a.get("published") or "")[:10],
                "source": a.get("author") or "",
            })
        return results
    except Exception as e:
        print(f"Warning: news fetch failed for category {category} ({e})")
        return []

# Series known to be quarterly-frequency (not daily/monthly) when fetched via fetch_fred_rate.
# A 6-month lookback window (fine for daily/monthly series - dozens to ~180 points) only yields
# 1-2 observations for a quarterly series, which can't show a real trend and often looks like a
# flat line even when there IS a genuine change, or literally a single point (no line at all) if
# the latest release happens to fall right at the edge of the window. These get a 2-year window
# instead, giving ~8 quarterly points - enough for an actual visible sparkline trend.
QUARTERLY_FRED_SERIES = {"DRSFRMACBS", "RSAHORUSQ156S", "RRVRUSQ156N", "RHVRUSQ156N"}

def fetch_fred_rate(series_id):
    """Latest value, the value from ~6 months ago, and the full history in between for sparklines."""
    lookback_days = 730 if series_id in QUARTERLY_FRED_SERIES else 183
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    series = fetch_fred(series_id, limit=200, sort_order="asc", observation_start=start_date)
    if not series:
        return None
    latest = series[-1]
    history = downsample_series([o["value"] for o in series])

    # "6 months ago" comparison value: find the observation closest to 183 days before latest,
    # not just the oldest point in the window - for quarterly series the window above is longer
    # than 6 months (to build a real sparkline trend), so series[0] would otherwise be ~2 years
    # old rather than ~6 months old, silently making the "6 mo ago" label on the page wrong.
    if lookback_days == 183:
        value_6mo = series[0]["value"]
    else:
        target_date = datetime.now() - timedelta(days=183)
        value_6mo = min(series, key=lambda o: abs(datetime.strptime(o["date"], "%Y-%m-%d") - target_date))["value"]

    return {"value": latest["value"], "date": latest["date"], "value_6mo": value_6mo, "history": history}

def fetch_fred_yoy(series_id):
    """Year-over-year % change now, what it was 6 months ago, and a rolling history in between."""
    obs = fetch_fred(series_id, limit=19)
    if not obs or len(obs) < 13:
        return None
    yoy_now = (obs[0]["value"] - obs[12]["value"]) / obs[12]["value"] * 100
    yoy_6mo = None
    if len(obs) >= 19:
        yoy_6mo = (obs[6]["value"] - obs[18]["value"]) / obs[18]["value"] * 100
    # Rolling YoY for each available month, oldest to newest, for the sparkline
    history = []
    max_i = min(len(obs) - 13, 6)
    for i in range(max_i, -1, -1):
        history.append((obs[i]["value"] - obs[i + 12]["value"]) / obs[i + 12]["value"] * 100)
    return {"display": f"{yoy_now:+.1f}% YoY", "num": yoy_now, "num_6mo": yoy_6mo,
            "date": obs[0]["date"], "history": history}

def fetch_fred_yoy_quarterly(series_id):
    """Same as fetch_fred_yoy but for quarterly series (e.g. real GDP) - compares each quarter
    to the same quarter a year earlier (4 quarters back instead of 12 months back)."""
    obs = fetch_fred(series_id, limit=9)
    if not obs or len(obs) < 5:
        return None
    yoy_now = (obs[0]["value"] - obs[4]["value"]) / obs[4]["value"] * 100
    yoy_1q_ago = None
    if len(obs) >= 6:
        yoy_1q_ago = (obs[1]["value"] - obs[5]["value"]) / obs[5]["value"] * 100
    history = []
    max_i = min(len(obs) - 5, 3)
    for i in range(max_i, -1, -1):
        history.append((obs[i]["value"] - obs[i + 4]["value"]) / obs[i + 4]["value"] * 100)
    return {"display": f"{yoy_now:+.1f}% YoY", "num": yoy_now, "num_6mo": yoy_1q_ago,
            "date": obs[0]["date"], "history": history}

def fetch_census_county_population():
    """Population and 5-year population growth for every US county, used by the County
    Investment Map. Uses the Census API's wildcard geography pattern (&for=county:*
    &in=state:*) which returns ALL counties nationally in a single request per vintage - not
    one request per county (3,143 separate calls would hit rate limits fast; this needs just
    two calls total, one per ACS 5-year vintage being compared).

    B01003_001E = total population, ACS 5-Year Estimates - a standard, stable Census variable.
    Comparing the 2023 5-year vintage (2019-2023) to the 2018 vintage (2014-2018) gives a
    genuine 5-year population change, not a same-period overlap.

    Returns a dict keyed by 5-digit county FIPS code, or None if either call fails."""
    if not CENSUS_API_KEY:
        print("Warning: CENSUS_API_KEY not set - skipping county population data for the "
              "Investment Map. Get a free key at https://api.census.gov/data/key_signup.html "
              "and set CENSUS_API_KEY near the top of this script.")
        return None
    try:
        url_now = f"https://api.census.gov/data/2023/acs/acs5?get=NAME,B01003_001E&for=county:*&in=state:*&key={CENSUS_API_KEY}"
        url_before = f"https://api.census.gov/data/2018/acs/acs5?get=NAME,B01003_001E&for=county:*&in=state:*&key={CENSUS_API_KEY}"
        r_now = requests.get(url_now, timeout=30)
        r_before = requests.get(url_before, timeout=30)
        r_now.raise_for_status()
        r_before.raise_for_status()
        data_now = r_now.json()
        data_before = r_before.json()
    except Exception as e:
        print("Warning: could not fetch Census county population data -", e)
        return None

    if not data_now or len(data_now) < 2 or not data_before or len(data_before) < 2:
        print("Warning: Census county population response was empty or malformed - skipping")
        return None

    header_now = data_now[0]
    header_before = data_before[0]
    try:
        idx_name = header_now.index("NAME")
        idx_pop = header_now.index("B01003_001E")
        idx_state = header_now.index("state")
        idx_county = header_now.index("county")
        idx_pop_before = header_before.index("B01003_001E")
        idx_state_before = header_before.index("state")
        idx_county_before = header_before.index("county")
    except ValueError as e:
        print("Warning: Census county population response is missing an expected column -", e)
        return None

    before_lookup = {}
    for row in data_before[1:]:
        try:
            fips = row[idx_state_before] + row[idx_county_before]
            before_lookup[fips] = float(row[idx_pop_before])
        except (ValueError, TypeError, IndexError):
            continue

    result = {}
    for row in data_now[1:]:
        try:
            fips = row[idx_state] + row[idx_county]
            pop_now = float(row[idx_pop])
        except (ValueError, TypeError, IndexError):
            continue
        pop_before = before_lookup.get(fips)
        growth_pct = None
        if pop_before and pop_before > 0:
            growth_pct = round((pop_now - pop_before) / pop_before * 100, 2)
        result[fips] = {
            "name": row[idx_name],
            "pop": int(pop_now),
            "pop_5yr_ago": int(pop_before) if pop_before else None,
            "growth_pct": growth_pct,
        }
    return result

def fetch_census_county_housing_units():
    """Total housing units and 5-year housing-unit growth for every US county, used by the
    County Investment Map. Mirrors fetch_census_county_population() exactly (same ACS wildcard
    query pattern, same two-vintage comparison, same proven, already-working infrastructure) -
    just a different Census variable, so this reuses code that's already reliable in production
    rather than depending on a separate, less certain Census data program.

    B25001_001E = total housing units, ACS 5-Year Estimates - a standard, stable Census variable
    (distinct from B01003_001E, total population, used elsewhere on this map). Comparing the
    2023 5-year vintage (2019-2023) to the 2018 vintage (2014-2018) gives a genuine 5-year
    change in the housing stock - where new supply has actually been added, not just requested
    via permit (that's the separate Building Permits layer already on this map).

    Returns a dict keyed by 5-digit county FIPS code, or None if either call fails."""
    if not CENSUS_API_KEY:
        print("Warning: CENSUS_API_KEY not set - skipping county housing-unit data for the "
              "Investment Map. Get a free key at https://api.census.gov/data/key_signup.html "
              "and set CENSUS_API_KEY near the top of this script.")
        return None
    try:
        url_now = f"https://api.census.gov/data/2023/acs/acs5?get=NAME,B25001_001E&for=county:*&in=state:*&key={CENSUS_API_KEY}"
        url_before = f"https://api.census.gov/data/2018/acs/acs5?get=NAME,B25001_001E&for=county:*&in=state:*&key={CENSUS_API_KEY}"
        r_now = requests.get(url_now, timeout=30)
        r_before = requests.get(url_before, timeout=30)
        r_now.raise_for_status()
        r_before.raise_for_status()
        data_now = r_now.json()
        data_before = r_before.json()
    except Exception as e:
        print("Warning: could not fetch Census county housing-unit data -", e)
        return None

    if not data_now or len(data_now) < 2 or not data_before or len(data_before) < 2:
        print("Warning: Census county housing-unit response was empty or malformed - skipping")
        return None

    header_now = data_now[0]
    header_before = data_before[0]
    try:
        idx_name = header_now.index("NAME")
        idx_units = header_now.index("B25001_001E")
        idx_state = header_now.index("state")
        idx_county = header_now.index("county")
        idx_units_before = header_before.index("B25001_001E")
        idx_state_before = header_before.index("state")
        idx_county_before = header_before.index("county")
    except ValueError as e:
        print("Warning: Census county housing-unit response is missing an expected column -", e)
        return None

    before_lookup = {}
    for row in data_before[1:]:
        try:
            fips = row[idx_state_before] + row[idx_county_before]
            before_lookup[fips] = float(row[idx_units_before])
        except (ValueError, TypeError, IndexError):
            continue

    result = {}
    for row in data_now[1:]:
        try:
            fips = row[idx_state] + row[idx_county]
            units_now = float(row[idx_units])
        except (ValueError, TypeError, IndexError):
            continue
        units_before = before_lookup.get(fips)
        growth_pct = None
        if units_before and units_before > 0:
            growth_pct = round((units_now - units_before) / units_before * 100, 2)
        result[fips] = {
            "name": row[idx_name],
            "housing_units": int(units_now),
            "housing_units_5yr_ago": int(units_before) if units_before else None,
            "housing_growth_pct": growth_pct,
        }
    return result

def fetch_census_county_median_home_value():
    """Median value of owner-occupied housing units for every US county, used by the County
    Investment Map. Same bulk wildcard pattern as population - one API call covers all 3,143
    counties. B25077_001E = median home value, ACS 5-Year Estimates (2019-2023 vintage).

    Unlike population growth or unemployment, home value has no inherent "good" direction for
    color purposes (high could mean expensive/less affordable, or appreciating/desirable,
    depending on who's looking) - this is intentionally left for the client-side color scale
    to render as a neutral sequential scale, not a red-green good/bad judgment.

    Returns a dict keyed by 5-digit county FIPS code, or None if the call fails."""
    if not CENSUS_API_KEY:
        print("Warning: CENSUS_API_KEY not set - skipping median home value for the "
              "Investment Map.")
        return None
    try:
        url = f"https://api.census.gov/data/2023/acs/acs5?get=NAME,B25077_001E&for=county:*&in=state:*&key={CENSUS_API_KEY}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print("Warning: could not fetch Census county median home value data -", e)
        return None

    if not data or len(data) < 2:
        print("Warning: Census county median home value response was empty or malformed - skipping")
        return None

    header = data[0]
    try:
        idx_name = header.index("NAME")
        idx_value = header.index("B25077_001E")
        idx_state = header.index("state")
        idx_county = header.index("county")
    except ValueError as e:
        print("Warning: Census county median home value response is missing an expected column -", e)
        return None

    result = {}
    for row in data[1:]:
        try:
            fips = row[idx_state] + row[idx_county]
            value = float(row[idx_value])
        except (ValueError, TypeError, IndexError):
            continue
        # Census uses sentinel values (e.g. -666666666) for "no reliable estimate available" -
        # same convention already handled elsewhere on this site (Property Search's
        # neighborhood data lookup). A negative "median home value" is never real data.
        if value < 0:
            continue
        result[fips] = {"name": row[idx_name], "median_home_value": value}
    return result

def fetch_census_county_vacant_for_sale():
    """Vacant housing units classified as "for sale only" for every US county, used by the
    County Investment Map's Vacant Homes For Sale layer. Same bulk wildcard pattern and single-
    vintage snapshot as median home value above - one API call covers all 3,143 counties.
    B25004_004E = vacant housing units, for sale only, ACS 5-Year Estimates (2019-2023 vintage) -
    verified directly against the Census Bureau's own B25004 (Vacancy Status) table documentation
    before using it here.

    IMPORTANT: this is a structural, once-every-5-years survey estimate, not a live listing
    count - it is NOT equivalent to current MLS/Realtor.com/Zillow active inventory, and should
    never be labeled as such anywhere this data is displayed. It measures the same underlying
    concept as the "Vacant Homes For Sale - ACS Estimate" figure already described in the
    original planning notes for this map: useful for structural, multi-year comparisons between
    counties, not for timing this month's market.

    Client-side, this is displayed as a rate (vacant-for-sale units per 1,000 total housing
    units, using the housing_units figure already fetched by
    fetch_census_county_housing_units() above) rather than a raw count, so a large county isn't
    penalized in the color scale just for having more homes overall.

    Returns a dict keyed by 5-digit county FIPS code, or None if the call fails."""
    if not CENSUS_API_KEY:
        print("Warning: CENSUS_API_KEY not set - skipping vacant-for-sale data for the "
              "Investment Map.")
        return None
    try:
        url = f"https://api.census.gov/data/2023/acs/acs5?get=NAME,B25004_004E&for=county:*&in=state:*&key={CENSUS_API_KEY}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print("Warning: could not fetch Census county vacant-for-sale data -", e)
        return None

    if not data or len(data) < 2:
        print("Warning: Census county vacant-for-sale response was empty or malformed - skipping")
        return None

    header = data[0]
    try:
        idx_name = header.index("NAME")
        idx_value = header.index("B25004_004E")
        idx_state = header.index("state")
        idx_county = header.index("county")
    except ValueError as e:
        print("Warning: Census county vacant-for-sale response is missing an expected column -", e)
        return None

    result = {}
    for row in data[1:]:
        try:
            fips = row[idx_state] + row[idx_county]
            value = float(row[idx_value])
        except (ValueError, TypeError, IndexError):
            continue
        # Same Census sentinel-value convention as home value/rent/income - negative counts are
        # never real data, they mean "no reliable estimate available for this geography."
        if value < 0:
            continue
        result[fips] = {"name": row[idx_name], "vacant_for_sale": int(value)}
    return result

def fetch_census_county_total_vacancy():
    """Total vacant housing units (all reasons - for rent, for sale, seasonal use, etc.) for
    every US county, used by the County Investment Map's Total Vacancy Rate layer. Same bulk
    wildcard pattern and single-vintage snapshot as fetch_census_county_vacant_for_sale() above -
    one API call covers all 3,143 counties. B25004_001E = total vacant housing units (all
    categories combined), ACS 5-Year Estimates (2019-2023 vintage) - the "Total:" line of the
    same B25004 (Vacancy Status) table used for the Vacant Homes For Sale layer, verified
    directly against the Census Bureau's own table documentation before using it here.

    Unlike Vacant Homes For Sale (which isolates just the "for sale only" category), this is the
    broader total vacancy rate - it captures homes vacant for any reason, giving a fuller picture
    of how much of a county's housing stock is sitting empty overall, not just what's on the
    market to buy.

    Client-side, this is displayed as a rate (total vacant units as a percentage of total
    housing units, using the housing_units figure already fetched by
    fetch_census_county_housing_units() above) rather than a raw count, so a large county isn't
    penalized in the color scale just for having more homes overall.

    Returns a dict keyed by 5-digit county FIPS code, or None if the call fails."""
    if not CENSUS_API_KEY:
        print("Warning: CENSUS_API_KEY not set - skipping total vacancy data for the "
              "Investment Map.")
        return None
    try:
        url = f"https://api.census.gov/data/2023/acs/acs5?get=NAME,B25004_001E&for=county:*&in=state:*&key={CENSUS_API_KEY}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print("Warning: could not fetch Census county total vacancy data -", e)
        return None

    if not data or len(data) < 2:
        print("Warning: Census county total vacancy response was empty or malformed - skipping")
        return None

    header = data[0]
    try:
        idx_name = header.index("NAME")
        idx_value = header.index("B25004_001E")
        idx_state = header.index("state")
        idx_county = header.index("county")
    except ValueError as e:
        print("Warning: Census county total vacancy response is missing an expected column -", e)
        return None

    result = {}
    for row in data[1:]:
        try:
            fips = row[idx_state] + row[idx_county]
            value = float(row[idx_value])
        except (ValueError, TypeError, IndexError):
            continue
        # Same Census sentinel-value convention as home value/rent/income - negative counts are
        # never real data, they mean "no reliable estimate available for this geography."
        if value < 0:
            continue
        result[fips] = {"name": row[idx_name], "vacant_total": int(value)}
    return result

def fetch_census_county_median_rent():
    """Median gross rent for every US county, used by the County Investment Map. Same bulk
    wildcard pattern as population/home value - one API call covers all 3,143 counties.
    B25064_001E = median gross rent, ACS 5-Year Estimates (2019-2023 vintage).

    Like home value, rent has no single inherent "good" color direction (high rent could mean
    a desirable area with strong renter demand, or an affordability problem, depending on
    perspective) - left as a neutral sequential scale on the client side, not red-green.

    Returns a dict keyed by 5-digit county FIPS code, or None if the call fails."""
    if not CENSUS_API_KEY:
        print("Warning: CENSUS_API_KEY not set - skipping median rent for the Investment Map.")
        return None
    try:
        url = f"https://api.census.gov/data/2023/acs/acs5?get=NAME,B25064_001E&for=county:*&in=state:*&key={CENSUS_API_KEY}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print("Warning: could not fetch Census county median rent data -", e)
        return None

    if not data or len(data) < 2:
        print("Warning: Census county median rent response was empty or malformed - skipping")
        return None

    header = data[0]
    try:
        idx_name = header.index("NAME")
        idx_value = header.index("B25064_001E")
        idx_state = header.index("state")
        idx_county = header.index("county")
    except ValueError as e:
        print("Warning: Census county median rent response is missing an expected column -", e)
        return None

    result = {}
    for row in data[1:]:
        try:
            fips = row[idx_state] + row[idx_county]
            value = float(row[idx_value])
        except (ValueError, TypeError, IndexError):
            continue
        # Same Census sentinel-value convention as home value - negative rent is never real.
        if value < 0:
            continue
        result[fips] = {"name": row[idx_name], "median_rent": value}
    return result

def fetch_census_county_median_income():
    """Median household income for every US county, used by the County Investment Map. Same
    bulk wildcard pattern as population/home value/rent - one API call covers all 3,143
    counties. B19013_001E = median household income, ACS 5-Year Estimates (2019-2023 vintage).

    Same neutral-scale reasoning as home value and rent - high income has no inherent "good"
    color direction for a map like this, left as a neutral sequential scale on the client side.

    Returns a dict keyed by 5-digit county FIPS code, or None if the call fails."""
    if not CENSUS_API_KEY:
        print("Warning: CENSUS_API_KEY not set - skipping median household income for the "
              "Investment Map.")
        return None
    try:
        url = f"https://api.census.gov/data/2023/acs/acs5?get=NAME,B19013_001E&for=county:*&in=state:*&key={CENSUS_API_KEY}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print("Warning: could not fetch Census county median income data -", e)
        return None

    if not data or len(data) < 2:
        print("Warning: Census county median income response was empty or malformed - skipping")
        return None

    header = data[0]
    try:
        idx_name = header.index("NAME")
        idx_value = header.index("B19013_001E")
        idx_state = header.index("state")
        idx_county = header.index("county")
    except ValueError as e:
        print("Warning: Census county median income response is missing an expected column -", e)
        return None

    result = {}
    for row in data[1:]:
        try:
            fips = row[idx_state] + row[idx_county]
            value = float(row[idx_value])
        except (ValueError, TypeError, IndexError):
            continue
        # Same Census sentinel-value convention as home value/rent - negative income is never real.
        if value < 0:
            continue
        result[fips] = {"name": row[idx_name], "median_income": value}
    return result

def fetch_census_county_building_permits():
    """Total new housing units authorized by building permits for every US county in the most
    recent full calendar year, used by the County Investment Map. Unlike the ACS-based layers
    above, this uses a completely different Census data pathway - the Building Permits Survey
    (BPS), delivered as a flat comma-delimited text file, not the ACS wildcard-query API. Full
    coverage of all 3,143 counties is available at the annual release (per Census's own 2022
    methodology change announcement), unlike the sampled coverage at some other BPS geographies.

    File format verified directly against Census's own documentation sample file
    (www.census.gov/construction/bps/sample/co2002a.txt, fetched and inspected byte-for-byte
    before writing this): comma-delimited, 2 header rows + 1 blank row, then one row per county
    with 30 columns:
      [0]=Year [1]=State FIPS [2]=County FIPS [3]=Region [4]=Division [5]=County Name
      [6..8]=1-unit (Bldgs,Units,Value) [9..11]=2-units [12..14]=3-4 units [15..17]=5+ units
      [18..29]=same 4 categories again, "reported only" (respondents only, not imputed)
    Total housing units authorized = sum of the Units column (index 7, 10, 13, 16) across all
    four structure-size categories, using the full imputed total, not the reported-only subset.

    This needs a fresh year number periodically - Census releases the final annual file for a
    given year on the first workday of May the following year. If this starts returning no
    data, ask Claude to "update my building permits year" - the file for the year below may not
    exist yet, or a newer one may now be the current release.
    """
    year = 2025  # See docstring - update once a newer annual file is released (each following May).
    url = f"https://www2.census.gov/econ/bps/County/co{year}a.txt"
    try:
        resp = requests.get(url, timeout=60, headers={"User-Agent": "USA Tools Inc Stock Digest contact@usatoolsinc.com"})
        resp.raise_for_status()
        text = resp.text
    except Exception as e:
        print(f"Warning: could not download Census building permits data for {year} -", e)
        return None

    lines = text.splitlines()
    if len(lines) < 4:
        print("Warning: Census building permits file was empty or malformed - skipping")
        return None

    result = {}
    parsed_rows = 0
    for line in lines[3:]:  # skip 2 header rows + 1 blank row
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 17:
            continue
        state_fips, county_fips = parts[1], parts[2]
        if not (state_fips.isdigit() and county_fips.isdigit()):
            continue
        fips = state_fips.zfill(2) + county_fips.zfill(3)
        county_name = parts[5]
        try:
            total_units = int(parts[7]) + int(parts[10]) + int(parts[13]) + int(parts[16])
        except (ValueError, IndexError):
            continue
        parsed_rows += 1
        result[fips] = {"name": county_name, "building_permits": total_units}

    if parsed_rows == 0:
        print("Warning: Census building permits file parsed but no matching rows found - "
              "the file format may have changed, or the year in the URL may not exist yet. Skipping.")
        return None

    return result

def fetch_census_county_permit_growth():
    """Year-over-year change in new-construction building permits for every US county, used by
    the County Investment Map's Permit Growth (YoY) layer. Also captures the single-family vs.
    multifamily split of the current year's permits (used by the separate Multifamily Share
    layer) - since this function already downloads and parses that file's per-structure-size
    columns to compute the total, breaking them out separately instead of only summing them
    needs no additional network call.

    Uses the same Census Building Permits Survey (BPS) flat-file source and the same parsing
    logic as fetch_census_county_building_permits() above (duplicated into a local helper here
    rather than calling that function directly, so the two stay fully independent and a change
    to one can never accidentally break the other) - just fetching two consecutive annual files
    (the current year and the prior year) instead of one, to compute whether permit activity is
    accelerating or slowing, rather than only a single-year snapshot.

    IMPORTANT: the two year numbers below should be kept in sync with the `year` variable inside
    fetch_census_county_building_permits() above - if that one is ever updated (each following
    May, per its own docstring, once a newer annual BPS file is released), update CURRENT_YEAR
    here to match it, and PRIOR_YEAR to be exactly one less.

    Returns a dict keyed by 5-digit county FIPS code, or None if either year's file fails to
    download or parse."""
    CURRENT_YEAR = 2025
    PRIOR_YEAR = 2024

    def fetch_and_parse(year):
        url = f"https://www2.census.gov/econ/bps/County/co{year}a.txt"
        try:
            resp = requests.get(url, timeout=60, headers={"User-Agent": "USA Tools Inc Stock Digest contact@usatoolsinc.com"})
            resp.raise_for_status()
            text = resp.text
        except Exception as e:
            print(f"Warning: could not download Census building permits data for {year} (permit growth layer) -", e)
            return None
        lines = text.splitlines()
        if len(lines) < 4:
            print(f"Warning: Census building permits file for {year} was empty or malformed (permit growth layer) - skipping")
            return None
        parsed = {}
        parsed_rows = 0
        for line in lines[3:]:  # skip 2 header rows + 1 blank row
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 17:
                continue
            state_fips, county_fips = parts[1], parts[2]
            if not (state_fips.isdigit() and county_fips.isdigit()):
                continue
            fips = state_fips.zfill(2) + county_fips.zfill(3)
            county_name = parts[5]
            try:
                # Column layout (see fetch_census_county_building_permits() docstring above for
                # the full field map): index 7 = 1-unit (single-family) Units column; indices
                # 10/13/16 = 2-unit, 3-4 unit, and 5+ unit Units columns respectively - all three
                # are conventionally grouped together as "multifamily" (anything above a single
                # detached unit) for this kind of housing-mix analysis.
                sf_units = int(parts[7])
                mf_units = int(parts[10]) + int(parts[13]) + int(parts[16])
                total_units = sf_units + mf_units
            except (ValueError, IndexError):
                continue
            parsed_rows += 1
            parsed[fips] = {"name": county_name, "permits": total_units, "sf_units": sf_units, "mf_units": mf_units}
        if parsed_rows == 0:
            print(f"Warning: Census building permits file for {year} parsed but no matching rows found (permit growth layer) - skipping")
            return None
        return parsed

    current_data = fetch_and_parse(CURRENT_YEAR)
    prior_data = fetch_and_parse(PRIOR_YEAR)
    if not current_data or not prior_data:
        return None

    result = {}
    for fips, rec in current_data.items():
        prior_rec = prior_data.get(fips)
        growth_pct = None
        if prior_rec and prior_rec["permits"] > 0:
            growth_pct = round((rec["permits"] - prior_rec["permits"]) / prior_rec["permits"] * 100, 2)
        mf_share_pct = None
        if rec["permits"] > 0:
            mf_share_pct = round(rec["mf_units"] / rec["permits"] * 100, 2)
        result[fips] = {
            "name": rec["name"],
            "permits_current": rec["permits"],
            "permits_prior": prior_rec["permits"] if prior_rec else None,
            "single_family_permits": rec["sf_units"],
            "multifamily_permits": rec["mf_units"],
            "multifamily_share_pct": mf_share_pct,
            "permit_growth_pct": growth_pct,
        }
    return result

def fetch_puerto_rico_municipio_boundaries():
    """GeoJSON boundaries for Puerto Rico's 78 municipios, used to render a dedicated Puerto
    Rico map on the County Investment Map page. Puerto Rico is NOT included in the standard
    us-atlas TopoJSON file used for the main US map - that package's Albers USA projection is
    built only for the 50 states + DC, and territories don't fit into it (confirmed against the
    package's own documentation, plus the existence of multiple third-party forks whose entire
    purpose is adding territory support the base package lacks).

    Rather than pull in one of those forks (the main one found is explicitly documented as
    unstable/pre-1.0 - not something to add as a dependency for a paid product), this fetches a
    small, standalone GeoJSON of just Puerto Rico's municipios and renders it as its own small
    map with its own projection, fitted to Puerto Rico's own bounds - conceptually the same idea
    as how Alaska/Hawaii get their own inset treatment on the main map, just built directly.

    Source: miguelrios/atlaspr, a GitHub project built specifically for D3.js maps of Puerto
    Rico. Verified directly (fetched and inspected before writing this): the file's "pueblos"
    key contains a proper 78-feature GeoJSON FeatureCollection, one per municipio, each with
    properties.STATE="72" and properties.COUNTY (3-digit) - the exact same FIPS scheme already
    used throughout this file, so no separate FIPS-mapping logic is needed. Coordinates are raw,
    unprojected lat/long (verified: longitude -67.27 to -65.24, latitude 17.93 to 18.52, matching
    Puerto Rico's real-world location).

    This is a personal repository, not a versioned/CDN-distributed package like the mainland
    boundary file - so unlike that one (which the client fetches live from jsdelivr on every
    page load), this is fetched once here at build time and embedded directly into the page.
    That way the map keeps working even if this particular repo is ever renamed or taken down;
    a build-time fetch failure just means Puerto Rico's map section doesn't render until the
    next successful build, not that visitors' pages break.

    Returns the "pueblos" GeoJSON FeatureCollection (as a Python dict, ready to embed as JSON),
    or None if the fetch/parse fails."""
    url = "https://raw.githubusercontent.com/miguelrios/atlaspr/master/geotiles/puertorico-geo.json"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print("Warning: could not fetch Puerto Rico municipio boundaries -", e)
        return None

    pueblos = data.get("pueblos")
    if not pueblos or pueblos.get("type") != "FeatureCollection" or not pueblos.get("features"):
        print("Warning: Puerto Rico boundary file fetched but did not have the expected "
              "'pueblos' FeatureCollection structure - the source file may have changed. Skipping.")
        return None

    valid_count = sum(
        1 for f in pueblos["features"]
        if f.get("properties", {}).get("STATE") == "72" and f.get("properties", {}).get("COUNTY")
    )
    if valid_count < 78:
        print(f"Warning: expected 78 Puerto Rico municipios, found {valid_count} with valid "
              "STATE/COUNTY properties - the source file may have changed. Skipping.")
        return None

    return pueblos

# FIPS-equivalent state codes for the four Pacific/Caribbean Island Areas, per the standard
# Census/ANSI state-code convention (same scheme already used throughout this file for the 50
# states + DC + Puerto Rico). Each territory is treated as a single county-equivalent unit for
# map purposes (population is small enough - 47K to 154K - that further subdividing into
# municipalities/villages/estates wouldn't add much, unlike Puerto Rico's 78 municipios).
TERRITORY_FIPS = {
    "American Samoa": "60",
    "Guam": "66",
    "Northern Mariana Islands": "69",
    "U.S. Virgin Islands": "78",
}

# Manually-researched data for the four U.S. Island Areas (American Samoa, Guam, CNMI, USVI).
# These are NOT covered by the American Community Survey - Census's own press materials state
# this explicitly ("Other surveys such as the American Community Survey (ACS) are not conducted
# in these territories"). Instead they rely on the decennial "Island Areas Census" - population,
# income, and home value below are from the 2020 count (income reflects 2019, the year the 2020
# census asked about) and won't update again until the 2030 census. Source: U.S. Census Bureau
# 2020 Island Areas Censuses Demographic and Housing Characteristics (DHC) press releases,
# census.gov/newsroom/press-releases/2023/2020-dhc-summary-file-{territory}.html and the
# accompanying 2024 detailed cross-tabulation releases (for unemployment).
#
# Rent is the one exception: rather than also using the static 2020 figure, this uses HUD's Fair
# Market Rent (FY2025, 2-bedroom, 40th percentile) instead, since HUD publishes and updates FMRs
# for these same four territories every fiscal year - so unlike the other figures, rent here can
# actually be refreshed on a future update rather than staying frozen until 2030. Source: HUD FMR
# data as compiled by rentdata.org for FY2025 (effective 10/1/2024).
#
# IMPORTANT: unlike every other data source on this map, none of this refreshes automatically.
# Population/income/home value need a manual update once the 2030 Island Areas Census results are
# released; rent should be manually refreshed against HUD's new FMRs each time this file gets a
# broader update, since HUD does publish new figures annually even though these other figures
# don't.
TERRITORY_DATA = {
    "American Samoa": {
        "pop": 49710, "median_income": 28352, "median_home_value": 84400,
        "median_rent": 1012, "unemployment_rate": 13.2,
    },
    "Guam": {
        "pop": 153836, "median_income": 58289, "median_home_value": 277800,
        "median_rent": 1765, "unemployment_rate": 10.2,
    },
    "Northern Mariana Islands": {
        "pop": 47329, "median_income": 31362, "median_home_value": 184200,
        "median_rent": 996, "unemployment_rate": 14.1,
    },
    "U.S. Virgin Islands": {
        "pop": 87146, "median_income": 40408, "median_home_value": 290600,
        "median_rent": 1723, "unemployment_rate": 9.7,
    },
}

def fetch_territory_boundaries():
    """GeoJSON boundaries for the four U.S. Island Areas not otherwise covered by the county
    map: American Samoa, Guam, the Northern Mariana Islands, and the U.S. Virgin Islands.

    Source: georgique/world-geojson, a general-purpose world GeoJSON project (verified directly
    - installed via npm and inspected before using). Fetched here from its GitHub repo (same
    reliable "fetch once at build time, embed the result" pattern already used for Puerto Rico's
    boundaries) rather than a CDN, since this is a smaller, less established package than the
    Census-derived files used for the mainland map.

    One known data issue, found by checking every feature's coordinates against real-world
    geography before trusting this file: the U.S. Virgin Islands file contains one invalid
    feature (of 11) whose coordinates actually fall within Puerto Rico, roughly 2 degrees of
    longitude away from the other 10 (which all check out correctly against known USVI geography
    - St. Croix, St. Thomas, St. John, and nearby cays). That one feature is dropped here.

    Returns a dict of {territory_name: GeoJSON FeatureCollection}, using only territories that
    fetched and validated successfully - a failure on one territory doesn't block the others."""
    base_url = "https://raw.githubusercontent.com/georgique/world-geojson/master/areas/usa/"
    files = {
        "American Samoa": "american_samoa.json",
        "Guam": "guam.json",
        "Northern Mariana Islands": "northern_mariana_islands.json",
        "U.S. Virgin Islands": "us_virgin_islands.json",
    }
    result = {}
    for territory, filename in files.items():
        try:
            resp = requests.get(base_url + filename, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"Warning: could not fetch {territory} boundary data -", e)
            continue

        if data.get("type") != "FeatureCollection" or not data.get("features"):
            print(f"Warning: {territory} boundary file fetched but did not have the expected "
                  "FeatureCollection structure - the source file may have changed. Skipping.")
            continue

        features = data["features"]
        if territory == "U.S. Virgin Islands":
            # Drop the one known-bad feature (see docstring) - identified by its longitude
            # falling far outside the real USVI range, rather than a hardcoded index, so this
            # stays correct even if the source file's feature order ever changes.
            def is_valid_usvi_feature(feat):
                coords = feat["geometry"]["coordinates"]
                # Walk to find any single coordinate pair to sample this feature's longitude
                c = coords
                while isinstance(c[0], list):
                    c = c[0]
                lon = c[0]
                return -66.0 <= lon <= -64.0  # real USVI longitude range, with margin
            valid_features = [f for f in features if is_valid_usvi_feature(f)]
            if len(valid_features) != 10:
                print(f"Warning: expected to keep 10 of 11 U.S. Virgin Islands features after "
                      f"filtering the known bad one, got {len(valid_features)} - the source file "
                      "may have changed. Using all fetched features instead of guessing.")
            else:
                features = valid_features

        result[territory] = {"type": "FeatureCollection", "features": features}

    return result

def fetch_bls_county_unemployment():
    """County-level unemployment rate for every US county, used by the County Investment Map.

    BLS publishes Local Area Unemployment Statistics (LAUS) as bulk flat files, not a
    rate-limited API - no key needed. The full historical county file is enormous (300+ MB,
    back to 1990), but BLS also publishes a "current window" file covering just the most
    recent ~5 years (currently 2025-2029), which is what we actually need since we only want
    each county's latest rate - roughly 22-33MB, a reasonable one-time download during a
    GitHub Actions run.

    Series ID format for county unemployment rate: "LAUCN" + 5-digit county FIPS + "0000000"
    + "03" (measure code 03 = unemployment rate). E.g. LAUCN010010000000003 = Autauga County,
    AL. Source: BLS LAUS series ID convention, cross-checked against a live example
    (LAUCN281070000000003) in BLS's own API documentation.

    File format: tab-separated, one header row, columns are series_id / year / period / value
    / footnote_codes. Period "M13" is the annual average - skipped here since we want the
    latest available month, not an annual figure. Fields are stripped of whitespace since
    BLS flat files are historically fixed-width-padded.

    Returns a dict keyed by 5-digit county FIPS code (rate + the year-month it's from), or
    None if the download/parse fails entirely."""
    url = "https://download.bls.gov/pub/time.series/la/la.data.0.CurrentU25-29"
    try:
        resp = requests.get(url, timeout=90, headers={"User-Agent": "USA Tools Inc Stock Digest contact@usatoolsinc.com"})
        resp.raise_for_status()
        text = resp.text
    except Exception as e:
        print("Warning: could not download BLS county unemployment data -", e)
        return None

    lines = text.splitlines()
    if len(lines) < 2:
        print("Warning: BLS county unemployment file was empty or malformed - skipping")
        return None

    result = {}
    parsed_rows = 0
    for line in lines[1:]:  # skip header row
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        series_id = parts[0].strip()
        year_str = parts[1].strip()
        period = parts[2].strip()
        value_str = parts[3].strip()

        if not series_id.startswith("LAUCN") or not series_id.endswith("03") or period == "M13":
            continue
        fips = series_id[5:10]
        if len(fips) != 5 or not fips.isdigit():
            continue
        try:
            year = int(year_str)
            rate = float(value_str)
        except (ValueError, TypeError):
            continue

        parsed_rows += 1
        # Period is like "M01".."M12" - keep only the latest (year, month) per county
        existing = result.get(fips)
        key_now = (year, period)
        if existing is None or key_now > existing["_sort_key"]:
            result[fips] = {"rate": rate, "period": f"{year}-{period[1:]}", "_sort_key": key_now}

    if parsed_rows == 0:
        print("Warning: BLS county unemployment file parsed but no matching rows found - "
              "the file format may have changed. Skipping.")
        return None

    for fips in result:
        del result[fips]["_sort_key"]

    return result

def fetch_fred_mom(series_id):
    """Month-over-month % change now, what it was 6 months ago, and a rolling history in between."""
    obs = fetch_fred(series_id, limit=8)
    if not obs or len(obs) < 2:
        return None
    mom_now = (obs[0]["value"] - obs[1]["value"]) / obs[1]["value"] * 100
    mom_6mo = None
    if len(obs) >= 8:
        mom_6mo = (obs[6]["value"] - obs[7]["value"]) / obs[7]["value"] * 100
    # Rolling MoM for each available month, oldest to newest, for the sparkline
    history = []
    max_i = min(len(obs) - 2, 6)
    for i in range(max_i, -1, -1):
        history.append((obs[i]["value"] - obs[i + 1]["value"]) / obs[i + 1]["value"] * 100)
    return {"display": f"{mom_now:+.1f}% MoM", "num": mom_now, "num_6mo": mom_6mo,
            "date": obs[0]["date"], "history": history}

def fetch_fred_recent_change(series_id, days_back=30):
    """Point change in a FRED series over roughly the last N calendar days (used for the 10-Year
    Treasury yield change feeding the Sector Divergence gauge). Returns None on any failure."""
    start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    obs = fetch_fred(series_id, limit=60, sort_order="asc", observation_start=start)
    if not obs or len(obs) < 2:
        return None
    return obs[-1]["value"] - obs[0]["value"]

def fetch_etf_return(ticker, trading_days=20):
    """Percent return of an ETF/index over the last N trading days. Returns None on failure."""
    try:
        data = yf.download(ticker, period="2mo", interval="1d", progress=False, auto_adjust=True)
        if data.empty or len(data) < trading_days + 1:
            return None
        close = data['Close']
        latest = close.iloc[-1].item()
        past = close.iloc[-(trading_days + 1)].item()
        if past == 0:
            return None
        return (latest - past) / past * 100
    except Exception:
        return None

def fetch_vix_change(trading_days=20):
    """Point change (not %) in the VIX over the last N trading days. Returns None on failure."""
    try:
        data = yf.download("^VIX", period="2mo", interval="1d", progress=False, auto_adjust=True)
        if data.empty or len(data) < trading_days + 1:
            return None
        close = data['Close']
        return close.iloc[-1].item() - close.iloc[-(trading_days + 1)].item()
    except Exception:
        return None

def compute_sector_divergence():
    """Sector Momentum vs. Macro Divergence gauge.

    For each sector SPDR ETF, compares:
      - Momentum Score: the ETF's 20-trading-day return relative to SPY's 20-trading-day return
        (positive = the sector is outperforming the broad market; negative = underperforming),
        scaled to roughly -50..+50.
      - Macro Fit Score: what that same ~1-month window in rates, oil, VIX, and inflation would
        suggest for the sector, using the illustrative SECTOR_MACRO_SENSITIVITIES weights above,
        also scaled to roughly -50..+50.
      - Divergence = Momentum Score - Macro Fit Score. A large positive divergence means the
        sector has moved further than the macro backdrop alone would explain (momentum/sentiment
        running ahead of fundamentals); a large negative divergence means the opposite. Near zero
        means the sector's move looks broadly consistent with the macro backdrop.

    All inputs are free, real data (yfinance price history + FRED). Returns None if any of the
    four macro inputs fails to fetch (whole gauge is skipped rather than shown with a gap), or a
    dict with the macro readings and a list of per-sector results.
    """
    spy_return = fetch_etf_return("SPY", 20)
    oil_pct = fetch_etf_return("CL=F", 20)
    vix_chg = fetch_vix_change(20)
    rate_chg = fetch_fred_recent_change("DGS10", 30)
    cpi_mom = fetch_fred_mom("CPIAUCSL")
    cpi_chg = cpi_mom["num"] if cpi_mom else None

    if spy_return is None or oil_pct is None or vix_chg is None or rate_chg is None or cpi_chg is None:
        print("Warning: sector divergence gauge skipped - one or more macro inputs failed to fetch "
              f"(spy_return={spy_return}, oil_pct={oil_pct}, vix_chg={vix_chg}, rate_chg={rate_chg}, cpi_chg={cpi_chg})")
        return None

    # Normalize each macro delta to a -1..+1 signal before applying sector weights.
    rate_signal = max(-1, min(1, rate_chg / 0.25))
    oil_signal = max(-1, min(1, oil_pct / 10))
    vix_signal = max(-1, min(1, vix_chg / 5))
    infl_signal = max(-1, min(1, cpi_chg / 0.5))

    sectors = []
    for name, ticker in SECTOR_ETFS:
        sector_return = fetch_etf_return(ticker, 20)
        weights = SECTOR_MACRO_SENSITIVITIES.get(ticker)
        if sector_return is None or not weights:
            continue
        momentum_score = max(-50, min(50, (sector_return - spy_return) * 5))
        weight_sum = sum(abs(w) for w in weights.values()) or 1
        macro_raw = (weights["rate"] * rate_signal + weights["oil"] * oil_signal +
                     weights["vix"] * vix_signal + weights["infl"] * infl_signal)
        macro_score = max(-50, min(50, 50 * macro_raw / weight_sum))
        divergence = momentum_score - macro_score
        sectors.append({
            "name": name, "ticker": ticker, "sector_return": sector_return,
            "momentum_score": momentum_score, "macro_score": macro_score, "divergence": divergence,
        })

    if not sectors:
        return None

    return {
        "spy_return": spy_return, "oil_pct": oil_pct, "vix_chg": vix_chg,
        "rate_chg": rate_chg, "cpi_chg": cpi_chg, "sectors": sectors,
    }

def fetch_payrolls():
    """Monthly change in nonfarm payrolls now vs 6 months ago (PAYEMS in thousands)."""
    obs = fetch_fred("PAYEMS", limit=8)
    if not obs or len(obs) < 2:
        return None
    chg_now = obs[0]["value"] - obs[1]["value"]
    chg_6mo = None
    if len(obs) >= 8:
        chg_6mo = obs[6]["value"] - obs[7]["value"]
    history = []
    max_i = min(len(obs) - 2, 6)
    for i in range(max_i, -1, -1):
        history.append(obs[i]["value"] - obs[i + 1]["value"])
    return {"display": f"{chg_now:+,.0f}K jobs", "num": chg_now, "num_6mo": chg_6mo,
            "date": obs[0]["date"], "history": history}

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

crypto_rows = []
for name, symbol in CRYPTO:
    r = fetch_simple_price(symbol)
    if r:
        crypto_rows.append({"name": name, **r})

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

core_pce = fetch_fred_yoy("PCEPILFE")
unemployment = fetch_fred_rate("UNRATE")
gdp_growth = fetch_fred_yoy_quarterly("GDPC1")
_fed_funds_row = next((r for r in rate_rows if r["name"] == "Fed Funds Rate"), None)

def compute_fed_targets():
    """Builds the Fed Policy Targets table: for each indicator, the actual reading, the Fed's
    longer-run target/projection, the deviation, and how many of the last few readings were
    above vs. below that target. Colors reflect distance from target only (not a judgment of
    whether above or below is "good," since that depends on the indicator and the Fed's dual
    mandate, not a simple direction). Skips any indicator whose data fetch failed."""
    rows = []
    specs = [
        ("CPI Inflation (YoY)", cpi, FED_LONGER_RUN_TARGETS["cpi_inflation"], "num", "history"),
        ("Core PCE Inflation (YoY)", core_pce, FED_LONGER_RUN_TARGETS["core_pce_inflation"], "num", "history"),
        ("Unemployment Rate", unemployment, FED_LONGER_RUN_TARGETS["unemployment"], "value", "history"),
        ("Real GDP Growth (YoY)", gdp_growth, FED_LONGER_RUN_TARGETS["gdp_growth"], "num", "history"),
        ("Effective Fed Funds Rate", _fed_funds_row, FED_LONGER_RUN_TARGETS["fed_funds_neutral"], "value", "history"),
    ]
    for name, source, target, value_key, hist_key in specs:
        if not source or source.get(value_key) is None:
            continue
        actual = source[value_key]
        deviation = actual - target
        history = source.get(hist_key) or []
        above = sum(1 for v in history if v > target)
        below = sum(1 for v in history if v < target)
        rows.append({
            "name": name, "actual": actual, "target": target, "deviation": deviation,
            "months_above": above, "months_below": below, "history_len": len(history),
        })
    return rows

fed_targets_rows = compute_fed_targets()

re_national_rows = []
for name, series_id, unit in RE_NATIONAL:
    r = fetch_fred_rate(series_id)
    if r:
        re_national_rows.append({"name": name, "unit": unit, **r})

international_housing_rows = []
for country, nominal_id, real_id in INTERNATIONAL_HOUSING:
    nominal = fetch_fred_yoy_quarterly(nominal_id)
    real = fetch_fred_yoy_quarterly(real_id)
    if nominal:
        international_housing_rows.append({
            "country": country,
            "nominal_yoy": nominal["num"],
            "real_yoy": real["num"] if real else None,
            "date": nominal["date"],
            "history": nominal["history"],
        })

consumer_debt_rows = []
for name, series_id, unit, factor in CONSUMER_DEBT:
    r = fetch_fred_rate(series_id)
    if r:
        r["value"] = r["value"] * factor
        if r.get("value_6mo") is not None:
            r["value_6mo"] = r["value_6mo"] * factor
        if r.get("history"):
            r["history"] = [v * factor for v in r["history"]]
        consumer_debt_rows.append({"name": name, "unit": unit, **r})

currency_rows = []
for name, code, series_id, direction in CURRENCY_SERIES:
    r = fetch_fred_rate(series_id)
    if r:
        currency_rows.append({"name": name, "code": code, "direction": direction, **r})

treasury_rows = []
for name, series_id in TREASURY_YIELDS:
    r = fetch_fred_rate(series_id)
    if r:
        treasury_rows.append({"name": name, **r})

corporate_bond_rows = []
for name, series_id in CORPORATE_BOND_SERIES:
    r = fetch_fred_rate(series_id)
    if r:
        corporate_bond_rows.append({"name": name, **r})

# 10yr-2yr yield curve spread - a classic recession/inversion indicator. Computed here
# rather than fetched as its own FRED series, since we already have both legs above.
yield_curve_spread = None
_t10 = next((r for r in treasury_rows if r["name"] == "10-Year Treasury"), None)
_t2 = next((r for r in treasury_rows if r["name"] == "2-Year Treasury"), None)
if _t10 and _t2:
    yield_curve_spread = {
        "name": "10-Yr minus 2-Yr Spread",
        "value": round(_t10["value"] - _t2["value"], 2),
        "date": _t10["date"],
        "value_6mo": (round(_t10["value_6mo"] - _t2["value_6mo"], 2)
                      if _t10.get("value_6mo") is not None and _t2.get("value_6mo") is not None else None),
    }

state_rows = []
for state_name, abbr in STATES:
    r = fetch_state_hpi(abbr)
    if r:
        state_rows.append({"state": state_name, **r})
state_rows.sort(key=lambda x: -x["yoy"])

# County-level data for the Investment Map (see PAGE 12 below for the map itself).
county_population_data = fetch_census_county_population()
county_housing_units_data = fetch_census_county_housing_units()
county_unemployment_data = fetch_bls_county_unemployment()
county_home_value_data = fetch_census_county_median_home_value()
county_vacant_for_sale_data = fetch_census_county_vacant_for_sale()
county_total_vacancy_data = fetch_census_county_total_vacancy()
county_rent_data = fetch_census_county_median_rent()
county_income_data = fetch_census_county_median_income()
county_permits_data = fetch_census_county_building_permits()
county_permit_growth_data = fetch_census_county_permit_growth()
puerto_rico_geojson = fetch_puerto_rico_municipio_boundaries()
territory_geojson = fetch_territory_boundaries()

# Merge 5-year housing-unit growth into the same per-FIPS dict, same pattern as every other
# county layer below.
if county_housing_units_data:
    if county_population_data is None:
        county_population_data = {}
    for fips, rec in county_housing_units_data.items():
        if fips not in county_population_data:
            county_population_data[fips] = {"name": rec["name"], "pop": None, "pop_5yr_ago": None, "growth_pct": None}
        elif not county_population_data[fips].get("name"):
            county_population_data[fips]["name"] = rec["name"]
        county_population_data[fips]["housing_units"] = rec["housing_units"]
        county_population_data[fips]["housing_units_5yr_ago"] = rec["housing_units_5yr_ago"]
        county_population_data[fips]["housing_growth_pct"] = rec["housing_growth_pct"]

# Merge unemployment into the same per-FIPS dict the population data uses, so the client only
# needs one data structure with a layer toggle, rather than two separate fetches/objects.
if county_unemployment_data:
    if county_population_data is None:
        county_population_data = {}
    for fips, rec in county_unemployment_data.items():
        if fips not in county_population_data:
            county_population_data[fips] = {"name": None, "pop": None, "pop_5yr_ago": None, "growth_pct": None}
        county_population_data[fips]["unemployment_rate"] = rec["rate"]
        county_population_data[fips]["unemployment_period"] = rec["period"]

# Same merge pattern for median home value.
if county_home_value_data:
    if county_population_data is None:
        county_population_data = {}
    for fips, rec in county_home_value_data.items():
        if fips not in county_population_data:
            county_population_data[fips] = {"name": rec["name"], "pop": None, "pop_5yr_ago": None, "growth_pct": None}
        elif not county_population_data[fips].get("name"):
            county_population_data[fips]["name"] = rec["name"]
        county_population_data[fips]["median_home_value"] = rec["median_home_value"]

# Same merge pattern for vacant homes for sale.
if county_vacant_for_sale_data:
    if county_population_data is None:
        county_population_data = {}
    for fips, rec in county_vacant_for_sale_data.items():
        if fips not in county_population_data:
            county_population_data[fips] = {"name": rec["name"], "pop": None, "pop_5yr_ago": None, "growth_pct": None}
        elif not county_population_data[fips].get("name"):
            county_population_data[fips]["name"] = rec["name"]
        county_population_data[fips]["vacant_for_sale"] = rec["vacant_for_sale"]

# Same merge pattern for total vacancy.
if county_total_vacancy_data:
    if county_population_data is None:
        county_population_data = {}
    for fips, rec in county_total_vacancy_data.items():
        if fips not in county_population_data:
            county_population_data[fips] = {"name": rec["name"], "pop": None, "pop_5yr_ago": None, "growth_pct": None}
        elif not county_population_data[fips].get("name"):
            county_population_data[fips]["name"] = rec["name"]
        county_population_data[fips]["vacant_total"] = rec["vacant_total"]

# Same merge pattern for median rent.
if county_rent_data:
    if county_population_data is None:
        county_population_data = {}
    for fips, rec in county_rent_data.items():
        if fips not in county_population_data:
            county_population_data[fips] = {"name": rec["name"], "pop": None, "pop_5yr_ago": None, "growth_pct": None}
        elif not county_population_data[fips].get("name"):
            county_population_data[fips]["name"] = rec["name"]
        county_population_data[fips]["median_rent"] = rec["median_rent"]

# Same merge pattern for median household income.
if county_income_data:
    if county_population_data is None:
        county_population_data = {}
    for fips, rec in county_income_data.items():
        if fips not in county_population_data:
            county_population_data[fips] = {"name": rec["name"], "pop": None, "pop_5yr_ago": None, "growth_pct": None}
        elif not county_population_data[fips].get("name"):
            county_population_data[fips]["name"] = rec["name"]
        county_population_data[fips]["median_income"] = rec["median_income"]

# Same merge pattern for building permits.
if county_permits_data:
    if county_population_data is None:
        county_population_data = {}
    for fips, rec in county_permits_data.items():
        if fips not in county_population_data:
            county_population_data[fips] = {"name": rec["name"], "pop": None, "pop_5yr_ago": None, "growth_pct": None}
        elif not county_population_data[fips].get("name"):
            county_population_data[fips]["name"] = rec["name"]
        county_population_data[fips]["building_permits"] = rec["building_permits"]

# Same merge pattern for year-over-year permit growth.
if county_permit_growth_data:
    if county_population_data is None:
        county_population_data = {}
    for fips, rec in county_permit_growth_data.items():
        if fips not in county_population_data:
            county_population_data[fips] = {"name": rec["name"], "pop": None, "pop_5yr_ago": None, "growth_pct": None}
        elif not county_population_data[fips].get("name"):
            county_population_data[fips]["name"] = rec["name"]
        county_population_data[fips]["permits_current"] = rec["permits_current"]
        county_population_data[fips]["permits_prior"] = rec["permits_prior"]
        county_population_data[fips]["permit_growth_pct"] = rec["permit_growth_pct"]
        county_population_data[fips]["single_family_permits"] = rec["single_family_permits"]
        county_population_data[fips]["multifamily_permits"] = rec["multifamily_permits"]
        county_population_data[fips]["multifamily_share_pct"] = rec["multifamily_share_pct"]

# Merge the four Island Areas (American Samoa, Guam, CNMI, USVI) into the same structure, using
# their FIPS-equivalent state codes as keys. Unlike the merges above, TERRITORY_DATA already has
# every field in one place per territory (it's manually-researched, not built up incrementally
# from several separate API calls), so this merge is simpler - no per-field existence checks
# needed.
if county_population_data is None:
    county_population_data = {}
for territory_name, fips in TERRITORY_FIPS.items():
    rec = TERRITORY_DATA[territory_name]
    county_population_data[fips + "000"] = {
        "name": territory_name,
        "pop": rec["pop"],
        "pop_5yr_ago": None,
        "growth_pct": None,
        "unemployment_rate": rec["unemployment_rate"],
        "unemployment_period": "2020 Island Areas Census",
        "median_home_value": rec["median_home_value"],
        "median_rent": rec["median_rent"],
        "median_income": rec["median_income"],
        "building_permits": None,
    }

oversold_count = sum(1 for r in rows if r["rsi"] <= RSI_OVERSOLD)
overbought_count = sum(1 for r in rows if r["rsi"] >= RSI_OVERBOUGHT)
top_mover = max(rows, key=lambda r: abs(r["pct"])) if rows else None

# ------------------- NEWS FEED (Currents API - free tier, commercial use permitted) -------------------
business_news = fetch_currents_news("business")

# ------------------- MARKET ALERT GAUGES (once per digest run, not per visit) -------------------
# Reuses data already fetched above - no additional API calls needed beyond the one Claude call
# per gauge. History accumulates in a small JSON file committed alongside the site each run.

def find_row(rows_list, name):
    return next((r for r in rows_list if r.get("name") == name), None)

_sp500 = find_row(index_rows, "S&P 500")
_dow = find_row(index_rows, "Dow Jones")
_nasdaq = find_row(index_rows, "Nasdaq Composite")
_fed_funds = find_row(rate_rows, "Fed Funds Rate")
_yield_curve = find_row(curve_rows, "10-Yr minus 2-Yr Spread")
_oil = find_row(commodity_rows, "Oil (WTI)")
_chip_tickers = ["NVDA", "AMD", "INTC", "QCOM", "TSM", "MU", "AVGO"]
_chip_pcts = [r["pct"] for r in rows if r["ticker"] in _chip_tickers]

_stock_snapshot_parts = []
if _sp500: _stock_snapshot_parts.append(f"S&P 500: {_sp500['price']} ({_sp500['pct']:+.2f}% today)")
if _dow: _stock_snapshot_parts.append(f"Dow Jones: {_dow['price']} ({_dow['pct']:+.2f}% today)")
if _nasdaq: _stock_snapshot_parts.append(f"Nasdaq Composite: {_nasdaq['price']} ({_nasdaq['pct']:+.2f}% today)")
if _fed_funds: _stock_snapshot_parts.append(f"Fed Funds Rate: {_fed_funds['value']:.2f}%")
if _yield_curve: _stock_snapshot_parts.append(f"10-Yr minus 2-Yr Spread: {_yield_curve['value']:.2f}")
if _oil: _stock_snapshot_parts.append(f"Oil (WTI): {_oil['price']} ({_oil['pct']:+.2f}% today)")
if _chip_pcts:
    _avg_chip = sum(_chip_pcts) / len(_chip_pcts)
    _stock_snapshot_parts.append(f"Semiconductor sector (avg of {len(_chip_pcts)} major chip stocks): {_avg_chip:+.2f}% today")

_stock_history = load_alert_history("market_alert_stocks_history.json")
_todays_stock_entry = get_todays_entry(_stock_history)
if _todays_stock_entry:
    # Already generated once today (this workflow runs every 15 min for fresh prices, but the
    # market alert only needs to run once per day) - reuse today's existing result.
    _stock_score_data = {"score": _todays_stock_entry["score"], "explanation": _todays_stock_entry["explanation"]}
else:
    _stock_score_data = None
    if _stock_snapshot_parts:
        _stock_score_data = call_anthropic_market_alert(". ".join(_stock_snapshot_parts))
    if _stock_score_data:
        _stock_history = append_to_history(_stock_history, _stock_score_data["score"], _stock_score_data["explanation"])
        save_alert_history("market_alert_stocks_history.json", _stock_history)

_mortgage_rate = find_row(re_national_rows, "30-Yr Mortgage Rate")
_housing_starts = find_row(re_national_rows, "Housing Starts (annualized)")
_permits = find_row(re_national_rows, "Building Permits (annualized)")
_new_home_sales = find_row(re_national_rows, "New Home Sales (annualized)")
_delinquency = find_row(re_national_rows, "Mortgage Delinquency Rate")

_re_snapshot_parts = []
if _mortgage_rate: _re_snapshot_parts.append(f"30-Yr Mortgage Rate: {_mortgage_rate['value']:.2f}%, 6 months ago: {_mortgage_rate.get('value_6mo')}")
if _housing_starts: _re_snapshot_parts.append(f"Housing Starts (annualized): {_housing_starts['value']:.0f}K, 6 months ago: {_housing_starts.get('value_6mo')}")
if _permits: _re_snapshot_parts.append(f"Building Permits (annualized): {_permits['value']:.0f}K, 6 months ago: {_permits.get('value_6mo')}")
if _new_home_sales: _re_snapshot_parts.append(f"New Home Sales (annualized): {_new_home_sales['value']:.0f}K, 6 months ago: {_new_home_sales.get('value_6mo')}")
if _delinquency: _re_snapshot_parts.append(f"Mortgage Delinquency Rate: {_delinquency['value']:.2f}%, 6 months ago: {_delinquency.get('value_6mo')}")

_re_history = load_alert_history("market_alert_realestate_history.json")
_todays_re_entry = get_todays_entry(_re_history)
if _todays_re_entry:
    _re_score_data = {"score": _todays_re_entry["score"], "explanation": _todays_re_entry["explanation"]}
else:
    _re_score_data = None
    if _re_snapshot_parts:
        _re_score_data = call_anthropic_market_alert(". ".join(_re_snapshot_parts) + ". This is for a real estate market condition assessment, not general stocks.")
    if _re_score_data:
        _re_history = append_to_history(_re_history, _re_score_data["score"], _re_score_data["explanation"])
        save_alert_history("market_alert_realestate_history.json", _re_history)

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
    <tr data-ticker="{r['ticker']}" data-pct="{r['pct']}">
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
        price_decimals = 2 if i["price"] >= 0.01 else 8
        spark = sparkline_svg(i.get("history", []))
        insight = ai_insight_button(i['name'], i['price'], prefix, i['pct'], i.get('price_6mo'), i.get('history'))
        out += f"""
    <div class="card" title="{def_for(i['name'])}">
      <p class="label">{i['name']}</p>
      <p class="value">{prefix}{i['price']:,.{price_decimals}f}</p>
      <p style="margin:2px 0 0;font-size:13px;color:{pct_color(i['pct'])};">{i['pct']:+.2f}% today</p>
      {spark}
      {six}
      {insight}
    </div>"""
    return out

def rate_cards(items):
    out = ""
    for i in items:
        six = sixmo_line(i.get("value_6mo"), i["value"], unit="%", pt_label=True)
        spark = sparkline_svg(i.get("history", []))
        insight = ai_insight_button(i['name'], i['value'], "%", None, i.get('value_6mo'), i.get('history'))
        out += f"""
    <div class="card" title="{def_for(i['name'])}">
      <p class="label">{i['name']}</p>
      <p class="value">{i['value']:.2f}%</p>
      <p style="margin:2px 0 0;font-size:11px;color:#999;">as of {i['date']}</p>
      {spark}
      {six}
      {insight}
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
        spark = sparkline_svg(i.get("history", []))
        insight = ai_insight_button(i['name'], i.get('num', i['display']), "", None, i.get('num_6mo'), i.get('history'))
        out += f"""
    <div class="card" title="{def_for(i['name'])}">
      <p class="label">{i['name']}</p>
      <p class="value">{i['display']}</p>
      <p style="margin:2px 0 0;font-size:11px;color:#999;">as of {i['date']}</p>
      {spark}
      {six}
      {insight}
    </div>"""
    return out

def fed_targets_table(rows):
    if not rows:
        return ""
    body = ""
    for r in rows:
        abs_dev = abs(r["deviation"])
        if abs_dev <= 0.3:
            read, color = "At target", "#1a8a3d"
        elif abs_dev <= 1.0:
            read, color = "Moderate gap", "#a5720b"
        else:
            read, color = "Large gap", "#c0392b"
        trend = ""
        if r["history_len"] > 0:
            trend = f"{r['months_above']} of last {r['history_len']} readings above, {r['months_below']} below"
        if abs_dev <= 0.3:
            meaning = f"{r['name']} is sitting right around the Fed's own target - not a source of policy pressure right now."
        else:
            direction = "above" if r["deviation"] > 0 else "below"
            meaning = f"{r['name']} is running {direction} the Fed's target, which is the kind of gap the Fed factors into its rate decisions."
        body += f"""
    <tr>
      <td style="font-weight:600;border-bottom:1px dotted #999;cursor:help;" title="{def_for(r['name'])}">{r['name']}</td>
      <td style="text-align:right;">{r['actual']:.1f}%</td>
      <td style="text-align:right;">{r['target']:.1f}%</td>
      <td style="text-align:right;font-weight:600;color:{color};">{r['deviation']:+.1f}pt</td>
      <td style="color:{color};">{read}</td>
      <td style="font-size:11px;color:#888;">{trend}</td>
    </tr>
    <tr class="learning-mode-only">
      <td colspan="6" style="font-size:12px;color:#555;background:#f7faf7;">&#127891; Meaning: {meaning}</td>
    </tr>"""
    return f"""
<h2>Fed Policy Targets</h2>
<p class="note">Compares each indicator's latest reading to the Federal Reserve's own longer-run target or projection ({FED_TARGETS_ASOF}). Inflation targets (CPI, Core PCE) are the Fed's official, fixed 2% policy goal. Unemployment, GDP growth, and the federal funds "neutral rate" are NOT fixed targets - they're the median of individual FOMC members' own quarterly forecasts (the Summary of Economic Projections), and they move release to release; the color reflects distance from target only, not a judgment that above or below is "good," since that depends on the indicator and the Fed's mandate. This is an educational, informational tool - not a prediction, a recommendation, or personalized investment advice.</p>
<div class="table-wrap">
<table>
<tr><th>Indicator</th><th style="text-align:right;">Actual</th><th style="text-align:right;">Fed Target</th><th style="text-align:right;">Deviation</th><th>Read</th><th>Recent Trend</th></tr>
{body}
</table>
</div>
"""

def bond_cards(items):
    out = ""
    for i in items:
        val = f"{i['value']:.2f}%"
        six = sixmo_line(i.get("value_6mo"), i["value"], unit="%", pt_label=True)
        spark = sparkline_svg(i.get("history", []))
        insight = ai_insight_button(i['name'], i['value'], "%", None, i.get('value_6mo'), i.get('history'))
        out += f"""
    <div class="card">
      <p class="label">{i['name']}</p>
      <p class="value">{val}</p>
      <p style="margin:2px 0 0;font-size:11px;color:#999;">as of {i['date']}</p>
      {spark}
      {six}
      {insight}
    </div>"""
    return out

def re_national_cards(items):
    out = ""
    for i in items:
        if i["unit"] == "%":
            val = f"{i['value']:.2f}%"
            six = sixmo_line(i.get("value_6mo"), i["value"], unit="%", pt_label=True)
        elif i["unit"] == "$B":
            val = f"${i['value']:,.1f}B"
            six = sixmo_line(i.get("value_6mo"), i["value"], unit="$B")
        elif i["unit"] == "mo":
            val = f"{i['value']:.1f} months"
            six = sixmo_line(i.get("value_6mo"), i["value"], unit=" months")
        else:
            val = f"{i['value']:,.0f}K"
            six = sixmo_line(i.get("value_6mo"), i["value"], unit="K")
        spark = sparkline_svg(i.get("history", []))
        insight = ai_insight_button(i['name'], i['value'], i['unit'] if i['unit'] != "$B" else "B", None, i.get('value_6mo'), i.get('history'))
        out += f"""
    <div class="card" title="{def_for(i['name'])}">
      <p class="label">{i['name']}</p>
      <p class="value">{val}</p>
      <p style="margin:2px 0 0;font-size:11px;color:#999;">as of {i['date']}</p>
      {spark}
      {six}
      {insight}
    </div>"""
    return out

def international_housing_cards(items):
    out = ""
    for i in items:
        val = f"{i['nominal_yoy']:+.1f}% YoY"
        real_line = (
            f"<p style='margin:4px 0 0;font-size:12px;color:var(--text-secondary);'>Inflation-adjusted: {i['real_yoy']:+.1f}% YoY</p>"
            if i.get("real_yoy") is not None else ""
        )
        spark = sparkline_svg(i.get("history", []))
        insight = ai_insight_button(f"{i['country']} House Prices (YoY)", i['nominal_yoy'], "%", None, None, i.get('history'))
        out += f"""
    <div class="card" title="{def_for('International Residential Property Prices')}">
      <p class="label">{i['country']}</p>
      <p class="value">{val}</p>
      {real_line}
      <p style="margin:2px 0 0;font-size:11px;color:#999;">as of {i['date']}</p>
      {spark}
      {insight}
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
        spark = sparkline_svg(i.get("history", []))
        insight = ai_insight_button(f"{i['name']} ({i['code']})", i['value'], "", None, i.get('value_6mo'), i.get('history'))
        out += f"""
    <div class="card" title="{def_for(i['name'])}">
      <p class="label">{i['name']} ({i['code']})</p>
      <p class="value" style="font-size:16px;">{val}</p>
      <p style="margin:2px 0 0;font-size:11px;color:#999;">as of {i['date']}</p>
      {spark}
      {six}
      {insight}
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

def sector_divergence_html(data):
    if not data:
        return ""
    rows = ""
    for s in sorted(data["sectors"], key=lambda x: x["divergence"], reverse=True):
        div = s["divergence"]
        if div > 15:
            label, color = "Sentiment running ahead of fundamentals", "#c0392b"
        elif div < -15:
            label, color = "Lagging what fundamentals would suggest", "#1a8a3d"
        else:
            label, color = "Roughly in line with fundamentals", "#666"
        rows += f"""
    <tr>
      <td style="font-weight:600;">{s['name']} ({s['ticker']})</td>
      <td style="text-align:right;">{s['sector_return']:+.1f}%</td>
      <td style="text-align:right;">{s['momentum_score']:+.0f}</td>
      <td style="text-align:right;">{s['macro_score']:+.0f}</td>
      <td style="text-align:right;font-weight:600;color:{color};">{div:+.0f}</td>
      <td style="color:{color};">{label}</td>
    </tr>"""
    return f"""
<h2>Fundamentals vs. Sentiment Gauge (by Sector)</h2>
<p class="note">Compares each sector's actual 20-trading-day performance (Momentum Score) against what the same window's move in the 10-Year Treasury yield ({data['rate_chg']:+.2f}pt), WTI crude oil ({data['oil_pct']:+.1f}%), the VIX ({data['vix_chg']:+.1f}pt), and CPI inflation ({data['cpi_chg']:+.2f}% MoM) would suggest (Fundamentals - Macro Fit Score), using a transparent, illustrative set of sector sensitivity weights - not a statistically fitted model. SPY's own 20-day return was {data['spy_return']:+.1f}%, used as the broad-market baseline for Momentum Score. A large positive Sentiment (Divergence) means the sector has moved further than fundamentals alone would explain; a large negative Sentiment (Divergence) means the opposite; near zero means the move looks broadly consistent with fundamentals. This is an educational, informational tool illustrating one way to think about sector moves - not a prediction, a recommendation, or personalized investment advice.</p>
<div class="table-wrap">
<table>
<tr><th>Sector</th><th style="text-align:right;">20-Day Return</th><th style="text-align:right;" title="Sector's 20-day return relative to SPY, scaled to roughly -50..+50">Momentum Score</th><th style="text-align:right;" title="What the macro/fundamental backdrop alone would suggest, scaled to roughly -50..+50">Fundamentals (Macro Fit Score)</th><th style="text-align:right;" title="Momentum Score minus Fundamentals (Macro Fit Score)">Sentiment (Divergence)</th><th>Read</th></tr>
{rows}
</table>
</div>
"""


def beginner_summary_html(fed_rows, sector_data):
    """Plain-English snapshot built entirely from data already computed elsewhere on this page
    (Fed Policy Targets deviations, Sector Divergence). Deliberately descriptive only - states
    where each reading sits relative to its target, never a prediction of what markets will do
    next, and never a recommendation. Hidden unless Learning Mode is toggled on."""
    bullets = []
    for r in fed_rows:
        dev = r["deviation"]
        if abs(dev) <= 0.3:
            bullets.append(f"{r['name']} is close to the Fed's target ({r['target']:.1f}%).")
        else:
            direction = "above" if dev > 0 else "below"
            plural = "s" if abs(round(dev, 1)) != 1 else ""
            bullets.append(f"{r['name']} is {abs(dev):.1f} point{plural} {direction} the Fed's target ({r['target']:.1f}%).")
    if sector_data and sector_data.get("sectors"):
        strongest = max(sector_data["sectors"], key=lambda s: s["divergence"])
        weakest = min(sector_data["sectors"], key=lambda s: s["divergence"])
        bullets.append(f"{strongest['name']} is trading furthest ahead of what its fundamentals alone would suggest today.")
        bullets.append(f"{weakest['name']} is trading furthest behind what its fundamentals alone would suggest today.")
    if not bullets:
        return ""
    items = "".join(f"<li>{b}</li>" for b in bullets)
    return f"""
<div class="beginner-box learning-mode-only">
<h3>&#127891; Beginner Summary - Plain-English Snapshot</h3>
<ul>{items}</ul>
<p style="font-size:11px;color:#888;margin:8px 0 0;">These are plain-language descriptions of the data shown further down this page - not predictions of what will happen next, and not a recommendation to buy or sell anything. Turn off Learning Mode (top of page) to hide this and see just the raw data.</p>
</div>
"""

timestamp = datetime.now().strftime('%Y-%m-%d %H:%M UTC')
sector_divergence_data = compute_sector_divergence()
top_mover_html = f"{top_mover['ticker']} ({top_mover['pct']:+.2f}%)" if top_mover else "-"

# ------------------- PAGE 1: STOCKS -------------------

stocks_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily Stock Digest</title>
<style>{PAGE_CSS}
body.dark-mode {{
  --bg: #0d0d0d;
  --text: #e8e8e8;
  --text-secondary: #b0b0b0;
  --text-muted: #909090;
  --text-faint: #787878;
  --card-bg: #1a1a1a;
  --card-border: #333;
  --table-header-bg: #222;
  --table-row-border: #2a2a2a;
}}
#theme-toggle {{
  position: fixed; top: 16px; right: 16px; z-index: 1000;
  padding: 8px 14px; font-size: 13px; font-weight: 600;
  background: var(--card-bg); color: var(--text); border: 1px solid var(--card-border);
  border-radius: 20px; cursor: pointer;
}}
{CHART_MODE_CSS}
.learning-mode-only {{ display: none; }}
body.learning-mode .learning-mode-only {{ display: block; }}
tr.learning-mode-only {{ display: none; }}
body.learning-mode tr.learning-mode-only {{ display: table-row; }}
.beginner-box {{ background: #eef6f0; border:1px solid #cfe8d6; border-radius:10px; padding:14px 16px; margin-bottom:16px; }}
.beginner-box h3 {{ margin:0 0 8px; font-size:14px; }}
.beginner-box ul {{ margin:0; padding-left:18px; font-size:13px; line-height:1.6; }}
</style>
</head>
<body>
<button id="theme-toggle" onclick="toggleTheme()">&#9680; Dark Mode</button>
{CHART_MODE_BUTTON}
<button id="learning-mode-toggle" onclick="toggleLearningMode()">&#127891; Learning Mode: Off</button>
<script>
(function() {{
  var savedLearning = localStorage.getItem('siteLearningMode');
  if (savedLearning === 'on') {{
    document.addEventListener('DOMContentLoaded', function() {{
      document.body.classList.add('learning-mode');
      document.getElementById('learning-mode-toggle').innerHTML = '&#127891; Learning Mode: On';
    }});
  }}
}})();
function toggleLearningMode() {{
  var isOn = document.body.classList.toggle('learning-mode');
  localStorage.setItem('siteLearningMode', isOn ? 'on' : 'off');
  document.getElementById('learning-mode-toggle').innerHTML = isOn ? '&#127891; Learning Mode: On' : '&#127891; Learning Mode: Off';
}}
(function() {{
  var saved = localStorage.getItem('siteDarkMode');
  if (saved === 'dark') {{
    document.addEventListener('DOMContentLoaded', function() {{
      document.body.classList.add('dark-mode');
      document.getElementById('theme-toggle').innerHTML = '&#9728; Light Mode';
    }});
  }}
}})();
function toggleTheme() {{
  var isDark = document.body.classList.toggle('dark-mode');
  localStorage.setItem('siteDarkMode', isDark ? 'dark' : 'light');
  document.getElementById('theme-toggle').innerHTML = isDark ? '&#9728; Light Mode' : '&#9680; Dark Mode';
}}

{CHART_MODE_JS}

var AI_INSIGHT_WORKER_URL = "https://finnhub-proxy.tonyhernandezusa.workers.dev";

function showAIInsight(btn) {{
  var card = btn.closest('.card');
  var area = card.querySelector('.ai-insight-area');
  var isOpen = area.style.display !== 'none';
  if (isOpen) {{
    area.style.display = 'none';
    btn.textContent = '🤖 AI Insight';
    return;
  }}
  area.style.display = 'block';
  btn.textContent = '🤖 Hide Insight';

  if (area.getAttribute('data-loaded') === 'true') return; // already fetched once, just re-showing

  area.innerHTML = '<span style="font-size:11px;color:#888;">Asking AI for context...</span>';
  var params = new URLSearchParams({{
    name: btn.getAttribute('data-name') || '',
    value: btn.getAttribute('data-value') || '',
    unit: btn.getAttribute('data-unit') || '',
    pct: btn.getAttribute('data-pct') || '',
    sixMo: btn.getAttribute('data-sixmo') || '',
    history: btn.getAttribute('data-history') || ''
  }});
  fetch(AI_INSIGHT_WORKER_URL + '/ai-chart-insight?' + params.toString())
    .then(function(resp) {{ return resp.json(); }})
    .then(function(data) {{
      if (data.error) {{
        area.innerHTML = '<span style="font-size:11px;color:#c0392b;">' + data.error + '</span>';
        return;
      }}
      // Defensive cleanup in case the AI includes markdown despite being asked not to -
      // strip headers/bold markers and convert paragraph breaks to real HTML breaks.
      var cleaned = data.insight
        .replace(/^#{{1,6}}\s*/gm, '')
        .replace(/\*\*(.+?)\*\*/g, '$1')
        .replace(/\\n\s*\\n/g, '</p><p style="font-size:12px;line-height:1.5;margin:8px 0 0;">')
        .replace(/\\n/g, ' ')
        .trim();
      area.innerHTML = '<p style="font-size:12px;line-height:1.5;margin:6px 0 0;">' + cleaned + '</p>' +
        '<span style="font-size:10px;color:#999;">AI-generated - a general explanation, not personalized financial advice.</span>';
      area.setAttribute('data-loaded', 'true');
    }})
    .catch(function() {{
      area.innerHTML = '<span style="font-size:11px;color:#c0392b;">Could not reach the AI insight service.</span>';
    }});
}}

</script>
{NAV_HTML}
<h1>Daily Stock Digest</h1>
<p class="timestamp">Updated {timestamp}</p>

{beginner_summary_html(fed_targets_rows, sector_divergence_data)}

{render_market_alert_section(_stock_score_data, _stock_history, "Stock Market Alert")}

{news_feed_html(business_news, "Stocks & Economy News")}

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

<h2>Consumer Debt</h2>
<div class="row">{re_national_cards(consumer_debt_rows)}</div>
<p class="note">Total Consumer Credit and Credit Card Balances are non-mortgage consumer debt (credit cards, auto loans, student loans, personal loans), seasonally adjusted. Delinquency rates are the share of loans 30+ days past due. Source: Federal Reserve (FRED).</p>

<h2>Economic Indicators</h2>
<div class="row">{econ_cards(econ_rows)}</div>
<p class="note">CPI and PPI shown as year-over-year change. Retail sales month-over-month. PMI above 50 = manufacturing expansion (entered manually from ISM's monthly release). "6 mo ago" compares each reading to the same measure six months earlier.</p>

{fed_targets_table(fed_targets_rows)}

<h2>Market Indexes</h2>
<div class="row">{simple_cards(index_rows, dollar=False)}</div>

<h2>Index Futures</h2>
<div class="row">{simple_cards(futures_rows, dollar=False)}</div>
<p class="note">Stock index futures trade nearly 24 hours a day, including outside regular market hours - often what's behind "futures point to a lower/higher open" headlines. Not directly comparable to the cash index level above since futures prices include financing costs and dividend expectations.</p>

<h2>Commodities</h2>
<div class="row">{simple_cards(commodity_rows)}</div>

{sector_divergence_html(sector_divergence_data)}

<h2>Cryptocurrency</h2>
<div class="row">{simple_cards(crypto_rows)}</div>
<p class="note">Prices via Yahoo Finance, quoted in USD. Crypto trades 24/7, unlike stocks and most commodities/indices - these prices can change even when traditional markets are closed. Extremely volatile compared to traditional assets - treat accordingly.</p>

<h2>Currency Exchange Rates</h2>
<div class="row">{currency_cards(currency_rows)}</div>
<p class="note">Federal Reserve H.10 daily noon buying rates vs the US Dollar - all 23 individual currency pairs the Fed publishes daily. "USD per" currencies (Euro, Pound, Australian Dollar, New Zealand Dollar) rise when that currency strengthens against the dollar; "per USD" currencies rise when the dollar strengthens. "6 mo ago" compares to the reading six months earlier. Source: Federal Reserve (FRED).</p>

<h2>Treasury Yields</h2>
<div class="row">{bond_cards(treasury_rows)}{bond_cards([yield_curve_spread]) if yield_curve_spread else ""}</div>
<p class="note">Constant-maturity Treasury yields across the curve. The 10-Yr minus 2-Yr spread is a widely watched recession indicator - it turns negative ("inverts") when short-term yields exceed long-term yields, which has preceded past recessions, though with variable and sometimes long lead times. Source: Federal Reserve (FRED).</p>

<h2>Corporate Bond Yields &amp; Spreads</h2>
<div class="row">{bond_cards(corporate_bond_rows)}</div>
<p class="note">Moody's seasoned corporate bond yields (Aaa = highest credit quality, Baa = lowest investment-grade) and their spread over the 10-Year Treasury - the extra yield investors demand to hold corporate debt over risk-free government debt. Widening spreads generally signal rising perceived credit risk or heavier corporate borrowing demand; this is worth watching given the current wave of AI-infrastructure-related corporate bond issuance. Source: Federal Reserve (FRED), based on Moody's data.</p>

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

__FOOTER__
</body>
</html>"""
stocks_html = stocks_html.replace("__FOOTER__", FOOTER_HTML)

# ------------------- PAGE 2: REAL ESTATE -------------------

realestate_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Real Estate Dashboard</title>
<style>{PAGE_CSS}
{LEARNING_MODE_CSS}
{CHART_MODE_CSS}
</style>
</head>
<body>
{CHART_MODE_BUTTON}{LEARNING_MODE_BUTTON}<script>{LEARNING_MODE_JS}{CHART_MODE_JS}</script>
{NAV_HTML}
<h1>Real Estate Dashboard</h1>
<p class="timestamp">Updated {timestamp}</p>

{render_market_alert_section(_re_score_data, _re_history, "Real Estate Market Alert")}

<div class="beginner-box learning-mode-only">
<h3>&#127891; What These Numbers Mean</h3>
<p style="font-size:13px;line-height:1.6;margin:0;">Housing Starts, Building Permits, and New Home Sales track new construction activity - permits come first (builders getting approval), starts come next (ground actually broken), and new home sales measure whether buyers are actually purchasing what gets built. The 30-Yr Mortgage Rate is the typical borrowing cost for a home loan, and Mortgage Delinquency Rate tracks how many homeowners are falling behind on payments - a rising rate is an early warning sign. Homeownership Rate is the share of households that own (versus rent) their home. Rental Vacancy Rate and Homeowner Vacancy Rate measure how much housing sits empty and available - rising vacancy generally signals softening demand, falling vacancy signals a tightening market. None of these alone says whether now is a good time to buy or sell - they're pieces of a much bigger picture.</p>
</div>

<h2>National Housing Indicators</h2>
<div class="row">{re_national_cards(re_national_rows)}</div>
<p class="note">Housing starts, permits, and new home sales are seasonally adjusted annual rates in thousands. "6 mo ago" compares to the reading six months earlier. Source: Federal Reserve (FRED).</p>

<h2>International Housing Snapshot</h2>
<div class="beginner-box learning-mode-only">
<h3>&#127891; What This Section Shows</h3>
<p style="font-size:13px;line-height:1.6;margin:0;">Year-over-year home price growth for a small set of countries where a genuine, official house price index actually exists and is freely available. Many countries don't have this - it's tempting to substitute real estate listing-site prices instead, but those come from private commercial platforms, not government sources, so they're deliberately left out here. "Inflation-adjusted" strips out each country's own general price inflation, so it reflects real purchasing-power change in housing, not just rising prices across the board.</p>
</div>
<div class="row">{international_housing_cards(international_housing_rows)}</div>
<p class="note">Source: Bank for International Settlements Residential Property Price database (National sources, BIS Residential Property Price database, http://www.bis.org/statistics/pp.htm), via Federal Reserve (FRED). Mexico is national coverage; Colombia covers 8 major cities. Limited to countries with a verified official house price index - several countries commonly covered by real estate listing sites (e.g. Bahamas, Dominican Republic, Turks &amp; Caicos) don't have one, so aren't included here.</p>

<h2>House Price Change by State (1-Year, FHFA Index)</h2>
<div class="table-wrap">
<table>
<tr><th>Rank</th><th>State</th><th style="text-align:right;border-bottom:1px dotted #999;cursor:help;" title="{def_for('State Home Price Index (FHFA)')}">1-Yr Change</th><th style="text-align:right;">Data as of</th></tr>
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

__FOOTER__
</body>
</html>"""
realestate_html = realestate_html.replace("__FOOTER__", FOOTER_HTML)

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
__DARKMODE_CSS__
__LEARNINGMODE_CSS__
</style>
</head>
<body>
__DARKMODE_BUTTON__<script>__DARKMODE_JS__</script>
__LEARNINGMODE_BUTTON__<script>__LEARNINGMODE_JS__</script>
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

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Advanced Loan Structure (optional)</h4>
<p class="chart-caption" style="text-align:left;margin:0 0 10px;">These change how much loan your monthly budget can support, or how fast you'd pay it off - not everyone needs these, but they matter if you're considering anything other than a plain fixed-rate loan.</p>

<label>Loan type</label>
<select id="q_loantype" onchange="toggleQualifyAdvanced()">
<option value="fixed" selected>Standard fixed-rate</option>
<option value="io">Interest-only period</option>
<option value="arm">Adjustable rate (ARM)</option>
</select>

<div id="q_io_fields" style="display:none;">
  <label>Interest-only period (years) - your qualifying payment during this time is interest only, letting the same budget support a larger loan. Many lenders still qualify you on the full amortizing payment for safety - this shows what's possible if they don't.</label>
  <input type="number" step="0.5" min="0" id="q_io_years" value="5">
</div>

<div id="q_arm_fields" style="display:none;">
  <label>Fixed-rate (teaser) period (years) - the rate above holds until this point</label><input type="number" step="0.5" min="0" id="q_arm_fixed" value="5">
  <label>Rate after fixed period (%) - the fully-indexed rate it resets to</label><input type="number" step="0.01" min="0" id="q_arm_reset" value="8">
  <label>Assumed further increase per year after that (percentage points)</label><input type="number" step="0.1" id="q_arm_increase" value="0.5">
</div>

<label><input type="checkbox" id="q_negam" style="width:auto;display:inline-block;"> Payment doesn't fully cover interest (negative amortization) - <span style="color:#c0392b;font-weight:600;">the unpaid difference gets added to your loan balance, meaning you'd owe MORE over time, not less. This is a genuinely risky structure - shown here for informational comparison, not as a recommendation.</span></label>

<label style="margin-top:10px;">Balloon due (years, optional) - 0 for none. The loan is calculated as if paid off over your loan term above, but the full remaining balance comes due at this point instead, requiring refinance or payoff.</label>
<input type="number" min="0" id="q_balloon" value="0">

<label style="margin-top:10px;"><input type="checkbox" id="q_biweekly" style="width:auto;display:inline-block;"> Pay biweekly instead of monthly (half the payment every 2 weeks = 13 monthly-equivalent payments/year instead of 12 - shows payoff time and interest saved, doesn't change what you qualify for)</label>

<label>Additional principal payment ($/month, optional) - extra amount applied directly to principal each month, on top of your regular payment</label>
<input type="number" min="0" id="q_extra_principal" value="0">

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Estimated Income Tax Savings (Itemized Deductions)</h4>
<label>Estimated annual property tax ($ - the portion of the combined figure above that is property tax, not insurance/HOA)</label><input type="number" id="q_proptax_annual" value="4800">
<label>Filing status</label>
<select id="q_filing" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="single" selected>Single</option><option value="mfj">Married Filing Jointly</option>
<option value="mfs">Married Filing Separately</option><option value="hoh">Head of Household</option>
</select>
<label>Property state</label>
<select id="q_state" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
__STATE_TAX_OPTIONS__
</select>
<label>Your federal marginal tax bracket</label>
<select id="q_fed_bracket" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="10">10%</option><option value="12">12%</option><option value="22">22%</option>
<option value="24" selected>24%</option><option value="32">32%</option><option value="35">35%</option>
<option value="37">37%</option>
</select>
<label>Other itemized deductions ($/yr - state/local income tax paid, charitable gifts, medical expenses above threshold, etc., not counting this home's mortgage interest or property tax)</label><input type="number" id="q_other_itemized" value="0">

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
<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Estimated Income Tax Savings (Itemized Deductions)</h4>
<label><input type="checkbox" id="m_pre2018" style="width:auto;display:inline-block;"> This loan originated before December 16, 2017 (grandfathered under the higher $1,000,000 acquisition debt cap, instead of $750,000)</label>
<label>Filing status</label>
<select id="m_filing" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="single" selected>Single</option><option value="mfj">Married Filing Jointly</option>
<option value="mfs">Married Filing Separately</option><option value="hoh">Head of Household</option>
</select>
<label>Property state</label>
<select id="m_state" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
__STATE_TAX_OPTIONS__
</select>
<label>Your federal marginal tax bracket</label>
<select id="m_fed_bracket" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="10">10%</option><option value="12">12%</option><option value="22">22%</option>
<option value="24" selected>24%</option><option value="32">32%</option><option value="35">35%</option>
<option value="37">37%</option>
</select>
<label>Other itemized deductions ($/yr - state/local income tax paid, charitable gifts, medical expenses above threshold, etc., not counting this home's mortgage interest or property tax)</label><input type="number" id="m_other_itemized" value="0">
<button onclick="calcMortgage()">Calculate</button>
<div class="result" id="m_result"></div>
<div class="chart-wrap"><canvas id="m_chart"></canvas></div>
<p class="chart-caption" id="m_chart_caption"></p>
<div id="m_amort" style="margin-top:14px;"></div>
</div>

<div class="calc calc-panel" id="panel-cre">
<h3>Real Estate Investment Loan Calculator (DSCR)</h3>
<div class="beginner-box learning-mode-only">
  <h3>&#127891; What This Calculator Does</h3>
  <p style="font-size:13px;line-height:1.6;margin:0 0 8px;">This estimates whether a rental property's own income can cover its loan payment - the core question behind investment property financing (as opposed to a regular home mortgage, which is qualified on your personal income instead).</p>
  <ul>
    <li><strong>DSCR</strong> tells you how many times over the rental income covers the mortgage payment. Below 1.0 means the property doesn't pay for itself as structured.</li>
    <li><strong>Cap Rate</strong> shows the return based on price alone, ignoring financing - useful for comparing properties regardless of how each one is financed.</li>
    <li><strong>Cash-on-Cash Return</strong> shows the return on the actual cash you'd put in, factoring in the loan.</li>
  </ul>
  <p style="font-size:11px;color:#888;margin:8px 0 0;">This is an educational estimate, not a preapproval or investment recommendation.</p>
</div>
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
<label>Loan start date (optional - used to show the balloon due date as an actual calendar date, and to determine where you are in an interest-only or ARM schedule)</label><input type="date" id="cre_loanstart">
<label>Interest-only period (years, optional) - no principal reduction during this time, then converts to a fully-amortizing payment</label><input type="number" step="0.5" min="0" id="cre_io" value="0">
<label><input type="checkbox" id="cre_isarm" onchange="toggleCREArmFields()" style="width:auto;display:inline-block;"> This is an ARM (Adjustable Rate Mortgage)</label>
<div id="cre_arm_fields" style="display:none;">
  <label>Fixed-rate period (years) - the rate above (the teaser rate) holds until this point</label><input type="number" step="0.5" min="0" id="cre_armfixed" value="0">
  <label>Rate after fixed period (%) - the fully-indexed rate it resets to once the fixed period ends</label><input type="number" step="0.01" min="0" id="cre_armreset" value="0">
  <label>Assumed further increase per year after that (percentage points)</label><input type="number" step="0.1" id="cre_armincrease" value="0">
</div>
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
<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Estimated Income Tax Savings</h4>
<label>Property state (used to estimate state income tax savings, below)</label>
<select id="cre_state" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
__STATE_TAX_OPTIONS__
</select>
<label>Your federal marginal tax bracket</label>
<select id="cre_fed_bracket" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="10">10%</option><option value="12">12%</option><option value="22">22%</option>
<option value="24" selected>24%</option><option value="32">32%</option><option value="35">35%</option>
<option value="37">37%</option>
</select>
<label>Building value (% of purchase price - land isn't depreciable; ~70-80% building is a common rule of thumb, editable based on your appraisal/tax assessor split)</label><input type="number" id="cre_bldg_pct" value="80" step="1" min="0" max="100">
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

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Business-Use Tax Deduction (optional)</h4>
<p class="chart-caption" style="text-align:left;margin:0 0 10px;">If this vehicle is leased for business use (client visits, deliveries, etc.), lease costs can be deducted as an ordinary business expense - not a personal itemized deduction, so no standard-deduction comparison or SALT cap applies. Pick one method; the IRS requires using the same method for the life of the lease.</p>
<label>Business-use percentage of total miles driven (%)</label><input type="number" id="ls_business_pct" value="0" step="1" min="0" max="100">
<label>Deduction method</label>
<select id="ls_method" onchange="toggleLeaseMethodFields()" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="mileage" selected>Standard mileage rate</option>
<option value="actual">Actual expense method (lease payment x business-use %)</option>
</select>
<div id="ls_mileage_fields">
<label>Total annual miles driven (business + personal)</label><input type="number" id="ls_total_miles" value="12000">
<label>IRS standard mileage rate ($/mile - 2025 rate was $0.70; 2026 is $0.725 through June, $0.76 from July 1 onward, editable)</label><input type="number" id="ls_mileage_rate" value="0.76" step="0.005">
</div>
<label>Your federal marginal tax bracket</label>
<select id="ls_fed_bracket" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="10">10%</option><option value="12">12%</option><option value="22">22%</option>
<option value="24" selected>24%</option><option value="32">32%</option><option value="35">35%</option>
<option value="37">37%</option>
</select>
<label>Property state (for state income tax rate)</label>
<select id="ls_state" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
__STATE_TAX_OPTIONS__
</select>

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

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Estimated Income Tax Savings (Qualified Second Home)</h4>
<p class="chart-caption" style="text-align:left;margin:0 0 10px;">A boat can be treated as a "second home" for mortgage interest deduction purposes only if it has sleeping, cooking, and toilet facilities, AND the loan is secured by the boat itself. Both must be true, or none of this interest is deductible.</p>
<label><input type="checkbox" id="bt_hasfacilities" style="width:auto;display:inline-block;"> This boat has sleeping, cooking, and toilet facilities</label>
<label><input type="checkbox" id="bt_loansecured" style="width:auto;display:inline-block;"> The loan is secured by the boat (not an unsecured personal loan)</label>
<label><input type="checkbox" id="bt_pre2018" style="width:auto;display:inline-block;"> This loan originated before December 16, 2017 (grandfathered under the higher $1,000,000 acquisition debt cap, instead of $750,000)</label>
<label>Annual personal property tax on the boat ($ - some states assess this; 0 if yours doesn't)</label><input type="number" id="bt_proptax" value="0">
<label>Filing status</label>
<select id="bt_filing" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="single" selected>Single</option><option value="mfj">Married Filing Jointly</option>
<option value="mfs">Married Filing Separately</option><option value="hoh">Head of Household</option>
</select>
<label>Property state</label>
<select id="bt_state" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
__STATE_TAX_OPTIONS__
</select>
<label>Your federal marginal tax bracket</label>
<select id="bt_fed_bracket" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="10">10%</option><option value="12">12%</option><option value="22">22%</option>
<option value="24" selected>24%</option><option value="32">32%</option><option value="35">35%</option>
<option value="37">37%</option>
</select>
<label>Other itemized deductions ($/yr - state/local income tax paid, charitable gifts, medical expenses above threshold, primary home mortgage interest/property tax, etc.)</label><input type="number" id="bt_other_itemized" value="0">

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

<h4 style="margin:16px 0 4px;font-size:13px;color:#666;">Estimated Income Tax Savings (Qualified Second Home)</h4>
<p class="chart-caption" style="text-align:left;margin:0 0 10px;">An RV can be treated as a "second home" for mortgage interest deduction purposes only if it has sleeping, cooking, and toilet facilities, AND the loan is secured by the RV itself. Both must be true, or none of this interest is deductible.</p>
<label><input type="checkbox" id="rv_hasfacilities" style="width:auto;display:inline-block;"> This RV has sleeping, cooking, and toilet facilities</label>
<label><input type="checkbox" id="rv_loansecured" style="width:auto;display:inline-block;"> The loan is secured by the RV (not an unsecured personal loan)</label>
<label><input type="checkbox" id="rv_pre2018" style="width:auto;display:inline-block;"> This loan originated before December 16, 2017 (grandfathered under the higher $1,000,000 acquisition debt cap, instead of $750,000)</label>
<label>Annual personal property tax on the RV ($ - some states assess this; 0 if yours doesn't)</label><input type="number" id="rv_proptax" value="0">
<label>Filing status</label>
<select id="rv_filing" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="single" selected>Single</option><option value="mfj">Married Filing Jointly</option>
<option value="mfs">Married Filing Separately</option><option value="hoh">Head of Household</option>
</select>
<label>Property state</label>
<select id="rv_state" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
__STATE_TAX_OPTIONS__
</select>
<label>Your federal marginal tax bracket</label>
<select id="rv_fed_bracket" style="width:100%;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
<option value="10">10%</option><option value="12">12%</option><option value="22">22%</option>
<option value="24" selected>24%</option><option value="32">32%</option><option value="35">35%</option>
<option value="37">37%</option>
</select>
<label>Other itemized deductions ($/yr - state/local income tax paid, charitable gifts, medical expenses above threshold, primary home mortgage interest/property tax, etc.)</label><input type="number" id="rv_other_itemized" value="0">

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
function toggleCREArmFields() {
  document.getElementById("cre_arm_fields").style.display = document.getElementById("cre_isarm").checked ? "block" : "none";
}

// Same tested month-by-month amortization simulator used in Property Manager - handles an
// interest-only period, an ARM's rate adjustments (teaser rate holds through the fixed period,
// then jumps once to the reset rate, then optionally keeps climbing), and balance tracking
// together, since none of this has a single closed-form formula once the rate itself changes.
function simulateLoanAmortization(loanAmount, initialRatePct, amortTermYears, interestOnlyYears, isARM, armFixedYears, armResetRate, armRateIncreasePerYear, numYears) {
  var balance = loanAmount;
  var ioMonths = Math.round((interestOnlyYears || 0) * 12);
  var armFixedMonths = isARM ? Math.round((armFixedYears || 0) * 12) : Infinity;
  var totalTermMonths = amortTermYears * 12;
  var currentRate = initialRatePct;
  var monthlyPayment = null;
  var yearResults = [];
  var yearDebtServiceSum = 0;

  for (var month = 0; month < numYears * 12; month++) {
    var newRate;
    if (!isARM || month < armFixedMonths) {
      newRate = initialRatePct;
    } else {
      var yearsPastReset = Math.floor((month - armFixedMonths) / 12);
      newRate = (armResetRate || 0) + yearsPastReset * (armRateIncreasePerYear || 0);
    }
    var rateChanged = newRate !== currentRate;
    currentRate = newRate;
    var monthlyRate = currentRate / 100 / 12;

    var thisMonthPayment;
    if (month < ioMonths) {
      thisMonthPayment = balance * monthlyRate;
    } else {
      var remainingMonths = totalTermMonths - month;
      if (remainingMonths <= 0) {
        thisMonthPayment = 0;
      } else if (monthlyPayment === null || rateChanged || month === ioMonths) {
        thisMonthPayment = calculateMonthlyPI(balance, currentRate, remainingMonths / 12);
      } else {
        thisMonthPayment = monthlyPayment;
      }
      var interestPortion = balance * monthlyRate;
      var principalPortion = thisMonthPayment - interestPortion;
      balance = Math.max(0, balance - principalPortion);
    }
    monthlyPayment = thisMonthPayment;
    yearDebtServiceSum += thisMonthPayment;

    if ((month + 1) % 12 === 0) {
      yearResults.push({ debtService: yearDebtServiceSum, endingBalance: balance, rate: currentRate, monthlyPayment: thisMonthPayment });
      yearDebtServiceSum = 0;
    }
  }
  return yearResults;
}

function calculateMonthlyPI(loanAmount, annualRatePct, termYears) {
  if (!loanAmount || loanAmount <= 0 || !termYears || termYears <= 0) return 0;
  var n = termYears * 12;
  if (!annualRatePct) return loanAmount / n;
  var r = (annualRatePct / 100) / 12;
  return loanAmount * (r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
}

__STATE_TAX_JS_HELPER__
function calcCRE() {
  var propType = document.getElementById("cre_type").value;
  var totalUnits = +document.getElementById("cre_total_units_hidden").value || 0;
  var price = +document.getElementById("cre_price").value;
  var downPct = (+document.getElementById("cre_down_pct").value || 0) / 100;
  var ratePct = +document.getElementById("cre_rate").value || 0;
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
  var loanStartDate = document.getElementById("cre_loanstart").value || "";
  var ioYears = +document.getElementById("cre_io").value || 0;
  var isARM = document.getElementById("cre_isarm").checked;
  var armFixedYears = +document.getElementById("cre_armfixed").value || 0;
  var armResetRate = +document.getElementById("cre_armreset").value || 0;
  var armIncrease = +document.getElementById("cre_armincrease").value || 0;

  var down = price * downPct;
  var loan = price - down;
  var closing_amt = price * closingPct;
  var cash_to_close = down + closing_amt;

  if (loan <= 0 || n <= 0 || rent_m <= 0) { show("cre_result", "Check your inputs - purchase price, amortization, and rental income must all be greater than zero."); return; }

  // Months elapsed since loan start (0 if no date given, e.g. evaluating a brand-new deal)
  var monthsElapsed = 0;
  if (loanStartDate) {
    var startYear = parseInt(loanStartDate.slice(0, 4), 10);
    var startMonthIdx = parseInt(loanStartDate.slice(5, 7), 10) - 1;
    var today = new Date();
    var startLinear = startYear * 12 + startMonthIdx;
    var nowLinear = today.getFullYear() * 12 + today.getMonth();
    monthsElapsed = Math.max(0, nowLinear - startLinear);
  }

  // Simulate far enough to cover both today's position and the balloon term (or full amortization)
  var yearsToSimulate = Math.max(Math.ceil(monthsElapsed / 12) + 1, termYears || amortYears, 1);
  var simYears = simulateLoanAmortization(loan, ratePct, amortYears, ioYears, isARM, armFixedYears, armResetRate, armIncrease, yearsToSimulate);
  var currentYearIndex = Math.floor(monthsElapsed / 12);
  var currentYear = simYears[Math.min(currentYearIndex, simYears.length - 1)] || { monthlyPayment: 0 };
  var pmt = currentYear.monthlyPayment;
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
    var balloonYear = simYears[Math.min(termYears - 1, simYears.length - 1)];
    var bal = balloonYear ? balloonYear.endingBalance : loan;
    var dueLabel = "year " + termYears;
    if (loanStartDate) {
      var startY = parseInt(loanStartDate.slice(0, 4), 10);
      var startM = parseInt(loanStartDate.slice(5, 7), 10) - 1;
      var dueLinear = startY * 12 + startM + termYears * 12;
      var dueYear = Math.floor(dueLinear / 12);
      var dueMonth = (dueLinear % 12) + 1;
      dueLabel = dueMonth + "/" + dueYear;
    }
    balloonNote = "<span style='color:#c0392b;font-weight:600;'>Balloon payment due " + dueLabel + ": " + money(Math.max(bal, 0)) + "</span><br>";
  }

  var dscrColor = dscr >= 1.25 ? "#1a8a3d" : (dscr >= 1.0 ? "#a5720b" : "#c0392b");
  var dscrNote = dscr >= 1.25 ? "Comfortably meets most lenders' minimum (typically 1.20-1.25+)." :
                 dscr >= 1.0 ? "Covers the debt payment, but below many lenders' comfort threshold (1.20-1.25+) - a bigger down payment, lower rate, or higher rent may be needed to qualify." :
                 "Below 1.0 means the property's income does not cover the debt payment as structured - most commercial lenders will not approve this loan without changes.";

  // --- Estimated income tax savings (depreciation + mortgage interest + property tax) ---
  var bldgPct = (+document.getElementById("cre_bldg_pct").value || 0) / 100;
  var fedRatePct = +document.getElementById("cre_fed_bracket").value || 0;
  var stateAbbr = document.getElementById("cre_state").value;
  var stateRatePct = getStateTopMarginalRate(stateAbbr) || 0;
  var depreciationLife = propType === "comm5" ? 39 : 27.5;
  var buildingValue = price * bldgPct;
  var annualDepreciation = buildingValue / depreciationLife;

  var startingBalance = currentYearIndex === 0 ? loan : ((simYears[currentYearIndex - 1] || {}).endingBalance != null ? simYears[currentYearIndex - 1].endingBalance : loan);
  var principalReduction = startingBalance - currentYear.endingBalance;
  var annualInterest = Math.max(0, annualDebtService - principalReduction);
  var annualPropertyTaxDeduction = tax_m * 12;

  var totalTaxDeductions = annualDepreciation + annualInterest + annualPropertyTaxDeduction;
  var combinedRatePct = fedRatePct + stateRatePct;
  var estTaxSavings = totalTaxDeductions * (combinedRatePct / 100);

  var taxSavingsHtml =
    "<br><u>Estimated Annual Income Tax Savings</u><br>" +
    "&nbsp;&nbsp;Depreciation (" + depreciationLife + "-yr, " + (bldgPct*100).toFixed(0) + "% building value of " + money(price) + "): " + money(annualDepreciation) + "/yr<br>" +
    "&nbsp;&nbsp;Mortgage interest (year " + (currentYearIndex + 1) + " of the loan): " + money(annualInterest) + "/yr<br>" +
    "&nbsp;&nbsp;Property taxes: " + money(annualPropertyTaxDeduction) + "/yr<br>" +
    "&nbsp;&nbsp;Total deductions: <strong>" + money(totalTaxDeductions) + "/yr</strong><br>" +
    "&nbsp;&nbsp;Combined marginal rate (federal " + fedRatePct + "% + state " + stateRatePct.toFixed(2) + "%): " + combinedRatePct.toFixed(2) + "%<br>" +
    "Estimated tax savings: <strong style='color:#1a8a3d;'>" + money(estTaxSavings) + "/yr</strong> (" + money(estTaxSavings/12) + "/mo)<br>" +
    "<span style='font-size:11px;color:#888;'>Estimate only, not tax advice. Assumes these losses are fully deductible against ordinary income - the IRS passive activity loss rules (Section 469) can limit or defer this for investors who aren't real estate professionals and don't actively manage the property, unless the loss qualifies for the $25,000 active-participation allowance (phased out between $100,000-$150,000 MAGI). Depreciation reduces your cost basis and is generally recaptured (taxed up to 25% federal) when you sell. State rate shown is each state's top marginal individual rate, not an income-specific calculation, and excludes local/county taxes. Consult a CPA before relying on this for a purchase decision.</span>";

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
    "Underwriting conventions vary by lender, property type, and market - treat these as estimates, not a preapproval.</span>" +
    taxSavingsHtml);

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
function toggleQualifyAdvanced() {
  var type = document.getElementById("q_loantype").value;
  document.getElementById("q_io_fields").style.display = type === "io" ? "block" : "none";
  document.getElementById("q_arm_fields").style.display = type === "arm" ? "block" : "none";
}

// Extended version of the tested Property Manager/CRE simulator, adding biweekly payments
// (approximated as an extra 1/12 payment's worth of principal each month, once amortizing -
// a standard, widely-used approximation for biweekly acceleration) and a fixed extra principal
// amount. Runs month-by-month up to a hard cap (50 years) so a loan structure that genuinely
// never pays off (e.g. negative amortization with no offsetting extra payment) can't loop forever.
function simulateLoanWithExtras(loanAmount, initialRatePct, amortTermYears, interestOnlyYears, isARM, armFixedYears, armResetRate, armRateIncreasePerYear, isNegativeAmortization, isBiweekly, extraPrincipal) {
  var balance = loanAmount;
  var ioMonths = Math.round((interestOnlyYears || 0) * 12);
  var armFixedMonths = isARM ? Math.round((armFixedYears || 0) * 12) : Infinity;
  var totalTermMonths = amortTermYears * 12;
  var currentRate = initialRatePct;
  var monthlyPayment = null;
  var negAmActive = isARM && isNegativeAmortization && (armResetRate || 0) > 0;
  var totalInterestPaid = 0;
  var month = 0;
  var maxMonths = 50 * 12;
  var firstMonthPayment = null;

  while (month < maxMonths && balance > 0.01) {
    var inTeaserPeriod = isARM && month < armFixedMonths;
    var newRate;
    if (!isARM || month < armFixedMonths) {
      newRate = initialRatePct;
    } else {
      var yearsPastReset = Math.floor((month - armFixedMonths) / 12);
      newRate = (armResetRate || 0) + yearsPastReset * (armRateIncreasePerYear || 0);
    }
    var rateChanged = newRate !== currentRate;
    currentRate = newRate;
    var monthlyRate = currentRate / 100 / 12;
    var accrualRate = (negAmActive && inTeaserPeriod) ? armResetRate : currentRate;
    var accrualMonthlyRate = accrualRate / 100 / 12;

    var thisMonthPayment;
    if (month < ioMonths) {
      thisMonthPayment = balance * monthlyRate;
    } else {
      var remainingMonths = totalTermMonths - month;
      if (remainingMonths <= 0) {
        thisMonthPayment = 0;
      } else if (monthlyPayment === null || rateChanged || month === ioMonths) {
        thisMonthPayment = calculateMonthlyPI(balance, currentRate, remainingMonths / 12);
      } else {
        thisMonthPayment = monthlyPayment;
      }
    }
    monthlyPayment = thisMonthPayment;
    if (firstMonthPayment === null) firstMonthPayment = thisMonthPayment;

    var interestAccrued = balance * accrualMonthlyRate;
    var principalPortion = thisMonthPayment - interestAccrued;

    var acceleration = 0;
    if (isBiweekly && month >= ioMonths) acceleration += thisMonthPayment / 12;
    acceleration += (extraPrincipal || 0);
    principalPortion += acceleration;

    totalInterestPaid += interestAccrued;
    balance = Math.max(0, balance - principalPortion);
    month++;
  }

  return {
    monthsToPayoff: month,
    payoffReached: balance <= 0.01,
    totalInterestPaid: totalInterestPaid,
    firstMonthPayment: firstMonthPayment,
    finalBalance: balance
  };
}

__PERSONAL_ITEMIZE_JS_HELPER__
function calcQualify() {
  var gm = ((+document.getElementById("q_inc1").value || 0) + (+document.getElementById("q_inc2").value || 0)) / 12;
  var debts = (+document.getElementById("q_debts").value || 0);
  var down = (+document.getElementById("q_down").value || 0);
  var ratePct = (+document.getElementById("q_rate").value || 0);
  var rate = ratePct / 100 / 12;
  var years = (+document.getElementById("q_years").value || 30);
  var n = years * 12;
  var tih = (+document.getElementById("q_tih").value || 0);
  var maint = (+document.getElementById("q_maint").value || 0);
  var loanType = document.getElementById("q_loantype").value;
  var ioYears = +document.getElementById("q_io_years").value || 0;
  var armFixedYears = +document.getElementById("q_arm_fixed").value || 0;
  var armResetRate = +document.getElementById("q_arm_reset").value || 0;
  var armIncrease = +document.getElementById("q_arm_increase").value || 0;
  var isNegAm = document.getElementById("q_negam").checked;
  var balloonYears = +document.getElementById("q_balloon").value || 0;
  var isBiweekly = document.getElementById("q_biweekly").checked;
  var extraPrincipal = +document.getElementById("q_extra_principal").value || 0;
  if (gm <= 0) { show("q_result", "Enter your income."); return; }

  // The rate used to reverse-calculate the loan from the qualifying P&I payment - for IO/ARM,
  // this is the teaser rate entered above (since that's what the initial payment is based on);
  // for a plain fixed loan, it's simply the loan's rate.
  var qualifyRate = ratePct;
  var qualifyRateDecimal = qualifyRate / 100 / 12;

  function scenario(front_pct, back_pct) {
    var housing = Math.min(gm * front_pct, gm * back_pct - debts);
    var pi = housing - tih - maint;
    if (pi <= 0) return null;
    var loan;
    if (loanType === "io") {
      loan = qualifyRateDecimal > 0 ? pi / qualifyRateDecimal : pi * n;
    } else {
      loan = qualifyRateDecimal > 0 ? pi * (1 - Math.pow(1 + qualifyRateDecimal, -n)) / qualifyRateDecimal : pi * n;
    }
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

  // Use the more generous (aggressive) scenario for the advanced-structure illustrations below,
  // since that's the one most likely to actually use them
  var illustrative = aggr || cons;
  if (illustrative && (loanType === "io" || loanType === "arm")) {
    var sim = simulateLoanWithExtras(illustrative.loan, ratePct, years, loanType === "io" ? ioYears : 0,
      loanType === "arm", loanType === "arm" ? armFixedYears : 0, loanType === "arm" ? armResetRate : 0,
      loanType === "arm" ? armIncrease : 0, isNegAm, false, 0);
    html += "<span style='color:#a5720b;font-weight:600;'>Payment change ahead:</span> the payment above is only your ";
    html += (loanType === "io" ? "interest-only" : "initial teaser-rate") + " payment on the upper-limit loan of " + money(illustrative.loan) + ". ";
    if (isNegAm && loanType === "arm") {
      html += "Because this is modeled with negative amortization, your balance would actually <strong style='color:#c0392b;'>grow</strong> during the initial period rather than shrink" +
        (sim.payoffReached ? "" : " - and at this rate, it would not fully pay off within 50 years") + ". ";
    }
    html += "Once " + (loanType === "io" ? "the interest-only period ends" : "the rate resets") + ", expect the payment to rise significantly - budget for that before committing to this structure.<br><br>";
  }

  if (illustrative && balloonYears > 0 && balloonYears * 12 < n) {
    var balloonSim = simulateLoanWithExtras(illustrative.loan, ratePct, years, loanType === "io" ? ioYears : 0,
      loanType === "arm", loanType === "arm" ? armFixedYears : 0, loanType === "arm" ? armResetRate : 0,
      loanType === "arm" ? armIncrease : 0, isNegAm, false, 0);
    // Re-simulate but stop exactly at the balloon year to read the balance at that point
    var balloonMonths = balloonYears * 12;
    var bal = illustrative.loan, curRate = ratePct, pmt = null;
    var ioM = Math.round((loanType === "io" ? ioYears : 0) * 12);
    var armFixedM = loanType === "arm" ? Math.round(armFixedYears * 12) : Infinity;
    for (var m = 0; m < balloonMonths; m++) {
      var nr = (!(loanType === "arm") || m < armFixedM) ? ratePct : armResetRate + Math.floor((m - armFixedM) / 12) * armIncrease;
      curRate = nr;
      var mr = curRate / 100 / 12;
      if (m < ioM) { pmt = bal * mr; }
      else {
        var remM = n - m;
        if (pmt === null || m === ioM) pmt = calculateMonthlyPI(bal, curRate, remM / 12);
        var ip = bal * mr;
        bal = Math.max(0, bal - (pmt - ip));
      }
    }
    html += "<span style='color:#c0392b;font-weight:600;'>Balloon due at year " + balloonYears + ":</span> " + money(bal) + " remaining principal on the upper-limit loan - you'd need to refinance or pay this off in full at that point.<br><br>";
  }

  if (illustrative && (isBiweekly || extraPrincipal > 0)) {
    var baseline = simulateLoanWithExtras(illustrative.loan, ratePct, years, 0, false, 0, 0, 0, false, false, 0);
    var accelerated = simulateLoanWithExtras(illustrative.loan, ratePct, years, 0, false, 0, 0, 0, false, isBiweekly, extraPrincipal);
    var yearsSaved = (baseline.monthsToPayoff - accelerated.monthsToPayoff) / 12;
    var interestSaved = baseline.totalInterestPaid - accelerated.totalInterestPaid;
    html += "<u>Paying " + (isBiweekly ? "biweekly" : "") + (isBiweekly && extraPrincipal > 0 ? " + " : "") +
      (extraPrincipal > 0 ? money(extraPrincipal) + "/mo extra principal" : "") + "</u><br>" +
      "Payoff in " + (accelerated.monthsToPayoff / 12).toFixed(1) + " years instead of " + (baseline.monthsToPayoff / 12).toFixed(1) +
      " - about " + yearsSaved.toFixed(1) + " years sooner<br>" +
      "Interest saved: <strong>" + money(interestSaved) + "</strong> over the life of the loan<br><br>";
  }

  html += "<span style='font-size:11px;color:#888;'>This is an estimate, not a preapproval. Lenders' 28/36 and 31/43 ratios do not actually count maintenance, but it is a real monthly cost - this calculator sets it aside first so the price you see is one you can genuinely afford to live in, not just qualify for. Lenders also weigh credit score, employment history, and cash reserves, and most qualify IO/ARM borrowers on the fully-amortizing or fully-indexed payment rather than the teaser payment shown here, specifically to guard against payment shock. The first number uses the classic 28/36 rule: housing under 28% of gross income, all debts under 36%.</span>";

  if (illustrative) {
    var annualPropertyTaxQ = +document.getElementById("q_proptax_annual").value || 0;
    var filingQ = document.getElementById("q_filing").value;
    var stateRatePctQ = getStateTopMarginalRate(document.getElementById("q_state").value) || 0;
    var fedRatePctQ = +document.getElementById("q_fed_bracket").value || 0;
    var otherItemizedQ = +document.getElementById("q_other_itemized").value || 0;
    var annualInterestQ = estimateFirstYearInterest(illustrative.loan, ratePct, years);
    var resultQ = computeItemizedTaxSavings({
      loanAmount: illustrative.loan, isPre2018Loan: false, annualInterest: annualInterestQ,
      annualPropertyTax: annualPropertyTaxQ, otherItemized: otherItemizedQ, filingStatus: filingQ,
      fedRatePct: fedRatePctQ, stateRatePct: stateRatePctQ
    });
    html += itemizeSavingsHtml(resultQ, { otherItemized: otherItemizedQ });
  }

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
  var ratePctM = +document.getElementById("m_rate").value || 0;
  var yearsM = +document.getElementById("m_years").value || 0;
  var annualInterestM = estimateFirstYearInterest(loan, ratePctM, yearsM);
  var isPre2018M = document.getElementById("m_pre2018").checked;
  var filingM = document.getElementById("m_filing").value;
  var stateRatePctM = getStateTopMarginalRate(document.getElementById("m_state").value) || 0;
  var fedRatePctM = +document.getElementById("m_fed_bracket").value || 0;
  var otherItemizedM = +document.getElementById("m_other_itemized").value || 0;
  var resultM = computeItemizedTaxSavings({
    loanAmount: loan, isPre2018Loan: isPre2018M, annualInterest: annualInterestM,
    annualPropertyTax: tax_m * 12, otherItemized: otherItemizedM, filingStatus: filingM,
    fedRatePct: fedRatePctM, stateRatePct: stateRatePctM
  });
  var taxSavingsHtmlM = itemizeSavingsHtml(resultM, { otherItemized: otherItemizedM });

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
    "<span style='font-size:11px;color:#888;'>Taxes, insurance, and HOA are estimates and usually rise over time. PMI (required below 20% down) is extra. With an interest-only second mortgage, the monthly payment never reduces its principal - the full amount remains due at payoff, sale, or refinance. Buyer-agent commission is negotiable and cannot usually be rolled into the loan - though sellers often agree to cover it, so ask. Every dollar paid in commission is a dollar unavailable for your down payment.</span>" +
    taxSavingsHtmlM);

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
function toggleLeaseMethodFields() {
  var method = document.getElementById("ls_method").value;
  document.getElementById("ls_mileage_fields").style.display = method === "mileage" ? "block" : "none";
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

  var businessPct = (+document.getElementById("ls_business_pct").value || 0) / 100;
  var businessHtml = "";
  if (businessPct > 0) {
    var method = document.getElementById("ls_method").value;
    var fedRatePctLs = +document.getElementById("ls_fed_bracket").value || 0;
    var stateRatePctLs = getStateTopMarginalRate(document.getElementById("ls_state").value) || 0;
    var combinedRateLs = fedRatePctLs + stateRatePctLs;
    var annualDeduction = 0;
    var methodNote = "";
    if (method === "mileage") {
      var totalMiles = +document.getElementById("ls_total_miles").value || 0;
      var mileageRate = +document.getElementById("ls_mileage_rate").value || 0;
      var businessMiles = totalMiles * businessPct;
      annualDeduction = businessMiles * mileageRate;
      methodNote = "&nbsp;&nbsp;Business miles (" + (businessPct*100).toFixed(0) + "% of " + totalMiles.toLocaleString() + " total miles): " + Math.round(businessMiles).toLocaleString() + " mi &times; " + money(mileageRate) + "/mi = " + money(annualDeduction) + "/yr<br>";
    } else {
      var annualLeaseAndDriving = (totalPayment + fuel_m + maint_m) * 12;
      annualDeduction = annualLeaseAndDriving * businessPct;
      methodNote = "&nbsp;&nbsp;Annual lease payment + fuel + maintenance (" + money(annualLeaseAndDriving) + ") &times; " + (businessPct*100).toFixed(0) + "% business use = " + money(annualDeduction) + "/yr<br>" +
        "<span style='font-size:11px;color:#888;'>Actual expense method: if this is a 'luxury' lease above IRS fair-market-value thresholds, a lease inclusion amount slightly reduces this deduction - not modeled here.</span><br>";
    }
    var businessTaxSavings = annualDeduction * (combinedRateLs / 100);
    businessHtml = "<br><u>Estimated Business-Use Tax Deduction</u><br>" +
      methodNote +
      "Estimated annual deduction: <strong>" + money(annualDeduction) + "</strong><br>" +
      "Combined marginal rate (federal " + fedRatePctLs + "% + state " + stateRatePctLs.toFixed(2) + "%): " + combinedRateLs.toFixed(2) + "%<br>" +
      "Estimated tax savings: <strong style='color:#1a8a3d;'>" + money(businessTaxSavings) + "/yr</strong> (" + money(businessTaxSavings/12) + "/mo)<br>" +
      "<span style='font-size:11px;color:#888;'>Estimate only, not tax advice. This is an ordinary business expense deduction (Schedule C or pass-through via K-1), not a personal itemized deduction - no standard-deduction comparison or SALT cap applies. You must use the same method (standard mileage or actual expense) for the entire lease term. Keep a mileage log or expense records to substantiate business use. Consult a CPA before relying on this for a decision.</span>";
  }

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
    "<span style='font-size:11px;color:#888;'>This is a standard lease payment estimate (depreciation + rent charge + tax), the same formula lenders use. Actual dealer quotes can vary based on lender-specific fees, regional taxes taxed on the full cap cost instead of the payment, and manufacturer-subsidized (subvented) money factors or residuals that beat the market rate. Always get the money factor and residual in writing before signing - a low advertised payment can hide a high money factor offset by a large down payment.</span>" +
    businessHtml);

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

  var hasFacilitiesBt = document.getElementById("bt_hasfacilities").checked;
  var loanSecuredBt = document.getElementById("bt_loansecured").checked;
  var taxSavingsHtmlBt = "";
  if (hasFacilitiesBt && loanSecuredBt) {
    var ratePctBt = +document.getElementById("bt_rate").value || 0;
    var yearsBt = +document.getElementById("bt_years").value || 0;
    var annualInterestBt = estimateFirstYearInterest(loan, ratePctBt, yearsBt);
    var annualPropertyTaxBt = +document.getElementById("bt_proptax").value || 0;
    var isPre2018Bt = document.getElementById("bt_pre2018").checked;
    var filingBt = document.getElementById("bt_filing").value;
    var stateRatePctBt = getStateTopMarginalRate(document.getElementById("bt_state").value) || 0;
    var fedRatePctBt = +document.getElementById("bt_fed_bracket").value || 0;
    var otherItemizedBt = +document.getElementById("bt_other_itemized").value || 0;
    var resultBt = computeItemizedTaxSavings({
      loanAmount: loan, isPre2018Loan: isPre2018Bt, annualInterest: annualInterestBt,
      annualPropertyTax: annualPropertyTaxBt, otherItemized: otherItemizedBt, filingStatus: filingBt,
      fedRatePct: fedRatePctBt, stateRatePct: stateRatePctBt
    });
    taxSavingsHtmlBt = itemizeSavingsHtml(resultBt, { otherItemized: otherItemizedBt });
  } else {
    taxSavingsHtmlBt = "<br><span style='font-size:11px;color:#a5720b;'>No tax savings shown: to deduct boat loan interest as a qualified second home, the boat needs sleeping, cooking, and toilet facilities AND the loan must be secured by the boat. Check both boxes above if they apply.</span>";
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
    "<br><br><span style='font-size:11px;color:#888;'>Industry rule of thumb: total boating costs commonly run 2-3x the loan payment alone once dockage, insurance, maintenance, and fuel are added - this is normal, not a sign something's wrong with your numbers. The 10% maintenance rule and 1-2% insurance rule are broad averages; actual costs vary a lot by boat age, engine type, and how hard the boat is used. This is an estimate, not a substitute for actual quotes from your marina, insurer, and mechanic.</span>" +
    taxSavingsHtmlBt);

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

  var hasFacilitiesRv = document.getElementById("rv_hasfacilities").checked;
  var loanSecuredRv = document.getElementById("rv_loansecured").checked;
  var taxSavingsHtmlRv = "";
  if (hasFacilitiesRv && loanSecuredRv) {
    var ratePctRv = +document.getElementById("rv_rate").value || 0;
    var yearsRv = +document.getElementById("rv_years").value || 0;
    var annualInterestRv = estimateFirstYearInterest(loan, ratePctRv, yearsRv);
    var annualPropertyTaxRv = +document.getElementById("rv_proptax").value || 0;
    var isPre2018Rv = document.getElementById("rv_pre2018").checked;
    var filingRv = document.getElementById("rv_filing").value;
    var stateRatePctRv = getStateTopMarginalRate(document.getElementById("rv_state").value) || 0;
    var fedRatePctRv = +document.getElementById("rv_fed_bracket").value || 0;
    var otherItemizedRv = +document.getElementById("rv_other_itemized").value || 0;
    var resultRv = computeItemizedTaxSavings({
      loanAmount: loan, isPre2018Loan: isPre2018Rv, annualInterest: annualInterestRv,
      annualPropertyTax: annualPropertyTaxRv, otherItemized: otherItemizedRv, filingStatus: filingRv,
      fedRatePct: fedRatePctRv, stateRatePct: stateRatePctRv
    });
    taxSavingsHtmlRv = itemizeSavingsHtml(resultRv, { otherItemized: otherItemizedRv });
  } else {
    taxSavingsHtmlRv = "<br><span style='font-size:11px;color:#a5720b;'>No tax savings shown: to deduct RV loan interest as a qualified second home, the RV needs sleeping, cooking, and toilet facilities AND the loan must be secured by the RV. Check both boxes above if they apply.</span>";
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
    "<br><br><span style='font-size:11px;color:#888;'>New RVs commonly lose 20-30% of value in the first year alone, more than most cars or boats - this calculator uses a blended annual rate rather than that steeper first-year hit, so treat year one as likely worse than shown. Insurance, maintenance, and depreciation percentages are broad industry averages and vary a lot by specific make, model, age, and condition. This is an estimate, not a substitute for actual quotes from your dealer, insurer, and RV service center.</span>" +
    taxSavingsHtmlRv);

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

__FOOTER__
</body>
</html>"""

calculators_html = (CALC_TEMPLATE
                    .replace("__CSS__", PAGE_CSS)
                    .replace("__NAV__", NAV_HTML)
                    .replace("__DARKMODE_CSS__", DARK_MODE_CSS)
                    .replace("__DARKMODE_BUTTON__", DARK_MODE_BUTTON)
                    .replace("__DARKMODE_JS__", DARK_MODE_JS)
                    .replace("__LEARNINGMODE_CSS__", LEARNING_MODE_CSS)
                    .replace("__LEARNINGMODE_BUTTON__", LEARNING_MODE_BUTTON)
                    .replace("__LEARNINGMODE_JS__", LEARNING_MODE_JS)
                    .replace("__FOOTER__", FOOTER_HTML)
                    .replace("__STATE_TAX_JS_HELPER__", STATE_TAX_JS_HELPER)
                    .replace("__STATE_TAX_OPTIONS__", STATE_TAX_OPTIONS_HTML)
                    .replace("__PERSONAL_ITEMIZE_JS_HELPER__", PERSONAL_ITEMIZE_JS_HELPER))

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
#comp-hover-panel {
  position: fixed; display: none; z-index: 2000; width: 300px;
  background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.3); padding: 10px; pointer-events: none;
}
#comp-hover-panel iframe { width: 100%; height: 170px; border: 0; border-radius: 6px; display: block; }
#comp-hover-panel .comp-info { font-size: 12px; margin-top: 8px; line-height: 1.6; color: var(--text); }
tr[data-comp-hover]:hover { background: rgba(31,78,121,0.08); cursor: pointer; }
@media (max-width: 600px) {
  body { padding:12px; }
  .calc { padding:14px; max-width:100%; }
  .calc input, .calc select { font-size:16px !important; padding:10px !important; }
  .calc button { width:100%; }
  .calc-tab-btn { flex:1 1 auto; text-align:center; font-size:12px; padding:10px 8px; }
}
__DARKMODE_CSS__
__LEARNINGMODE_CSS__
</style>
</head>
<body>
__DARKMODE_BUTTON__<script>__DARKMODE_JS__</script>
__LEARNINGMODE_BUTTON__<script>__LEARNINGMODE_JS__</script>
__NAV__
<h1>Property &amp; Foreclosure Search</h1>
<p class="timestamp">Live lookups powered by ATTOM Data, via a Cloudflare Worker proxy.</p>

<div class="setup-banner" id="setup-banner">
  <strong>One-time setup:</strong> replace <code>WORKER_URL</code> near the top of this page's script with your own deployed Cloudflare Worker URL (looks like <code>https://attom-proxy.YOUR-SUBDOMAIN.workers.dev</code>) before this will return real results.
</div>

<div id="comp-hover-panel"></div>

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

function escAttr(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/'/g, "&#39;")
    .replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

var compPreviewTimer = null;
function showCompPreview(event, row) {
  clearTimeout(compPreviewTimer);
  // Small debounce so quickly passing the mouse over several rows in a row doesn't fire off a
  // cascade of map loads for rows the user wasn't actually trying to look at.
  compPreviewTimer = setTimeout(function() {
    var panel = document.getElementById("comp-hover-panel");
    var addr = row.getAttribute("data-addr");
    var mapSrc = "https://maps.google.com/maps?q=" + encodeURIComponent(addr) + "&z=19&t=k&output=embed";
    panel.innerHTML = "<iframe src='" + escAttr(mapSrc) + "' loading='lazy'></iframe>" +
      "<div class='comp-info'><strong>" + escAttr(addr) + "</strong><br>" +
      "Sale Price: " + escAttr(row.getAttribute("data-price")) + " &middot; Sale Date: " + escAttr(row.getAttribute("data-date")) + "<br>" +
      "Beds/Baths: " + escAttr(row.getAttribute("data-beds")) + " &middot; Sq Ft: " + escAttr(row.getAttribute("data-sqft")) +
      " &middot; Distance: " + escAttr(row.getAttribute("data-dist")) + "</div>";
    panel.style.display = "block";
    positionCompPreview(event);
  }, 150);
}

function positionCompPreview(event) {
  var panel = document.getElementById("comp-hover-panel");
  if (panel.style.display !== "block") return;
  var panelWidth = 300, panelHeight = 250;
  var x = event.clientX + 16;
  var y = event.clientY + 16;
  if (x + panelWidth > window.innerWidth) { x = event.clientX - panelWidth - 16; }
  if (y + panelHeight > window.innerHeight) { y = event.clientY - panelHeight - 16; }
  panel.style.left = Math.max(8, x) + "px";
  panel.style.top = Math.max(8, y) + "px";
}

function hideCompPreview() {
  clearTimeout(compPreviewTimer);
  document.getElementById("comp-hover-panel").style.display = "none";
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
      // Sort most-recent-sale-first - ATTOM's own comps order is similarity/proximity-based,
      // not recency-based, so without this the freshest sales could end up buried at the bottom
      // of the list rather than surfaced at the top where they're most useful.
      comps.sort(function(a, b) {
        var dateA = (a.SALES_HISTORY && a.SALES_HISTORY["@TransferDate_ext"]) || "";
        var dateB = (b.SALES_HISTORY && b.SALES_HISTORY["@TransferDate_ext"]) || "";
        return dateB.localeCompare(dateA); // descending - newest first, missing dates sort last
      });
      if (comps.length) {
        compsHtml = "<h4 style='font-size:13px;margin:14px 0 6px;'>Comparable Sales (" + comps.length + " found, most recent first)</h4><div class='table-wrap'><table><tr><th>Address</th><th style='text-align:right;'>Distance</th><th style='text-align:right;'>Sale Price</th><th>Sale Date</th><th>Beds/Baths</th><th style='text-align:right;'>Sq Ft</th></tr>";
        comps.forEach(function(c) {
          var sh = c.SALES_HISTORY || {};
          var st = c.STRUCTURE || {};
          var addrStr = (c["@_StreetAddress"] || "N/A") + ", " + (c["@_City"] || "");
          var dist = c["@DistanceFromSubjectPropertyMilesCount"] ? (+c["@DistanceFromSubjectPropertyMilesCount"]).toFixed(2) + " mi" : "N/A";
          var saleDateStr = sh["@TransferDate_ext"] ? sh["@TransferDate_ext"].slice(0, 10) : "N/A";
          var isRecent = false;
          if (sh["@TransferDate_ext"]) {
            var saleDate = new Date(sh["@TransferDate_ext"]);
            var sixMonthsAgo = new Date();
            sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);
            isRecent = saleDate >= sixMonthsAgo;
          }
          var dateCell = isRecent ? "<strong style='color:#1a8a3d;'>" + saleDateStr + "</strong>" : saleDateStr;
          var priceStr = money(sh["@PropertySalesAmount"]) || "N/A";
          var bedsBathsStr = (st["@TotalBedroomCount"] || "N/A") + " / " + (st["@TotalBathroomCount"] || "N/A");
          var sqftStr = st["@GrossLivingAreaSquareFeetCount"] || "N/A";
          compsHtml += "<tr data-comp-hover data-addr='" + escAttr(addrStr) + "' data-price='" + escAttr(priceStr) +
            "' data-date='" + escAttr(saleDateStr) + "' data-beds='" + escAttr(bedsBathsStr) + "' data-sqft='" + escAttr(sqftStr) +
            "' data-dist='" + escAttr(dist) + "' onmouseenter='showCompPreview(event,this)' onmousemove='positionCompPreview(event)' onmouseleave='hideCompPreview()'>" +
            "<td>" + addrStr + "</td><td style='text-align:right;'>" + dist + "</td>" +
            "<td style='text-align:right;'>" + priceStr + "</td>" +
            "<td>" + dateCell + "</td>" +
            "<td>" + bedsBathsStr + "</td>" +
            "<td style='text-align:right;'>" + sqftStr + "</td></tr>";
        });
        compsHtml += "</table></div><span style='font-size:11px;color:#888;'>Sales within the last 6 months are shown in <strong style='color:#1a8a3d;'>bold green</strong>. ATTOM's comps selection is based on proximity and similarity to the subject property, not recency - the freshest sales are sorted to the top here, but the underlying set of comps returned isn't limited to a specific time window. Hover any row for a satellite view and quick summary.</span>";
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
      "<div id='neighborhood-data'></div>" +

      "<br><span style='font-size:11px;color:#888;'>Data from ATTOM public records. Satellite image via Google Maps, based on the property's coordinates - not an MLS listing photo. Field availability varies by property and county recorder data quality.</span>");

    loadNeighborhoodData(address);
  } catch (err) {
    showResult("ps_result", "<strong style='color:#c0392b;'>Could not reach the search service.</strong> Confirm WORKER_URL is set to your deployed Cloudflare Worker, and that the Worker is running.");
  }
}

// Separate, non-blocking lookup - free Census Bureau data (rental vacancy rate, median gross
// rent for the surrounding Census Tract). Runs after the main property display, and failing
// here doesn't affect the ATTOM property data above, which already rendered successfully.
function loadNeighborhoodData(address) {
  var el = document.getElementById("neighborhood-data");
  if (!el) return;
  el.innerHTML = "<h4 style='font-size:13px;margin:14px 0 6px;'>Neighborhood Data</h4><span style='font-size:12px;color:#888;'>Loading...</span>";
  fetch(WORKER_URL + "/neighborhood-data?address=" + encodeURIComponent(address))
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
      if (data.error) { el.innerHTML = ""; return; }
      // The Census Bureau uses negative "sentinel" codes (e.g. -888888888) to mean "no reliable
      // estimate available for this specific small geography" - not a real percentage/dollar value.
      var isSentinel = function(v) { return v == null || Number(v) < 0; };
      var vacancy = isSentinel(data.rentalVacancyRatePercent) ? null : data.rentalVacancyRatePercent;
      var rent = isSentinel(data.medianGrossRent) ? null : data.medianGrossRent;
      if (vacancy == null && rent == null) { el.innerHTML = ""; return; }
      el.innerHTML = "<h4 style='font-size:13px;margin:14px 0 6px;'>Neighborhood Data</h4>" +
        (vacancy != null ? "Rental vacancy rate: " + vacancy + "%<br>" : "Rental vacancy rate: not available (sample too small for this specific area)<br>") +
        (rent != null && rent > 0 ? "Median gross rent: $" + Number(rent).toLocaleString() + "/mo<br>" : "") +
        "<span style='font-size:11px;color:#888;'>Source: U.S. Census Bureau American Community Survey (5-year estimates), for the Census Tract containing this address - a reasonable proxy for the immediate neighborhood, not the exact block.</span>";
    })
    .catch(function() { el.innerHTML = ""; });
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

__FOOTER__
</body>
</html>"""

search_html = (SEARCH_TEMPLATE
               .replace("__CSS__", PAGE_CSS)
               .replace("__NAV__", NAV_HTML)
               .replace("__DARKMODE_CSS__", DARK_MODE_CSS)
               .replace("__DARKMODE_BUTTON__", DARK_MODE_BUTTON)
               .replace("__DARKMODE_JS__", DARK_MODE_JS)
               .replace("__LEARNINGMODE_CSS__", LEARNING_MODE_CSS)
               .replace("__LEARNINGMODE_BUTTON__", LEARNING_MODE_BUTTON)
               .replace("__LEARNINGMODE_JS__", LEARNING_MODE_JS)
               .replace("__FOOTER__", FOOTER_HTML))

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
__DARKMODE_CSS__
__LEARNINGMODE_CSS__
</style>
</head>
<body>
__DARKMODE_BUTTON__<script>__DARKMODE_JS__</script>
__LEARNINGMODE_BUTTON__<script>__LEARNINGMODE_JS__</script>
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

__FOOTER__
</body>
</html>"""

stocksearch_html = (STOCKSEARCH_TEMPLATE
                     .replace("__CSS__", PAGE_CSS)
                     .replace("__NAV__", NAV_HTML)
                     .replace("__DARKMODE_CSS__", DARK_MODE_CSS)
                     .replace("__DARKMODE_BUTTON__", DARK_MODE_BUTTON)
                     .replace("__DARKMODE_JS__", DARK_MODE_JS)
                     .replace("__LEARNINGMODE_CSS__", LEARNING_MODE_CSS)
                     .replace("__LEARNINGMODE_BUTTON__", LEARNING_MODE_BUTTON)
                     .replace("__LEARNINGMODE_JS__", LEARNING_MODE_JS)
                     .replace("__FOOTER__", FOOTER_HTML))

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
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js"></script>
<style>__CSS__
.calc { background:#fff; border-radius:10px; padding:18px; border:1px solid #e5e3dc; margin-bottom:20px; max-width:640px; }
.calc-wide { background:#fff; border-radius:10px; padding:18px; border:1px solid #e5e3dc; margin-bottom:20px; max-width:100%; }
.calc-wide h3 { margin:0 0 12px; font-size:16px; }
.calc h3 { margin:0 0 12px; font-size:16px; }
.calc label { display:block; font-size:12px; color:#666; margin:10px 0 3px; }
.calc input { width:100%; padding:8px; font-size:14px; border:1px solid #ccc; border-radius:6px; box-sizing:border-box; }
.calc button, .calc-wide button { margin-top:14px; padding:10px 18px; font-size:14px; font-weight:600; color:#fff; background:#1f4e79; border:none; border-radius:6px; cursor:pointer; }
.calc button:hover, .calc-wide button:hover { background:#163a5c; }
.calc button.secondary, .calc-wide button.secondary { background:#888; }
.calc button.secondary:hover, .calc-wide button.secondary:hover { background:#666; }
.result { margin-top:14px; padding:12px; background:#f0f6ec; border-radius:6px; font-size:14px; }
.err { color:#c0392b; font-size:13px; margin-top:8px; }
.property-card { background:#fff; border:1px solid #e5e3dc; border-radius:8px; padding:16px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04); }
.property-card h4 { margin:0 0 6px; font-size:16px; color:#1f4e79; }
@media (max-width: 600px) {
  body { padding:12px; }
  .calc { padding:14px; max-width:100%; }
  .calc-wide { padding:14px; }
  .calc input { font-size:16px !important; padding:10px !important; }
  .calc button { width:100%; }
}
__DARKMODE_CSS__
__LEARNINGMODE_CSS__
body.dark-mode .property-card { background: var(--card-bg); border-color: var(--card-border); color: var(--text); }
</style>
</head>
<body>
__DARKMODE_BUTTON__<script>__DARKMODE_JS__</script>
__LEARNINGMODE_BUTTON__<script>__LEARNINGMODE_JS__</script>
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
    <h3 style="cursor:pointer;" onclick="toggleAddPropertyForm()">+ Add a Property <span id="add-property-toggle-icon">&#9656;</span></h3>
    <div id="add-property-form" style="display:none;">
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
    <label style="margin-top:14px;font-weight:600;">Financing (optional - enables Cap Rate, DSCR, and Cash-on-Cash calculations)</label>
    <label>Down Payment</label>
    <input type="number" id="p-downpayment">
    <label>Loan Amount</label>
    <input type="number" id="p-loanamount">
    <label>Interest Rate (%)</label>
    <input type="number" step="0.01" id="p-rate">
    <label>Amortization Term (years) - used to calculate the monthly payment</label>
    <input type="number" id="p-term" value="30">
    <label>Balloon Term (years, optional) - if the full balance comes due sooner than the amortization period (common in commercial loans)</label>
    <input type="number" id="p-balloon">
    <label>Loan Start Date</label>
    <input type="date" id="p-loanstart">
    <button onclick="addProperty()">Add Property</button>
    <div class="err" id="add-error"></div>
    </div>
  </div>

  <div style="margin-bottom:16px;">
    <button onclick="showRentalView()" id="tab-rental" style="margin-right:8px;">Rental Properties</button>
    <button onclick="showRedevView()" id="tab-redev" class="secondary">Redevelopment Analysis</button>
  </div>

  <div id="rental-view">
  <div id="portfolio-dashboard" style="display:none;margin-bottom:20px;">
    <h3>Portfolio Overview</h3>
    <div class="row" id="portfolio-cards"></div>
  </div>

  <h3>Your Properties</h3>
  <div id="property-list"></div>

  <div id="property-detail" style="display:none;">
    <div class="calc">
      <a href="#" id="back-to-properties" style="font-size:13px;color:#1f4e79;">&larr; Back to Properties</a>
      <h3 id="detail-address" style="margin-top:8px;"></h3>
      <div id="detail-summary" style="font-size:14px;"></div>
      <div class="beginner-box learning-mode-only">
        <h3>&#127891; What These Ratios Mean</h3>
        <ul>
          <li><strong>Cap Rate</strong> - the property's yearly income divided by its price, ignoring the loan entirely. Higher generally means more income relative to price, but often comes with more risk or a rougher market.</li>
          <li><strong>DSCR (Debt Service Coverage Ratio)</strong> - how many times over the property's income covers the loan payment. Above 1.0 means it covers the payment; most commercial lenders want at least 1.20-1.25.</li>
          <li><strong>Cash-on-Cash Return</strong> - the yearly cash flow divided by the actual cash you put in (down payment, closing costs). This accounts for the loan, unlike cap rate.</li>
          <li><strong>GRM (Gross Rent Multiplier)</strong> - price divided by yearly rental income, before any expenses. A rough, quick comparison tool - lower generally means cheaper relative to rent.</li>
        </ul>
        <p style="font-size:11px;color:#888;margin:8px 0 0;">These are standard real estate investing metrics, not a recommendation to buy, hold, or sell this or any property.</p>
      </div>
      <div id="key-ratios" style="font-size:14px;margin-top:10px;"></div>
      <label style="margin-top:14px;">Fixed Monthly Costs (taxes, insurance, etc. - allocated evenly per month)</label>
      <input type="number" id="fixed-monthly-costs" style="max-width:160px;">

      <h4 style="margin:16px 0 6px;font-size:13px;cursor:pointer;" onclick="toggleManagementForm()">Management Fee <span id="management-toggle-icon">&#9656;</span></h4>
      <div id="management-form" style="display:none;">
        <label>Management Fee Structure</label>
        <select id="mgmt-type" onchange="onManagementTypeChange()" style="max-width:250px;">
          <option value="none">Self-Managed (No Fee)</option>
          <option value="flat">Flat Monthly Fee</option>
          <option value="freeApartment">Free Apartment (value = that unit's rent)</option>
          <option value="percentage">Percentage of Collected Rent</option>
        </select>
        <div id="mgmt-flat-fields" style="display:none;">
          <label style="max-width:200px;">Monthly Fee ($)</label>
          <input type="number" id="mgmt-flat-amount" style="max-width:200px;">
        </div>
        <div id="mgmt-freeapt-fields" style="display:none;">
          <label style="max-width:250px;">Which unit is the manager's free apartment?</label>
          <select id="mgmt-unit" style="max-width:250px;"></select>
        </div>
        <div id="mgmt-pct-fields" style="display:none;">
          <label style="max-width:200px;">Percentage of Collected Rent (%)</label>
          <input type="number" step="0.1" id="mgmt-pct-amount" style="max-width:200px;">
        </div>
        <button onclick="saveManagementFee()">Save Management Fee</button>
        <span id="management-save-status" style="margin-left:10px;font-size:13px;"></span>
      </div>

      <h4 style="margin:16px 0 6px;font-size:13px;cursor:pointer;" onclick="toggleFinancingForm()">Financing Details <span id="financing-toggle-icon">&#9656;</span></h4>
      <div id="financing-form" style="display:none;">
        <label>Purchase Price</label>
        <input type="number" id="d-price" style="max-width:160px;">
        <label>Down Payment</label>
        <input type="number" id="d-downpayment" style="max-width:160px;">
        <label>Loan Amount</label>
        <input type="number" id="d-loanamount" style="max-width:160px;">
        <label>Interest Rate (%)</label>
        <input type="number" step="0.01" id="d-rate" style="max-width:160px;">
        <label>Amortization Term (years)</label>
        <input type="number" id="d-term" style="max-width:160px;">
        <label>Balloon Term (years, optional)</label>
        <input type="number" id="d-balloon" style="max-width:160px;">
        <label>Loan Start Date</label>
        <input type="date" id="d-loanstart" style="max-width:160px;">
        <label>Interest-Only Period (years, optional) - no principal reduction during this time, then converts to a fully-amortizing payment</label>
        <input type="number" step="0.5" min="0" id="d-interestonly" placeholder="e.g. 5" style="max-width:160px;">
        <label><input type="checkbox" id="d-isarm" onchange="toggleARMFields()" style="width:auto;display:inline-block;"> This is an ARM (Adjustable Rate Mortgage)</label>
        <div id="arm-fields" style="display:none;">
          <label>Fixed-Rate Period (years) - the "Interest Rate" above (the teaser rate) holds until this point</label>
          <input type="number" step="0.5" min="0" id="d-armfixed" placeholder="e.g. 3" style="max-width:160px;">
          <label>Rate After Fixed Period (%) - the fully-indexed rate it resets to once the fixed period ends</label>
          <input type="number" step="0.01" min="0" id="d-armresetrate" placeholder="e.g. 8" style="max-width:160px;">
          <label>Assumed Further Increase Per Year After That (percentage points) - for stress-testing continued rate risk, e.g. 0.5 means it climbs another 0.5% every year after the reset above</label>
          <input type="number" step="0.1" id="d-armincrease" placeholder="e.g. 0.5" style="max-width:160px;">
          <label><input type="checkbox" id="d-negam" style="width:auto;display:inline-block;"> Interest actually accrues at the Rate After Fixed Period during the teaser period (negative amortization) - check this only if the teaser payment doesn't cover the real interest owed, so the shortfall adds to your balance</label>
        </div>
        <label>Annual Rent Growth Rate (%) - for the 5/10-Year Pro Forma</label>
        <input type="number" step="0.1" id="d-rentgrowth" placeholder="e.g. 3" style="max-width:160px;">
        <label>Annual Expense Growth Rate (%) - for the 5/10-Year Pro Forma</label>
        <input type="number" step="0.1" id="d-expensegrowth" placeholder="e.g. 3" style="max-width:160px;">
        <label>Closing Costs (% of purchase price) - for the IRR calculation, added to your initial cash investment</label>
        <input type="number" step="0.1" id="d-closingcosts" placeholder="e.g. 3" style="max-width:160px;">
        <label>Assumed Exit Cap Rate (%) - for the IRR calculation, used to estimate the sale price if you sold at the end of the hold period (Sale Price = that year's NOI &divide; this rate)</label>
        <input type="number" step="0.01" id="d-exitcaprate" placeholder="e.g. 6" style="max-width:160px;">
        <label>Selling Costs (% of sale price) - broker commission, closing costs, etc.</label>
        <input type="number" step="0.1" id="d-sellingcosts" placeholder="e.g. 6" style="max-width:160px;">
        <label style="margin-top:14px;font-weight:600;">Tax Savings Estimator (optional - enables an estimated income tax savings figure below)</label>
        <label>Annual Property Tax ($)</label>
        <input type="number" id="d-proptax" style="max-width:160px;">
        <label>Building Value (% of Purchase Price) - land isn't depreciable; ~70-80% building is a common rule of thumb, editable based on your appraisal/tax assessor split</label>
        <input type="number" id="d-bldgpct" placeholder="e.g. 80" step="1" min="0" max="100" style="max-width:160px;">
        <label>Your Federal Marginal Tax Bracket (%)</label>
        <select id="d-fedbracket" style="max-width:160px;padding:8px;font-size:14px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;">
        <option value="10">10%</option><option value="12">12%</option><option value="22">22%</option>
        <option value="24" selected>24%</option><option value="32">32%</option><option value="35">35%</option>
        <option value="37">37%</option>
        </select>
        <span style="font-size:11px;color:#888;display:block;max-width:400px;margin-top:4px;">State income tax rate is estimated automatically from the property's State field above. Not tax advice - consult a CPA.</span>
        <button onclick="saveFinancingDetails()">Save Financing Details</button>
        <span id="financing-save-status" style="margin-left:10px;font-size:13px;"></span>
      </div>
      <div style="margin-top:14px;">
        <button onclick="generateRentRollPDF()">Download Rent Roll PDF</button>
        <button onclick="generate5And10YearProFormaPDF()">Download 5/10-Year Pro Forma PDF</button>
        <button onclick="generateYTDReportPDF()">Download YTD Summary PDF</button>
      </div>
      <div style="margin-top:14px;">
        <button onclick="refreshPropertyTaxFromATTOM()">Refresh Property Tax from ATTOM</button>
        <span id="attom-refresh-status" style="margin-left:10px;font-size:13px;"></span>
      </div>
      <div style="margin-top:14px;">
        <label style="display:inline-block;">Statement Month</label>
        <input type="month" id="income-statement-month" style="max-width:160px;display:inline-block;">
        <button onclick="generateIncomeStatementPDF()">Download Income Statement PDF</button>
      </div>
    </div>

    <div class="calc-wide">
      <h3>Units</h3>
      <p class="note">Add units in a batch by type (e.g. 10 x "1 Bed / 1 Bath"), then rename each one's unit number below.</p>
      <label style="max-width:400px;">Unit Type</label>
      <input type="text" id="u-type" placeholder="1 Bed / 1 Bath" style="max-width:400px;">
      <label style="max-width:400px;">How Many of This Type</label>
      <input type="number" id="u-count" value="1" min="1" style="max-width:400px;">
      <label style="max-width:400px;">Rent per Unit</label>
      <input type="number" id="u-rent" style="max-width:400px;">
      <label style="max-width:400px;">Living Area (sq ft per unit)</label>
      <input type="number" id="u-sf" style="max-width:400px;">
      <button onclick="addUnitBatch()">Add Units</button>
      <div class="err" id="unit-error"></div>
      <div id="unit-list" style="margin-top:12px;"></div>
    </div>

    <div class="calc-wide">
      <h3>Other Income</h3>
      <p class="note">Laundry, parking, storage, pet fees, application fees, late fees actually collected, etc. - anything beyond rent.</p>
      <label style="max-width:400px;">Category</label>
      <input type="text" id="i-category" placeholder="Laundry, parking, pet fees, etc." style="max-width:400px;">
      <label style="max-width:400px;">Amount</label>
      <input type="number" id="i-amount" style="max-width:400px;">
      <label style="max-width:400px;">Date</label>
      <input type="date" id="i-date" style="max-width:400px;">
      <label style="margin-top:10px;"><input type="checkbox" id="i-annual" style="width:auto;display:inline-block;"> Annual (spread evenly across all 12 months)</label>
      <button onclick="addIncome()">Add Income</button>
      <div class="err" id="income-error"></div>
      <div id="income-list" style="margin-top:12px;"></div>
    </div>

    <div class="calc-wide">
      <h3>Expenses</h3>
      <label style="max-width:400px;">Category</label>
      <input type="text" id="e-category" placeholder="Property tax, insurance, repairs, etc." style="max-width:400px;">
      <label style="max-width:400px;">Amount</label>
      <input type="number" id="e-amount">
      <label>Date</label>
      <input type="date" id="e-date">
      <label style="margin-top:10px;"><input type="checkbox" id="e-annual" style="width:auto;display:inline-block;"> Annual cost (this amount is the TOTAL for the year - spread evenly across all 12 months, e.g. property tax, insurance)</label>
      <label><input type="checkbox" id="e-recurring" style="width:auto;display:inline-block;"> Recurring monthly (this amount repeats EVERY month starting from the date above, e.g. management fee)</label>
      <label><input type="checkbox" id="e-capex" onchange="toggleCapExFinancing()" style="width:auto;display:inline-block;"> Capital improvement (roof, HVAC replacement, etc. - kept separate from operating expenses)</label>
      <div id="capex-financing-fields" style="display:none;margin-top:10px;padding:10px;background:#f7f6f2;border-radius:6px;">
        <label><input type="checkbox" id="e-financed" style="width:auto;display:inline-block;"> This improvement is financed (not paid in cash)</label>
        <label style="max-width:200px;">Financed Amount</label>
        <input type="number" id="e-financed-amount" style="max-width:200px;">
        <label style="max-width:200px;">Interest Rate (%)</label>
        <input type="number" step="0.01" id="e-financed-rate" style="max-width:200px;">
        <label style="max-width:200px;">Term (years)</label>
        <input type="number" step="0.5" id="e-financed-term" style="max-width:200px;">
      </div>
      <button onclick="addExpense()">Add Expense</button>
      <div class="err" id="expense-error"></div>
      <div id="expense-list" style="margin-top:12px;"></div>
    </div>
  </div>
  </div>

  <div id="redev-view" style="display:none;">
    <div class="calc-wide">
      <h3 style="cursor:pointer;" onclick="toggleAddRedevForm()">+ New Redevelopment Project <span id="add-redev-toggle-icon">&#9656;</span></h3>
      <div id="add-redev-form" style="display:none;">
        <label style="max-width:400px;">Project Name</label>
        <input type="text" id="rp-name" placeholder="e.g. 8100 Harding Ave Assemblage" style="max-width:400px;">
        <button onclick="addRedevProject()">Create Project</button>
        <div class="err" id="redev-error"></div>
      </div>
    </div>

    <h3>Your Redevelopment Projects</h3>
    <div id="redev-list"></div>

    <div id="redev-detail" style="display:none;">
      <div class="calc">
        <a href="#" id="back-to-redev-list" style="font-size:13px;color:#1f4e79;">&larr; Back to Projects</a>
        <h3 id="redev-detail-name" style="margin-top:8px;"></h3>
        <div id="redev-summary" style="font-size:14px;"></div>
      </div>

      <div class="calc-wide">
        <h3>Parcels (add multiple to assemble adjacent properties)</h3>
        <label style="max-width:400px;">Address</label>
        <input type="text" id="pc-address" placeholder="123 Main St" style="max-width:400px;">
        <label style="max-width:400px;">Lot Size (sq ft)</label>
        <input type="number" id="pc-lotsize" style="max-width:400px;">
        <label style="max-width:400px;">Existing Building Size (sq ft)</label>
        <input type="number" id="pc-buildingsize" style="max-width:400px;">
        <label style="max-width:400px;">Existing Use</label>
        <input type="text" id="pc-use" placeholder="Hotel, apartment building, vacant land, etc." style="max-width:400px;">
        <label style="max-width:400px;">Purchase Price (or asking price)</label>
        <input type="number" id="pc-price" style="max-width:400px;">
        <button onclick="addParcel()">Add Parcel</button>
        <div class="err" id="parcel-error"></div>
        <div id="parcel-list" style="margin-top:12px;"></div>
      </div>

      <div class="calc-wide">
        <h3>Zoning Parameters</h3>
        <p class="note">Look these up from the specific city/county's zoning code or GIS portal for this site - there's no national database for this, so these need to be entered manually.</p>
        <label style="max-width:250px;">FAR (Floor Area Ratio)</label>
        <input type="number" step="0.01" id="zp-far" placeholder="e.g. 2.0" style="max-width:250px;">
        <label style="max-width:250px;">Max Height (feet)</label>
        <input type="number" id="zp-height" style="max-width:250px;">
        <label style="max-width:250px;">Max Density (units/acre)</label>
        <input type="number" id="zp-density" style="max-width:250px;">
        <label style="max-width:250px;">Parking Ratio (spaces/unit)</label>
        <input type="number" step="0.1" id="zp-parking" style="max-width:250px;">
        <label style="max-width:250px;">Max Lot Coverage (%)</label>
        <input type="number" id="zp-coverage" style="max-width:250px;">
        <label style="max-width:250px;">Zoning District</label>
        <input type="text" id="zp-district" placeholder="e.g. T6-8, RM-3" style="max-width:250px;">
        <button onclick="saveZoningParams()">Save Zoning Parameters</button>
        <span id="zoning-save-status" style="margin-left:10px;font-size:13px;"></span>
        <div id="buildable-envelope" style="margin-top:14px;"></div>
      </div>

      <div class="calc-wide">
        <h3>Unit Mix Plan</h3>
        <p class="note">Plan out the proposed new building's unit mix and projected rents.</p>
        <label style="max-width:250px;">Unit Type</label>
        <input type="text" id="um-type" placeholder="Studio, 1BR, 2BR, Retail, etc." style="max-width:250px;">
        <label style="max-width:250px;">Number of Units</label>
        <input type="number" id="um-count" min="1" style="max-width:250px;">
        <label style="max-width:250px;">Avg. Size (sq ft)</label>
        <input type="number" id="um-sf" style="max-width:250px;">
        <label style="max-width:250px;">Avg. Monthly Rent</label>
        <input type="number" id="um-rent" style="max-width:250px;">
        <button onclick="addUnitMixItem()">Add to Unit Mix</button>
        <div class="err" id="unitmix-error"></div>
        <div id="unitmix-list" style="margin-top:12px;"></div>
      </div>

      <div class="calc-wide">
        <h3>Development Cost &amp; Operating Assumptions</h3>
        <label style="max-width:250px;">Hard Cost ($/sq ft)</label>
        <input type="number" id="dc-hardcost" placeholder="e.g. 250" style="max-width:250px;">
        <label style="max-width:250px;">Soft Costs (% of hard cost)</label>
        <input type="number" id="dc-softcost" placeholder="e.g. 20" style="max-width:250px;">
        <label style="max-width:250px;">Contingency (% of hard+soft)</label>
        <input type="number" id="dc-contingency" placeholder="e.g. 10" style="max-width:250px;">
        <label style="max-width:250px;">Vacancy Assumption (%)</label>
        <input type="number" id="dc-vacancy" placeholder="e.g. 5" style="max-width:250px;">
        <label style="max-width:250px;">Operating Expense Ratio (% of EGI)</label>
        <input type="number" id="dc-opex" placeholder="e.g. 40" style="max-width:250px;">
        <label style="max-width:250px;">Exit Cap Rate (%)</label>
        <input type="number" step="0.01" id="dc-exitcap" placeholder="e.g. 5.5" style="max-width:250px;">
        <button onclick="saveDevCostAssumptions()">Save Assumptions</button>
        <span id="devcost-save-status" style="margin-left:10px;font-size:13px;"></span>
      </div>

      <div class="calc-wide">
        <h3>Redevelopment Pro Forma</h3>
        <div id="redev-proforma"></div>
      </div>
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

// Reuses the same ATTOM Worker already deployed for Property Search, to auto-fetch
// property tax when a new property is added here.
var ATTOM_WORKER_URL = "https://attom-proxy.tonyhernandezusa.workers.dev";

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
    loadRedevProjects(user.uid);
  } else {
    document.getElementById("auth-panel").style.display = "block";
    document.getElementById("dashboard").style.display = "none";
  }
});

function toggleAddPropertyForm() {
  var form = document.getElementById("add-property-form");
  var icon = document.getElementById("add-property-toggle-icon");
  var isHidden = form.style.display === "none";
  form.style.display = isHidden ? "block" : "none";
  icon.innerHTML = isHidden ? "&#9662;" : "&#9656;";
}

// Standard amortization formula for monthly Principal & Interest payment.
// Reusable across Key Ratios, the Balloon calculation, Income Statement, and the 5/10-Year
// Pro Forma - all need to know how many monthly payments have been made as of a given point.
function getMonthsElapsedSinceLoanStart(loanStartDate, asOfYear, asOfMonthIdx) {
  if (!loanStartDate) return 0;
  var startYear = parseInt(loanStartDate.slice(0, 4), 10);
  var startMonthIdx = parseInt(loanStartDate.slice(5, 7), 10) - 1;
  if (isNaN(startYear) || isNaN(startMonthIdx)) return 0;
  var startLinearMonth = startYear * 12 + startMonthIdx;
  var asOfLinearMonth = asOfYear * 12 + asOfMonthIdx;
  return Math.max(0, asOfLinearMonth - startLinearMonth);
}

function calculateMonthlyPI(loanAmount, annualRatePct, termYears) {
  if (!loanAmount || loanAmount <= 0 || !termYears || termYears <= 0) return 0;
  var n = termYears * 12;
  if (!annualRatePct || annualRatePct === 0) return loanAmount / n;
  var r = (annualRatePct / 100) / 12;
  return loanAmount * (r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
}

// Remaining principal balance after a given number of payments into an amortizing loan -
// used for balloon payment calculations (e.g. a loan amortized over 25 years but with the
// full remaining balance due after 10 years, common in commercial financing).
function calculateRemainingBalance(loanAmount, annualRatePct, amortTermYears, paymentsAlreadyMade) {
  if (!loanAmount || loanAmount <= 0 || !amortTermYears || amortTermYears <= 0) return 0;
  var n = amortTermYears * 12;
  var p = paymentsAlreadyMade;
  if (p >= n) return 0;
  if (!annualRatePct || annualRatePct === 0) return loanAmount * (1 - p / n);
  var r = (annualRatePct / 100) / 12;
  return loanAmount * (Math.pow(1 + r, n) - Math.pow(1 + r, p)) / (Math.pow(1 + r, n) - 1);
}

// Monthly payment accounting for an interest-only period: during IO, the payment is just
// interest on the full principal (no reduction); once IO ends, the payment recalculates to
// fully amortize the ORIGINAL principal (since it never went down) over whatever years remain
// in the total amortization term - this correctly produces the real-world "payment shock"
// interest-only loans are known for.
function calculateMonthlyDebtService(loanAmount, annualRatePct, amortTermYears, interestOnlyYears, monthsElapsed) {
  var ioMonths = Math.round((interestOnlyYears || 0) * 12);
  if (monthsElapsed < ioMonths) {
    return loanAmount * ((annualRatePct || 0) / 100) / 12;
  }
  var remainingYears = amortTermYears - (interestOnlyYears || 0);
  return calculateMonthlyPI(loanAmount, annualRatePct, remainingYears);
}

// Remaining balance accounting for an interest-only period - the balance stays at the full
// original amount throughout IO (since no principal is being paid down), then decreases
// normally once amortization begins.
function calculateRemainingBalanceWithIO(loanAmount, annualRatePct, amortTermYears, interestOnlyYears, monthsElapsed) {
  var ioMonths = Math.round((interestOnlyYears || 0) * 12);
  if (monthsElapsed <= ioMonths) return loanAmount;
  var remainingYears = amortTermYears - (interestOnlyYears || 0);
  return calculateRemainingBalance(loanAmount, annualRatePct, remainingYears, monthsElapsed - ioMonths);
}

// Full month-by-month amortization simulator - the only correct way to combine an
// interest-only period, an ARM's rate adjustments, negative amortization, and balance tracking
// together, since ARM rate changes require recalculating the payment against the current
// balance and remaining term (there's no single closed-form formula once the rate changes).
// Rate structure: initialRatePct (the teaser rate) holds through armFixedYears, then jumps
// once to armResetRate (the fully-indexed rate), then optionally continues climbing by
// armRateIncreasePerYear each subsequent year from that new base.
// If isNegativeAmortization is true, interest actually ACCRUES at armResetRate throughout the
// teaser period (not the teaser rate) - so the payment (based on the lower teaser rate) doesn't
// cover the real interest owed, and the shortfall is added to the balance each month.
// Returns, for each of the requested number of years: the annual debt service paid and the
// balance remaining at the end of that year.
// Solves for the Internal Rate of Return given a series of annual cash flows (index 0 = the
// initial investment, typically negative). Uses bisection search rather than a closed-form
// formula, since none exists for an arbitrary cash flow series - verified against known cases
// and cross-checked against numpy_financial's IRR implementation during development.
function calculateIRR(cashFlows) {
  function npv(rate) {
    return cashFlows.reduce(function(sum, cf, i) { return sum + cf / Math.pow(1 + rate, i); }, 0);
  }
  var low = -0.99, high = 10;
  var npvLow = npv(low), npvHigh = npv(high);
  if (npvLow * npvHigh > 0) return null; // no clear single IRR found in this range
  for (var i = 0; i < 100; i++) {
    var mid = (low + high) / 2;
    var npvMid = npv(mid);
    if (Math.abs(npvMid) < 0.0001) return mid;
    if (npvMid * npvLow < 0) { high = mid; npvHigh = npvMid; }
    else { low = mid; npvLow = npvMid; }
  }
  return (low + high) / 2;
}

function simulateLoanAmortization(loanAmount, initialRatePct, amortTermYears, interestOnlyYears, isARM, armFixedYears, armResetRate, armRateIncreasePerYear, isNegativeAmortization, numYears) {
  var balance = loanAmount;
  var ioMonths = Math.round((interestOnlyYears || 0) * 12);
  var armFixedMonths = isARM ? Math.round((armFixedYears || 0) * 12) : Infinity;
  var totalTermMonths = amortTermYears * 12;
  var currentRate = initialRatePct;
  var monthlyPayment = null;
  var yearResults = [];
  var yearDebtServiceSum = 0;
  var ioEndedThisYear = false;
  var negAmActive = isARM && isNegativeAmortization && (armResetRate || 0) > 0;

  for (var month = 0; month < numYears * 12; month++) {
    var inTeaserPeriod = isARM && month < armFixedMonths;
    var newRate;
    if (!isARM || month < armFixedMonths) {
      newRate = initialRatePct; // still within the teaser/fixed-rate period (payment rate)
    } else {
      var yearsPastReset = Math.floor((month - armFixedMonths) / 12); // 0 in the reset year itself
      newRate = (armResetRate || 0) + yearsPastReset * (armRateIncreasePerYear || 0);
    }
    var rateChanged = newRate !== currentRate;
    currentRate = newRate;
    var monthlyRate = currentRate / 100 / 12;

    // The rate interest actually ACCRUES at - only differs from the payment rate during the
    // negative-amortization teaser period, when it's the higher fully-indexed reset rate.
    var accrualRate = (negAmActive && inTeaserPeriod) ? armResetRate : currentRate;
    var accrualMonthlyRate = accrualRate / 100 / 12;

    var thisMonthPayment;
    if (month < ioMonths) {
      thisMonthPayment = balance * monthlyRate; // interest-only, calculated at the PAYMENT rate
    } else {
      var remainingMonths = totalTermMonths - month;
      if (remainingMonths <= 0) {
        thisMonthPayment = 0;
      } else if (monthlyPayment === null || rateChanged || month === ioMonths) {
        // Recalculate only when entering amortization for the first time, or the rate changes -
        // otherwise the payment stays the same between adjustment points, like a real ARM.
        thisMonthPayment = calculateMonthlyPI(balance, currentRate, remainingMonths / 12);
        if (month === ioMonths && ioMonths > 0) ioEndedThisYear = true;
      } else {
        thisMonthPayment = monthlyPayment;
      }
    }

    // Unified balance update: interest actually accrued (at accrualRate) vs. what was paid.
    // In the normal case these match, so principalPortion is 0 during IO, same as before.
    // During negative amortization, accrued interest exceeds the payment, so principalPortion
    // is negative - meaning the balance GROWS instead of shrinking.
    var interestAccrued = balance * accrualMonthlyRate;
    var principalPortion = thisMonthPayment - interestAccrued;
    balance = Math.max(0, balance - principalPortion);

    monthlyPayment = thisMonthPayment;
    yearDebtServiceSum += thisMonthPayment;

    if ((month + 1) % 12 === 0) {
      yearResults.push({ debtService: yearDebtServiceSum, endingBalance: balance, rate: currentRate, ioEndedThisYear: ioEndedThisYear });
      yearDebtServiceSum = 0;
      ioEndedThisYear = false;
    }
  }
  return yearResults;
}

// Financed capital improvements (e.g. a roof paid off over 5 years) show up as a recurring
// monthly payment for the life of that specific loan, not a one-time hit in the month incurred -
// same treatment as the property's main mortgage, just per-improvement and time-bounded.
function getCapExFinancingForMonth(capExExpenses, year, monthIdx) {
  var targetLinearMonth = year * 12 + monthIdx;
  var items = [];
  capExExpenses.forEach(function(e) {
    if (!e.isFinanced) return;
    var d = e.date || "";
    var startYear = parseInt(d.slice(0, 4), 10);
    var startMonthIdx = parseInt(d.slice(5, 7), 10) - 1;
    if (isNaN(startYear) || isNaN(startMonthIdx)) return;
    var startLinearMonth = startYear * 12 + startMonthIdx;
    var termMonths = Math.round((e.financedTermYears || 0) * 12);
    if (termMonths <= 0) return;
    var endLinearMonth = startLinearMonth + termMonths; // exclusive - loan is paid off by this month
    if (targetLinearMonth >= startLinearMonth && targetLinearMonth < endLinearMonth) {
      var payment = calculateMonthlyPI(e.financedAmount || e.amount, e.financedRate || 0, e.financedTermYears);
      items.push({ category: e.category, amount: payment });
    }
  });
  return items;
}

function addProperty() {
  var user = auth.currentUser;
  if (!user) return;
  var address = document.getElementById("p-address").value.trim();
  var city = document.getElementById("p-city").value.trim();
  var state = document.getElementById("p-state").value.trim();
  var zip = document.getElementById("p-zip").value.trim();
  var units = parseInt(document.getElementById("p-units").value, 10) || 1;
  var price = document.getElementById("p-price").value ? parseFloat(document.getElementById("p-price").value) : null;
  var downPayment = parseFloat(document.getElementById("p-downpayment").value) || 0;
  var loanAmount = parseFloat(document.getElementById("p-loanamount").value) || 0;
  var interestRate = parseFloat(document.getElementById("p-rate").value) || 0;
  var loanTermYears = parseFloat(document.getElementById("p-term").value) || 30;
  var balloonTermYears = parseFloat(document.getElementById("p-balloon").value) || 0;
  var loanStartDate = document.getElementById("p-loanstart").value || "";

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
    downPayment: downPayment,
    loanAmount: loanAmount,
    interestRate: interestRate,
    loanTermYears: loanTermYears,
    balloonTermYears: balloonTermYears,
    loanStartDate: loanStartDate,
    createdAt: firebase.firestore.FieldValue.serverTimestamp()
  }).then(function(docRef) {
    document.getElementById("p-address").value = "";
    document.getElementById("p-city").value = "";
    document.getElementById("p-state").value = "";
    document.getElementById("p-zip").value = "";
    document.getElementById("p-units").value = "1";
    document.getElementById("p-price").value = "";
    document.getElementById("p-downpayment").value = "";
    document.getElementById("p-loanamount").value = "";
    document.getElementById("p-rate").value = "";
    document.getElementById("p-term").value = "30";
    document.getElementById("p-balloon").value = "";
    document.getElementById("p-loanstart").value = "";
    toggleAddPropertyForm();
    autoFetchPropertyTax(docRef.id, address, city, state, zip);
  }).catch(function(err) {
    showError("add-error", err.message);
  });
}

// Reuses the same ATTOM Worker as Property Search to automatically look up and log this
// property's current annual property tax as an Annual expense entry - no manual entry needed.
// Runs silently in the background; if the lookup fails or finds nothing, it just does nothing,
// since the property itself was already created successfully regardless.
function autoFetchPropertyTax(propertyId, address, city, state, zip) {
  var fullAddress = [address, city, state, zip].filter(Boolean).join(", ");
  fetch(ATTOM_WORKER_URL + "/property-search?address=" + encodeURIComponent(fullAddress))
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
      var prop = data.property && data.property[0];
      var tax = prop && prop.assessment && prop.assessment.tax;
      if (!tax || !tax.taxAmt) return; // no tax data found - silently skip, nothing to add
      return db.collection("properties").doc(propertyId).collection("entries").add({
        type: "expense",
        category: "Property Tax (via ATTOM)",
        amount: Number(tax.taxAmt),
        date: new Date().toISOString().slice(0, 10),
        isAnnual: true,
        isCapEx: false,
        createdAt: firebase.firestore.FieldValue.serverTimestamp()
      });
    })
    .catch(function() { /* silent - property creation already succeeded either way */ });
}

// Same lookup as autoFetchPropertyTax, but for existing properties triggered manually via
// button click - shows visible status feedback since there's no "property just got created"
// context to silently piggyback on.
function refreshPropertyTaxFromATTOM() {
  if (!currentPropertyId) return;
  var statusEl = document.getElementById("attom-refresh-status");
  var d = currentPropertyData;
  var fullAddress = [d.address, d.city, d.state, d.zip].filter(Boolean).join(", ");
  if (!d.address) {
    statusEl.textContent = "No address on file for this property.";
    statusEl.style.color = "#c0392b";
    return;
  }
  statusEl.textContent = "Looking up property tax...";
  statusEl.style.color = "#888";
  fetch(ATTOM_WORKER_URL + "/property-search?address=" + encodeURIComponent(fullAddress))
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
      var prop = data.property && data.property[0];
      var tax = prop && prop.assessment && prop.assessment.tax;
      if (!tax || !tax.taxAmt) {
        statusEl.textContent = "No property tax data found for this address via ATTOM.";
        statusEl.style.color = "#c0392b";
        return;
      }
      return db.collection("properties").doc(currentPropertyId).collection("entries").add({
        type: "expense",
        category: "Property Tax (via ATTOM)",
        amount: Number(tax.taxAmt),
        date: new Date().toISOString().slice(0, 10),
        isAnnual: true,
        isCapEx: false,
        createdAt: firebase.firestore.FieldValue.serverTimestamp()
      }).then(function() {
        statusEl.textContent = "Added: $" + Number(tax.taxAmt).toLocaleString() + " (" + (tax.taxYear || "current") + ")";
        statusEl.style.color = "#1a8a3d";
      });
    })
    .catch(function(err) {
      statusEl.textContent = "Error: " + err.message;
      statusEl.style.color = "#c0392b";
    });
}


var portfolioStats = {};
var portfolioListeners = {};

function trackPropertyForPortfolio(propertyId) {
  if (portfolioListeners[propertyId]) return; // already tracked
  portfolioStats[propertyId] = { units: 0, occupied: 0, monthlyRent: 0, monthlyOpEx: 0, monthlyOtherIncome: 0 };

  function recompute() {
    renderPortfolioDashboard();
  }

  var unitsL = db.collection("properties").doc(propertyId).collection("entries").where("type", "==", "unit")
    .onSnapshot(function(snap) {
      var units = [];
      snap.forEach(function(d) { units.push(d.data()); });
      var occupied = units.filter(function(u) { return getUnitStatus(u) !== "vacant"; });
      portfolioStats[propertyId].units = units.length;
      portfolioStats[propertyId].occupied = occupied.length;
      portfolioStats[propertyId].monthlyRent = occupied.reduce(function(s, u) { return s + Number(u.rent || 0); }, 0);
      recompute();
    });

  var expensesL = db.collection("properties").doc(propertyId).collection("entries").where("type", "==", "expense")
    .onSnapshot(function(snap) {
      var expenses = [];
      snap.forEach(function(d) { expenses.push(d.data()); });
      var operating = expenses.filter(function(e) { return !e.isCapEx; });
      var now = new Date();
      var eff = getEffectiveMonthlyExpenses(operating, now.getFullYear(), now.getMonth());
      var fixed = eff.fixedFromAnnual.reduce(function(s, e) { return s + e.amount; }, 0);
      var variable = eff.variable.reduce(function(s, e) { return s + e.amount; }, 0);
      portfolioStats[propertyId].monthlyOpEx = fixed + variable;
      recompute();
    });

  var incomeL = db.collection("properties").doc(propertyId).collection("entries").where("type", "==", "income")
    .onSnapshot(function(snap) {
      var incomeEntries = [];
      snap.forEach(function(d) { incomeEntries.push(d.data()); });
      var now = new Date();
      var eff = getEffectiveMonthlyExpenses(incomeEntries, now.getFullYear(), now.getMonth());
      portfolioStats[propertyId].monthlyOtherIncome = eff.fixedFromAnnual.reduce(function(s, e) { return s + e.amount; }, 0) +
        eff.variable.reduce(function(s, e) { return s + e.amount; }, 0);
      recompute();
    });

  portfolioListeners[propertyId] = { unitsL: unitsL, expensesL: expensesL, incomeL: incomeL };
}

function untrackPropertyForPortfolio(propertyId) {
  var l = portfolioListeners[propertyId];
  if (l) { l.unitsL(); l.expensesL(); l.incomeL(); delete portfolioListeners[propertyId]; }
  delete portfolioStats[propertyId];
}

function renderPortfolioDashboard() {
  var el = document.getElementById("portfolio-cards");
  var ids = Object.keys(portfolioStats);
  if (!ids.length) { document.getElementById("portfolio-dashboard").style.display = "none"; return; }
  document.getElementById("portfolio-dashboard").style.display = "block";

  var totalProperties = ids.length;
  var totalUnits = 0, totalOccupied = 0, totalRent = 0, totalOpEx = 0, totalOtherIncome = 0;
  ids.forEach(function(id) {
    var s = portfolioStats[id];
    totalUnits += s.units;
    totalOccupied += s.occupied;
    totalRent += s.monthlyRent;
    totalOpEx += s.monthlyOpEx;
    totalOtherIncome += s.monthlyOtherIncome;
  });
  var occupancyPct = totalUnits ? Math.round((totalOccupied / totalUnits) * 100) : 0;
  var totalIncome = totalRent + totalOtherIncome;
  var cashFlow = totalIncome - totalOpEx;
  var cashFlowColor = cashFlow >= 0 ? "#1a8a3d" : "#c0392b";

  el.innerHTML =
    "<div class='card'><p class='label'>Properties</p><p class='value'>" + totalProperties + "</p></div>" +
    "<div class='card'><p class='label'>Total Units</p><p class='value'>" + totalUnits + "</p></div>" +
    "<div class='card'><p class='label'>Occupancy</p><p class='value'>" + occupancyPct + "%</p><p style='margin:2px 0 0;font-size:11px;color:#999;'>" + totalOccupied + " of " + totalUnits + " occupied</p></div>" +
    "<div class='card'><p class='label'>Monthly Income</p><p class='value'>$" + totalIncome.toLocaleString(undefined, {maximumFractionDigits: 0}) + "</p></div>" +
    "<div class='card'><p class='label'>Monthly Expenses</p><p class='value'>$" + totalOpEx.toLocaleString(undefined, {maximumFractionDigits: 0}) + "</p></div>" +
    "<div class='card'><p class='label'>Monthly Cash Flow</p><p class='value' style='color:" + cashFlowColor + ";'>$" + cashFlow.toLocaleString(undefined, {maximumFractionDigits: 0}) + "</p></div>";
}

function loadProperties(uid) {
  db.collection("properties").where("ownerId", "==", uid).onSnapshot(function(snapshot) {
    var listEl = document.getElementById("property-list");
    var currentIds = [];
    snapshot.forEach(function(doc) { currentIds.push(doc.id); });
    Object.keys(portfolioListeners).forEach(function(id) {
      if (currentIds.indexOf(id) === -1) untrackPropertyForPortfolio(id);
    });
    currentIds.forEach(function(id) { trackPropertyForPortfolio(id); });

    if (snapshot.empty) {
      listEl.innerHTML = "<p class='note'>No properties yet - add one above.</p>";
      document.getElementById("portfolio-dashboard").style.display = "none";
      return;
    }
    var html = "";
    snapshot.forEach(function(doc) {
      var p = doc.data();
      var stats = portfolioStats[doc.id];
      var quickStats = stats ? (stats.occupied + "/" + stats.units + " occupied &middot; $" + stats.monthlyRent.toLocaleString() + "/mo rent") : "";
      html += "<div class='property-card'>" +
        "<h4>" + p.address + "</h4>" +
        (p.city || p.state || p.zip ? "<span style='font-size:13px;color:#666;'>" + [p.city, p.state, p.zip].filter(Boolean).join(", ") + "</span><br>" : "") +
        (quickStats ? "<span style='font-size:13px;color:#1f4e79;font-weight:600;'>" + quickStats + "</span><br>" : "Units: " + p.units + "<br>") +
        (p.purchasePrice ? "Purchase price: $" + Number(p.purchasePrice).toLocaleString() : "") +
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
          untrackPropertyForPortfolio(btn.getAttribute("data-id"));
          db.collection("properties").doc(btn.getAttribute("data-id")).delete();
        }
      });
    });
  });
}

function showRentalView() {
  document.getElementById("rental-view").style.display = "block";
  document.getElementById("redev-view").style.display = "none";
  document.getElementById("tab-rental").classList.remove("secondary");
  document.getElementById("tab-redev").classList.add("secondary");
}
function showRedevView() {
  document.getElementById("rental-view").style.display = "none";
  document.getElementById("redev-view").style.display = "block";
  document.getElementById("tab-rental").classList.add("secondary");
  document.getElementById("tab-redev").classList.remove("secondary");
}

function toggleAddRedevForm() {
  var form = document.getElementById("add-redev-form");
  var icon = document.getElementById("add-redev-toggle-icon");
  var isHidden = form.style.display === "none";
  form.style.display = isHidden ? "block" : "none";
  icon.innerHTML = isHidden ? "&#9662;" : "&#9656;";
}

function addRedevProject() {
  var user = auth.currentUser;
  if (!user) return;
  var name = document.getElementById("rp-name").value.trim();
  showError("redev-error", "");
  if (!name) { showError("redev-error", "Enter a project name."); return; }

  db.collection("redevProjects").add({
    ownerId: user.uid,
    name: name,
    createdAt: firebase.firestore.FieldValue.serverTimestamp()
  }).then(function() {
    document.getElementById("rp-name").value = "";
    toggleAddRedevForm();
  }).catch(function(err) { showError("redev-error", err.message); });
}

function loadRedevProjects(uid) {
  db.collection("redevProjects").where("ownerId", "==", uid).onSnapshot(function(snapshot) {
    var listEl = document.getElementById("redev-list");
    if (snapshot.empty) {
      listEl.innerHTML = "<p class='note'>No redevelopment projects yet - add one above.</p>";
      return;
    }
    var html = "";
    snapshot.forEach(function(doc) {
      var p = doc.data();
      html += "<div class='property-card'>" +
        "<h4>" + p.name + "</h4>" +
        "<button style='margin-top:8px;padding:6px 12px;font-size:12px;' data-view-id='" + doc.id + "' data-view-name='" + p.name.replace(/'/g, "&#39;") + "'>Open Analysis</button> " +
        "<button class='secondary' style='margin-top:8px;padding:6px 12px;font-size:12px;' data-id='" + doc.id + "'>Delete</button>" +
        "</div>";
    });
    listEl.innerHTML = html;
    listEl.querySelectorAll("button[data-view-id]").forEach(function(btn) {
      btn.addEventListener("click", function() {
        openRedevDetail(btn.getAttribute("data-view-id"), btn.getAttribute("data-view-name"));
      });
    });
    listEl.querySelectorAll("button[data-id]").forEach(function(btn) {
      btn.addEventListener("click", function() {
        if (confirm("Delete this redevelopment project?")) {
          db.collection("redevProjects").doc(btn.getAttribute("data-id")).delete();
        }
      });
    });
  });
}

var currentRedevProjectId = null;
var parcelsUnsub = null;
var currentParcels = [];

var currentRedevProjectData = {};
var currentUnitMix = [];
var unitMixUnsub = null;

function openRedevDetail(projectId, name) {
  currentRedevProjectId = projectId;
  document.getElementById("redev-list").parentElement.querySelector("h3").style.display = "none";
  document.getElementById("redev-list").style.display = "none";
  document.getElementById("redev-detail").style.display = "block";
  document.getElementById("redev-detail-name").textContent = name;

  db.collection("redevProjects").doc(projectId).get().then(function(doc) {
    var data = doc.data() || {};
    currentRedevProjectData = data;
    document.getElementById("zp-far").value = data.far || "";
    document.getElementById("zp-height").value = data.maxHeight || "";
    document.getElementById("zp-density").value = data.maxDensity || "";
    document.getElementById("zp-parking").value = data.parkingRatio || "";
    document.getElementById("zp-coverage").value = data.lotCoverage || "";
    document.getElementById("zp-district").value = data.zoningDistrict || "";
    document.getElementById("dc-hardcost").value = data.hardCostPerSF || "";
    document.getElementById("dc-softcost").value = data.softCostPct || "";
    document.getElementById("dc-contingency").value = data.contingencyPct || "";
    document.getElementById("dc-vacancy").value = data.vacancyPct || "";
    document.getElementById("dc-opex").value = data.opexPct || "";
    document.getElementById("dc-exitcap").value = data.exitCapRate || "";
    renderBuildableEnvelope();
    renderProForma();
  });

  if (parcelsUnsub) parcelsUnsub();
  parcelsUnsub = db.collection("redevProjects").doc(projectId).collection("parcels")
    .onSnapshot(function(snapshot) {
      currentParcels = [];
      snapshot.forEach(function(doc) { currentParcels.push({ id: doc.id, ...doc.data() }); });
      renderParcels();
      renderBuildableEnvelope();
      renderProForma();
    });

  if (unitMixUnsub) unitMixUnsub();
  unitMixUnsub = db.collection("redevProjects").doc(projectId).collection("unitMix")
    .onSnapshot(function(snapshot) {
      currentUnitMix = [];
      snapshot.forEach(function(doc) { currentUnitMix.push({ id: doc.id, ...doc.data() }); });
      renderUnitMix();
      renderBuildableEnvelope();
      renderProForma();
    });
}

function saveZoningParams() {
  if (!currentRedevProjectId) return;
  var updates = {
    far: parseFloat(document.getElementById("zp-far").value) || 0,
    maxHeight: parseFloat(document.getElementById("zp-height").value) || 0,
    maxDensity: parseFloat(document.getElementById("zp-density").value) || 0,
    parkingRatio: parseFloat(document.getElementById("zp-parking").value) || 0,
    lotCoverage: parseFloat(document.getElementById("zp-coverage").value) || 0,
    zoningDistrict: document.getElementById("zp-district").value.trim()
  };
  var statusEl = document.getElementById("zoning-save-status");
  statusEl.textContent = "Saving...";
  statusEl.style.color = "#888";
  db.collection("redevProjects").doc(currentRedevProjectId).update(updates).then(function() {
    currentRedevProjectData = Object.assign({}, currentRedevProjectData, updates);
    renderBuildableEnvelope();
    statusEl.textContent = "Saved.";
    statusEl.style.color = "#1a8a3d";
    setTimeout(function() { statusEl.textContent = ""; }, 3000);
  }).catch(function(err) {
    statusEl.textContent = "Error: " + err.message;
    statusEl.style.color = "#c0392b";
  });
}

function saveDevCostAssumptions() {
  if (!currentRedevProjectId) return;
  var updates = {
    hardCostPerSF: parseFloat(document.getElementById("dc-hardcost").value) || 0,
    softCostPct: parseFloat(document.getElementById("dc-softcost").value) || 0,
    contingencyPct: parseFloat(document.getElementById("dc-contingency").value) || 0,
    vacancyPct: parseFloat(document.getElementById("dc-vacancy").value) || 0,
    opexPct: parseFloat(document.getElementById("dc-opex").value) || 0,
    exitCapRate: parseFloat(document.getElementById("dc-exitcap").value) || 0
  };
  var statusEl = document.getElementById("devcost-save-status");
  statusEl.textContent = "Saving...";
  statusEl.style.color = "#888";
  db.collection("redevProjects").doc(currentRedevProjectId).update(updates).then(function() {
    currentRedevProjectData = Object.assign({}, currentRedevProjectData, updates);
    renderProForma();
    statusEl.textContent = "Saved.";
    statusEl.style.color = "#1a8a3d";
    setTimeout(function() { statusEl.textContent = ""; }, 3000);
  }).catch(function(err) {
    statusEl.textContent = "Error: " + err.message;
    statusEl.style.color = "#c0392b";
  });
}

function addUnitMixItem() {
  if (!currentRedevProjectId) return;
  var type = document.getElementById("um-type").value.trim();
  var count = parseInt(document.getElementById("um-count").value, 10) || 0;
  var sf = parseFloat(document.getElementById("um-sf").value) || 0;
  var rent = parseFloat(document.getElementById("um-rent").value) || 0;

  showError("unitmix-error", "");
  if (!type) { showError("unitmix-error", "Enter a unit type."); return; }
  if (!count) { showError("unitmix-error", "Enter how many units."); return; }

  db.collection("redevProjects").doc(currentRedevProjectId).collection("unitMix").add({
    type: type, count: count, sf: sf, rent: rent,
    createdAt: firebase.firestore.FieldValue.serverTimestamp()
  }).then(function() {
    document.getElementById("um-type").value = "";
    document.getElementById("um-count").value = "";
    document.getElementById("um-sf").value = "";
    document.getElementById("um-rent").value = "";
  }).catch(function(err) { showError("unitmix-error", err.message); });
}

function renderUnitMix() {
  var el = document.getElementById("unitmix-list");
  if (!currentUnitMix.length) { el.innerHTML = "<p class='note'>No unit mix planned yet.</p>"; return; }
  var totalUnits = currentUnitMix.reduce(function(s, u) { return s + Number(u.count || 0); }, 0);
  var totalSF = currentUnitMix.reduce(function(s, u) { return s + Number(u.count || 0) * Number(u.sf || 0); }, 0);
  var totalMonthlyRent = currentUnitMix.reduce(function(s, u) { return s + Number(u.count || 0) * Number(u.rent || 0); }, 0);
  var html = "<div class='table-wrap'><table><tr><th>Type</th><th style='text-align:right;'>Units</th><th style='text-align:right;'>Avg SF</th><th style='text-align:right;'>Total SF</th><th style='text-align:right;'>Avg Rent</th><th></th></tr>";
  currentUnitMix.forEach(function(u) {
    html += "<tr><td>" + u.type + "</td>" +
      "<td style='text-align:right;'>" + u.count + "</td>" +
      "<td style='text-align:right;'>" + Number(u.sf || 0).toLocaleString() + "</td>" +
      "<td style='text-align:right;'>" + (Number(u.count || 0) * Number(u.sf || 0)).toLocaleString() + "</td>" +
      "<td style='text-align:right;'>$" + Number(u.rent || 0).toLocaleString() + "</td>" +
      "<td><button class='secondary' style='margin:0;padding:4px 10px;font-size:11px;' data-um-id='" + u.id + "'>Delete</button></td></tr>";
  });
  html += "<tr style='font-weight:600;'><td>Total</td><td style='text-align:right;'>" + totalUnits +
    "</td><td></td><td style='text-align:right;'>" + totalSF.toLocaleString() +
    "</td><td style='text-align:right;'>$" + totalMonthlyRent.toLocaleString() + "/mo</td><td></td></tr>";
  html += "</table></div>";
  el.innerHTML = html;
  el.querySelectorAll("button[data-um-id]").forEach(function(btn) {
    btn.addEventListener("click", function() {
      db.collection("redevProjects").doc(currentRedevProjectId).collection("unitMix").doc(btn.getAttribute("data-um-id")).delete();
    });
  });
}

function renderBuildableEnvelope() {
  var el = document.getElementById("buildable-envelope");
  if (!el) return;
  var totalLotSize = currentParcels.reduce(function(s, p) { return s + Number(p.lotSize || 0); }, 0);
  if (!totalLotSize) { el.innerHTML = "<span style='font-size:11px;color:#888;'>Add at least one parcel to see the buildable envelope.</span>"; return; }

  var far = currentRedevProjectData.far || 0;
  var maxDensity = currentRedevProjectData.maxDensity || 0;
  var lotCoverage = currentRedevProjectData.lotCoverage || 0;
  var totalAcres = totalLotSize / 43560;

  var html = "<h4 style='font-size:13px;margin:0 0 6px;'>Buildable Envelope</h4><div style='display:flex;flex-wrap:wrap;gap:16px;font-size:13px;'>";
  var maxBuildableSF = 0, maxUnits = 0;
  if (far > 0) {
    maxBuildableSF = far * totalLotSize;
    html += "<div><strong>Max Buildable SF:</strong> " + Math.round(maxBuildableSF).toLocaleString() + "</div>";
  }
  if (maxDensity > 0) {
    maxUnits = Math.floor(totalAcres * maxDensity);
    html += "<div><strong>Max Units (by density):</strong> " + maxUnits.toLocaleString() + "</div>";
  }
  if (lotCoverage > 0) {
    var maxFootprint = (lotCoverage / 100) * totalLotSize;
    html += "<div><strong>Max Building Footprint:</strong> " + Math.round(maxFootprint).toLocaleString() + " sq ft</div>";
  }
  html += "</div>";
  if (!far && !maxDensity) {
    html += "<span style='font-size:11px;color:#888;'>Enter FAR and/or Max Density above to see buildable limits.</span>";
  }

  // Compliance check: compare the planned unit mix against these limits, if both exist
  if (currentUnitMix.length && (maxBuildableSF > 0 || maxUnits > 0)) {
    var plannedUnits = currentUnitMix.reduce(function(s, u) { return s + Number(u.count || 0); }, 0);
    var plannedSF = currentUnitMix.reduce(function(s, u) { return s + Number(u.count || 0) * Number(u.sf || 0); }, 0);
    html += "<h4 style='font-size:13px;margin:12px 0 6px;'>Unit Mix vs. Zoning Limits</h4><div style='display:flex;flex-wrap:wrap;gap:16px;font-size:13px;'>";
    if (maxUnits > 0) {
      var unitsOk = plannedUnits <= maxUnits;
      html += "<div><strong>Units:</strong> " + plannedUnits + " planned / " + maxUnits + " max &nbsp;" +
        "<span style='color:" + (unitsOk ? "#1a8a3d" : "#c0392b") + ";'>" + (unitsOk ? "(within limit)" : "(EXCEEDS LIMIT)") + "</span></div>";
    }
    if (maxBuildableSF > 0) {
      var sfOk = plannedSF <= maxBuildableSF;
      html += "<div><strong>SF:</strong> " + plannedSF.toLocaleString() + " planned / " + Math.round(maxBuildableSF).toLocaleString() + " max &nbsp;" +
        "<span style='color:" + (sfOk ? "#1a8a3d" : "#c0392b") + ";'>" + (sfOk ? "(within limit)" : "(EXCEEDS LIMIT)") + "</span></div>";
    }
    html += "</div>";
  }
  el.innerHTML = html;
}

function renderProForma() {
  var el = document.getElementById("redev-proforma");
  if (!el) return;
  if (!currentUnitMix.length) {
    el.innerHTML = "<span style='font-size:11px;color:#888;'>Add a unit mix plan above to see the redevelopment pro forma.</span>";
    return;
  }

  var d = currentRedevProjectData;
  var totalLandCost = currentParcels.reduce(function(s, p) { return s + Number(p.price || 0); }, 0);
  var plannedSF = currentUnitMix.reduce(function(s, u) { return s + Number(u.count || 0) * Number(u.sf || 0); }, 0);

  var hardCostPerSF = d.hardCostPerSF || 0;
  var softCostPct = (d.softCostPct || 0) / 100;
  var contingencyPct = (d.contingencyPct || 0) / 100;
  var vacancyPct = (d.vacancyPct || 0) / 100;
  var opexPct = (d.opexPct || 0) / 100;
  var exitCapRate = (d.exitCapRate || 0) / 100;

  var hardCosts = plannedSF * hardCostPerSF;
  var softCosts = hardCosts * softCostPct;
  var contingency = (hardCosts + softCosts) * contingencyPct;
  var totalDevCost = totalLandCost + hardCosts + softCosts + contingency;

  var grossPotentialIncome = currentUnitMix.reduce(function(s, u) { return s + Number(u.count || 0) * Number(u.rent || 0) * 12; }, 0);
  var vacancyLoss = grossPotentialIncome * vacancyPct;
  var effectiveGrossIncome = grossPotentialIncome - vacancyLoss;
  var operatingExpenses = effectiveGrossIncome * opexPct;
  var noi = effectiveGrossIncome - operatingExpenses;

  var yieldOnCost = totalDevCost > 0 ? (noi / totalDevCost) * 100 : 0;
  var stabilizedValue = exitCapRate > 0 ? noi / exitCapRate : 0;
  var developmentProfit = stabilizedValue - totalDevCost;
  var developmentMargin = totalDevCost > 0 ? (developmentProfit / totalDevCost) * 100 : 0;
  var spread = exitCapRate > 0 ? yieldOnCost - (exitCapRate * 100) : null;

  var fmt = function(n) { return "$" + Math.round(n).toLocaleString(); };

  var html = "<div class='table-wrap'><table>" +
    "<tr><td>Total Land Cost</td><td style='text-align:right;'>" + fmt(totalLandCost) + "</td></tr>" +
    "<tr><td>Hard Costs (" + fmt(hardCostPerSF) + "/SF &times; " + plannedSF.toLocaleString() + " SF)</td><td style='text-align:right;'>" + fmt(hardCosts) + "</td></tr>" +
    "<tr><td>Soft Costs (" + (softCostPct * 100).toFixed(0) + "% of hard)</td><td style='text-align:right;'>" + fmt(softCosts) + "</td></tr>" +
    "<tr><td>Contingency (" + (contingencyPct * 100).toFixed(0) + "% of hard+soft)</td><td style='text-align:right;'>" + fmt(contingency) + "</td></tr>" +
    "<tr style='font-weight:600;'><td>Total Development Cost</td><td style='text-align:right;'>" + fmt(totalDevCost) + "</td></tr>" +
    "<tr><td colspan='2'>&nbsp;</td></tr>" +
    "<tr><td>Gross Potential Income (annual)</td><td style='text-align:right;'>" + fmt(grossPotentialIncome) + "</td></tr>" +
    "<tr><td>Less: Vacancy (" + (vacancyPct * 100).toFixed(0) + "%)</td><td style='text-align:right;'>-" + fmt(vacancyLoss) + "</td></tr>" +
    "<tr><td>Effective Gross Income</td><td style='text-align:right;'>" + fmt(effectiveGrossIncome) + "</td></tr>" +
    "<tr><td>Operating Expenses (" + (opexPct * 100).toFixed(0) + "% of EGI)</td><td style='text-align:right;'>-" + fmt(operatingExpenses) + "</td></tr>" +
    "<tr style='font-weight:600;'><td>Stabilized NOI</td><td style='text-align:right;'>" + fmt(noi) + "</td></tr>" +
    "</table></div>" +
    "<div style='margin-top:14px;display:flex;flex-wrap:wrap;gap:16px;font-size:13px;'>" +
    "<div><strong>Yield on Cost:</strong> " + yieldOnCost.toFixed(2) + "%</div>" +
    (exitCapRate > 0 ? "<div><strong>Exit Cap Rate:</strong> " + (exitCapRate * 100).toFixed(2) + "%</div>" : "") +
    (spread !== null ? "<div><strong>Spread:</strong> <span style='color:" + (spread >= 1.5 ? "#1a8a3d" : spread >= 0 ? "#a5720b" : "#c0392b") + ";'>" + spread.toFixed(2) + " pts</span></div>" : "") +
    (exitCapRate > 0 ? "<div><strong>Stabilized Value:</strong> " + fmt(stabilizedValue) + "</div>" : "") +
    (exitCapRate > 0 ? "<div><strong>Development Profit:</strong> <span style='color:" + (developmentProfit >= 0 ? "#1a8a3d" : "#c0392b") + ";'>" + fmt(developmentProfit) + " (" + developmentMargin.toFixed(1) + "%)</span></div>" : "") +
    "</div>" +
    "<span style='font-size:11px;color:#888;display:block;margin-top:10px;'>Yield on Cost = Stabilized NOI &divide; Total Development Cost - the standard way developers compare a ground-up/redevelopment project's return against buying a stabilized asset at the market cap rate (the Exit Cap Rate). A spread of 150+ basis points (1.5 points) over the exit cap rate is a common rule-of-thumb minimum to justify development risk versus just buying an existing stabilized property.</span>";

  el.innerHTML = html;
}

document.getElementById("back-to-redev-list").addEventListener("click", function(e) {
  e.preventDefault();
  if (parcelsUnsub) { parcelsUnsub(); parcelsUnsub = null; }
  if (unitMixUnsub) { unitMixUnsub(); unitMixUnsub = null; }
  currentRedevProjectId = null;
  document.getElementById("redev-detail").style.display = "none";
  document.getElementById("redev-list").style.display = "block";
  document.getElementById("redev-list").parentElement.querySelector("h3").style.display = "block";
});

function addParcel() {
  if (!currentRedevProjectId) return;
  var address = document.getElementById("pc-address").value.trim();
  var lotSize = parseFloat(document.getElementById("pc-lotsize").value) || 0;
  var buildingSize = parseFloat(document.getElementById("pc-buildingsize").value) || 0;
  var use = document.getElementById("pc-use").value.trim();
  var price = parseFloat(document.getElementById("pc-price").value) || 0;

  showError("parcel-error", "");
  if (!address) { showError("parcel-error", "Enter an address."); return; }
  if (!lotSize) { showError("parcel-error", "Enter a lot size."); return; }

  db.collection("redevProjects").doc(currentRedevProjectId).collection("parcels").add({
    address: address, lotSize: lotSize, buildingSize: buildingSize, use: use, price: price,
    createdAt: firebase.firestore.FieldValue.serverTimestamp()
  }).then(function() {
    document.getElementById("pc-address").value = "";
    document.getElementById("pc-lotsize").value = "";
    document.getElementById("pc-buildingsize").value = "";
    document.getElementById("pc-use").value = "";
    document.getElementById("pc-price").value = "";
  }).catch(function(err) { showError("parcel-error", err.message); });
}

function renderParcels() {
  var el = document.getElementById("parcel-list");
  if (!currentParcels.length) { el.innerHTML = "<p class='note'>No parcels yet.</p>"; renderRedevSummary(); return; }
  var html = "<div class='table-wrap'><table><tr><th>Address</th><th style='text-align:right;'>Lot Size (SF)</th><th style='text-align:right;'>Existing Bldg (SF)</th><th>Use</th><th style='text-align:right;'>Price</th><th></th></tr>";
  currentParcels.forEach(function(p) {
    html += "<tr><td>" + p.address + "</td>" +
      "<td style='text-align:right;'>" + Number(p.lotSize).toLocaleString() + "</td>" +
      "<td style='text-align:right;'>" + Number(p.buildingSize || 0).toLocaleString() + "</td>" +
      "<td>" + (p.use || "N/A") + "</td>" +
      "<td style='text-align:right;'>$" + Number(p.price || 0).toLocaleString() + "</td>" +
      "<td><button class='secondary' style='margin:0;padding:4px 10px;font-size:11px;' data-pc-id='" + p.id + "'>Delete</button></td></tr>";
  });
  html += "</table></div>";
  el.innerHTML = html;
  el.querySelectorAll("button[data-pc-id]").forEach(function(btn) {
    btn.addEventListener("click", function() {
      db.collection("redevProjects").doc(currentRedevProjectId).collection("parcels").doc(btn.getAttribute("data-pc-id")).delete();
    });
  });
  renderRedevSummary();
}

function renderRedevSummary() {
  var el = document.getElementById("redev-summary");
  var totalLotSize = currentParcels.reduce(function(s, p) { return s + Number(p.lotSize || 0); }, 0);
  var totalBuildingSize = currentParcels.reduce(function(s, p) { return s + Number(p.buildingSize || 0); }, 0);
  var totalPrice = currentParcels.reduce(function(s, p) { return s + Number(p.price || 0); }, 0);
  el.innerHTML = "Parcels: " + currentParcels.length +
    " &middot; Combined lot size: " + totalLotSize.toLocaleString() + " sq ft (" + (totalLotSize / 43560).toFixed(2) + " acres)" +
    " &middot; Existing building total: " + totalBuildingSize.toLocaleString() + " sq ft" +
    " &middot; Total land cost: $" + totalPrice.toLocaleString();
}

var currentPropertyId = null;
var currentPropertyData = {};
var unitsUnsub = null;
var expensesUnsub = null;
var incomeUnsub = null;
var currentUnits = [];
var currentExpenses = [];

function openPropertyDetail(propertyId, address) {
  currentPropertyId = propertyId;
  document.getElementById("property-list").parentElement.querySelector("h3").style.display = "none";
  document.getElementById("property-list").style.display = "none";
  document.getElementById("property-detail").style.display = "block";
  document.getElementById("detail-address").textContent = address;

  db.collection("properties").doc(propertyId).get().then(function(doc) {
    var data = doc.data() || {};
    currentPropertyData = data;
    document.getElementById("fixed-monthly-costs").value = data.fixedMonthlyCosts || 0;
    document.getElementById("d-price").value = data.purchasePrice || "";
    document.getElementById("d-downpayment").value = data.downPayment || "";
    document.getElementById("d-loanamount").value = data.loanAmount || "";
    document.getElementById("d-rate").value = data.interestRate || "";
    document.getElementById("d-term").value = data.loanTermYears || "";
    document.getElementById("d-balloon").value = data.balloonTermYears || "";
    document.getElementById("d-loanstart").value = data.loanStartDate || "";
    document.getElementById("d-interestonly").value = data.interestOnlyYears || "";
    document.getElementById("d-isarm").checked = !!data.isARM;
    document.getElementById("d-armfixed").value = data.armFixedYears || "";
    document.getElementById("d-armresetrate").value = data.armResetRate || "";
    document.getElementById("d-armincrease").value = data.armRateIncreasePerYear || "";
    document.getElementById("d-negam").checked = !!data.isNegativeAmortization;
    toggleARMFields();
    document.getElementById("d-rentgrowth").value = data.rentGrowthRate || "";
    document.getElementById("d-expensegrowth").value = data.expenseGrowthRate || "";
    document.getElementById("d-closingcosts").value = data.closingCostsPct || "";
    document.getElementById("d-exitcaprate").value = data.exitCapRate || "";
    document.getElementById("d-sellingcosts").value = data.sellingCostsPct || "";
    document.getElementById("d-proptax").value = data.annualPropertyTax || "";
    document.getElementById("d-bldgpct").value = data.buildingValuePct || "";
    document.getElementById("d-fedbracket").value = data.federalTaxBracket || "24";
    restoreManagementFeeUI();
    renderKeyRatios();
  });
  document.getElementById("fixed-monthly-costs").onblur = function() {
    var val = parseFloat(this.value) || 0;
    db.collection("properties").doc(currentPropertyId).update({ fixedMonthlyCosts: val });
  };
  document.getElementById("income-statement-month").value = new Date().toISOString().slice(0, 7);

  if (unitsUnsub) unitsUnsub();
  if (expensesUnsub) expensesUnsub();
  if (incomeUnsub) incomeUnsub();

  unitsUnsub = db.collection("properties").doc(propertyId).collection("entries")
    .where("type", "==", "unit").onSnapshot(function(snapshot) {
      currentUnits = [];
      snapshot.forEach(function(doc) { currentUnits.push({ id: doc.id, ...doc.data() }); });
      backfillSortOrder();
      renderUnits();
      renderSummary();
      renderKeyRatios();
      restoreManagementFeeUI();
    });

  expensesUnsub = db.collection("properties").doc(propertyId).collection("entries")
    .where("type", "==", "expense").onSnapshot(function(snapshot) {
      currentExpenses = [];
      snapshot.forEach(function(doc) { currentExpenses.push({ id: doc.id, ...doc.data() }); });
      renderExpenses();
      renderSummary();
      renderKeyRatios();
    });

  incomeUnsub = db.collection("properties").doc(propertyId).collection("entries")
    .where("type", "==", "income").onSnapshot(function(snapshot) {
      currentIncomeEntries = [];
      snapshot.forEach(function(doc) { currentIncomeEntries.push({ id: doc.id, ...doc.data() }); });
      renderIncome();
      renderSummary();
      renderKeyRatios();
    });
}

document.getElementById("back-to-properties").addEventListener("click", function(e) {
  e.preventDefault();
  if (unitsUnsub) { unitsUnsub(); unitsUnsub = null; }
  if (expensesUnsub) { expensesUnsub(); expensesUnsub = null; }
  if (incomeUnsub) { incomeUnsub(); incomeUnsub = null; }
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
  var sf = parseFloat(document.getElementById("u-sf").value) || 0;
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
      sf: sf,
      status: "vacant",
      sortOrder: maxSort + i,
      leaseTermMonths: null,
      moveInDate: "",
      leaseEndDate: "",
      threeDayNoticeDate: "",
      lateFeeAmount: 0,
      gracePeriodDays: 5,
      securityDeposit: 0,
      firstMonthDeposit: 0,
      lastMonthDeposit: 0,
      noDeposit: false,
      tenantName: "",
      tenantPhone: "",
      tenantEmail: "",
      createdAt: firebase.firestore.FieldValue.serverTimestamp()
    });
  }
  batch.commit().then(function() {
    document.getElementById("u-type").value = "";
    document.getElementById("u-count").value = "1";
    document.getElementById("u-rent").value = "";
  }).catch(function(err) { showError("unit-error", err.message); });
}

function backfillSortOrder() {
  var missing = currentUnits.filter(function(u) { return u.sortOrder === undefined || u.sortOrder === null; });
  if (!missing.length) return; // already backfilled - nothing to do, avoids re-writing every time

  var batch = db.batch();
  var nextOrder = currentUnits.reduce(function(max, u) { return Math.max(max, u.sortOrder || 0); }, 0) + 1;
  missing.forEach(function(u) {
    u.sortOrder = nextOrder; // update in-memory too, so this render already reflects it
    batch.update(unitDocRef(u.id), { sortOrder: nextOrder });
    nextOrder++;
  });
  batch.commit();
}

function unitDocRef(unitId) {
  return db.collection("properties").doc(currentPropertyId).collection("entries").doc(unitId);
}

function updateUnitField(unitId, field, value) {
  var update = {};
  update[field] = value;
  unitDocRef(unitId).update(update);
}

function setUnitStatus(unitId, status) {
  updateUnitField(unitId, "status", status);
}

// Backward compatibility: units created before "status" existed only have the old
// occupied (boolean) + leaseType fields - derive an equivalent status from those.
function getUnitStatus(u) {
  if (u.status) return u.status;
  if (u.occupied === false) return "vacant";
  if (u.leaseType === "lease") return "leased";
  return "rental";
}

function reorderUnits(draggedId, dropOnId) {
  if (draggedId === dropOnId) return;
  var sorted = currentUnits.slice().sort(function(a, b) { return (a.sortOrder || 0) - (b.sortOrder || 0); });
  var fromIdx = sorted.findIndex(function(u) { return u.id === draggedId; });
  var toIdx = sorted.findIndex(function(u) { return u.id === dropOnId; });
  if (fromIdx === -1 || toIdx === -1) return;

  var moved = sorted.splice(fromIdx, 1)[0];
  sorted.splice(toIdx, 0, moved);

  // Reassign sortOrder for the whole list based on new position - simpler and more robust
  // than calculating a partial shift, and it's just one batch write either way.
  var batch = db.batch();
  sorted.forEach(function(u, i) {
    u.sortOrder = i + 1;
    batch.update(unitDocRef(u.id), { sortOrder: i + 1 });
  });
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
  updateUnitField(unitId, "leaseTermMonths", parseInt(document.getElementById("term-" + unitId).value, 10) || null);
  updateUnitField(unitId, "leaseEndDate", document.getElementById("le-" + unitId).value);
  updateUnitField(unitId, "threeDayNoticeDate", document.getElementById("tdn-" + unitId).value);
  updateUnitField(unitId, "lateFeeAmount", parseFloat(document.getElementById("lf-" + unitId).value) || 0);
  updateUnitField(unitId, "gracePeriodDays", parseInt(document.getElementById("gp-" + unitId).value, 10) || 0);
  updateUnitField(unitId, "noDeposit", noDeposit);
  updateUnitField(unitId, "securityDeposit", noDeposit ? 0 : (parseFloat(document.getElementById("sd-" + unitId).value) || 0));
  updateUnitField(unitId, "firstMonthDeposit", noDeposit ? 0 : (parseFloat(document.getElementById("fm-" + unitId).value) || 0));
  updateUnitField(unitId, "lastMonthDeposit", noDeposit ? 0 : (parseFloat(document.getElementById("lm-" + unitId).value) || 0));
}

function renderUnits() {
  var el = document.getElementById("unit-list");
  if (!currentUnits.length) { el.innerHTML = "<p class='note'>No units yet.</p>"; return; }
  var sorted = currentUnits.slice().sort(function(a, b) { return (a.sortOrder || 0) - (b.sortOrder || 0); });
  var html = "<div class='table-wrap'><table><tr><th></th><th>Type</th><th>Apartment #</th><th style='text-align:right;'>Rent</th><th style='text-align:right;'>SF</th><th style='text-align:right;'>Rent/SF</th><th>Status</th><th>Tenant Name</th><th>Phone</th><th>Email</th><th>Lease</th><th></th></tr>";
  sorted.forEach(function(u, i) {
    var esc = function(s) { return (s || "").toString().replace(/'/g, "&#39;"); };
    var status = getUnitStatus(u);
    var rentPerSF = (Number(u.sf) > 0) ? (Number(u.rent || 0) / Number(u.sf)).toFixed(2) : "N/A";
    html += "<tr draggable='true' data-unit-row='" + u.id + "'><td style='cursor:grab;text-align:center;color:#999;font-size:16px;'>&#8942;&#8942;</td>" +
      "<td>" + (u.unitType || "N/A") + "</td>" +
      "<td><input type='text' value='" + esc(u.unitNumber !== undefined ? u.unitNumber : u.label) + "' placeholder='e.g. 204' data-field-id='" + u.id + "' data-field='unitNumber' style='width:90px;padding:4px;font-size:12px;'></td>" +
      "<td><input type='number' value='" + Number(u.rent || 0) + "' data-field-id='" + u.id + "' data-field='rent' style='width:80px;padding:4px;font-size:12px;text-align:right;'></td>" +
      "<td><input type='number' value='" + Number(u.sf || 0) + "' data-field-id='" + u.id + "' data-field='sf' style='width:70px;padding:4px;font-size:12px;text-align:right;'></td>" +
      "<td style='text-align:right;'>" + (rentPerSF !== "N/A" ? "$" + rentPerSF : "N/A") + "</td>" +
      "<td><select data-status-id='" + u.id + "' style='padding:4px;font-size:12px;'>" +
        "<option value='rental'" + (status === "rental" ? " selected" : "") + ">Rental</option>" +
        "<option value='leased'" + (status === "leased" ? " selected" : "") + ">Leased</option>" +
        "<option value='eviction'" + (status === "eviction" ? " selected" : "") + ">Eviction</option>" +
        "<option value='vacant'" + (status === "vacant" ? " selected" : "") + ">Vacant</option>" +
      "</select></td>" +
      "<td><input type='text' value='" + esc(u.tenantName) + "' placeholder='Tenant name' data-field-id='" + u.id + "' data-field='tenantName' style='width:120px;padding:4px;font-size:12px;'></td>" +
      "<td><input type='tel' value='" + esc(u.tenantPhone) + "' placeholder='Phone' data-field-id='" + u.id + "' data-field='tenantPhone' style='width:110px;padding:4px;font-size:12px;'></td>" +
      "<td><input type='email' value='" + esc(u.tenantEmail) + "' placeholder='Email' data-field-id='" + u.id + "' data-field='tenantEmail' style='width:150px;padding:4px;font-size:12px;'></td>" +
      "<td><button style='margin:0;padding:4px 8px;font-size:11px;' data-toggle-detail='" + u.id + "'>" + (openDetailPanels[u.id] ? "Hide" : "Details") + "</button></td>" +
      "<td><button class='secondary' style='margin:0;padding:4px 10px;font-size:11px;' data-unit-id='" + u.id + "'>Delete</button></td></tr>";

    if (openDetailPanels[u.id]) {
      html += "<tr><td colspan='12'><div style='background:#f7f6f2;padding:12px;border-radius:6px;'>" +
        "<div style='display:flex;flex-wrap:wrap;gap:14px;'>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>Lease Beginning Date</label><input type='date' id='mi-" + u.id + "' value='" + esc(u.moveInDate) + "' style='padding:6px;font-size:12px;'></div>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>Term (months)</label><input type='number' id='term-" + u.id + "' value='" + (u.leaseTermMonths || "") + "' style='width:70px;padding:6px;font-size:12px;'></div>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>Lease Ending Date</label><input type='date' id='le-" + u.id + "' value='" + esc(u.leaseEndDate) + "' style='padding:6px;font-size:12px;'></div>" +
        (status === "eviction" ? "<div><label style='font-size:11px;color:#c0392b;font-weight:600;display:block;'>Date of 3-Day Notice</label><input type='date' id='tdn-" + u.id + "' value='" + esc(u.threeDayNoticeDate) + "' style='padding:6px;font-size:12px;border:1px solid #c0392b;'></div>" : "<input type='hidden' id='tdn-" + u.id + "' value='" + esc(u.threeDayNoticeDate) + "'>") +
        "</div>" +
        "<div style='margin-top:10px;display:flex;flex-wrap:wrap;gap:14px;align-items:end;'>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>Security Deposit</label><input type='number' id='sd-" + u.id + "' value='" + Number(u.securityDeposit || 0) + "' style='width:90px;padding:6px;font-size:12px;'></div>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>1st Month Collected</label><input type='number' id='fm-" + u.id + "' value='" + Number(u.firstMonthDeposit || 0) + "' style='width:90px;padding:6px;font-size:12px;'></div>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>Last Month Collected</label><input type='number' id='lm-" + u.id + "' value='" + Number(u.lastMonthDeposit || 0) + "' style='width:90px;padding:6px;font-size:12px;'></div>" +
        "<div><label style='font-size:12px;'><input type='checkbox' id='nd-" + u.id + "' " + (u.noDeposit ? "checked" : "") + " style='width:auto;'> No deposit collected</label></div>" +
        "</div>" +
        "<div style='margin-top:10px;display:flex;flex-wrap:wrap;gap:14px;'>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>Late Fee Amount</label><input type='number' id='lf-" + u.id + "' value='" + Number(u.lateFeeAmount || 0) + "' style='width:90px;padding:6px;font-size:12px;'></div>" +
        "<div><label style='font-size:11px;color:#666;display:block;'>Grace Period (days)</label><input type='number' id='gp-" + u.id + "' value='" + (u.gracePeriodDays !== undefined && u.gracePeriodDays !== null ? u.gracePeriodDays : "") + "' style='width:80px;padding:6px;font-size:12px;'></div>" +
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
      var numericFields = ["rent", "sf"];
      var value = numericFields.indexOf(field) !== -1 ? (parseFloat(input.value) || 0) : input.value.trim();
      updateUnitField(input.getAttribute("data-field-id"), field, value);
    });
  });
  el.querySelectorAll("select[data-status-id]").forEach(function(select) {
    select.addEventListener("change", function() {
      setUnitStatus(select.getAttribute("data-status-id"), select.value);
    });
  });
  var draggedUnitId = null;
  el.querySelectorAll("tr[data-unit-row]").forEach(function(row) {
    row.addEventListener("dragstart", function() {
      draggedUnitId = row.getAttribute("data-unit-row");
      row.style.opacity = "0.4";
    });
    row.addEventListener("dragend", function() {
      row.style.opacity = "1";
    });
    row.addEventListener("dragover", function(e) {
      e.preventDefault(); // required to allow dropping
      row.style.borderTop = "2px solid #1f4e79";
    });
    row.addEventListener("dragleave", function() {
      row.style.borderTop = "";
    });
    row.addEventListener("drop", function(e) {
      e.preventDefault();
      row.style.borderTop = "";
      var dropOnId = row.getAttribute("data-unit-row");
      if (draggedUnitId) reorderUnits(draggedUnitId, dropOnId);
    });
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

function toggleCapExFinancing() {
  var isCapEx = document.getElementById("e-capex").checked;
  document.getElementById("capex-financing-fields").style.display = isCapEx ? "block" : "none";
  if (isCapEx && !document.getElementById("e-financed-amount").value) {
    document.getElementById("e-financed-amount").value = document.getElementById("e-amount").value;
  }
}

function addExpense() {
  if (!currentPropertyId) return;
  var category = document.getElementById("e-category").value.trim();
  var amount = parseFloat(document.getElementById("e-amount").value) || 0;
  var date = document.getElementById("e-date").value;
  var isAnnual = document.getElementById("e-annual").checked;
  var isRecurringMonthly = document.getElementById("e-recurring").checked;
  var isCapEx = document.getElementById("e-capex").checked;
  var isFinanced = isCapEx && document.getElementById("e-financed").checked;
  var financedAmount = isFinanced ? (parseFloat(document.getElementById("e-financed-amount").value) || amount) : 0;
  var financedRate = isFinanced ? (parseFloat(document.getElementById("e-financed-rate").value) || 0) : 0;
  var financedTermYears = isFinanced ? (parseFloat(document.getElementById("e-financed-term").value) || 0) : 0;
  showError("expense-error", "");
  if (!category) { showError("expense-error", "Enter a category."); return; }
  if (!date) { showError("expense-error", "Select a date."); return; }
  if (isAnnual && isRecurringMonthly) { showError("expense-error", "Choose either Annual or Recurring Monthly, not both."); return; }

  db.collection("properties").doc(currentPropertyId).collection("entries").add({
    type: "expense", category: category, amount: amount, date: date, isAnnual: isAnnual,
    isRecurringMonthly: isRecurringMonthly, isCapEx: isCapEx,
    isFinanced: isFinanced, financedAmount: financedAmount, financedRate: financedRate, financedTermYears: financedTermYears,
    createdAt: firebase.firestore.FieldValue.serverTimestamp()
  }).then(function() {
    document.getElementById("e-category").value = "";
    document.getElementById("e-amount").value = "";
    document.getElementById("e-date").value = "";
    document.getElementById("e-annual").checked = false;
    document.getElementById("e-recurring").checked = false;
    document.getElementById("e-capex").checked = false;
    document.getElementById("e-financed").checked = false;
    document.getElementById("e-financed-amount").value = "";
    document.getElementById("e-financed-rate").value = "";
    document.getElementById("e-financed-term").value = "";
    document.getElementById("capex-financing-fields").style.display = "none";
  }).catch(function(err) { showError("expense-error", err.message); });
}

var currentIncomeEntries = [];

function addIncome() {
  if (!currentPropertyId) return;
  var category = document.getElementById("i-category").value.trim();
  var amount = parseFloat(document.getElementById("i-amount").value) || 0;
  var date = document.getElementById("i-date").value;
  var isAnnual = document.getElementById("i-annual").checked;
  showError("income-error", "");
  if (!category) { showError("income-error", "Enter a category."); return; }
  if (!date) { showError("income-error", "Select a date."); return; }

  db.collection("properties").doc(currentPropertyId).collection("entries").add({
    type: "income", category: category, amount: amount, date: date, isAnnual: isAnnual,
    createdAt: firebase.firestore.FieldValue.serverTimestamp()
  }).then(function() {
    document.getElementById("i-category").value = "";
    document.getElementById("i-amount").value = "";
    document.getElementById("i-date").value = "";
    document.getElementById("i-annual").checked = false;
  }).catch(function(err) { showError("income-error", err.message); });
}

function updateIncomeField(incomeId, field, value) {
  var update = {};
  update[field] = value;
  db.collection("properties").doc(currentPropertyId).collection("entries").doc(incomeId).update(update);
}

function renderIncome() {
  var el = document.getElementById("income-list");
  if (!currentIncomeEntries.length) { el.innerHTML = "<p class='note'>No other income logged yet.</p>"; return; }
  var sorted = currentIncomeEntries.slice().sort(function(a, b) { return (b.date || "").localeCompare(a.date || ""); });
  var esc = function(s) { return (s || "").toString().replace(/'/g, "&#39;"); };
  var html = "<div class='table-wrap'><table><tr><th>Date</th><th>Category</th><th style='text-align:right;'>Amount</th><th>Annual</th><th></th></tr>";
  sorted.forEach(function(inc) {
    html += "<tr>" +
      "<td><input type='date' value='" + esc(inc.date) + "' data-inc-field-id='" + inc.id + "' data-inc-field='date' style='width:130px;padding:4px;font-size:12px;'></td>" +
      "<td><input type='text' value='" + esc(inc.category) + "' data-inc-field-id='" + inc.id + "' data-inc-field='category' style='width:160px;padding:4px;font-size:12px;'></td>" +
      "<td><input type='number' value='" + Number(inc.amount || 0) + "' data-inc-field-id='" + inc.id + "' data-inc-field='amount' style='width:90px;padding:4px;font-size:12px;text-align:right;'></td>" +
      "<td style='text-align:center;'><input type='checkbox' data-inc-annual-id='" + inc.id + "' " + (inc.isAnnual ? "checked" : "") + " style='width:auto;'></td>" +
      "<td><button class='secondary' style='margin:0;padding:4px 10px;font-size:11px;' data-inc-id='" + inc.id + "'>Delete</button></td></tr>";
  });
  html += "</table></div>";
  el.innerHTML = html;
  el.querySelectorAll("input[data-inc-field]").forEach(function(input) {
    input.addEventListener("blur", function() {
      var field = input.getAttribute("data-inc-field");
      var value = field === "amount" ? (parseFloat(input.value) || 0) : input.value.trim();
      updateIncomeField(input.getAttribute("data-inc-field-id"), field, value);
    });
  });
  el.querySelectorAll("input[data-inc-annual-id]").forEach(function(input) {
    input.addEventListener("change", function() {
      updateIncomeField(input.getAttribute("data-inc-annual-id"), "isAnnual", input.checked);
    });
  });
  el.querySelectorAll("button[data-inc-id]").forEach(function(btn) {
    btn.addEventListener("click", function() {
      db.collection("properties").doc(currentPropertyId).collection("entries").doc(btn.getAttribute("data-inc-id")).delete();
    });
  });
}

function updateExpenseField(expenseId, field, value) {
  var update = {};
  update[field] = value;
  db.collection("properties").doc(currentPropertyId).collection("entries").doc(expenseId).update(update);
}

function renderExpenses() {
  var el = document.getElementById("expense-list");
  if (!currentExpenses.length) { el.innerHTML = "<p class='note'>No expenses logged yet.</p>"; return; }
  var sorted = currentExpenses.slice().sort(function(a, b) { return (b.date || "").localeCompare(a.date || ""); });
  var esc = function(s) { return (s || "").toString().replace(/'/g, "&#39;"); };
  var html = "<div class='table-wrap'><table><tr><th>Date</th><th>Category</th><th style='text-align:right;'>Amount</th><th>Annual</th><th>Recurring Monthly</th><th></th></tr>";
  sorted.forEach(function(e) {
    html += "<tr>" +
      "<td><input type='date' value='" + esc(e.date) + "' data-exp-field-id='" + e.id + "' data-exp-field='date' style='width:130px;padding:4px;font-size:12px;'></td>" +
      "<td><input type='text' value='" + esc(e.category) + "' data-exp-field-id='" + e.id + "' data-exp-field='category' style='width:160px;padding:4px;font-size:12px;'></td>" +
      "<td><input type='number' value='" + Number(e.amount || 0) + "' data-exp-field-id='" + e.id + "' data-exp-field='amount' style='width:90px;padding:4px;font-size:12px;text-align:right;'></td>" +
      "<td style='text-align:center;'><input type='checkbox' data-exp-annual-id='" + e.id + "' " + (e.isAnnual ? "checked" : "") + " style='width:auto;'></td>" +
      "<td style='text-align:center;'><input type='checkbox' data-exp-recurring-id='" + e.id + "' " + (e.isRecurringMonthly ? "checked" : "") + " style='width:auto;'></td>" +
      "<td><button class='secondary' style='margin:0;padding:4px 10px;font-size:11px;' data-exp-id='" + e.id + "'>Delete</button></td></tr>";
  });
  html += "</table></div>";
  el.innerHTML = html;
  el.querySelectorAll("input[data-exp-field]").forEach(function(input) {
    input.addEventListener("blur", function() {
      var field = input.getAttribute("data-exp-field");
      var value = field === "amount" ? (parseFloat(input.value) || 0) : input.value.trim();
      updateExpenseField(input.getAttribute("data-exp-field-id"), field, value);
    });
  });
  el.querySelectorAll("input[data-exp-annual-id]").forEach(function(input) {
    input.addEventListener("change", function() {
      updateExpenseField(input.getAttribute("data-exp-annual-id"), "isAnnual", input.checked);
      if (input.checked) updateExpenseField(input.getAttribute("data-exp-annual-id"), "isRecurringMonthly", false);
    });
  });
  el.querySelectorAll("input[data-exp-recurring-id]").forEach(function(input) {
    input.addEventListener("change", function() {
      updateExpenseField(input.getAttribute("data-exp-recurring-id"), "isRecurringMonthly", input.checked);
      if (input.checked) updateExpenseField(input.getAttribute("data-exp-recurring-id"), "isAnnual", false);
    });
  });
  el.querySelectorAll("button[data-exp-id]").forEach(function(btn) {
    btn.addEventListener("click", function() {
      db.collection("properties").doc(currentPropertyId).collection("entries").doc(btn.getAttribute("data-exp-id")).delete();
    });
  });
}

function restoreManagementFeeUI() {
  var d = currentPropertyData;
  document.getElementById("mgmt-type").value = d.managementFeeType || "none";
  document.getElementById("mgmt-flat-amount").value = d.managementFeeFlat || "";
  document.getElementById("mgmt-pct-amount").value = d.managementFeePct || "";
  onManagementTypeChange(); // shows the right sub-fields and populates the unit dropdown from currentUnits
  if (d.managementFeeUnitId) {
    var sel = document.getElementById("mgmt-unit");
    if (sel.querySelector("option[value='" + d.managementFeeUnitId + "']")) {
      sel.value = d.managementFeeUnitId;
    }
  }
}

function toggleManagementForm() {
  var form = document.getElementById("management-form");
  var icon = document.getElementById("management-toggle-icon");
  var isHidden = form.style.display === "none";
  form.style.display = isHidden ? "block" : "none";
  icon.innerHTML = isHidden ? "&#9662;" : "&#9656;";
}

function onManagementTypeChange() {
  var type = document.getElementById("mgmt-type").value;
  document.getElementById("mgmt-flat-fields").style.display = type === "flat" ? "block" : "none";
  document.getElementById("mgmt-freeapt-fields").style.display = type === "freeApartment" ? "block" : "none";
  document.getElementById("mgmt-pct-fields").style.display = type === "percentage" ? "block" : "none";

  if (type === "freeApartment") {
    var sel = document.getElementById("mgmt-unit");
    var currentValue = sel.value;
    sel.innerHTML = currentUnits.map(function(u) {
      var label = (u.unitNumber || u.label || u.unitType || "Unit") + " ($" + Number(u.rent || 0).toLocaleString() + "/mo)";
      return "<option value='" + u.id + "'>" + label + "</option>";
    }).join("");
    if (currentValue) sel.value = currentValue;
  }
}

function saveManagementFee() {
  if (!currentPropertyId) return;
  var updates = {
    managementFeeType: document.getElementById("mgmt-type").value,
    managementFeeFlat: parseFloat(document.getElementById("mgmt-flat-amount").value) || 0,
    managementFeePct: parseFloat(document.getElementById("mgmt-pct-amount").value) || 0,
    managementFeeUnitId: document.getElementById("mgmt-unit").value || ""
  };
  var statusEl = document.getElementById("management-save-status");
  statusEl.textContent = "Saving...";
  statusEl.style.color = "#888";
  db.collection("properties").doc(currentPropertyId).update(updates).then(function() {
    currentPropertyData = Object.assign({}, currentPropertyData, updates);
    return syncManagementFeeExpenseEntry();
  }).then(function() {
    renderSummary();
    renderKeyRatios();
    statusEl.textContent = "Saved.";
    statusEl.style.color = "#1a8a3d";
    setTimeout(function() { statusEl.textContent = ""; }, 3000);
  }).catch(function(err) {
    statusEl.textContent = "Error: " + err.message;
    statusEl.style.color = "#c0392b";
  });
}

// Keeps a real, visible expense entry in sync with the management fee settings, so it shows
// up in the Expenses list like any other expense (editable, deletable, included in reports),
// rather than only existing as a background calculation. Finds the existing entry (marked
// isManagementFeeEntry) if one exists, and creates, updates, or removes it as needed.
function syncManagementFeeExpenseEntry() {
  var mgmtFee = getMonthlyManagementFee();
  var existing = currentExpenses.find(function(e) { return e.isManagementFeeEntry; });

  if (!mgmtFee.amount) {
    // Self-managed, or fee dropped to $0 - remove any existing synced entry
    if (existing) {
      return db.collection("properties").doc(currentPropertyId).collection("entries").doc(existing.id).delete();
    }
    return Promise.resolve();
  }

  if (existing) {
    return db.collection("properties").doc(currentPropertyId).collection("entries").doc(existing.id).update({
      amount: mgmtFee.amount
    });
  }

  return db.collection("properties").doc(currentPropertyId).collection("entries").add({
    type: "expense", category: "Management Fee", amount: mgmtFee.amount,
    date: new Date().toISOString().slice(0, 10), isAnnual: false, isRecurringMonthly: true,
    isCapEx: false, isManagementFeeEntry: true,
    createdAt: firebase.firestore.FieldValue.serverTimestamp()
  });
}

// Computes the actual monthly $ value of the management fee, and (for the Free Apartment
// case) which unit's rent should be excluded from income since it's not actually collected.
function getMonthlyManagementFee() {
  var type = currentPropertyData.managementFeeType || "none";
  var occupiedUnits = currentUnits.filter(function(u) { return getUnitStatus(u) !== "vacant"; });
  var totalMonthlyRent = occupiedUnits.reduce(function(s, u) { return s + Number(u.rent || 0); }, 0);

  if (type === "flat") {
    return { amount: currentPropertyData.managementFeeFlat || 0, excludedUnitId: null };
  }
  if (type === "freeApartment") {
    var unit = currentUnits.find(function(u) { return u.id === currentPropertyData.managementFeeUnitId; });
    return { amount: unit ? Number(unit.rent || 0) : 0, excludedUnitId: currentPropertyData.managementFeeUnitId || null };
  }
  if (type === "percentage") {
    var pct = (currentPropertyData.managementFeePct || 0) / 100;
    return { amount: totalMonthlyRent * pct, excludedUnitId: null };
  }
  return { amount: 0, excludedUnitId: null }; // self-managed
}

function toggleARMFields() {
  document.getElementById("arm-fields").style.display = document.getElementById("d-isarm").checked ? "block" : "none";
}

function toggleFinancingForm() {
  var form = document.getElementById("financing-form");
  var icon = document.getElementById("financing-toggle-icon");
  var isHidden = form.style.display === "none";
  form.style.display = isHidden ? "block" : "none";
  icon.innerHTML = isHidden ? "&#9662;" : "&#9656;";
}

function saveFinancingDetails() {
  if (!currentPropertyId) return;
  var updates = {
    purchasePrice: parseFloat(document.getElementById("d-price").value) || null,
    downPayment: parseFloat(document.getElementById("d-downpayment").value) || 0,
    loanAmount: parseFloat(document.getElementById("d-loanamount").value) || 0,
    interestRate: parseFloat(document.getElementById("d-rate").value) || 0,
    loanTermYears: parseFloat(document.getElementById("d-term").value) || 0,
    balloonTermYears: parseFloat(document.getElementById("d-balloon").value) || 0,
    loanStartDate: document.getElementById("d-loanstart").value || "",
    interestOnlyYears: Math.max(0, parseFloat(document.getElementById("d-interestonly").value) || 0),
    isARM: document.getElementById("d-isarm").checked,
    armFixedYears: Math.max(0, parseFloat(document.getElementById("d-armfixed").value) || 0),
    armResetRate: parseFloat(document.getElementById("d-armresetrate").value) || 0,
    armRateIncreasePerYear: parseFloat(document.getElementById("d-armincrease").value) || 0,
    isNegativeAmortization: document.getElementById("d-negam").checked,
    rentGrowthRate: parseFloat(document.getElementById("d-rentgrowth").value) || 0,
    expenseGrowthRate: parseFloat(document.getElementById("d-expensegrowth").value) || 0,
    closingCostsPct: parseFloat(document.getElementById("d-closingcosts").value) || 0,
    exitCapRate: parseFloat(document.getElementById("d-exitcaprate").value) || 0,
    sellingCostsPct: parseFloat(document.getElementById("d-sellingcosts").value) || 0,
    annualPropertyTax: parseFloat(document.getElementById("d-proptax").value) || 0,
    buildingValuePct: parseFloat(document.getElementById("d-bldgpct").value) || 0,
    federalTaxBracket: parseFloat(document.getElementById("d-fedbracket").value) || 0
  };
  var statusEl = document.getElementById("financing-save-status");
  statusEl.textContent = "Saving...";
  statusEl.style.color = "#888";
  db.collection("properties").doc(currentPropertyId).update(updates).then(function() {
    currentPropertyData = Object.assign({}, currentPropertyData, updates);
    renderKeyRatios();
    statusEl.textContent = "Saved.";
    statusEl.style.color = "#1a8a3d";
    setTimeout(function() { statusEl.textContent = ""; }, 3000);
  }).catch(function(err) {
    statusEl.textContent = "Error saving: " + err.message;
    statusEl.style.color = "#c0392b";
  });
}

__STATE_TAX_JS_HELPER__
function renderKeyRatios() {
  var el = document.getElementById("key-ratios");
  var purchasePrice = currentPropertyData.purchasePrice;
  if (!purchasePrice) {
    el.innerHTML = "<span style='font-size:11px;color:#888;'>Enter a purchase price under Financing Details below to see Cap Rate, DSCR, and other key ratios.</span>";
    return;
  }

  var mgmtFee = getMonthlyManagementFee();
  var occupiedUnits = currentUnits.filter(function(u) { return getUnitStatus(u) !== "vacant" && u.id !== mgmtFee.excludedUnitId; });
  var totalMonthlyRent = occupiedUnits.reduce(function(sum, u) { return sum + Number(u.rent || 0); }, 0);
  var grossScheduledIncome = currentUnits.reduce(function(sum, u) { return sum + Number(u.rent || 0); }, 0);

  var now = new Date();
  var manualFixedCosts = parseFloat((document.getElementById("fixed-monthly-costs") || {}).value) || 0;
  var operatingExpenses = currentExpenses.filter(function(e) { return !e.isCapEx; });
  var effective = getEffectiveMonthlyExpenses(operatingExpenses, now.getFullYear(), now.getMonth());
  var autoFixedFromAnnual = effective.fixedFromAnnual.reduce(function(sum, e) { return sum + e.amount; }, 0);
  var totalVariableThisMonth = effective.variable.reduce(function(sum, e) { return sum + e.amount; }, 0);
  var totalMonthlyOpEx = manualFixedCosts + autoFixedFromAnnual + totalVariableThisMonth;

  var effectiveIncome = getEffectiveMonthlyExpenses(currentIncomeEntries, now.getFullYear(), now.getMonth());
  var totalOtherIncomeThisMonth = effectiveIncome.fixedFromAnnual.reduce(function(sum, e) { return sum + e.amount; }, 0) +
    effectiveIncome.variable.reduce(function(sum, e) { return sum + e.amount; }, 0);
  var totalMonthlyIncome = totalMonthlyRent + totalOtherIncomeThisMonth;

  var annualNOI = (totalMonthlyIncome - totalMonthlyOpEx) * 12;
  var capRate = (annualNOI / purchasePrice) * 100;

  var loanAmount = currentPropertyData.loanAmount || 0;
  var interestRate = currentPropertyData.interestRate || 0;
  var loanTermYears = currentPropertyData.loanTermYears || 0;
  var interestOnlyYears = currentPropertyData.interestOnlyYears || 0;
  var downPayment = currentPropertyData.downPayment || 0;
  var monthsElapsed = getMonthsElapsedSinceLoanStart(currentPropertyData.loanStartDate, now.getFullYear(), now.getMonth());
  var monthlyMortgagePayment = calculateMonthlyDebtService(loanAmount, interestRate, loanTermYears, interestOnlyYears, monthsElapsed);

  var capExExpenses = currentExpenses.filter(function(e) { return e.isCapEx; });
  var activeCapExFinancing = getCapExFinancingForMonth(capExExpenses, now.getFullYear(), now.getMonth());
  var monthlyCapExFinancing = activeCapExFinancing.reduce(function(sum, item) { return sum + item.amount; }, 0);

  var monthlyDebtService = monthlyMortgagePayment + monthlyCapExFinancing;
  var annualDebtService = monthlyDebtService * 12;

  var expenseRatio = totalMonthlyIncome > 0 ? (totalMonthlyOpEx * 12) / (totalMonthlyIncome * 12) * 100 : 0;
  var grm = grossScheduledIncome > 0 ? purchasePrice / (grossScheduledIncome * 12) : 0;
  var ltv = loanAmount > 0 && purchasePrice > 0 ? (loanAmount / purchasePrice) * 100 : null;
  var debtYield = loanAmount > 0 ? (annualNOI / loanAmount) * 100 : null;

  // Equity Growth: how much of the loan balance gets paid down over the next 12 months from
  // today - reuses the same tested IO-aware balance calculation, just called twice.
  var annualPrincipalPaydown = null;
  if (loanAmount > 0) {
    var balanceNow = calculateRemainingBalanceWithIO(loanAmount, interestRate, loanTermYears, interestOnlyYears, monthsElapsed);
    var balanceIn12Months = calculateRemainingBalanceWithIO(loanAmount, interestRate, loanTermYears, interestOnlyYears, monthsElapsed + 12);
    annualPrincipalPaydown = balanceNow - balanceIn12Months;
  }

  var html = "<h4 style='font-size:13px;margin:0 0 6px;'>Key Financial Ratios</h4>" +
    "<div style='display:flex;flex-wrap:wrap;gap:16px;font-size:13px;'>" +
    "<div><strong>Cap Rate:</strong> " + capRate.toFixed(2) + "%</div>" +
    "<div><strong>Expense Ratio:</strong> " + expenseRatio.toFixed(1) + "%</div>" +
    "<div><strong>GRM:</strong> " + (grm ? grm.toFixed(2) : "N/A") + "</div>";

  if (loanAmount > 0 || monthlyCapExFinancing > 0) {
    var dscr = annualDebtService > 0 ? annualNOI / annualDebtService : 0;
    var annualCashFlowAfterDebt = annualNOI - annualDebtService;
    var cashOnCash = downPayment > 0 ? (annualCashFlowAfterDebt / downPayment) * 100 : null;
    html += "<div><strong>Monthly Debt Service:</strong> $" + monthlyDebtService.toLocaleString(undefined, {maximumFractionDigits: 0}) +
      (monthlyCapExFinancing > 0 ? " <span style='font-size:11px;color:#888;'>(incl. $" + monthlyCapExFinancing.toLocaleString(undefined, {maximumFractionDigits: 0}) + " financed CapEx)</span>" : "") + "</div>" +
      "<div><strong>DSCR:</strong> " + dscr.toFixed(2) + (dscr < 1.25 ? " <span style='color:#c0392b;'>(below typical 1.25 lender minimum)</span>" : "") + "</div>" +
      (cashOnCash !== null ? "<div><strong>Cash-on-Cash Return:</strong> " + cashOnCash.toFixed(2) + "%</div>" : "") +
      (ltv !== null ? "<div><strong>LTV:</strong> " + ltv.toFixed(1) + "%" + (ltv > 75 ? " <span style='color:#c0392b;'>(above typical 75% lender max)</span>" : "") + "</div>" : "") +
      (debtYield !== null ? "<div><strong>Debt Yield:</strong> " + debtYield.toFixed(2) + "%" + (debtYield < 8 ? " <span style='color:#c0392b;'>(below typical 8% lender minimum)</span>" : "") + "</div>" : "") +
      (annualPrincipalPaydown !== null ? "<div><strong>Equity Growth (next 12mo):</strong> $" + annualPrincipalPaydown.toLocaleString(undefined, {maximumFractionDigits: 0}) + " principal paydown" + (annualPrincipalPaydown === 0 ? " <span style='font-size:11px;color:#888;'>(interest-only - no paydown yet)</span>" : "") + "</div>" : "");
  }

  var balloonTermYears = currentPropertyData.balloonTermYears || 0;
  var loanStartDate = currentPropertyData.loanStartDate || "";
  if (loanAmount > 0 && balloonTermYears > 0 && loanStartDate) {
    var startYear = parseInt(loanStartDate.slice(0, 4), 10);
    var startMonthIdx = parseInt(loanStartDate.slice(5, 7), 10) - 1;
    var startLinearMonth = startYear * 12 + startMonthIdx;
    var paymentsMade = monthsElapsed;
    var remainingBalance = calculateRemainingBalanceWithIO(loanAmount, interestRate, loanTermYears, interestOnlyYears, paymentsMade);
    var balloonDueLinearMonth = startLinearMonth + Math.round(balloonTermYears * 12);
    var balloonDueYear = Math.floor(balloonDueLinearMonth / 12);
    var balloonDueMonth = (balloonDueLinearMonth % 12) + 1;
    var monthsUntilBalloon = balloonDueLinearMonth - (startLinearMonth + monthsElapsed);
    html += "</div><div style='margin-top:10px;padding:10px;background:#fef3c7;border-radius:6px;font-size:13px;'>" +
      "<strong>Balloon Payment Due:</strong> $" + remainingBalance.toLocaleString(undefined, {maximumFractionDigits: 0}) +
      " (remaining principal) due " + balloonDueMonth + "/" + balloonDueYear +
      (monthsUntilBalloon > 0 ? " (" + monthsUntilBalloon + " months from now)" : " <span style='color:#c0392b;'>(past due or due now - refinance or payoff needed)</span>") +
      "</div>";
  } else {
    html += "</div>";
  }

  // --- Estimated income tax savings (depreciation + mortgage interest + property tax) ---
  var annualPropertyTaxForSavings = currentPropertyData.annualPropertyTax || 0;
  var buildingValuePct = currentPropertyData.buildingValuePct || 0;
  var federalTaxBracket = currentPropertyData.federalTaxBracket || 0;
  var stateRatePctForSavings = getStateTopMarginalRate(currentPropertyData.state) || 0;
  if (buildingValuePct > 0 && (federalTaxBracket > 0 || stateRatePctForSavings > 0)) {
    var depreciationLife = (currentPropertyData.units || 1) >= 5 ? 39 : 27.5;
    var buildingValue = purchasePrice * (buildingValuePct / 100);
    var annualDepreciation = buildingValue / depreciationLife;

    var annualInterestForSavings = 0;
    if (loanAmount > 0) {
      var balanceStartOfYear = calculateRemainingBalanceWithIO(loanAmount, interestRate, loanTermYears, interestOnlyYears, Math.max(0, monthsElapsed - 12));
      var balanceEndOfYear = calculateRemainingBalanceWithIO(loanAmount, interestRate, loanTermYears, interestOnlyYears, monthsElapsed);
      var principalReductionForSavings = balanceStartOfYear - balanceEndOfYear;
      annualInterestForSavings = Math.max(0, annualDebtService - principalReductionForSavings);
    }

    var totalTaxDeductions = annualDepreciation + annualInterestForSavings + annualPropertyTaxForSavings;
    var combinedRatePctForSavings = federalTaxBracket + stateRatePctForSavings;
    var estTaxSavings = totalTaxDeductions * (combinedRatePctForSavings / 100);

    html += "<div style='margin-top:10px;padding:10px;background:#eef6f0;border-radius:6px;font-size:13px;'>" +
      "<strong>Estimated Annual Income Tax Savings:</strong> $" + estTaxSavings.toLocaleString(undefined, {maximumFractionDigits: 0}) + "/yr" +
      " ($" + (estTaxSavings/12).toLocaleString(undefined, {maximumFractionDigits: 0}) + "/mo)<br>" +
      "<span style='font-size:11px;color:#888;'>Depreciation (" + depreciationLife + "-yr, " + buildingValuePct + "% building value of $" + purchasePrice.toLocaleString() + "): $" + annualDepreciation.toLocaleString(undefined, {maximumFractionDigits: 0}) + "/yr &middot; " +
      "Mortgage interest: $" + annualInterestForSavings.toLocaleString(undefined, {maximumFractionDigits: 0}) + "/yr &middot; " +
      "Property tax: $" + annualPropertyTaxForSavings.toLocaleString(undefined, {maximumFractionDigits: 0}) + "/yr &middot; " +
      "Combined rate (federal " + federalTaxBracket + "% + state " + stateRatePctForSavings.toFixed(2) + "%): " + combinedRatePctForSavings.toFixed(2) + "%<br>" +
      "Estimate only, not tax advice. Assumes these losses are fully deductible against ordinary income - IRS passive activity loss rules (Section 469) can limit or defer this unless you qualify as a real estate professional or the property's income is low enough for the $25,000 active-participation allowance (phased out $100,000-$150,000 MAGI). Depreciation is generally recaptured (taxed up to 25% federal) when you sell. State rate is that state's top marginal individual rate (from the property's State field above), not an income-specific calculation, and excludes local/county taxes. Consult a CPA before relying on this for a purchase decision.</span>" +
      "</div>";
  }

  // Lending-target comparison table - shows how the property's metrics stack up against
  // typical commercial underwriting guidelines. Cap Rate has no universal target (it's
  // market/property-type dependent), so it's shown for reference without a pass/fail mark.
  if (loanAmount > 0) {
    var occupancyPct = currentUnits.length > 0 ? (occupiedUnits.length / currentUnits.length) * 100 : null;
    var vacancyPct = occupancyPct !== null ? 100 - occupancyPct : null;
    var checks = [
      { label: "Loan-to-Value", value: ltv, fmt: "%", target: "&le; 75%", pass: ltv !== null ? ltv <= 75 : null },
      { label: "DSCR", value: dscr, fmt: "", target: "&ge; 1.25", pass: dscr > 0 ? dscr >= 1.25 : null },
      { label: "Cap Rate", value: capRate, fmt: "%", target: "Market dependent", pass: null },
      { label: "Debt Yield", value: debtYield, fmt: "%", target: "&ge; 8%", pass: debtYield !== null ? debtYield >= 8 : null },
      { label: "Occupancy", value: occupancyPct, fmt: "%", target: "&ge; 90%", pass: occupancyPct !== null ? occupancyPct >= 90 : null },
      { label: "Vacancy", value: vacancyPct, fmt: "%", target: "&le; 10%", pass: vacancyPct !== null ? vacancyPct <= 10 : null }
    ];
    html += "<h4 style='font-size:13px;margin:14px 0 6px;'>Lending Guideline Comparison</h4>" +
      "<div class='table-wrap'><table><tr><th>Metric</th><th style='text-align:right;'>Property</th><th>Typical Target</th><th>Status</th></tr>";
    checks.forEach(function(c) {
      var valStr = c.value === null ? "N/A" : c.value.toFixed(2) + c.fmt;
      var statusStr = c.pass === null ? "&mdash;" : (c.pass ? "<span style='color:#1a8a3d;'>&#10003;</span>" : "<span style='color:#c0392b;'>&#10007;</span>");
      html += "<tr><td>" + c.label + "</td><td style='text-align:right;'>" + valStr + "</td><td>" + c.target + "</td><td>" + statusStr + "</td></tr>";
    });
    html += "</table></div>";
  }

  html += "<span style='font-size:11px;color:#888;'>Based on this month's rent and expenses, annualized. Cap Rate and Expense Ratio don't depend on financing; DSCR and Cash-on-Cash require loan details under Financing Details.</span>";
  el.innerHTML = html;
}

function renderSummary() {
  var mgmtFee = getMonthlyManagementFee();
  var occupiedUnits = currentUnits.filter(function(u) { return getUnitStatus(u) !== "vacant" && u.id !== mgmtFee.excludedUnitId; });
  var totalMonthlyRent = occupiedUnits.reduce(function(sum, u) { return sum + Number(u.rent || 0); }, 0);
  var vacantCount = currentUnits.length - occupiedUnits.length - (mgmtFee.excludedUnitId ? 1 : 0);

  var now = new Date();
  var thisYear = now.getFullYear();
  var thisMonthIdx = now.getMonth();
  var manualFixedCosts = parseFloat((document.getElementById("fixed-monthly-costs") || {}).value) || 0;

  // CapEx (capital improvements) is tracked separately - it's not an operating expense and
  // shouldn't reduce NOI/cash flow the way routine repairs do.
  var operatingExpenses = currentExpenses.filter(function(e) { return !e.isCapEx; });
  var capExExpenses = currentExpenses.filter(function(e) { return e.isCapEx; });
  var totalCapExThisMonth = capExExpenses.filter(function(e) { return (e.date || "").slice(0, 7) === (thisYear + "-" + String(thisMonthIdx + 1).padStart(2, "0")); })
    .reduce(function(sum, e) { return sum + Number(e.amount || 0); }, 0);
  var totalAllCapEx = capExExpenses.reduce(function(sum, e) { return sum + Number(e.amount || 0); }, 0);

  var effective = getEffectiveMonthlyExpenses(operatingExpenses, thisYear, thisMonthIdx);
  var autoFixedFromAnnual = effective.fixedFromAnnual.reduce(function(sum, e) { return sum + e.amount; }, 0);
  var totalFixedThisMonth = manualFixedCosts + autoFixedFromAnnual;
  var totalVariableThisMonth = effective.variable.reduce(function(sum, e) { return sum + e.amount; }, 0);
  var totalThisMonthExpenses = totalFixedThisMonth + totalVariableThisMonth;
  var totalAllExpenses = operatingExpenses.reduce(function(sum, e) { return sum + Number(e.amount || 0); }, 0);

  var effectiveIncome = getEffectiveMonthlyExpenses(currentIncomeEntries, thisYear, thisMonthIdx);
  var totalOtherIncomeThisMonth = effectiveIncome.fixedFromAnnual.reduce(function(sum, e) { return sum + e.amount; }, 0) +
    effectiveIncome.variable.reduce(function(sum, e) { return sum + e.amount; }, 0);
  var totalMonthlyIncome = totalMonthlyRent + totalOtherIncomeThisMonth;

  var cashFlow = totalMonthlyIncome - totalThisMonthExpenses;
  var cashFlowColor = cashFlow >= 0 ? "#1a8a3d" : "#c0392b";

  var vacantUnits = currentUnits.filter(function(u) { return getUnitStatus(u) === "vacant"; });
  var vacantWithZeroRent = vacantUnits.filter(function(u) { return !Number(u.rent); });
  var zeroRentWarning = vacantWithZeroRent.length
    ? "<div style='margin-top:8px;padding:8px;background:#fef3c7;border-radius:6px;font-size:12px;color:#78350f;'>" +
      vacantWithZeroRent.length + " vacant unit(s) have a Rent field of $0 - this understates Vacancy Loss on your reports. " +
      "Enter the market rent that unit would charge if occupied, not $0.</div>"
    : "";

  var occupiedWithSF = occupiedUnits.filter(function(u) { return Number(u.sf) > 0; });
  var totalOccupiedSF = occupiedWithSF.reduce(function(s, u) { return s + Number(u.sf); }, 0);
  var totalOccupiedRentForSF = occupiedWithSF.reduce(function(s, u) { return s + Number(u.rent || 0); }, 0);
  var avgRentPerSF = totalOccupiedSF > 0 ? (totalOccupiedRentForSF / totalOccupiedSF) : null;

  document.getElementById("detail-summary").innerHTML =
    "Units: " + currentUnits.length + " total &middot; " + occupiedUnits.length + " occupied &middot; " + vacantCount + " vacant" +
    (avgRentPerSF !== null ? " &middot; Avg rent/SF (occupied): $" + avgRentPerSF.toFixed(2) : "") + "<br>" +
    "Total monthly rent (occupied units): <strong>$" + totalMonthlyRent.toLocaleString() + "</strong>" +
    (totalOtherIncomeThisMonth ? " &middot; Other income this month: $" + totalOtherIncomeThisMonth.toLocaleString(undefined, {maximumFractionDigits: 0}) : "") + "<br>" +
    (mgmtFee.amount ? "Management fee this month: $" + mgmtFee.amount.toLocaleString(undefined, {maximumFractionDigits: 0}) +
      " (included in Fixed Costs below and itemized in your Expenses list)" +
      (mgmtFee.excludedUnitId ? " - free apartment, that unit's rent is excluded from income above" : "") + "<br>" : "") +
    "Fixed costs this month: $" + totalFixedThisMonth.toLocaleString(undefined, {maximumFractionDigits: 0}) +
    " &middot; Variable expenses this month: $" + totalVariableThisMonth.toLocaleString(undefined, {maximumFractionDigits: 0}) + "<br>" +
    (totalAllCapEx ? "Capital improvements this month: $" + totalCapExThisMonth.toLocaleString() + " &middot; All-time: $" + totalAllCapEx.toLocaleString() + "<br>" : "") +
    "All-time logged expenses: $" + totalAllExpenses.toLocaleString() + "<br>" +
    "<span style='color:" + cashFlowColor + ";font-weight:600;'>Estimated monthly cash flow: $" + cashFlow.toLocaleString(undefined, {maximumFractionDigits: 0}) + "</span>" +
    "<br><span style='font-size:11px;color:#888;'>Fixed costs = the Fixed Monthly Costs figure below plus any expenses flagged Annual, divided by 12 (this includes the management fee, if set). Variable expenses are other logged entries dated this month. Capital improvements (flagged CapEx) are tracked separately and don't reduce cash flow here. A simple estimate, not a full P&amp;L.</span>" +
    zeroRentWarning;
}

function statusLabel(status) {
  var labels = { rental: "Rental", leased: "Leased", eviction: "Eviction", vacant: "Vacant" };
  return labels[status] || status;
}

function generate5And10YearProFormaPDF() {
  if (!currentPropertyId) return;
  var address = document.getElementById("detail-address").textContent;

  // Year 1 baseline, annualized from current actual data - same exclusions/inclusions as
  // Key Ratios (manager's free apartment excluded from income, management fee counted as expense,
  // CapEx excluded since it's not a recurring operating cost).
  var mgmtFee = getMonthlyManagementFee();
  var occupiedUnits = currentUnits.filter(function(u) { return getUnitStatus(u) !== "vacant" && u.id !== mgmtFee.excludedUnitId; });
  var totalMonthlyRent = occupiedUnits.reduce(function(s, u) { return s + Number(u.rent || 0); }, 0);

  var now = new Date();
  var manualFixedCosts = parseFloat((document.getElementById("fixed-monthly-costs") || {}).value) || 0;
  var operatingExpenses = currentExpenses.filter(function(e) { return !e.isCapEx; });
  var effective = getEffectiveMonthlyExpenses(operatingExpenses, now.getFullYear(), now.getMonth());
  var autoFixedFromAnnual = effective.fixedFromAnnual.reduce(function(s, e) { return s + e.amount; }, 0);
  var totalVariableThisMonth = effective.variable.reduce(function(s, e) { return s + e.amount; }, 0);
  var totalMonthlyOpEx = manualFixedCosts + autoFixedFromAnnual + totalVariableThisMonth;

  var effectiveIncome = getEffectiveMonthlyExpenses(currentIncomeEntries, now.getFullYear(), now.getMonth());
  var totalOtherIncomeThisMonth = effectiveIncome.fixedFromAnnual.reduce(function(s, e) { return s + e.amount; }, 0) +
    effectiveIncome.variable.reduce(function(s, e) { return s + e.amount; }, 0);

  var year1Income = (totalMonthlyRent + totalOtherIncomeThisMonth) * 12;
  var year1Expenses = totalMonthlyOpEx * 12;

  var loanAmount = currentPropertyData.loanAmount || 0;
  var interestRate = currentPropertyData.interestRate || 0;
  var loanTermYears = currentPropertyData.loanTermYears || 0;
  var interestOnlyYears = currentPropertyData.interestOnlyYears || 0;
  var loanStartDateForProForma = currentPropertyData.loanStartDate || "";

  var rentGrowth = (currentPropertyData.rentGrowthRate || 0) / 100;
  var expenseGrowth = (currentPropertyData.expenseGrowthRate || 0) / 100;

  var isARM = currentPropertyData.isARM || false;
  var armFixedYears = currentPropertyData.armFixedYears || 0;
  var armResetRate = currentPropertyData.armResetRate || 0;
  var armRateIncreasePerYear = currentPropertyData.armRateIncreasePerYear || 0;
  var isNegativeAmortization = currentPropertyData.isNegativeAmortization || false;

  var balloonTermYears = currentPropertyData.balloonTermYears || 0;
  var loanStartDate = currentPropertyData.loanStartDate || "";
  var balloonDueYear = null;
  if (loanAmount > 0 && balloonTermYears > 0 && loanStartDate) {
    var loanStartYear = parseInt(loanStartDate.slice(0, 4), 10);
    balloonDueYear = loanStartYear + balloonTermYears;
  }

  // Align the simulator (which counts years from loan origination) with the pro forma's
  // calendar-year projection (Year 1 = this year) - run the simulator from loan start through
  // the end of the 10-year projection, then take just the years the projection actually covers.
  var currentCalendarYear = new Date().getFullYear();
  var monthsElapsedAtProjectionStart = getMonthsElapsedSinceLoanStart(loanStartDateForProForma, currentCalendarYear, 0);
  var startYearOffset = Math.round(monthsElapsedAtProjectionStart / 12);
  var simulatedYears = loanAmount > 0
    ? simulateLoanAmortization(loanAmount, interestRate, loanTermYears, interestOnlyYears, isARM, armFixedYears, armResetRate, armRateIncreasePerYear, isNegativeAmortization, startYearOffset + 10)
    : [];

  var rows = [];
  var yearlyNOI = [];
  var yearlyCashFlow = [];
  var yearlyEndingBalance = [];
  var cumulativeCashFlow = 0;
  var lastRate = interestRate;
  for (var year = 1; year <= 10; year++) {
    var yearIncome = year1Income * Math.pow(1 + rentGrowth, year - 1);
    var yearExpenses = year1Expenses * Math.pow(1 + expenseGrowth, year - 1);
    var yearNOI = yearIncome - yearExpenses;
    var calendarYear = currentCalendarYear + year - 1;

    var simIndex = startYearOffset + year - 1;
    var simYear = simulatedYears[simIndex];
    var annualDebtService = simYear ? simYear.debtService : 0;
    var endingBalance = simYear ? simYear.endingBalance : 0;
    var justTransitioned = simYear ? simYear.ioEndedThisYear : false;
    var rateChangedThisYear = simYear && simYear.rate !== lastRate;
    if (simYear) lastRate = simYear.rate;

    var yearCashFlow = yearNOI - annualDebtService;
    yearlyNOI.push(yearNOI);
    yearlyCashFlow.push(yearCashFlow);
    yearlyEndingBalance.push(endingBalance);
    cumulativeCashFlow += yearCashFlow;
    var balloonNote = (balloonDueYear && calendarYear === balloonDueYear) ? " (balloon due)" : "";
    var ioNote = justTransitioned ? " (IO ends)" : "";
    var armNote = simYear ? " (rate: " + lastRate.toFixed(2) + "%)" : "";

    rows.push([
      "Year " + year + balloonNote + ioNote + armNote,
      "$" + Math.round(yearIncome).toLocaleString(),
      "$" + Math.round(yearExpenses).toLocaleString(),
      "$" + Math.round(yearNOI).toLocaleString(),
      annualDebtService > 0 ? "-$" + Math.round(annualDebtService).toLocaleString() : "$0",
      "$" + Math.round(yearCashFlow).toLocaleString(),
      "$" + Math.round(cumulativeCashFlow).toLocaleString(),
      loanAmount > 0 ? "$" + Math.round(endingBalance).toLocaleString() : "N/A"
    ]);
  }

  // IRR at a 5-year and 10-year exit, using the assumed exit cap rate to estimate sale price
  // (Sale Price = that exit year's NOI / Exit Cap Rate), less selling costs and the remaining
  // loan balance, to get net sale proceeds added to that final year's cash flow.
  var downPaymentForIRR = currentPropertyData.downPayment || 0;
  var purchasePriceForIRR = currentPropertyData.purchasePrice || 0;
  var closingCostsPct = (currentPropertyData.closingCostsPct || 0) / 100;
  var exitCapRatePct = currentPropertyData.exitCapRate || 0;
  var sellingCostsPct = (currentPropertyData.sellingCostsPct || 0) / 100;
  var initialInvestment = downPaymentForIRR + purchasePriceForIRR * closingCostsPct;

  function irrForHoldPeriod(holdYears) {
    if (initialInvestment <= 0 || exitCapRatePct <= 0) return null;
    var exitNOI = yearlyNOI[holdYears - 1];
    var exitBalance = yearlyEndingBalance[holdYears - 1];
    var salePrice = exitNOI / (exitCapRatePct / 100);
    var netSaleProceeds = salePrice * (1 - sellingCostsPct) - exitBalance;
    var cashFlows = [-initialInvestment];
    for (var y = 0; y < holdYears; y++) {
      var cf = yearlyCashFlow[y];
      if (y === holdYears - 1) cf += netSaleProceeds;
      cashFlows.push(cf);
    }
    var irr = calculateIRR(cashFlows);
    return { irr: irr, salePrice: salePrice, netSaleProceeds: netSaleProceeds };
  }

  var irr5 = irrForHoldPeriod(5);
  var irr10 = irrForHoldPeriod(10);

  var doc = new jspdf.jsPDF();
  var today = new Date().toLocaleDateString();

  doc.setFontSize(16);
  doc.text("5 & 10-Year Pro Forma", 14, 18);
  doc.setFontSize(11);
  doc.setTextColor(80);
  doc.text(address, 14, 26);
  doc.text("Generated: " + today + "  |  Rent Growth: " + (rentGrowth * 100).toFixed(1) + "%/yr  |  Expense Growth: " + (expenseGrowth * 100).toFixed(1) + "%/yr" + (isARM ? "  |  ARM" : ""), 14, 32);

  var tableStartY = 40;
  var isTeaserRate = isARM && armResetRate > 0 && armResetRate > interestRate;
  if (isTeaserRate) {
    var boxHeight = isNegativeAmortization ? 26 : 14;
    doc.setFillColor(254, 243, 199);
    doc.setDrawColor(245, 158, 11);
    doc.rect(14, 37, 182, boxHeight, "FD");
    doc.setFontSize(9);
    doc.setTextColor(120, 53, 15);
    doc.text(
      "TEASER RATE: This loan starts at " + interestRate.toFixed(2) + "% for the first " + armFixedYears +
      " year" + (armFixedYears === 1 ? "" : "s") + " - a temporary, below-market rate.",
      18, 43
    );
    doc.text(
      "It resets to " + armResetRate.toFixed(2) + "% after that (see Year " + (armFixedYears + 1) + " below), which is what this loan actually costs long-term.",
      18, 48
    );
    if (isNegativeAmortization) {
      doc.setFont(undefined, "bold");
      doc.text(
        "NEGATIVE AMORTIZATION: interest is actually accruing at " + armResetRate.toFixed(2) + "% during this period, not " +
        interestRate.toFixed(2) + "%. The unpaid difference (" + (armResetRate - interestRate).toFixed(2) + "% per year) is added to",
        18, 53
      );
      doc.text("your balance each month - see the Loan Balance column below actually increase during Years 1-" + armFixedYears + ".", 18, 58);
      doc.setFont(undefined, "normal");
    }
    tableStartY = 37 + boxHeight + 6;
  }

  doc.autoTable({
    startY: tableStartY,
    head: [["Year", "Gross Income", "Op. Expenses", "NOI", "Debt Service", "Cash Flow", "Cumulative", "Loan Balance"]],
    body: rows,
    styles: { fontSize: 7.5 },
    headStyles: { fillColor: [31, 78, 121] },
    didParseCell: function(data) {
      if (data.row.index === 4 || data.row.index === 9) { data.cell.styles.fontStyle = "bold"; } // Year 5 and Year 10
    }
  });

  var afterTableY = doc.lastAutoTable.finalY + 10;

  if (irr5 || irr10) {
    doc.setFontSize(11);
    doc.setTextColor(31, 78, 121);
    doc.text("IRR Analysis (assumes sale at exit)", 14, afterTableY);
    doc.setFontSize(9);
    doc.setTextColor(60);
    var irrY = afterTableY + 6;
    if (irr5) {
      doc.text("5-Year Hold: IRR " + (irr5.irr !== null ? (irr5.irr * 100).toFixed(1) + "%" : "N/A (check assumptions)") +
        "  |  Est. Sale Price: $" + Math.round(irr5.salePrice).toLocaleString() +
        "  |  Net Sale Proceeds: $" + Math.round(irr5.netSaleProceeds).toLocaleString(), 14, irrY);
      irrY += 5;
    }
    if (irr10) {
      doc.text("10-Year Hold: IRR " + (irr10.irr !== null ? (irr10.irr * 100).toFixed(1) + "%" : "N/A (check assumptions)") +
        "  |  Est. Sale Price: $" + Math.round(irr10.salePrice).toLocaleString() +
        "  |  Net Sale Proceeds: $" + Math.round(irr10.netSaleProceeds).toLocaleString(), 14, irrY);
      irrY += 5;
    }
    afterTableY = irrY + 4;
  }

  doc.setFontSize(8);
  doc.setTextColor(140);
  var noteLines = [
    "Year 1 is annualized from current actual rent, other income, and operating expenses. Years 2-10 apply the",
    "growth rates above, compounding annually. Loan Balance shows the remaining principal at the end of each year -",
    "it will stay flat during an interest-only period, then decline once amortization begins. Debt Service reflects",
    "your loan's actual terms, including an interest-only period if one is set (marked IO ends in the year it",
    "converts to a fully-amortizing payment, which is typically higher than the interest-only payment).",
    "This is a projection based on assumptions you provide, not a guarantee - actual results depend on real market",
    "conditions, tenant turnover, unexpected expenses, and other factors this model cannot predict."
  ];
  if (irr5 || irr10) {
    noteLines.push("IRR assumes you sell at the end of the hold period at the Exit Cap Rate you entered (Sale Price = that year's");
    noteLines.push("NOI / Exit Cap Rate), less selling costs and the remaining loan balance. This is a projection based on your");
    noteLines.push("assumptions, not a market prediction - actual sale price and timing depend on real conditions at exit.");
  }
  if (isARM) {
    noteLines.push("This loan is modeled as an ARM: the rate holds during the fixed period, then increases by the assumed");
    noteLines.push("rate above every year after - marked with the new rate in the year each adjustment takes effect. This is a");
    noteLines.push("stress-test assumption, not a prediction of actual future rates.");
  }
  if (balloonDueYear) {
    noteLines.push("Note: your loan's balloon payment is due in " + balloonDueYear + " (marked above) - the full remaining balance");
    noteLines.push("comes due then, requiring a refinance or payoff, which this projection does not model.");
  }
  doc.text(noteLines, 14, afterTableY);

  var fileSafeAddress = address.replace(/[^a-z0-9]/gi, "_").slice(0, 40);
  doc.save("ProForma_5_10Year_" + fileSafeAddress + ".pdf");
}

function generateRentRollPDF() {
  if (!currentPropertyId) return;
  var address = document.getElementById("detail-address").textContent;
  var sorted = currentUnits.slice().sort(function(a, b) { return (a.sortOrder || 0) - (b.sortOrder || 0); });

  var occupiedUnits = currentUnits.filter(function(u) { return getUnitStatus(u) !== "vacant"; });
  var totalMonthlyRent = occupiedUnits.reduce(function(sum, u) { return sum + Number(u.rent || 0); }, 0);
  var vacantCount = currentUnits.length - occupiedUnits.length;
  var occupancyPct = currentUnits.length ? Math.round((occupiedUnits.length / currentUnits.length) * 100) : 0;

  var doc = new jspdf.jsPDF();
  var today = new Date().toLocaleDateString();

  doc.setFontSize(16);
  doc.text("Rent Roll Report", 14, 18);
  doc.setFontSize(11);
  doc.setTextColor(80);
  doc.text(address, 14, 26);
  doc.text("Generated: " + today, 14, 32);

  doc.setFontSize(10);
  doc.text(
    "Units: " + currentUnits.length + "   Occupied: " + occupiedUnits.length + " (" + occupancyPct + "%)   " +
    "Vacant: " + vacantCount + "   Total Monthly Rent: $" + totalMonthlyRent.toLocaleString(),
    14, 40
  );

  var rows = sorted.map(function(u) {
    return [
      u.unitNumber || u.label || "N/A",
      u.unitType || "N/A",
      statusLabel(getUnitStatus(u)),
      u.tenantName || "-",
      "$" + Number(u.rent || 0).toLocaleString(),
      u.leaseEndDate || "-"
    ];
  });

  doc.autoTable({
    startY: 46,
    head: [["Apt #", "Type", "Status", "Tenant", "Rent", "Lease End"]],
    body: rows,
    styles: { fontSize: 9 },
    headStyles: { fillColor: [31, 78, 121] }
  });

  var fileSafeAddress = address.replace(/[^a-z0-9]/gi, "_").slice(0, 40);
  doc.save("RentRoll_" + fileSafeAddress + "_" + new Date().toISOString().slice(0, 10) + ".pdf");
}

var MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function generateYTDReportPDF() {
  if (!currentPropertyId) return;
  var address = document.getElementById("detail-address").textContent;
  var fixedMonthlyCosts = parseFloat(document.getElementById("fixed-monthly-costs").value) || 0;

  var occupiedUnits = currentUnits.filter(function(u) { return getUnitStatus(u) !== "vacant"; });
  var totalMonthlyRent = occupiedUnits.reduce(function(sum, u) { return sum + Number(u.rent || 0); }, 0);

  var now = new Date();
  var year = now.getFullYear();
  var currentMonthIdx = now.getMonth(); // 0 = January

  var rows = [];
  var ytdIncome = 0, ytdFixed = 0, ytdVariable = 0;

  for (var m = 0; m <= currentMonthIdx; m++) {
    var effective = getEffectiveMonthlyExpenses(currentExpenses, year, m);
    var autoFixedFromAnnual = effective.fixedFromAnnual.reduce(function(sum, e) { return sum + e.amount; }, 0);
    var monthFixed = fixedMonthlyCosts + autoFixedFromAnnual;
    var variableTotal = effective.variable.reduce(function(sum, e) { return sum + e.amount; }, 0);
    var totalExpenses = monthFixed + variableTotal;
    var netCashFlow = totalMonthlyRent - totalExpenses;

    ytdIncome += totalMonthlyRent;
    ytdFixed += monthFixed;
    ytdVariable += variableTotal;

    rows.push([
      MONTH_NAMES[m],
      "$" + totalMonthlyRent.toLocaleString(),
      "$" + monthFixed.toLocaleString(undefined, {maximumFractionDigits: 0}),
      "$" + variableTotal.toLocaleString(undefined, {maximumFractionDigits: 0}),
      "$" + totalExpenses.toLocaleString(undefined, {maximumFractionDigits: 0}),
      "$" + netCashFlow.toLocaleString(undefined, {maximumFractionDigits: 0})
    ]);
  }

  var ytdTotalExpenses = ytdFixed + ytdVariable;
  var ytdNetCashFlow = ytdIncome - ytdTotalExpenses;
  rows.push([
    "YTD Total", "$" + ytdIncome.toLocaleString(),
    "$" + ytdFixed.toLocaleString(undefined, {maximumFractionDigits: 0}),
    "$" + ytdVariable.toLocaleString(undefined, {maximumFractionDigits: 0}),
    "$" + ytdTotalExpenses.toLocaleString(undefined, {maximumFractionDigits: 0}),
    "$" + ytdNetCashFlow.toLocaleString(undefined, {maximumFractionDigits: 0})
  ]);

  var doc = new jspdf.jsPDF();
  var today = new Date().toLocaleDateString();

  doc.setFontSize(16);
  doc.text("Year-to-Date Financial Summary", 14, 18);
  doc.setFontSize(11);
  doc.setTextColor(80);
  doc.text(address, 14, 26);
  doc.text("Generated: " + today + "  (January - " + MONTH_NAMES[currentMonthIdx] + " " + year + ")", 14, 32);

  doc.autoTable({
    startY: 40,
    head: [["Month", "Rental Income", "Fixed Costs", "Variable Expenses", "Total Expenses", "Net Cash Flow"]],
    body: rows,
    styles: { fontSize: 9 },
    headStyles: { fillColor: [31, 78, 121] },
    didParseCell: function(data) {
      if (data.row.index === rows.length - 1) { data.cell.styles.fontStyle = "bold"; }
    }
  });

  var afterTableY = doc.lastAutoTable.finalY + 10;
  doc.setFontSize(11);
  doc.setTextColor(0);
  doc.text("Current Apartment Status (as of " + today + ")", 14, afterTableY);

  var statusCounts = { rental: 0, leased: 0, eviction: 0, vacant: 0 };
  currentUnits.forEach(function(u) { statusCounts[getUnitStatus(u)] = (statusCounts[getUnitStatus(u)] || 0) + 1; });

  doc.setFontSize(10);
  doc.setTextColor(80);
  doc.text(
    currentUnits.length + " units total:  " + statusCounts.rental + " Rental,  " + statusCounts.leased + " Leased,  " +
    statusCounts.eviction + " Eviction,  " + statusCounts.vacant + " Vacant",
    14, afterTableY + 7
  );

  doc.setFontSize(8);
  doc.setTextColor(140);
  doc.text(
    [
      "Rental income and the manually-entered fixed cost figure are held constant across all months. Expenses flagged as",
      "Annual (property tax, insurance, etc.) are divided by 12 and spread evenly across every month of the year, rather",
      "than counted entirely in the month they were logged. Other expenses reflect actual logged entries per month."
    ],
    14, afterTableY + 15
  );

  var fileSafeAddress = address.replace(/[^a-z0-9]/gi, "_").slice(0, 40);
  doc.save("YTDSummary_" + fileSafeAddress + "_" + year + ".pdf");
}

// Given all logged expenses, returns the effective breakdown for one specific month, split into
// two separate buckets - since expenses flagged "Annual" are meant to be treated as Fixed Costs
// (spread evenly, divided by 12, counted in every month of that year), not mixed in with genuinely
// one-time Variable expenses (which only count in full in the specific month they were dated).
function getEffectiveMonthlyExpenses(allExpenses, year, monthIdx) {
  var monthKey = year + "-" + String(monthIdx + 1).padStart(2, "0");
  var targetLinearMonth = year * 12 + monthIdx;
  var fixedFromAnnual = [];
  var variable = [];
  allExpenses.forEach(function(e) {
    var d = e.date || "";
    if (e.isAnnual) {
      if (d.slice(0, 4) === String(year)) {
        fixedFromAnnual.push({ category: e.category, amount: Number(e.amount || 0) / 12 });
      }
    } else if (e.isRecurringMonthly) {
      // Same amount applies to every month from the start date forward, indefinitely -
      // e.g. a $1,000/month management fee, not divided or run-rate-projected.
      var startYear = parseInt(d.slice(0, 4), 10);
      var startMonthIdx = parseInt(d.slice(5, 7), 10) - 1;
      var startLinearMonth = startYear * 12 + startMonthIdx;
      if (!isNaN(startLinearMonth) && targetLinearMonth >= startLinearMonth) {
        fixedFromAnnual.push({ category: e.category, amount: Number(e.amount || 0) });
      }
    } else if (d.slice(0, 7) === monthKey) {
      variable.push({ category: e.category, amount: Number(e.amount || 0) });
    }
  });
  return { fixedFromAnnual: fixedFromAnnual, variable: variable };
}

function groupExpensesByCategory(expenses) {
  var groups = {};
  var order = [];
  expenses.forEach(function(e) {
    var key = (e.category || "Uncategorized").trim().toLowerCase();
    if (!groups[key]) { groups[key] = { label: (e.category || "Uncategorized").trim(), total: 0 }; order.push(key); }
    groups[key].total += Number(e.amount || 0);
  });
  return order.map(function(key) { return groups[key]; });
}

function generateIncomeStatementPDF() {
  if (!currentPropertyId) return;
  var address = document.getElementById("detail-address").textContent;
  var fixedMonthlyCosts = parseFloat(document.getElementById("fixed-monthly-costs").value) || 0;
  var selectedMonth = document.getElementById("income-statement-month").value; // "YYYY-MM"
  if (!selectedMonth) { alert("Select a statement month first."); return; }

  var year = parseInt(selectedMonth.slice(0, 4), 10);
  var monthIdx = parseInt(selectedMonth.slice(5, 7), 10) - 1; // 0-based

  var occupiedUnits = currentUnits.filter(function(u) { return getUnitStatus(u) !== "vacant"; });
  var vacantUnits = currentUnits.filter(function(u) { return getUnitStatus(u) === "vacant"; });
  var totalMonthlyRent = occupiedUnits.reduce(function(sum, u) { return sum + Number(u.rent || 0); }, 0);
  var grossScheduledIncome = currentUnits.reduce(function(sum, u) { return sum + Number(u.rent || 0); }, 0);
  var vacancyLoss = vacantUnits.reduce(function(sum, u) { return sum + Number(u.rent || 0); }, 0);
  var vacantUnitsWithZeroRent = vacantUnits.filter(function(u) { return !Number(u.rent); });
  var monthsElapsedInYear = monthIdx + 1; // Jan=1 through selected month, inclusive

  // CapEx (capital improvements) is excluded from operating expenses - tracked in its own section below.
  var operatingExpenses = currentExpenses.filter(function(e) { return !e.isCapEx; });
  var capExExpenses = currentExpenses.filter(function(e) { return e.isCapEx; });

  // This month: split into auto-fixed (annual-flagged, /12) and variable (one-time, dated this month)
  var thisMonthEffective = getEffectiveMonthlyExpenses(operatingExpenses, year, monthIdx);
  var thisMonthAutoFixed = thisMonthEffective.fixedFromAnnual.reduce(function(sum, e) { return sum + e.amount; }, 0);
  var thisMonthFixedGroups = groupExpensesByCategory(thisMonthEffective.fixedFromAnnual);
  var thisMonthGroups = groupExpensesByCategory(thisMonthEffective.variable);
  var thisMonthVariableTotal = thisMonthGroups.reduce(function(sum, g) { return sum + g.total; }, 0);

  // Year-to-date: accumulate each month's fixed and variable buckets separately (Jan through selected month).
  var ytdAutoFixed = 0;
  var ytdFixedFromAnnualEntries = [];
  var ytdVariableEntries = [];
  for (var mm = 0; mm <= monthIdx; mm++) {
    var monthEffective = getEffectiveMonthlyExpenses(operatingExpenses, year, mm);
    ytdAutoFixed += monthEffective.fixedFromAnnual.reduce(function(sum, e) { return sum + e.amount; }, 0);
    ytdFixedFromAnnualEntries = ytdFixedFromAnnualEntries.concat(monthEffective.fixedFromAnnual);
    ytdVariableEntries = ytdVariableEntries.concat(monthEffective.variable);
  }
  var ytdFixedGroups = groupExpensesByCategory(ytdFixedFromAnnualEntries);
  var ytdGroups = groupExpensesByCategory(ytdVariableEntries);
  var ytdVariableTotal = ytdGroups.reduce(function(sum, g) { return sum + g.total; }, 0);

  // Other Income: same effective-monthly-spreading logic as expenses, applied to income entries.
  var thisMonthIncomeEffective = getEffectiveMonthlyExpenses(currentIncomeEntries, year, monthIdx);
  var thisMonthIncomeGroups = groupExpensesByCategory(thisMonthIncomeEffective.fixedFromAnnual.concat(thisMonthIncomeEffective.variable));
  var thisMonthOtherIncomeTotal = thisMonthIncomeGroups.reduce(function(sum, g) { return sum + g.total; }, 0);
  var ytdIncomeEntries = [];
  for (var mi = 0; mi <= monthIdx; mi++) {
    var monthIncomeEffective = getEffectiveMonthlyExpenses(currentIncomeEntries, year, mi);
    ytdIncomeEntries = ytdIncomeEntries.concat(monthIncomeEffective.fixedFromAnnual).concat(monthIncomeEffective.variable);
  }
  var ytdIncomeGroups = groupExpensesByCategory(ytdIncomeEntries);
  var ytdOtherIncomeTotal = ytdIncomeGroups.reduce(function(sum, g) { return sum + g.total; }, 0);
  var allIncomeCategoryLabels = {};
  thisMonthIncomeGroups.forEach(function(g) { allIncomeCategoryLabels[g.label.toLowerCase()] = g.label; });
  ytdIncomeGroups.forEach(function(g) { allIncomeCategoryLabels[g.label.toLowerCase()] = g.label; });
  function monthIncomeAmountFor(label) {
    var g = thisMonthIncomeGroups.find(function(x) { return x.label.toLowerCase() === label.toLowerCase(); });
    return g ? g.total : 0;
  }
  function ytdIncomeAmountFor(label) {
    var g = ytdIncomeGroups.find(function(x) { return x.label.toLowerCase() === label.toLowerCase(); });
    return g ? g.total : 0;
  }

  // Capital Expenditures: actual logged amounts only - not run-rate projected, since capital
  // improvements are lumpy/infrequent by nature and a run-rate would be misleading.
  var thisMonthCapEx = capExExpenses.filter(function(e) { return (e.date || "").slice(0, 7) === selectedMonth; })
    .reduce(function(sum, e) { return sum + Number(e.amount || 0); }, 0);
  var ytdCapEx = capExExpenses.filter(function(e) {
    var d = e.date || "";
    return d.slice(0, 4) === String(year) && (parseInt(d.slice(5, 7), 10) - 1) <= monthIdx;
  }).reduce(function(sum, e) { return sum + Number(e.amount || 0); }, 0);
  var capExGroups = groupExpensesByCategory(capExExpenses.filter(function(e) {
    var d = e.date || "";
    return d.slice(0, 4) === String(year) && (parseInt(d.slice(5, 7), 10) - 1) <= monthIdx;
  }));

  // Union of category labels appearing in either period, so both columns line up on the same rows
  var allCategoryLabels = {};
  thisMonthGroups.forEach(function(g) { allCategoryLabels[g.label.toLowerCase()] = g.label; });
  ytdGroups.forEach(function(g) { allCategoryLabels[g.label.toLowerCase()] = g.label; });
  function monthAmountFor(label) {
    var g = thisMonthGroups.find(function(x) { return x.label.toLowerCase() === label.toLowerCase(); });
    return g ? g.total : 0;
  }
  function ytdAmountFor(label) {
    var g = ytdGroups.find(function(x) { return x.label.toLowerCase() === label.toLowerCase(); });
    return g ? g.total : 0;
  }

  // Same lookup pattern, but for the annual/fixed-cost categories
  var allFixedCategoryLabels = {};
  thisMonthFixedGroups.forEach(function(g) { allFixedCategoryLabels[g.label.toLowerCase()] = g.label; });
  ytdFixedGroups.forEach(function(g) { allFixedCategoryLabels[g.label.toLowerCase()] = g.label; });
  function monthFixedAmountFor(label) {
    var g = thisMonthFixedGroups.find(function(x) { return x.label.toLowerCase() === label.toLowerCase(); });
    return g ? g.total : 0;
  }
  function ytdFixedAmountFor(label) {
    var g = ytdFixedGroups.find(function(x) { return x.label.toLowerCase() === label.toLowerCase(); });
    return g ? g.total : 0;
  }

  var thisMonthFixedCosts = fixedMonthlyCosts + thisMonthAutoFixed;
  var ytdEffectiveRentalIncome = totalMonthlyRent * monthsElapsedInYear;
  var thisMonthTotalRevenue = totalMonthlyRent + thisMonthOtherIncomeTotal;
  var ytdTotalRevenue = ytdEffectiveRentalIncome + ytdOtherIncomeTotal;
  var ytdFixedCosts = (fixedMonthlyCosts * monthsElapsedInYear) + ytdAutoFixed;
  var thisMonthTotalExpenses = thisMonthFixedCosts + thisMonthVariableTotal;
  var ytdTotalExpenses = ytdFixedCosts + ytdVariableTotal;
  var thisMonthNOI = thisMonthTotalRevenue - thisMonthTotalExpenses;
  var ytdNOI = ytdTotalRevenue - ytdTotalExpenses;

  // Debt service: primary mortgage (if financing details are on file) plus any actively-financed
  // capital improvements (e.g. a roof loan) - summed month-by-month for YTD since a CapEx loan
  // (or an interest-only period ending) may change mid-year and shouldn't be applied retroactively.
  var loanAmount = currentPropertyData.loanAmount || 0;
  var interestRate = currentPropertyData.interestRate || 0;
  var loanTermYears = currentPropertyData.loanTermYears || 0;
  var interestOnlyYears = currentPropertyData.interestOnlyYears || 0;
  var loanStartDateForDebtService = currentPropertyData.loanStartDate || "";
  var monthsElapsedForSelectedMonth = getMonthsElapsedSinceLoanStart(loanStartDateForDebtService, year, monthIdx);
  var monthlyMortgagePayment = calculateMonthlyDebtService(loanAmount, interestRate, loanTermYears, interestOnlyYears, monthsElapsedForSelectedMonth);

  var thisMonthCapExFinancingItems = getCapExFinancingForMonth(capExExpenses, year, monthIdx);
  var thisMonthCapExFinancing = thisMonthCapExFinancingItems.reduce(function(sum, item) { return sum + item.amount; }, 0);
  var ytdCapExFinancing = 0;
  var ytdCapExFinancingByCategory = {};
  var ytdMortgagePayments = 0;
  for (var cf = 0; cf <= monthIdx; cf++) {
    getCapExFinancingForMonth(capExExpenses, year, cf).forEach(function(item) {
      ytdCapExFinancing += item.amount;
      ytdCapExFinancingByCategory[item.category] = (ytdCapExFinancingByCategory[item.category] || 0) + item.amount;
    });
    var monthsElapsedForThatMonth = getMonthsElapsedSinceLoanStart(loanStartDateForDebtService, year, cf);
    ytdMortgagePayments += calculateMonthlyDebtService(loanAmount, interestRate, loanTermYears, interestOnlyYears, monthsElapsedForThatMonth);
  }

  var monthlyDebtService = monthlyMortgagePayment + thisMonthCapExFinancing;
  var ytdDebtService = ytdMortgagePayments + ytdCapExFinancing;
  var thisMonthCashFlowAfterDebt = thisMonthNOI - monthlyDebtService;
  var ytdCashFlowAfterDebt = ytdNOI - ytdDebtService;

  // Projected Annual: Rental Income and Fixed Costs just annualize directly since they're already
  // held constant per month. Variable expenses use a run-rate: the YTD pace extrapolated to 12 months,
  // since these vary and a straight multiply-by-12 of any single month wouldn't be representative.
  function projectRunRate(ytdTotal) {
    return monthsElapsedInYear > 0 ? (ytdTotal / monthsElapsedInYear) * 12 : 0;
  }
  var projectedRentalIncome = totalMonthlyRent * 12;
  var projectedFixedCosts = thisMonthFixedCosts * 12;
  function projectedAmountFor(label) {
    return projectRunRate(ytdAmountFor(label));
  }
  function projectedIncomeAmountFor(label) {
    return projectRunRate(ytdIncomeAmountFor(label));
  }
  // Fixed-cost categories are already smoothed (divided by 12), so their monthly value IS
  // the ongoing rate - just annualize directly rather than run-rate from YTD.
  function projectedFixedAmountFor(label) {
    return monthFixedAmountFor(label) * 12;
  }
  var projectedVariableTotal = Object.keys(allCategoryLabels).reduce(function(sum, key) {
    return sum + projectedAmountFor(allCategoryLabels[key]);
  }, 0);
  var projectedOtherIncomeTotal = Object.keys(allIncomeCategoryLabels).reduce(function(sum, key) {
    return sum + projectedIncomeAmountFor(allIncomeCategoryLabels[key]);
  }, 0);
  var projectedTotalRevenue = projectedRentalIncome + projectedOtherIncomeTotal;
  var projectedTotalExpenses = projectedFixedCosts + projectedVariableTotal;
  var projectedNOI = projectedTotalRevenue - projectedTotalExpenses;
  var projectedDebtService = monthlyDebtService * 12;
  var projectedCashFlowAfterDebt = projectedNOI - projectedDebtService;

  var rows = [];
  rows.push(["REVENUE", "", "", ""]);
  rows.push(["  Gross Scheduled Income", "$" + grossScheduledIncome.toLocaleString(), "$" + (grossScheduledIncome * monthsElapsedInYear).toLocaleString(), "$" + (grossScheduledIncome * 12).toLocaleString()]);
  rows.push(["  Less: Vacancy Loss", "-$" + vacancyLoss.toLocaleString(), "-$" + (vacancyLoss * monthsElapsedInYear).toLocaleString(), "-$" + (vacancyLoss * 12).toLocaleString()]);
  rows.push(["  Effective Rental Income", "$" + totalMonthlyRent.toLocaleString(), "$" + ytdEffectiveRentalIncome.toLocaleString(), "$" + projectedRentalIncome.toLocaleString()]);
  Object.keys(allIncomeCategoryLabels).sort().forEach(function(key) {
    var label = allIncomeCategoryLabels[key];
    rows.push([
      "  " + label,
      "$" + monthIncomeAmountFor(label).toLocaleString(undefined, {maximumFractionDigits: 0}),
      "$" + ytdIncomeAmountFor(label).toLocaleString(undefined, {maximumFractionDigits: 0}),
      "$" + projectedIncomeAmountFor(label).toLocaleString(undefined, {maximumFractionDigits: 0})
    ]);
  });
  rows.push(["TOTAL REVENUE", "$" + thisMonthTotalRevenue.toLocaleString(undefined, {maximumFractionDigits: 0}), "$" + ytdTotalRevenue.toLocaleString(undefined, {maximumFractionDigits: 0}), "$" + projectedTotalRevenue.toLocaleString(undefined, {maximumFractionDigits: 0})]);
  var totalRevenueRowIndex = rows.length - 1;
  rows.push(["", "", "", ""]);
  rows.push(["OPERATING EXPENSES", "", "", ""]);
  if (fixedMonthlyCosts > 0) {
    rows.push([
      "  Fixed Costs (manually entered)",
      "$" + fixedMonthlyCosts.toLocaleString(),
      "$" + (fixedMonthlyCosts * monthsElapsedInYear).toLocaleString(),
      "$" + (fixedMonthlyCosts * 12).toLocaleString()
    ]);
  }
  Object.keys(allFixedCategoryLabels).sort().forEach(function(key) {
    var label = allFixedCategoryLabels[key];
    rows.push([
      "  " + label + " (Annual)",
      "$" + monthFixedAmountFor(label).toLocaleString(undefined, {maximumFractionDigits: 0}),
      "$" + ytdFixedAmountFor(label).toLocaleString(undefined, {maximumFractionDigits: 0}),
      "$" + projectedFixedAmountFor(label).toLocaleString(undefined, {maximumFractionDigits: 0})
    ]);
  });
  rows.push([
    "  Total Fixed Costs",
    "$" + thisMonthFixedCosts.toLocaleString(undefined, {maximumFractionDigits: 0}),
    "$" + ytdFixedCosts.toLocaleString(undefined, {maximumFractionDigits: 0}),
    "$" + projectedFixedCosts.toLocaleString(undefined, {maximumFractionDigits: 0})
  ]);
  var totalFixedRowIndex = rows.length - 1;
  Object.keys(allCategoryLabels).sort().forEach(function(key) {
    var label = allCategoryLabels[key];
    rows.push([
      "  " + label,
      "$" + monthAmountFor(label).toLocaleString(undefined, {maximumFractionDigits: 0}),
      "$" + ytdAmountFor(label).toLocaleString(undefined, {maximumFractionDigits: 0}),
      "$" + projectedAmountFor(label).toLocaleString(undefined, {maximumFractionDigits: 0})
    ]);
  });
  rows.push([
    "TOTAL OPERATING EXPENSES",
    "$" + thisMonthTotalExpenses.toLocaleString(undefined, {maximumFractionDigits: 0}),
    "$" + ytdTotalExpenses.toLocaleString(undefined, {maximumFractionDigits: 0}),
    "$" + projectedTotalExpenses.toLocaleString(undefined, {maximumFractionDigits: 0})
  ]);
  rows.push(["", "", "", ""]);
  rows.push([
    "NET OPERATING INCOME",
    "$" + thisMonthNOI.toLocaleString(undefined, {maximumFractionDigits: 0}),
    "$" + ytdNOI.toLocaleString(undefined, {maximumFractionDigits: 0}),
    "$" + projectedNOI.toLocaleString(undefined, {maximumFractionDigits: 0})
  ]);
  var noiRowIndex = rows.length - 1;

  var debtServiceRowIndexes = [];
  if (loanAmount > 0 || ytdCapExFinancing > 0 || thisMonthCapExFinancing > 0) {
    rows.push(["", "", "", ""]);
    rows.push(["DEBT SERVICE", "", "", ""]);
    debtServiceRowIndexes.push(rows.length - 1);
    if (loanAmount > 0) {
      rows.push(["  Principal & Interest (Mortgage)", "-$" + monthlyMortgagePayment.toLocaleString(undefined, {maximumFractionDigits: 0}), "-$" + ytdMortgagePayments.toLocaleString(undefined, {maximumFractionDigits: 0}), "-$" + (monthlyMortgagePayment * 12).toLocaleString(undefined, {maximumFractionDigits: 0})]);
    }
    thisMonthCapExFinancingItems.forEach(function(item) {
      var itemYtd = ytdCapExFinancingByCategory[item.category] || 0;
      rows.push(["  " + item.category + " (Financed)", "-$" + item.amount.toLocaleString(undefined, {maximumFractionDigits: 0}), "-$" + itemYtd.toLocaleString(undefined, {maximumFractionDigits: 0}), "-$" + (item.amount * 12).toLocaleString(undefined, {maximumFractionDigits: 0})]);
    });
    rows.push(["CASH FLOW AFTER DEBT SERVICE", "$" + thisMonthCashFlowAfterDebt.toLocaleString(undefined, {maximumFractionDigits: 0}), "$" + ytdCashFlowAfterDebt.toLocaleString(undefined, {maximumFractionDigits: 0}), "$" + projectedCashFlowAfterDebt.toLocaleString(undefined, {maximumFractionDigits: 0})]);
    debtServiceRowIndexes.push(rows.length - 1);
  }

  var capExRowIndexes = [];
  if (ytdCapEx > 0 || thisMonthCapEx > 0) {
    rows.push(["", "", "", ""]);
    rows.push(["CAPITAL EXPENDITURES (not included in NOI)", "", "", ""]);
    capExRowIndexes.push(rows.length - 1);
    capExGroups.forEach(function(g) {
      var monthAmt = capExExpenses.filter(function(e) { return e.category === g.label && (e.date || "").slice(0, 7) === selectedMonth; })
        .reduce(function(sum, e) { return sum + Number(e.amount || 0); }, 0);
      rows.push(["  " + g.label, "$" + monthAmt.toLocaleString(), "$" + g.total.toLocaleString(), "N/A"]);
    });
    rows.push(["  Total Capital Expenditures", "$" + thisMonthCapEx.toLocaleString(), "$" + ytdCapEx.toLocaleString(), "N/A"]);
    capExRowIndexes.push(rows.length - 1);
  }

  var opExHeaderRowIndex = rows.findIndex(function(r) { return r[0] === "OPERATING EXPENSES"; });
  var boldRowIndexes = [0, totalRevenueRowIndex, opExHeaderRowIndex, totalFixedRowIndex, noiRowIndex].concat(debtServiceRowIndexes).concat(capExRowIndexes);
  var totalOpExRowIndex = rows.findIndex(function(r) { return r[0] === "TOTAL OPERATING EXPENSES"; });
  if (totalOpExRowIndex !== -1) boldRowIndexes.push(totalOpExRowIndex);

  var doc = new jspdf.jsPDF();
  var today = new Date().toLocaleDateString();

  doc.setFontSize(16);
  doc.text("Income Statement", 14, 18);
  doc.setFontSize(11);
  doc.setTextColor(80);
  doc.text(address, 14, 26);
  doc.text("Statement Month: " + MONTH_NAMES[monthIdx] + " " + year + "  |  Generated: " + today, 14, 32);

  var tableStartY = 40;
  if (vacantUnitsWithZeroRent.length) {
    doc.setFontSize(9);
    doc.setTextColor(192, 57, 43);
    doc.text(
      "Warning: " + vacantUnitsWithZeroRent.length + " vacant unit(s) have a Rent field of $0, which understates Vacancy Loss below.",
      14, 38
    );
    doc.text("Go to that unit in the Units table and enter its market rent (the rent it would charge if occupied), not $0.", 14, 43);
    tableStartY = 50;
  }

  doc.autoTable({
    startY: tableStartY,
    head: [["Line Item", MONTH_NAMES[monthIdx] + " " + year, "Year-to-Date", "Projected Annual"]],
    body: rows,
    styles: { fontSize: 9 },
    headStyles: { fillColor: [31, 78, 121] },
    columnStyles: { 1: { halign: "right" }, 2: { halign: "right" }, 3: { halign: "right" } },
    didParseCell: function(data) {
      if (boldRowIndexes.indexOf(data.row.index) !== -1) { data.cell.styles.fontStyle = "bold"; }
    }
  });

  var afterTableY = doc.lastAutoTable.finalY + 10;

  var purchasePrice = currentPropertyData.purchasePrice;
  if (purchasePrice) {
    var annualNOIForRatio = thisMonthNOI * 12;
    var capRate = (annualNOIForRatio / purchasePrice) * 100;
    var expenseRatio = thisMonthTotalRevenue > 0 ? (thisMonthTotalExpenses * 12) / (thisMonthTotalRevenue * 12) * 100 : 0;
    var grm = grossScheduledIncome > 0 ? purchasePrice / (grossScheduledIncome * 12) : 0;

    doc.setFontSize(11);
    doc.setTextColor(0);
    doc.text("Key Financial Ratios", 14, afterTableY);
    doc.setFontSize(9);
    doc.setTextColor(80);
    var ratioLines = [
      "Cap Rate: " + capRate.toFixed(2) + "%     Expense Ratio: " + expenseRatio.toFixed(1) + "%     GRM: " + (grm ? grm.toFixed(2) : "N/A")
    ];
    if (loanAmount > 0) {
      var dscr = ytdDebtService > 0 ? ytdNOI / ytdDebtService : 0;
      var downPayment = currentPropertyData.downPayment || 0;
      var cashOnCash = downPayment > 0 ? (thisMonthCashFlowAfterDebt * 12 / downPayment) * 100 : null;
      ratioLines.push(
        "DSCR: " + dscr.toFixed(2) + (dscr < 1.25 ? " (below typical 1.25 lender minimum)" : "") +
        (cashOnCash !== null ? "     Cash-on-Cash Return: " + cashOnCash.toFixed(2) + "%" : "")
      );
    }
    var annualPropertyTaxForPdf = currentPropertyData.annualPropertyTax || 0;
    var buildingValuePctForPdf = currentPropertyData.buildingValuePct || 0;
    var federalTaxBracketForPdf = currentPropertyData.federalTaxBracket || 0;
    var stateRatePctForPdf = getStateTopMarginalRate(currentPropertyData.state) || 0;
    if (buildingValuePctForPdf > 0 && (federalTaxBracketForPdf > 0 || stateRatePctForPdf > 0)) {
      var depreciationLifeForPdf = (currentPropertyData.units || 1) >= 5 ? 39 : 27.5;
      var annualDepreciationForPdf = purchasePrice * (buildingValuePctForPdf / 100) / depreciationLifeForPdf;
      var annualInterestForPdf = 0;
      if (loanAmount > 0) {
        var balanceStartForPdf = calculateRemainingBalanceWithIO(loanAmount, interestRate, loanTermYears, interestOnlyYears, Math.max(0, monthsElapsedForSelectedMonth - 12));
        var balanceEndForPdf = calculateRemainingBalanceWithIO(loanAmount, interestRate, loanTermYears, interestOnlyYears, monthsElapsedForSelectedMonth);
        annualInterestForPdf = Math.max(0, (ytdMortgagePayments > 0 ? monthlyMortgagePayment * 12 : 0) - (balanceStartForPdf - balanceEndForPdf));
      }
      var estTaxSavingsForPdf = (annualDepreciationForPdf + annualInterestForPdf + annualPropertyTaxForPdf) * ((federalTaxBracketForPdf + stateRatePctForPdf) / 100);
      ratioLines.push(
        "Est. Annual Income Tax Savings: $" + estTaxSavingsForPdf.toLocaleString(undefined, {maximumFractionDigits: 0}) +
        " (depreciation + mortgage interest + property tax x combined " + (federalTaxBracketForPdf + stateRatePctForPdf).toFixed(2) + "% rate - estimate only, not tax advice)"
      );
    }
    doc.text(ratioLines, 14, afterTableY + 7);
    afterTableY += 7 + (ratioLines.length * 5) + 8;
  }

  doc.setFontSize(8);
  doc.setTextColor(140);
  doc.text(
    [
      "Rental Income and the manually-entered Fixed Costs figure use current values applied across all months. Expenses",
      "flagged as Annual (property tax, insurance, etc.) are divided by 12 and spread evenly across every month of the",
      "year, rather than counted entirely in the month logged. Other income and expense categories reflect actual logged",
      "entries. Capital Expenditures are shown separately and excluded from Net Operating Income. Debt Service (if",
      "financing details are on file) reflects a standard amortized Principal & Interest payment.",
      "Projected Annual: Rental Income and Fixed Costs are annualized directly from current values (x 12). Variable",
      "income/expense categories use a run-rate projection - the Year-to-Date pace extrapolated to a full 12 months -",
      "since these vary month to month. Treat this as an estimate based on the pace so far, not a guarantee."
    ],
    14, afterTableY
  );

  var fileSafeAddress = address.replace(/[^a-z0-9]/gi, "_").slice(0, 40);
  doc.save("IncomeStatement_" + fileSafeAddress + "_" + selectedMonth + ".pdf");
}
</script>

__FOOTER__
</body>
</html>"""

propertymanager_html = (PROPERTYMANAGER_TEMPLATE
                        .replace("__CSS__", PAGE_CSS)
                        .replace("__NAV__", NAV_HTML)
                        .replace("__DARKMODE_CSS__", DARK_MODE_CSS)
                        .replace("__DARKMODE_BUTTON__", DARK_MODE_BUTTON)
                        .replace("__DARKMODE_JS__", DARK_MODE_JS)
                        .replace("__LEARNINGMODE_CSS__", LEARNING_MODE_CSS)
                        .replace("__LEARNINGMODE_BUTTON__", LEARNING_MODE_BUTTON)
                        .replace("__LEARNINGMODE_JS__", LEARNING_MODE_JS)
                        .replace("__FOOTER__", FOOTER_HTML)
                        .replace("__STATE_TAX_JS_HELPER__", STATE_TAX_JS_HELPER))

# ------------------- PAGE 8: GLOSSARY -------------------

def glossary_body_html():
    """Builds the full glossary from DEFINITIONS, alphabetized, each term shown with its full
    three-part definition (what it is / what it measures / who calculates it)."""
    items = ""
    for name in sorted(DEFINITIONS.keys(), key=str.lower):
        parts = DEFINITIONS[name].split("\n")
        paras = "".join(f"<p style='margin:2px 0;'>{html_escape_mod.escape(p)}</p>" for p in parts)
        items += f"""
<div class="card" style="min-width:260px;">
  <p class="label" style="font-size:14px;font-weight:600;color:var(--text);">{html_escape_mod.escape(name)}</p>
  {paras}
</div>"""
    return items

GLOSSARY_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Glossary - Stock Digest</title>
<style>__CSS__
__DARKMODE_CSS__
__LEARNINGMODE_CSS__
</style>
</head>
<body>
__DARKMODE_BUTTON__<script>__DARKMODE_JS__</script>
__LEARNINGMODE_BUTTON__<script>__LEARNINGMODE_JS__</script>
__NAV__
<h1>Glossary</h1>
<p class="timestamp">Every indicator, index, and rate used across Stock Digest - what it is, what it measures, and who calculates it.</p>
<div class="row" style="flex-wrap:wrap;">
__GLOSSARY_BODY__
</div>
__FOOTER__
</body>
</html>"""

glossary_html = (GLOSSARY_TEMPLATE
                  .replace("__CSS__", PAGE_CSS)
                  .replace("__NAV__", NAV_HTML)
                  .replace("__DARKMODE_CSS__", DARK_MODE_CSS)
                  .replace("__DARKMODE_BUTTON__", DARK_MODE_BUTTON)
                  .replace("__DARKMODE_JS__", DARK_MODE_JS)
                  .replace("__LEARNINGMODE_CSS__", LEARNING_MODE_CSS)
                  .replace("__LEARNINGMODE_BUTTON__", LEARNING_MODE_BUTTON)
                  .replace("__LEARNINGMODE_JS__", LEARNING_MODE_JS)
                  .replace("__FOOTER__", FOOTER_HTML)
                  .replace("__GLOSSARY_BODY__", glossary_body_html()))

# ------------------- PAGE 9: FOR EDUCATORS & STUDENTS -------------------

# Single place to update the contact address this page uses - change this one line if you'd
# rather route requests somewhere else (a dedicated inbox, a form, etc.).
EDUCATOR_CONTACT_EMAIL = "tonyhernandezusa@gmail.com"

EDUCATORS_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>For Educators &amp; Students - Stock Digest</title>
<style>__CSS__
__DARKMODE_CSS__
__LEARNINGMODE_CSS__
.edu-section { background:var(--card-bg); border:1px solid var(--card-border); border-radius:10px; padding:16px 18px; margin-bottom:16px; }
.edu-section h2 { margin:0 0 8px; font-size:16px; color:var(--text); }
.edu-section p { font-size:13px; line-height:1.6; color:var(--text); margin:0 0 10px; }
.edu-section ul { margin:0 0 10px; padding-left:18px; font-size:13px; line-height:1.7; color:var(--text); }
.edu-cta { display:inline-block; background:#1f4e79; color:#fff; text-decoration:none; font-weight:600; font-size:13px; padding:10px 18px; border-radius:6px; }
</style>
</head>
<body>
__DARKMODE_BUTTON__<script>__DARKMODE_JS__</script>
__LEARNINGMODE_BUTTON__<script>__LEARNINGMODE_JS__</script>
__NAV__
<h1>For Business Educators &amp; Students</h1>
<p class="timestamp">Stock Digest is free to explore, and we're glad to have it used in the classroom.</p>

<div class="edu-section">
<h2>Free Classroom Access for Professors</h2>
<p>If you teach finance, economics, accounting, or business at the high school, community college, or university level, we'll set up free classroom access for you and your students - no cost, no catch. This is a manual, no-verification-hassle process right now: just tell us a bit about your course and we'll get you set up.</p>
<a class="edu-cta" href="mailto:__EDUCATOR_EMAIL__?subject=Classroom%20Access%20Request&amp;body=Course%20name%3A%0ASchool%2Finstitution%3A%0AApproximate%20number%20of%20students%3A%0AWhat%20you%27d%20like%20to%20use%20Stock%20Digest%20for%3A" target="_blank" rel="noopener">Request Classroom Access</a>
</div>

<div class="edu-section">
<h2>Suggested Classroom Uses</h2>
<ul>
<li><strong>Monetary policy &amp; the Fed's dual mandate:</strong> The <a href="index.html">Fed Policy Targets</a> table shows real, current CPI, Core PCE, unemployment, GDP growth, and Fed Funds Rate readings against the Fed's own longer-run targets - a live example for teaching how the FOMC's Summary of Economic Projections works.</li>
<li><strong>Fundamentals vs. market sentiment:</strong> The <a href="index.html">Fundamentals vs. Sentiment Gauge</a> gives students a concrete, numeric way to separate "what the macro data explains" from "what's left over" in a sector's price move - a good jumping-off point for discussing market efficiency and behavioral finance.</li>
<li><strong>Time value of money &amp; loan mechanics:</strong> The <a href="calculators.html">Financial Calculators</a> page (mortgage, auto loan, business valuation, real estate investment) shows students the actual amortization and DSCR math behind the numbers, not just a black-box payment figure.</li>
<li><strong>Building financial vocabulary:</strong> The <a href="glossary.html">Glossary</a> covers every indicator, index, and rate on the site, with what it measures and who publishes it - useful as an assigned reading or reference for an intro finance/econ course.</li>
<li><strong>Real estate &amp; property finance:</strong> The <a href="propertymanager.html">Property Manager</a> and <a href="realestate.html">Real Estate</a> pages work as a live case study for cap rate, cash-on-cash return, and DSCR concepts in a real estate finance course.</li>
</ul>
</div>

<div class="edu-section">
<h2>For Students</h2>
<p>Everything on Stock Digest is free to explore on your own - no login required for most pages. If your professor sets up classroom access, ask them about any course-specific materials or discussion questions they're using alongside it. If you're studying independently and have a question about how a specific calculator or indicator works, the <a href="glossary.html">Glossary</a> and the hover-over definitions throughout the site are a good place to start.</p>
</div>

<p class="note">Stock Digest is an educational and informational tool. Nothing on this site is personalized financial advice or a recommendation to buy or sell any security.</p>

__FOOTER__
</body>
</html>"""

educators_html = (EDUCATORS_TEMPLATE
                   .replace("__CSS__", PAGE_CSS)
                   .replace("__NAV__", NAV_HTML)
                   .replace("__DARKMODE_CSS__", DARK_MODE_CSS)
                   .replace("__DARKMODE_BUTTON__", DARK_MODE_BUTTON)
                   .replace("__DARKMODE_JS__", DARK_MODE_JS)
                   .replace("__LEARNINGMODE_CSS__", LEARNING_MODE_CSS)
                   .replace("__LEARNINGMODE_BUTTON__", LEARNING_MODE_BUTTON)
                   .replace("__LEARNINGMODE_JS__", LEARNING_MODE_JS)
                   .replace("__FOOTER__", FOOTER_HTML)
                   .replace("__EDUCATOR_EMAIL__", EDUCATOR_CONTACT_EMAIL))

# ------------------- PAGE 10: MY PORTFOLIO (SIMPLEST VERSION - ONE PORTFOLIO, ONE EXPERIENCE) -------------------
#
# Reuses the exact same Firebase project, Auth pattern, and login UI already proven out in
# Property Manager - same account works on both pages. Adds one new Firestore collection
# ("portfolios", one doc per user at portfolios/{uid} with a single "tickers" array field)
# rather than a doc-per-ticker model, since a simple array is all this needs for now.
#
# IMPORTANT: when you add the "portfolios" collection, add a matching Firestore security rule
# restricting it to the owner only - e.g.:
#   match /portfolios/{userId} {
#     allow read, write: if request.auth != null && request.auth.uid == userId;
#   }
# Firestore does not automatically extend the rule protecting "properties" to a new collection.
#
# Live prices for each user's own tickers can't be pre-baked at build time (unlike the fixed
# WATCHLIST on the Stocks & Rates page), since we don't know in advance which tickers each user
# will add - so this fetches quotes client-side from the browser, reusing the same Finnhub
# Worker already deployed for Stock Search (GET /stock-profile?symbol=X).

PORTFOLIO_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>My Portfolio - Stock Digest</title>
<script src="https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.14.1/firebase-auth-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.14.1/firebase-firestore-compat.js"></script>
<style>__CSS__
__DARKMODE_CSS__
__LEARNINGMODE_CSS__
.err { color:#c0392b; font-size:13px; margin-top:8px; }
.calc button.secondary { background:#888; }
.calc button.secondary:hover { background:#666; }
.ticker-card { background:var(--card-bg); border:1px solid var(--card-border); border-radius:8px; padding:14px 16px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; }
.ticker-card .remove-btn { background:#fbe0dd; color:#c0392b; border:1px solid #f3c6c2; border-radius:6px; padding:6px 10px; font-size:11px; cursor:pointer; }
.ticker-card .remove-btn:hover { background:#f7cac5; }
</style>
</head>
<body>
__DARKMODE_BUTTON__<script>__DARKMODE_JS__</script>
__LEARNINGMODE_BUTTON__<script>__LEARNINGMODE_JS__</script>
__NAV__
<h1>My Portfolio</h1>
<p class="timestamp">Track your own list of tickers - saved to your account, available wherever you log in.</p>

<div class="beginner-box learning-mode-only">
<h3>&#127891; What This Page Does</h3>
<p style="font-size:13px;line-height:1.6;margin:0;">This is separate from the main Watchlist on the Stocks &amp; Rates page (which is fixed and the same for every visitor). Here, you create your own personal list of tickers, saved to your own account - log in from any device and it's there. Prices update live when you load the page, using the same data source as Stock Search.</p>
</div>

<div class="calc" id="auth-panel">
<h3 id="auth-title">Log In</h3>
<label>Email</label>
<input type="email" id="auth-email">
<label>Password</label>
<input type="password" id="auth-password">
<button onclick="doLogin()">Log In</button>
<button class="secondary" onclick="doSignup()">Create Account</button>
<div class="err" id="auth-error"></div>
<p class="note" style="margin-top:10px;">Uses the same account as Property Manager - if you already have one, log in with the same email and password here.</p>
</div>

<div id="dashboard" style="display:none;">
  <div class="calc">
    <span id="welcome-msg"></span> &nbsp;
    <button class="secondary" onclick="doLogout()" style="margin-top:0;">Log Out</button>
  </div>

  <div class="calc">
    <h3>Add a Ticker</h3>
    <label>Stock or ETF symbol</label>
    <input type="text" id="add-ticker-input" placeholder="e.g. AAPL" style="text-transform:uppercase;">
    <button onclick="addTicker()">Add to My Portfolio</button>
    <div class="err" id="add-ticker-error"></div>
  </div>

  <div class="calc" id="portfolio-summary" style="display:none;"></div>

  <h3>Your Tickers</h3>
  <div id="portfolio-list"><p style="font-size:13px;color:#888;">No tickers yet - add one above.</p></div>
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

// Reuses the same Finnhub Worker already deployed for Stock Search.
var FINNHUB_WORKER_URL = "https://finnhub-proxy.tonyhernandezusa.workers.dev";

var currentUid = null;
var portfolioUnsub = null;

function showAddTickerError(message) {
  document.getElementById("add-ticker-error").textContent = message;
}

function doSignup() {
  var email = document.getElementById("auth-email").value.trim();
  var password = document.getElementById("auth-password").value;
  document.getElementById("auth-error").textContent = "";
  auth.createUserWithEmailAndPassword(email, password).catch(function(err) {
    document.getElementById("auth-error").textContent = err.message;
  });
}

function doLogin() {
  var email = document.getElementById("auth-email").value.trim();
  var password = document.getElementById("auth-password").value;
  document.getElementById("auth-error").textContent = "";
  auth.signInWithEmailAndPassword(email, password).catch(function(err) {
    document.getElementById("auth-error").textContent = err.message;
  });
}

function doLogout() {
  if (portfolioUnsub) { portfolioUnsub(); portfolioUnsub = null; }
  auth.signOut();
}

auth.onAuthStateChanged(function(user) {
  if (user) {
    currentUid = user.uid;
    document.getElementById("auth-panel").style.display = "none";
    document.getElementById("dashboard").style.display = "block";
    document.getElementById("welcome-msg").textContent = "Logged in as " + user.email;
    loadPortfolio(user.uid);
  } else {
    currentUid = null;
    if (portfolioUnsub) { portfolioUnsub(); portfolioUnsub = null; }
    document.getElementById("auth-panel").style.display = "block";
    document.getElementById("dashboard").style.display = "none";
  }
});

function addTicker() {
  var input = document.getElementById("add-ticker-input");
  var ticker = input.value.trim().toUpperCase();
  showAddTickerError("");
  if (!ticker) { showAddTickerError("Enter a ticker symbol first."); return; }
  if (!/^[A-Z.\\-]{1,10}$/.test(ticker)) { showAddTickerError("That doesn't look like a valid ticker symbol."); return; }
  db.collection("portfolios").doc(currentUid).set({
    tickers: firebase.firestore.FieldValue.arrayUnion(ticker)
  }, { merge: true }).then(function() {
    input.value = "";
  }).catch(function(err) {
    showAddTickerError(err.message);
  });
}

function removeTicker(ticker) {
  db.collection("portfolios").doc(currentUid).set({
    tickers: firebase.firestore.FieldValue.arrayRemove(ticker)
  }, { merge: true });
}

function loadPortfolio(uid) {
  if (portfolioUnsub) portfolioUnsub();
  portfolioUnsub = db.collection("portfolios").doc(uid).onSnapshot(function(doc) {
    var tickers = (doc.exists && doc.data().tickers) || [];
    renderPortfolio(tickers);
  });
}

function money(x) {
  if (x === undefined || x === null || x === "") return "N/A";
  return "$" + Number(x).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

async function fetchQuote(ticker) {
  try {
    var resp = await fetch(FINNHUB_WORKER_URL + "/stock-profile?symbol=" + encodeURIComponent(ticker));
    var data = await resp.json();
    if (data.error) return { ticker: ticker, error: data.error };
    return { ticker: ticker, profile: data.profile || {}, quote: data.quote || {} };
  } catch (e) {
    return { ticker: ticker, error: "Could not fetch data for this ticker." };
  }
}

async function renderPortfolio(tickers) {
  var listEl = document.getElementById("portfolio-list");
  var summaryEl = document.getElementById("portfolio-summary");
  if (!tickers.length) {
    listEl.innerHTML = "<p style='font-size:13px;color:#888;'>No tickers yet - add one above.</p>";
    summaryEl.style.display = "none";
    return;
  }
  listEl.innerHTML = "<p style='font-size:13px;color:#888;'>Loading live prices...</p>";

  var results = await Promise.all(tickers.map(fetchQuote));

  var cardsHtml = "";
  var validChanges = [];
  var sectorCounts = {};
  results.forEach(function(r) {
    if (r.error) {
      cardsHtml += "<div class='ticker-card'><div><strong>" + r.ticker + "</strong><br><span style='font-size:12px;color:#c0392b;'>" + r.error + "</span></div>" +
        "<button class='remove-btn' onclick=\\"removeTicker('" + r.ticker + "')\\">Remove</button></div>";
      return;
    }
    var q = r.quote, p = r.profile;
    var dp = q.dp;
    var changeColor = (q.d || 0) >= 0 ? "#1a8a3d" : "#c0392b";
    if (typeof dp === "number") validChanges.push(dp);
    var sector = p.finnhubIndustry || "Unclassified";
    sectorCounts[sector] = (sectorCounts[sector] || 0) + 1;
    cardsHtml += "<div class='ticker-card'>" +
      "<div><strong>" + r.ticker + "</strong> - " + (p.name || "") + "<br>" +
      "<span style='font-size:12px;color:#666;'>" + sector + "</span></div>" +
      "<div style='text-align:right;'><div style='font-size:16px;font-weight:700;'>" + money(q.c) + "</div>" +
      "<div style='font-size:12px;font-weight:600;color:" + changeColor + ";'>" + (q.d >= 0 ? "+" : "") +
      (q.d !== undefined ? q.d.toFixed(2) : "N/A") + " (" + (dp !== undefined ? dp.toFixed(2) : "N/A") + "%)</div></div>" +
      "<button class='remove-btn' onclick=\\"removeTicker('" + r.ticker + "')\\">Remove</button></div>";
  });
  listEl.innerHTML = cardsHtml;

  if (validChanges.length) {
    var avgChange = validChanges.reduce(function(a, b) { return a + b; }, 0) / validChanges.length;
    var avgColor = avgChange >= 0 ? "#1a8a3d" : "#c0392b";
    var sectorLines = Object.keys(sectorCounts).sort(function(a, b) { return sectorCounts[b] - sectorCounts[a]; })
      .map(function(s) { return s + ": " + sectorCounts[s] + " of " + results.length; }).join(" &middot; ");
    summaryEl.style.display = "block";
    summaryEl.innerHTML = "<h3>Portfolio Summary</h3>" +
      "<p style='margin:4px 0;'>Average change today across your " + results.length + " ticker(s): " +
      "<strong style='color:" + avgColor + ";'>" + (avgChange >= 0 ? "+" : "") + avgChange.toFixed(2) + "%</strong></p>" +
      "<p style='font-size:12px;color:#666;margin:4px 0;'>By sector: " + sectorLines + "</p>" +
      "<p class='note' style='margin-top:8px;'>A simple average across your holdings, not weighted by position size (this page doesn't track how many shares you own, only which tickers you follow).</p>";
  } else {
    summaryEl.style.display = "none";
  }
}
</script>
__FOOTER__
</body>
</html>"""

portfolio_html = (PORTFOLIO_TEMPLATE
                   .replace("__CSS__", PAGE_CSS)
                   .replace("__NAV__", NAV_HTML)
                   .replace("__DARKMODE_CSS__", DARK_MODE_CSS)
                   .replace("__DARKMODE_BUTTON__", DARK_MODE_BUTTON)
                   .replace("__DARKMODE_JS__", DARK_MODE_JS)
                   .replace("__LEARNINGMODE_CSS__", LEARNING_MODE_CSS)
                   .replace("__LEARNINGMODE_BUTTON__", LEARNING_MODE_BUTTON)
                   .replace("__LEARNINGMODE_JS__", LEARNING_MODE_JS)
                   .replace("__FOOTER__", FOOTER_HTML))

# ------------------- PAGE 12: COUNTY INVESTMENT MAP -------------------
#
# First layer: 5-year county population growth (Census ACS, see fetch_census_county_population()
# above). More layers (unemployment, income, home price appreciation, building permits) and the
# Investment Opportunity Score are a planned fast-follow, not included in this first pass - see
# the note in the page's methodology section.
#
# Architecture: county boundaries (TopoJSON, ~3,143 counties) and the D3/topojson-client
# rendering libraries load from CDNs at runtime, same pattern as Chart.js/jsPDF/Firebase
# elsewhere on this site. This page's own per-county data (county_data.json) is generated here
# at build time and fetched by the browser alongside the boundary file.

county_data_json = json.dumps(county_population_data) if county_population_data else "null"

def _with_territory_properties(geojson, territory_name):
    """Stamp every feature in a territory's GeoJSON with STATE/COUNTY/NAME properties matching
    the TERRITORY_FIPS convention, so the same client-side fipsKey lookup (STATE + COUNTY) used
    for the mainland and Puerto Rico works identically here - these source files ship with empty
    properties since the whole territory is treated as a single data unit, not per-island."""
    if not geojson:
        return None
    fips = TERRITORY_FIPS[territory_name]
    stamped = []
    for feat in geojson["features"]:
        new_feat = dict(feat)
        new_feat["properties"] = {"STATE": fips, "COUNTY": "000", "NAME": territory_name}
        stamped.append(new_feat)
    return {"type": "FeatureCollection", "features": stamped}

# U.S. Virgin Islands joins the same map as Puerto Rico rather than getting its own - they're
# geographically adjacent (both in the northeast Caribbean, within about 3 degrees of longitude
# of each other) so a single combined projection fits both reasonably well without distortion.
_usvi_stamped = _with_territory_properties(territory_geojson.get("U.S. Virgin Islands"), "U.S. Virgin Islands")
if puerto_rico_geojson and _usvi_stamped:
    puerto_rico_geojson = {
        "type": "FeatureCollection",
        "features": puerto_rico_geojson["features"] + _usvi_stamped["features"],
    }
elif _usvi_stamped and not puerto_rico_geojson:
    puerto_rico_geojson = _usvi_stamped

# Guam and the Northern Mariana Islands are both in the Mariana Islands chain, close enough
# together to share one small map. American Samoa is thousands of miles further south in the
# Pacific and needs its own separate map - combining it with Guam/CNMI would force a projection
# spanning most of the Pacific Ocean, making all three islands tiny and hard to see.
_guam_stamped = _with_territory_properties(territory_geojson.get("Guam"), "Guam")
_cnmi_stamped = _with_territory_properties(territory_geojson.get("Northern Mariana Islands"), "Northern Mariana Islands")
mariana_geojson = None
if _guam_stamped or _cnmi_stamped:
    mariana_geojson = {
        "type": "FeatureCollection",
        "features": (_guam_stamped["features"] if _guam_stamped else []) + (_cnmi_stamped["features"] if _cnmi_stamped else []),
    }

american_samoa_geojson = _with_territory_properties(territory_geojson.get("American Samoa"), "American Samoa")

pr_geojson_json = json.dumps(puerto_rico_geojson) if puerto_rico_geojson else "null"
mariana_geojson_json = json.dumps(mariana_geojson) if mariana_geojson else "null"
american_samoa_geojson_json = json.dumps(american_samoa_geojson) if american_samoa_geojson else "null"


INVESTMENT_MAP_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>County Investment Map - Stock Digest</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js"></script>
<style>__CSS__
__DARKMODE_CSS__
__LEARNINGMODE_CSS__
#map-wrap { position:relative; background:var(--card-bg); border:1px solid var(--card-border); border-radius:10px; padding:12px; }
#county-map { width:100%; height:auto; }
#county-map path.county { stroke:#fff; stroke-width:0.3; cursor:pointer; }
#county-map path.county:hover { stroke:#111; stroke-width:1; }
#county-map path.state-border { fill:none; stroke:#555; stroke-width:0.7; pointer-events:none; }
#map-tooltip { position:fixed; display:none; background:#111; color:#fff; font-size:12px; padding:6px 10px; border-radius:6px; pointer-events:none; z-index:1000; max-width:220px; }
#map-legend { display:flex; align-items:center; flex-wrap:wrap; gap:12px; font-size:11px; color:var(--text); margin-top:10px; }
#map-legend, #pr-map-legend, #mariana-map-legend, #american-samoa-map-legend { display:flex; align-items:center; flex-wrap:wrap; gap:12px; font-size:11px; color:var(--text); margin-top:10px; } .legend-item { display:flex; align-items:center; gap:4px; white-space:nowrap; } .swatch { width:16px; height:12px; display:inline-block; border-radius:2px; border:1px solid rgba(0,0,0,0.15); } { display:flex; align-items:center; gap:4px; white-space:nowrap; }
#map-legend .swatch { width:16px; height:12px; display:inline-block; border-radius:2px; border:1px solid rgba(0,0,0,0.15); }
#map-loading { text-align:center; padding:40px; font-size:13px; color:var(--text-secondary); }
#layer-toggle { display:flex; gap:8px; margin-bottom:12px; }
#layer-toggle button { padding:8px 14px; border-radius:8px; border:1px solid var(--card-border); background:var(--card-bg); color:var(--text); cursor:pointer; font-size:13px; font-weight:600; }
#layer-toggle button.active { background:#1f4e79; color:#fff; border-color:#1f4e79; }
</style>
</head>
<body>
__DARKMODE_BUTTON__<script>__DARKMODE_JS__</script>
__LEARNINGMODE_BUTTON__<script>__LEARNINGMODE_JS__</script>
__NAV__
<h1>County Investment Map</h1>
<p class="timestamp">Population growth, unemployment, median home value, median rent, median household income, and building permits by U.S. county.</p>

<div class="beginner-box learning-mode-only">
<h3>&#127891; What This Map Shows</h3>
<p style="font-size:13px;line-height:1.6;margin:0;">Switch between the buttons above to see different views of the same counties: population and housing-unit growth over the last 5 years (green = growing, red = shrinking), current unemployment rate (green = lower/better, red = higher/worse), median home value, rent, and household income (dollar figures shown on neutral scales - darker just means a higher number, not "better"), new building permits and permit growth (construction activity and its year-over-year trend), the mix of new construction (single-family vs. multifamily), and vacancy figures (structural survey estimates, not live listings). Some layers are shown as rates (per 1,000 housing units, or as a percentage) rather than raw counts, so a small fast-growing county isn't dwarfed by a huge slow-growing one just because it's smaller. Each layer is one input real estate investors watch, but each is one factor among many, not a standalone signal.</p>
</div>

<div id="layer-toggle">
  <button id="layer-btn-growth" class="active" onclick="setLayer('growth')">Population Growth</button>
  <button id="layer-btn-unemployment" onclick="setLayer('unemployment')">Unemployment Rate</button>
  <button id="layer-btn-homevalue" onclick="setLayer('homevalue')">Median Home Value</button>
  <button id="layer-btn-rent" onclick="setLayer('rent')">Median Rent</button>
  <button id="layer-btn-income" onclick="setLayer('income')">Median Household Income</button>
  <button id="layer-btn-permits" onclick="setLayer('permits')">Building Permits</button>
  <button id="layer-btn-housinggrowth" onclick="setLayer('housinggrowth')">Housing-Unit Growth</button>
  <button id="layer-btn-permitgrowth" onclick="setLayer('permitgrowth')">Permit Growth (YoY)</button>
  <button id="layer-btn-multifamilyshare" onclick="setLayer('multifamilyshare')">Multifamily Share</button>
  <button id="layer-btn-vacantforsale" onclick="setLayer('vacantforsale')">Vacant Homes For Sale</button>
  <button id="layer-btn-totalvacancy" onclick="setLayer('totalvacancy')">Total Vacancy Rate</button>
</div>

<div id="map-wrap">
  <div id="map-loading">Loading county boundaries and data...</div>
  <svg id="county-map" viewBox="0 0 975 610" style="display:none;"></svg>
  <div id="map-tooltip"></div>
</div>
<div id="map-legend"></div>

<h2 style="margin-top:28px;font-size:18px;">Puerto Rico &amp; U.S. Virgin Islands</h2>
<p class="timestamp">Same six layers, same toggle above - shown separately since they don't fit the mainland map's projection. Puerto Rico's 78 municipios are individually mapped; the U.S. Virgin Islands is shown as a single territory-wide figure (see note below).</p>
<div id="pr-map-wrap" style="position:relative; background:var(--card-bg); border:1px solid var(--card-border); border-radius:10px; padding:12px; max-width:500px;">
  <div id="pr-map-loading" style="text-align:center; padding:30px; font-size:13px; color:var(--text-secondary);">Loading map...</div>
  <svg id="pr-map" viewBox="0 0 500 260" style="display:none; width:100%; height:auto;"></svg>
</div>
<div id="pr-map-legend"></div>
<p class="note" style="margin-top:4px;">On the dollar-figure and building-permit layers, this map uses a territory-wide color scale rather than the mainland scale above - figures here run considerably lower (Puerto Rico) to considerably higher (parts of the Virgin Islands) than typical mainland ranges, so a shared scale would show almost every area at the same end regardless of real differences.</p>

<h2 style="margin-top:28px;font-size:18px;">Guam &amp; Northern Mariana Islands</h2>
<p class="timestamp">Shown together as they're both part of the Mariana Islands chain. Each is a single territory-wide figure, not broken out by island or village - see note below.</p>
<div id="mariana-map-wrap" style="position:relative; background:var(--card-bg); border:1px solid var(--card-border); border-radius:10px; padding:12px; max-width:500px;">
  <div id="mariana-map-loading" style="text-align:center; padding:30px; font-size:13px; color:var(--text-secondary);">Loading map...</div>
  <svg id="mariana-map" viewBox="0 0 500 320" style="display:none; width:100%; height:auto;"></svg>
</div>
<div id="mariana-map-legend"></div>

<h2 style="margin-top:28px;font-size:18px;">American Samoa</h2>
<p class="timestamp">Shown on its own map since it's thousands of miles from Guam/CNMI in the Pacific. A single territory-wide figure, not broken out by island or district.</p>
<div id="american-samoa-map-wrap" style="position:relative; background:var(--card-bg); border:1px solid var(--card-border); border-radius:10px; padding:12px; max-width:500px;">
  <div id="american-samoa-map-loading" style="text-align:center; padding:30px; font-size:13px; color:var(--text-secondary);">Loading map...</div>
  <svg id="american-samoa-map" viewBox="0 0 500 260" style="display:none; width:100%; height:auto;"></svg>
</div>
<div id="american-samoa-map-legend"></div>
<p class="note" style="margin-top:4px;">Unlike every other layer on this page, American Samoa, Guam, CNMI, and the U.S. Virgin Islands are shown as a single figure for the whole territory rather than broken down by county or municipio - these territories are small enough (47,000 to 154,000 residents each) that further subdividing wouldn't add much. They're also not covered by the American Community Survey the way the mainland and Puerto Rico are; population, income, and home value come from the 2020 Island Areas Census instead and won't update again until the 2030 census. Rent is the one exception - it uses HUD's Fair Market Rent estimate, which HUD does publish annually for these territories, so it's more current than the other figures here. These four territories don't have a building permits figure at all currently.</p>

<p class="note" style="margin-top:14px;">
<strong>Methodology:</strong> Population, housing-unit growth, median home value, median rent, median household income, vacant homes for sale, and total vacancy rate figures are from the Census Bureau's American Community Survey 5-Year Estimates (2019-2023 vintage; population and housing-unit growth compare that to the 2014-2018 vintage). Housing-Unit Growth measures the actual change in the housing stock over 5 years - homes that have actually been built and occupied or made available, as opposed to Building Permits, which measures construction requests that may not yet be completed. Vacant Homes For Sale and Total Vacancy Rate are both structural, once-every-5-years survey estimates - NOT live listing counts, and not equivalent to current MLS, Realtor.com, or Zillow active inventory; treat them as slow-moving structural comparisons between counties, not a current-month market-timing signal. Vacant Homes For Sale isolates only units classified as vacant and for sale (shown per 1,000 housing units); Total Vacancy Rate is the broader figure, covering units vacant for any reason - for rent, for sale, seasonal/vacation use, and more (shown as a % of the housing stock) - so it will always read notably higher than the For Sale figure alone, and the two aren't meant to be compared directly on the same scale. Unemployment rates are from the Bureau of Labor Statistics' Local Area Unemployment Statistics program, showing each county's most recent available month. Building permits are new housing units authorized in the most recent full calendar year (Census Building Permits Survey), shown per 1,000 housing units using the housing-unit figure above (a different data vintage than the permits year, so treat this as an approximation, not an exact same-year ratio). Permit Growth (YoY) compares that same annual permits count to the prior year, from the same Census Building Permits Survey - a rising figure means construction activity is accelerating, a falling figure means builders are pulling back; in smaller counties, a handful of additional permits can swing this percentage widely, so treat outsized moves in low-population counties with extra caution. Multifamily Share shows what portion of that same year's new permits are for multifamily structures (2+ units, including apartment and condo buildings) versus single-family homes, from the same Census Building Permits Survey - this describes the character of new construction, not whether it's good or bad for any particular investor's strategy. Counties with no available data for the selected layer are shown in gray. This is eleven data layers of a planned multi-factor County Investment Map - a housing affordability layer and a documented, transparent Investment Opportunity Score are planned additions, not yet included here. <strong>This map is an educational and informational tool, not a recommendation to buy, sell, or invest in property in any specific location.</strong> None of these figures alone indicates whether an area is a good investment - consult a licensed real estate professional and do your own diligence before making any investment decision.
</p>

<h2 style="margin-top:28px;">County Ranking Table</h2>
<p class="timestamp">Sortable list of every county with data for the currently selected layer above - switch layers with the buttons at the top of the page and this table updates to match. Useful for finding the actual top or bottom counties rather than reading colors off the map.</p>
<div style="margin-bottom:10px;">
  <input type="text" id="ranking-search" placeholder="Search county or municipio name..." oninput="renderRankingTable()" style="padding:8px;font-size:13px;border:1px solid var(--card-border);border-radius:6px;width:280px;max-width:100%;background:var(--card-bg);color:var(--text);">
  <span id="ranking-count" style="margin-left:10px;font-size:12px;color:var(--text-secondary);"></span>
</div>
<div id="ranking-table-container"></div>

<script>
var COUNTY_DATA = __COUNTY_DATA_JSON__;
var currentLayer = "growth";
var countyPaths = null; // set once the map itself has rendered, reused when the layer toggles
var PR_GEOJSON = __PR_GEOJSON__;
var prPaths = null; // same idea as countyPaths, for the separate Puerto Rico (+ USVI) map
var MARIANA_GEOJSON = __MARIANA_GEOJSON__;
var marianaPaths = null; // Guam + Northern Mariana Islands, sharing one small map
var AMERICAN_SAMOA_GEOJSON = __AMERICAN_SAMOA_GEOJSON__;
var americanSamoaPaths = null; // American Samoa, far enough from Guam/CNMI to need its own map

function fipsKey(id) {
  return String(id).padStart(5, "0");
}

function colorForGrowth(pct) {
  if (pct === null || pct === undefined || isNaN(pct)) return "#ccc";
  var clamped = Math.max(-10, Math.min(20, pct));
  var t = (clamped + 10) / 30; // 0 at -10%, 1 at +20%
  return d3.interpolateRdYlGn(t);
}

function colorForPermitGrowth(pct) {
  if (pct === null || pct === undefined || isNaN(pct)) return "#ccc";
  // Year-over-year permit counts swing far more than population or housing-stock growth,
  // especially in smaller counties where a handful of new permits can look like a huge percentage
  // move - so this uses a wider clamp range (-50%..+100%) than colorForGrowth's -10%..+20%,
  // rather than reusing that tighter scale and having nearly every county read as fully
  // saturated red or green.
  var clamped = Math.max(-50, Math.min(100, pct));
  var t = (clamped + 50) / 150; // 0 at -50%, 1 at +100%
  return d3.interpolateRdYlGn(t);
}

function colorForMultifamilyShare(pct) {
  if (pct === null || pct === undefined || isNaN(pct)) return "#ccc";
  // Neutral sequential scale, not diverging red-green - a high or low multifamily share isn't
  // inherently "good" or "bad" for an investor, just a description of what's being built (houses
  // vs. apartment buildings). Runs 0-100% directly since this is already a percentage, unlike the
  // dollar-figure layers above that needed a clamped range. Uses BuPu (a hue not already used by
  // any other layer on this map) so it reads as its own distinct category at a glance.
  var t = Math.max(0, Math.min(100, pct)) / 100;
  return d3.interpolateBuPu(t);
}

function vacantForSaleRate(rec) {
  if (!rec || rec.vacant_for_sale === null || rec.vacant_for_sale === undefined) return null;
  if (!rec.housing_units || rec.housing_units <= 0) return null; // can't compute a rate without a housing-stock denominator
  return (rec.vacant_for_sale / rec.housing_units) * 1000;
}

function colorForVacantForSale(rate) {
  if (rate === null || rate === undefined || isNaN(rate)) return "#ccc";
  // Sequential scale (not diverging red-green), similar treatment to permits-per-capita above -
  // a higher rate can suggest softer demand relative to the housing stock, but this is a single
  // structural, once-every-5-years survey estimate (not a live listing count), so it's shown as
  // an intensity gradient rather than a strict good/bad judgment. Reds is a hue not already used
  // by any other layer on this map.
  var clamped = Math.max(0, Math.min(20, rate));
  var t = clamped / 20;
  return d3.interpolateReds(t);
}

function totalVacancyRate(rec) {
  if (!rec || rec.vacant_total === null || rec.vacant_total === undefined) return null;
  if (!rec.housing_units || rec.housing_units <= 0) return null; // can't compute a rate without a housing-stock denominator
  return (rec.vacant_total / rec.housing_units) * 100;
}

function colorForTotalVacancy(pct) {
  if (pct === null || pct === undefined || isNaN(pct)) return "#ccc";
  // Sequential scale, same treatment as Vacant Homes For Sale above but a distinct hue (OrRd,
  // orange-to-red) so the two related-but-different vacancy layers are visually distinguishable
  // from one another at a glance. Total vacancy naturally runs quite a bit higher than the
  // for-sale-only subset (it includes seasonal/vacation homes, units for rent, etc.), so this
  // uses a wider 0-30% clamp range rather than Vacant Homes For Sale's tighter per-1,000 scale.
  var clamped = Math.max(0, Math.min(30, pct));
  var t = clamped / 30;
  return d3.interpolateOrRd(t);
}

function colorForUnemployment(rate) {
  if (rate === null || rate === undefined || isNaN(rate)) return "#ccc";
  var clamped = Math.max(2, Math.min(12, rate));
  var t = 1 - ((clamped - 2) / 10); // inverted: low unemployment (2%) = green, high (12%) = red
  return d3.interpolateRdYlGn(t);
}

function colorForHomeValue(value) {
  if (value === null || value === undefined || isNaN(value)) return "#ccc";
  // Neutral sequential scale (not red-green) - high value isn't "good" or "bad," just higher.
  // Clamped 50k-1M covers the large majority of US counties without a few ultra-high-cost
  // outliers (e.g. San Francisco, Manhattan) compressing the rest of the country to one color.
  var clamped = Math.max(50000, Math.min(1000000, value));
  var t = (clamped - 50000) / 950000;
  return d3.interpolateBlues(t);
}

function colorForRent(value) {
  if (value === null || value === undefined || isNaN(value)) return "#ccc";
  // Same neutral-scale reasoning as home value, using a distinct hue (purple, not blue) so the
  // two "no inherent good/bad direction" layers stay visually distinguishable from each other.
  var clamped = Math.max(500, Math.min(2500, value));
  var t = (clamped - 500) / 2000;
  return d3.interpolatePurples(t);
}

function colorForIncome(value) {
  if (value === null || value === undefined || isNaN(value)) return "#ccc";
  // Same neutral-scale reasoning, using a third distinct hue (orange) so all three dollar-figure
  // layers (home value/rent/income) stay visually distinguishable from one another.
  var clamped = Math.max(30000, Math.min(150000, value));
  var t = (clamped - 30000) / 120000;
  return d3.interpolateOranges(t);
}

// Puerto Rico's dollar-figure ranges run considerably lower than the mainland's (median
// household income roughly half the lowest mainland state's, for example) - using the mainland
// clamp ranges above would push nearly every municipio to the very bottom of the scale, reading
// as uniformly pale or gray even though real variation exists between municipios. These variants
// use ranges scaled to cover Puerto Rico and the four other U.S. territories on this map
// (American Samoa, Guam, CNMI, USVI) instead - Guam and USVI in particular run notably higher
// than Puerto Rico on income/home value/rent, so the ranges are wide enough to fit all five
// without clipping the higher end. Building permits per capita is likewise lower island-wide,
// given considerably less new construction activity than fast-growing mainland suburbs in
// recent years (though the four newer territories don't have a permits figure at all yet, so
// this only actually applies to Puerto Rico's municipios in practice).
function colorForHomeValuePR(value) {
  if (value === null || value === undefined || isNaN(value)) return "#ccc";
  var clamped = Math.max(60000, Math.min(300000, value));
  var t = (clamped - 60000) / 240000;
  return d3.interpolateBlues(t);
}

function colorForRentPR(value) {
  if (value === null || value === undefined || isNaN(value)) return "#ccc";
  var clamped = Math.max(350, Math.min(1800, value));
  var t = (clamped - 350) / 1450;
  return d3.interpolatePurples(t);
}

function colorForIncomePR(value) {
  if (value === null || value === undefined || isNaN(value)) return "#ccc";
  var clamped = Math.max(15000, Math.min(60000, value));
  var t = (clamped - 15000) / 45000;
  return d3.interpolateOranges(t);
}

function colorForPermitsPR(perCapita) {
  if (perCapita === null || perCapita === undefined || isNaN(perCapita)) return "#ccc";
  var clamped = Math.max(0, Math.min(10, perCapita));
  var t = clamped / 10;
  return d3.interpolateGreens(t);
}

function permitsPerHousingUnit(rec) {
  if (!rec || rec.building_permits === null || rec.building_permits === undefined) return null;
  if (!rec.housing_units || rec.housing_units <= 0) return null; // can't compute a rate without a housing-stock denominator
  return (rec.building_permits / rec.housing_units) * 1000;
}

function colorForPermits(perCapita) {
  if (perCapita === null || perCapita === undefined || isNaN(perCapita)) return "#ccc";
  // Neutral scale, distinct hue (green) from the diverging red-green used for growth/unemployment -
  // this uses a single-hue sequential Greens scale, not the diverging RdYlGn, so it doesn't
  // accidentally read as "green = good" the same way the two rate layers do.
  var clamped = Math.max(0, Math.min(40, perCapita));
  var t = clamped / 40;
  return d3.interpolateGreens(t);
}

function colorForCounty(rec, isPR) {
  if (!rec) return "#ccc";
  if (currentLayer === "growth") return colorForGrowth(rec.growth_pct);
  if (currentLayer === "unemployment") return colorForUnemployment(rec.unemployment_rate);
  if (currentLayer === "homevalue") return isPR ? colorForHomeValuePR(rec.median_home_value) : colorForHomeValue(rec.median_home_value);
  if (currentLayer === "rent") return isPR ? colorForRentPR(rec.median_rent) : colorForRent(rec.median_rent);
  if (currentLayer === "income") return isPR ? colorForIncomePR(rec.median_income) : colorForIncome(rec.median_income);
  if (currentLayer === "housinggrowth") return colorForGrowth(rec.housing_growth_pct);
  if (currentLayer === "permitgrowth") return colorForPermitGrowth(rec.permit_growth_pct);
  if (currentLayer === "multifamilyshare") return colorForMultifamilyShare(rec.multifamily_share_pct);
  if (currentLayer === "vacantforsale") return colorForVacantForSale(vacantForSaleRate(rec));
  if (currentLayer === "totalvacancy") return colorForTotalVacancy(totalVacancyRate(rec));
  return isPR ? colorForPermitsPR(permitsPerHousingUnit(rec)) : colorForPermits(permitsPerHousingUnit(rec));
}

function formatMoney(n) {
  return "$" + Math.round(n).toLocaleString();
}

// Returns { raw, formatted } for whichever layer is currently selected, given one county's
// record. "raw" is a plain number used for sorting; "formatted" is the same display string
// already used in the map's own tooltips, kept consistent so the ranking table below never
// disagrees with what hovering the map shows. Reuses the same rate-computing helper functions
// (vacantForSaleRate, totalVacancyRate, permitsPerHousingUnit) already defined above rather than
// recalculating anything - this function only decides which one applies to which layer and how
// to format the result.
function getLayerValue(rec, layer) {
  if (!rec) return { raw: null, formatted: "N/A" };
  var raw = null, formatted = "N/A";
  function pctStr(v) { return (v > 0 ? "+" : "") + v.toFixed(1) + "%"; }
  if (layer === "growth") {
    raw = rec.growth_pct;
  } else if (layer === "unemployment") {
    raw = rec.unemployment_rate;
    if (raw !== null && raw !== undefined) formatted = raw.toFixed(1) + "%";
  } else if (layer === "homevalue") {
    raw = rec.median_home_value;
    if (raw !== null && raw !== undefined) formatted = formatMoney(raw);
  } else if (layer === "rent") {
    raw = rec.median_rent;
    if (raw !== null && raw !== undefined) formatted = formatMoney(raw) + "/mo";
  } else if (layer === "income") {
    raw = rec.median_income;
    if (raw !== null && raw !== undefined) formatted = formatMoney(raw);
  } else if (layer === "housinggrowth") {
    raw = rec.housing_growth_pct;
  } else if (layer === "permitgrowth") {
    raw = rec.permit_growth_pct;
  } else if (layer === "multifamilyshare") {
    raw = rec.multifamily_share_pct;
    if (raw !== null && raw !== undefined) formatted = raw.toFixed(0) + "%";
  } else if (layer === "vacantforsale") {
    raw = vacantForSaleRate(rec);
    if (raw !== null && raw !== undefined) formatted = raw.toFixed(1) + " per 1,000 housing units";
  } else if (layer === "totalvacancy") {
    raw = totalVacancyRate(rec);
    if (raw !== null && raw !== undefined) formatted = raw.toFixed(1) + "%";
  } else {
    raw = permitsPerHousingUnit(rec); // "permits" fallback, matches colorForCounty's own fallback
    if (raw !== null && raw !== undefined) formatted = raw.toFixed(1) + " per 1,000 housing units";
  }
  // The three percentage-growth layers (growth, housinggrowth, permitgrowth) all share the same
  // "+X.X%" formatting, so it's handled once here rather than repeated in each branch above.
  if ((layer === "growth" || layer === "housinggrowth" || layer === "permitgrowth") && raw !== null && raw !== undefined) {
    formatted = pctStr(raw);
  }
  if (raw === null || raw === undefined || isNaN(raw)) return { raw: null, formatted: "N/A" };
  return { raw: raw, formatted: formatted };
}

var rankingSortColumn = "value";
var rankingSortDir = "desc";

function setRankingSort(column) {
  if (rankingSortColumn === column) {
    rankingSortDir = rankingSortDir === "desc" ? "asc" : "desc";
  } else {
    rankingSortColumn = column;
    rankingSortDir = column === "name" ? "asc" : "desc";
  }
  renderRankingTable();
}

function renderRankingTable() {
  var container = document.getElementById("ranking-table-container");
  var countEl = document.getElementById("ranking-count");
  if (!container || !countEl) return;
  if (!COUNTY_DATA) {
    container.innerHTML = "<span style='font-size:12px;color:var(--text-secondary);'>County data is temporarily unavailable.</span>";
    return;
  }
  var searchBox = document.getElementById("ranking-search");
  var searchTerm = searchBox ? searchBox.value.trim().toLowerCase() : "";

  var rows = [];
  Object.keys(COUNTY_DATA).forEach(function(fips) {
    var rec = COUNTY_DATA[fips];
    var lv = getLayerValue(rec, currentLayer);
    if (lv.raw === null) return; // skip entries with no data for the currently selected layer
    var name = rec.name || fips;
    if (searchTerm && name.toLowerCase().indexOf(searchTerm) === -1) return;
    rows.push({ name: name, raw: lv.raw, formatted: lv.formatted });
  });

  rows.sort(function(a, b) {
    if (rankingSortColumn === "name") {
      return rankingSortDir === "asc" ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
    }
    return rankingSortDir === "desc" ? b.raw - a.raw : a.raw - b.raw;
  });

  countEl.textContent = rows.length.toLocaleString() + " counties/municipios with data for this layer" + (searchTerm ? " matching " + JSON.stringify(searchTerm) : "");

  var nameArrow = rankingSortColumn === "name" ? (rankingSortDir === "asc" ? " \u25B2" : " \u25BC") : "";
  var valueArrow = rankingSortColumn === "value" ? (rankingSortDir === "asc" ? " \u25B2" : " \u25BC") : "";
  var html = "<div class='table-wrap'><table><tr>" +
    "<th style='cursor:pointer;' onclick=\"setRankingSort('name')\">County / Municipio" + nameArrow + "</th>" +
    "<th style='text-align:right;cursor:pointer;' onclick=\"setRankingSort('value')\">Value" + valueArrow + "</th>" +
    "</tr>";
  // Cap the rendered rows for performance - with search/sort already narrowing things down,
  // showing the top 500 of whatever's currently sorted/filtered covers every realistic use case
  // (finding the top or bottom counties for a layer) without asking the browser to build and
  // hold several thousand table rows in the DOM at once for a view nobody scrolls that deep into.
  var displayRows = rows.slice(0, 500);
  displayRows.forEach(function(r) {
    html += "<tr><td>" + r.name + "</td><td style='text-align:right;'>" + r.formatted + "</td></tr>";
  });
  html += "</table></div>";
  if (rows.length > displayRows.length) {
    html += "<p class='note' style='margin-top:6px;'>Showing the top " + displayRows.length + " of " + rows.length.toLocaleString() + " matching rows for this sort order - narrow your search or change the sort to see others.</p>";
  }
  container.innerHTML = html;
}

function renderLegend() {
  var html = "<div class='legend-item'><span class='swatch' style='background:#ccc;'></span><span>No data</span></div>";
  if (currentLayer === "growth") {
    [-10, -5, 0, 5, 10, 15, 20].forEach(function(v) {
      var label = (v > 0 ? "+" : "") + v + "%";
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForGrowth(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>5-yr population growth</span>";
  } else if (currentLayer === "unemployment") {
    [2, 4, 6, 8, 10, 12].forEach(function(v) {
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForUnemployment(v) + ";'></span><span>" + v + "%</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>unemployment rate (lower is greener)</span>";
  } else if (currentLayer === "homevalue") {
    [50000, 150000, 300000, 500000, 750000, 1000000].forEach(function(v) {
      var label = v >= 1000000 ? "$1M+" : "$" + Math.round(v / 1000) + "K";
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForHomeValue(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>median home value (darker = higher, not &quot;better&quot;)</span>";
  } else if (currentLayer === "rent") {
    [500, 900, 1300, 1700, 2100, 2500].forEach(function(v) {
      var label = v >= 2500 ? "$2.5K+" : "$" + Math.round(v);
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForRent(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>median rent (darker = higher, not &quot;better&quot;)</span>";
  } else if (currentLayer === "income") {
    [30000, 55000, 80000, 105000, 130000, 150000].forEach(function(v) {
      var label = v >= 150000 ? "$150K+" : "$" + Math.round(v / 1000) + "K";
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForIncome(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>median household income (darker = higher, not &quot;better&quot;)</span>";
  } else if (currentLayer === "housinggrowth") {
    [-10, -5, 0, 5, 10, 15, 20].forEach(function(v) {
      var label = (v > 0 ? "+" : "") + v + "%";
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForGrowth(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>5-yr housing-unit growth (new supply added, not just permitted)</span>";
  } else if (currentLayer === "permitgrowth") {
    [-50, -25, 0, 25, 50, 75, 100].forEach(function(v) {
      var label = (v > 0 ? "+" : "") + v + "%";
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForPermitGrowth(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>building permits, year-over-year change (construction accelerating or slowing)</span>";
  } else if (currentLayer === "multifamilyshare") {
    [0, 20, 40, 60, 80, 100].forEach(function(v) {
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForMultifamilyShare(v) + ";'></span><span>" + v + "%</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>share of new permits that are multifamily (not a good/bad scale, just a mix indicator)</span>";
  } else if (currentLayer === "vacantforsale") {
    [0, 4, 8, 12, 16, 20].forEach(function(v) {
      var label = v >= 20 ? "20+" : String(v);
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForVacantForSale(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>vacant homes for sale per 1,000 housing units (5-yr survey estimate, not live listings)</span>";
  } else if (currentLayer === "totalvacancy") {
    [0, 6, 12, 18, 24, 30].forEach(function(v) {
      var label = v >= 30 ? "30+" : String(v);
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForTotalVacancy(v) + ";'></span><span>" + label + "%</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>total vacant units, all reasons, as % of housing stock (5-yr survey estimate)</span>";
  } else {
    [0, 8, 16, 24, 32, 40].forEach(function(v) {
      var label = v >= 40 ? "40+" : String(v);
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForPermits(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>new building permits per 1,000 housing units (most recent year)</span>";
  }
  document.getElementById("map-legend").innerHTML = html;
}

function renderTerritoryLegend(containerId) {
  var el = document.getElementById(containerId);
  if (!el) return;
  var html = "<div class='legend-item'><span class='swatch' style='background:#ccc;'></span><span>No data</span></div>";
  if (currentLayer === "growth") {
    [-10, -5, 0, 5, 10, 15, 20].forEach(function(v) {
      var label = (v > 0 ? "+" : "") + v + "%";
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForGrowth(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>5-yr population growth</span>";
  } else if (currentLayer === "unemployment") {
    [2, 4, 6, 8, 10, 12].forEach(function(v) {
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForUnemployment(v) + ";'></span><span>" + v + "%</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>unemployment rate (lower is greener)</span>";
  } else if (currentLayer === "homevalue") {
    [60000, 110000, 160000, 210000, 260000, 300000].forEach(function(v) {
      var label = v >= 300000 ? "$300K+" : "$" + Math.round(v / 1000) + "K";
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForHomeValuePR(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>median home value - territory scale (darker = higher, not &quot;better&quot;)</span>";
  } else if (currentLayer === "rent") {
    [350, 640, 930, 1220, 1510, 1800].forEach(function(v) {
      var label = v >= 1800 ? "$1.8K+" : "$" + Math.round(v);
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForRentPR(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>median rent - territory scale (darker = higher, not &quot;better&quot;)</span>";
  } else if (currentLayer === "income") {
    [15000, 24000, 33000, 42000, 51000, 60000].forEach(function(v) {
      var label = v >= 60000 ? "$60K+" : "$" + Math.round(v / 1000) + "K";
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForIncomePR(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>median household income - territory scale (darker = higher, not &quot;better&quot;)</span>";
  } else if (currentLayer === "housinggrowth") {
    [-10, -5, 0, 5, 10, 15, 20].forEach(function(v) {
      var label = (v > 0 ? "+" : "") + v + "%";
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForGrowth(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>5-yr housing-unit growth (new supply added, not just permitted)</span>";
  } else if (currentLayer === "permitgrowth") {
    [-50, -25, 0, 25, 50, 75, 100].forEach(function(v) {
      var label = (v > 0 ? "+" : "") + v + "%";
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForPermitGrowth(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>building permits, year-over-year change (construction accelerating or slowing)</span>";
  } else if (currentLayer === "multifamilyshare") {
    [0, 20, 40, 60, 80, 100].forEach(function(v) {
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForMultifamilyShare(v) + ";'></span><span>" + v + "%</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>share of new permits that are multifamily (not a good/bad scale, just a mix indicator)</span>";
  } else if (currentLayer === "vacantforsale") {
    [0, 4, 8, 12, 16, 20].forEach(function(v) {
      var label = v >= 20 ? "20+" : String(v);
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForVacantForSale(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>vacant homes for sale per 1,000 housing units (5-yr survey estimate, not live listings)</span>";
  } else if (currentLayer === "totalvacancy") {
    [0, 6, 12, 18, 24, 30].forEach(function(v) {
      var label = v >= 30 ? "30+" : String(v);
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForTotalVacancy(v) + ";'></span><span>" + label + "%</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>total vacant units, all reasons, as % of housing stock (5-yr survey estimate)</span>";
  } else {
    [0, 2, 4, 6, 8, 10].forEach(function(v) {
      var label = v >= 10 ? "10+" : String(v);
      html += "<div class='legend-item'><span class='swatch' style='background:" + colorForPermitsPR(v) + ";'></span><span>" + label + "</span></div>";
    });
    html += "<span style='margin-left:6px;color:var(--text-secondary);'>new building permits per 1,000 housing units - territory scale</span>";
  }
  el.innerHTML = html;
}

function setLayer(layer) {
  currentLayer = layer;
  document.getElementById("layer-btn-growth").classList.toggle("active", layer === "growth");
  document.getElementById("layer-btn-unemployment").classList.toggle("active", layer === "unemployment");
  document.getElementById("layer-btn-homevalue").classList.toggle("active", layer === "homevalue");
  document.getElementById("layer-btn-rent").classList.toggle("active", layer === "rent");
  document.getElementById("layer-btn-income").classList.toggle("active", layer === "income");
  document.getElementById("layer-btn-permits").classList.toggle("active", layer === "permits");
  document.getElementById("layer-btn-housinggrowth").classList.toggle("active", layer === "housinggrowth");
  document.getElementById("layer-btn-permitgrowth").classList.toggle("active", layer === "permitgrowth");
  document.getElementById("layer-btn-multifamilyshare").classList.toggle("active", layer === "multifamilyshare");
  document.getElementById("layer-btn-vacantforsale").classList.toggle("active", layer === "vacantforsale");
  document.getElementById("layer-btn-totalvacancy").classList.toggle("active", layer === "totalvacancy");
  renderLegend();
  renderTerritoryLegend("pr-map-legend");
  renderTerritoryLegend("mariana-map-legend");
  renderTerritoryLegend("american-samoa-map-legend");
  if (countyPaths) {
    countyPaths.attr("fill", function(d) {
      var rec = COUNTY_DATA ? COUNTY_DATA[fipsKey(d.id)] : null;
      return colorForCounty(rec);
    });
  }
  if (prPaths) {
    prPaths.attr("fill", function(d) {
      var fips = d.properties.STATE + d.properties.COUNTY;
      var rec = COUNTY_DATA ? COUNTY_DATA[fips] : null;
      return colorForCounty(rec, true);
    });
  }
  if (marianaPaths) {
    marianaPaths.attr("fill", function(d) {
      var fips = d.properties.STATE + d.properties.COUNTY;
      var rec = COUNTY_DATA ? COUNTY_DATA[fips] : null;
      return colorForCounty(rec, true);
    });
  }
  if (americanSamoaPaths) {
    americanSamoaPaths.attr("fill", function(d) {
      var fips = d.properties.STATE + d.properties.COUNTY;
      var rec = COUNTY_DATA ? COUNTY_DATA[fips] : null;
      return colorForCounty(rec, true);
    });
  }
  renderRankingTable();
}

// Initial ranking table render - runs immediately using the already-embedded COUNTY_DATA, rather
// than waiting on the county-boundary map(s) to finish loading below, since the table doesn't
// depend on the D3/TopoJSON rendering at all.
renderRankingTable();

Promise.all([
  fetch("https://cdn.jsdelivr.net/npm/us-atlas@3/counties-albers-10m.json").then(function(r) { return r.json(); }),
]).then(function(results) {
  var us = results[0];
  var counties = topojson.feature(us, us.objects.counties);
  var states = topojson.mesh(us, us.objects.states, function(a, b) { return a !== b; });

  document.getElementById("map-loading").style.display = "none";
  var svg = document.getElementById("county-map");
  svg.style.display = "block";

  var d3svg = d3.select("#county-map");
  var path = d3.geoPath();

  countyPaths = d3svg.append("g")
    .selectAll("path")
    .data(counties.features)
    .join("path")
    .attr("class", "county")
    .attr("d", path)
    .attr("fill", function(d) {
      var rec = COUNTY_DATA ? COUNTY_DATA[fipsKey(d.id)] : null;
      return colorForCounty(rec);
    })
    .on("mousemove", function(event, d) {
      var tooltip = document.getElementById("map-tooltip");
      var rec = COUNTY_DATA ? COUNTY_DATA[fipsKey(d.id)] : null;
      if (!rec) {
        tooltip.innerHTML = "No data available";
      } else {
        var lines = [];
        if (rec.name) lines.push("<strong>" + rec.name + "</strong>");
        if (rec.pop) {
          var growthText = (rec.growth_pct === null || rec.growth_pct === undefined) ? "N/A" : (rec.growth_pct > 0 ? "+" : "") + rec.growth_pct.toFixed(1) + "%";
          lines.push("Population: " + rec.pop.toLocaleString() + " (5-yr growth: " + growthText + ")");
        }
        if (rec.housing_units) {
          var housingGrowthText = (rec.housing_growth_pct === null || rec.housing_growth_pct === undefined) ? "N/A" : (rec.housing_growth_pct > 0 ? "+" : "") + rec.housing_growth_pct.toFixed(1) + "%";
          lines.push("Housing units: " + rec.housing_units.toLocaleString() + " (5-yr growth: " + housingGrowthText + ")");
        }
        if (rec.unemployment_rate !== null && rec.unemployment_rate !== undefined) {
          lines.push("Unemployment: " + rec.unemployment_rate.toFixed(1) + "% (" + rec.unemployment_period + ")");
        }
        if (rec.median_home_value !== null && rec.median_home_value !== undefined) {
          lines.push("Median home value: " + formatMoney(rec.median_home_value));
        }
        if (rec.median_rent !== null && rec.median_rent !== undefined) {
          lines.push("Median rent: " + formatMoney(rec.median_rent) + "/mo");
        }
        if (rec.median_income !== null && rec.median_income !== undefined) {
          lines.push("Median household income: " + formatMoney(rec.median_income));
        }
        if (rec.building_permits !== null && rec.building_permits !== undefined) {
          var perHousingUnit = permitsPerHousingUnit(rec);
          lines.push("Building permits: " + rec.building_permits.toLocaleString() + (perHousingUnit !== null ? " (" + perHousingUnit.toFixed(1) + " per 1,000 housing units)" : ""));
        }
        if (rec.permit_growth_pct !== null && rec.permit_growth_pct !== undefined) {
          var permitGrowthText = (rec.permit_growth_pct > 0 ? "+" : "") + rec.permit_growth_pct.toFixed(1) + "%";
          lines.push("Permit growth (YoY): " + permitGrowthText + (rec.permits_current !== undefined ? " (" + rec.permits_current.toLocaleString() + " permits)" : ""));
        }
        if (rec.multifamily_share_pct !== null && rec.multifamily_share_pct !== undefined) {
          lines.push("New permits: " + rec.multifamily_share_pct.toFixed(0) + "% multifamily / " + (100 - rec.multifamily_share_pct).toFixed(0) + "% single-family");
        }
        if (rec.vacant_for_sale !== null && rec.vacant_for_sale !== undefined) {
          var vfsRate = vacantForSaleRate(rec);
          lines.push("Vacant for sale: " + rec.vacant_for_sale.toLocaleString() + (vfsRate !== null ? " (" + vfsRate.toFixed(1) + " per 1,000 housing units, 5-yr survey estimate)" : ""));
        }
        if (rec.vacant_total !== null && rec.vacant_total !== undefined) {
          var totalVacRate = totalVacancyRate(rec);
          lines.push("Total vacant (all reasons): " + rec.vacant_total.toLocaleString() + (totalVacRate !== null ? " (" + totalVacRate.toFixed(1) + "% of housing stock, 5-yr survey estimate)" : ""));
        }
        tooltip.innerHTML = lines.length ? lines.join("<br>") : "No data available";
      }
      tooltip.style.left = (event.clientX + 14) + "px";
      tooltip.style.top = (event.clientY + 10) + "px";
      tooltip.style.display = "block";
    })
    .on("mouseleave", function() {
      document.getElementById("map-tooltip").style.display = "none";
    });

  d3svg.append("path")
    .datum(states)
    .attr("class", "state-border")
    .attr("d", path);

  renderLegend();
}).catch(function(err) {
  document.getElementById("map-loading").textContent = "Could not load the map. Error: " + (err && err.message ? err.message : err) + " - try refreshing the page.";
  console.error("County map load error:", err);
});



function rewindForD3(geojson) {
  function fixPolygonRings(rings) {
    var test = {
      type: "Feature",
      properties: {},
      geometry: {
        type: "Polygon",
        coordinates: rings
      }
    };

    if (d3.geoArea(test) > 2 * Math.PI) {
      rings.forEach(function(ring) {
        ring.reverse();
      });
    }
  }

  var features = geojson.features.map(function(f) {
    var geom = JSON.parse(JSON.stringify(f.geometry));

    if (geom.type === "Polygon") {
      fixPolygonRings(geom.coordinates);
    } else if (geom.type === "MultiPolygon") {
      geom.coordinates.forEach(fixPolygonRings);
    }

    return {
      type: "Feature",
      properties: f.properties,
      geometry: geom
    };
  });

  return {
    type: "FeatureCollection",
    features: features
  };
}
// Generic territory map renderer, used for Puerto Rico+USVI, Guam+CNMI, and American Samoa -
// same rendering, tooltip, and error-handling logic for all three, just pointed at different
// elements and GeoJSON data. Returns the rendered path selection (or null on failure) so the
// caller can store it in the right module-level *Paths variable for setLayer() to recolor later.
function renderTerritoryMap(geojson, svgId, loadingId, legendId, viewBoxWidth, viewBoxHeight, label) {
  try {
    if (!geojson) {
      document.getElementById(loadingId).textContent = label + " map data is temporarily unavailable.";
      return null;
    }
    geojson = rewindForD3(geojson);   
var projection = d3.geoMercator().fitSize([viewBoxWidth, viewBoxHeight], geojson);
    var path = d3.geoPath().projection(projection);
    var svg = d3.select("#" + svgId);

    var paths = svg.append("g")
      .selectAll("path")
      .data(geojson.features)
      .join("path")
      .attr("class", "county")
      .attr("d", path)
      .attr("fill", function(d) {
        var fips = d.properties.STATE + d.properties.COUNTY;
        var rec = COUNTY_DATA ? COUNTY_DATA[fips] : null;
        return colorForCounty(rec, true);
      })
      .on("mousemove", function(event, d) {
        var tooltip = document.getElementById("map-tooltip");
        var fips = d.properties.STATE + d.properties.COUNTY;
        var rec = COUNTY_DATA ? COUNTY_DATA[fips] : null;
        if (!rec) {
          tooltip.innerHTML = "No data available";
        } else {
          var lines = [];
          if (rec.name) { lines.push("<strong>" + rec.name + "</strong>"); }
          else { lines.push("<strong>" + d.properties.NAME + "</strong>"); }
          if (rec.pop) {
            var growthText = (rec.growth_pct === null || rec.growth_pct === undefined) ? "N/A" : (rec.growth_pct > 0 ? "+" : "") + rec.growth_pct.toFixed(1) + "%";
            lines.push("Population: " + rec.pop.toLocaleString() + " (5-yr growth: " + growthText + ")");
          }
          if (rec.housing_units) {
            var housingGrowthText = (rec.housing_growth_pct === null || rec.housing_growth_pct === undefined) ? "N/A" : (rec.housing_growth_pct > 0 ? "+" : "") + rec.housing_growth_pct.toFixed(1) + "%";
            lines.push("Housing units: " + rec.housing_units.toLocaleString() + " (5-yr growth: " + housingGrowthText + ")");
          }
          if (rec.unemployment_rate !== null && rec.unemployment_rate !== undefined) {
            lines.push("Unemployment: " + rec.unemployment_rate.toFixed(1) + "% (" + rec.unemployment_period + ")");
          }
          if (rec.median_home_value !== null && rec.median_home_value !== undefined) {
            lines.push("Median home value: " + formatMoney(rec.median_home_value));
          }
          if (rec.median_rent !== null && rec.median_rent !== undefined) {
            lines.push("Median rent: " + formatMoney(rec.median_rent) + "/mo");
          }
          if (rec.median_income !== null && rec.median_income !== undefined) {
            lines.push("Median household income: " + formatMoney(rec.median_income));
          }
          if (rec.building_permits !== null && rec.building_permits !== undefined) {
            var perHousingUnit = permitsPerHousingUnit(rec);
            lines.push("Building permits: " + rec.building_permits.toLocaleString() + (perHousingUnit !== null ? " (" + perHousingUnit.toFixed(1) + " per 1,000 housing units)" : ""));
          }
          if (rec.permit_growth_pct !== null && rec.permit_growth_pct !== undefined) {
            var permitGrowthText = (rec.permit_growth_pct > 0 ? "+" : "") + rec.permit_growth_pct.toFixed(1) + "%";
            lines.push("Permit growth (YoY): " + permitGrowthText + (rec.permits_current !== undefined ? " (" + rec.permits_current.toLocaleString() + " permits)" : ""));
          }
          if (rec.multifamily_share_pct !== null && rec.multifamily_share_pct !== undefined) {
            lines.push("New permits: " + rec.multifamily_share_pct.toFixed(0) + "% multifamily / " + (100 - rec.multifamily_share_pct).toFixed(0) + "% single-family");
          }
          if (rec.vacant_for_sale !== null && rec.vacant_for_sale !== undefined) {
            var vfsRate = vacantForSaleRate(rec);
            lines.push("Vacant for sale: " + rec.vacant_for_sale.toLocaleString() + (vfsRate !== null ? " (" + vfsRate.toFixed(1) + " per 1,000 housing units, 5-yr survey estimate)" : ""));
          }
          if (rec.vacant_total !== null && rec.vacant_total !== undefined) {
            var totalVacRate = totalVacancyRate(rec);
            lines.push("Total vacant (all reasons): " + rec.vacant_total.toLocaleString() + (totalVacRate !== null ? " (" + totalVacRate.toFixed(1) + "% of housing stock, 5-yr survey estimate)" : ""));
          }
          tooltip.innerHTML = lines.length ? lines.join("<br>") : "No data available";
        }
        tooltip.style.left = (event.clientX + 14) + "px";
        tooltip.style.top = (event.clientY + 10) + "px";
        tooltip.style.display = "block";
      })
      .on("mouseleave", function() {
        document.getElementById("map-tooltip").style.display = "none";
      });

    document.getElementById(svgId).style.display = "block";
    document.getElementById(loadingId).style.display = "none";
    renderTerritoryLegend(legendId);
    return paths;
  } catch (err) {
    document.getElementById(loadingId).textContent = "Could not load the " + label + " map.";
    console.error(label + " map load error:", err);
    return null;
  }
}

prPaths = renderTerritoryMap(PR_GEOJSON, "pr-map", "pr-map-loading", "pr-map-legend", 500, 260, "Puerto Rico / USVI");
marianaPaths = renderTerritoryMap(MARIANA_GEOJSON, "mariana-map", "mariana-map-loading", "mariana-map-legend", 500, 320, "Guam / CNMI");
americanSamoaPaths = renderTerritoryMap(AMERICAN_SAMOA_GEOJSON, "american-samoa-map", "american-samoa-map-loading", "american-samoa-map-legend", 500, 260, "American Samoa");
</script>
__FOOTER__
</body>
</html>"""

investment_map_html = (INVESTMENT_MAP_TEMPLATE
                        .replace("__CSS__", PAGE_CSS)
                        .replace("__NAV__", NAV_HTML)
                        .replace("__DARKMODE_CSS__", DARK_MODE_CSS)
                        .replace("__DARKMODE_BUTTON__", DARK_MODE_BUTTON)
                        .replace("__DARKMODE_JS__", DARK_MODE_JS)
                        .replace("__LEARNINGMODE_CSS__", LEARNING_MODE_CSS)
                        .replace("__LEARNINGMODE_BUTTON__", LEARNING_MODE_BUTTON)
                        .replace("__LEARNINGMODE_JS__", LEARNING_MODE_JS)
                        .replace("__FOOTER__", FOOTER_HTML)
                        .replace("__COUNTY_DATA_JSON__", county_data_json)
                        .replace("__PR_GEOJSON__", pr_geojson_json)
                        .replace("__MARIANA_GEOJSON__", mariana_geojson_json)
                        .replace("__AMERICAN_SAMOA_GEOJSON__", american_samoa_geojson_json))

with open("index.html", "w") as f:
    f.write(stocks_html)

with open("portfolio.html", "w") as f:
    f.write(portfolio_html)

with open("investment-map.html", "w") as f:
    f.write(investment_map_html)

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

with open("glossary.html", "w") as f:
    f.write(glossary_html)

with open("educators.html", "w") as f:
    f.write(educators_html)

# ------------------- PAGE 7: MARKET INSIGHTS (LOGIN-GATED, PERSONAL USE ONLY) -------------------

INSIGHTS_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Market Insights</title>
<script src="https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.14.1/firebase-auth-compat.js"></script>
<style>__CSS__
.calc { background:#fff; border-radius:10px; padding:18px; border:1px solid #e5e3dc; margin-bottom:20px; max-width:640px; }
.calc h3 { margin:0 0 12px; font-size:16px; }
.calc label { display:block; font-size:12px; color:#666; margin:10px 0 3px; }
.calc input { width:100%; padding:8px; font-size:14px; border:1px solid #ccc; border-radius:6px; box-sizing:border-box; }
.calc button { margin-top:14px; padding:10px 18px; font-size:14px; font-weight:600; color:#fff; background:#1f4e79; border:none; border-radius:6px; cursor:pointer; }
.calc button.secondary { background:#888; }
.err { color:#c0392b; font-size:13px; margin-top:8px; }
.restricted-banner { background:#fef3c7; border:2px solid #f59e0b; padding:15px; border-radius:10px; margin-bottom:20px; font-size:13px; color:#78350f; }
@media (max-width: 600px) {
  body { padding:12px; }
  .calc { padding:14px; max-width:100%; }
  .calc input { font-size:16px !important; padding:10px !important; }
  .calc button { width:100%; }
}
__DARKMODE_CSS__
__LEARNINGMODE_CSS__
</style>
</head>
<body>
__DARKMODE_BUTTON__<script>__DARKMODE_JS__</script>
__LEARNINGMODE_BUTTON__<script>__LEARNINGMODE_JS__</script>
__NAV__
<h1>Market Insights</h1>
<p class="timestamp">Not yet public - restricted to a single account while data-licensing terms with Finnhub and FINRA are being confirmed.</p>

<div class="calc" id="auth-panel">
<h3 id="auth-title">Log In</h3>
<label>Email</label>
<input type="email" id="auth-email">
<label>Password</label>
<input type="password" id="auth-password">
<button onclick="doLogin()">Log In</button>
<div class="err" id="auth-error"></div>
</div>

<div id="restricted-view" style="display:none;">
  <div class="restricted-banner">
    You're logged in, but this account doesn't have access to this section. Market Insights is
    restricted to a single account while licensing terms are confirmed with data providers.
  </div>
  <button class="secondary" onclick="doLogout()">Log Out</button>
</div>

<div id="allowed-view" style="display:none;">
  <div class="calc">
    <span id="welcome-msg"></span> &nbsp;
    <button class="secondary" onclick="doLogout()" style="margin-top:0;">Log Out</button>
  </div>
  <div class="calc">
    <h3>Under development</h3>
    <p class="note">This section is reserved for AI-generated stock and bond market summaries.
    It's intentionally empty right now - content will be added once Finnhub and FINRA have
    confirmed what can be shared under their personal-use terms. This page itself is safe to use
    in the meantime: it's just a login gate with nothing behind it yet.</p>
  </div>
</div>

<script>
// Same Firebase project as Property Manager - reused here only for its login system,
// not for sharing any Property Manager data.
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

// Hard allowlist - only these specific accounts can see the "allowed-view" content below,
// regardless of who else signs up for Property Manager on this same Firebase project.
var ALLOWED_EMAILS = ["chambelon@aol.com"];

function showError(elId, message) {
  document.getElementById(elId).textContent = message;
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
  document.getElementById("auth-panel").style.display = "none";
  document.getElementById("restricted-view").style.display = "none";
  document.getElementById("allowed-view").style.display = "none";

  if (!user) {
    document.getElementById("auth-panel").style.display = "block";
    return;
  }

  if (ALLOWED_EMAILS.indexOf(user.email) === -1) {
    document.getElementById("restricted-view").style.display = "block";
    return;
  }

  document.getElementById("allowed-view").style.display = "block";
  document.getElementById("welcome-msg").textContent = "Logged in as " + user.email;
});
</script>

__FOOTER__
</body>
</html>"""

insights_html = (INSIGHTS_TEMPLATE
                  .replace("__CSS__", PAGE_CSS)
                  .replace("__NAV__", NAV_HTML)
                  .replace("__DARKMODE_CSS__", DARK_MODE_CSS)
                  .replace("__DARKMODE_BUTTON__", DARK_MODE_BUTTON)
                  .replace("__DARKMODE_JS__", DARK_MODE_JS)
                  .replace("__LEARNINGMODE_CSS__", LEARNING_MODE_CSS)
                  .replace("__LEARNINGMODE_BUTTON__", LEARNING_MODE_BUTTON)
                  .replace("__LEARNINGMODE_JS__", LEARNING_MODE_JS)
                  .replace("__FOOTER__", FOOTER_HTML))

with open("insights.html", "w") as f:
    f.write(insights_html)

# ------------------- PAGE 11: LEGAL (TERMS, PRIVACY, REFUND POLICY) -------------------
#
# Content below is pre-converted from the reviewed Markdown drafts (see the three .md files
# provided separately) into static HTML at build time, rather than converting Markdown to HTML
# on every GitHub Actions run - these documents don't contain live data, so there's no reason to
# add a new pip dependency (the "markdown" package) to the workflow for content that doesn't
# change automatically. If you revise the wording, re-run the conversion and paste the updated
# HTML here (or ask Claude to do it) rather than editing this HTML by hand.

LEGAL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__PAGE_TITLE__ - Stock Digest</title>
<style>__CSS__
__DARKMODE_CSS__
__LEARNINGMODE_CSS__
.legal-content h2 { font-size:16px; margin:22px 0 8px; }
.legal-content ul { padding-left:20px; }
.legal-content li { margin-bottom:4px; }
.legal-content hr { border:none; border-top:1px solid var(--card-border); margin:16px 0; }
.legal-content em { display:block; font-size:12px; color:var(--text-faint); margin-top:20px; }
</style>
</head>
<body>
__DARKMODE_BUTTON__<script>__DARKMODE_JS__</script>
__LEARNINGMODE_BUTTON__<script>__LEARNINGMODE_JS__</script>
__NAV__
<div class="legal-content">
__LEGAL_BODY__
</div>
__FOOTER__
</body>
</html>"""

terms_html = (LEGAL_TEMPLATE
              .replace("__PAGE_TITLE__", "Terms of Service")
              .replace("__CSS__", PAGE_CSS)
              .replace("__NAV__", NAV_HTML)
              .replace("__DARKMODE_CSS__", DARK_MODE_CSS)
              .replace("__DARKMODE_BUTTON__", DARK_MODE_BUTTON)
              .replace("__DARKMODE_JS__", DARK_MODE_JS)
              .replace("__LEARNINGMODE_CSS__", LEARNING_MODE_CSS)
              .replace("__LEARNINGMODE_BUTTON__", LEARNING_MODE_BUTTON)
              .replace("__LEARNINGMODE_JS__", LEARNING_MODE_JS)
              .replace("__FOOTER__", FOOTER_HTML)
              .replace("__LEGAL_BODY__", """<h1>Terms of Service</h1>
<p><strong>Winners Stock LLC</strong> ("Winners Stock," "we," "us," or "our")
Operating Stock Digest at winnersstock.com (the "Service")</p>
<p><strong>Effective Date:</strong> September 1, 2026
<strong>Last Updated:</strong> September 1, 2026</p>
<hr />
<h2>1. Acceptance of Terms</h2>
<p>By accessing or using Stock Digest, creating an account, or subscribing to any paid tier of the Service, you agree to be bound by these Terms of Service ("Terms"). If you do not agree to these Terms, do not use the Service.</p>
<p>You must be at least 18 years old, or the age of majority in your jurisdiction, to create an account or subscribe to the Service.</p>
<h2>2. Description of Service</h2>
<p>Stock Digest provides financial market data, economic indicators, educational content, calculators, and portfolio-tracking tools for informational and educational purposes. The Service may include:</p>
<ul>
<li>Market data dashboards (stock indexes, commodities, currencies, cryptocurrency prices, interest rates, and related economic indicators)</li>
<li>Real estate market data and calculators</li>
<li>Financial calculators (mortgage, loan, tax estimation, and related tools)</li>
<li>A personal portfolio-tracking feature tied to your account</li>
<li>Educational glossary and reference content</li>
<li>[Any additional features - property management tools, market insights, etc.]</li>
</ul>
<h2>3. Not Financial Advice</h2>
<p><strong>The Service is for informational and educational purposes only.</strong> Nothing on Stock Digest constitutes financial, investment, legal, or tax advice, and nothing on the Service is a recommendation to buy, sell, or hold any security, cryptocurrency, real property, or other asset.</p>
<ul>
<li>Market data, indicators, and calculator outputs are estimates based on available data sources and may contain errors, delays, or inaccuracies.</li>
<li>Any AI-generated content, summaries, or "insight" features are automated and may be incomplete or incorrect.</li>
<li>You are solely responsible for your own financial, investment, and tax decisions. Consult a licensed financial advisor, attorney, or tax professional before making decisions based on anything presented through the Service.</li>
<li>Winners Stock LLC is not a registered investment advisor, broker-dealer, or tax preparation service.</li>
</ul>
<h2>4. Accounts</h2>
<ul>
<li>You are responsible for maintaining the confidentiality of your account credentials and for all activity under your account.</li>
<li>You must provide accurate information when creating an account.</li>
<li>You may not share your account, or create multiple accounts to circumvent subscription limits or pricing.</li>
<li>We reserve the right to suspend or terminate accounts that violate these Terms, engage in abusive behavior, or are used for unlawful purposes.</li>
</ul>
<h2>5. Subscriptions, Billing, and Cancellation</h2>
<ul>
<li>Certain features of the Service require a paid subscription. Current pricing is listed at [PRICING PAGE URL].</li>
<li>Subscriptions renew automatically at the end of each billing period unless canceled before the renewal date.</li>
<li>You may cancel your subscription at any time through your account settings. Cancellation takes effect at the end of the current billing period; you will retain access through that period, and you will not be billed again afterward.</li>
<li>Refunds: see our <a href="refund-policy.html">Cancellation &amp; Refund Policy</a>.</li>
<li>We reserve the right to change subscription pricing with advance notice. Continued use of the Service after a price change takes effect constitutes acceptance of the new pricing.</li>
<li>Payment processing is handled by a third-party payment processor. We do not store your full payment card information on our own servers.</li>
</ul>
<h2>6. Educational and Institutional Access</h2>
<p>Free classroom access offered to educators and students under our Educators &amp; Students program is provided at our discretion and may be modified, limited, or discontinued at any time. Educational access is for non-commercial classroom use only.</p>
<h2>7. Acceptable Use</h2>
<p>You agree not to:</p>
<ul>
<li>Use the Service for any unlawful purpose or in violation of any applicable law or regulation</li>
<li>Attempt to gain unauthorized access to any part of the Service, other users' accounts or data, or our underlying systems</li>
<li>Scrape, reverse-engineer, or systematically extract data from the Service beyond normal personal use</li>
<li>Interfere with or disrupt the integrity or performance of the Service</li>
<li>Use automated means (bots, scripts) to access the Service in a manner that sends more requests than a human could reasonably send</li>
</ul>
<h2>8. Intellectual Property</h2>
<p>The Service, including its design, calculators, compiled data presentations, and original written content, is owned by Winners Stock LLC and protected by applicable intellectual property laws. Underlying market data is sourced from third parties (see Section 9) and remains subject to those parties' own rights where applicable. You may not copy, resell, or redistribute the Service or its content without our written permission.</p>
<h2>9. Third-Party Data Sources</h2>
<p>The Service aggregates and displays data from third-party sources, including but not limited to Yahoo Finance, the Federal Reserve Bank of St. Louis (FRED), the U.S. Bureau of Labor Statistics, the U.S. Census Bureau, the Federal Housing Finance Agency, Finnhub, and other public or licensed data providers. We do not control, and are not responsible for, the accuracy, timeliness, or availability of third-party data. Data may be delayed and is not intended for use in time-sensitive trading decisions.</p>
<h2>10. Disclaimer of Warranties</h2>
<p>THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, ACCURACY, OR NON-INFRINGEMENT. WE DO NOT WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED, ERROR-FREE, OR SECURE.</p>
<h2>11. Limitation of Liability</h2>
<p>TO THE MAXIMUM EXTENT PERMITTED BY LAW, WINNERS STOCK LLC AND ITS OWNERS, EMPLOYEES, AND CONTRACTORS SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS, DATA, OR FINANCIAL LOSSES ARISING FROM YOUR USE OF, OR INABILITY TO USE, THE SERVICE, INCLUDING ANY FINANCIAL, INVESTMENT, OR TRADING DECISIONS MADE IN RELIANCE ON INFORMATION PROVIDED THROUGH THE SERVICE. OUR TOTAL LIABILITY FOR ANY CLAIM ARISING FROM THESE TERMS OR THE SERVICE SHALL NOT EXCEED THE AMOUNT YOU PAID US IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM.</p>
<h2>12. Indemnification</h2>
<p>You agree to indemnify and hold harmless Winners Stock LLC from any claims, damages, losses, or expenses (including reasonable attorney's fees) arising from your use of the Service or violation of these Terms.</p>
<h2>13. Changes to These Terms</h2>
<p>We may update these Terms from time to time. Material changes will be posted on this page with an updated "Last Updated" date. Continued use of the Service after changes take effect constitutes acceptance of the revised Terms.</p>
<h2>14. Termination</h2>
<p>We may suspend or terminate your access to the Service at any time for violation of these Terms. You may stop using the Service and close your account at any time.</p>
<h2>15. Governing Law</h2>
<p>These Terms are governed by the laws of the State of Florida, without regard to its conflict of law principles. Any disputes arising from these Terms or the Service shall be resolved in the state or federal courts located in Miami-Dade County, Florida.</p>
<h2>16. Contact</h2>
<p>Questions about these Terms can be directed to:</p>
<p>Winners Stock LLC<br />
2037 NW 27th Avenue<br />
Miami, Florida 33142<br />
support@winnersstock.com</p>
<hr />
<em>This document is a draft template and has not been reviewed by an attorney. Please have it reviewed by a business attorney licensed in your state before publishing it live or relying on it for legal protection.</em>"""))

privacy_html = (LEGAL_TEMPLATE
                .replace("__PAGE_TITLE__", "Privacy Policy")
                .replace("__CSS__", PAGE_CSS)
                .replace("__NAV__", NAV_HTML)
                .replace("__DARKMODE_CSS__", DARK_MODE_CSS)
                .replace("__DARKMODE_BUTTON__", DARK_MODE_BUTTON)
                .replace("__DARKMODE_JS__", DARK_MODE_JS)
                .replace("__LEARNINGMODE_CSS__", LEARNING_MODE_CSS)
                .replace("__LEARNINGMODE_BUTTON__", LEARNING_MODE_BUTTON)
                .replace("__LEARNINGMODE_JS__", LEARNING_MODE_JS)
                .replace("__FOOTER__", FOOTER_HTML)
                .replace("__LEGAL_BODY__", """<h1>Privacy Policy</h1>
<p><strong>Winners Stock LLC</strong> ("Winners Stock," "we," "us," or "our")
Operating Stock Digest at winnersstock.com (the "Service")</p>
<p><strong>Effective Date:</strong> September 1, 2026
<strong>Last Updated:</strong> September 1, 2026</p>
<hr />
<h2>1. Overview</h2>
<p>This Privacy Policy explains what information we collect, how we use it, and the choices you have. By using the Service, you agree to the collection and use of information as described here.</p>
<h2>2. Information We Collect</h2>
<h3>Information you provide directly</h3>
<ul>
<li><strong>Account information</strong>: email address and password (used to create and secure your account). Passwords are handled by our authentication provider (Firebase Authentication, operated by Google) and are never stored or visible to us in plain text.</li>
<li><strong>Portfolio data</strong>: any stock or ETF tickers you choose to add to your personal portfolio.</li>
<li><strong>Property Manager data</strong> (if applicable to your account): property addresses, financial details, and related records you choose to enter for your own use.</li>
<li><strong>Payment information</strong>: if you subscribe to a paid tier, billing is handled directly by our payment processor. We do not receive or store your full credit card number on our own servers.</li>
<li><strong>Communications</strong>: information you provide when you contact us for support (e.g., email content).</li>
</ul>
<h3>Information collected automatically</h3>
<ul>
<li>Basic usage data such as pages visited and general browser/device information, to the extent provided by standard web hosting and analytics tools.</li>
<li>A local browser preference (e.g., dark mode or "Learning Mode" setting) stored in your browser's local storage. This is not transmitted to our servers and is specific to the browser/device you're using.</li>
</ul>
<h3>Information we do NOT collect</h3>
<ul>
<li>We do not collect your full payment card number, card verification code, or bank account number directly - these are handled by our third-party payment processor.</li>
<li>We do not sell your personal information to third parties.</li>
</ul>
<h2>3. How We Use Your Information</h2>
<p>We use the information we collect to:</p>
<ul>
<li>Create and maintain your account</li>
<li>Provide the features you use (e.g., displaying your saved portfolio tickers, saving your property records)</li>
<li>Process subscription payments and manage billing</li>
<li>Respond to support requests</li>
<li>Maintain the security and integrity of the Service</li>
<li>Comply with legal obligations</li>
</ul>
<p>We do not use your portfolio holdings, property data, or other account content to generate targeted advertising, and we do not sell this information.</p>
<h2>4. Third-Party Service Providers</h2>
<p>We use the following categories of third-party providers to operate the Service. Each handles a defined, limited scope of data as part of providing their service to us:</p>
<ul>
<li><strong>Firebase (Google)</strong> - authentication and database storage for account and portfolio/property data</li>
<li><strong>Payment processor</strong> [NAME ONCE FINALIZED - e.g., PayPal, North American Bancard/Payments Hub] - subscription billing</li>
<li><strong>Market data providers</strong> (Yahoo Finance, Finnhub, FRED, and similar) - supply the market data displayed on the Service; we do not share your personal account information with these providers as part of displaying market data</li>
<li><strong>Cloudflare</strong> - infrastructure used to securely relay certain data requests (e.g., live stock quote lookups) without exposing API credentials in your browser</li>
</ul>
<p>These providers have their own privacy policies governing how they handle data on our behalf.</p>
<h2>5. Data Security</h2>
<p>We use industry-standard providers (Firebase Authentication and Firestore) to store account and application data, with access restricted so that each user can only read or modify their own data. No method of electronic storage or transmission is 100% secure, and we cannot guarantee absolute security.</p>
<h2>6. Data Retention</h2>
<p>We retain your account information and associated data for as long as your account remains active. If you close your account, we will delete or anonymize your personal data within [RETENTION PERIOD, e.g., 30-90 days], except where we are required to retain certain records (e.g., billing records) for legal, tax, or accounting purposes.</p>
<h2>7. Your Rights and Choices</h2>
<p>Depending on your location, you may have rights to:</p>
<ul>
<li>Access the personal information we hold about you</li>
<li>Request correction of inaccurate information</li>
<li>Request deletion of your account and associated data</li>
<li>Object to or restrict certain processing of your information</li>
</ul>
<p>To exercise any of these rights, contact us at support@winnersstock.com. We will respond within a reasonable time and in accordance with applicable law.</p>
<p>If you are a California resident, you may have additional rights under the California Consumer Privacy Act (CCPA); if you are in the European Economic Area or UK, you may have additional rights under the GDPR/UK GDPR. [Confirm with counsel whether these apply based on where your users are located, and expand this section accordingly if so.]</p>
<h2>8. Children's Privacy</h2>
<p>The Service is not directed to children under 13 (or under 16 in jurisdictions where that is the relevant threshold), and we do not knowingly collect personal information from children. If you believe a child has provided us with personal information, contact us at support@winnersstock.com and we will take steps to delete it.</p>
<h2>9. Cookies and Local Storage</h2>
<p>We use browser local storage (not third-party tracking cookies) to remember display preferences such as dark mode and Learning Mode settings. This information stays on your device and is not transmitted to us.</p>
<h2>10. Changes to This Policy</h2>
<p>We may update this Privacy Policy from time to time. Material changes will be posted on this page with an updated "Last Updated" date. If changes are significant, we will make reasonable efforts to notify account holders (e.g., via email or an in-app notice).</p>
<h2>11. Contact Us</h2>
<p>Questions about this Privacy Policy or your personal information can be directed to:</p>
<p>Winners Stock LLC<br />
2037 NW 27th Avenue<br />
Miami, Florida 33142<br />
support@winnersstock.com</p>
<hr />
<em>This document is a draft template and has not been reviewed by an attorney. Data privacy law varies significantly by state and country (e.g., CCPA, GDPR, and other state privacy laws), and applicability depends on where your users are located. Please have this reviewed by a business attorney before publishing it live or relying on it for compliance.</em>"""))

refund_html = (LEGAL_TEMPLATE
               .replace("__PAGE_TITLE__", "Cancellation & Refund Policy")
               .replace("__CSS__", PAGE_CSS)
               .replace("__NAV__", NAV_HTML)
               .replace("__DARKMODE_CSS__", DARK_MODE_CSS)
               .replace("__DARKMODE_BUTTON__", DARK_MODE_BUTTON)
               .replace("__DARKMODE_JS__", DARK_MODE_JS)
               .replace("__LEARNINGMODE_CSS__", LEARNING_MODE_CSS)
               .replace("__LEARNINGMODE_BUTTON__", LEARNING_MODE_BUTTON)
               .replace("__LEARNINGMODE_JS__", LEARNING_MODE_JS)
               .replace("__FOOTER__", FOOTER_HTML)
               .replace("__LEGAL_BODY__", """<h1>Cancellation &amp; Refund Policy</h1>
<p><strong>Winners Stock LLC</strong> ("Winners Stock," "we," "us," or "our")
Operating Stock Digest at winnersstock.com (the "Service")</p>
<p><strong>Effective Date:</strong> September 1, 2026
<strong>Last Updated:</strong> September 1, 2026</p>
<hr />
<h2>1. Subscription Billing</h2>
<p>Paid subscriptions to Stock Digest bill automatically on a recurring basis (e.g., monthly or annually, as selected at signup) until canceled. Your billing date is set from the date you first subscribe.</p>
<h2>2. How to Cancel</h2>
<p>You can cancel your subscription at any time by [DESCRIBE ACTUAL MECHANISM ONCE BUILT - e.g., "going to Account Settings and clicking Cancel Subscription"]. Cancellation takes effect at the end of your current billing period - you will keep access to paid features through the end of the period you already paid for, and you will not be charged again afterward.</p>
<p>We do not require you to contact support to cancel; cancellation is self-service and available directly in your account, consistent with the same ease you used to subscribe.</p>
<h2>3. Refunds</h2>
<p>[CHOOSE ONE APPROACH AND DELETE THE OTHERS BEFORE PUBLISHING - PICK WHAT YOU ACTUALLY WANT TO OFFER:]</p>
<p><strong>Option A - No refunds for partial periods:</strong>
Subscription fees are non-refundable for the remainder of a billing period after cancellation. When you cancel, you retain access through the end of the period you already paid for; we do not provide prorated refunds for unused time within a billing period.</p>
<p><strong>Option B - Money-back guarantee window:</strong>
If you are not satisfied with your subscription, you may request a full refund within [X] days of your initial subscription charge by contacting support@winnersstock.com. Refund requests made after this window, or for renewal charges after the first billing cycle, are handled on a case-by-case basis at our discretion.</p>
<p><strong>Option C - Prorated refund:</strong>
If you cancel mid-billing-period, we will refund the unused portion of that period on a prorated basis.</p>
<h2>4. Billing Errors and Duplicate Charges</h2>
<p>If you believe you were charged in error or were billed more than once for the same period, contact us at support@winnersstock.com with your account email and the date of the charge. We will investigate and issue a correction or refund promptly where warranted.</p>
<h2>5. Failed Payments</h2>
<p>If a scheduled payment fails (e.g., an expired card), we will attempt to notify you and may retry the charge. If payment is not resolved within [X] days, your subscription may be downgraded to the free tier or suspended until payment is updated.</p>
<h2>6. Price Changes</h2>
<p>If we change subscription pricing, we will provide advance notice before the new price takes effect for existing subscribers. Continuing your subscription after that date constitutes acceptance of the new price. You may cancel before the new price takes effect if you do not agree to it.</p>
<h2>7. Chargebacks</h2>
<p>If you have a billing concern, we ask that you contact us first at support@winnersstock.com so we can resolve it directly - most issues can be handled faster this way than through a card dispute. Initiating a chargeback without first attempting to resolve the issue with us may result in suspension of your account while the dispute is investigated.</p>
<h2>8. Contact</h2>
<p>Questions about billing, cancellation, or refunds:</p>
<p>Winners Stock LLC<br />
support@winnersstock.com</p>
<hr />
<em>This document is a draft template and has not been reviewed by an attorney. The refund approach (Section 3) is a business decision you should make deliberately - whichever option you choose also needs to match what you actually configure in your payment processor's subscription settings. Please have this reviewed by a business attorney before publishing it live.</em>"""))

with open("terms.html", "w") as f:
    f.write(terms_html)

with open("privacy.html", "w") as f:
    f.write(privacy_html)

with open("refund-policy.html", "w") as f:
    f.write(refund_html)

print("index.html, realestate.html, calculators.html, search.html, stocksearch.html, tickers.json, propertymanager.html, insights.html, glossary.html, educators.html, portfolio.html, terms.html, privacy.html, and refund-policy.html generated successfully")
