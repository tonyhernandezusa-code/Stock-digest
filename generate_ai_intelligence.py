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
adds a preliminary point-in-time historical backtest and score-band calibration lab.
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
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    documents = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])
    items = []
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
        items.append(
            {
                "form": form,
                "date": date,
                "description": descriptions[index] if index < len(descriptions) else "",
                "url": url,
            }
        )
        if len(items) >= 4:
            break
    return items


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
*{box-sizing:border-box}body{margin:0;padding:24px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text)}a{color:var(--accent)}.container{max-width:1250px;margin:0 auto}.topbar{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:18px;flex-wrap:wrap}.nav a{font-size:14px;font-weight:650;text-decoration:none;margin-right:16px}.theme-btn{border:1px solid var(--border);border-radius:20px;background:var(--card);color:var(--text);padding:8px 14px;cursor:pointer}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--accent);font-weight:800}.title-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}h1{font-size:28px;margin:5px 0}.premium{background:#f4c95d;color:#342800;font-size:11px;font-weight:800;border-radius:999px;padding:5px 9px}.timestamp{font-size:13px;color:var(--secondary);margin:0 0 18px}.notice{border:1px solid var(--border);background:var(--card);border-radius:10px;padding:12px 14px;color:var(--secondary);font-size:12px;line-height:1.5;margin-bottom:16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px}.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px;box-shadow:var(--shadow)}.label{font-size:11px;color:var(--secondary);text-transform:uppercase;letter-spacing:.04em}.value{font-size:22px;font-weight:750;margin-top:5px}.subvalue{font-size:11px;color:var(--muted);margin-top:4px}.positive{color:var(--positive)}.negative{color:var(--negative)}h2{font-size:19px;margin:28px 0 10px}.section-note{font-size:12px;color:var(--secondary);margin:0 0 12px;line-height:1.5}.chart-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px;box-shadow:var(--shadow)}.chart-wrap{height:390px}.range-buttons,.metric-buttons{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:10px}.range-buttons button,.metric-buttons button,.filter-row select,.filter-row input{border:1px solid var(--border);background:var(--card);color:var(--text);border-radius:7px;padding:7px 10px;font-size:12px}.range-buttons button,.metric-buttons button{cursor:pointer}.range-buttons button.active,.metric-buttons button.active{background:var(--accent);color:#fff;border-color:var(--accent)}.filter-row{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:10px}.filter-row input{min-width:230px}.table-wrap{overflow:auto;border:1px solid var(--border);border-radius:12px;background:var(--card)}table{border-collapse:collapse;width:100%;min-width:1040px}th{position:sticky;top:0;background:var(--header);color:var(--secondary);font-size:11px;text-align:left;padding:9px;white-space:nowrap;cursor:pointer}td{border-top:1px solid var(--border);padding:9px;font-size:12px;white-space:nowrap}tr.company-row{cursor:pointer}tr.company-row:hover{background:var(--header)}.score-pill{display:inline-block;min-width:48px;text-align:center;padding:4px 7px;border-radius:999px;background:var(--header);font-weight:750}.detail{display:grid;grid-template-columns:minmax(0,2fr) minmax(280px,1fr);gap:14px}.detail-panel{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:15px;box-shadow:var(--shadow)}.detail h3{margin:0 0 5px}.summary-text{font-size:13px;line-height:1.6;color:var(--secondary)}.mini-grid{display:grid;grid-template-columns:repeat(2,minmax(120px,1fr));gap:8px}.mini{border:1px solid var(--border);border-radius:9px;padding:10px}.mini .value{font-size:16px}.component-row{display:grid;grid-template-columns:135px 1fr 42px;align-items:center;gap:8px;margin:9px 0;font-size:12px}.bar{height:8px;border-radius:6px;background:var(--header);overflow:hidden}.bar span{display:block;height:100%;background:var(--accent)}.filings{padding-left:18px;margin:8px 0}.filings li{margin:7px 0;font-size:12px}.source-note{font-size:11px;color:var(--muted);line-height:1.5}.empty{padding:22px;text-align:center;color:var(--secondary)}.leaders-table{min-width:980px}.leaders-table td{white-space:normal;vertical-align:top}.leaders-table .company-link{cursor:pointer;color:var(--accent);font-weight:750}.tag{display:inline-block;border:1px solid var(--border);background:var(--header);border-radius:999px;padding:3px 7px;font-size:10px;font-weight:700}.analysis-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}.analysis-box{border:1px solid var(--border);border-radius:10px;padding:12px}.analysis-box h4{margin:0 0 8px;font-size:13px}.analysis-box ul{margin:0;padding-left:18px;font-size:12px;line-height:1.5}.warning-box{border:1px solid #d9a441;background:rgba(217,164,65,.08);border-radius:10px;padding:11px;margin-top:12px;font-size:12px;line-height:1.5}.peer-table{min-width:650px}.peer-table th{cursor:default}.peer-table td{white-space:nowrap}.selected-peer{font-weight:750;background:var(--header)}.quality-high{color:var(--positive)}.quality-limited{color:var(--negative)}.rank-up{color:var(--positive);font-weight:750}.rank-down{color:var(--negative);font-weight:750}.rank-flat{color:var(--secondary)}.backtest-note{border-left:4px solid var(--accent)}.calibration-table{min-width:900px}.calibration-table th{cursor:default}@media(max-width:800px){body{padding:14px}.detail{grid-template-columns:1fr}.analysis-grid{grid-template-columns:1fr}.chart-wrap{height:320px}}
</style>
</head>
<body>
<div class="container">
  <div class="topbar">
    <div class="nav"><a href="index.html">Stocks &amp; Rates</a><a href="investment-map.html">Investment Map</a><a href="realestate.html">Real Estate</a></div>
    <button class="theme-btn" id="theme-toggle">◐ Dark Mode</button>
  </div>

  <div class="eyebrow">Stock Digest Research</div>
  <div class="title-row"><h1>AI Market Intelligence</h1><span class="premium">PHASE 4 PREMIUM PREVIEW</span></div>
  <p class="timestamp" id="updated-at">Loading the latest AI company dataset...</p>
  <div class="notice"><strong>Research framework—not investment advice.</strong> The company score organizes reported financial facts and market momentum using the published methodology below. Phase 4 retains the permanent weekly record and adds a preliminary point-in-time historical backtest. Historical outperformance rates are research diagnostics—not probabilities, price targets, or buy/sell recommendations. SEC figures can differ across issuers because companies use different permitted XBRL tags and fiscal calendars.</div>

  <div class="grid" id="summary-cards"></div>

  <h2>Official AI Weekly Leaders</h2>
  <p class="section-note" id="leaders-note">The official list is frozen once each week; prices, live rank, and performance update daily.</p>
  <div class="table-wrap"><table class="leaders-table"><thead><tr>
    <th>Official</th><th>Live</th><th>Change</th><th>Company</th><th>Official score</th><th>Entry price</th><th>Return</th><th>Peer return</th><th>Relative</th>
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
    <th data-sort="overall_rank">Rank</th><th data-sort="ticker">Ticker</th><th data-sort="name">Company</th><th data-sort="subsector">Subsector</th><th data-sort="market_cap_tier">Cap group</th><th data-sort="score">Score</th><th data-sort="revenue_growth_pct">Revenue growth</th><th data-sort="latest_free_cash_flow">Free cash flow</th><th data-sort="latest_capex">CapEx</th><th data-sort="return_1y_pct">1-year return</th>
  </tr></thead><tbody id="ranking-body"></tbody></table></div>

  <h2>Company Intelligence Snapshot</h2>
  <div class="detail" id="company-detail"><div class="detail-panel empty">Select a company from the ranking table.</div></div>

  <h2>How the preliminary score works</h2>
  <div class="notice">Revenue growth 25% · standardized free-cash-flow strength 20% · financial strength 15% · profitability 10% · market momentum 20% · R&amp;D and capital-investment intensity 10%. Missing inputs are excluded and the remaining weights are renormalized. The score ranks financial and market characteristics; it does not estimate the chance of a positive return. A separately backtested and calibrated model would be required before publishing any probability.</div>
  <p class="source-note">Financial facts: SEC EDGAR Company Facts API. Recent filings: SEC Submissions API. Historical prices: Yahoo Finance through yfinance for prototype development. Stock Digest standardized free cash flow equals operating cash flow minus cash capital expenditures. Total company CapEx is not automatically labeled AI-only CapEx.</p>
</div>
<script>
(function(){
'use strict';
let DATA=null, marketChart=null, companyChart=null, selectedTicker=null, rangeYears=5, companyMetric='revenue';
let sortKey='score', sortDirection='desc';
const moneyFmt=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',notation:'compact',maximumFractionDigits:1});
const numFmt=new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:1});
function esc(value){return String(value==null?'':value).replace(/[&<>'"]/g,function(ch){return {'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch];});}
function money(value){return value==null?'N/A':moneyFmt.format(value);}
function pct(value){if(value==null)return 'N/A';return (value>0?'+':'')+Number(value).toFixed(1)+'%';}
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
function renderWeeklyLeaders(){const weekly=DATA.weekly_leaders||{},leaders=weekly.leaders||[];document.getElementById('leaders-note').textContent=(weekly.status||'Official weekly research ranking')+(weekly.week_start?' · Week beginning '+weekly.week_start:'')+(weekly.captured_at?' · Captured '+weekly.captured_at:'')+'. It is not a buy list or recommendation.';const body=document.getElementById('leaders-body');if(!leaders.length){body.innerHTML='<tr><td colspan="9" class="empty">The first official weekly snapshot will be recorded during the next successful refresh.</td></tr>';return;}body.innerHTML=leaders.map(item=>'<tr data-leader-ticker="'+esc(item.ticker)+'"><td><strong>'+esc(item.official_rank||'—')+'</strong></td><td>'+esc(item.live_rank||'—')+'</td><td>'+rankChange(item.rank_change)+'</td><td><span class="company-link">'+esc(item.name)+' ('+esc(item.ticker)+')</span><br><span class="source-note">'+esc(item.subsector||'')+'</span></td><td><span class="score-pill">'+esc(item.official_score==null?'N/A':Number(item.official_score).toFixed(1))+'</span></td><td>'+money(item.entry_price)+'</td><td class="'+signedClass(item.return_since_selection_pct)+'">'+pct(item.return_since_selection_pct)+'</td><td class="'+signedClass(item.peer_return_since_selection_pct)+'">'+pct(item.peer_return_since_selection_pct)+'</td><td class="'+signedClass(item.relative_return_pct)+'"><strong>'+pct(item.relative_return_pct)+'</strong></td></tr>').join('');body.querySelectorAll('tr[data-leader-ticker]').forEach(row=>row.addEventListener('click',()=>renderCompanyDetail(row.dataset.leaderTicker,true)));}
function renderTrackRecord(){const track=DATA.performance_scorecard||{},horizons=track.horizons||[],weeks=track.recent_weeks||[];const h30=horizons.find(x=>x.days===30)||{},h90=horizons.find(x=>x.days===90)||{},h365=horizons.find(x=>x.days===365)||{};const cards=[['Tracking started',track.tracking_started?String(track.tracking_started).slice(0,10):'Awaiting first snapshot','Permanent history begins in Phase 3'],['Weeks recorded',track.weeks_recorded||0,'Official snapshots retained'],['30-day hit rate',h30.hit_rate_pct==null?'Awaiting history':pct(h30.hit_rate_pct),(h30.evaluated_selections||0)+' selections evaluated'],['3-month hit rate',h90.hit_rate_pct==null?'Awaiting history':pct(h90.hit_rate_pct),(h90.evaluated_selections||0)+' selections evaluated'],['12-month hit rate',h365.hit_rate_pct==null?'Awaiting history':pct(h365.hit_rate_pct),(h365.evaluated_selections||0)+' selections evaluated']];document.getElementById('track-record-cards').innerHTML=cards.map(c=>'<div class="card"><div class="label">'+esc(c[0])+'</div><div class="value">'+esc(c[1])+'</div><div class="subvalue">'+esc(c[2])+'</div></div>').join('');document.getElementById('track-record-body').innerHTML=horizons.map(h=>'<tr><td><strong>'+esc(h.label)+'</strong></td><td>'+esc(h.evaluated_selections||0)+'</td><td>'+esc(h.outperformed_count||0)+'</td><td>'+pct(h.hit_rate_pct)+'</td><td class="'+signedClass(h.average_selection_return_pct)+'">'+pct(h.average_selection_return_pct)+'</td><td class="'+signedClass(h.average_peer_return_pct)+'">'+pct(h.average_peer_return_pct)+'</td><td class="'+signedClass(h.average_excess_return_pct)+'"><strong>'+pct(h.average_excess_return_pct)+'</strong></td></tr>').join('')||'<tr><td colspan="7" class="empty">No fixed-horizon results are available yet.</td></tr>';document.getElementById('snapshot-history-body').innerHTML=[...weeks].reverse().map(w=>'<tr><td>'+esc(w.week_start||'N/A')+'</td><td>'+esc(w.top_company||'N/A')+'</td><td>'+esc(w.selection_count||0)+'</td><td class="'+signedClass(w.average_return_to_date_pct)+'">'+pct(w.average_return_to_date_pct)+'</td><td class="'+signedClass(w.average_excess_to_date_pct)+'">'+pct(w.average_excess_to_date_pct)+'</td></tr>').join('')||'<tr><td colspan="5" class="empty">The first official weekly snapshot will appear after the next refresh.</td></tr>';}

function renderBacktest(){const b=DATA.historical_backtest||{},horizons=b.top5_horizons||[],bands=b.score_band_calibration||[];const cards=[['Backtest period',b.period_start&&b.period_end?b.period_start+' to '+b.period_end:'Awaiting live history','Monthly point-in-time tests'],['Months tested',b.tested_months||0,b.rebalance_frequency||'Monthly'],['Prototype universe',b.current_universe_size||0,'Current companies only'],['Selected each month',b.selected_each_month||0,'Top-ranked historical scores'],['Calibration status',b.calibration_readiness||'Awaiting sample','Not a published probability']];document.getElementById('backtest-cards').innerHTML=cards.map(c=>'<div class="card"><div class="label">'+esc(c[0])+'</div><div class="value">'+esc(c[1])+'</div><div class="subvalue">'+esc(c[2])+'</div></div>').join('');document.getElementById('backtest-horizon-body').innerHTML=horizons.map(h=>'<tr><td><strong>'+esc(h.label)+'</strong></td><td>'+esc(h.selection_observations||0)+'</td><td>'+pct(h.peer_outperformance_rate_pct)+'</td><td>'+pct(h.nasdaq100_outperformance_rate_pct)+'</td><td class="'+signedClass(h.average_selection_return_pct)+'">'+pct(h.average_selection_return_pct)+'</td><td class="'+signedClass(h.average_excess_peer_pct)+'"><strong>'+pct(h.average_excess_peer_pct)+'</strong></td><td class="'+signedClass(h.average_excess_nasdaq100_pct)+'">'+pct(h.average_excess_nasdaq100_pct)+'</td></tr>').join('')||'<tr><td colspan="7" class="empty">The historical test could not be produced from the available data.</td></tr>';document.getElementById('backtest-band-body').innerHTML=bands.map(row=>'<tr><td><strong>'+esc(row.score_band)+'</strong></td><td>'+esc(row.horizon)+'</td><td>'+esc(row.observations||0)+'</td><td>'+pct(row.historical_peer_outperformance_rate_pct)+'</td><td class="'+signedClass(row.average_return_pct)+'">'+pct(row.average_return_pct)+'</td><td class="'+signedClass(row.average_excess_peer_pct)+'">'+pct(row.average_excess_peer_pct)+'</td></tr>').join('')||'<tr><td colspan="6" class="empty">No score-band observations are available.</td></tr>';const limits=b.limitations||[];document.getElementById('backtest-limitations').innerHTML='<strong>Important backtest limits</strong><ul>'+limits.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul><span class="source-note">'+esc(b.fundamental_policy||'')+'</span>';}

function populateFilters(){const subs=[...new Set(DATA.companies.map(c=>c.subsector))].sort();const caps=[...new Set(DATA.companies.map(c=>c.market_cap_tier))].sort();document.getElementById('subsector-filter').innerHTML='<option value="">All subsectors</option>'+subs.map(v=>'<option>'+esc(v)+'</option>').join('');document.getElementById('cap-filter').innerHTML='<option value="">All market-cap groups</option>'+caps.map(v=>'<option>'+esc(v)+'</option>').join('');}
function compare(a,b){let av=a[sortKey],bv=b[sortKey];if(av==null)av=sortDirection==='asc'?Infinity:-Infinity;if(bv==null)bv=sortDirection==='asc'?Infinity:-Infinity;if(typeof av==='string')return sortDirection==='asc'?av.localeCompare(bv):bv.localeCompare(av);return sortDirection==='asc'?av-bv:bv-av;}
function filteredCompanies(){const q=document.getElementById('company-search').value.trim().toLowerCase();const sub=document.getElementById('subsector-filter').value;const cap=document.getElementById('cap-filter').value;return DATA.companies.filter(c=>(!q||(c.name+' '+c.ticker).toLowerCase().includes(q))&&(!sub||c.subsector===sub)&&(!cap||c.market_cap_tier===cap)).sort(compare);}
function renderTable(){const rows=filteredCompanies();const body=document.getElementById('ranking-body');if(!rows.length){body.innerHTML='<tr><td colspan="10" class="empty">No companies match the selected filters.</td></tr>';return;}body.innerHTML=rows.map(c=>'<tr class="company-row" data-ticker="'+esc(c.ticker)+'"><td>'+esc(c.overall_rank||'—')+'</td><td><strong>'+esc(c.ticker)+'</strong></td><td>'+esc(c.name)+'</td><td>'+esc(c.subsector)+'</td><td>'+esc(c.market_cap_tier)+'</td><td><span class="score-pill">'+esc(c.score==null?'N/A':Number(c.score).toFixed(1))+'</span></td><td class="'+signedClass(c.revenue_growth_pct)+'">'+pct(c.revenue_growth_pct)+'</td><td class="'+signedClass(c.latest_free_cash_flow)+'">'+money(c.latest_free_cash_flow)+'</td><td>'+money(c.latest_capex)+'</td><td class="'+signedClass(c.return_1y_pct)+'">'+pct(c.return_1y_pct)+'</td></tr>').join('');body.querySelectorAll('tr[data-ticker]').forEach(row=>row.addEventListener('click',()=>renderCompanyDetail(row.dataset.ticker,true)));}
function metricTitle(metric){return {revenue:'Revenue',net_income:'Net income',free_cash_flow:'Free cash flow',capex:'Capital expenditures',rnd:'Research & development'}[metric]||metric;}
function renderCompanyChart(company){const history=(company.history||[]).filter(r=>r[companyMetric]!=null);const c=chartColors();if(companyChart)companyChart.destroy();companyChart=new Chart(document.getElementById('company-history-chart'),{type:'line',data:{labels:history.map(r=>r.year),datasets:[{label:metricTitle(companyMetric),data:history.map(r=>r[companyMetric]),borderColor:c.ai,backgroundColor:'rgba(31,119,180,.12)',fill:true,tension:.18,pointRadius:3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:c.text}},tooltip:{callbacks:{label:ctx=>metricTitle(companyMetric)+': '+money(ctx.raw)}}},scales:{x:{ticks:{color:c.text},grid:{color:c.grid}},y:{ticks:{color:c.text,callback:v=>numFmt.format(v)},grid:{color:c.grid}}}}});}
function renderCompanyDetail(ticker,shouldScroll=true){const c=DATA.companies.find(x=>x.ticker===ticker);if(!c)return;selectedTicker=ticker;const components=c.score_components||{};const componentHtml=Object.entries(components).map(([k,v])=>'<div class="component-row"><span>'+esc(componentLabel(k))+'</span><div class="bar"><span style="width:'+(v==null?0:v)+'%"></span></div><strong>'+(v==null?'—':Number(v).toFixed(0))+'</strong></div>').join('');const filings=(c.latest_filings||[]).map(f=>'<li><a target="_blank" rel="noopener" href="'+esc(f.url)+'">'+esc(f.form)+' — '+esc(f.date)+'</a> '+esc(f.description||'')+'</li>').join('')||'<li>No recent filings were retrieved.</li>';const strengths=(c.strengths||[]).map(x=>'<li>'+esc(x)+'</li>').join('');const risks=(c.risks||[]).map(x=>'<li>'+esc(x)+'</li>').join('');const warnings=(c.data_warnings||[]);const warningHtml=warnings.length?'<div class="warning-box"><strong>Missing-data warnings</strong><ul>'+warnings.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul></div>':'<div class="notice" style="margin-top:12px"><strong>Data coverage:</strong> No major standardized field is currently missing from the Phase 3 coverage check.</div>';const peerRows=(c.peer_snapshot||[]).map(p=>'<tr class="'+(p.ticker===c.ticker?'selected-peer':'')+'"><td>'+esc(p.name)+' ('+esc(p.ticker)+')</td><td>'+esc(p.score==null?'N/A':Number(p.score).toFixed(1))+'</td><td>'+pct(p.revenue_growth_pct)+'</td><td>'+pct(p.fcf_margin_pct)+'</td><td>'+pct(p.return_1y_pct)+'</td></tr>').join('');const peerMetrics=(c.peer_metrics||[]).map(m=>'<tr><td>'+esc(m.label)+'</td><td>'+formatPeerValue(m.key,m.company_value)+'</td><td>'+formatPeerValue(m.key,m.peer_median)+'</td><td>'+esc(m.peer_percentile==null?'N/A':Number(m.peer_percentile).toFixed(0)+'th')+'</td></tr>').join('');const qualityClass=c.data_quality==='High'?'quality-high':c.data_quality==='Limited'?'quality-limited':'';document.getElementById('company-detail').innerHTML='<div class="detail-panel"><div class="eyebrow">'+esc(c.subsector)+' · '+esc(c.market_cap_tier)+'</div><h3>'+esc(c.name)+' ('+esc(c.ticker)+')</h3><p class="summary-text">'+esc(c.automated_summary||'No summary available.')+'</p><div class="mini-grid"><div class="mini"><div class="label">Company score</div><div class="value">'+esc(c.score==null?'N/A':Number(c.score).toFixed(1))+'</div></div><div class="mini"><div class="label">Overall rank</div><div class="value">'+esc(c.overall_rank||'N/A')+'</div></div><div class="mini"><div class="label">Subsector rank</div><div class="value">'+esc(c.subsector_rank||'N/A')+' of '+esc(c.peer_count||'N/A')+'</div></div><div class="mini"><div class="label">Cap-group rank</div><div class="value">'+esc(c.cap_group_rank||'N/A')+' of '+esc(c.cap_group_count||'N/A')+'</div></div><div class="mini"><div class="label">Data coverage</div><div class="value '+qualityClass+'">'+esc(c.data_coverage_pct==null?'N/A':Number(c.data_coverage_pct).toFixed(0)+'%')+'</div><div class="subvalue">'+esc(c.data_quality||'Unknown')+'</div></div><div class="mini"><div class="label">Market cap</div><div class="value">'+money(c.market_cap)+'</div></div><div class="mini"><div class="label">Revenue growth</div><div class="value '+signedClass(c.revenue_growth_pct)+'">'+pct(c.revenue_growth_pct)+'</div></div><div class="mini"><div class="label">FCF margin</div><div class="value '+signedClass(c.fcf_margin_pct)+'">'+pct(c.fcf_margin_pct)+'</div></div><div class="mini"><div class="label">Reported CapEx</div><div class="value">'+money(c.latest_capex)+'</div></div><div class="mini"><div class="label">R&amp;D</div><div class="value">'+money(c.latest_rnd)+'</div></div></div><div class="analysis-grid"><div class="analysis-box"><h4>Measured strengths</h4><ul>'+strengths+'</ul></div><div class="analysis-box"><h4>Measured risks</h4><ul>'+risks+'</ul></div></div>'+warningHtml+'<h3 style="margin-top:18px">10-Year Reported History</h3><div class="metric-buttons" id="metric-buttons">'+['revenue','net_income','free_cash_flow','capex','rnd'].map(m=>'<button data-metric="'+m+'" class="'+(m===companyMetric?'active':'')+'">'+metricTitle(m)+'</button>').join('')+'</div><div class="chart-wrap" style="height:330px"><canvas id="company-history-chart"></canvas></div><h3 style="margin-top:20px">Peer comparison</h3><div class="table-wrap"><table class="peer-table"><thead><tr><th>Metric</th><th>Company</th><th>Peer median</th><th>Peer percentile</th></tr></thead><tbody>'+peerMetrics+'</tbody></table></div><h3 style="margin-top:20px">Companies in this subsector</h3><div class="table-wrap"><table class="peer-table"><thead><tr><th>Company</th><th>Score</th><th>Revenue growth</th><th>FCF margin</th><th>1-year return</th></tr></thead><tbody>'+peerRows+'</tbody></table></div></div><div class="detail-panel"><h3>Score components</h3>'+componentHtml+'<h3 style="margin-top:20px">Recent SEC filings</h3><ul class="filings">'+filings+'</ul><p class="source-note">Latest fiscal year: '+esc(c.latest_fiscal_year||'N/A')+' · Market price date: '+esc(c.price_date||'N/A')+' · SEC CIK: '+esc(c.cik||'N/A')+'</p><p class="source-note">Peer percentiles use only the companies currently included in the same prototype subsector. They will become more meaningful as the company universe expands.</p></div>';document.querySelectorAll('#metric-buttons button').forEach(btn=>btn.addEventListener('click',function(){companyMetric=this.dataset.metric;renderCompanyDetail(ticker,false);}));renderCompanyChart(c);if(shouldScroll)document.getElementById('company-detail').scrollIntoView({behavior:'smooth',block:'start'});}

document.querySelectorAll('#range-buttons button').forEach(btn=>btn.addEventListener('click',function(){rangeYears=Number(this.dataset.years);document.querySelectorAll('#range-buttons button').forEach(x=>x.classList.toggle('active',x===this));renderMarketChart();}));
['company-search','subsector-filter','cap-filter'].forEach(id=>document.getElementById(id).addEventListener(id==='company-search'?'input':'change',renderTable));
document.querySelectorAll('th[data-sort]').forEach(th=>th.addEventListener('click',function(){const key=this.dataset.sort;if(sortKey===key)sortDirection=sortDirection==='asc'?'desc':'asc';else{sortKey=key;sortDirection=['name','ticker','subsector','market_cap_tier'].includes(key)?'asc':'desc';}renderTable();}));
fetch('ai_company_data.json?ts='+Date.now()).then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}).then(data=>{DATA=data;document.getElementById('updated-at').textContent='Updated '+(data.generated_at||'unknown')+' · '+(data.companies||[]).length+' companies · '+(data.status||'prototype');renderSummary();renderWeeklyLeaders();renderTrackRecord();renderBacktest();populateFilters();renderTable();renderMarketChart();if(DATA.companies.length)renderCompanyDetail(DATA.companies[0].ticker,false);}).catch(err=>{document.getElementById('updated-at').textContent='The AI dataset could not be loaded.';document.getElementById('summary-cards').innerHTML='<div class="notice">Run generate_ai_intelligence.py to create ai_company_data.json. Error: '+esc(err.message)+'</div>';});
})();
</script>
</body>
</html>

'''


def seed_data() -> dict[str, Any]:
    return {
        "schema_version": 4,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "awaiting first live refresh",
        "market_summary": {},
        "market_index": [],
        "weekly_leaders": {"week_start": None, "as_of": None, "status": "Awaiting first refresh", "leaders": []},
        "weekly_snapshots": [],
        "performance_scorecard": {"tracking_started": None, "weeks_recorded": 0, "horizons": [], "recent_weeks": []},
        "historical_backtest": {"status": "Awaiting first Phase 4 live refresh", "tested_months": 0, "top5_horizons": [], "score_band_calibration": [], "limitations": []},
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

    weekly_snapshots = create_or_preserve_weekly_snapshots(old_data, ranked)
    weekly_leaders = build_live_weekly_leaders(weekly_snapshots, ranked)
    performance_scorecard = build_performance_scorecard(weekly_snapshots, ranked, price_history)
    historical_backtest = build_historical_backtest(ranked, price_history)

    # Internal point-in-time fact rows are used only by the generator and are not published.
    for company in ranked:
        company.pop("_backtest_facts", None)

    output = {
        "schema_version": 4,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "live Phase 4 backtest prototype" if any(c.get("score") is not None for c in companies) else "partial / cached prototype",
        "market_summary": build_market_summary(companies, market_index),
        "market_index": market_index or old_data.get("market_index", []),
        "weekly_leaders": weekly_leaders,
        "weekly_snapshots": weekly_snapshots,
        "performance_scorecard": performance_scorecard,
        "historical_backtest": historical_backtest,
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
                "Historical score-band rates are retrospective diagnostics, not calibrated probabilities.",
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
        },
    }

    OUTPUT_JSON.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    OUTPUT_HTML.write_text(HTML_TEMPLATE, encoding="utf-8")
    print(f"Created {OUTPUT_JSON} and {OUTPUT_HTML}")
    if errors:
        print(f"Completed with {len(errors)} warning(s). See the errors array in {OUTPUT_JSON}.")


if __name__ == "__main__":
    main()
