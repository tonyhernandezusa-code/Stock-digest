#!/usr/bin/env python3
"""Generate the standalone Stock Digest AI Market Intelligence prototype.

This script creates only:
  * ai_company_data.json
  * ai-intelligence.html

It intentionally does not import, edit, or regenerate generate_digest.py,
investment-map.html, county_data.json, or any other Stock Digest page.

Data sources:
  * SEC EDGAR Company Facts and Submissions APIs for reported financial facts
  * Yahoo Finance through yfinance for historical market prices (prototype use)

The scoring model is a transparent research score, not an investment recommendation
and not a probability forecast. Missing inputs are excluded and the remaining weights
are renormalized. Phase 2 adds deterministic peer comparisons, strengths, risks,
data-coverage warnings, and a preliminary weekly-leaders view. Phase 3 adds a
permanent weekly snapshot history, live-versus-official ranking changes, and a
track-record scorecard that measures subsequent returns against subsector peers. Phase 4
adds a preliminary point-in-time historical backtest and score-band calibration lab. Phase 5
adds a conservative 12-month backtest-based likelihood research model with a chronological
calibration/validation split, sample-size gates, shrinkage toward 50%, and uncertainty ranges. Phase 6 adds transparent
three-year conservative, base, and optimistic operating scenarios so each company can be viewed
from past reported results through the present and into clearly labeled model-generated futures. Phase 7
adds a capital-efficiency and financial-durability research layer that compares reported CapEx, R&D,
operating cash flow, free cash flow, and balance-sheet capacity within each AI subsector. Phase 8 adds a
separate relative-valuation and growth-quality layer using transparent market-cap-to-financial ratios. It
keeps the original ranking model unchanged so the Phase 3 track record remains comparable over time. Phase 9 adds
a separate SEC filing catalyst-and-reaction monitor that classifies recent public filings and measures observed
one-day and five-trading-day price reactions without changing the original ranking score. Phase 10 adds
an integrated evidence brief that combines the existing research layers into a separate, transparent research
balance score, past-present-future narrative, supporting evidence, counter-evidence, and monitoring checklist.
Phase 11 adds a daily change monitor that preserves one research-state snapshot per New York business date,
compares the current refresh with the previous available snapshot, and highlights material changes in scores,
ranks, likelihoods, outlooks, valuation/capital profiles, market price, data coverage, and SEC filing activity. Phase 12 adds a separate AI subsector leadership and competitive-landscape layer that summarizes peer-group strength, breadth, growth, cash flow, concentration, and company positioning without changing the original ranking score.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests

try:
    import yfinance as yf
except ImportError as exc:  # Clear message for GitHub Actions/local runs.
    raise SystemExit("Missing dependency: yfinance. Run: pip install yfinance requests") from exc

OUTPUT_JSON = Path("ai_company_data.json")
OUTPUT_HTML = Path("ai-intelligence.html")
EASTERN = ZoneInfo("America/New_York")

SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "Stock Digest AI Intelligence support@winnersstock.com",
)
SEC_HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json",
}
SEC_DELAY_SECONDS = 0.16  # About 6 requests/second, below the SEC's 10 requests/second guideline.

COMPANIES = [
    {"ticker": "MSFT", "name": "Microsoft", "subsector": "Cloud & AI Platforms"},
    {"ticker": "GOOGL", "name": "Alphabet", "subsector": "Cloud & AI Platforms"},
    {"ticker": "AMZN", "name": "Amazon", "subsector": "Cloud & AI Platforms"},
    {"ticker": "META", "name": "Meta Platforms", "subsector": "Cloud & AI Platforms"},
    {"ticker": "NVDA", "name": "NVIDIA", "subsector": "Semiconductors & Infrastructure"},
    {"ticker": "AMD", "name": "Advanced Micro Devices", "subsector": "Semiconductors & Infrastructure"},
    {"ticker": "AVGO", "name": "Broadcom", "subsector": "Semiconductors & Infrastructure"},
    {"ticker": "MRVL", "name": "Marvell Technology", "subsector": "Semiconductors & Infrastructure"},
    {"ticker": "PLTR", "name": "Palantir Technologies", "subsector": "AI Software & Growth"},
    {"ticker": "SNOW", "name": "Snowflake", "subsector": "AI Software & Growth"},
    {"ticker": "AI", "name": "C3.ai", "subsector": "AI Software & Growth"},
    {"ticker": "PATH", "name": "UiPath", "subsector": "AI Software & Growth"},
]

BENCHMARKS = {"nasdaq100": "^NDX", "sp500": "^GSPC"}

# Standard XBRL concepts. Companies can use different permitted tags, so each metric
# lists several candidates and the script chooses the candidate with the best recent coverage.
DURATION_TAGS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
    ],
    "rnd": ["ResearchAndDevelopmentExpense"],
}

INSTANT_TAGS: dict[str, list[str]] = {
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "short_term_investments": [
        "ShortTermInvestments",
        "MarketableSecuritiesCurrent",
    ],
    "debt_current": [
        "LongTermDebtCurrent",
        "ShortTermBorrowings",
        "DebtCurrent",
    ],
    "debt_noncurrent": [
        "LongTermDebtNoncurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
    ],
}


@dataclass
class AnnualPoint:
    end: str
    filed: str
    value: float
    form: str


def safe_float(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def pct_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior in (None, 0):
        return None
    return round((current / prior - 1.0) * 100.0, 2)


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def money_round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def fetch_json(session: requests.Session, url: str) -> dict[str, Any]:
    response = session.get(url, headers=SEC_HEADERS, timeout=45)
    response.raise_for_status()
    time.sleep(SEC_DELAY_SECONDS)
    return response.json()


def load_ticker_cik_map(session: requests.Session) -> dict[str, int]:
    raw = fetch_json(session, "https://www.sec.gov/files/company_tickers.json")
    result: dict[str, int] = {}
    for row in raw.values():
        ticker = str(row.get("ticker", "")).upper()
        cik = row.get("cik_str")
        if ticker and cik is not None:
            result[ticker] = int(cik)
    return result


def duration_series_for_tag(companyfacts: dict[str, Any], tag: str) -> list[AnnualPoint]:
    units = (
        companyfacts.get("facts", {})
        .get("us-gaap", {})
        .get(tag, {})
        .get("units", {})
    )
    rows = units.get("USD", [])
    by_end: dict[str, AnnualPoint] = {}
    for row in rows:
        form = str(row.get("form", ""))
        start = row.get("start")
        end = row.get("end")
        filed = str(row.get("filed", ""))
        value = safe_float(row.get("val"))
        if form not in {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}:
            continue
        if not start or not end or value is None:
            continue
        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            days = (end_dt - start_dt).days
        except ValueError:
            continue
        if not 300 <= days <= 430:
            continue
        point = AnnualPoint(end=end, filed=filed, value=value, form=form)
        existing = by_end.get(end)
        if existing is None or filed > existing.filed:
            by_end[end] = point
    return sorted(by_end.values(), key=lambda item: item.end)


def choose_duration_series(companyfacts: dict[str, Any], tags: Iterable[str]) -> tuple[str | None, list[AnnualPoint]]:
    candidates: list[tuple[tuple[int, str], str, list[AnnualPoint]]] = []
    for tag in tags:
        series = duration_series_for_tag(companyfacts, tag)
        if series:
            recent = [p for p in series if p.end >= "2015-01-01"]
            score = (len(recent), series[-1].end)
            candidates.append((score, tag, series))
    if not candidates:
        return None, []
    _, tag, series = max(candidates, key=lambda item: item[0])
    return tag, series[-10:]


def instant_value_for_tag(companyfacts: dict[str, Any], taxonomy: str, tag: str, unit: str) -> tuple[float | None, str | None]:
    units = (
        companyfacts.get("facts", {})
        .get(taxonomy, {})
        .get(tag, {})
        .get("units", {})
    )
    rows = units.get(unit, [])
    candidates: list[tuple[str, str, float]] = []
    for row in rows:
        form = str(row.get("form", ""))
        if form not in {"10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A"}:
            continue
        end = str(row.get("end", ""))
        filed = str(row.get("filed", ""))
        value = safe_float(row.get("val"))
        if end and value is not None:
            candidates.append((end, filed, value))
    if not candidates:
        return None, None
    end, _, value = max(candidates, key=lambda item: (item[0], item[1]))
    return value, end


def choose_instant_value(companyfacts: dict[str, Any], tags: Iterable[str]) -> tuple[float | None, str | None, str | None]:
    choices: list[tuple[str, float, str]] = []
    for tag in tags:
        value, end = instant_value_for_tag(companyfacts, "us-gaap", tag, "USD")
        if value is not None and end:
            choices.append((end, value, tag))
    if not choices:
        return None, None, None
    end, value, tag = max(choices, key=lambda item: item[0])
    return value, end, tag


def latest_shares(companyfacts: dict[str, Any]) -> tuple[float | None, str | None]:
    for taxonomy, tag in [
        ("dei", "EntityCommonStockSharesOutstanding"),
        ("us-gaap", "CommonStockSharesOutstanding"),
    ]:
        value, end = instant_value_for_tag(companyfacts, taxonomy, tag, "shares")
        if value is not None:
            return value, end
    return None, None


def series_to_year_map(series: list[AnnualPoint]) -> dict[str, float]:
    result: dict[str, float] = {}
    for point in series:
        result[point.end[:4]] = point.value
    return result


def duration_backtest_rows(companyfacts: dict[str, Any], tag: str | None) -> list[dict[str, Any]]:
    """Return annual facts with filing dates so historical tests use only then-public data."""
    if not tag:
        return []
    units = (
        companyfacts.get("facts", {})
        .get("us-gaap", {})
        .get(tag, {})
        .get("units", {})
    )
    rows = []
    seen = set()
    for row in units.get("USD", []):
        form = str(row.get("form", ""))
        start = row.get("start")
        end = row.get("end")
        filed = str(row.get("filed", ""))
        value = safe_float(row.get("val"))
        if form not in {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}:
            continue
        if not start or not end or not filed or value is None:
            continue
        try:
            days = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days
        except ValueError:
            continue
        if not 300 <= days <= 430:
            continue
        key = (str(end), filed, round(value, 4))
        if key in seen:
            continue
        seen.add(key)
        rows.append({"end": str(end), "filed": filed, "value": money_round(value), "form": form})
    return sorted(rows, key=lambda item: (item["filed"], item["end"]))


def instant_backtest_rows(companyfacts: dict[str, Any], tag: str | None) -> list[dict[str, Any]]:
    """Return balance-sheet facts with filing dates for point-in-time reconstruction."""
    if not tag:
        return []
    units = (
        companyfacts.get("facts", {})
        .get("us-gaap", {})
        .get(tag, {})
        .get("units", {})
    )
    rows = []
    seen = set()
    for row in units.get("USD", []):
        form = str(row.get("form", ""))
        end = str(row.get("end", ""))
        filed = str(row.get("filed", ""))
        value = safe_float(row.get("val"))
        if form not in {"10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A"}:
            continue
        if not end or not filed or value is None:
            continue
        key = (end, filed, round(value, 4))
        if key in seen:
            continue
        seen.add(key)
        rows.append({"end": end, "filed": filed, "value": money_round(value), "form": form})
    return sorted(rows, key=lambda item: (item["filed"], item["end"]))


def build_financial_record(companyfacts: dict[str, Any]) -> dict[str, Any]:
    picked_tags: dict[str, str | None] = {}
    series_maps: dict[str, dict[str, float]] = {}
    series_points: dict[str, list[AnnualPoint]] = {}
    for metric, tags in DURATION_TAGS.items():
        tag, series = choose_duration_series(companyfacts, tags)
        picked_tags[metric] = tag
        series_points[metric] = series
        series_maps[metric] = series_to_year_map(series)

    all_years = sorted(set().union(*(mapping.keys() for mapping in series_maps.values())))[-10:]
    history = []
    for year in all_years:
        revenue = series_maps["revenue"].get(year)
        ocf = series_maps["operating_cash_flow"].get(year)
        capex = series_maps["capex"].get(year)
        fcf = ocf - capex if ocf is not None and capex is not None else None
        history.append(
            {
                "year": year,
                "revenue": money_round(revenue),
                "net_income": money_round(series_maps["net_income"].get(year)),
                "operating_cash_flow": money_round(ocf),
                "capex": money_round(capex),
                "free_cash_flow": money_round(fcf),
                "rnd": money_round(series_maps["rnd"].get(year)),
            }
        )

    valid_revenue = [(y, v) for y, v in sorted(series_maps["revenue"].items()) if v is not None]
    latest_year = valid_revenue[-1][0] if valid_revenue else (all_years[-1] if all_years else None)
    prior_year = valid_revenue[-2][0] if len(valid_revenue) >= 2 else None

    def annual(metric: str, year: str | None) -> float | None:
        return series_maps[metric].get(year) if year else None

    latest_revenue = annual("revenue", latest_year)
    prior_revenue = annual("revenue", prior_year)
    latest_net_income = annual("net_income", latest_year)
    latest_ocf = annual("operating_cash_flow", latest_year)
    latest_capex = annual("capex", latest_year)
    latest_rnd = annual("rnd", latest_year)
    latest_fcf = latest_ocf - latest_capex if latest_ocf is not None and latest_capex is not None else None

    cash, cash_date, cash_tag = choose_instant_value(companyfacts, INSTANT_TAGS["cash"])
    short_inv, short_inv_date, short_inv_tag = choose_instant_value(companyfacts, INSTANT_TAGS["short_term_investments"])
    debt_current, debt_current_date, debt_current_tag = choose_instant_value(companyfacts, INSTANT_TAGS["debt_current"])
    debt_noncurrent, debt_noncurrent_date, debt_noncurrent_tag = choose_instant_value(companyfacts, INSTANT_TAGS["debt_noncurrent"])
    shares, shares_date = latest_shares(companyfacts)

    total_cash = None
    if cash is not None or short_inv is not None:
        total_cash = (cash or 0.0) + (short_inv or 0.0)
    total_debt = None
    if debt_current is not None or debt_noncurrent is not None:
        total_debt = (debt_current or 0.0) + (debt_noncurrent or 0.0)

    backtest_facts = {
        "duration": {
            metric: duration_backtest_rows(companyfacts, picked_tags.get(metric))
            for metric in DURATION_TAGS
        },
        "instant": {
            "cash": instant_backtest_rows(companyfacts, cash_tag),
            "short_term_investments": instant_backtest_rows(companyfacts, short_inv_tag),
            "debt_current": instant_backtest_rows(companyfacts, debt_current_tag),
            "debt_noncurrent": instant_backtest_rows(companyfacts, debt_noncurrent_tag),
        },
    }

    return {
        "latest_fiscal_year": latest_year,
        "latest_reported_revenue": money_round(latest_revenue),
        "revenue_growth_pct": pct_change(latest_revenue, prior_revenue),
        "latest_net_income": money_round(latest_net_income),
        "latest_operating_cash_flow": money_round(latest_ocf),
        "latest_capex": money_round(latest_capex),
        "latest_free_cash_flow": money_round(latest_fcf),
        "latest_rnd": money_round(latest_rnd),
        "net_margin_pct": round(latest_net_income / latest_revenue * 100, 2) if latest_net_income is not None and latest_revenue else None,
        "fcf_margin_pct": round(latest_fcf / latest_revenue * 100, 2) if latest_fcf is not None and latest_revenue else None,
        "capex_intensity_pct": round(latest_capex / latest_revenue * 100, 2) if latest_capex is not None and latest_revenue else None,
        "rnd_intensity_pct": round(latest_rnd / latest_revenue * 100, 2) if latest_rnd is not None and latest_revenue else None,
        "cash_and_short_investments": money_round(total_cash),
        "total_debt": money_round(total_debt),
        "shares_outstanding": money_round(shares),
        "balance_sheet_date": max(filter(None, [cash_date, short_inv_date, debt_current_date, debt_noncurrent_date, shares_date]), default=None),
        "history": history,
        "xbrl_tags": {
            **picked_tags,
            "cash": cash_tag,
            "short_term_investments": short_inv_tag,
            "debt_current": debt_current_tag,
            "debt_noncurrent": debt_noncurrent_tag,
        },
        "_backtest_facts": backtest_facts,
    }


def latest_filings(submissions: dict[str, Any], cik: int) -> list[dict[str, str]]:
    """Return recent material and periodic SEC filings with available 8-K item codes."""
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    documents = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])
    item_codes = recent.get("items", [])
    filings = []
    allowed = {"10-K", "10-Q", "8-K", "20-F", "6-K"}
    for index, form in enumerate(forms):
        if form not in allowed:
            continue
        try:
            accession = accessions[index]
            document = documents[index]
            date = dates[index]
        except IndexError:
            continue
        accession_path = accession.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_path}/{document}"
        filings.append(
            {
                "form": form,
                "date": date,
                "description": descriptions[index] if index < len(descriptions) else "",
                "items": item_codes[index] if index < len(item_codes) else "",
                "url": url,
            }
        )
        if len(filings) >= 12:
            break
    return filings


def market_cap_tier(market_cap: float | None) -> str:
    if market_cap is None:
        return "Unclassified"
    if market_cap >= 200_000_000_000:
        return "Mega-Cap"
    if market_cap >= 10_000_000_000:
        return "Large-Cap"
    if market_cap >= 2_000_000_000:
        return "Mid-Cap"
    if market_cap >= 300_000_000:
        return "Small-Cap"
    return "Micro-Cap"


def nearest_return(series: Any, days: int) -> float | None:
    series = series.dropna()
    if len(series) < 2:
        return None
    target = series.index[-1] - __import__("datetime").timedelta(days=days)
    prior = series.loc[:target]
    if prior.empty:
        prior_value = safe_float(series.iloc[0])
    else:
        prior_value = safe_float(prior.iloc[-1])
    latest = safe_float(series.iloc[-1])
    return pct_change(latest, prior_value)


def build_price_data(tickers: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]], list[str], dict[str, Any]]:
    errors: list[str] = []
    all_symbols = tickers + list(BENCHMARKS.values())
    try:
        downloaded = yf.download(
            all_symbols,
            period="10y",
            interval="1d",
            auto_adjust=True,
            progress=False,
            group_by="column",
            threads=True,
        )
        close = downloaded["Close"] if hasattr(downloaded.columns, "levels") else downloaded
    except Exception as exc:  # noqa: BLE001 - preserve prior data when an upstream service fails.
        return {}, [], [f"Price download failed: {exc}"], {}

    company_market: dict[str, Any] = {}
    price_history: dict[str, Any] = {}
    normalized_daily = []
    for ticker in tickers:
        try:
            series = close[ticker].dropna()
        except Exception:
            errors.append(f"No price series returned for {ticker}")
            continue
        if series.empty:
            errors.append(f"No price history returned for {ticker}")
            continue
        latest_price = safe_float(series.iloc[-1])
        first_price = safe_float(series.iloc[0])
        normalized = series / first_price * 100 if first_price else series * math.nan
        normalized.name = ticker
        normalized_daily.append(normalized)
        price_history[ticker] = series.copy()
        ma50 = safe_float(series.tail(50).mean()) if len(series) >= 20 else None
        ma200 = safe_float(series.tail(200).mean()) if len(series) >= 50 else None
        market_cap = None
        try:
            fast = yf.Ticker(ticker).fast_info
            market_cap = safe_float(fast.get("market_cap"))
        except Exception:
            pass
        company_market[ticker] = {
            "latest_price": round(latest_price, 4) if latest_price is not None else None,
            "price_date": str(series.index[-1].date()),
            "return_30d_pct": nearest_return(series, 30),
            "return_1y_pct": nearest_return(series, 365),
            "above_50_day": bool(latest_price is not None and ma50 is not None and latest_price > ma50),
            "above_200_day": bool(latest_price is not None and ma200 is not None and latest_price > ma200),
            "market_cap": money_round(market_cap),
        }

    index_rows: list[dict[str, Any]] = []
    if normalized_daily:
        import pandas as pd

        frame = pd.concat(normalized_daily, axis=1)
        ai_daily = frame.mean(axis=1, skipna=True)
        weekly = ai_daily.resample("W-FRI").last().dropna()

        benchmark_series: dict[str, Any] = {}
        for key, symbol in BENCHMARKS.items():
            try:
                s = close[symbol].dropna()
                price_history[key] = s.copy()
                price_history[symbol] = s.copy()
                benchmark_series[key] = s / s.iloc[0] * 100
            except Exception:
                benchmark_series[key] = None

        for date, value in weekly.items():
            row: dict[str, Any] = {"date": str(date.date()), "ai_index": round(float(value), 3)}
            for key, series in benchmark_series.items():
                if series is None:
                    row[key] = None
                    continue
                subset = series.loc[:date]
                row[key] = round(float(subset.iloc[-1]), 3) if not subset.empty else None
            index_rows.append(row)

    return company_market, index_rows[-530:], errors, price_history


def component_scores(record: dict[str, Any]) -> dict[str, float | None]:
    rev_growth = safe_float(record.get("revenue_growth_pct"))
    fcf_margin = safe_float(record.get("fcf_margin_pct"))
    net_margin = safe_float(record.get("net_margin_pct"))
    cash = safe_float(record.get("cash_and_short_investments"))
    debt = safe_float(record.get("total_debt"))
    return_1y = safe_float(record.get("return_1y_pct"))
    investment_intensity = sum(
        value or 0.0
        for value in [
            safe_float(record.get("capex_intensity_pct")),
            safe_float(record.get("rnd_intensity_pct")),
        ]
    )

    growth = clamp(50 + rev_growth * 2.0) if rev_growth is not None else None
    fcf = clamp(50 + fcf_margin * (2.2 if fcf_margin >= 0 else 3.0)) if fcf_margin is not None else None
    profitability = clamp(50 + net_margin * (2.0 if net_margin >= 0 else 2.5)) if net_margin is not None else None

    balance = None
    if cash is not None or debt is not None:
        cash_value = cash or 0.0
        debt_value = debt or 0.0
        denominator = cash_value + debt_value
        balance = 100.0 if denominator == 0 and cash_value > 0 else (cash_value / denominator * 100 if denominator else 50.0)

    momentum_parts = []
    if return_1y is not None:
        momentum_parts.append(clamp(50 + return_1y * 0.7))
    if record.get("above_50_day") is not None:
        momentum_parts.append(75.0 if record.get("above_50_day") else 25.0)
    if record.get("above_200_day") is not None:
        momentum_parts.append(80.0 if record.get("above_200_day") else 20.0)
    momentum = statistics.fmean(momentum_parts) if momentum_parts else None

    investment = clamp(30 + investment_intensity * 1.4) if investment_intensity else None
    return {
        "growth": round(growth, 1) if growth is not None else None,
        "free_cash_flow": round(fcf, 1) if fcf is not None else None,
        "financial_strength": round(balance, 1) if balance is not None else None,
        "profitability": round(profitability, 1) if profitability is not None else None,
        "momentum": round(momentum, 1) if momentum is not None else None,
        "strategic_investment": round(investment, 1) if investment is not None else None,
    }


def weighted_score(components: dict[str, float | None]) -> float | None:
    weights = {
        "growth": 25,
        "free_cash_flow": 20,
        "financial_strength": 15,
        "profitability": 10,
        "momentum": 20,
        "strategic_investment": 10,
    }
    available = [(key, value) for key, value in components.items() if value is not None]
    if not available:
        return None
    weight_total = sum(weights[key] for key, _ in available)
    score = sum(value * weights[key] for key, value in available) / weight_total
    return round(score, 1)


def automated_summary(record: dict[str, Any]) -> str:
    parts = []
    growth = safe_float(record.get("revenue_growth_pct"))
    if growth is not None:
        direction = "grew" if growth >= 0 else "declined"
        parts.append(f"Reported annual revenue {direction} {abs(growth):.1f}% in the latest fiscal year")
    fcf = safe_float(record.get("latest_free_cash_flow"))
    fcf_margin = safe_float(record.get("fcf_margin_pct"))
    if fcf is not None:
        status = "positive" if fcf >= 0 else "negative"
        margin_text = f" at a {fcf_margin:.1f}% margin" if fcf_margin is not None else ""
        parts.append(f"standardized free cash flow was {status}{margin_text}")
    if record.get("above_50_day") is not None and record.get("above_200_day") is not None:
        if record["above_50_day"] and record["above_200_day"]:
            parts.append("the share price was above both its 50-day and 200-day averages")
        elif not record["above_50_day"] and not record["above_200_day"]:
            parts.append("the share price was below both its 50-day and 200-day averages")
        else:
            parts.append("price momentum was mixed across the 50-day and 200-day averages")
    cash = safe_float(record.get("cash_and_short_investments"))
    debt = safe_float(record.get("total_debt"))
    if cash is not None and debt is not None:
        parts.append("cash exceeded reported debt" if cash > debt else "reported debt exceeded cash and short-term investments")
    if not parts:
        return "Insufficient standardized data is available for an automated summary. Review the source filings directly."
    return "; ".join(parts) + ". This is an automated factual summary, not a forecast or recommendation."



def median_value(values: Iterable[Any]) -> float | None:
    cleaned = [value for value in (safe_float(v) for v in values) if value is not None]
    return round(float(statistics.median(cleaned)), 2) if cleaned else None


def percentile_rank(value: Any, values: Iterable[Any], higher_is_better: bool = True) -> float | None:
    current = safe_float(value)
    cleaned = [v for v in (safe_float(item) for item in values) if v is not None]
    if current is None or not cleaned:
        return None
    if len(cleaned) == 1:
        return 50.0
    below = sum(v < current for v in cleaned)
    equal = sum(v == current for v in cleaned)
    percentile = (below + 0.5 * equal) / len(cleaned) * 100.0
    if not higher_is_better:
        percentile = 100.0 - percentile
    return round(percentile, 1)


def data_coverage(record: dict[str, Any]) -> tuple[float, list[str]]:
    checks = [
        ("latest_reported_revenue", "Revenue was not retrieved from standardized SEC facts."),
        ("revenue_growth_pct", "Revenue growth could not be calculated."),
        ("latest_net_income", "Net income was not retrieved."),
        ("latest_operating_cash_flow", "Operating cash flow was not retrieved."),
        ("latest_capex", "Cash capital expenditures were not retrieved; standardized free cash flow may be unavailable."),
        ("latest_rnd", "Research and development expense was not separately retrieved."),
        ("cash_and_short_investments", "Cash and short-term investments were not fully retrieved."),
        ("total_debt", "Total debt was not fully retrieved."),
        ("market_cap", "Current market capitalization was unavailable."),
        ("return_1y_pct", "One-year market-price performance was unavailable."),
    ]
    missing = [message for key, message in checks if record.get(key) is None]
    coverage = round((len(checks) - len(missing)) / len(checks) * 100.0, 1)
    return coverage, missing


def strength_and_risk_analysis(record: dict[str, Any], peers: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    strengths: list[str] = []
    risks: list[str] = []

    metric_specs = [
        ("revenue_growth_pct", "Revenue growth is among the stronger results in its peer group.", "Revenue growth trails most companies in its peer group."),
        ("fcf_margin_pct", "Free-cash-flow margin compares favorably with peers.", "Free-cash-flow margin is weak relative to peers."),
        ("net_margin_pct", "Net profitability is strong relative to peers.", "Net profitability is weak relative to peers."),
        ("return_1y_pct", "One-year price momentum ranks favorably within the peer group.", "One-year price momentum trails the peer group."),
    ]
    for key, strength_text, risk_text in metric_specs:
        percentile = percentile_rank(record.get(key), [peer.get(key) for peer in peers])
        if percentile is not None and percentile >= 67:
            strengths.append(strength_text)
        elif percentile is not None and percentile <= 33:
            risks.append(risk_text)

    fcf = safe_float(record.get("latest_free_cash_flow"))
    if fcf is not None:
        if fcf > 0:
            strengths.append("The latest standardized free cash flow is positive.")
        elif fcf < 0:
            risks.append("The latest standardized free cash flow is negative.")

    growth = safe_float(record.get("revenue_growth_pct"))
    if growth is not None and growth < 0:
        risks.append("Reported annual revenue declined in the latest fiscal year.")

    cash = safe_float(record.get("cash_and_short_investments"))
    debt = safe_float(record.get("total_debt"))
    if cash is not None and debt is not None:
        if cash > debt:
            strengths.append("Cash and short-term investments exceed reported debt.")
        elif debt > cash * 1.5:
            risks.append("Reported debt materially exceeds cash and short-term investments.")

    if record.get("above_50_day") is True and record.get("above_200_day") is True:
        strengths.append("The share price is above both its 50-day and 200-day averages.")
    elif record.get("above_50_day") is False and record.get("above_200_day") is False:
        risks.append("The share price is below both its 50-day and 200-day averages.")

    # Keep the lists focused and remove repeated wording while preserving order.
    strengths = list(dict.fromkeys(strengths))[:4]
    risks = list(dict.fromkeys(risks))[:4]
    if not strengths:
        strengths = ["No standout strength was identified from the currently available standardized metrics."]
    if not risks:
        risks = ["No major quantitative warning was identified, but qualitative and valuation risks still require review."]
    return strengths, risks


def add_peer_intelligence(companies: list[dict[str, Any]]) -> None:
    metric_labels = {
        "score": "Company score",
        "revenue_growth_pct": "Revenue growth",
        "fcf_margin_pct": "FCF margin",
        "net_margin_pct": "Net margin",
        "return_1y_pct": "1-year return",
    }
    for company in companies:
        peers = [item for item in companies if item.get("subsector") == company.get("subsector")]
        peer_rows = sorted(peers, key=lambda item: (item.get("score") is not None, item.get("score") or -1), reverse=True)
        peer_metrics: list[dict[str, Any]] = []
        for key, label in metric_labels.items():
            peer_metrics.append({
                "key": key,
                "label": label,
                "company_value": company.get(key),
                "peer_median": median_value(peer.get(key) for peer in peers),
                "peer_percentile": percentile_rank(company.get(key), [peer.get(key) for peer in peers]),
            })
        company["peer_metrics"] = peer_metrics
        company["peer_count"] = len(peers)
        company["peer_snapshot"] = [
            {
                "ticker": peer.get("ticker"),
                "name": peer.get("name"),
                "score": peer.get("score"),
                "revenue_growth_pct": peer.get("revenue_growth_pct"),
                "fcf_margin_pct": peer.get("fcf_margin_pct"),
                "return_1y_pct": peer.get("return_1y_pct"),
            }
            for peer in peer_rows
        ]
        coverage, warnings = data_coverage(company)
        company["data_coverage_pct"] = coverage
        company["data_quality"] = "High" if coverage >= 80 else "Moderate" if coverage >= 60 else "Limited"
        company["data_warnings"] = warnings
        strengths, risks = strength_and_risk_analysis(company, peers)
        company["strengths"] = strengths
        company["risks"] = risks

    for tier in sorted({company.get("market_cap_tier") for company in companies}):
        tier_group = sorted(
            [company for company in companies if company.get("market_cap_tier") == tier],
            key=lambda item: (item.get("score") is not None, item.get("score") or -1),
            reverse=True,
        )
        for rank, company in enumerate(tier_group, start=1):
            company["cap_group_rank"] = rank if company.get("score") is not None else None
            company["cap_group_count"] = len(tier_group)



def latest_value_as_of(rows: list[dict[str, Any]], as_of: datetime) -> float | None:
    cutoff = as_of.date().isoformat()
    eligible = [row for row in rows if str(row.get("filed", "")) <= cutoff]
    if not eligible:
        return None
    row = max(eligible, key=lambda item: (str(item.get("filed", "")), str(item.get("end", ""))))
    return safe_float(row.get("value"))


def annual_rows_as_of(rows: list[dict[str, Any]], as_of: datetime) -> list[dict[str, Any]]:
    """Return the latest then-public filing for each annual period."""
    cutoff = as_of.date().isoformat()
    by_end: dict[str, dict[str, Any]] = {}
    for row in rows:
        filed = str(row.get("filed", ""))
        end = str(row.get("end", ""))
        if not filed or not end or filed > cutoff:
            continue
        existing = by_end.get(end)
        if existing is None or filed > str(existing.get("filed", "")):
            by_end[end] = row
    return [by_end[key] for key in sorted(by_end)]


def annual_metric_for_period(rows: list[dict[str, Any]], as_of: datetime, period_end: str | None) -> float | None:
    if not period_end:
        return None
    available = annual_rows_as_of(rows, as_of)
    exact = [row for row in available if row.get("end") == period_end]
    if exact:
        return safe_float(exact[-1].get("value"))
    prior = [row for row in available if str(row.get("end", "")) <= period_end]
    return safe_float(prior[-1].get("value")) if prior else None


def price_slice_as_of(series: Any, as_of: datetime) -> Any:
    try:
        target = as_of
        if getattr(series.index, "tz", None) is None:
            target = target.replace(tzinfo=None)
        return series.loc[series.index <= target].dropna()
    except Exception:
        return None


def historical_record_as_of(company: dict[str, Any], series: Any, as_of: datetime) -> dict[str, Any] | None:
    facts = company.get("_backtest_facts") or {}
    duration = facts.get("duration") or {}
    instant = facts.get("instant") or {}
    revenues = annual_rows_as_of(duration.get("revenue", []), as_of)
    if len(revenues) < 2:
        return None
    latest_revenue_row = revenues[-1]
    prior_revenue_row = revenues[-2]
    period_end = str(latest_revenue_row.get("end", ""))
    latest_revenue = safe_float(latest_revenue_row.get("value"))
    prior_revenue = safe_float(prior_revenue_row.get("value"))
    if latest_revenue in (None, 0):
        return None

    net_income = annual_metric_for_period(duration.get("net_income", []), as_of, period_end)
    ocf = annual_metric_for_period(duration.get("operating_cash_flow", []), as_of, period_end)
    capex = annual_metric_for_period(duration.get("capex", []), as_of, period_end)
    rnd = annual_metric_for_period(duration.get("rnd", []), as_of, period_end)
    fcf = ocf - capex if ocf is not None and capex is not None else None

    cash = latest_value_as_of(instant.get("cash", []), as_of)
    short_inv = latest_value_as_of(instant.get("short_term_investments", []), as_of)
    debt_current = latest_value_as_of(instant.get("debt_current", []), as_of)
    debt_noncurrent = latest_value_as_of(instant.get("debt_noncurrent", []), as_of)
    total_cash = (cash or 0.0) + (short_inv or 0.0) if cash is not None or short_inv is not None else None
    total_debt = (debt_current or 0.0) + (debt_noncurrent or 0.0) if debt_current is not None or debt_noncurrent is not None else None

    prices = price_slice_as_of(series, as_of)
    if prices is None or len(prices) < 50:
        return None
    latest_price = safe_float(prices.iloc[-1])
    one_year_return = nearest_return(prices, 365)
    ma50 = safe_float(prices.tail(50).mean()) if len(prices) >= 50 else None
    ma200 = safe_float(prices.tail(200).mean()) if len(prices) >= 200 else None

    record = {
        "ticker": company.get("ticker"),
        "name": company.get("name"),
        "subsector": company.get("subsector"),
        "as_of": as_of.date().isoformat(),
        "fundamental_period_end": period_end,
        "latest_reported_revenue": latest_revenue,
        "revenue_growth_pct": pct_change(latest_revenue, prior_revenue),
        "latest_net_income": net_income,
        "latest_operating_cash_flow": ocf,
        "latest_capex": capex,
        "latest_free_cash_flow": fcf,
        "latest_rnd": rnd,
        "net_margin_pct": round(net_income / latest_revenue * 100, 2) if net_income is not None else None,
        "fcf_margin_pct": round(fcf / latest_revenue * 100, 2) if fcf is not None else None,
        "capex_intensity_pct": round(capex / latest_revenue * 100, 2) if capex is not None else None,
        "rnd_intensity_pct": round(rnd / latest_revenue * 100, 2) if rnd is not None else None,
        "cash_and_short_investments": total_cash,
        "total_debt": total_debt,
        "latest_price": latest_price,
        "return_1y_pct": one_year_return,
        "above_50_day": bool(latest_price is not None and ma50 is not None and latest_price > ma50),
        "above_200_day": bool(latest_price is not None and ma200 is not None and latest_price > ma200),
    }
    record["score_components"] = component_scores(record)
    record["component_count"] = sum(value is not None for value in record["score_components"].values())
    record["score"] = weighted_score(record["score_components"])
    return record


def price_at_or_before(series: Any, target_date: datetime) -> float | None:
    try:
        target = target_date
        if getattr(series.index, "tz", None) is None:
            target = target.replace(tzinfo=None)
        subset = series.loc[series.index <= target].dropna()
        return safe_float(subset.iloc[-1]) if not subset.empty else None
    except Exception:
        return None


def forward_return(series: Any, start: datetime, days: int) -> float | None:
    entry = price_at_or_before(series, start)
    end = price_at_or_after(series, start + timedelta(days=days))
    return pct_change(end, entry)


def monthly_rebalance_dates(series: Any, years: int = 5) -> list[datetime]:
    if series is None or getattr(series, "empty", True):
        return []
    latest_index = series.dropna().index[-1]
    latest = latest_index.to_pydatetime() if hasattr(latest_index, "to_pydatetime") else latest_index
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    cutoff = latest - timedelta(days=365 * years)
    by_month: dict[tuple[int, int], datetime] = {}
    for item in series.dropna().index:
        current = item.to_pydatetime() if hasattr(item, "to_pydatetime") else item
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        if current < cutoff:
            continue
        by_month[(current.year, current.month)] = current
    return [by_month[key] for key in sorted(by_month)]


def score_band(score: float | None) -> str | None:
    if score is None:
        return None
    if score < 60:
        return "Below 60"
    if score < 70:
        return "60–69.9"
    if score < 80:
        return "70–79.9"
    return "80 and above"



def likelihood_research_range(wins: int, observations: int, prior_strength: int = 10) -> tuple[float, float, float]:
    """Return a conservative beta-smoothed estimate and approximate 80% research range."""
    prior_wins = prior_strength / 2.0
    alpha = wins + prior_wins
    beta = max(0, observations - wins) + prior_wins
    total = alpha + beta
    estimate = alpha / total if total else 0.5
    variance = (alpha * beta) / ((total ** 2) * (total + 1.0)) if total > 0 else 0.0
    spread = 1.2815515655446004 * math.sqrt(max(0.0, variance))
    low = max(0.0, estimate - spread)
    high = min(1.0, estimate + spread)
    return round(estimate * 100.0, 1), round(low * 100.0, 1), round(high * 100.0, 1)


def build_likelihood_research(all_observations: list[dict[str, Any]], companies: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a chronological development/validation likelihood model for 12-month peer outperformance."""
    matured = [
        row for row in all_observations
        if row.get("days") == 365
        and row.get("band")
        and row.get("as_of")
        and row.get("excess_peer") is not None
    ]
    dates = sorted({str(row.get("as_of")) for row in matured})
    if len(dates) < 8:
        for company in companies:
            company["likelihood_score_band"] = score_band(safe_float(company.get("score")))
            company["outperformance_likelihood_12m_pct"] = None
            company["likelihood_range_low_pct"] = None
            company["likelihood_range_high_pct"] = None
            company["likelihood_calibration_observations"] = 0
            company["likelihood_validation_observations"] = 0
            company["likelihood_status"] = "Insufficient matured backtest history"
        return {
            "status": "Insufficient matured history for Phase 5 likelihood research",
            "horizon": "12 months versus equal-weighted prototype subsector peers",
            "calibration_period": None,
            "validation_period": None,
            "calibration_observations": 0,
            "validation_observations": 0,
            "eligible_company_count": 0,
            "bands": [],
            "limitations": [
                "No likelihood estimate is displayed until a score band has at least 12 calibration observations.",
                "This is research calibration, not a forecast, guarantee, price target, or investment recommendation.",
            ],
        }

    split_index = min(len(dates) - 1, max(1, int(len(dates) * 0.70)))
    calibration_dates = set(dates[:split_index])
    validation_dates = set(dates[split_index:])
    calibration = [row for row in matured if str(row.get("as_of")) in calibration_dates]
    validation = [row for row in matured if str(row.get("as_of")) in validation_dates]

    band_order = ["Below 60", "60–69.9", "70–79.9", "80 and above"]
    band_models: list[dict[str, Any]] = []
    prediction_by_band: dict[str, float] = {}
    validation_pairs: list[tuple[float, int]] = []

    for band in band_order:
        cal_rows = [row for row in calibration if row.get("band") == band]
        val_rows = [row for row in validation if row.get("band") == band]
        cal_wins = sum(safe_float(row.get("excess_peer")) > 0 for row in cal_rows)
        estimate, low, high = likelihood_research_range(cal_wins, len(cal_rows))
        prediction_by_band[band] = estimate
        val_wins = sum(safe_float(row.get("excess_peer")) > 0 for row in val_rows)
        val_actual = round(val_wins / len(val_rows) * 100.0, 1) if val_rows else None
        absolute_error = round(abs(estimate - val_actual), 1) if val_actual is not None else None
        for row in val_rows:
            validation_pairs.append((estimate / 100.0, 1 if safe_float(row.get("excess_peer")) > 0 else 0))

        if len(cal_rows) < 12:
            status = "Insufficient calibration sample"
        elif len(val_rows) < 8:
            status = "Limited validation sample"
        elif absolute_error is not None and absolute_error <= 10:
            status = "Developing validation"
        else:
            status = "Research only"

        band_models.append({
            "score_band": band,
            "calibration_observations": len(cal_rows),
            "calibration_outperformed_count": cal_wins,
            "smoothed_likelihood_pct": estimate if len(cal_rows) >= 12 else None,
            "research_range_low_pct": low if len(cal_rows) >= 12 else None,
            "research_range_high_pct": high if len(cal_rows) >= 12 else None,
            "validation_observations": len(val_rows),
            "validation_outperformed_count": val_wins,
            "validation_actual_rate_pct": val_actual,
            "validation_absolute_error_pct": absolute_error if len(cal_rows) >= 12 else None,
            "status": status,
        })

    band_lookup = {row["score_band"]: row for row in band_models}
    eligible = 0
    for company in companies:
        band = score_band(safe_float(company.get("score")))
        model = band_lookup.get(band or "", {})
        estimate = model.get("smoothed_likelihood_pct")
        company["likelihood_score_band"] = band
        company["outperformance_likelihood_12m_pct"] = estimate
        company["likelihood_range_low_pct"] = model.get("research_range_low_pct")
        company["likelihood_range_high_pct"] = model.get("research_range_high_pct")
        company["likelihood_calibration_observations"] = model.get("calibration_observations", 0)
        company["likelihood_validation_observations"] = model.get("validation_observations", 0)
        company["likelihood_validation_actual_pct"] = model.get("validation_actual_rate_pct")
        company["likelihood_status"] = model.get("status", "No score-band model")
        if estimate is not None:
            eligible += 1

    brier = (
        round(statistics.fmean((prediction - outcome) ** 2 for prediction, outcome in validation_pairs), 4)
        if validation_pairs else None
    )
    validated_bands = [row for row in band_models if row.get("validation_actual_rate_pct") is not None and row.get("smoothed_likelihood_pct") is not None]
    weighted_error_numerator = sum(
        safe_float(row.get("validation_absolute_error_pct")) * int(row.get("validation_observations") or 0)
        for row in validated_bands
    )
    weighted_error_denominator = sum(int(row.get("validation_observations") or 0) for row in validated_bands)
    weighted_mae = round(weighted_error_numerator / weighted_error_denominator, 1) if weighted_error_denominator else None

    return {
        "status": "Phase 5 backtest-based likelihood research; not a published investment probability",
        "horizon": "12 months versus equal-weighted prototype subsector peers",
        "method": "Chronological 70% calibration / 30% validation split. Score-band rates are beta-smoothed toward 50% using ten neutral prior observations.",
        "calibration_period": {
            "start": min(calibration_dates) if calibration_dates else None,
            "end": max(calibration_dates) if calibration_dates else None,
        },
        "validation_period": {
            "start": min(validation_dates) if validation_dates else None,
            "end": max(validation_dates) if validation_dates else None,
        },
        "calibration_observations": len(calibration),
        "validation_observations": len(validation),
        "eligible_company_count": eligible,
        "brier_score": brier,
        "weighted_validation_error_pct": weighted_mae,
        "bands": band_models,
        "limitations": [
            "The historical universe contains today's prototype companies, so survivorship and selection bias remain.",
            "Monthly 12-month observations overlap and are not independent; the displayed research range may understate real uncertainty.",
            "The likelihood is assigned by broad score band, not by a company-specific causal model.",
            "The peer benchmark is equal-weighted within the small prototype subsector groups and is not an investable published index.",
            "No score-band estimate is displayed with fewer than 12 calibration observations.",
            "This is research calibration, not a forecast, guarantee, price target, buy/sell signal, or personalized investment advice.",
        ],
    }

def build_historical_backtest(companies: list[dict[str, Any]], price_history: dict[str, Any]) -> dict[str, Any]:
    """Preliminary monthly point-in-time backtest for research validation, not a forecast."""
    benchmark = price_history.get("nasdaq100")
    if benchmark is None:
        benchmark = price_history.get("^NDX")
    dates = monthly_rebalance_dates(benchmark, years=5)
    horizons = [(90, "3 months"), (180, "6 months"), (365, "12 months")]
    company_by_ticker = {str(company.get("ticker")): company for company in companies}
    top_observations: dict[int, list[dict[str, float]]] = {days: [] for days, _ in horizons}
    all_observations: list[dict[str, Any]] = []
    tested_months = 0

    for as_of in dates:
        records = []
        for ticker, company in company_by_ticker.items():
            series = price_history.get(ticker)
            if series is None:
                continue
            record = historical_record_as_of(company, series, as_of)
            if record and record.get("score") is not None and record.get("component_count", 0) >= 4:
                records.append(record)
        if len(records) < 6:
            continue
        tested_months += 1
        ranked = sorted(records, key=lambda item: item.get("score") or -1, reverse=True)
        top_tickers = {str(item.get("ticker")) for item in ranked[:5]}

        for days, _label in horizons:
            universe_returns: dict[str, float] = {}
            subsector_returns: dict[str, list[tuple[str, float]]] = {}
            for record in ranked:
                ticker = str(record.get("ticker"))
                result = forward_return(price_history.get(ticker), as_of, days)
                if result is None:
                    continue
                universe_returns[ticker] = result
                subsector_returns.setdefault(str(record.get("subsector")), []).append((ticker, result))

            ndx_series = price_history.get("nasdaq100")
            if ndx_series is None:
                ndx_series = price_history.get("^NDX")
            sp_series = price_history.get("sp500")
            if sp_series is None:
                sp_series = price_history.get("^GSPC")
            ndx_return = forward_return(ndx_series, as_of, days)
            sp_return = forward_return(sp_series, as_of, days)
            for record in ranked:
                ticker = str(record.get("ticker"))
                company_return = universe_returns.get(ticker)
                if company_return is None:
                    continue
                peers = [value for peer_ticker, value in subsector_returns.get(str(record.get("subsector")), []) if peer_ticker != ticker]
                peer_return = statistics.fmean(peers) if peers else None
                observation = {
                    "as_of": as_of.date().isoformat(),
                    "ticker": ticker,
                    "subsector": record.get("subsector"),
                    "score": safe_float(record.get("score")),
                    "band": score_band(safe_float(record.get("score"))),
                    "company_return": company_return,
                    "peer_return": peer_return,
                    "excess_peer": company_return - peer_return if peer_return is not None else None,
                    "nasdaq100_return": ndx_return,
                    "excess_nasdaq100": company_return - ndx_return if ndx_return is not None else None,
                    "sp500_return": sp_return,
                    "excess_sp500": company_return - sp_return if sp_return is not None else None,
                    "days": days,
                    "is_top5": ticker in top_tickers,
                }
                all_observations.append(observation)
                if ticker in top_tickers:
                    top_observations[days].append(observation)

    horizon_rows = []
    for days, label in horizons:
        rows = top_observations[days]
        peer_rows = [row for row in rows if row.get("excess_peer") is not None]
        ndx_rows = [row for row in rows if row.get("excess_nasdaq100") is not None]
        winners = sum((row.get("excess_peer") or 0) > 0 for row in peer_rows)
        ndx_winners = sum((row.get("excess_nasdaq100") or 0) > 0 for row in ndx_rows)
        horizon_rows.append({
            "days": days,
            "label": label,
            "selection_observations": len(rows),
            "peer_comparison_observations": len(peer_rows),
            "peer_outperformance_rate_pct": round(winners / len(peer_rows) * 100, 1) if peer_rows else None,
            "nasdaq100_outperformance_rate_pct": round(ndx_winners / len(ndx_rows) * 100, 1) if ndx_rows else None,
            "average_selection_return_pct": round(statistics.fmean(row["company_return"] for row in rows), 2) if rows else None,
            "average_excess_peer_pct": round(statistics.fmean(row["excess_peer"] for row in peer_rows), 2) if peer_rows else None,
            "average_excess_nasdaq100_pct": round(statistics.fmean(row["excess_nasdaq100"] for row in ndx_rows), 2) if ndx_rows else None,
        })

    band_rows = []
    band_order = ["Below 60", "60–69.9", "70–79.9", "80 and above"]
    for days, label in horizons:
        for band in band_order:
            rows = [row for row in all_observations if row.get("days") == days and row.get("band") == band]
            comparable = [row for row in rows if row.get("excess_peer") is not None]
            winners = sum((row.get("excess_peer") or 0) > 0 for row in comparable)
            band_rows.append({
                "score_band": band,
                "days": days,
                "horizon": label,
                "observations": len(rows),
                "peer_comparison_observations": len(comparable),
                "outperformed_peer_count": winners,
                "historical_peer_outperformance_rate_pct": round(winners / len(comparable) * 100, 1) if comparable else None,
                "average_return_pct": round(statistics.fmean(row["company_return"] for row in rows), 2) if rows else None,
                "average_excess_peer_pct": round(statistics.fmean(row["excess_peer"] for row in comparable), 2) if comparable else None,
            })

    comparable_count = sum(row.get("peer_comparison_observations", 0) for row in band_rows if row.get("days") == 365)
    readiness = "Early research sample"
    if tested_months >= 48 and comparable_count >= 250:
        readiness = "Large enough for model-development review, but not yet a published probability"
    elif tested_months >= 24 and comparable_count >= 100:
        readiness = "Developing research sample"

    return {
        "status": "Preliminary point-in-time retrospective backtest; not a probability forecast",
        "period_start": dates[0].date().isoformat() if dates else None,
        "period_end": dates[-1].date().isoformat() if dates else None,
        "rebalance_frequency": "Monthly, using the final available trading date of each month",
        "tested_months": tested_months,
        "current_universe_size": len(companies),
        "selected_each_month": 5,
        "fundamental_policy": "Only annual facts with SEC filing dates on or before each test date are used. Price momentum uses only prices available through that date.",
        "calibration_readiness": readiness,
        "top5_horizons": horizon_rows,
        "score_band_calibration": band_rows,
        "_all_observations": all_observations,
        "limitations": [
            "The universe contains today's 12 prototype companies, creating survivorship and selection bias; delisted and omitted historical companies are not included.",
            "Monthly observations overlap, so they are not independent trials and should not be interpreted as a simple probability sample.",
            "The backtest uses annual standardized fundamentals, which can remain unchanged between filings.",
            "Peer benchmarks are equal-weighted within the small prototype subsectors and are not published investable sector indexes.",
            "Adjusted historical prices exclude transaction costs, taxes, market impact, and real-world execution delays.",
            "Historical outperformance rates describe this retrospective sample only and are not forecasts or investment recommendations.",
        ],
    }


def build_weekly_leaders(companies: list[dict[str, Any]]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    week_start = (now - __import__("datetime").timedelta(days=now.weekday())).date().isoformat()
    leaders = []
    for company in sorted(
        companies,
        key=lambda item: (item.get("score") is not None, item.get("score") or -1),
        reverse=True,
    )[:10]:
        leaders.append({
            "rank": company.get("overall_rank"),
            "ticker": company.get("ticker"),
            "name": company.get("name"),
            "subsector": company.get("subsector"),
            "score": company.get("score"),
            "subsector_rank": company.get("subsector_rank"),
            "data_coverage_pct": company.get("data_coverage_pct"),
            "key_strength": (company.get("strengths") or [None])[0],
            "key_risk": (company.get("risks") or [None])[0],
            "research_likelihood_12m_pct": company.get("outperformance_likelihood_12m_pct"),
            "likelihood_score_band": company.get("likelihood_score_band"),
            "likelihood_status": company.get("likelihood_status"),
        })
    return {
        "week_start": week_start,
        "as_of": now.isoformat(),
        "status": "Preliminary research ranking; refreshes with the daily dataset",
        "leaders": leaders,
    }



def current_week_start(now: datetime | None = None) -> str:
    """Return Monday's date for the current New York trading week."""
    current = (now or datetime.now(timezone.utc)).astimezone(EASTERN)
    return (current.date() - timedelta(days=current.weekday())).isoformat()


def create_or_preserve_weekly_snapshots(
    old_data: dict[str, Any], companies: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Create one immutable official snapshot per week and preserve all prior weeks."""
    snapshots = [
        item for item in old_data.get("weekly_snapshots", [])
        if isinstance(item, dict) and item.get("week_start")
    ]
    # Deduplicate older files by week, preferring the earliest saved snapshot.
    by_week: dict[str, dict[str, Any]] = {}
    for item in sorted(snapshots, key=lambda row: (row.get("week_start", ""), row.get("captured_at", ""))):
        by_week.setdefault(str(item.get("week_start")), item)

    week = current_week_start()
    eligible = [
        company for company in companies
        if company.get("score") is not None and company.get("latest_price") is not None
    ]
    if week not in by_week and len(eligible) >= 6:
        ranked = sorted(eligible, key=lambda item: item.get("score") or -1, reverse=True)
        universe = [
            {
                "ticker": company.get("ticker"),
                "name": company.get("name"),
                "subsector": company.get("subsector"),
                "market_cap_tier": company.get("market_cap_tier"),
                "official_rank": company.get("overall_rank"),
                "score": company.get("score"),
                "entry_price": company.get("latest_price"),
                "price_date": company.get("price_date"),
                "official_likelihood_12m_pct": company.get("outperformance_likelihood_12m_pct"),
                "likelihood_score_band": company.get("likelihood_score_band"),
                "likelihood_status": company.get("likelihood_status"),
            }
            for company in ranked
        ]
        by_week[week] = {
            "week_start": week,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "capture_policy": "First successful AI Intelligence refresh of the New York trading week",
            "leaders": universe[:10],
            "universe": universe,
        }
    return [by_week[key] for key in sorted(by_week)]


def snapshot_return(entry_price: Any, current_price: Any) -> float | None:
    return pct_change(safe_float(current_price), safe_float(entry_price))


def build_live_weekly_leaders(
    snapshots: list[dict[str, Any]], companies: list[dict[str, Any]]
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    week = current_week_start(now)
    snapshot = next((item for item in snapshots if item.get("week_start") == week), None)
    if snapshot is None and snapshots:
        snapshot = snapshots[-1]
    if snapshot is None:
        return {
            "week_start": None,
            "as_of": now.isoformat(),
            "status": "Awaiting the first official Phase 3 weekly snapshot",
            "leaders": [],
        }

    current = {company.get("ticker"): company for company in companies}
    snapshot_universe = snapshot.get("universe", [])
    peer_returns: dict[str, list[float]] = {}
    for item in snapshot_universe:
        ticker = item.get("ticker")
        company = current.get(ticker, {})
        result = snapshot_return(item.get("entry_price"), company.get("latest_price"))
        if result is not None:
            peer_returns.setdefault(str(item.get("subsector")), []).append(result)

    leaders = []
    for official_rank, item in enumerate(snapshot.get("leaders", []), start=1):
        ticker = item.get("ticker")
        company = current.get(ticker, {})
        company_return = snapshot_return(item.get("entry_price"), company.get("latest_price"))
        peer_values = peer_returns.get(str(item.get("subsector")), [])
        peer_return = round(statistics.fmean(peer_values), 2) if peer_values else None
        relative = (
            round(company_return - peer_return, 2)
            if company_return is not None and peer_return is not None else None
        )
        live_rank = company.get("overall_rank")
        rank_change = (
            official_rank - live_rank
            if isinstance(live_rank, int) else None
        )
        leaders.append({
            "official_rank": official_rank,
            "live_rank": live_rank,
            "rank_change": rank_change,
            "ticker": ticker,
            "name": item.get("name"),
            "subsector": item.get("subsector"),
            "market_cap_tier": item.get("market_cap_tier"),
            "official_score": item.get("score"),
            "live_score": company.get("score"),
            "entry_price": item.get("entry_price"),
            "entry_price_date": item.get("price_date"),
            "current_price": company.get("latest_price"),
            "current_price_date": company.get("price_date"),
            "return_since_selection_pct": company_return,
            "peer_return_since_selection_pct": peer_return,
            "relative_return_pct": relative,
            "data_coverage_pct": company.get("data_coverage_pct"),
            "key_strength": (company.get("strengths") or [None])[0],
            "key_risk": (company.get("risks") or [None])[0],
            "research_likelihood_12m_pct": item.get("official_likelihood_12m_pct") if item.get("official_likelihood_12m_pct") is not None else company.get("outperformance_likelihood_12m_pct"),
            "likelihood_score_band": item.get("likelihood_score_band") or company.get("likelihood_score_band"),
            "likelihood_status": item.get("likelihood_status") or company.get("likelihood_status"),
        })
    return {
        "week_start": snapshot.get("week_start"),
        "captured_at": snapshot.get("captured_at"),
        "as_of": now.isoformat(),
        "status": "Official weekly snapshot with daily live performance updates",
        "leaders": leaders,
    }


def price_at_or_after(series: Any, target_date: datetime) -> float | None:
    """Return the first available closing price on or after a target date."""
    try:
        index = series.index
        # yfinance can return timezone-aware or timezone-naive indexes.
        target = target_date
        if getattr(index, "tz", None) is None:
            target = target.replace(tzinfo=None)
        subset = series.loc[index >= target]
        return safe_float(subset.iloc[0]) if not subset.empty else None
    except Exception:
        return None


def build_performance_scorecard(
    snapshots: list[dict[str, Any]], companies: list[dict[str, Any]], price_history: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate matured weekly selections at fixed horizons versus their subsector peers."""
    now = datetime.now(timezone.utc)
    horizons = [(30, "30 days"), (90, "3 months"), (180, "6 months"), (365, "12 months")]
    current = {company.get("ticker"): company for company in companies}
    horizon_rows = []

    for days, label in horizons:
        observations = []
        for snapshot in snapshots:
            try:
                start = datetime.fromisoformat(str(snapshot.get("captured_at", "")).replace("Z", "+00:00"))
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            target = start + timedelta(days=days)
            if now < target:
                continue

            universe = snapshot.get("universe", [])
            peer_outcomes: dict[str, list[float]] = {}
            outcome_by_ticker: dict[str, float] = {}
            for item in universe:
                ticker = item.get("ticker")
                entry = safe_float(item.get("entry_price"))
                series = price_history.get(ticker)
                end_price = price_at_or_after(series, target) if series is not None else None
                result = pct_change(end_price, entry)
                if result is not None:
                    outcome_by_ticker[str(ticker)] = result
                    peer_outcomes.setdefault(str(item.get("subsector")), []).append(result)

            for leader in snapshot.get("leaders", []):
                ticker = str(leader.get("ticker"))
                company_return = outcome_by_ticker.get(ticker)
                peers = peer_outcomes.get(str(leader.get("subsector")), [])
                peer_return = statistics.fmean(peers) if peers else None
                if company_return is None or peer_return is None:
                    continue
                observations.append({
                    "company_return": company_return,
                    "peer_return": peer_return,
                    "excess_return": company_return - peer_return,
                })

        count = len(observations)
        winners = sum(item["excess_return"] > 0 for item in observations)
        horizon_rows.append({
            "days": days,
            "label": label,
            "evaluated_selections": count,
            "outperformed_count": winners,
            "hit_rate_pct": round(winners / count * 100.0, 1) if count else None,
            "average_selection_return_pct": round(statistics.fmean(item["company_return"] for item in observations), 2) if count else None,
            "average_peer_return_pct": round(statistics.fmean(item["peer_return"] for item in observations), 2) if count else None,
            "average_excess_return_pct": round(statistics.fmean(item["excess_return"] for item in observations), 2) if count else None,
        })

    recent_weeks = []
    for snapshot in snapshots[-12:]:
        universe_current = {item.get("ticker"): item for item in snapshot.get("universe", [])}
        leader_returns = []
        excess_returns = []
        for leader in snapshot.get("leaders", []):
            ticker = leader.get("ticker")
            company = current.get(ticker, {})
            result = snapshot_return(leader.get("entry_price"), company.get("latest_price"))
            peer_results = []
            for item in snapshot.get("universe", []):
                if item.get("subsector") != leader.get("subsector"):
                    continue
                peer_company = current.get(item.get("ticker"), {})
                peer_result = snapshot_return(item.get("entry_price"), peer_company.get("latest_price"))
                if peer_result is not None:
                    peer_results.append(peer_result)
            peer_return = statistics.fmean(peer_results) if peer_results else None
            if result is not None:
                leader_returns.append(result)
            if result is not None and peer_return is not None:
                excess_returns.append(result - peer_return)
        recent_weeks.append({
            "week_start": snapshot.get("week_start"),
            "captured_at": snapshot.get("captured_at"),
            "top_company": (snapshot.get("leaders") or [{}])[0].get("name"),
            "selection_count": len(snapshot.get("leaders", [])),
            "average_return_to_date_pct": round(statistics.fmean(leader_returns), 2) if leader_returns else None,
            "average_excess_to_date_pct": round(statistics.fmean(excess_returns), 2) if excess_returns else None,
        })

    return {
        "tracking_started": snapshots[0].get("captured_at") if snapshots else None,
        "weeks_recorded": len(snapshots),
        "method": "Each official weekly Top 10 is frozen at the first successful refresh of the week and compared with the equal-weighted return of companies in the same prototype subsector.",
        "horizons": horizon_rows,
        "recent_weeks": recent_weeks,
    }


def merge_old_company(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    merged = dict(old)
    for key, value in new.items():
        if value not in (None, [], {}):
            merged[key] = value
    return merged



def annualized_growth(first_value: Any, last_value: Any, years: int) -> float | None:
    first = safe_float(first_value)
    last = safe_float(last_value)
    if first is None or last is None or first <= 0 or last <= 0 or years <= 0:
        return None
    try:
        return round(((last / first) ** (1.0 / years) - 1.0) * 100.0, 2)
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def historical_revenue_growth_rates(history: list[dict[str, Any]]) -> list[float]:
    rows = [row for row in history if safe_float(row.get("revenue")) not in (None, 0)]
    rates: list[float] = []
    for previous, current in zip(rows, rows[1:]):
        change = pct_change(safe_float(current.get("revenue")), safe_float(previous.get("revenue")))
        if change is not None and math.isfinite(change):
            rates.append(change)
    return rates


def historical_fcf_margins(history: list[dict[str, Any]]) -> list[float]:
    margins: list[float] = []
    for row in history:
        revenue = safe_float(row.get("revenue"))
        fcf = safe_float(row.get("free_cash_flow"))
        if revenue not in (None, 0) and fcf is not None:
            margins.append(fcf / revenue * 100.0)
    return margins


def weighted_available(values: list[tuple[float | None, float]]) -> float | None:
    available = [(value, weight) for value, weight in values if value is not None and math.isfinite(value)]
    if not available:
        return None
    total_weight = sum(weight for _, weight in available)
    if total_weight <= 0:
        return None
    return sum(value * weight for value, weight in available) / total_weight


def project_operating_scenario(
    latest_revenue: float, start_year: int, growth_pct: float, fcf_margin_pct: float | None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    revenue = latest_revenue
    for offset in range(1, 4):
        revenue *= 1.0 + growth_pct / 100.0
        projected_fcf = revenue * fcf_margin_pct / 100.0 if fcf_margin_pct is not None else None
        rows.append({
            "year": str(start_year + offset),
            "revenue": money_round(revenue),
            "free_cash_flow": money_round(projected_fcf),
            "revenue_growth_pct": round(growth_pct, 2),
            "fcf_margin_pct": round(fcf_margin_pct, 2) if fcf_margin_pct is not None else None,
        })
    return rows


def add_outlook_scenarios(companies: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach transparent operating scenarios; these are not analyst consensus or price targets."""
    peer_growth = {
        subsector: median_value(
            company.get("revenue_growth_pct")
            for company in companies
            if company.get("subsector") == subsector
        )
        for subsector in {str(company.get("subsector")) for company in companies}
    }

    modeled = 0
    labels: dict[str, int] = {}
    base_growth_values: list[float] = []
    positive_year3_fcf = 0

    for company in companies:
        history = [row for row in company.get("history", []) if isinstance(row, dict)]
        revenue_rows = [row for row in history if safe_float(row.get("revenue")) not in (None, 0)]
        latest_revenue = safe_float(company.get("latest_reported_revenue"))
        latest_year_text = str(company.get("latest_fiscal_year") or "")
        try:
            latest_year = int(latest_year_text)
        except ValueError:
            latest_year = int(revenue_rows[-1].get("year")) if revenue_rows else datetime.now(timezone.utc).year

        three_year_cagr = None
        five_year_cagr = None
        if len(revenue_rows) >= 4:
            start = revenue_rows[-4]
            three_year_cagr = annualized_growth(start.get("revenue"), revenue_rows[-1].get("revenue"), 3)
        if len(revenue_rows) >= 6:
            start = revenue_rows[-6]
            five_year_cagr = annualized_growth(start.get("revenue"), revenue_rows[-1].get("revenue"), 5)

        latest_growth = safe_float(company.get("revenue_growth_pct"))
        peer_median_growth = safe_float(peer_growth.get(str(company.get("subsector"))))
        base_growth = weighted_available([
            (latest_growth, 0.40),
            (three_year_cagr, 0.35),
            (peer_median_growth, 0.25),
        ])

        growth_rates = historical_revenue_growth_rates(history)
        growth_volatility = statistics.pstdev(growth_rates[-5:]) if len(growth_rates) >= 2 else 6.0
        growth_spread = clamp(growth_volatility * 0.65, 4.0, 12.0)

        fcf_margins = historical_fcf_margins(history)
        latest_fcf_margin = safe_float(company.get("fcf_margin_pct"))
        recent_fcf_margin = median_value(fcf_margins[-3:])
        base_fcf_margin = weighted_available([
            (latest_fcf_margin, 0.60),
            (recent_fcf_margin, 0.40),
        ])
        margin_volatility = statistics.pstdev(fcf_margins[-5:]) if len(fcf_margins) >= 2 else 4.0
        margin_spread = clamp(margin_volatility * 0.50, 3.0, 8.0)

        coverage = safe_float(company.get("data_coverage_pct")) or 0.0
        revenue_points = len(revenue_rows)
        fcf_points = len(fcf_margins)
        confidence = (
            "High" if revenue_points >= 6 and fcf_points >= 4 and coverage >= 80
            else "Moderate" if revenue_points >= 4 and coverage >= 60
            else "Limited"
        )

        if latest_revenue is None or latest_revenue <= 0 or base_growth is None:
            company["outlook"] = {
                "status": "Insufficient standardized history for operating scenarios",
                "label": "Insufficient data",
                "confidence": confidence,
                "historical_revenue_cagr_3y_pct": three_year_cagr,
                "historical_revenue_cagr_5y_pct": five_year_cagr,
                "peer_median_growth_pct": peer_median_growth,
                "scenarios": [],
            }
            labels["Insufficient data"] = labels.get("Insufficient data", 0) + 1
            continue

        base_growth = clamp(base_growth, -20.0, 40.0)
        scenario_inputs = [
            ("Conservative", clamp(base_growth - growth_spread, -30.0, 35.0),
             clamp(base_fcf_margin - margin_spread, -40.0, 50.0) if base_fcf_margin is not None else None),
            ("Base", base_growth,
             clamp(base_fcf_margin, -40.0, 50.0) if base_fcf_margin is not None else None),
            ("Optimistic", clamp(base_growth + growth_spread, -15.0, 55.0),
             clamp(base_fcf_margin + margin_spread, -40.0, 55.0) if base_fcf_margin is not None else None),
        ]
        scenarios: list[dict[str, Any]] = []
        for name, growth_assumption, margin_assumption in scenario_inputs:
            projections = project_operating_scenario(
                latest_revenue, latest_year, growth_assumption, margin_assumption
            )
            scenarios.append({
                "name": name,
                "annual_revenue_growth_pct": round(growth_assumption, 2),
                "fcf_margin_pct": round(margin_assumption, 2) if margin_assumption is not None else None,
                "projections": projections,
            })

        likelihood = safe_float(company.get("outperformance_likelihood_12m_pct"))
        score = safe_float(company.get("score"))
        if (likelihood is not None and likelihood >= 65 and (score or 0) >= 72 and base_growth > 0):
            label = "Favorable research outlook"
        elif ((likelihood is not None and likelihood < 45) or base_growth < 0 or
              (base_fcf_margin is not None and base_fcf_margin < 0)):
            label = "Cautious research outlook"
        else:
            label = "Balanced research outlook"

        base_case = next(item for item in scenarios if item["name"] == "Base")
        year3 = base_case["projections"][-1]
        company["outlook"] = {
            "status": "Three-year model-generated operating scenarios",
            "label": label,
            "confidence": confidence,
            "latest_reported_year": str(latest_year),
            "latest_reported_revenue": money_round(latest_revenue),
            "historical_revenue_cagr_3y_pct": three_year_cagr,
            "historical_revenue_cagr_5y_pct": five_year_cagr,
            "peer_median_growth_pct": peer_median_growth,
            "growth_spread_pct_points": round(growth_spread, 2),
            "base_fcf_margin_pct": round(base_fcf_margin, 2) if base_fcf_margin is not None else None,
            "margin_spread_pct_points": round(margin_spread, 2),
            "base_year3_revenue": year3.get("revenue"),
            "base_year3_free_cash_flow": year3.get("free_cash_flow"),
            "scenarios": scenarios,
            "summary": (
                f"The base operating scenario uses {base_growth:.1f}% annual revenue growth"
                + (f" and a {base_fcf_margin:.1f}% free-cash-flow margin" if base_fcf_margin is not None else "")
                + f" for three years. The scenario confidence is {confidence.lower()}."
            ),
        }
        modeled += 1
        labels[label] = labels.get(label, 0) + 1
        base_growth_values.append(base_growth)
        if safe_float(year3.get("free_cash_flow")) is not None and safe_float(year3.get("free_cash_flow")) > 0:
            positive_year3_fcf += 1

    return {
        "status": "Phase 6 model-generated operating scenarios",
        "companies_modeled": modeled,
        "company_count": len(companies),
        "favorable_count": labels.get("Favorable research outlook", 0),
        "balanced_count": labels.get("Balanced research outlook", 0),
        "cautious_count": labels.get("Cautious research outlook", 0),
        "insufficient_count": labels.get("Insufficient data", 0),
        "median_base_revenue_growth_pct": median_value(base_growth_values),
        "positive_base_year3_fcf_count": positive_year3_fcf,
        "method": (
            "Base revenue growth blends latest reported growth (40%), three-year reported CAGR (35%), "
            "and current subsector median growth (25%), using only available inputs. Conservative and "
            "optimistic cases widen the base by recent historical variability. Free-cash-flow margins "
            "blend the latest reported margin with the recent historical median."
        ),
        "limitations": [
            "These are Stock Digest model-generated operating scenarios, not company guidance, analyst consensus estimates, or price targets.",
            "The same annual growth and margin assumptions are carried through each three-year scenario for transparency; actual results will vary.",
            "The prototype subsector peer groups are small and may not represent the full competitive market.",
            "Scenario labels combine current quantitative conditions and the Phase 5 research likelihood; they are not buy, sell, or hold recommendations.",
            "Unexpected acquisitions, divestitures, accounting changes, regulation, competition, and economic conditions are not forecast by this model.",
        ],
    }

def build_market_summary(companies: list[dict[str, Any]], index_rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [c for c in companies if c.get("latest_price") is not None]
    above50 = sum(bool(c.get("above_50_day")) for c in valid)
    above200 = sum(bool(c.get("above_200_day")) for c in valid)
    positive_fcf = sum((safe_float(c.get("latest_free_cash_flow")) or 0) > 0 for c in companies if c.get("latest_free_cash_flow") is not None)
    fcf_count = sum(c.get("latest_free_cash_flow") is not None for c in companies)
    total_capex = sum(safe_float(c.get("latest_capex")) or 0 for c in companies)

    return_30d = None
    return_1y = None
    if index_rows:
        values = [(datetime.fromisoformat(row["date"]), safe_float(row.get("ai_index"))) for row in index_rows]
        values = [(d, v) for d, v in values if v is not None]
        if values:
            latest_date, latest_value = values[-1]
            for days, field in [(30, "30d"), (365, "1y")]:
                target = latest_date - __import__("datetime").timedelta(days=days)
                prior = [item for item in values if item[0] <= target]
                prior_value = prior[-1][1] if prior else values[0][1]
                result = pct_change(latest_value, prior_value)
                if field == "30d":
                    return_30d = result
                else:
                    return_1y = result

    breadth_ratio = above50 / len(valid) if valid else 0.5
    direction_points = 0
    if return_30d is not None:
        direction_points += 2 if return_30d >= 5 else 1 if return_30d > 0 else -2 if return_30d <= -5 else -1
    if return_1y is not None:
        direction_points += 2 if return_1y >= 15 else 1 if return_1y > 0 else -2 if return_1y <= -15 else -1
    direction_points += 2 if breadth_ratio >= 0.7 else 1 if breadth_ratio >= 0.55 else -2 if breadth_ratio <= 0.3 else -1 if breadth_ratio < 0.45 else 0
    direction = (
        "Strong Uptrend" if direction_points >= 5 else
        "Moderate Uptrend" if direction_points >= 2 else
        "Strong Downtrend" if direction_points <= -5 else
        "Moderate Downtrend" if direction_points <= -2 else
        "Neutral / Mixed"
    )

    return {
        "direction": direction,
        "return_30d_pct": return_30d,
        "return_1y_pct": return_1y,
        "above_50_day": above50,
        "above_200_day": above200,
        "priced_company_count": len(valid),
        "positive_fcf_count": positive_fcf,
        "fcf_company_count": fcf_count,
        "aggregate_latest_capex": round(total_capex, 2),
    }



def historical_metric_cagr(history: list[dict[str, Any]], metric: str, minimum_years: int = 3) -> float | None:
    """Calculate CAGR from the latest positive value to a point at least minimum_years earlier."""
    rows: list[tuple[int, float]] = []
    for row in history:
        value = safe_float(row.get(metric))
        try:
            year = int(str(row.get("year")))
        except (TypeError, ValueError):
            continue
        if value is not None and value > 0:
            rows.append((year, value))
    rows.sort()
    if len(rows) < 2:
        return None
    end_year, end_value = rows[-1]
    candidates = [(year, value) for year, value in rows[:-1] if end_year - year >= minimum_years]
    if not candidates:
        return None
    start_year, start_value = candidates[-1]
    return annualized_growth(start_value, end_value, end_year - start_year)


def weighted_percentile_score(parts: list[tuple[float | None, float]]) -> float | None:
    available = [(value, weight) for value, weight in parts if value is not None]
    if not available:
        return None
    weight_total = sum(weight for _, weight in available)
    return round(sum(value * weight for value, weight in available) / weight_total, 1)


def add_capital_efficiency_research(companies: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach a peer-relative capital-efficiency and financial-durability research profile."""
    for company in companies:
        revenue = safe_float(company.get("latest_reported_revenue"))
        capex = safe_float(company.get("latest_capex"))
        rnd = safe_float(company.get("latest_rnd"))
        ocf = safe_float(company.get("latest_operating_cash_flow"))
        cash = safe_float(company.get("cash_and_short_investments"))
        debt = safe_float(company.get("total_debt"))

        investment_values = [value for value in (capex, rnd) if value is not None]
        combined_investment = sum(investment_values) if investment_values else None
        innovation_intensity = (
            combined_investment / revenue * 100.0
            if combined_investment is not None and revenue not in (None, 0) else None
        )
        ocf_capex_coverage = ocf / capex if ocf is not None and capex not in (None, 0) else None
        revenue_per_investment = (
            revenue / combined_investment
            if revenue is not None and combined_investment not in (None, 0) else None
        )
        net_cash = cash - debt if cash is not None and debt is not None else None
        net_cash_to_revenue = (
            net_cash / revenue * 100.0
            if net_cash is not None and revenue not in (None, 0) else None
        )
        growth = safe_float(company.get("revenue_growth_pct"))
        growth_per_investment = (
            growth / innovation_intensity
            if growth is not None and innovation_intensity not in (None, 0) else None
        )
        history = [row for row in company.get("history", []) if isinstance(row, dict)]

        company["capital_efficiency"] = {
            "status": "Awaiting peer-relative scoring",
            "profile": "Insufficient data",
            "score": None,
            "combined_capex_and_rnd": money_round(combined_investment),
            "innovation_intensity_pct": round(innovation_intensity, 2) if innovation_intensity is not None else None,
            "operating_cash_flow_to_capex_x": round(ocf_capex_coverage, 2) if ocf_capex_coverage is not None else None,
            "revenue_per_investment_dollar_x": round(revenue_per_investment, 2) if revenue_per_investment is not None else None,
            "growth_per_investment_point_x": round(growth_per_investment, 3) if growth_per_investment is not None else None,
            "net_cash": money_round(net_cash),
            "net_cash_to_revenue_pct": round(net_cash_to_revenue, 2) if net_cash_to_revenue is not None else None,
            "capex_cagr_3y_pct": historical_metric_cagr(history, "capex", 3),
            "rnd_cagr_3y_pct": historical_metric_cagr(history, "rnd", 3),
            "peer_percentiles": {},
        }

    subsectors = sorted({str(company.get("subsector")) for company in companies})
    for subsector in subsectors:
        peers = [company for company in companies if str(company.get("subsector")) == subsector]
        metric_map = {
            "revenue_growth": ("revenue_growth_pct", True),
            "fcf_margin": ("fcf_margin_pct", True),
            "ocf_capex_coverage": ("operating_cash_flow_to_capex_x", True),
            "net_cash_to_revenue": ("net_cash_to_revenue_pct", True),
            "revenue_per_investment": ("revenue_per_investment_dollar_x", True),
        }
        for company in peers:
            capital = company.get("capital_efficiency", {})
            percentiles: dict[str, float | None] = {}
            for label, (field, higher_is_better) in metric_map.items():
                if field in capital:
                    value = capital.get(field)
                    values = [peer.get("capital_efficiency", {}).get(field) for peer in peers]
                else:
                    value = company.get(field)
                    values = [peer.get(field) for peer in peers]
                percentiles[label] = percentile_rank(value, values, higher_is_better=higher_is_better)
            capital["peer_percentiles"] = percentiles
            capital["score"] = weighted_percentile_score([
                (percentiles.get("revenue_growth"), 25),
                (percentiles.get("fcf_margin"), 25),
                (percentiles.get("ocf_capex_coverage"), 20),
                (percentiles.get("net_cash_to_revenue"), 15),
                (percentiles.get("revenue_per_investment"), 15),
            ])

            fcf = safe_float(company.get("latest_free_cash_flow"))
            fcf_margin = safe_float(company.get("fcf_margin_pct"))
            intensity = safe_float(capital.get("innovation_intensity_pct"))
            coverage = safe_float(capital.get("operating_cash_flow_to_capex_x"))
            net_cash = safe_float(capital.get("net_cash"))
            revenue_growth = safe_float(company.get("revenue_growth_pct"))
            peer_intensity = median_value(
                peer.get("capital_efficiency", {}).get("innovation_intensity_pct") for peer in peers
            )

            if fcf is not None and fcf < 0:
                profile = "Cash-consuming expansion"
            elif coverage is not None and coverage >= 2.0 and fcf_margin is not None and fcf_margin >= 10:
                profile = "Self-funded reinvestment"
            elif intensity is not None and intensity < 10 and revenue_growth is not None and revenue_growth > 10:
                profile = "Capital-light growth"
            elif (intensity is not None and peer_intensity is not None and intensity >= peer_intensity * 1.25
                  and fcf is not None and fcf >= 0):
                profile = "Heavy but self-funded investment"
            elif net_cash is not None and net_cash < 0 and coverage is not None and coverage < 1:
                profile = "Balance-sheet-dependent investment"
            else:
                profile = "Balanced capital deployment"

            score = safe_float(capital.get("score"))
            if score is None:
                status = "Insufficient comparable metrics"
            else:
                status = "Peer-relative capital-efficiency research score"
            capital["profile"] = profile
            capital["status"] = status
            capital["summary"] = (
                f"{profile}. Combined reported CapEx and R&D equals "
                + (f"{intensity:.1f}% of revenue" if intensity is not None else "an unavailable share of revenue")
                + (f", while operating cash flow covers CapEx {coverage:.2f} times" if coverage is not None else "")
                + "."
            )

    scored = [company for company in companies if safe_float(company.get("capital_efficiency", {}).get("score")) is not None]
    ranked = sorted(scored, key=lambda item: safe_float(item.get("capital_efficiency", {}).get("score")) or -1, reverse=True)
    for rank, company in enumerate(ranked, start=1):
        company["capital_efficiency"]["overall_rank"] = rank
    for subsector in subsectors:
        peers = sorted(
            [company for company in scored if str(company.get("subsector")) == subsector],
            key=lambda item: safe_float(item.get("capital_efficiency", {}).get("score")) or -1,
            reverse=True,
        )
        for rank, company in enumerate(peers, start=1):
            company["capital_efficiency"]["subsector_rank"] = rank
            company["capital_efficiency"]["subsector_count"] = len(peers)

    profiles: dict[str, int] = {}
    for company in companies:
        profile = str(company.get("capital_efficiency", {}).get("profile") or "Insufficient data")
        profiles[profile] = profiles.get(profile, 0) + 1

    return {
        "status": "Phase 7 capital-efficiency and financial-durability research",
        "companies_scored": len(scored),
        "company_count": len(companies),
        "median_score": median_value(company.get("capital_efficiency", {}).get("score") for company in scored),
        "self_funded_count": profiles.get("Self-funded reinvestment", 0) + profiles.get("Heavy but self-funded investment", 0),
        "cash_consuming_count": profiles.get("Cash-consuming expansion", 0),
        "positive_net_cash_count": sum(
            (safe_float(company.get("capital_efficiency", {}).get("net_cash")) or 0) > 0
            for company in companies if company.get("capital_efficiency", {}).get("net_cash") is not None
        ),
        "median_innovation_intensity_pct": median_value(
            company.get("capital_efficiency", {}).get("innovation_intensity_pct") for company in companies
        ),
        "profiles": profiles,
        "method": (
            "The peer-relative score combines revenue-growth percentile (25%), free-cash-flow-margin percentile (25%), "
            "operating-cash-flow-to-CapEx coverage percentile (20%), net-cash-to-revenue percentile (15%), and revenue "
            "per combined reported CapEx-plus-R&D dollar percentile (15%). Missing components are excluded and weights are renormalized."
        ),
        "limitations": [
            "Combined CapEx plus R&D is a Stock Digest analytical total, not a GAAP subtotal and not a measure of AI-only investment.",
            "A high score does not prove that past spending caused growth or that future spending will be productive.",
            "Peer percentiles use only the small current prototype subsector universe and can change materially as companies are added.",
            "R&D and CapEx reporting practices differ among issuers, and some companies do not separately report every field.",
            "This research layer is not a valuation opinion, success probability, price target, or investment recommendation.",
        ],
    }



def add_relative_valuation_research(companies: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach transparent peer-relative valuation and growth-quality research metrics.

    This layer deliberately remains separate from the original company score so historical weekly
    snapshots and backtests are not silently rewritten when a new research component is introduced.
    """
    for company in companies:
        market_cap = safe_float(company.get("market_cap"))
        revenue = safe_float(company.get("latest_reported_revenue"))
        fcf = safe_float(company.get("latest_free_cash_flow"))
        net_income = safe_float(company.get("latest_net_income"))
        cash = safe_float(company.get("cash_and_short_investments"))
        debt = safe_float(company.get("total_debt"))
        growth = safe_float(company.get("revenue_growth_pct"))
        fcf_margin = safe_float(company.get("fcf_margin_pct"))

        enterprise_value = None
        if market_cap is not None and cash is not None and debt is not None:
            enterprise_value = market_cap + debt - cash

        price_to_sales = (
            market_cap / revenue
            if market_cap is not None and market_cap > 0 and revenue is not None and revenue > 0 else None
        )
        enterprise_value_to_sales = (
            enterprise_value / revenue
            if enterprise_value is not None and enterprise_value > 0 and revenue is not None and revenue > 0 else None
        )
        price_to_fcf = (
            market_cap / fcf
            if market_cap is not None and market_cap > 0 and fcf is not None and fcf > 0 else None
        )
        price_to_earnings = (
            market_cap / net_income
            if market_cap is not None and market_cap > 0 and net_income is not None and net_income > 0 else None
        )
        fcf_yield = (
            fcf / market_cap * 100.0
            if fcf is not None and market_cap is not None and market_cap > 0 else None
        )
        earnings_yield = (
            net_income / market_cap * 100.0
            if net_income is not None and market_cap is not None and market_cap > 0 else None
        )
        growth_adjusted_price_to_sales = (
            price_to_sales / growth
            if price_to_sales is not None and growth is not None and growth > 0 else None
        )

        company["relative_valuation"] = {
            "status": "Awaiting peer-relative scoring",
            "profile": "Insufficient data",
            "score": None,
            "enterprise_value": money_round(enterprise_value),
            "price_to_sales_x": round(price_to_sales, 2) if price_to_sales is not None else None,
            "enterprise_value_to_sales_x": round(enterprise_value_to_sales, 2) if enterprise_value_to_sales is not None else None,
            "price_to_free_cash_flow_x": round(price_to_fcf, 2) if price_to_fcf is not None else None,
            "price_to_earnings_x": round(price_to_earnings, 2) if price_to_earnings is not None else None,
            "free_cash_flow_yield_pct": round(fcf_yield, 2) if fcf_yield is not None else None,
            "earnings_yield_pct": round(earnings_yield, 2) if earnings_yield is not None else None,
            "growth_adjusted_price_to_sales": (
                round(growth_adjusted_price_to_sales, 3)
                if growth_adjusted_price_to_sales is not None else None
            ),
            "peer_percentiles": {},
            "peer_medians": {},
            "available_component_count": 0,
        }

    subsectors = sorted({str(company.get("subsector")) for company in companies})
    for subsector in subsectors:
        peers = [company for company in companies if str(company.get("subsector")) == subsector]
        peer_ps_median = median_value(
            peer.get("relative_valuation", {}).get("price_to_sales_x") for peer in peers
        )
        peer_ev_sales_median = median_value(
            peer.get("relative_valuation", {}).get("enterprise_value_to_sales_x") for peer in peers
        )
        peer_growth_median = median_value(peer.get("revenue_growth_pct") for peer in peers)
        peer_fcf_margin_median = median_value(peer.get("fcf_margin_pct") for peer in peers)

        for company in peers:
            valuation = company.get("relative_valuation", {})
            percentiles = {
                "price_to_sales": percentile_rank(
                    valuation.get("price_to_sales_x"),
                    [peer.get("relative_valuation", {}).get("price_to_sales_x") for peer in peers],
                    higher_is_better=False,
                ),
                "enterprise_value_to_sales": percentile_rank(
                    valuation.get("enterprise_value_to_sales_x"),
                    [peer.get("relative_valuation", {}).get("enterprise_value_to_sales_x") for peer in peers],
                    higher_is_better=False,
                ),
                "free_cash_flow_yield": percentile_rank(
                    valuation.get("free_cash_flow_yield_pct"),
                    [peer.get("relative_valuation", {}).get("free_cash_flow_yield_pct") for peer in peers],
                    higher_is_better=True,
                ),
                "earnings_yield": percentile_rank(
                    valuation.get("earnings_yield_pct"),
                    [peer.get("relative_valuation", {}).get("earnings_yield_pct") for peer in peers],
                    higher_is_better=True,
                ),
                "growth_adjusted_price_to_sales": percentile_rank(
                    valuation.get("growth_adjusted_price_to_sales"),
                    [peer.get("relative_valuation", {}).get("growth_adjusted_price_to_sales") for peer in peers],
                    higher_is_better=False,
                ),
                "revenue_growth": percentile_rank(
                    company.get("revenue_growth_pct"),
                    [peer.get("revenue_growth_pct") for peer in peers],
                    higher_is_better=True,
                ),
                "fcf_margin": percentile_rank(
                    company.get("fcf_margin_pct"),
                    [peer.get("fcf_margin_pct") for peer in peers],
                    higher_is_better=True,
                ),
            }
            valuation["peer_percentiles"] = percentiles
            valuation["peer_medians"] = {
                "price_to_sales_x": peer_ps_median,
                "enterprise_value_to_sales_x": peer_ev_sales_median,
                "revenue_growth_pct": peer_growth_median,
                "fcf_margin_pct": peer_fcf_margin_median,
            }
            components = [
                (percentiles.get("price_to_sales"), 20),
                (percentiles.get("enterprise_value_to_sales"), 15),
                (percentiles.get("free_cash_flow_yield"), 20),
                (percentiles.get("earnings_yield"), 10),
                (percentiles.get("growth_adjusted_price_to_sales"), 15),
                (percentiles.get("revenue_growth"), 10),
                (percentiles.get("fcf_margin"), 10),
            ]
            valuation["available_component_count"] = sum(value is not None for value, _ in components)
            valuation["score"] = weighted_percentile_score(components)

            ps = safe_float(valuation.get("price_to_sales_x"))
            fcf_value = safe_float(company.get("latest_free_cash_flow"))
            fcf_yield_value = safe_float(valuation.get("free_cash_flow_yield_pct"))
            growth_value = safe_float(company.get("revenue_growth_pct"))
            score = safe_float(valuation.get("score"))

            if score is None:
                profile = "Insufficient comparable data"
                status = "Insufficient comparable metrics"
            elif fcf_value is not None and fcf_value <= 0:
                profile = "Speculative / negative cash flow"
                status = "Peer-relative valuation research score"
            elif (
                ps is not None and peer_ps_median is not None and ps > peer_ps_median * 1.35
                and growth_value is not None and peer_growth_median is not None
                and growth_value > peer_growth_median * 1.20
            ):
                profile = "Growth-supported premium"
                status = "Peer-relative valuation research score"
            elif ps is not None and peer_ps_median is not None and ps > peer_ps_median * 1.50:
                profile = "Demanding premium valuation"
                status = "Peer-relative valuation research score"
            elif (
                ps is not None and peer_ps_median is not None and ps <= peer_ps_median
                and fcf_yield_value is not None and fcf_yield_value >= 3.0
            ):
                profile = "Lower-multiple cash generator"
                status = "Peer-relative valuation research score"
            elif score >= 65:
                profile = "Relatively favorable valuation mix"
                status = "Peer-relative valuation research score"
            elif score < 40:
                profile = "Relatively demanding valuation mix"
                status = "Peer-relative valuation research score"
            else:
                profile = "Balanced relative valuation"
                status = "Peer-relative valuation research score"

            valuation["profile"] = profile
            valuation["status"] = status
            valuation["summary"] = (
                f"{profile}. Market capitalization equals "
                + (f"{ps:.2f} times latest reported revenue" if ps is not None else "an unavailable multiple of revenue")
                + (f", and standardized free-cash-flow yield is {fcf_yield_value:.2f}%" if fcf_yield_value is not None else "")
                + "."
            )
            company["relative_valuation_score"] = valuation.get("score")

    scored = [
        company for company in companies
        if safe_float(company.get("relative_valuation", {}).get("score")) is not None
    ]
    ranked = sorted(
        scored,
        key=lambda item: safe_float(item.get("relative_valuation", {}).get("score")) or -1,
        reverse=True,
    )
    for rank, company in enumerate(ranked, start=1):
        company["relative_valuation"]["overall_rank"] = rank
    for subsector in subsectors:
        peer_ranked = sorted(
            [company for company in scored if str(company.get("subsector")) == subsector],
            key=lambda item: safe_float(item.get("relative_valuation", {}).get("score")) or -1,
            reverse=True,
        )
        for rank, company in enumerate(peer_ranked, start=1):
            company["relative_valuation"]["subsector_rank"] = rank
            company["relative_valuation"]["subsector_count"] = len(peer_ranked)

    profiles: dict[str, int] = {}
    for company in companies:
        profile = str(company.get("relative_valuation", {}).get("profile") or "Insufficient data")
        profiles[profile] = profiles.get(profile, 0) + 1

    return {
        "status": "Phase 8 relative-valuation and growth-quality research",
        "companies_scored": len(scored),
        "company_count": len(companies),
        "median_score": median_value(
            company.get("relative_valuation", {}).get("score") for company in scored
        ),
        "median_price_to_sales_x": median_value(
            company.get("relative_valuation", {}).get("price_to_sales_x") for company in companies
        ),
        "median_enterprise_value_to_sales_x": median_value(
            company.get("relative_valuation", {}).get("enterprise_value_to_sales_x") for company in companies
        ),
        "positive_fcf_yield_count": sum(
            (safe_float(company.get("relative_valuation", {}).get("free_cash_flow_yield_pct")) or 0) > 0
            for company in companies
            if company.get("relative_valuation", {}).get("free_cash_flow_yield_pct") is not None
        ),
        "profiles": profiles,
        "method": (
            "The Phase 8 peer-relative score combines lower price-to-sales percentile (20%), lower enterprise-value-to-sales "
            "percentile (15%), higher standardized free-cash-flow-yield percentile (20%), higher earnings-yield percentile "
            "(10%), lower growth-adjusted price-to-sales percentile (15%), revenue-growth percentile (10%), and free-cash-flow-margin "
            "percentile (10%). Missing components are excluded and the remaining weights are renormalized."
        ),
        "limitations": [
            "This is relative valuation research, not an intrinsic-value estimate, fair-value opinion, price target, or investment recommendation.",
            "Market capitalization and prices come from the prototype market-data source and require licensing review before commercial redistribution.",
            "Latest annual SEC financial facts can become stale between filings and may not match trailing-twelve-month market conventions.",
            "Negative earnings or free cash flow make some conventional multiples unavailable; the model does not replace them with artificial values.",
            "Peer percentiles use only the small current prototype subsector universe and can change materially as companies are added.",
            "Phase 8 does not alter the original company score or prior weekly snapshots, preserving comparability of the existing track record.",
        ],
    }


SEC_8K_EVENT_LABELS = {
    "1.01": "Material agreement",
    "1.02": "Termination of agreement",
    "1.03": "Bankruptcy or receivership",
    "1.05": "Material cybersecurity incident",
    "2.01": "Acquisition or disposition",
    "2.02": "Earnings / financial results",
    "2.03": "Debt or financing obligation",
    "2.04": "Triggering event affecting an obligation",
    "2.05": "Exit or disposal activity",
    "2.06": "Material impairment",
    "3.01": "Listing or compliance notice",
    "3.02": "Unregistered securities sale",
    "3.03": "Security-holder rights change",
    "4.01": "Auditor change or disagreement",
    "4.02": "Non-reliance on prior financial statements",
    "5.01": "Change in control",
    "5.02": "Leadership or board change",
    "5.03": "Charter or bylaw amendment",
    "5.07": "Shareholder vote results",
    "7.01": "Regulation FD disclosure",
    "8.01": "Other material event",
    "9.01": "Financial statements or exhibits",
}


def classify_filing_event(form: str, item_text: str, description: str = "") -> dict[str, Any]:
    """Classify a filing using only the SEC form and disclosed 8-K item codes."""
    form = str(form or "")
    codes = []
    for token in str(item_text or "").replace(";", ",").split(","):
        cleaned = token.strip()
        if cleaned and cleaned not in codes:
            codes.append(cleaned)
    labels = [SEC_8K_EVENT_LABELS[code] for code in codes if code in SEC_8K_EVENT_LABELS]
    if form in {"10-Q"}:
        category = "Quarterly financial report"
    elif form in {"10-K"}:
        category = "Annual financial report"
    elif form in {"20-F"}:
        category = "Foreign issuer annual report"
    elif form in {"6-K"}:
        category = "Foreign issuer current report"
    elif labels:
        category = " / ".join(labels[:2])
    elif form == "8-K":
        category = "Current material report"
    else:
        category = description.strip() or "SEC filing"
    material_codes = [code for code in codes if code not in {"9.01"}]
    return {
        "category": category,
        "item_codes": codes,
        "material_item_count": len(material_codes),
        "is_periodic_report": form in {"10-Q", "10-K", "20-F"},
    }


def filing_price_reaction(series: Any, filing_date: str) -> dict[str, float | None]:
    """Measure closes after a filing versus the prior trading close.

    The exact filing time is not available here, so the first-close measure can include a
    filing submitted after that day's close. This limitation is disclosed on the webpage.
    """
    try:
        target = datetime.fromisoformat(str(filing_date)).date()
        clean = series.dropna()
        dates = [stamp.date() for stamp in clean.index]
        before = [index for index, date in enumerate(dates) if date < target]
        after = [index for index, date in enumerate(dates) if date >= target]
        if not before or not after:
            return {"reaction_1d_pct": None, "reaction_5d_pct": None}
        base = safe_float(clean.iloc[before[-1]])
        first = safe_float(clean.iloc[after[0]])
        fifth = safe_float(clean.iloc[after[4]]) if len(after) >= 5 else None
        return {
            "reaction_1d_pct": pct_change(first, base),
            "reaction_5d_pct": pct_change(fifth, base),
        }
    except Exception:
        return {"reaction_1d_pct": None, "reaction_5d_pct": None}


def add_filing_event_research(
    companies: list[dict[str, Any]], price_history: dict[str, Any]
) -> dict[str, Any]:
    """Add a deterministic SEC filing activity and observed market-reaction layer."""
    now = datetime.now(timezone.utc)
    all_categories: dict[str, int] = {}
    total_events = 0
    total_reactions = 0

    for company in companies:
        ticker = str(company.get("ticker") or "")
        series = price_history.get(ticker)
        events = []
        for filing in company.get("latest_filings", []) or []:
            classification = classify_filing_event(
                str(filing.get("form") or ""),
                str(filing.get("items") or ""),
                str(filing.get("description") or ""),
            )
            reaction = (
                filing_price_reaction(series, str(filing.get("date") or ""))
                if series is not None else {"reaction_1d_pct": None, "reaction_5d_pct": None}
            )
            event = {
                **filing,
                **classification,
                **reaction,
            }
            events.append(event)
            all_categories[classification["category"]] = all_categories.get(classification["category"], 0) + 1

        dated_events = []
        for event in events:
            try:
                date = datetime.fromisoformat(str(event.get("date"))).replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
            dated_events.append((date, event))
        dated_events.sort(key=lambda pair: pair[0], reverse=True)
        events = [event for _, event in dated_events]
        total_events += len(events)

        cutoff_90 = now - timedelta(days=90)
        cutoff_30 = now - timedelta(days=30)
        events_90d = [event for date, event in dated_events if date >= cutoff_90]
        material_30d = [
            event for date, event in dated_events
            if date >= cutoff_30 and (event.get("material_item_count") or 0) > 0
        ]
        one_day = [safe_float(event.get("reaction_1d_pct")) for event in events]
        five_day = [safe_float(event.get("reaction_5d_pct")) for event in events]
        one_day = [value for value in one_day if value is not None]
        five_day = [value for value in five_day if value is not None]
        total_reactions += len(five_day)
        average_1d = round(statistics.fmean(one_day), 2) if one_day else None
        average_5d = round(statistics.fmean(five_day), 2) if five_day else None
        positive_5d = sum(value > 0 for value in five_day)
        negative_5d = sum(value < 0 for value in five_day)
        consistency = round(positive_5d / len(five_day) * 100.0, 1) if five_day else None

        components = []
        if average_5d is not None:
            components.append((clamp(50.0 + average_5d * 4.0), 70))
        if consistency is not None:
            components.append((consistency, 30))
        reaction_score = weighted_percentile_score(components)

        if len(five_day) < 2:
            profile = "Limited reaction history"
        elif average_5d is not None and average_5d >= 2.0 and consistency is not None and consistency >= 60:
            profile = "Positive recent reaction pattern"
        elif average_5d is not None and average_5d <= -2.0 and consistency is not None and consistency <= 40:
            profile = "Negative recent reaction pattern"
        else:
            profile = "Mixed recent reaction pattern"

        if len(material_30d) >= 2 or (average_5d is not None and abs(average_5d) >= 5.0):
            attention = "High"
        elif material_30d or events_90d:
            attention = "Moderate"
        else:
            attention = "Routine"

        latest = events[0] if events else {}
        latest_date = latest.get("date")
        days_since_latest = None
        if latest_date:
            try:
                days_since_latest = (now.date() - datetime.fromisoformat(str(latest_date)).date()).days
            except ValueError:
                pass

        monitor = {
            "status": "Observed SEC filing activity and price-reaction research",
            "profile": profile,
            "attention_level": attention,
            "reaction_score": reaction_score,
            "latest_filing_date": latest_date,
            "days_since_latest_filing": days_since_latest,
            "latest_event_category": latest.get("category"),
            "filings_90d": len(events_90d),
            "material_events_30d": len(material_30d),
            "events_reviewed": len(events),
            "events_with_5d_reaction": len(five_day),
            "average_1d_reaction_pct": average_1d,
            "average_5d_reaction_pct": average_5d,
            "positive_5d_reactions": positive_5d,
            "negative_5d_reactions": negative_5d,
            "positive_5d_share_pct": consistency,
            "events": events,
        }
        monitor["summary"] = (
            f"{profile}. {len(events_90d)} tracked filing(s) were submitted in the last 90 days"
            + (f", with an average five-trading-day reaction of {average_5d:+.2f}%" if average_5d is not None else "")
            + "."
        )
        company["filing_monitor"] = monitor
        company["filing_reaction_score"] = reaction_score

    scored = [
        company for company in companies
        if safe_float(company.get("filing_monitor", {}).get("reaction_score")) is not None
    ]
    scored.sort(
        key=lambda company: safe_float(company.get("filing_monitor", {}).get("reaction_score")) or -1,
        reverse=True,
    )
    for rank, company in enumerate(scored, start=1):
        company["filing_monitor"]["reaction_rank"] = rank

    common_categories = [
        {"category": category, "count": count}
        for category, count in sorted(all_categories.items(), key=lambda item: (-item[1], item[0]))[:8]
    ]
    average_reactions = [
        safe_float(company.get("filing_monitor", {}).get("average_5d_reaction_pct"))
        for company in companies
    ]
    average_reactions = [value for value in average_reactions if value is not None]

    return {
        "status": "Phase 9 SEC filing catalyst and reaction monitor",
        "companies_analyzed": sum(bool(company.get("filing_monitor", {}).get("events")) for company in companies),
        "company_count": len(companies),
        "events_reviewed": total_events,
        "events_with_5d_reaction": total_reactions,
        "median_company_5d_reaction_pct": round(statistics.median(average_reactions), 2) if average_reactions else None,
        "positive_reaction_company_count": sum(
            (safe_float(company.get("filing_monitor", {}).get("average_5d_reaction_pct")) or 0) > 0
            for company in companies
            if company.get("filing_monitor", {}).get("average_5d_reaction_pct") is not None
        ),
        "high_attention_company_count": sum(
            company.get("filing_monitor", {}).get("attention_level") == "High" for company in companies
        ),
        "common_event_categories": common_categories,
        "method": (
            "Phase 9 classifies recent filings from SEC form types and disclosed 8-K item codes, then measures the first "
            "available close and fifth trading close after each filing against the prior trading close. The reaction score "
            "combines average five-day reaction (70%) and the share of positive five-day reactions (30%)."
        ),
        "limitations": [
            "Filing categories are derived from SEC form types and item codes, not from a full natural-language review of every filing.",
            "The SEC submissions feed does not provide exact market-session timing; a filing submitted after the close can make the first-close reaction imprecise.",
            "Observed price reactions can reflect broad market, sector, macroeconomic, or unrelated company news rather than the filing alone.",
            "The reaction score describes recent observed behavior and is not a forecast of the next filing reaction or future return.",
            "Only the most recent tracked filings are included, and reaction samples can be small.",
            "Phase 9 remains separate from the original company score and does not rewrite official weekly snapshots or historical backtests.",
        ],
    }



def unique_research_items(items: Iterable[Any], limit: int = 4) -> list[str]:
    """Return a short, de-duplicated list of non-empty research statements."""
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = " ".join(str(item or "").split()).strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def add_integrated_research_briefs(companies: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine existing research layers into a separate evidence-synthesis brief.

    The Phase 10 score is deliberately separate from the original company score and the
    immutable weekly ranking record. It summarizes available evidence; it is not a new
    investment recommendation, price target, or probability of success.
    """
    outlook_signal_map = {
        "Favorable research outlook": 75.0,
        "Balanced research outlook": 52.0,
        "Cautious research outlook": 30.0,
    }

    for company in companies:
        outlook = company.get("outlook", {}) if isinstance(company.get("outlook"), dict) else {}
        capital = company.get("capital_efficiency", {}) if isinstance(company.get("capital_efficiency"), dict) else {}
        valuation = company.get("relative_valuation", {}) if isinstance(company.get("relative_valuation"), dict) else {}
        filing = company.get("filing_monitor", {}) if isinstance(company.get("filing_monitor"), dict) else {}

        original_score = safe_float(company.get("score"))
        likelihood = safe_float(company.get("outperformance_likelihood_12m_pct"))
        outlook_signal = outlook_signal_map.get(str(outlook.get("label")))
        capital_score = safe_float(capital.get("score"))
        valuation_score = safe_float(valuation.get("score"))
        filing_score = safe_float(filing.get("reaction_score"))

        weighted_parts = [
            (original_score, 30),
            (likelihood, 20),
            (outlook_signal, 15),
            (capital_score, 15),
            (valuation_score, 15),
            (filing_score, 5),
        ]
        integrated_score = weighted_percentile_score(weighted_parts)
        available_component_count = sum(value is not None for value, _ in weighted_parts)
        coverage = safe_float(company.get("data_coverage_pct")) or 0.0

        if available_component_count >= 5 and coverage >= 80 and likelihood is not None:
            confidence = "High"
        elif available_component_count >= 4 and coverage >= 60:
            confidence = "Moderate"
        else:
            confidence = "Limited"

        if integrated_score is None:
            stance = "Insufficient integrated evidence"
        elif integrated_score >= 72:
            stance = "Favorable evidence balance"
        elif integrated_score >= 60:
            stance = "Constructive evidence balance"
        elif integrated_score >= 48:
            stance = "Balanced / mixed evidence"
        else:
            stance = "Cautious evidence balance"

        cagr3 = safe_float(outlook.get("historical_revenue_cagr_3y_pct"))
        latest_growth = safe_float(company.get("revenue_growth_pct"))
        fcf_margin = safe_float(company.get("fcf_margin_pct"))
        return_1y = safe_float(company.get("return_1y_pct"))
        past_parts: list[str] = []
        if cagr3 is not None:
            past_parts.append(f"Reported revenue changed at a {cagr3:+.1f}% annualized rate over the latest three-year span available.")
        elif latest_growth is not None:
            past_parts.append(f"Latest reported annual revenue growth was {latest_growth:+.1f}%.")
        if fcf_margin is not None:
            past_parts.append(f"Latest standardized free-cash-flow margin was {fcf_margin:+.1f}%.")
        if return_1y is not None:
            past_parts.append(f"The observed one-year stock-price return was {return_1y:+.1f}% through the latest market-data date.")
        past_summary = " ".join(past_parts) or "Standardized historical evidence is incomplete."

        present_parts: list[str] = []
        if original_score is not None:
            present_parts.append(
                f"The current original company score is {original_score:.1f}, ranked {company.get('overall_rank') or 'N/A'} overall."
            )
        if capital.get("profile"):
            present_parts.append(f"Capital profile: {capital.get('profile')}.")
        if valuation.get("profile"):
            present_parts.append(f"Relative valuation profile: {valuation.get('profile')}.")
        if filing.get("latest_event_category"):
            present_parts.append(
                f"Latest tracked SEC disclosure category: {filing.get('latest_event_category')} on {filing.get('latest_filing_date') or 'an unavailable date'}."
            )
        present_summary = " ".join(present_parts) or "Current integrated evidence is incomplete."

        future_parts: list[str] = []
        if outlook.get("label"):
            future_parts.append(f"The operating-scenario label is {outlook.get('label').lower()} with {str(outlook.get('confidence') or 'limited').lower()} scenario confidence.")
        base_scenario = next(
            (item for item in outlook.get("scenarios", []) if isinstance(item, dict) and item.get("name") == "Base"),
            {},
        )
        base_growth = safe_float(base_scenario.get("annual_revenue_growth_pct"))
        if base_growth is not None:
            future_parts.append(f"The transparent base scenario assumes {base_growth:.1f}% annual revenue growth for three years.")
        if likelihood is not None:
            future_parts.append(
                f"The separate backtest-based 12-month peer-outperformance research estimate is {likelihood:.1f}%, subject to its displayed sample and validation limits."
            )
        future_summary = " ".join(future_parts) or "No standardized future research scenario is currently available."

        supporting: list[str] = list(company.get("strengths") or [])
        if likelihood is not None and likelihood >= 60:
            supporting.append(f"Backtest-based peer-outperformance research estimate is {likelihood:.1f}%.")
        if capital_score is not None and capital_score >= 65:
            supporting.append(f"Capital-efficiency score is above the current prototype peer midpoint at {capital_score:.1f}.")
        if valuation_score is not None and valuation_score >= 65:
            supporting.append(f"Relative-valuation and growth-quality score is comparatively favorable at {valuation_score:.1f}.")
        if str(outlook.get("label")) == "Favorable research outlook":
            supporting.append("The operating-scenario framework currently produces a favorable research outlook.")
        if safe_float(filing.get("average_5d_reaction_pct")) is not None and safe_float(filing.get("average_5d_reaction_pct")) > 0:
            supporting.append("Recent tracked SEC filings have had a positive average five-trading-day observed reaction.")

        counter: list[str] = list(company.get("risks") or [])
        if likelihood is not None and likelihood < 45:
            counter.append(f"Backtest-based peer-outperformance research estimate is below 45% at {likelihood:.1f}%.")
        if capital_score is not None and capital_score < 40:
            counter.append(f"Capital-efficiency score is relatively weak at {capital_score:.1f}.")
        if valuation_score is not None and valuation_score < 40:
            counter.append(f"Relative-valuation score is demanding at {valuation_score:.1f}.")
        if str(outlook.get("label")) == "Cautious research outlook":
            counter.append("The operating-scenario framework currently produces a cautious research outlook.")
        if safe_float(filing.get("average_5d_reaction_pct")) is not None and safe_float(filing.get("average_5d_reaction_pct")) < 0:
            counter.append("Recent tracked SEC filings have had a negative average five-trading-day observed reaction.")
        if confidence == "Limited":
            counter.append("Integrated confidence is limited because several standardized research inputs are unavailable or thinly validated.")

        watch_items: list[str] = []
        if filing.get("latest_event_category"):
            watch_items.append(
                f"Review the next SEC disclosure after the latest {filing.get('latest_event_category')} filing and compare the subsequent reported facts with the current profile."
            )
        watch_items.append("Compare the next reported revenue-growth and free-cash-flow margins with the current subsector medians.")
        if valuation.get("profile"):
            watch_items.append(f"Monitor whether the current '{valuation.get('profile')}' valuation profile changes as price and reported fundamentals update.")
        if base_growth is not None:
            watch_items.append(f"Test future reported revenue against the Phase 6 base scenario assumption of {base_growth:.1f}% annual growth.")
        if likelihood is not None:
            watch_items.append("Continue tracking the Phase 5 validation sample before treating the likelihood estimate as stable.")

        company["integrated_research"] = {
            "status": "Phase 10 automated evidence synthesis; not investment advice",
            "score": integrated_score,
            "stance": stance,
            "confidence": confidence,
            "available_component_count": available_component_count,
            "data_coverage_pct": round(coverage, 1),
            "component_scores": {
                "original_company_score": original_score,
                "backtest_likelihood": likelihood,
                "operating_outlook_signal": outlook_signal,
                "capital_efficiency": capital_score,
                "relative_valuation": valuation_score,
                "filing_reaction": filing_score,
            },
            "past_summary": past_summary,
            "present_summary": present_summary,
            "future_summary": future_summary,
            "supporting_evidence": unique_research_items(supporting, 5),
            "counter_evidence": unique_research_items(counter, 5),
            "watch_items": unique_research_items(watch_items, 5),
        }
        company["integrated_research_score"] = integrated_score

    scored = [
        company for company in companies
        if safe_float(company.get("integrated_research", {}).get("score")) is not None
    ]
    scored.sort(
        key=lambda company: safe_float(company.get("integrated_research", {}).get("score")) or -1,
        reverse=True,
    )
    for rank, company in enumerate(scored, start=1):
        company["integrated_research"]["overall_rank"] = rank

    for subsector in sorted({str(company.get("subsector")) for company in companies}):
        peers = [company for company in scored if str(company.get("subsector")) == subsector]
        peers.sort(
            key=lambda company: safe_float(company.get("integrated_research", {}).get("score")) or -1,
            reverse=True,
        )
        for rank, company in enumerate(peers, start=1):
            company["integrated_research"]["subsector_rank"] = rank
            company["integrated_research"]["subsector_count"] = len(peers)

    return {
        "status": "Phase 10 integrated evidence and company research briefs",
        "companies_scored": len(scored),
        "company_count": len(companies),
        "median_score": median_value(
            company.get("integrated_research", {}).get("score") for company in scored
        ),
        "favorable_count": sum(
            company.get("integrated_research", {}).get("stance") == "Favorable evidence balance"
            for company in companies
        ),
        "constructive_count": sum(
            company.get("integrated_research", {}).get("stance") == "Constructive evidence balance"
            for company in companies
        ),
        "balanced_count": sum(
            company.get("integrated_research", {}).get("stance") == "Balanced / mixed evidence"
            for company in companies
        ),
        "cautious_count": sum(
            company.get("integrated_research", {}).get("stance") == "Cautious evidence balance"
            for company in companies
        ),
        "high_confidence_count": sum(
            company.get("integrated_research", {}).get("confidence") == "High"
            for company in companies
        ),
        "method": (
            "The separate Phase 10 evidence-balance score combines the original company score (30%), the Phase 5 "
            "backtest-based likelihood estimate (20%), the Phase 6 operating-outlook signal (15%), Phase 7 capital "
            "efficiency (15%), Phase 8 relative valuation (15%), and the Phase 9 observed filing-reaction score (5%). "
            "Missing components are excluded and remaining weights are renormalized."
        ),
        "limitations": [
            "Phase 10 summarizes existing quantitative research layers; it does not independently verify management quality, competitive moat, product quality, or undisclosed risks.",
            "The integrated evidence score is separate from the original company score and does not change official weekly rankings, prior snapshots, or historical backtests.",
            "The filing-reaction component is lightly weighted because observed price reactions do not prove causation and can be noisy.",
            "The likelihood estimate and operating scenarios retain the survivorship, sample-size, overlap, and model limitations displayed in their own sections.",
            "The evidence stance is not a buy, sell, hold, fair-value, price-target, or probability-of-success conclusion.",
            "Automated summaries can omit qualitative information that is not represented in standardized SEC facts and prototype market data.",
        ],
    }



def leader_summary(
    companies: list[dict[str, Any]],
    value_getter,
    higher_is_better: bool = True,
) -> dict[str, Any] | None:
    """Return a compact leader record for a comparable company metric."""
    eligible: list[tuple[float, dict[str, Any]]] = []
    for company in companies:
        value = safe_float(value_getter(company))
        if value is not None:
            eligible.append((value, company))
    if not eligible:
        return None
    value, company = (max(eligible, key=lambda item: item[0]) if higher_is_better else min(eligible, key=lambda item: item[0]))
    return {
        "ticker": company.get("ticker"),
        "name": company.get("name"),
        "value": round(value, 2),
    }


def most_common_research_item(companies: list[dict[str, Any]], field: str) -> str | None:
    """Return the most frequently repeated deterministic strength or risk statement."""
    counts: dict[str, int] = {}
    order: list[str] = []
    for company in companies:
        items = company.get(field) if isinstance(company.get(field), list) else []
        for item in items:
            wording = str(item).strip()
            if not wording:
                continue
            if wording not in counts:
                order.append(wording)
                counts[wording] = 0
            counts[wording] += 1
    if not counts:
        return None
    return max(order, key=lambda wording: (counts[wording], -order.index(wording)))


def add_subsector_landscape(companies: list[dict[str, Any]]) -> dict[str, Any]:
    """Build Phase 12 subsector health and company competitive-position research."""
    subsectors: list[dict[str, Any]] = []
    all_position_scores: list[float] = []

    for subsector in sorted({str(company.get("subsector")) for company in companies if company.get("subsector")}):
        peers = [company for company in companies if str(company.get("subsector")) == subsector]
        priced = [company for company in peers if safe_float(company.get("latest_price")) is not None]
        fcf_reporters = [company for company in peers if safe_float(company.get("latest_free_cash_flow")) is not None]

        median_score = median_value(company.get("score") for company in peers)
        median_integrated = median_value(company.get("integrated_research", {}).get("score") for company in peers)
        median_growth = median_value(company.get("revenue_growth_pct") for company in peers)
        median_fcf_margin = median_value(company.get("fcf_margin_pct") for company in peers)
        median_return_1y = median_value(company.get("return_1y_pct") for company in peers)
        breadth_pct = round(sum(company.get("above_50_day") is True for company in priced) / len(priced) * 100.0, 1) if priced else None
        positive_fcf_pct = round(sum((safe_float(company.get("latest_free_cash_flow")) or 0.0) > 0 for company in fcf_reporters) / len(fcf_reporters) * 100.0, 1) if fcf_reporters else None
        growth_signal = clamp(50.0 + (median_growth or 0.0) * 2.0) if median_growth is not None else None

        strength_score = weighted_percentile_score([
            (median_score, 30),
            (median_integrated, 25),
            (breadth_pct, 15),
            (positive_fcf_pct, 15),
            (growth_signal, 15),
        ])
        if strength_score is None:
            profile = "Insufficient subsector evidence"
        elif strength_score >= 72:
            profile = "Leading subsector evidence"
        elif strength_score >= 60:
            profile = "Constructive subsector evidence"
        elif strength_score >= 48:
            profile = "Mixed subsector evidence"
        else:
            profile = "Cautious subsector evidence"

        market_caps = [safe_float(company.get("market_cap")) for company in peers]
        market_caps = [value for value in market_caps if value is not None and value > 0]
        total_market_cap = sum(market_caps) if market_caps else None
        sorted_caps = sorted(market_caps, reverse=True)
        top2_share = round(sum(sorted_caps[:2]) / total_market_cap * 100.0, 1) if total_market_cap else None
        if top2_share is None:
            concentration = "Unclassified"
        elif top2_share >= 80:
            concentration = "Highly concentrated"
        elif top2_share >= 60:
            concentration = "Moderately concentrated"
        else:
            concentration = "Broadly distributed"

        # Company-level position scores are calculated only against the current subsector.
        peer_original_scores = [company.get("score") for company in peers]
        peer_integrated_scores = [company.get("integrated_research", {}).get("score") for company in peers]
        peer_growth = [company.get("revenue_growth_pct") for company in peers]
        peer_fcf = [company.get("fcf_margin_pct") for company in peers]
        peer_capital = [company.get("capital_efficiency", {}).get("score") for company in peers]
        peer_valuation = [company.get("relative_valuation", {}).get("score") for company in peers]

        for company in peers:
            components = {
                "original_score_percentile": percentile_rank(company.get("score"), peer_original_scores),
                "integrated_evidence_percentile": percentile_rank(company.get("integrated_research", {}).get("score"), peer_integrated_scores),
                "revenue_growth_percentile": percentile_rank(company.get("revenue_growth_pct"), peer_growth),
                "free_cash_flow_margin_percentile": percentile_rank(company.get("fcf_margin_pct"), peer_fcf),
                "capital_efficiency_percentile": percentile_rank(company.get("capital_efficiency", {}).get("score"), peer_capital),
                "relative_valuation_percentile": percentile_rank(company.get("relative_valuation", {}).get("score"), peer_valuation),
            }
            position_score = weighted_percentile_score([
                (components["original_score_percentile"], 25),
                (components["integrated_evidence_percentile"], 25),
                (components["revenue_growth_percentile"], 15),
                (components["free_cash_flow_margin_percentile"], 15),
                (components["capital_efficiency_percentile"], 10),
                (components["relative_valuation_percentile"], 10),
            ])
            available = sum(value is not None for value in components.values())
            if position_score is None or available < 3:
                position_profile = "Insufficient comparative evidence"
            elif position_score >= 75:
                position_profile = "Subsector leader"
            elif position_score >= 60:
                position_profile = "Strong competitive position"
            elif position_score >= 42:
                position_profile = "Balanced competitive position"
            else:
                position_profile = "Developing competitive position"
            company["competitive_position"] = {
                "status": "Phase 12 peer-relative competitive-position research",
                "score": position_score,
                "profile": position_profile,
                "available_component_count": available,
                "components": components,
            }
            company["competitive_position_score"] = position_score
            if position_score is not None:
                all_position_scores.append(position_score)

        positioned = [company for company in peers if safe_float(company.get("competitive_position_score")) is not None]
        positioned.sort(key=lambda company: safe_float(company.get("competitive_position_score")) or -1, reverse=True)
        for rank, company in enumerate(positioned, start=1):
            company["competitive_position"]["subsector_rank"] = rank
            company["competitive_position"]["subsector_count"] = len(positioned)

        subsectors.append({
            "subsector": subsector,
            "profile": profile,
            "research_strength_score": strength_score,
            "company_count": len(peers),
            "priced_company_count": len(priced),
            "median_company_score": median_score,
            "median_integrated_evidence_score": median_integrated,
            "median_revenue_growth_pct": median_growth,
            "median_fcf_margin_pct": median_fcf_margin,
            "median_return_1y_pct": median_return_1y,
            "breadth_above_50_day_pct": breadth_pct,
            "positive_fcf_company_pct": positive_fcf_pct,
            "aggregate_market_cap": round(total_market_cap, 2) if total_market_cap is not None else None,
            "top_two_market_cap_share_pct": top2_share,
            "market_cap_concentration": concentration,
            "original_score_leader": leader_summary(peers, lambda company: company.get("score")),
            "integrated_evidence_leader": leader_summary(peers, lambda company: company.get("integrated_research", {}).get("score")),
            "revenue_growth_leader": leader_summary(peers, lambda company: company.get("revenue_growth_pct")),
            "capital_efficiency_leader": leader_summary(peers, lambda company: company.get("capital_efficiency", {}).get("score")),
            "relative_valuation_leader": leader_summary(peers, lambda company: company.get("relative_valuation", {}).get("score")),
            "dominant_strength": most_common_research_item(peers, "strengths"),
            "dominant_risk": most_common_research_item(peers, "risks"),
        })

    subsectors.sort(key=lambda row: safe_float(row.get("research_strength_score")) or -1, reverse=True)
    for rank, row in enumerate(subsectors, start=1):
        row["research_strength_rank"] = rank

    strongest = subsectors[0] if subsectors else {}
    highest_growth = max(
        (row for row in subsectors if safe_float(row.get("median_revenue_growth_pct")) is not None),
        key=lambda row: safe_float(row.get("median_revenue_growth_pct")) or -1e18,
        default={},
    )
    highest_fcf = max(
        (row for row in subsectors if safe_float(row.get("median_fcf_margin_pct")) is not None),
        key=lambda row: safe_float(row.get("median_fcf_margin_pct")) or -1e18,
        default={},
    )
    breadth_values = [safe_float(row.get("breadth_above_50_day_pct")) for row in subsectors]
    breadth_values = [value for value in breadth_values if value is not None]

    return {
        "status": "Phase 12 AI subsector leadership and competitive-landscape research",
        "subsector_count": len(subsectors),
        "company_count": len(companies),
        "median_competitive_position_score": median_value(all_position_scores),
        "average_subsector_breadth_pct": round(statistics.fmean(breadth_values), 1) if breadth_values else None,
        "strongest_subsector": strongest.get("subsector"),
        "strongest_subsector_score": strongest.get("research_strength_score"),
        "highest_growth_subsector": highest_growth.get("subsector"),
        "highest_growth_median_pct": highest_growth.get("median_revenue_growth_pct"),
        "highest_fcf_subsector": highest_fcf.get("subsector"),
        "highest_fcf_median_pct": highest_fcf.get("median_fcf_margin_pct"),
        "subsectors": subsectors,
        "method": (
            "The separate Phase 12 subsector research-strength score combines the median original company score (30%), "
            "median integrated evidence score (25%), share of priced companies above their 50-day average (15%), share "
            "of reporting companies with positive standardized free cash flow (15%), and a transparent revenue-growth "
            "signal (15%). Company competitive-position scores use within-subsector percentiles and remain separate from "
            "the original ranking score."
        ),
        "limitations": [
            "The prototype has only a small number of companies in each subsector, so rankings and medians can change materially when the universe expands.",
            "Subsector labels are Stock Digest research classifications and may not match an issuer's formal reporting segments or a licensed industry taxonomy.",
            "Aggregate market capitalization and concentration are descriptive snapshots, not measures of addressable market, economic moat, or future industry share.",
            "The subsector strength and competitive-position scores summarize available quantitative evidence; they do not independently measure products, patents, management, customers, regulation, or private competitors.",
            "Phase 12 remains separate from the original company score and does not rewrite official weekly rankings, historical snapshots, backtests, or likelihood calibration.",
            "No Phase 12 label is a buy, sell, hold, sector-allocation, or investment recommendation.",
        ],
    }



def eastern_business_date(now: datetime | None = None) -> str:
    """Return the current New York calendar date used for daily research snapshots."""
    current = (now or datetime.now(timezone.utc)).astimezone(EASTERN)
    return current.date().isoformat()


def daily_snapshot_company_state(company: dict[str, Any]) -> dict[str, Any]:
    """Store only fields needed to explain later day-over-day research changes."""
    integrated = company.get("integrated_research", {}) if isinstance(company.get("integrated_research"), dict) else {}
    outlook = company.get("outlook", {}) if isinstance(company.get("outlook"), dict) else {}
    capital = company.get("capital_efficiency", {}) if isinstance(company.get("capital_efficiency"), dict) else {}
    valuation = company.get("relative_valuation", {}) if isinstance(company.get("relative_valuation"), dict) else {}
    filing = company.get("filing_monitor", {}) if isinstance(company.get("filing_monitor"), dict) else {}
    return {
        "ticker": company.get("ticker"),
        "name": company.get("name"),
        "subsector": company.get("subsector"),
        "overall_rank": company.get("overall_rank"),
        "score": company.get("score"),
        "integrated_research_score": integrated.get("score"),
        "integrated_stance": integrated.get("stance"),
        "outperformance_likelihood_12m_pct": company.get("outperformance_likelihood_12m_pct"),
        "outlook_label": outlook.get("label"),
        "capital_profile": capital.get("profile"),
        "relative_valuation_profile": valuation.get("profile"),
        "latest_price": company.get("latest_price"),
        "price_date": company.get("price_date"),
        "data_coverage_pct": company.get("data_coverage_pct"),
        "latest_filing_date": filing.get("latest_filing_date"),
        "latest_event_category": filing.get("latest_event_category"),
    }


def create_or_preserve_daily_snapshots(
    old_data: dict[str, Any], companies: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Preserve one immutable first-successful-refresh snapshot per New York date."""
    snapshots = [
        item for item in old_data.get("daily_snapshots", [])
        if isinstance(item, dict) and item.get("snapshot_date")
    ]
    by_date: dict[str, dict[str, Any]] = {}
    for item in sorted(snapshots, key=lambda row: (str(row.get("snapshot_date", "")), str(row.get("captured_at", "")))):
        by_date.setdefault(str(item.get("snapshot_date")), item)

    snapshot_date = eastern_business_date()
    if snapshot_date not in by_date:
        by_date[snapshot_date] = {
            "snapshot_date": snapshot_date,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "capture_policy": "First successful AI Intelligence refresh of the New York calendar date",
            "companies": [daily_snapshot_company_state(company) for company in companies],
        }

    # Retain roughly one year plus a buffer while preventing unbounded JSON growth.
    ordered = [by_date[key] for key in sorted(by_date)]
    return ordered[-400:]


def rounded_delta(current: Any, previous: Any) -> float | None:
    current_value = safe_float(current)
    previous_value = safe_float(previous)
    if current_value is None or previous_value is None:
        return None
    return round(current_value - previous_value, 2)


def build_daily_change_monitor(
    snapshots: list[dict[str, Any]], companies: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compare current research state with the previous preserved daily snapshot."""
    now = datetime.now(timezone.utc)
    current_date = eastern_business_date(now)
    prior_candidates = [
        item for item in snapshots
        if str(item.get("snapshot_date", "")) < current_date
    ]
    prior_snapshot = prior_candidates[-1] if prior_candidates else None

    if prior_snapshot is None:
        for company in companies:
            company["daily_change"] = {
                "status": "Baseline recorded; awaiting a later daily snapshot for comparison",
                "comparison_date": None,
                "priority": "Baseline",
                "summary": "No prior Phase 11 daily snapshot is available yet.",
                "material_change": False,
            }
        return {
            "status": "Phase 11 baseline recorded; awaiting the next successful daily refresh",
            "as_of": now.isoformat(),
            "comparison_date": None,
            "snapshot_date": current_date,
            "snapshots_recorded": len(snapshots),
            "companies_with_material_change": 0,
            "high_priority_count": 0,
            "moderate_priority_count": 0,
            "new_filing_count": 0,
            "largest_absolute_score_change": None,
            "alerts": [],
            "method": "The first Phase 11 refresh establishes a baseline. Later refreshes compare with the most recent prior preserved New York-date snapshot.",
            "limitations": [
                "A baseline and at least one later daily snapshot are required before change alerts can be calculated.",
                "The scheduled workflow normally runs on weekdays, so the comparison may span weekends or holidays.",
                "Alerts identify changes in the research system; they are not buy, sell, or risk-management instructions.",
            ],
        }

    previous_by_ticker = {
        item.get("ticker"): item
        for item in prior_snapshot.get("companies", [])
        if isinstance(item, dict) and item.get("ticker")
    }
    alerts: list[dict[str, Any]] = []
    material_filing_categories = {
        "Earnings / Financial Results",
        "Acquisition or Disposition",
        "Cybersecurity Incident",
        "Debt or Financing",
        "Material Agreement",
        "Leadership / Board Change",
    }

    for company in companies:
        ticker = company.get("ticker")
        previous = previous_by_ticker.get(ticker)
        if not previous:
            company["daily_change"] = {
                "status": "New company without a prior daily comparison",
                "comparison_date": prior_snapshot.get("snapshot_date"),
                "priority": "Baseline",
                "summary": "This company was not present in the previous Phase 11 snapshot.",
                "material_change": False,
            }
            continue

        integrated = company.get("integrated_research", {}) if isinstance(company.get("integrated_research"), dict) else {}
        outlook = company.get("outlook", {}) if isinstance(company.get("outlook"), dict) else {}
        capital = company.get("capital_efficiency", {}) if isinstance(company.get("capital_efficiency"), dict) else {}
        valuation = company.get("relative_valuation", {}) if isinstance(company.get("relative_valuation"), dict) else {}
        filing = company.get("filing_monitor", {}) if isinstance(company.get("filing_monitor"), dict) else {}

        score_delta = rounded_delta(company.get("score"), previous.get("score"))
        evidence_delta = rounded_delta(integrated.get("score"), previous.get("integrated_research_score"))
        likelihood_delta = rounded_delta(
            company.get("outperformance_likelihood_12m_pct"),
            previous.get("outperformance_likelihood_12m_pct"),
        )
        coverage_delta = rounded_delta(company.get("data_coverage_pct"), previous.get("data_coverage_pct"))
        price_change = pct_change(
            safe_float(company.get("latest_price")),
            safe_float(previous.get("latest_price")),
        )
        current_rank = company.get("overall_rank")
        previous_rank = previous.get("overall_rank")
        rank_change = (
            int(previous_rank) - int(current_rank)
            if isinstance(previous_rank, int) and isinstance(current_rank, int)
            else None
        )

        current_filing_date = str(filing.get("latest_filing_date") or "")
        previous_filing_date = str(previous.get("latest_filing_date") or "")
        new_filing = bool(current_filing_date and current_filing_date > previous_filing_date)
        current_category = filing.get("latest_event_category")

        outlook_changed = bool(outlook.get("label") and outlook.get("label") != previous.get("outlook_label"))
        stance_changed = bool(integrated.get("stance") and integrated.get("stance") != previous.get("integrated_stance"))
        capital_changed = bool(capital.get("profile") and capital.get("profile") != previous.get("capital_profile"))
        valuation_changed = bool(
            valuation.get("profile") and valuation.get("profile") != previous.get("relative_valuation_profile")
        )

        messages: list[str] = []
        severity_points = 0
        high_trigger = False

        if score_delta is not None and abs(score_delta) >= 2:
            messages.append(f"Original score changed {score_delta:+.1f} points")
            severity_points += 2 if abs(score_delta) >= 5 else 1
            high_trigger = high_trigger or abs(score_delta) >= 5
        if evidence_delta is not None and abs(evidence_delta) >= 3:
            messages.append(f"Integrated evidence changed {evidence_delta:+.1f} points")
            severity_points += 2 if abs(evidence_delta) >= 6 else 1
            high_trigger = high_trigger or abs(evidence_delta) >= 6
        if rank_change is not None and abs(rank_change) >= 2:
            direction = "rose" if rank_change > 0 else "fell"
            messages.append(f"Overall rank {direction} {abs(rank_change)} places")
            severity_points += 2 if abs(rank_change) >= 4 else 1
            high_trigger = high_trigger or abs(rank_change) >= 4
        if likelihood_delta is not None and abs(likelihood_delta) >= 4:
            messages.append(f"12-month research likelihood changed {likelihood_delta:+.1f} percentage points")
            severity_points += 2 if abs(likelihood_delta) >= 8 else 1
            high_trigger = high_trigger or abs(likelihood_delta) >= 8
        if price_change is not None and abs(price_change) >= 3:
            messages.append(f"Observed market price changed {price_change:+.1f}% since the prior snapshot")
            severity_points += 2 if abs(price_change) >= 7 else 1
            high_trigger = high_trigger or abs(price_change) >= 7
        if outlook_changed:
            messages.append(f"Operating outlook changed to {outlook.get('label')}")
            severity_points += 2
            high_trigger = True
        if stance_changed:
            messages.append(f"Integrated evidence stance changed to {integrated.get('stance')}")
            severity_points += 2
        if capital_changed:
            messages.append(f"Capital profile changed to {capital.get('profile')}")
            severity_points += 1
        if valuation_changed:
            messages.append(f"Relative valuation profile changed to {valuation.get('profile')}")
            severity_points += 1
        if coverage_delta is not None and coverage_delta <= -10:
            messages.append(f"Data coverage declined {abs(coverage_delta):.0f} percentage points")
            severity_points += 1
        if new_filing:
            messages.append(
                f"New SEC filing: {current_category or 'Unclassified filing'} on {current_filing_date}"
            )
            severity_points += 2 if current_category in material_filing_categories else 1
            high_trigger = high_trigger or current_category in material_filing_categories

        material = bool(messages)
        if not material:
            priority = "Routine"
            summary = "No Phase 11 material-change threshold was crossed."
        elif high_trigger or severity_points >= 4:
            priority = "High"
            summary = "; ".join(messages)
        else:
            priority = "Moderate"
            summary = "; ".join(messages)

        change_record = {
            "status": "Compared with the most recent prior Phase 11 daily snapshot",
            "comparison_date": prior_snapshot.get("snapshot_date"),
            "priority": priority,
            "material_change": material,
            "summary": summary,
            "score_delta": score_delta,
            "integrated_evidence_delta": evidence_delta,
            "rank_change": rank_change,
            "likelihood_delta_pct_points": likelihood_delta,
            "price_change_pct": price_change,
            "data_coverage_delta_pct_points": coverage_delta,
            "outlook_changed": outlook_changed,
            "integrated_stance_changed": stance_changed,
            "capital_profile_changed": capital_changed,
            "valuation_profile_changed": valuation_changed,
            "new_filing": new_filing,
            "latest_filing_date": current_filing_date or None,
            "latest_event_category": current_category,
            "messages": messages,
        }
        company["daily_change"] = change_record
        if material:
            alerts.append({
                "ticker": ticker,
                "name": company.get("name"),
                "subsector": company.get("subsector"),
                **change_record,
            })

    priority_order = {"High": 0, "Moderate": 1, "Routine": 2, "Baseline": 3}
    alerts.sort(
        key=lambda item: (
            priority_order.get(str(item.get("priority")), 9),
            -abs(safe_float(item.get("score_delta")) or 0),
            str(item.get("ticker")),
        )
    )
    score_moves = [abs(safe_float(item.get("score_delta")) or 0) for item in alerts if item.get("score_delta") is not None]
    return {
        "status": "Phase 11 daily change monitor with research alert thresholds",
        "as_of": now.isoformat(),
        "snapshot_date": current_date,
        "comparison_date": prior_snapshot.get("snapshot_date"),
        "snapshots_recorded": len(snapshots),
        "companies_with_material_change": len(alerts),
        "high_priority_count": sum(item.get("priority") == "High" for item in alerts),
        "moderate_priority_count": sum(item.get("priority") == "Moderate" for item in alerts),
        "new_filing_count": sum(bool(item.get("new_filing")) for item in alerts),
        "largest_absolute_score_change": round(max(score_moves), 2) if score_moves else None,
        "alerts": alerts,
        "method": (
            "Phase 11 compares the current refresh with the most recent prior preserved New York-date snapshot. "
            "It flags changes that cross published thresholds in scores, ranks, likelihoods, outlook/profile labels, "
            "market price, data coverage, or SEC filing activity."
        ),
        "limitations": [
            "A daily alert means the research state changed; it does not determine whether the change is favorable, durable, or investable.",
            "The comparison spans the most recent successful workflow dates and may cover more than one calendar day across weekends, holidays, or failed runs.",
            "Market-price changes can reflect broad market or macroeconomic developments unrelated to company fundamentals.",
            "SEC filing alerts identify new tracked disclosures but do not replace reading the complete filing.",
            "Phase 11 does not alter the original score, official weekly rankings, historical backtest, or likelihood calibration.",
        ],
    }


HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Market Intelligence - Stock Digest</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#f7f7f5;--text:#111;--secondary:#666;--muted:#888;--card:#fff;--border:#e4e2dc;--header:#f0efe9;--accent:#1f4e79;--positive:#1a7f37;--negative:#b42318;--shadow:0 8px 24px rgba(0,0,0,.05)}
body.dark-mode{--bg:#0d0d0d;--text:#e9e9e9;--secondary:#b5b5b5;--muted:#8d8d8d;--card:#191919;--border:#333;--header:#222;--accent:#82b9e6;--positive:#67c587;--negative:#ff8b84;--shadow:none}
*{box-sizing:border-box}body{margin:0;padding:24px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text)}a{color:var(--accent)}.container{max-width:1250px;margin:0 auto}.topbar{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:18px;flex-wrap:wrap}.nav a{font-size:14px;font-weight:650;text-decoration:none;margin-right:16px}.theme-btn{border:1px solid var(--border);border-radius:20px;background:var(--card);color:var(--text);padding:8px 14px;cursor:pointer}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--accent);font-weight:800}.title-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}h1{font-size:28px;margin:5px 0}.premium{background:#f4c95d;color:#342800;font-size:11px;font-weight:800;border-radius:999px;padding:5px 9px}.timestamp{font-size:13px;color:var(--secondary);margin:0 0 18px}.notice{border:1px solid var(--border);background:var(--card);border-radius:10px;padding:12px 14px;color:var(--secondary);font-size:12px;line-height:1.5;margin-bottom:16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px}.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px;box-shadow:var(--shadow)}.label{font-size:11px;color:var(--secondary);text-transform:uppercase;letter-spacing:.04em}.value{font-size:22px;font-weight:750;margin-top:5px}.subvalue{font-size:11px;color:var(--muted);margin-top:4px}.positive{color:var(--positive)}.negative{color:var(--negative)}h2{font-size:19px;margin:28px 0 10px}.section-note{font-size:12px;color:var(--secondary);margin:0 0 12px;line-height:1.5}.chart-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px;box-shadow:var(--shadow)}.chart-wrap{height:390px}.range-buttons,.metric-buttons{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:10px}.range-buttons button,.metric-buttons button,.filter-row select,.filter-row input{border:1px solid var(--border);background:var(--card);color:var(--text);border-radius:7px;padding:7px 10px;font-size:12px}.range-buttons button,.metric-buttons button{cursor:pointer}.range-buttons button.active,.metric-buttons button.active{background:var(--accent);color:#fff;border-color:var(--accent)}.filter-row{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:10px}.filter-row input{min-width:230px}.table-wrap{overflow:auto;border:1px solid var(--border);border-radius:12px;background:var(--card)}table{border-collapse:collapse;width:100%;min-width:1040px}th{position:sticky;top:0;background:var(--header);color:var(--secondary);font-size:11px;text-align:left;padding:9px;white-space:nowrap;cursor:pointer}td{border-top:1px solid var(--border);padding:9px;font-size:12px;white-space:nowrap}tr.company-row{cursor:pointer}tr.company-row:hover{background:var(--header)}.score-pill{display:inline-block;min-width:48px;text-align:center;padding:4px 7px;border-radius:999px;background:var(--header);font-weight:750}.detail{display:grid;grid-template-columns:minmax(0,2fr) minmax(280px,1fr);gap:14px}.detail-panel{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:15px;box-shadow:var(--shadow)}.detail h3{margin:0 0 5px}.summary-text{font-size:13px;line-height:1.6;color:var(--secondary)}.mini-grid{display:grid;grid-template-columns:repeat(2,minmax(120px,1fr));gap:8px}.mini{border:1px solid var(--border);border-radius:9px;padding:10px}.mini .value{font-size:16px}.component-row{display:grid;grid-template-columns:135px 1fr 42px;align-items:center;gap:8px;margin:9px 0;font-size:12px}.bar{height:8px;border-radius:6px;background:var(--header);overflow:hidden}.bar span{display:block;height:100%;background:var(--accent)}.filings{padding-left:18px;margin:8px 0}.filings li{margin:7px 0;font-size:12px}.source-note{font-size:11px;color:var(--muted);line-height:1.5}.empty{padding:22px;text-align:center;color:var(--secondary)}.leaders-table{min-width:980px}.leaders-table td{white-space:normal;vertical-align:top}.leaders-table .company-link{cursor:pointer;color:var(--accent);font-weight:750}.tag{display:inline-block;border:1px solid var(--border);background:var(--header);border-radius:999px;padding:3px 7px;font-size:10px;font-weight:700}.analysis-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}.brief-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:12px}.brief-box{border:1px solid var(--border);border-radius:10px;padding:12px;background:var(--card)}.brief-box h4{margin:0 0 7px;font-size:13px}.brief-box p{margin:0;color:var(--secondary);font-size:12px;line-height:1.55}.analysis-box{border:1px solid var(--border);border-radius:10px;padding:12px}.analysis-box h4{margin:0 0 8px;font-size:13px}.analysis-box ul{margin:0;padding-left:18px;font-size:12px;line-height:1.5}.warning-box{border:1px solid #d9a441;background:rgba(217,164,65,.08);border-radius:10px;padding:11px;margin-top:12px;font-size:12px;line-height:1.5}.peer-table{min-width:650px}.peer-table th{cursor:default}.peer-table td{white-space:nowrap}.selected-peer{font-weight:750;background:var(--header)}.quality-high{color:var(--positive)}.quality-limited{color:var(--negative)}.rank-up{color:var(--positive);font-weight:750}.rank-down{color:var(--negative);font-weight:750}.rank-flat{color:var(--secondary)}.backtest-note{border-left:4px solid var(--accent)}.calibration-table{min-width:900px}.calibration-table th{cursor:default}.priority-pill{display:inline-block;border-radius:999px;padding:4px 8px;font-size:10px;font-weight:800}.priority-high{background:rgba(180,35,24,.13);color:var(--negative)}.priority-moderate{background:rgba(217,164,65,.16);color:#9a6b00}.priority-routine{background:var(--header);color:var(--secondary)}.change-summary{white-space:normal;min-width:320px;line-height:1.45}@media(max-width:800px){body{padding:14px}.detail{grid-template-columns:1fr}.analysis-grid,.brief-grid{grid-template-columns:1fr}.chart-wrap{height:320px}}
</style>
</head>
<body>
<div class="container">
  <div class="topbar">
    <div class="nav"><a href="index.html">Stocks &amp; Rates</a><a href="investment-map.html">Investment Map</a><a href="realestate.html">Real Estate</a></div>
    <button class="theme-btn" id="theme-toggle">◐ Dark Mode</button>
  </div>

  <div class="eyebrow">Stock Digest Research</div>
  <div class="title-row"><h1>AI Market Intelligence</h1><span class="premium">PHASE 12 PREMIUM PREVIEW</span></div>
  <p class="timestamp" id="updated-at">Loading the latest AI company dataset...</p>
  <div class="notice"><strong>Research framework—not investment advice.</strong> The company score organizes reported financial facts and market momentum using the published methodology below. Phase 12 retains the weekly record, historical backtest, likelihood research, operating scenarios, capital-efficiency, relative-valuation, SEC filing-reaction, integrated-evidence, and daily-change layers, then adds a separate AI subsector leadership and competitive-landscape section. The original ranking score remains unchanged so the existing track record stays comparable. Every score remains research rather than advice. SEC figures can differ across issuers because companies use different permitted XBRL tags and fiscal calendars.</div>

  <div class="grid" id="summary-cards"></div>

  <h2>Official AI Weekly Leaders</h2>
  <p class="section-note" id="leaders-note">The official list is frozen once each week; prices, live rank, and performance update daily.</p>
  <div class="table-wrap"><table class="leaders-table"><thead><tr>
    <th>Official</th><th>Live</th><th>Change</th><th>Company</th><th>Official score</th><th>12-mo research likelihood</th><th>Entry price</th><th>Return</th><th>Peer return</th><th>Relative</th>
  </tr></thead><tbody id="leaders-body"></tbody></table></div>

  <h2>Weekly Ranking Track Record</h2>
  <p class="section-note">Tracking begins with the first Phase 3 refresh. The system keeps every weekly snapshot, including weeks that underperform. Fixed-horizon results appear only after enough time has passed.</p>
  <div class="grid" id="track-record-cards"></div>
  <div class="table-wrap" style="margin-top:12px"><table class="leaders-table"><thead><tr>
    <th>Evaluation horizon</th><th>Selections evaluated</th><th>Outperformed peers</th><th>Hit rate</th><th>Average selection return</th><th>Average peer return</th><th>Average relative return</th>
  </tr></thead><tbody id="track-record-body"></tbody></table></div>
  <h3 style="font-size:15px;margin:18px 0 8px">Recent official weekly snapshots</h3>
  <div class="table-wrap"><table class="peer-table"><thead><tr><th>Week</th><th>Top-ranked company</th><th>Selections</th><th>Average return to date</th><th>Average relative return to date</th></tr></thead><tbody id="snapshot-history-body"></tbody></table></div>

  <h2>Phase 4 Historical Backtest Lab</h2>
  <p class="section-note">A preliminary monthly point-in-time test of the same transparent score. It uses only annual SEC facts filed by each historical test date and price information available through that date. The top five are tested because the prototype universe currently contains only 12 companies.</p>
  <div class="grid" id="backtest-cards"></div>
  <div class="table-wrap" style="margin-top:12px"><table class="calibration-table"><thead><tr><th>Holding period</th><th>Top-five observations</th><th>Outperformed subsector peers</th><th>Outperformed Nasdaq-100</th><th>Average return</th><th>Average relative to peers</th><th>Average relative to Nasdaq-100</th></tr></thead><tbody id="backtest-horizon-body"></tbody></table></div>
  <h3 style="font-size:15px;margin:18px 0 8px">Score-band calibration research</h3>
  <p class="section-note">This table asks whether higher score ranges historically performed differently. It reports retrospective rates only; it does not convert a score into a probability.</p>
  <div class="table-wrap"><table class="calibration-table"><thead><tr><th>Score band</th><th>Holding period</th><th>Observations</th><th>Historical peer-outperformance rate</th><th>Average return</th><th>Average relative to peers</th></tr></thead><tbody id="backtest-band-body"></tbody></table></div>
  <div class="notice backtest-note" id="backtest-limitations" style="margin-top:12px"></div>

  <h2>Phase 5 Backtest-Based Likelihood Lab</h2>
  <p class="section-note">A conservative research estimate of whether a company in the same score band historically outperformed its prototype subsector peers over the following 12 months. The model uses earlier observations for calibration and later observations for validation. It is not a guarantee, target, or investment recommendation.</p>
  <div class="grid" id="likelihood-cards"></div>
  <div class="table-wrap" style="margin-top:12px"><table class="calibration-table"><thead><tr><th>Score band</th><th>Calibration observations</th><th>Smoothed 12-mo likelihood</th><th>Research range</th><th>Validation observations</th><th>Validation actual rate</th><th>Validation error</th><th>Status</th></tr></thead><tbody id="likelihood-band-body"></tbody></table></div>
  <h3 style="font-size:15px;margin:18px 0 8px">Current company research estimates</h3>
  <div class="table-wrap"><table class="calibration-table"><thead><tr><th>Rank</th><th>Company</th><th>Score</th><th>Score band</th><th>12-mo research likelihood</th><th>Research range</th><th>Calibration sample</th><th>Validation sample</th><th>Status</th></tr></thead><tbody id="company-likelihood-body"></tbody></table></div>
  <div class="notice backtest-note" id="likelihood-limitations" style="margin-top:12px"></div>

  <h2>Phase 6 Past–Present–Future Outlook</h2>
  <p class="section-note">Three-year conservative, base, and optimistic operating scenarios built from reported revenue history, current growth, peer growth, and free-cash-flow margins. These are transparent Stock Digest scenarios—not company guidance, analyst consensus estimates, or price targets.</p>
  <div class="grid" id="outlook-cards"></div>
  <div class="table-wrap" style="margin-top:12px"><table class="calibration-table"><thead><tr><th>Rank</th><th>Company</th><th>Research outlook</th><th>Scenario confidence</th><th>3-year reported revenue CAGR</th><th>Base annual growth</th><th>Base year-3 revenue</th><th>Base year-3 free cash flow</th><th>12-mo research likelihood</th></tr></thead><tbody id="outlook-body"></tbody></table></div>
  <div class="notice backtest-note" id="outlook-limitations" style="margin-top:12px"></div>

  <h2>Phase 7 Capital Efficiency &amp; Financial Durability</h2>
  <p class="section-note">Compares how each company funds reported CapEx and R&amp;D, converts operating cash flow into free cash flow, and carries cash versus debt. The score is peer-relative within the current AI subsector universe and does not identify AI-only spending.</p>
  <div class="grid" id="capital-cards"></div>
  <div class="table-wrap" style="margin-top:12px"><table class="calibration-table"><thead><tr><th>Capital rank</th><th>Company</th><th>Capital profile</th><th>Efficiency score</th><th>CapEx + R&amp;D</th><th>Investment intensity</th><th>OCF / CapEx</th><th>FCF margin</th><th>Net cash</th><th>Revenue / investment $</th></tr></thead><tbody id="capital-body"></tbody></table></div>
  <div class="notice backtest-note" id="capital-limitations" style="margin-top:12px"></div>

  <h2>Phase 8 Relative Valuation &amp; Growth Quality</h2>
  <p class="section-note">Compares market capitalization and enterprise value with reported revenue, earnings, and standardized free cash flow. Lower multiples are considered together with growth and cash-flow quality; this is not an intrinsic-value estimate or price target.</p>
  <div class="grid" id="valuation-cards"></div>
  <div class="table-wrap" style="margin-top:12px"><table class="calibration-table"><thead><tr><th>Valuation rank</th><th>Company</th><th>Valuation profile</th><th>Relative score</th><th>Price / sales</th><th>EV / sales</th><th>FCF yield</th><th>Price / FCF</th><th>Revenue growth</th><th>FCF margin</th></tr></thead><tbody id="valuation-body"></tbody></table></div>
  <div class="notice backtest-note" id="valuation-limitations" style="margin-top:12px"></div>

  <h2>Phase 9 SEC Filing Catalyst &amp; Reaction Monitor</h2>
  <p class="section-note">Classifies recent SEC filings using form types and disclosed 8-K item codes, then measures the observed first-close and five-trading-day stock reactions. This is a disclosure and reaction monitor—not news sentiment, causation analysis, or a prediction.</p>
  <div class="grid" id="filing-cards"></div>
  <div class="table-wrap" style="margin-top:12px"><table class="calibration-table"><thead><tr><th>Reaction rank</th><th>Company</th><th>Attention</th><th>Latest filing</th><th>Latest category</th><th>Filings 90d</th><th>Average 1-day reaction</th><th>Average 5-day reaction</th><th>Positive 5-day share</th><th>Observed profile</th></tr></thead><tbody id="filing-body"></tbody></table></div>
  <div class="notice backtest-note" id="filing-limitations" style="margin-top:12px"></div>

  <h2>Phase 10 Integrated Evidence &amp; Company Research Brief</h2>
  <p class="section-note">Combines the existing company score, backtest-based likelihood, operating outlook, capital efficiency, relative valuation, and observed filing-reaction research into one transparent evidence summary. This separate synthesis does not change the official weekly ranking or its track record.</p>
  <div class="grid" id="integrated-cards"></div>
  <div class="table-wrap" style="margin-top:12px"><table class="calibration-table"><thead><tr><th>Evidence rank</th><th>Company</th><th>Evidence stance</th><th>Integrated score</th><th>Confidence</th><th>Original score</th><th>12-mo likelihood</th><th>Operating outlook</th><th>Capital profile</th><th>Valuation profile</th><th>Latest tracked catalyst</th></tr></thead><tbody id="integrated-body"></tbody></table></div>
  <div class="notice backtest-note" id="integrated-limitations" style="margin-top:12px"></div>

  <h2>Phase 11 Daily Change Monitor &amp; Research Alerts</h2>
  <p class="section-note">Compares the current successful refresh with the most recent prior preserved New York-date snapshot. It highlights material changes in scores, rank, likelihood, outlook, capital and valuation profiles, market price, data coverage, and SEC filing activity. Alerts describe changes—not investment actions.</p>
  <div class="grid" id="daily-change-cards"></div>
  <div class="table-wrap" style="margin-top:12px"><table class="calibration-table"><thead><tr><th>Priority</th><th>Company</th><th>What changed</th><th>Score Δ</th><th>Rank Δ</th><th>Evidence Δ</th><th>Likelihood Δ</th><th>Price move</th><th>New filing</th></tr></thead><tbody id="daily-change-body"></tbody></table></div>
  <div class="notice backtest-note" id="daily-change-limitations" style="margin-top:12px"></div>

  <h2>Phase 12 AI Subsector Leadership &amp; Competitive Landscape</h2>
  <p class="section-note">Aggregates the companies inside each Stock Digest AI subsector, compares financial strength, market breadth, growth, cash flow, integrated evidence, and market-cap concentration, then shows each company’s peer-relative competitive position. This layer does not change the official company score or weekly Top 10.</p>
  <div class="grid" id="subsector-cards"></div>
  <div class="table-wrap" style="margin-top:12px"><table class="calibration-table"><thead><tr><th>Subsector rank</th><th>Subsector</th><th>Evidence profile</th><th>Strength score</th><th>Companies</th><th>Median company score</th><th>Median integrated evidence</th><th>Median revenue growth</th><th>Median FCF margin</th><th>1-year return</th><th>Above 50-day</th><th>Top-two market-cap share</th><th>Original-score leader</th></tr></thead><tbody id="subsector-body"></tbody></table></div>
  <h3 style="font-size:15px;margin:18px 0 8px">Company competitive-position matrix</h3>
  <div class="table-wrap"><table class="calibration-table"><thead><tr><th>Peer rank</th><th>Company</th><th>Subsector</th><th>Position profile</th><th>Position score</th><th>Original score</th><th>Integrated evidence</th><th>Revenue growth</th><th>FCF margin</th><th>Capital efficiency</th><th>Relative valuation</th></tr></thead><tbody id="competitive-position-body"></tbody></table></div>
  <div class="notice backtest-note" id="subsector-limitations" style="margin-top:12px"></div>

  <h2>Past to Present: AI Market Direction</h2>
  <p class="section-note">Equal-weighted Stock Digest AI Index compared with the Nasdaq-100 and S&amp;P 500. Constituents enter when their public trading history begins, so earlier periods contain fewer companies.</p>
  <div class="chart-card">
    <div class="range-buttons" id="range-buttons"><button data-years="1">1 Year</button><button data-years="5" class="active">5 Years</button><button data-years="10">10 Years</button></div>
    <div class="chart-wrap"><canvas id="market-chart"></canvas></div>
  </div>

  <h2>AI Company Ranking</h2>
  <p class="section-note">Click a company to open its reported financial history, detailed score components, peer comparisons, strengths, risks, missing-data warnings, and recent SEC filings.</p>
  <div class="filter-row">
    <input id="company-search" type="search" placeholder="Search company or ticker">
    <select id="subsector-filter"><option value="">All subsectors</option></select>
    <select id="cap-filter"><option value="">All market-cap groups</option></select>
  </div>
  <div class="table-wrap"><table><thead><tr>
    <th data-sort="overall_rank">Rank</th><th data-sort="ticker">Ticker</th><th data-sort="name">Company</th><th data-sort="subsector">Subsector</th><th data-sort="market_cap_tier">Cap group</th><th data-sort="score">Score</th><th data-sort="integrated_research_score">Integrated evidence</th><th data-sort="outperformance_likelihood_12m_pct">12-mo research likelihood</th><th data-sort="capital_efficiency_score">Capital efficiency</th><th data-sort="relative_valuation_score">Relative valuation</th><th data-sort="revenue_growth_pct">Revenue growth</th><th data-sort="latest_free_cash_flow">Free cash flow</th><th data-sort="latest_capex">CapEx</th><th data-sort="return_1y_pct">1-year return</th>
  </tr></thead><tbody id="ranking-body"></tbody></table></div>

  <h2>Company Intelligence Snapshot</h2>
  <div class="detail" id="company-detail"><div class="detail-panel empty">Select a company from the ranking table.</div></div>

  <h2>How the preliminary score works</h2>
  <div class="notice">Revenue growth 25% · standardized free-cash-flow strength 20% · financial strength 15% · profitability 10% · market momentum 20% · R&amp;D and capital-investment intensity 10%. Missing inputs are excluded and the remaining weights are renormalized. The score ranks financial and market characteristics. Phase 5 maps broad score bands to a conservative, backtest-based 12-month peer-outperformance research estimate using earlier observations for calibration and later observations for validation. Phase 6 then adds operating scenarios, Phase 7 adds capital-efficiency research, Phase 8 adds a separate relative-valuation layer, Phase 9 adds observed SEC filing and market-reaction research, Phase 10 adds a separate integrated evidence brief, Phase 11 adds daily change detection and research alerts, and Phase 12 adds subsector leadership and company competitive-position research. The original ranking score is not retroactively changed. None of these features is a guarantee, target, analyst consensus estimate, intrinsic-value conclusion, or investment recommendation.</div>
  <p class="source-note">Financial facts: SEC EDGAR Company Facts API. Recent filings and disclosed 8-K item codes: SEC Submissions API. Historical prices and filing-date reactions: Yahoo Finance through yfinance for prototype development. Stock Digest standardized free cash flow equals operating cash flow minus cash capital expenditures. Total company CapEx is not automatically labeled AI-only CapEx.</p>
</div>
<script>
(function(){
'use strict';
let DATA=null, marketChart=null, companyChart=null, outlookChart=null, selectedTicker=null, rangeYears=5, companyMetric='revenue';
let sortKey='score', sortDirection='desc';
const moneyFmt=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',notation:'compact',maximumFractionDigits:1});
const numFmt=new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:1});
function esc(value){return String(value==null?'':value).replace(/[&<>'"]/g,function(ch){return {'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch];});}
function money(value){return value==null?'N/A':moneyFmt.format(value);}
function pct(value){if(value==null)return 'N/A';return (value>0?'+':'')+Number(value).toFixed(1)+'%';}
function plainPct(value){return value==null?'N/A':Number(value).toFixed(1)+'%';}
function numberOrNA(value,digits=1){return value==null?'N/A':Number(value).toFixed(digits);}
function formatPeerValue(key,value){if(value==null)return 'N/A';if(key==='score')return Number(value).toFixed(1);return pct(value);}
function componentLabel(key){return {growth:'Revenue growth',free_cash_flow:'Free cash flow',financial_strength:'Financial strength',profitability:'Profitability',momentum:'Market momentum',strategic_investment:'R&D and CapEx intensity'}[key]||key.replaceAll('_',' ');}
function signedClass(value){return value==null?'':Number(value)>=0?'positive':'negative';}
function saveTheme(){localStorage.setItem('siteDarkMode',document.body.classList.contains('dark-mode')?'dark':'light');}
function applyTheme(){const dark=localStorage.getItem('siteDarkMode')==='dark';document.body.classList.toggle('dark-mode',dark);document.getElementById('theme-toggle').textContent=dark?'☀ Light Mode':'◐ Dark Mode';}
document.getElementById('theme-toggle').addEventListener('click',function(){document.body.classList.toggle('dark-mode');saveTheme();applyTheme();renderMarketChart();if(selectedTicker)renderCompanyDetail(selectedTicker,false);});applyTheme();
function renderSummary(){const m=DATA.market_summary||{};const cards=[
['AI Market Direction',m.direction||'N/A','Rule-based trend label'],
['AI Index — 30 Days',pct(m.return_30d_pct),'Equal-weighted index',signedClass(m.return_30d_pct)],
['AI Index — 1 Year',pct(m.return_1y_pct),'Equal-weighted index',signedClass(m.return_1y_pct)],
['Above 50-Day Average',(m.above_50_day||0)+' of '+(m.priced_company_count||0),'Market breadth'],
['Positive Free Cash Flow',(m.positive_fcf_count||0)+' of '+(m.fcf_company_count||0),'Latest reported fiscal year'],
['Aggregate Reported CapEx',money(m.aggregate_latest_capex),'Total company CapEx; not AI-only']];
 document.getElementById('summary-cards').innerHTML=cards.map(c=>'<div class="card"><div class="label">'+esc(c[0])+'</div><div class="value '+(c[3]||'')+'">'+esc(c[1])+'</div><div class="subvalue">'+esc(c[2])+'</div></div>').join('');}
function rankChange(value){if(value==null||value===0)return '<span class="rank-flat">—</span>';return value>0?'<span class="rank-up">▲ '+value+'</span>':'<span class="rank-down">▼ '+Math.abs(value)+'</span>';}
function renderWeeklyLeaders(){const weekly=DATA.weekly_leaders||{},leaders=weekly.leaders||[];document.getElementById('leaders-note').textContent=(weekly.status||'Official weekly research ranking')+(weekly.week_start?' · Week beginning '+weekly.week_start:'')+(weekly.captured_at?' · Captured '+weekly.captured_at:'')+'. It is not a buy list or recommendation.';const body=document.getElementById('leaders-body');if(!leaders.length){body.innerHTML='<tr><td colspan="10" class="empty">The first official weekly snapshot will be recorded during the next successful refresh.</td></tr>';return;}body.innerHTML=leaders.map(item=>'<tr data-leader-ticker="'+esc(item.ticker)+'"><td><strong>'+esc(item.official_rank||'—')+'</strong></td><td>'+esc(item.live_rank||'—')+'</td><td>'+rankChange(item.rank_change)+'</td><td><span class="company-link">'+esc(item.name)+' ('+esc(item.ticker)+')</span><br><span class="source-note">'+esc(item.subsector||'')+'</span></td><td><span class="score-pill">'+esc(item.official_score==null?'N/A':Number(item.official_score).toFixed(1))+'</span></td><td>'+plainPct(item.research_likelihood_12m_pct)+'<br><span class="source-note">'+esc(item.likelihood_status||'')+'</span></td><td>'+money(item.entry_price)+'</td><td class="'+signedClass(item.return_since_selection_pct)+'">'+pct(item.return_since_selection_pct)+'</td><td class="'+signedClass(item.peer_return_since_selection_pct)+'">'+pct(item.peer_return_since_selection_pct)+'</td><td class="'+signedClass(item.relative_return_pct)+'"><strong>'+pct(item.relative_return_pct)+'</strong></td></tr>').join('');body.querySelectorAll('tr[data-leader-ticker]').forEach(row=>row.addEventListener('click',()=>renderCompanyDetail(row.dataset.leaderTicker,true)));}
function renderTrackRecord(){const track=DATA.performance_scorecard||{},horizons=track.horizons||[],weeks=track.recent_weeks||[];const h30=horizons.find(x=>x.days===30)||{},h90=horizons.find(x=>x.days===90)||{},h365=horizons.find(x=>x.days===365)||{};const cards=[['Tracking started',track.tracking_started?String(track.tracking_started).slice(0,10):'Awaiting first snapshot','Permanent history begins in Phase 3'],['Weeks recorded',track.weeks_recorded||0,'Official snapshots retained'],['30-day hit rate',h30.hit_rate_pct==null?'Awaiting history':pct(h30.hit_rate_pct),(h30.evaluated_selections||0)+' selections evaluated'],['3-month hit rate',h90.hit_rate_pct==null?'Awaiting history':pct(h90.hit_rate_pct),(h90.evaluated_selections||0)+' selections evaluated'],['12-month hit rate',h365.hit_rate_pct==null?'Awaiting history':pct(h365.hit_rate_pct),(h365.evaluated_selections||0)+' selections evaluated']];document.getElementById('track-record-cards').innerHTML=cards.map(c=>'<div class="card"><div class="label">'+esc(c[0])+'</div><div class="value">'+esc(c[1])+'</div><div class="subvalue">'+esc(c[2])+'</div></div>').join('');document.getElementById('track-record-body').innerHTML=horizons.map(h=>'<tr><td><strong>'+esc(h.label)+'</strong></td><td>'+esc(h.evaluated_selections||0)+'</td><td>'+esc(h.outperformed_count||0)+'</td><td>'+pct(h.hit_rate_pct)+'</td><td class="'+signedClass(h.average_selection_return_pct)+'">'+pct(h.average_selection_return_pct)+'</td><td class="'+signedClass(h.average_peer_return_pct)+'">'+pct(h.average_peer_return_pct)+'</td><td class="'+signedClass(h.average_excess_return_pct)+'"><strong>'+pct(h.average_excess_return_pct)+'</strong></td></tr>').join('')||'<tr><td colspan="7" class="empty">No fixed-horizon results are available yet.</td></tr>';document.getElementById('snapshot-history-body').innerHTML=[...weeks].reverse().map(w=>'<tr><td>'+esc(w.week_start||'N/A')+'</td><td>'+esc(w.top_company||'N/A')+'</td><td>'+esc(w.selection_count||0)+'</td><td class="'+signedClass(w.average_return_to_date_pct)+'">'+pct(w.average_return_to_date_pct)+'</td><td class="'+signedClass(w.average_excess_to_date_pct)+'">'+pct(w.average_excess_to_date_pct)+'</td></tr>').join('')||'<tr><td colspan="5" class="empty">The first official weekly snapshot will appear after the next refresh.</td></tr>';}

function renderBacktest(){const b=DATA.historical_backtest||{},horizons=b.top5_horizons||[],bands=b.score_band_calibration||[];const cards=[['Backtest period',b.period_start&&b.period_end?b.period_start+' to '+b.period_end:'Awaiting live history','Monthly point-in-time tests'],['Months tested',b.tested_months||0,b.rebalance_frequency||'Monthly'],['Prototype universe',b.current_universe_size||0,'Current companies only'],['Selected each month',b.selected_each_month||0,'Top-ranked historical scores'],['Calibration status',b.calibration_readiness||'Awaiting sample','Not a published probability']];document.getElementById('backtest-cards').innerHTML=cards.map(c=>'<div class="card"><div class="label">'+esc(c[0])+'</div><div class="value">'+esc(c[1])+'</div><div class="subvalue">'+esc(c[2])+'</div></div>').join('');document.getElementById('backtest-horizon-body').innerHTML=horizons.map(h=>'<tr><td><strong>'+esc(h.label)+'</strong></td><td>'+esc(h.selection_observations||0)+'</td><td>'+pct(h.peer_outperformance_rate_pct)+'</td><td>'+pct(h.nasdaq100_outperformance_rate_pct)+'</td><td class="'+signedClass(h.average_selection_return_pct)+'">'+pct(h.average_selection_return_pct)+'</td><td class="'+signedClass(h.average_excess_peer_pct)+'"><strong>'+pct(h.average_excess_peer_pct)+'</strong></td><td class="'+signedClass(h.average_excess_nasdaq100_pct)+'">'+pct(h.average_excess_nasdaq100_pct)+'</td></tr>').join('')||'<tr><td colspan="7" class="empty">The historical test could not be produced from the available data.</td></tr>';document.getElementById('backtest-band-body').innerHTML=bands.map(row=>'<tr><td><strong>'+esc(row.score_band)+'</strong></td><td>'+esc(row.horizon)+'</td><td>'+esc(row.observations||0)+'</td><td>'+pct(row.historical_peer_outperformance_rate_pct)+'</td><td class="'+signedClass(row.average_return_pct)+'">'+pct(row.average_return_pct)+'</td><td class="'+signedClass(row.average_excess_peer_pct)+'">'+pct(row.average_excess_peer_pct)+'</td></tr>').join('')||'<tr><td colspan="6" class="empty">No score-band observations are available.</td></tr>';const limits=b.limitations||[];document.getElementById('backtest-limitations').innerHTML='<strong>Important backtest limits</strong><ul>'+limits.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul><span class="source-note">'+esc(b.fundamental_policy||'')+'</span>';}

function renderLikelihood(){const model=DATA.likelihood_research||{},bands=model.bands||[],companies=(DATA.companies||[]).filter(c=>c.score!=null).slice().sort((a,b)=>(a.overall_rank||999)-(b.overall_rank||999));const cp=model.calibration_period||{},vp=model.validation_period||{};const cards=[['Model status',model.status||'Awaiting data','Research only'],['Calibration sample',model.calibration_observations||0,cp.start&&cp.end?cp.start+' to '+cp.end:'Awaiting history'],['Validation sample',model.validation_observations||0,vp.start&&vp.end?vp.start+' to '+vp.end:'Awaiting history'],['Eligible companies',model.eligible_company_count||0,'Minimum 12 calibration observations'],['Validation Brier score',model.brier_score==null?'N/A':Number(model.brier_score).toFixed(3),'Lower is better; research diagnostic'],['Weighted validation error',plainPct(model.weighted_validation_error_pct),'Absolute difference by score band']];document.getElementById('likelihood-cards').innerHTML=cards.map(c=>'<div class="card"><div class="label">'+esc(c[0])+'</div><div class="value">'+esc(c[1])+'</div><div class="subvalue">'+esc(c[2])+'</div></div>').join('');document.getElementById('likelihood-band-body').innerHTML=bands.map(row=>'<tr><td><strong>'+esc(row.score_band)+'</strong></td><td>'+esc(row.calibration_observations||0)+'</td><td><strong>'+plainPct(row.smoothed_likelihood_pct)+'</strong></td><td>'+(row.research_range_low_pct==null?'N/A':plainPct(row.research_range_low_pct)+'–'+plainPct(row.research_range_high_pct))+'</td><td>'+esc(row.validation_observations||0)+'</td><td>'+plainPct(row.validation_actual_rate_pct)+'</td><td>'+plainPct(row.validation_absolute_error_pct)+'</td><td>'+esc(row.status||'')+'</td></tr>').join('')||'<tr><td colspan="8" class="empty">The likelihood model is awaiting enough matured backtest observations.</td></tr>';document.getElementById('company-likelihood-body').innerHTML=companies.map(c=>'<tr data-likelihood-ticker="'+esc(c.ticker)+'"><td>'+esc(c.overall_rank||'—')+'</td><td><span class="company-link">'+esc(c.name)+' ('+esc(c.ticker)+')</span></td><td>'+esc(c.score==null?'N/A':Number(c.score).toFixed(1))+'</td><td>'+esc(c.likelihood_score_band||'N/A')+'</td><td><strong>'+plainPct(c.outperformance_likelihood_12m_pct)+'</strong></td><td>'+(c.likelihood_range_low_pct==null?'N/A':plainPct(c.likelihood_range_low_pct)+'–'+plainPct(c.likelihood_range_high_pct))+'</td><td>'+esc(c.likelihood_calibration_observations||0)+'</td><td>'+esc(c.likelihood_validation_observations||0)+'</td><td>'+esc(c.likelihood_status||'')+'</td></tr>').join('')||'<tr><td colspan="9" class="empty">No current company likelihood estimates are available.</td></tr>';document.querySelectorAll('tr[data-likelihood-ticker]').forEach(row=>row.addEventListener('click',()=>renderCompanyDetail(row.dataset.likelihoodTicker,true)));const limits=model.limitations||[];document.getElementById('likelihood-limitations').innerHTML='<strong>Important likelihood limits</strong><ul>'+limits.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul><span class="source-note">'+esc(model.method||'')+'</span>';}
function rangeRows(){const rows=DATA.market_index||[];if(!rows.length)return [];const cutoff=new Date(rows[rows.length-1].date);cutoff.setFullYear(cutoff.getFullYear()-rangeYears);const subset=rows.filter(r=>new Date(r.date)>=cutoff);if(!subset.length)return [];const base={ai_index:subset.find(r=>r.ai_index!=null)?.ai_index,nasdaq100:subset.find(r=>r.nasdaq100!=null)?.nasdaq100,sp500:subset.find(r=>r.sp500!=null)?.sp500};return subset.map(r=>({date:r.date,ai_index:r.ai_index!=null&&base.ai_index?r.ai_index/base.ai_index*100:null,nasdaq100:r.nasdaq100!=null&&base.nasdaq100?r.nasdaq100/base.nasdaq100*100:null,sp500:r.sp500!=null&&base.sp500?r.sp500/base.sp500*100:null}));}
function chartColors(){const dark=document.body.classList.contains('dark-mode');return {text:dark?'#d8d8d8':'#333',grid:dark?'#333':'#e7e5df',ai:'#1f77b4',ndx:'#9467bd',sp:'#777',conservative:'#b42318',optimistic:'#1a7f37'};}
function renderMarketChart(){const rows=rangeRows(),c=chartColors();if(marketChart)marketChart.destroy();marketChart=new Chart(document.getElementById('market-chart'),{type:'line',data:{labels:rows.map(r=>r.date),datasets:[{label:'Stock Digest AI Index',data:rows.map(r=>r.ai_index),borderColor:c.ai,pointRadius:0,borderWidth:2.5},{label:'Nasdaq-100',data:rows.map(r=>r.nasdaq100),borderColor:c.ndx,pointRadius:0,borderWidth:1.8},{label:'S&P 500',data:rows.map(r=>r.sp500),borderColor:c.sp,pointRadius:0,borderWidth:1.5}]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{labels:{color:c.text}}},scales:{x:{ticks:{color:c.text,maxTicksLimit:9},grid:{color:c.grid}},y:{ticks:{color:c.text},grid:{color:c.grid},title:{display:true,text:'Normalized value (start = 100)',color:c.text}}}}});}
function renderOutlook(){const model=DATA.outlook_research||{},companies=(DATA.companies||[]).filter(c=>c.outlook&&c.outlook.scenarios&&c.outlook.scenarios.length).slice().sort((a,b)=>(a.overall_rank||999)-(b.overall_rank||999));const cards=[['Companies modeled',model.companies_modeled||0,'of '+(model.company_count||0)+' tracked'],['Favorable outlook',model.favorable_count||0,'Quantitative research label'],['Balanced outlook',model.balanced_count||0,'Quantitative research label'],['Cautious outlook',model.cautious_count||0,'Quantitative research label'],['Median base growth',plainPct(model.median_base_revenue_growth_pct),'Annual revenue scenario'],['Positive base year-3 FCF',model.positive_base_year3_fcf_count||0,'Modeled companies']];document.getElementById('outlook-cards').innerHTML=cards.map(c=>'<div class="card"><div class="label">'+esc(c[0])+'</div><div class="value">'+esc(c[1])+'</div><div class="subvalue">'+esc(c[2])+'</div></div>').join('');document.getElementById('outlook-body').innerHTML=companies.map(c=>{const o=c.outlook||{},base=(o.scenarios||[]).find(s=>s.name==='Base')||{},year3=(base.projections||[]).slice(-1)[0]||{};return '<tr data-outlook-ticker="'+esc(c.ticker)+'"><td>'+esc(c.overall_rank||'—')+'</td><td><span class="company-link">'+esc(c.name)+' ('+esc(c.ticker)+')</span></td><td><strong>'+esc(o.label||'N/A')+'</strong></td><td>'+esc(o.confidence||'N/A')+'</td><td>'+plainPct(o.historical_revenue_cagr_3y_pct)+'</td><td>'+plainPct(base.annual_revenue_growth_pct)+'</td><td>'+money(year3.revenue)+'</td><td class="'+signedClass(year3.free_cash_flow)+'">'+money(year3.free_cash_flow)+'</td><td>'+plainPct(c.outperformance_likelihood_12m_pct)+'</td></tr>';}).join('')||'<tr><td colspan="9" class="empty">The operating outlook is awaiting enough standardized history.</td></tr>';document.querySelectorAll('tr[data-outlook-ticker]').forEach(row=>row.addEventListener('click',()=>renderCompanyDetail(row.dataset.outlookTicker,true)));const limits=model.limitations||[];document.getElementById('outlook-limitations').innerHTML='<strong>How to read these scenarios</strong><ul>'+limits.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul><span class="source-note">'+esc(model.method||'')+'</span>';}
function renderCapitalEfficiency(){const model=DATA.capital_efficiency_research||{},companies=(DATA.companies||[]).filter(c=>c.capital_efficiency&&c.capital_efficiency.score!=null).slice().sort((a,b)=>(a.capital_efficiency.overall_rank||999)-(b.capital_efficiency.overall_rank||999));const cards=[['Companies scored',model.companies_scored||0,'of '+(model.company_count||0)+' tracked'],['Median efficiency score',model.median_score==null?'N/A':Number(model.median_score).toFixed(1),'Peer-relative research score'],['Self-funded profiles',model.self_funded_count||0,'Includes heavy self-funded investment'],['Cash-consuming profiles',model.cash_consuming_count||0,'Latest standardized FCF negative'],['Positive net cash',model.positive_net_cash_count||0,'Cash and short investments exceed debt'],['Median investment intensity',plainPct(model.median_innovation_intensity_pct),'Reported CapEx + R&D / revenue']];document.getElementById('capital-cards').innerHTML=cards.map(c=>'<div class="card"><div class="label">'+esc(c[0])+'</div><div class="value">'+esc(c[1])+'</div><div class="subvalue">'+esc(c[2])+'</div></div>').join('');document.getElementById('capital-body').innerHTML=companies.map(c=>{const d=c.capital_efficiency||{};return '<tr data-capital-ticker="'+esc(c.ticker)+'"><td>'+esc(d.overall_rank||'—')+'</td><td><span class="company-link">'+esc(c.name)+' ('+esc(c.ticker)+')</span></td><td><strong>'+esc(d.profile||'N/A')+'</strong></td><td><span class="score-pill">'+esc(d.score==null?'N/A':Number(d.score).toFixed(1))+'</span></td><td>'+money(d.combined_capex_and_rnd)+'</td><td>'+plainPct(d.innovation_intensity_pct)+'</td><td>'+(d.operating_cash_flow_to_capex_x==null?'N/A':Number(d.operating_cash_flow_to_capex_x).toFixed(2)+'x')+'</td><td class="'+signedClass(c.fcf_margin_pct)+'">'+plainPct(c.fcf_margin_pct)+'</td><td class="'+signedClass(d.net_cash)+'">'+money(d.net_cash)+'</td><td>'+(d.revenue_per_investment_dollar_x==null?'N/A':Number(d.revenue_per_investment_dollar_x).toFixed(2)+'x')+'</td></tr>';}).join('')||'<tr><td colspan="10" class="empty">Capital-efficiency research is awaiting comparable financial data.</td></tr>';document.querySelectorAll('tr[data-capital-ticker]').forEach(row=>row.addEventListener('click',()=>renderCompanyDetail(row.dataset.capitalTicker,true)));const limits=model.limitations||[];document.getElementById('capital-limitations').innerHTML='<strong>How to read this research layer</strong><ul>'+limits.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul><span class="source-note">'+esc(model.method||'')+'</span>';}
function capitalDetailHtml(c){const d=c.capital_efficiency||{},p=d.peer_percentiles||{};const pctRow=(label,value)=>'<tr><td>'+esc(label)+'</td><td>'+(value==null?'N/A':Number(value).toFixed(0)+'th')+'</td></tr>';return '<h3 style="margin-top:20px">Capital Efficiency &amp; Financial Durability</h3><p class="section-note">'+esc(d.summary||d.status||'No capital-efficiency profile is available.')+'</p><div class="mini-grid"><div class="mini"><div class="label">Capital efficiency score</div><div class="value">'+esc(d.score==null?'N/A':Number(d.score).toFixed(1))+'</div><div class="subvalue">Rank '+esc(d.overall_rank||'N/A')+'</div></div><div class="mini"><div class="label">Capital profile</div><div class="value">'+esc(d.profile||'N/A')+'</div></div><div class="mini"><div class="label">CapEx + R&amp;D</div><div class="value">'+money(d.combined_capex_and_rnd)+'</div><div class="subvalue">Analytical total; not AI-only</div></div><div class="mini"><div class="label">Investment intensity</div><div class="value">'+plainPct(d.innovation_intensity_pct)+'</div><div class="subvalue">CapEx + R&amp;D / revenue</div></div><div class="mini"><div class="label">OCF covers CapEx</div><div class="value">'+(d.operating_cash_flow_to_capex_x==null?'N/A':Number(d.operating_cash_flow_to_capex_x).toFixed(2)+'x')+'</div></div><div class="mini"><div class="label">Net cash</div><div class="value '+signedClass(d.net_cash)+'">'+money(d.net_cash)+'</div></div><div class="mini"><div class="label">Revenue / investment $</div><div class="value">'+(d.revenue_per_investment_dollar_x==null?'N/A':Number(d.revenue_per_investment_dollar_x).toFixed(2)+'x')+'</div></div><div class="mini"><div class="label">3-year CapEx CAGR</div><div class="value">'+plainPct(d.capex_cagr_3y_pct)+'</div></div></div><div class="table-wrap" style="margin-top:12px"><table class="peer-table"><thead><tr><th>Peer-relative component</th><th>Subsector percentile</th></tr></thead><tbody>'+pctRow('Revenue growth',p.revenue_growth)+pctRow('FCF margin',p.fcf_margin)+pctRow('OCF / CapEx coverage',p.ocf_capex_coverage)+pctRow('Net cash / revenue',p.net_cash_to_revenue)+pctRow('Revenue / investment dollar',p.revenue_per_investment)+'</tbody></table></div><p class="source-note">This is a comparative research framework. It does not establish causation, identify AI-only investment, or constitute a valuation or investment recommendation.</p>';}
function renderValuation(){const model=DATA.relative_valuation_research||{},companies=(DATA.companies||[]).filter(c=>c.relative_valuation&&c.relative_valuation.score!=null).slice().sort((a,b)=>(a.relative_valuation.overall_rank||999)-(b.relative_valuation.overall_rank||999));const cards=[['Companies scored',model.companies_scored||0,'of '+(model.company_count||0)+' tracked'],['Median relative score',model.median_score==null?'N/A':Number(model.median_score).toFixed(1),'Separate from original ranking score'],['Median price / sales',model.median_price_to_sales_x==null?'N/A':Number(model.median_price_to_sales_x).toFixed(2)+'x','Latest annual reported revenue'],['Median EV / sales',model.median_enterprise_value_to_sales_x==null?'N/A':Number(model.median_enterprise_value_to_sales_x).toFixed(2)+'x','Requires cash and debt data'],['Positive FCF yield',model.positive_fcf_yield_count||0,'Companies with positive standardized FCF yield'],['Model version','Phase 8','Does not rewrite prior weekly snapshots']];document.getElementById('valuation-cards').innerHTML=cards.map(c=>'<div class="card"><div class="label">'+esc(c[0])+'</div><div class="value">'+esc(c[1])+'</div><div class="subvalue">'+esc(c[2])+'</div></div>').join('');document.getElementById('valuation-body').innerHTML=companies.map(c=>{const d=c.relative_valuation||{};return '<tr data-valuation-ticker="'+esc(c.ticker)+'"><td>'+esc(d.overall_rank||'—')+'</td><td><span class="company-link">'+esc(c.name)+' ('+esc(c.ticker)+')</span></td><td><strong>'+esc(d.profile||'N/A')+'</strong></td><td><span class="score-pill">'+esc(d.score==null?'N/A':Number(d.score).toFixed(1))+'</span></td><td>'+(d.price_to_sales_x==null?'N/A':Number(d.price_to_sales_x).toFixed(2)+'x')+'</td><td>'+(d.enterprise_value_to_sales_x==null?'N/A':Number(d.enterprise_value_to_sales_x).toFixed(2)+'x')+'</td><td class="'+signedClass(d.free_cash_flow_yield_pct)+'">'+plainPct(d.free_cash_flow_yield_pct)+'</td><td>'+(d.price_to_free_cash_flow_x==null?'N/A':Number(d.price_to_free_cash_flow_x).toFixed(1)+'x')+'</td><td class="'+signedClass(c.revenue_growth_pct)+'">'+pct(c.revenue_growth_pct)+'</td><td class="'+signedClass(c.fcf_margin_pct)+'">'+plainPct(c.fcf_margin_pct)+'</td></tr>';}).join('')||'<tr><td colspan="10" class="empty">Relative-valuation research is awaiting comparable market and financial data.</td></tr>';document.querySelectorAll('tr[data-valuation-ticker]').forEach(row=>row.addEventListener('click',()=>renderCompanyDetail(row.dataset.valuationTicker,true)));const limits=model.limitations||[];document.getElementById('valuation-limitations').innerHTML='<strong>How to read this research layer</strong><ul>'+limits.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul><span class="source-note">'+esc(model.method||'')+'</span>';}
function valuationDetailHtml(c){const d=c.relative_valuation||{},p=d.peer_percentiles||{},m=d.peer_medians||{};const pctRow=(label,value)=>'<tr><td>'+esc(label)+'</td><td>'+(value==null?'N/A':Number(value).toFixed(0)+'th')+'</td></tr>';return '<h3 style="margin-top:20px">Relative Valuation &amp; Growth Quality</h3><p class="section-note">'+esc(d.summary||d.status||'No relative-valuation profile is available.')+'</p><div class="mini-grid"><div class="mini"><div class="label">Relative valuation score</div><div class="value">'+esc(d.score==null?'N/A':Number(d.score).toFixed(1))+'</div><div class="subvalue">Rank '+esc(d.overall_rank||'N/A')+'</div></div><div class="mini"><div class="label">Valuation profile</div><div class="value">'+esc(d.profile||'N/A')+'</div></div><div class="mini"><div class="label">Price / sales</div><div class="value">'+(d.price_to_sales_x==null?'N/A':Number(d.price_to_sales_x).toFixed(2)+'x')+'</div><div class="subvalue">Peer median '+(m.price_to_sales_x==null?'N/A':Number(m.price_to_sales_x).toFixed(2)+'x')+'</div></div><div class="mini"><div class="label">EV / sales</div><div class="value">'+(d.enterprise_value_to_sales_x==null?'N/A':Number(d.enterprise_value_to_sales_x).toFixed(2)+'x')+'</div><div class="subvalue">Peer median '+(m.enterprise_value_to_sales_x==null?'N/A':Number(m.enterprise_value_to_sales_x).toFixed(2)+'x')+'</div></div><div class="mini"><div class="label">FCF yield</div><div class="value '+signedClass(d.free_cash_flow_yield_pct)+'">'+plainPct(d.free_cash_flow_yield_pct)+'</div></div><div class="mini"><div class="label">Price / FCF</div><div class="value">'+(d.price_to_free_cash_flow_x==null?'N/A':Number(d.price_to_free_cash_flow_x).toFixed(1)+'x')+'</div></div><div class="mini"><div class="label">Price / earnings</div><div class="value">'+(d.price_to_earnings_x==null?'N/A':Number(d.price_to_earnings_x).toFixed(1)+'x')+'</div></div><div class="mini"><div class="label">Growth-adjusted P/S</div><div class="value">'+(d.growth_adjusted_price_to_sales==null?'N/A':Number(d.growth_adjusted_price_to_sales).toFixed(3))+'</div></div></div><div class="table-wrap" style="margin-top:12px"><table class="peer-table"><thead><tr><th>Peer-relative component</th><th>Subsector percentile</th></tr></thead><tbody>'+pctRow('Lower price / sales',p.price_to_sales)+pctRow('Lower EV / sales',p.enterprise_value_to_sales)+pctRow('FCF yield',p.free_cash_flow_yield)+pctRow('Earnings yield',p.earnings_yield)+pctRow('Growth-adjusted price / sales',p.growth_adjusted_price_to_sales)+pctRow('Revenue growth',p.revenue_growth)+pctRow('FCF margin',p.fcf_margin)+'</tbody></table></div><p class="source-note">This is relative, annual-data-based research. It is not an intrinsic-value calculation, fair-value conclusion, price target, or recommendation.</p>';}
function populateFilters(){const subs=[...new Set(DATA.companies.map(c=>c.subsector))].sort();const caps=[...new Set(DATA.companies.map(c=>c.market_cap_tier))].sort();document.getElementById('subsector-filter').innerHTML='<option value="">All subsectors</option>'+subs.map(v=>'<option>'+esc(v)+'</option>').join('');document.getElementById('cap-filter').innerHTML='<option value="">All market-cap groups</option>'+caps.map(v=>'<option>'+esc(v)+'</option>').join('');}
function compare(a,b){let av=sortKey==='capital_efficiency_score'?(a.capital_efficiency||{}).score:sortKey==='relative_valuation_score'?(a.relative_valuation||{}).score:sortKey==='integrated_research_score'?(a.integrated_research||{}).score:a[sortKey],bv=sortKey==='capital_efficiency_score'?(b.capital_efficiency||{}).score:sortKey==='relative_valuation_score'?(b.relative_valuation||{}).score:sortKey==='integrated_research_score'?(b.integrated_research||{}).score:b[sortKey];if(av==null)av=sortDirection==='asc'?Infinity:-Infinity;if(bv==null)bv=sortDirection==='asc'?Infinity:-Infinity;if(typeof av==='string')return sortDirection==='asc'?av.localeCompare(bv):bv.localeCompare(av);return sortDirection==='asc'?av-bv:bv-av;}
function filteredCompanies(){const q=document.getElementById('company-search').value.trim().toLowerCase();const sub=document.getElementById('subsector-filter').value;const cap=document.getElementById('cap-filter').value;return DATA.companies.filter(c=>(!q||(c.name+' '+c.ticker).toLowerCase().includes(q))&&(!sub||c.subsector===sub)&&(!cap||c.market_cap_tier===cap)).sort(compare);}
function renderTable(){const rows=filteredCompanies();const body=document.getElementById('ranking-body');if(!rows.length){body.innerHTML='<tr><td colspan="14" class="empty">No companies match the selected filters.</td></tr>';return;}body.innerHTML=rows.map(c=>{const capital=(c.capital_efficiency||{}).score,valuation=(c.relative_valuation||{}).score,integrated=(c.integrated_research||{}).score;return '<tr class="company-row" data-ticker="'+esc(c.ticker)+'"><td>'+esc(c.overall_rank||'—')+'</td><td><strong>'+esc(c.ticker)+'</strong></td><td>'+esc(c.name)+'</td><td>'+esc(c.subsector)+'</td><td>'+esc(c.market_cap_tier)+'</td><td><span class="score-pill">'+esc(c.score==null?'N/A':Number(c.score).toFixed(1))+'</span></td><td>'+esc(integrated==null?'N/A':Number(integrated).toFixed(1))+'</td><td>'+plainPct(c.outperformance_likelihood_12m_pct)+'</td><td>'+esc(capital==null?'N/A':Number(capital).toFixed(1))+'</td><td>'+esc(valuation==null?'N/A':Number(valuation).toFixed(1))+'</td><td class="'+signedClass(c.revenue_growth_pct)+'">'+pct(c.revenue_growth_pct)+'</td><td class="'+signedClass(c.latest_free_cash_flow)+'">'+money(c.latest_free_cash_flow)+'</td><td>'+money(c.latest_capex)+'</td><td class="'+signedClass(c.return_1y_pct)+'">'+pct(c.return_1y_pct)+'</td></tr>';}).join('');body.querySelectorAll('tr[data-ticker]').forEach(row=>row.addEventListener('click',()=>renderCompanyDetail(row.dataset.ticker,true)));}
function metricTitle(metric){return {revenue:'Revenue',net_income:'Net income',free_cash_flow:'Free cash flow',capex:'Capital expenditures',rnd:'Research & development'}[metric]||metric;}
function renderCompanyChart(company){const history=(company.history||[]).filter(r=>r[companyMetric]!=null);const c=chartColors();if(companyChart)companyChart.destroy();companyChart=new Chart(document.getElementById('company-history-chart'),{type:'line',data:{labels:history.map(r=>r.year),datasets:[{label:metricTitle(companyMetric),data:history.map(r=>r[companyMetric]),borderColor:c.ai,backgroundColor:'rgba(31,119,180,.12)',fill:true,tension:.18,pointRadius:3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:c.text}},tooltip:{callbacks:{label:ctx=>metricTitle(companyMetric)+': '+money(ctx.raw)}}},scales:{x:{ticks:{color:c.text},grid:{color:c.grid}},y:{ticks:{color:c.text,callback:v=>numFmt.format(v)},grid:{color:c.grid}}}}});}
function renderCompanyOutlookChart(company){const canvas=document.getElementById('company-outlook-chart');if(!canvas)return;if(outlookChart)outlookChart.destroy();const o=company.outlook||{},scenarios=o.scenarios||[];const hist=(company.history||[]).filter(r=>r.revenue!=null).slice(-5);if(!hist.length||!scenarios.length)return;const futureYears=(scenarios[0].projections||[]).map(r=>r.year);const labels=hist.map(r=>r.year).concat(futureYears);const actual=hist.map(r=>r.revenue).concat(futureYears.map(()=>null));const lastActual=hist[hist.length-1].revenue;const c=chartColors();const scenarioColors={Conservative:c.conservative,Base:c.ai,Optimistic:c.optimistic};const datasets=[{label:'Reported revenue',data:actual,borderColor:c.sp,backgroundColor:'rgba(119,119,119,.10)',pointRadius:3,borderWidth:2}];scenarios.forEach(s=>{const values=hist.slice(0,-1).map(()=>null).concat([lastActual]).concat((s.projections||[]).map(r=>r.revenue));datasets.push({label:s.name+' scenario',data:values,borderColor:scenarioColors[s.name]||c.ai,borderDash:s.name==='Base'?[]:[6,4],pointRadius:3,borderWidth:s.name==='Base'?2.5:1.8,tension:.15});});outlookChart=new Chart(canvas,{type:'line',data:{labels:labels,datasets:datasets},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{labels:{color:c.text}},tooltip:{callbacks:{label:ctx=>ctx.dataset.label+': '+money(ctx.raw)}}},scales:{x:{ticks:{color:c.text},grid:{color:c.grid}},y:{ticks:{color:c.text,callback:v=>numFmt.format(v)},grid:{color:c.grid},title:{display:true,text:'Revenue',color:c.text}}}}});}
function renderFilingEvents(){const model=DATA.filing_event_research||{},companies=(DATA.companies||[]).filter(c=>c.filing_monitor&&c.filing_monitor.events_reviewed>0).slice().sort((a,b)=>(a.filing_monitor.reaction_rank||999)-(b.filing_monitor.reaction_rank||999));const cards=[['Companies analyzed',model.companies_analyzed||0,'of '+(model.company_count||0)+' tracked'],['Filing events reviewed',model.events_reviewed||0,'Recent periodic and current reports'],['Events with 5-day reactions',model.events_with_5d_reaction||0,'Observed price-history matches'],['Median company 5-day reaction',plainPct(model.median_company_5d_reaction_pct),'Median of company averages'],['Positive reaction companies',model.positive_reaction_company_count||0,'Average 5-day reaction above zero'],['High-attention companies',model.high_attention_company_count||0,'Recent activity or large reactions']];document.getElementById('filing-cards').innerHTML=cards.map(c=>'<div class="card"><div class="label">'+esc(c[0])+'</div><div class="value">'+esc(c[1])+'</div><div class="subvalue">'+esc(c[2])+'</div></div>').join('');document.getElementById('filing-body').innerHTML=companies.map(c=>{const d=c.filing_monitor||{};return '<tr data-filing-ticker="'+esc(c.ticker)+'"><td>'+esc(d.reaction_rank||'—')+'</td><td><span class="company-link">'+esc(c.name)+' ('+esc(c.ticker)+')</span></td><td><span class="tag">'+esc(d.attention_level||'N/A')+'</span></td><td>'+esc(d.latest_filing_date||'N/A')+'</td><td>'+esc(d.latest_event_category||'N/A')+'</td><td>'+esc(d.filings_90d==null?'N/A':d.filings_90d)+'</td><td class="'+signedClass(d.average_1d_reaction_pct)+'">'+pct(d.average_1d_reaction_pct)+'</td><td class="'+signedClass(d.average_5d_reaction_pct)+'">'+pct(d.average_5d_reaction_pct)+'</td><td>'+plainPct(d.positive_5d_share_pct)+'</td><td><strong>'+esc(d.profile||'N/A')+'</strong></td></tr>';}).join('')||'<tr><td colspan="10" class="empty">SEC filing reaction research is awaiting recent filings and matching price history.</td></tr>';document.querySelectorAll('tr[data-filing-ticker]').forEach(row=>row.addEventListener('click',()=>renderCompanyDetail(row.dataset.filingTicker,true)));const limits=model.limitations||[];document.getElementById('filing-limitations').innerHTML='<strong>How to read Phase 9</strong><ul>'+limits.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul><span class="source-note">'+esc(model.method||'')+'</span>';}
function filingDetailHtml(c){const d=c.filing_monitor||{},events=d.events||[];const rows=events.map(e=>'<tr><td><a target="_blank" rel="noopener" href="'+esc(e.url)+'">'+esc(e.form)+' — '+esc(e.date)+'</a></td><td>'+esc(e.category||'N/A')+'</td><td>'+esc((e.item_codes||[]).join(', ')||'—')+'</td><td class="'+signedClass(e.reaction_1d_pct)+'">'+pct(e.reaction_1d_pct)+'</td><td class="'+signedClass(e.reaction_5d_pct)+'">'+pct(e.reaction_5d_pct)+'</td></tr>').join('')||'<tr><td colspan="5" class="empty">No recent filing events were retrieved.</td></tr>';return '<h3 style="margin-top:20px">SEC Filing Catalyst &amp; Reaction Monitor</h3><p class="section-note">'+esc(d.summary||d.status||'No filing-reaction profile is available.')+'</p><div class="mini-grid"><div class="mini"><div class="label">Observed profile</div><div class="value">'+esc(d.profile||'N/A')+'</div></div><div class="mini"><div class="label">Attention level</div><div class="value">'+esc(d.attention_level||'N/A')+'</div></div><div class="mini"><div class="label">Reaction score</div><div class="value">'+esc(d.reaction_score==null?'N/A':Number(d.reaction_score).toFixed(1))+'</div><div class="subvalue">Rank '+esc(d.reaction_rank||'N/A')+'</div></div><div class="mini"><div class="label">Filings in 90 days</div><div class="value">'+esc(d.filings_90d==null?'N/A':d.filings_90d)+'</div></div><div class="mini"><div class="label">Average 1-day reaction</div><div class="value '+signedClass(d.average_1d_reaction_pct)+'">'+pct(d.average_1d_reaction_pct)+'</div></div><div class="mini"><div class="label">Average 5-day reaction</div><div class="value '+signedClass(d.average_5d_reaction_pct)+'">'+pct(d.average_5d_reaction_pct)+'</div></div><div class="mini"><div class="label">Positive 5-day share</div><div class="value">'+plainPct(d.positive_5d_share_pct)+'</div></div><div class="mini"><div class="label">Events reviewed</div><div class="value">'+esc(d.events_reviewed==null?'N/A':d.events_reviewed)+'</div></div></div><div class="table-wrap" style="margin-top:12px"><table class="peer-table"><thead><tr><th>Filing</th><th>SEC event category</th><th>8-K items</th><th>1-day reaction</th><th>5-day reaction</th></tr></thead><tbody>'+rows+'</tbody></table></div><p class="source-note">Price reactions are observations, not proof that a filing caused the move. Exact filing-session timing is not available in this prototype.</p>';}
function renderIntegratedResearch(){const model=DATA.integrated_research||{},companies=(DATA.companies||[]).filter(c=>c.integrated_research&&c.integrated_research.score!=null).slice().sort((a,b)=>(a.integrated_research.overall_rank||999)-(b.integrated_research.overall_rank||999));const cards=[['Companies synthesized',model.companies_scored||0,'of '+(model.company_count||0)+' tracked'],['Median evidence score',model.median_score==null?'N/A':Number(model.median_score).toFixed(1),'Separate integrated research score'],['Favorable balance',model.favorable_count||0,'Highest evidence stance'],['Constructive balance',model.constructive_count||0,'Positive but mixed evidence'],['Cautious balance',model.cautious_count||0,'Weakest evidence stance'],['High-confidence briefs',model.high_confidence_count||0,'Coverage and component gate']];document.getElementById('integrated-cards').innerHTML=cards.map(c=>'<div class="card"><div class="label">'+esc(c[0])+'</div><div class="value">'+esc(c[1])+'</div><div class="subvalue">'+esc(c[2])+'</div></div>').join('');document.getElementById('integrated-body').innerHTML=companies.map(c=>{const d=c.integrated_research||{},filing=c.filing_monitor||{};return '<tr data-integrated-ticker="'+esc(c.ticker)+'"><td>'+esc(d.overall_rank||'—')+'</td><td><span class="company-link">'+esc(c.name)+' ('+esc(c.ticker)+')</span></td><td><strong>'+esc(d.stance||'N/A')+'</strong></td><td><span class="score-pill">'+esc(d.score==null?'N/A':Number(d.score).toFixed(1))+'</span></td><td>'+esc(d.confidence||'N/A')+'</td><td>'+esc(c.score==null?'N/A':Number(c.score).toFixed(1))+'</td><td>'+plainPct(c.outperformance_likelihood_12m_pct)+'</td><td>'+esc((c.outlook||{}).label||'N/A')+'</td><td>'+esc((c.capital_efficiency||{}).profile||'N/A')+'</td><td>'+esc((c.relative_valuation||{}).profile||'N/A')+'</td><td>'+esc(filing.latest_event_category||'N/A')+(filing.latest_filing_date?' · '+esc(filing.latest_filing_date):'')+'</td></tr>';}).join('')||'<tr><td colspan="11" class="empty">Integrated evidence briefs are awaiting enough research components.</td></tr>';document.querySelectorAll('tr[data-integrated-ticker]').forEach(row=>row.addEventListener('click',()=>renderCompanyDetail(row.dataset.integratedTicker,true)));const limits=model.limitations||[];document.getElementById('integrated-limitations').innerHTML='<strong>How to read Phase 10</strong><ul>'+limits.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul><span class="source-note">'+esc(model.method||'')+'</span>';}
function integratedDetailHtml(c){const d=c.integrated_research||{},component=d.component_scores||{};const bullets=items=>(items||[]).map(x=>'<li>'+esc(x)+'</li>').join('')||'<li>No standardized item is currently available.</li>';const componentRows=[['Original company score',component.original_company_score],['Backtest likelihood',component.backtest_likelihood],['Operating outlook signal',component.operating_outlook_signal],['Capital efficiency',component.capital_efficiency],['Relative valuation',component.relative_valuation],['Filing reaction',component.filing_reaction]].map(row=>'<tr><td>'+esc(row[0])+'</td><td>'+(row[1]==null?'N/A':Number(row[1]).toFixed(1))+'</td></tr>').join('');return '<h3 style="margin-top:20px">Phase 10 Integrated Evidence Brief</h3><p class="section-note">'+esc(d.status||'No integrated brief is available.')+'</p><div class="mini-grid"><div class="mini"><div class="label">Integrated evidence score</div><div class="value">'+esc(d.score==null?'N/A':Number(d.score).toFixed(1))+'</div><div class="subvalue">Evidence rank '+esc(d.overall_rank||'N/A')+'</div></div><div class="mini"><div class="label">Evidence stance</div><div class="value">'+esc(d.stance||'N/A')+'</div></div><div class="mini"><div class="label">Integrated confidence</div><div class="value">'+esc(d.confidence||'N/A')+'</div><div class="subvalue">'+esc(d.available_component_count||0)+' of 6 components</div></div><div class="mini"><div class="label">Data coverage</div><div class="value">'+plainPct(d.data_coverage_pct)+'</div></div></div><div class="brief-grid"><div class="brief-box"><h4>Past</h4><p>'+esc(d.past_summary||'N/A')+'</p></div><div class="brief-box"><h4>Present</h4><p>'+esc(d.present_summary||'N/A')+'</p></div><div class="brief-box"><h4>Future research view</h4><p>'+esc(d.future_summary||'N/A')+'</p></div></div><div class="analysis-grid"><div class="analysis-box"><h4>Supporting evidence</h4><ul>'+bullets(d.supporting_evidence)+'</ul></div><div class="analysis-box"><h4>Counter-evidence and risks</h4><ul>'+bullets(d.counter_evidence)+'</ul></div></div><div class="analysis-box" style="margin-top:12px"><h4>What to monitor next</h4><ul>'+bullets(d.watch_items)+'</ul></div><div class="table-wrap" style="margin-top:12px"><table class="peer-table"><thead><tr><th>Integrated component</th><th>Current input</th></tr></thead><tbody>'+componentRows+'</tbody></table></div><p class="source-note">This is an automated synthesis of the research layers shown on this page. It is not a qualitative due-diligence report, investment recommendation, price target, or probability of company success.</p>';}

function changeDelta(value,suffix=''){if(value==null)return 'N/A';const n=Number(value);return (n>0?'+':'')+n.toFixed(1)+suffix;}
function priorityHtml(priority){const p=priority||'Routine',cls=p==='High'?'priority-high':p==='Moderate'?'priority-moderate':'priority-routine';return '<span class="priority-pill '+cls+'">'+esc(p)+'</span>';}
function renderDailyChanges(){const model=DATA.daily_change_monitor||{},alerts=model.alerts||[];const cards=[['Comparison date',model.comparison_date||'Baseline','Previous preserved snapshot'],['Material changes',model.companies_with_material_change||0,'Companies crossing a threshold'],['High priority',model.high_priority_count||0,'Research changes needing review'],['Moderate priority',model.moderate_priority_count||0,'Secondary research changes'],['New filing alerts',model.new_filing_count||0,'New tracked SEC disclosures'],['Daily snapshots',model.snapshots_recorded||0,'Preserved New York dates']];document.getElementById('daily-change-cards').innerHTML=cards.map(c=>'<div class="card"><div class="label">'+esc(c[0])+'</div><div class="value">'+esc(c[1])+'</div><div class="subvalue">'+esc(c[2])+'</div></div>').join('');const body=document.getElementById('daily-change-body');if(!alerts.length){body.innerHTML='<tr><td colspan="9" class="empty">'+esc(model.status||'No material Phase 11 changes crossed the published thresholds.')+'</td></tr>';}else{body.innerHTML=alerts.map(a=>'<tr data-change-ticker="'+esc(a.ticker)+'"><td>'+priorityHtml(a.priority)+'</td><td><span class="company-link">'+esc(a.name)+' ('+esc(a.ticker)+')</span><br><span class="source-note">'+esc(a.subsector||'')+'</span></td><td class="change-summary">'+esc(a.summary||'N/A')+'</td><td class="'+signedClass(a.score_delta)+'">'+changeDelta(a.score_delta)+'</td><td>'+rankChange(a.rank_change)+'</td><td class="'+signedClass(a.integrated_evidence_delta)+'">'+changeDelta(a.integrated_evidence_delta)+'</td><td class="'+signedClass(a.likelihood_delta_pct_points)+'">'+changeDelta(a.likelihood_delta_pct_points,' pp')+'</td><td class="'+signedClass(a.price_change_pct)+'">'+changeDelta(a.price_change_pct,'%')+'</td><td>'+(a.new_filing?esc((a.latest_event_category||'SEC filing')+' · '+(a.latest_filing_date||'')):'—')+'</td></tr>').join('');document.querySelectorAll('tr[data-change-ticker]').forEach(row=>row.addEventListener('click',()=>renderCompanyDetail(row.dataset.changeTicker,true)));}const limits=model.limitations||[];document.getElementById('daily-change-limitations').innerHTML='<strong>How to read Phase 11</strong><ul>'+limits.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul><span class="source-note">'+esc(model.method||'')+'</span>';}
function leaderName(item){return item&&item.name?item.name+(item.ticker?' ('+item.ticker+')':''):'N/A';}
function competitiveProfileHtml(profile){return '<span class="tag">'+esc(profile||'N/A')+'</span>';}
function renderSubsectorLandscape(){const model=DATA.subsector_landscape||{},rows=model.subsectors||[];const cards=[['Subsectors tracked',model.subsector_count||0,(model.company_count||0)+' companies'],['Strongest current evidence',model.strongest_subsector||'N/A',model.strongest_subsector_score==null?'Awaiting score':'Strength score '+Number(model.strongest_subsector_score).toFixed(1)],['Highest median growth',model.highest_growth_subsector||'N/A',plainPct(model.highest_growth_median_pct)],['Highest median FCF margin',model.highest_fcf_subsector||'N/A',plainPct(model.highest_fcf_median_pct)],['Average market breadth',plainPct(model.average_subsector_breadth_pct),'Share above 50-day average'],['Median company position',model.median_competitive_position_score==null?'N/A':Number(model.median_competitive_position_score).toFixed(1),'Within-subsector research score']];document.getElementById('subsector-cards').innerHTML=cards.map(c=>'<div class="card"><div class="label">'+esc(c[0])+'</div><div class="value">'+esc(c[1])+'</div><div class="subvalue">'+esc(c[2])+'</div></div>').join('');document.getElementById('subsector-body').innerHTML=rows.map(r=>'<tr><td>'+esc(r.research_strength_rank||'—')+'</td><td><strong>'+esc(r.subsector||'N/A')+'</strong></td><td>'+competitiveProfileHtml(r.profile)+'</td><td><span class="score-pill">'+esc(r.research_strength_score==null?'N/A':Number(r.research_strength_score).toFixed(1))+'</span></td><td>'+esc(r.company_count||0)+'</td><td>'+numberOrNA(r.median_company_score,1)+'</td><td>'+numberOrNA(r.median_integrated_evidence_score,1)+'</td><td class="'+signedClass(r.median_revenue_growth_pct)+'">'+plainPct(r.median_revenue_growth_pct)+'</td><td class="'+signedClass(r.median_fcf_margin_pct)+'">'+plainPct(r.median_fcf_margin_pct)+'</td><td class="'+signedClass(r.median_return_1y_pct)+'">'+plainPct(r.median_return_1y_pct)+'</td><td>'+plainPct(r.breadth_above_50_day_pct)+'</td><td>'+plainPct(r.top_two_market_cap_share_pct)+'</td><td>'+esc(leaderName(r.original_score_leader))+'</td></tr>').join('')||'<tr><td colspan="13" class="empty">Subsector landscape research is awaiting comparable company data.</td></tr>';const companies=(DATA.companies||[]).filter(c=>c.competitive_position&&c.competitive_position.score!=null).slice().sort((a,b)=>{const s=String(a.subsector||'').localeCompare(String(b.subsector||''));if(s!==0)return s;return (a.competitive_position.subsector_rank||999)-(b.competitive_position.subsector_rank||999);});document.getElementById('competitive-position-body').innerHTML=companies.map(c=>{const p=c.competitive_position||{},cap=c.capital_efficiency||{},val=c.relative_valuation||{},integrated=c.integrated_research||{};return '<tr data-competitive-ticker="'+esc(c.ticker)+'"><td>'+esc(p.subsector_rank||'—')+' of '+esc(p.subsector_count||'—')+'</td><td><span class="company-link">'+esc(c.name)+' ('+esc(c.ticker)+')</span></td><td>'+esc(c.subsector||'N/A')+'</td><td>'+competitiveProfileHtml(p.profile)+'</td><td><span class="score-pill">'+numberOrNA(p.score,1)+'</span></td><td>'+numberOrNA(c.score,1)+'</td><td>'+numberOrNA(integrated.score,1)+'</td><td class="'+signedClass(c.revenue_growth_pct)+'">'+plainPct(c.revenue_growth_pct)+'</td><td class="'+signedClass(c.fcf_margin_pct)+'">'+plainPct(c.fcf_margin_pct)+'</td><td>'+numberOrNA(cap.score,1)+'</td><td>'+numberOrNA(val.score,1)+'</td></tr>';}).join('')||'<tr><td colspan="11" class="empty">Company competitive-position research is awaiting comparable peer data.</td></tr>';document.querySelectorAll('tr[data-competitive-ticker]').forEach(row=>row.addEventListener('click',()=>renderCompanyDetail(row.dataset.competitiveTicker,true)));const limits=model.limitations||[];document.getElementById('subsector-limitations').innerHTML='<strong>How to read this Phase 12 layer</strong><ul>'+limits.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul><span class="source-note">'+esc(model.method||'')+'</span>';}
function competitivePositionDetailHtml(c){const p=c.competitive_position||{},components=p.components||{};const rows=Object.entries(components).map(([key,value])=>'<tr><td>'+esc(key.replaceAll('_',' '))+'</td><td>'+plainPct(value)+'</td></tr>').join('');return '<h3 style="margin-top:20px">Phase 12 Competitive Position</h3><p class="section-note">'+esc(p.status||'Awaiting peer comparison')+'</p><div class="mini-grid"><div class="mini"><div class="label">Position profile</div><div class="value">'+esc(p.profile||'N/A')+'</div></div><div class="mini"><div class="label">Position score</div><div class="value">'+numberOrNA(p.score,1)+'</div></div><div class="mini"><div class="label">Subsector rank</div><div class="value">'+esc(p.subsector_rank||'N/A')+' of '+esc(p.subsector_count||'N/A')+'</div></div><div class="mini"><div class="label">Components available</div><div class="value">'+esc(p.available_component_count||0)+' of 6</div></div></div><div class="table-wrap" style="margin-top:12px"><table class="peer-table"><thead><tr><th>Peer-relative component</th><th>Percentile</th></tr></thead><tbody>'+rows+'</tbody></table></div><p class="source-note">Percentiles compare only with companies in the same current Stock Digest prototype subsector. This is not a market-share, moat, or investment conclusion.</p>';}
function dailyChangeDetailHtml(c){const d=c.daily_change||{};const messages=(d.messages||[]).map(x=>'<li>'+esc(x)+'</li>').join('')||'<li>'+esc(d.summary||'No prior daily comparison is available.')+'</li>';return '<h3 style="margin-top:20px">Phase 11 Daily Change Monitor</h3><p class="section-note">Compared with '+esc(d.comparison_date||'no prior baseline')+'. '+esc(d.status||'')+'</p><div class="mini-grid"><div class="mini"><div class="label">Alert priority</div><div class="value">'+priorityHtml(d.priority)+'</div></div><div class="mini"><div class="label">Original score change</div><div class="value '+signedClass(d.score_delta)+'">'+changeDelta(d.score_delta)+'</div></div><div class="mini"><div class="label">Rank change</div><div class="value">'+rankChange(d.rank_change)+'</div></div><div class="mini"><div class="label">Integrated evidence change</div><div class="value '+signedClass(d.integrated_evidence_delta)+'">'+changeDelta(d.integrated_evidence_delta)+'</div></div><div class="mini"><div class="label">Likelihood change</div><div class="value '+signedClass(d.likelihood_delta_pct_points)+'">'+changeDelta(d.likelihood_delta_pct_points,' pp')+'</div></div><div class="mini"><div class="label">Observed price move</div><div class="value '+signedClass(d.price_change_pct)+'">'+changeDelta(d.price_change_pct,'%')+'</div></div></div><div class="analysis-box" style="margin-top:12px"><h4>Changes crossing Phase 11 thresholds</h4><ul>'+messages+'</ul></div><p class="source-note">A change alert is a research-review prompt, not a buy, sell, hold, or risk-management instruction.</p>';}
function renderCompanyDetail(ticker,shouldScroll=true){const c=DATA.companies.find(x=>x.ticker===ticker);if(!c)return;selectedTicker=ticker;const components=c.score_components||{};const componentHtml=Object.entries(components).map(([k,v])=>'<div class="component-row"><span>'+esc(componentLabel(k))+'</span><div class="bar"><span style="width:'+(v==null?0:v)+'%"></span></div><strong>'+(v==null?'—':Number(v).toFixed(0))+'</strong></div>').join('');const filings=(c.latest_filings||[]).map(f=>'<li><a target="_blank" rel="noopener" href="'+esc(f.url)+'">'+esc(f.form)+' — '+esc(f.date)+'</a> '+esc(f.description||'')+'</li>').join('')||'<li>No recent filings were retrieved.</li>';const strengths=(c.strengths||[]).map(x=>'<li>'+esc(x)+'</li>').join('');const risks=(c.risks||[]).map(x=>'<li>'+esc(x)+'</li>').join('');const warnings=(c.data_warnings||[]);const warningHtml=warnings.length?'<div class="warning-box"><strong>Missing-data warnings</strong><ul>'+warnings.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul></div>':'<div class="notice" style="margin-top:12px"><strong>Data coverage:</strong> No major standardized field is currently missing from the Phase 3 coverage check.</div>';const peerRows=(c.peer_snapshot||[]).map(p=>'<tr class="'+(p.ticker===c.ticker?'selected-peer':'')+'"><td>'+esc(p.name)+' ('+esc(p.ticker)+')</td><td>'+esc(p.score==null?'N/A':Number(p.score).toFixed(1))+'</td><td>'+pct(p.revenue_growth_pct)+'</td><td>'+pct(p.fcf_margin_pct)+'</td><td>'+pct(p.return_1y_pct)+'</td></tr>').join('');const peerMetrics=(c.peer_metrics||[]).map(m=>'<tr><td>'+esc(m.label)+'</td><td>'+formatPeerValue(m.key,m.company_value)+'</td><td>'+formatPeerValue(m.key,m.peer_median)+'</td><td>'+esc(m.peer_percentile==null?'N/A':Number(m.peer_percentile).toFixed(0)+'th')+'</td></tr>').join('');const qualityClass=c.data_quality==='High'?'quality-high':c.data_quality==='Limited'?'quality-limited':'';const outlook=c.outlook||{};const scenarios=outlook.scenarios||[];const scenarioRows=scenarios.map(s=>{const p=s.projections||[];const y1=p[0]||{},y2=p[1]||{},y3=p[2]||{};return '<tr><td><strong>'+esc(s.name)+'</strong></td><td>'+plainPct(s.annual_revenue_growth_pct)+'</td><td>'+money(y1.revenue)+'</td><td>'+money(y2.revenue)+'</td><td>'+money(y3.revenue)+'</td><td>'+plainPct(s.fcf_margin_pct)+'</td><td class="'+signedClass(y3.free_cash_flow)+'">'+money(y3.free_cash_flow)+'</td></tr>';}).join('');document.getElementById('company-detail').innerHTML='<div class="detail-panel"><div class="eyebrow">'+esc(c.subsector)+' · '+esc(c.market_cap_tier)+'</div><h3>'+esc(c.name)+' ('+esc(c.ticker)+')</h3><p class="summary-text">'+esc(c.automated_summary||'No summary available.')+'</p><div class="mini-grid"><div class="mini"><div class="label">Company score</div><div class="value">'+esc(c.score==null?'N/A':Number(c.score).toFixed(1))+'</div></div><div class="mini"><div class="label">12-mo research likelihood</div><div class="value">'+plainPct(c.outperformance_likelihood_12m_pct)+'</div><div class="subvalue">'+esc(c.likelihood_status||'Not available')+'</div></div><div class="mini"><div class="label">Research outlook</div><div class="value">'+esc(outlook.label||'N/A')+'</div><div class="subvalue">'+esc(outlook.confidence||'N/A')+' scenario confidence</div></div><div class="mini"><div class="label">3-year revenue CAGR</div><div class="value">'+plainPct(outlook.historical_revenue_cagr_3y_pct)+'</div><div class="subvalue">Reported history</div></div><div class="mini"><div class="label">Overall rank</div><div class="value">'+esc(c.overall_rank||'N/A')+'</div></div><div class="mini"><div class="label">Subsector rank</div><div class="value">'+esc(c.subsector_rank||'N/A')+' of '+esc(c.peer_count||'N/A')+'</div></div><div class="mini"><div class="label">Cap-group rank</div><div class="value">'+esc(c.cap_group_rank||'N/A')+' of '+esc(c.cap_group_count||'N/A')+'</div></div><div class="mini"><div class="label">Data coverage</div><div class="value '+qualityClass+'">'+esc(c.data_coverage_pct==null?'N/A':Number(c.data_coverage_pct).toFixed(0)+'%')+'</div><div class="subvalue">'+esc(c.data_quality||'Unknown')+'</div></div><div class="mini"><div class="label">Market cap</div><div class="value">'+money(c.market_cap)+'</div></div><div class="mini"><div class="label">Revenue growth</div><div class="value '+signedClass(c.revenue_growth_pct)+'">'+pct(c.revenue_growth_pct)+'</div></div><div class="mini"><div class="label">FCF margin</div><div class="value '+signedClass(c.fcf_margin_pct)+'">'+pct(c.fcf_margin_pct)+'</div></div><div class="mini"><div class="label">Reported CapEx</div><div class="value">'+money(c.latest_capex)+'</div></div><div class="mini"><div class="label">R&amp;D</div><div class="value">'+money(c.latest_rnd)+'</div></div></div><div class="analysis-grid"><div class="analysis-box"><h4>Measured strengths</h4><ul>'+strengths+'</ul></div><div class="analysis-box"><h4>Measured risks</h4><ul>'+risks+'</ul></div></div>'+warningHtml+integratedDetailHtml(c)+dailyChangeDetailHtml(c)+competitivePositionDetailHtml(c)+'<h3 style="margin-top:18px">10-Year Reported History</h3><div class="metric-buttons" id="metric-buttons">'+['revenue','net_income','free_cash_flow','capex','rnd'].map(m=>'<button data-metric="'+m+'" class="'+(m===companyMetric?'active':'')+'">'+metricTitle(m)+'</button>').join('')+'</div><div class="chart-wrap" style="height:330px"><canvas id="company-history-chart"></canvas></div><h3 style="margin-top:20px">Past–Present–Future Operating Scenarios</h3><p class="section-note">'+esc(outlook.summary||outlook.status||'No operating scenario is available.')+'</p><div class="chart-wrap" style="height:330px"><canvas id="company-outlook-chart"></canvas></div><div class="table-wrap"><table class="peer-table"><thead><tr><th>Scenario</th><th>Annual growth</th><th>Year 1 revenue</th><th>Year 2 revenue</th><th>Year 3 revenue</th><th>FCF margin</th><th>Year 3 FCF</th></tr></thead><tbody>'+scenarioRows+'</tbody></table></div><p class="source-note">Model-generated operating scenarios only. They are not company guidance, analyst consensus estimates, price targets, or recommendations.</p>'+capitalDetailHtml(c)+valuationDetailHtml(c)+filingDetailHtml(c)+'<h3 style="margin-top:20px">Peer comparison</h3><div class="table-wrap"><table class="peer-table"><thead><tr><th>Metric</th><th>Company</th><th>Peer median</th><th>Peer percentile</th></tr></thead><tbody>'+peerMetrics+'</tbody></table></div><h3 style="margin-top:20px">Companies in this subsector</h3><div class="table-wrap"><table class="peer-table"><thead><tr><th>Company</th><th>Score</th><th>Revenue growth</th><th>FCF margin</th><th>1-year return</th></tr></thead><tbody>'+peerRows+'</tbody></table></div></div><div class="detail-panel"><h3>Score components</h3>'+componentHtml+'<h3 style="margin-top:20px">Recent SEC filings</h3><ul class="filings">'+filings+'</ul><p class="source-note">Latest fiscal year: '+esc(c.latest_fiscal_year||'N/A')+' · Market price date: '+esc(c.price_date||'N/A')+' · SEC CIK: '+esc(c.cik||'N/A')+'</p><p class="source-note">Peer percentiles use only the companies currently included in the same prototype subsector. They will become more meaningful as the company universe expands.</p></div>';document.querySelectorAll('#metric-buttons button').forEach(btn=>btn.addEventListener('click',function(){companyMetric=this.dataset.metric;renderCompanyDetail(ticker,false);}));renderCompanyChart(c);renderCompanyOutlookChart(c);if(shouldScroll)document.getElementById('company-detail').scrollIntoView({behavior:'smooth',block:'start'});}

document.querySelectorAll('#range-buttons button').forEach(btn=>btn.addEventListener('click',function(){rangeYears=Number(this.dataset.years);document.querySelectorAll('#range-buttons button').forEach(x=>x.classList.toggle('active',x===this));renderMarketChart();}));
['company-search','subsector-filter','cap-filter'].forEach(id=>document.getElementById(id).addEventListener(id==='company-search'?'input':'change',renderTable));
document.querySelectorAll('th[data-sort]').forEach(th=>th.addEventListener('click',function(){const key=this.dataset.sort;if(sortKey===key)sortDirection=sortDirection==='asc'?'desc':'asc';else{sortKey=key;sortDirection=['name','ticker','subsector','market_cap_tier'].includes(key)?'asc':'desc';}renderTable();}));
fetch('ai_company_data.json?ts='+Date.now()).then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}).then(data=>{DATA=data;document.getElementById('updated-at').textContent='Updated '+(data.generated_at||'unknown')+' · '+(data.companies||[]).length+' companies · '+(data.status||'prototype');renderSummary();renderWeeklyLeaders();renderTrackRecord();renderBacktest();renderLikelihood();renderOutlook();renderCapitalEfficiency();renderValuation();renderFilingEvents();renderIntegratedResearch();renderDailyChanges();renderSubsectorLandscape();populateFilters();renderTable();renderMarketChart();if(DATA.companies.length)renderCompanyDetail(DATA.companies[0].ticker,false);}).catch(err=>{document.getElementById('updated-at').textContent='The AI dataset could not be loaded.';document.getElementById('summary-cards').innerHTML='<div class="notice">Run generate_ai_intelligence.py to create ai_company_data.json. Error: '+esc(err.message)+'</div>';});
})();
</script>
</body>
</html>

'''


def seed_data() -> dict[str, Any]:
    return {
        "schema_version": 12,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "awaiting first Phase 12 live refresh",
        "market_summary": {},
        "market_index": [],
        "weekly_leaders": {"week_start": None, "as_of": None, "status": "Awaiting first refresh", "leaders": []},
        "weekly_snapshots": [],
        "performance_scorecard": {"tracking_started": None, "weeks_recorded": 0, "horizons": [], "recent_weeks": []},
        "historical_backtest": {"status": "Awaiting first Phase 8 live refresh", "tested_months": 0, "top5_horizons": [], "score_band_calibration": [], "limitations": []},
        "likelihood_research": {"status": "Awaiting first Phase 8 live refresh", "bands": [], "limitations": []},
        "outlook_research": {"status": "Awaiting first Phase 8 live refresh", "companies_modeled": 0, "limitations": []},
        "capital_efficiency_research": {"status": "Awaiting first Phase 8 live refresh", "companies_scored": 0, "limitations": []},
        "relative_valuation_research": {"status": "Awaiting first Phase 9 live refresh", "companies_scored": 0, "limitations": []},
        "filing_event_research": {"status": "Awaiting first Phase 9 live refresh", "companies_analyzed": 0, "limitations": []},
        "integrated_research": {"status": "Awaiting first Phase 10 live refresh", "companies_scored": 0, "limitations": []},
        "daily_snapshots": [],
        "daily_change_monitor": {"status": "Awaiting first Phase 11 live refresh", "alerts": [], "limitations": []},
        "subsector_landscape": {"status": "Awaiting first Phase 12 live refresh", "subsectors": [], "limitations": []},
        "companies": [
            {
                **company,
                "market_cap_tier": "Unclassified",
                "score": None,
                "score_components": {},
                "history": [],
                "latest_filings": [],
                "automated_summary": "Run the AI Intelligence update workflow to retrieve live SEC financial facts and market-price history.",
            }
            for company in COMPANIES
        ],
        "errors": [],
        "methodology": {
            "score_weights": {
                "growth": 25,
                "free_cash_flow": 20,
                "financial_strength": 15,
                "profitability": 10,
                "momentum": 20,
                "strategic_investment": 10,
            },
            "free_cash_flow": "Operating cash flow minus cash capital expenditures",
        },
    }


def main() -> None:
    old_data = seed_data()
    if OUTPUT_JSON.exists():
        try:
            old_data = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    old_by_ticker = {c.get("ticker"): c for c in old_data.get("companies", [])}

    session = requests.Session()
    errors: list[str] = []
    try:
        cik_map = load_ticker_cik_map(session)
    except Exception as exc:  # noqa: BLE001
        cik_map = {}
        errors.append(f"SEC ticker-to-CIK lookup failed: {exc}")

    market_data, market_index, price_errors, price_history = build_price_data([c["ticker"] for c in COMPANIES])
    errors.extend(price_errors)

    companies: list[dict[str, Any]] = []
    for metadata in COMPANIES:
        ticker = metadata["ticker"]
        record: dict[str, Any] = dict(metadata)
        cik = cik_map.get(ticker)
        record["cik"] = cik
        if cik:
            cik10 = f"{cik:010d}"
            try:
                facts = fetch_json(session, f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json")
                record.update(build_financial_record(facts))
                record["sec_companyfacts_url"] = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{ticker} Company Facts failed: {exc}")
            try:
                submissions = fetch_json(session, f"https://data.sec.gov/submissions/CIK{cik10}.json")
                record["latest_filings"] = latest_filings(submissions, cik)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{ticker} submissions failed: {exc}")
        else:
            errors.append(f"No SEC CIK mapping found for {ticker}")

        record.update(market_data.get(ticker, {}))
        if record.get("market_cap") is None:
            shares = safe_float(record.get("shares_outstanding"))
            price = safe_float(record.get("latest_price"))
            if shares is not None and price is not None:
                record["market_cap"] = round(shares * price, 2)
        record["market_cap_tier"] = market_cap_tier(safe_float(record.get("market_cap")))
        record["score_components"] = component_scores(record)
        record["score"] = weighted_score(record["score_components"])
        record["automated_summary"] = automated_summary(record)
        companies.append(merge_old_company(old_by_ticker.get(ticker, {}), record))

    ranked = sorted(companies, key=lambda c: (c.get("score") is not None, c.get("score") or -1), reverse=True)
    for rank, company in enumerate(ranked, start=1):
        company["overall_rank"] = rank if company.get("score") is not None else None
    for subsector in sorted({c["subsector"] for c in companies}):
        peer_group = sorted(
            [c for c in companies if c["subsector"] == subsector],
            key=lambda c: (c.get("score") is not None, c.get("score") or -1),
            reverse=True,
        )
        for rank, company in enumerate(peer_group, start=1):
            company["subsector_rank"] = rank if company.get("score") is not None else None

    add_peer_intelligence(companies)

    historical_backtest = build_historical_backtest(ranked, price_history)
    likelihood_observations = historical_backtest.pop("_all_observations", [])
    likelihood_research = build_likelihood_research(likelihood_observations, ranked)
    outlook_research = add_outlook_scenarios(ranked)
    capital_efficiency_research = add_capital_efficiency_research(ranked)
    relative_valuation_research = add_relative_valuation_research(ranked)
    filing_event_research = add_filing_event_research(ranked, price_history)
    integrated_research = add_integrated_research_briefs(ranked)
    subsector_landscape = add_subsector_landscape(ranked)
    daily_snapshots = create_or_preserve_daily_snapshots(old_data, ranked)
    daily_change_monitor = build_daily_change_monitor(daily_snapshots, ranked)
    weekly_snapshots = create_or_preserve_weekly_snapshots(old_data, ranked)
    weekly_leaders = build_live_weekly_leaders(weekly_snapshots, ranked)
    performance_scorecard = build_performance_scorecard(weekly_snapshots, ranked, price_history)

    # Internal point-in-time fact rows are used only by the generator and are not published.
    for company in ranked:
        company.pop("_backtest_facts", None)

    output = {
        "schema_version": 12,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "live Phase 12 subsector leadership and daily change research prototype" if any(c.get("score") is not None for c in companies) else "partial / cached prototype",
        "market_summary": build_market_summary(companies, market_index),
        "market_index": market_index or old_data.get("market_index", []),
        "weekly_leaders": weekly_leaders,
        "weekly_snapshots": weekly_snapshots,
        "performance_scorecard": performance_scorecard,
        "historical_backtest": historical_backtest,
        "likelihood_research": likelihood_research,
        "outlook_research": outlook_research,
        "capital_efficiency_research": capital_efficiency_research,
        "relative_valuation_research": relative_valuation_research,
        "filing_event_research": filing_event_research,
        "integrated_research": integrated_research,
        "daily_snapshots": daily_snapshots,
        "daily_change_monitor": daily_change_monitor,
        "subsector_landscape": subsector_landscape,
        "companies": ranked,
        "errors": errors,
        "methodology": {
            "score_weights": {
                "growth": 25,
                "free_cash_flow": 20,
                "financial_strength": 15,
                "profitability": 10,
                "momentum": 20,
                "strategic_investment": 10,
            },
            "free_cash_flow": "Operating cash flow minus cash capital expenditures",
            "important_limits": [
                "The score is not a probability or investment recommendation.",
                "Reported total CapEx is not automatically AI-only CapEx.",
                "XBRL tags and fiscal calendars can differ across companies.",
                "Historical-price licensing must be reviewed before commercial redistribution.",
                "Peer percentiles are based only on the companies currently included in each prototype subsector.",
                "Strengths and risks are deterministic summaries of available metrics, not qualitative due diligence.",
                "The Phase 3 performance record starts only when the first Phase 3 snapshot is created; it does not backfill hypothetical prior rankings.",
                "The peer benchmark is equal-weighted within the small prototype subsector universe and is not an investable published sector index.",
                "The Phase 4 historical test uses the current prototype universe and therefore has survivorship and selection bias.",
                "Historical score-band rates and Phase 5 likelihood estimates are retrospective research diagnostics, not guarantees or investment recommendations.",
                "Phase 7 combined CapEx-plus-R&D figures are analytical totals, not GAAP subtotals or AI-only investment measures.",
                "Phase 8 valuation ratios use latest annual reported financial facts and current prototype market capitalization; they are relative research, not fair-value estimates.",
                "Phase 8 remains separate from the original score so the existing weekly track record and historical backtest are not silently rewritten.",
                "Phase 9 filing reactions are observational and can reflect market-wide or unrelated news; they are not causation findings or forecasts.",
                "Phase 10 is an automated synthesis of existing research layers and does not replace qualitative due diligence or create an investment recommendation.",
                "Phase 11 alerts describe changes between preserved daily research snapshots and are not trade instructions or proof that a change will persist.",
                "Phase 12 subsector and competitive-position scores are based on the small current prototype universe and do not measure market share, moat, or private competition.",
            ],
            "phase_2_features": [
                "Peer medians and percentiles",
                "Market-cap group rank",
                "Data coverage and missing-data warnings",
                "Deterministic strengths and risks",
            ],
            "phase_3_features": [
                "Permanent immutable weekly ranking snapshots",
                "Official rank versus daily live rank",
                "Return since selection versus equal-weighted prototype subsector peers",
                "Fixed 30-day, 3-month, 6-month, and 12-month scorecard",
                "Complete retention of underperforming as well as outperforming weeks",
            ],
            "phase_4_features": [
                "Monthly point-in-time historical score reconstruction",
                "Top-five 3-month, 6-month, and 12-month retrospective tests",
                "Comparison with subsector peers and the Nasdaq-100",
                "Score-band historical outperformance calibration research",
                "Explicit survivorship-bias, overlap, and execution limitations",
            ],
            "phase_5_features": [
                "Chronological 70% calibration and 30% validation split",
                "Beta-smoothed 12-month peer-outperformance research estimates",
                "Minimum sample-size gate before displaying an estimate",
                "Research uncertainty ranges and validation diagnostics",
                "Company and weekly-leader likelihood display with explicit limitations",
                "Three-year conservative, base, and optimistic operating scenarios with published assumptions",
            ],
            "phase_6_features": [
                "Three-year conservative, base, and optimistic operating scenarios",
                "Reported-history and peer-growth scenario inputs",
                "Past-present-future company charts with explicit model labels",
            ],
            "phase_7_features": [
                "Peer-relative capital-efficiency score",
                "Combined reported CapEx and R&D intensity",
                "Operating-cash-flow coverage of CapEx",
                "Net-cash financial-durability comparison",
                "Capital profile labels and peer percentiles",
            ],
            "phase_8_features": [
                "Peer-relative price-to-sales and enterprise-value-to-sales comparisons",
                "Standardized free-cash-flow and earnings yields",
                "Growth-adjusted price-to-sales research",
                "Valuation profile labels and subsector percentiles",
                "Separate model version that preserves the original ranking track record",
            ],
            "phase_9_features": [
                "SEC form and 8-K item-code event classification",
                "Observed first-close and five-trading-day filing reactions",
                "Ninety-day disclosure activity and attention levels",
                "Company filing-reaction profiles and separate reaction ranking",
                "No change to the original company score or weekly track record",
            ],
            "phase_10_features": [
                "Integrated evidence-balance score kept separate from the original ranking",
                "Past, present, and future company research narratives",
                "Supporting evidence, counter-evidence, and monitoring checklist",
                "Confidence gate based on data coverage and available research components",
                "No change to official weekly snapshots or historical backtests",
            ],
            "phase_11_features": [
                "One preserved research-state snapshot per New York calendar date",
                "Daily comparison with the most recent prior successful snapshot",
                "Published thresholds for score, rank, likelihood, price, profile, coverage, and filing changes",
                "High and moderate research-review priorities",
                "No change to the original company score, weekly rankings, backtest, or calibration",
            ],
            "phase_12_features": [
                "AI subsector research-strength ranking",
                "Subsector market breadth, growth, free-cash-flow, and concentration summaries",
                "Original-score, integrated-evidence, growth, capital-efficiency, and relative-valuation leaders",
                "Within-subsector company competitive-position scores and percentiles",
                "No change to the original company score, official weekly rankings, snapshots, backtests, or likelihood calibration",
            ],
        },
    }

    OUTPUT_JSON.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    OUTPUT_HTML.write_text(HTML_TEMPLATE, encoding="utf-8")
    print(f"Created {OUTPUT_JSON} and {OUTPUT_HTML}")
    if errors:
        print(f"Completed with {len(errors)} warning(s). See the errors array in {OUTPUT_JSON}.")


if __name__ == "__main__":
    main()
