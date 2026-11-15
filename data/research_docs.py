"""Research documents finder (BE-5, D-079): concall transcripts and results filings for any NSE ticker.

Both come from the NSE corporate-announcements API (D-020 = A), i.e. the company's own filings:
{primary sources}. One request covers ~18 months, enough for the last 5 quarters.
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import config
from data import filings as filings_mod
from data.clock import ist_now
from data.symbols import resolve
from engine.classifier import classify


def quarter_end_before(day: date) -> date:
    """The last quarter end (31 Mar / 30 Jun / 30 Sep / 31 Dec) strictly before `day`."""
    ends = [date(day.year - 1, 12, 31), date(day.year, 3, 31), date(day.year, 6, 30),
            date(day.year, 9, 30), date(day.year, 12, 31)]
    return max(e for e in ends if e < day)


def is_transcript(f: dict) -> bool:
    return classify(f) == "earnings_call" and "transcript" in (f.get("title") or "").lower()


def pick_documents(rows: list[dict], n_quarters: int = config.RESEARCH_QUARTERS) -> dict:
    """From parsed filings (newest first), keep one transcript and one results filing per quarter.

    A results filing is a filing classified `results`; for a quarter that has none, a bare
    "Outcome of Board Meeting" filed within 75 days of the quarter end is kept as a candidate
    (some companies file results under that title; the statement finder decides later).
    """
    results: dict[date, dict] = {}
    candidates: dict[date, dict] = {}
    for f in rows:
        filed = datetime.fromisoformat(f["date"]).date()
        q = quarter_end_before(filed)
        kind = classify(f)
        if kind == "results":
            results.setdefault(q, f)
        elif kind == "board_outcome" and (filed - q).days <= 75:
            candidates.setdefault(q, f)
    for q, f in candidates.items():
        results.setdefault(q, {**f, "candidate": True})

    # A transcript discusses the latest results published before it; per quarter keep the
    # first transcript after those results (the earnings call), not a later investor meet.
    published = sorted((f["date"], q) for q, f in results.items())
    transcripts: dict[date, dict] = {}
    for f in sorted((f for f in rows if is_transcript(f)), key=lambda f: f["date"]):
        before = [q for d, q in published if d <= f["date"]]
        q = before[-1] if before else quarter_end_before(datetime.fromisoformat(f["date"]).date())
        transcripts.setdefault(q, f)
    keep_t = sorted(transcripts, reverse=True)[:n_quarters]
    keep_r = sorted(results, reverse=True)[: n_quarters + 1]   # +1: covers the oldest promise's quarter
    return {
        "transcripts": [{**transcripts[q], "quarter_end": q.isoformat()} for q in keep_t],
        "results": [{**results[q], "quarter_end": q.isoformat()} for q in keep_r],
    }


def find_documents(ticker: str, today: date | None = None) -> dict:
    """Transcripts and results filings for an NSE ticker (live NSE, one retry).

    Returns {symbol, company, transcripts, results}. Raises ValueError for an unknown ticker,
    RuntimeError if NSE cannot be reached.
    """
    company = resolve(ticker)
    end = today or ist_now().date()
    start = end - timedelta(days=config.RESEARCH_LOOKBACK_DAYS)
    errors: list[str] = []
    for attempt in range(1 + config.RETRIES):
        try:
            rows = filings_mod.parse_filings(filings_mod._fetch_nse(company.symbol, start, end))
            docs = pick_documents(rows)
            return {"symbol": company.symbol, "company": company.name, **docs}
        except Exception as exc:  # network, HTTP block, bad JSON
            errors.append(f"attempt {attempt + 1}: {exc}")
            time.sleep(1)
    raise RuntimeError(f"Could not reach NSE for {company.symbol}'s filings. {'; '.join(errors)}")
