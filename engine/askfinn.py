"""Ask FINN across the portfolio (block 10g, D-107 decision 5A).

The cheap model only turns the question into a small structured query [a form with fields:
what to look for, which stocks, which filing types, how many days]. Python then answers from the
same data the app shows: ranked filings (Today), price moves (Pulse) and the event calendar. The
model never writes the answer, so it cannot invent holdings, filings or news. If the AI is down,
a rule-based parser fills the same form.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Callable, Literal

from pydantic import BaseModel, ValidationError

import config
from engine import llm
from engine.ranker import rank_filings

Intent = Literal["filings", "moves", "events", "company", "unsupported"]
CATEGORIES = list(config.CATEGORY_TIER)


class Query(BaseModel):
    intent: Intent
    tickers: list[str] = []
    categories: list[str] = []
    days: int | None = None
    direction: Literal["up", "down", "volume"] | None = None
    limit: int | None = None


PROMPT = """Turn an investor's question about their stock portfolio into a query. Do NOT answer it.
Portfolio (ticker: company): {portfolio}
Filing categories: {categories}
Today is {today}.

intent:
- "filings": which stocks filed / announced something (results, management change, pledging, dividend...)
- "moves": price or volume moves (biggest gainers/losers, unusual volume)
- "events": upcoming board meetings, results dates, dividends/ex-dates
- "company": a question about one company's business, numbers or management commentary
- "unsupported": advice, price targets, news, anything not about the portfolio's filings, moves or events
tickers: portfolio tickers named or clearly meant (by company name too); [] = all.
categories: filing categories asked about, from the list; [] = any that matters.
days: look-back (filings, moves) or look-ahead (events) in days if said ("this week" = 7, "today" = 1).
direction: "up", "down" or "volume" for moves.
limit: how many if said ("top 3").

QUESTION: {question}
"""

_CAT_WORDS = {
    "results": r"result|earnings|quarter(ly)? numbers", "management_change": r"management|ceo|cfo|director|resign|appoint|kmp",
    "m_and_a": r"acqui|merger|m&a|demerger|stake", "litigation": r"litigation|lawsuit|court|penalt|fine|regulator",
    "credit_rating": r"credit rating|rating", "pledging": r"pledg", "dividend": r"dividend", "fund_raise": r"fund ?rais|qip|rights issue",
    "capex": r"capex|capacity|plant", "bonus_split": r"bonus|split", "insider_trading": r"insider|promoter (buy|sell)",
    "order_win": r"order win|order", "agm_egm": r"\bagm\b|\begm\b", "earnings_call": r"earnings call|con ?call",
}


def rule_query(question: str, portfolio: dict[str, str]) -> Query:
    """Fallback parser (no AI) for the common shapes of question."""
    q = question.lower()
    tickers = [t for t, name in portfolio.items()
               if re.search(rf"\b{re.escape(t.lower())}\b", q) or name.lower().split()[0] in q.split()]
    cats = [c for c, pat in _CAT_WORDS.items() if re.search(pat, q)]
    days = 1 if "today" in q else 7 if "week" in q else 30 if "month" in q else None
    m = re.search(r"\btop (\d+)", q)
    if re.search(r"price target|should i|buy or sell|news|valuation", q):
        intent: Intent = "unsupported"
    elif re.search(r"upcoming|next|coming|when (is|are)|calendar|ex-?date|record date|schedul", q):
        intent = "events"
    elif re.search(r"gain|los(e|er)|fell|rose|move|up the most|down the most|volume|spike|drop", q):
        intent = "moves"
    elif cats or re.search(r"file|filing|announce", q):
        intent = "filings"
    elif tickers:
        intent = "company"
    else:
        intent = "filings"
    direction = "volume" if "volume" in q else "down" if re.search(r"fell|los|drop|down|worst", q) else "up" if re.search(r"gain|rose|up|best", q) else None
    return Query(intent=intent, tickers=tickers, categories=cats, days=days, direction=direction, limit=int(m.group(1)) if m else None)


def parse(question: str, portfolio: dict[str, str], today: date, ask: Callable[..., Any] | None) -> tuple[Query, str]:
    """(query, who parsed it): the cheap model, or the rules if the AI fails."""
    if ask is not None:
        def check(obj: Any) -> Query:
            try:
                return Query.model_validate(obj)
            except ValidationError as exc:
                raise ValueError(f"bad query shape: {exc.errors()[0]['msg']}") from exc
        try:
            q = ask(PROMPT.format(portfolio=", ".join(f"{t}: {n}" for t, n in portfolio.items()), categories=", ".join(CATEGORIES),
                                  today=today.isoformat(), question=question), strong=False, validate=check, use_cache=True,
                    meta={}, schema=Query)
            q.tickers = [t for t in q.tickers if t in portfolio]
            q.categories = [c for c in q.categories if c in CATEGORIES]
            return q, "ai"
        except (ValueError, RuntimeError):
            pass
    return rule_query(question, portfolio), "rules"


# ------------------------------------------------------------------ Python answers

def answer_filings(q: Query, filings: list[dict], now: datetime) -> dict:
    days = q.days or 7
    since = (now - timedelta(days=days)).isoformat()
    ranked = [f for f in rank_filings(filings, {}, {}) if f["date"] >= since
              and (not q.tickers or f["ticker"] in q.tickers)
              and (f["kind"] in q.categories if q.categories else f["tier"] != "Low")]
    items = [{"ticker": f["ticker"], "date": f["date"][:10], "text": f.get("title", "")[:110], "kind": f["kind"],
              "url": f.get("pdf_url")} for f in ranked[: (q.limit or 8)]]
    what = " or ".join(c.replace("_", " ") for c in q.categories) or "filings that matter"
    who = ", ".join(q.tickers) if q.tickers else "your portfolio"
    if not ranked:
        return {"answer": f"No {what} from {who} in the last {days} days.", "items": []}
    stocks = sorted({f["ticker"] for f in ranked})
    n = len(ranked)
    return {"answer": f"{n} {'filing' if n == 1 else 'filings'} ({what}) in the last {days} days from {len(stocks)} "
                      f"{'stock' if len(stocks) == 1 else 'stocks'}: {', '.join(stocks[:8])}.", "items": items}


def answer_moves(q: Query, rows: list[dict]) -> dict:
    rows = [r for r in rows if r.get("move") is not None and (not q.tickers or r["ticker"] in q.tickers)]
    n = q.limit or 3
    if q.direction == "volume":
        top = sorted([r for r in rows if r.get("vol_x") is not None], key=lambda r: -r["vol_x"])[:n]
        text = "Highest volume against the 20-day average: " + ", ".join(f"{r['ticker']} {r['vol_x']}×" for r in top) + "."
    else:
        down = q.direction == "down"
        top = sorted(rows, key=lambda r: r["move"] if down else -r["move"])[:n]
        text = ("Biggest fallers" if down else "Biggest gainers") + " on the last session: " + \
            ", ".join(f"{r['ticker']} {r['move']:+.2f}%" for r in top) + "."
    items = [{"ticker": r["ticker"], "date": r.get("date"), "text": f"{r['move']:+.2f}% on the day, {r.get('move_5d') or 0:+.2f}% over 5 days, volume {r.get('vol_x')}×",
              "kind": "move", "url": None} for r in top]
    return {"answer": text, "items": items}


def answer_events(q: Query, pulse: dict) -> dict:
    ev = [e for e in pulse.get("events", []) + pulse.get("expected", []) if not q.tickers or e["ticker"] in q.tickers]
    if q.categories and "dividend" in q.categories:
        ev = [e for e in ev if "ividend" in e["title"]]
    if q.days:
        end = (date.today() + timedelta(days=q.days)).isoformat()
        ev = [e for e in ev if e["date"] <= end]
    ev = sorted(ev, key=lambda e: e["date"])[: (q.limit or 8)]
    if not ev:
        return {"answer": "Nothing scheduled or expected for that in FINN's calendar.", "items": []}
    items = [{"ticker": e["ticker"], "date": e["date"], "text": e["title"] + (" (estimate)" if e["kind"] == "expected" else ""),
              "kind": e["kind"], "url": None} for e in ev]
    confirmed = sum(1 for e in ev if e["kind"] != "expected")
    return {"answer": f"{len(ev)} coming up ({confirmed} confirmed by NSE, {len(ev) - confirmed} estimated from last year's dates). "
                      f"First: {ev[0]['ticker']} on {ev[0]['date']}.", "items": items}


def ask_portfolio(question: str, filings: list[dict], pulse: dict, now: datetime,
                  ask: Callable[..., Any] | None = llm.ask_json, company_asker: Callable[[str, str], dict] | None = None) -> dict:
    """Answer a portfolio question: parse (AI or rules) → Python over the app's own data."""
    from engine.copilot import REFUSE
    portfolio = {r["ticker"]: r.get("company", r["ticker"]) for r in pulse.get("stocks", [])}
    q, parsed_by = (Query(intent="unsupported"), "rules") if REFUSE.search(question) else parse(question, portfolio, now.date(), ask)
    base = {"refused": False, "answered_by": "python", "parsed_by": parsed_by, "query": q.model_dump(), "citations": [], "suggestions": []}
    if q.intent == "unsupported":
        return {**base, "refused": True, "answered_by": "rules", "items": [],
                "answer": "FINN answers from your portfolio's filings, price moves and calendar. It does not give advice, price targets or news."}
    if q.intent == "company":
        if q.tickers and company_asker:
            out = company_asker(question, q.tickers[0])
            return {**out, "parsed_by": parsed_by, "query": q.model_dump(), "items": [], "routed_to": q.tickers[0]}
        q.intent = "filings"
    out = answer_filings(q, filings, now) if q.intent == "filings" else answer_moves(q, pulse.get("stocks", [])) \
        if q.intent == "moves" else answer_events(q, pulse)
    return {**base, **out}
