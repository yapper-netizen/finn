"""Research for one company (pull side): promise tracker + bull vs bear, with receipts.

{Primary sources only}: the company's concall transcripts and results filings from NSE.
Division of labour (D-079..D-084):
- Python finds the documents, picks the guidance pages of each transcript (keywords, D-021),
  builds every number from the block 7 results cards, decides timing ("Too early"), and checks
  every quote against the transcript text (fuzzy match, D-041). Unverified quotes are dropped.
- Cheap model: list management's promises per transcript, with verbatim quotes (EN-12).
- Strong model, one call per stock: Delivered / Partial / Missed per promise, citing fact ids
  that Python made (EN-13); one more call for bull vs bear (EN-14). Neither does arithmetic.
"""
from __future__ import annotations

import difflib
import re
import time
from datetime import date, datetime
from typing import Any, Callable, Literal

from pydantic import BaseModel, ValidationError

import config
from data import docs
from data.research_docs import find_documents
from engine import cards
from engine.results import fiscal_label

ENGINE_VERSION = 2       # 2: XBRL facts, say-do targets, tone vs numbers (block 10f)
MIN_ENGINE_VERSION = 1   # older saved results still open (without the 10f parts)
Ask = Callable[..., Any]   # engine.llm.ask_json-compatible
Progress = Callable[[str], None]

# ---------------------------------------------------------------- transcript pages (EN-10)

_KEYWORDS = re.compile(
    r"guidance|guide[ds]?\b|outlook|expect|target|aspir|\baim\b|going forward|next (year|quarter|few)|"
    r"\bFY ?'?2\d|margin|growth|grow\b|double[- ]digit|\bband\b|range of|visibility|capex|"
    r"we (will|should|would) (be|see|achieve|deliver)|confident|trajectory", re.I)


def pick_pages(pages: list[str], max_chars: int = config.TRANSCRIPT_MAX_CHARS) -> list[int]:
    """Indexes of the pages most likely to hold guidance, in page order, within a size budget."""
    scored = sorted(((len(_KEYWORDS.findall(t)), i) for i, t in enumerate(pages) if t.strip()), reverse=True)
    keep: list[int] = []
    used = 0
    for score, i in scored:
        if score == 0 or used + len(pages[i]) > max_chars:
            continue
        keep.append(i)
        used += len(pages[i])
    return sorted(keep)


def pages_text(pages: list[str], idx: list[int]) -> str:
    return "\n".join(f"===== PAGE {i + 1} =====\n{pages[i]}" for i in idx)


# ---------------------------------------------------------------- quote guard (EN-15)
# Lives in engine/quotes.py (shared with management cards); re-exported here.
from engine.quotes import norm, quote_score, verify_quote  # noqa: E402,F401


# ---------------------------------------------------------------- promise extraction (EN-12)

Metric = Literal["revenue_growth", "revenue", "ebitda_margin", "ebitda_growth", "pat_growth", "pat_margin", "other"]
CHECKABLE = {"revenue_growth", "revenue", "ebitda_margin", "ebitda_growth", "pat_growth", "pat_margin"}


class PromiseOut(BaseModel):
    metric: Metric
    statement: str
    period_text: str
    due_quarter_end: str | None
    quote: str
    page: int


class PromisesOut(BaseModel):
    promises: list[PromiseOut]


PROMISE_PROMPT = """You read an Indian listed company's earnings-call transcript.
Company: {company}. This call discussed the results for the quarter ended {quarter_end} ({quarter}).
Below are the pages most likely to contain guidance, from the transcript PDF.

List MANAGEMENT's forward-looking commitments: guidance, targets, and clear expectations about
the whole company, numeric or directional (e.g. "we expect revenue growth of 20%+ in FY27",
"EBITDA margin should be 13-14%", "margins will improve from the next quarter", "we expect
double-digit growth this year", "profitability will recover in H2").
Rules:
- Only statements made by company management, never by analysts asking questions.
- "quote": copy the management sentence(s) VERBATIM from the text (max 60 words). Do not edit.
  The quote must itself state the target (its numbers), not just agree with an analyst.
- "page": the PAGE number the quote is on.
- "metric": revenue_growth, revenue, ebitda_margin, ebitda_growth, pat_growth or pat_margin when
  the commitment is about that number for the whole company; otherwise "other" (capex, volumes,
  segments, launches, market share, order book, debt). EBIT, operating margin or PBT margin
  targets are "other" too: only EBITDA margin counts as ebitda_margin.
- "statement": one short plain sentence of the promise (max 20 words).
- "period_text": the period as said ("FY27", "next quarter", "H2", "medium term").
- "due_quarter_end": the last quarter-end date (YYYY-MM-DD) by which it can be judged, using
  Indian fiscal years (FY27 = April 2026 to March 2027, so FY27 -> 2027-03-31; "next quarter" after
  {quarter_end} -> the following quarter end). null if vague ("medium term", "long run").
- If one sentence covers several periods ("100 bps better in FY26 and another 100 bps in FY27"),
  list one commitment per period, each with its own due date (the same quote may be reused).
- Always include standing company-level ranges ("long-term EBITDA margin of 11-13%"), with
  due_quarter_end null.
- Put company-level guidance on revenue, growth, EBITDA margin or profit FIRST: these are checked
  against the results filings. Include at most 3 "other" items (the most material ones).
- At most 10 commitments in all. Use [] if there are none.
Use only this text, no outside knowledge.

TEXT:
{text}
"""


def extract_promises(ask: Ask, company: str, transcript: dict, pages: list[str], meta: dict) -> list[dict]:
    """Cheap model: promises in one transcript, each with a quote and page (unverified yet)."""
    idx = pick_pages(pages)
    q_end = date.fromisoformat(transcript["quarter_end"])
    prompt = PROMISE_PROMPT.format(company=company, quarter_end=q_end.isoformat(), quarter=fiscal_label(q_end),
                                   text=pages_text(pages, idx))
    out = ask(prompt, strong=config.RESEARCH_EXTRACT_STRONG, validate=_validator(PromisesOut), use_cache=True,
              meta=meta, schema=PromisesOut)
    return [p.model_dump() for p in out.promises[:10]]


def _validator(model: type[BaseModel]) -> Callable[[Any], BaseModel]:
    def check(obj: Any) -> BaseModel:
        try:
            return model.model_validate(obj)
        except ValidationError as exc:
            err = exc.errors()[0]
            raise ValueError(f"AI answer has the wrong shape at {'.'.join(map(str, err['loc']))}: {err['msg']}") from exc
    return check


# ---------------------------------------------------------------- actuals as facts (Python only)

def _fy(q_end: date) -> int:
    return q_end.year + 1 if q_end.month > 3 else q_end.year


def card_facts(card_list: list[dict]) -> list[dict]:
    """Numbered facts from results cards. Each fact comes from ONE card (same basis, same filing),
    so growth compares like with like. FY totals only when all 4 quarters are on file."""
    facts: list[dict] = []
    ok_cards = sorted((c for c in card_list if c.get("status") in ("ok", "partial") and c.get("period")),
                      key=lambda c: c["period"]["current"])

    def add(metric: str, quarter: str, text: str, value: float | None, card: dict, page: int | None) -> None:
        unit = "%" if "margin" in metric else "% YoY"
        facts.append({"id": f"F{len(facts) + 1}", "metric": metric, "quarter": quarter, "text": text, "value": value, "unit": unit,
                      "source": {"filing_id": card.get("filing_id"), "pdf_url": card.get("pdf_url"), "page": page,
                                 "basis": card.get("basis")}})

    def pct(p: float | None, note: str | None) -> str:
        return note or "n/a" if p is None else f"{'up' if p >= 0 else 'down'} {abs(p):.1f}% YoY"

    for c in ok_cards:
        q = c["period"]["label"]
        by = {m["key"]: m for m in c["metrics"] if m.get("available")}
        top = by.get("revenue") or by.get("total_income")
        if top:
            add("revenue", q, f"{top['label']} {q}: ₹{top['values']['current']:,.0f} cr, "
                f"{pct(top.get('yoy_pct'), top.get('yoy_note'))} ({c.get('basis')})",
                top.get("yoy_pct"), c, (top.get("source") or {}).get("page"))
        for key, label in (("ebitda", "EBITDA"), ("pat", "PAT")):
            m = by.get(key)
            if m:
                add(f"{key}_growth", q, f"{label} {q}: ₹{m['values']['current']:,.0f} cr, "
                    f"{pct(m.get('yoy_pct'), m.get('yoy_note'))}{' (computed)' if m.get('computed') else ''}",
                    m.get("yoy_pct"), c, (m.get("source") or {}).get("page"))
        for g in c.get("margins") or []:
            cur, bps = g["values"]["current"], g.get("yoy_bps")
            if cur is not None:
                add(g["key"], q, f"{g['label']} {q}: {cur:.1f}%" + (f", {'+' if bps >= 0 else '−'}{abs(bps)} bps YoY" if bps is not None else ""),
                    cur, c, (by.get("revenue", {}).get("source") or {}).get("page"))

    # FY totals (Python sums): needs the 4 quarter cards of one fiscal year, same basis.
    by_fy: dict[int, list[dict]] = {}
    for c in ok_cards:
        by_fy.setdefault(_fy(date.fromisoformat(c["period"]["current"])), []).append(c)
    for fy, cs in sorted(by_fy.items()):
        if len(cs) != 4 or len({c.get("basis") for c in cs}) != 1:
            continue
        for key, label in (("revenue", "Revenue"), ("ebitda", "EBITDA"), ("pat", "PAT")):
            ms = [next((m for m in c["metrics"] if m["key"] == key and m.get("available")), None) for c in cs]
            if any(m is None or m["values"]["current"] is None for m in ms):
                continue
            cur = sum(m["values"]["current"] for m in ms)
            text = f"{label} FY{fy % 100:02d} (sum of 4 quarters): ₹{cur:,.0f} cr"
            growth = None
            if all(m["values"].get("year_ago") not in (None, 0) for m in ms):
                prev = sum(m["values"]["year_ago"] for m in ms)
                if prev > 0:
                    growth = round((cur - prev) / prev * 100, 1)
                    text += f", {'up' if growth >= 0 else 'down'} {abs(growth):.1f}% YoY"
            add(f"{key}_fy", f"FY{fy % 100:02d}", text, growth, cs[-1], None)
            if key == "ebitda":
                rev = [next((m for m in c["metrics"] if m["key"] == "revenue" and m.get("available")), None) for c in cs]
                if all(r and r["values"]["current"] for r in rev):
                    margin = round(cur / sum(r["values"]["current"] for r in rev) * 100, 1)
                    add("ebitda_margin_fy", f"FY{fy % 100:02d}", f"EBITDA margin FY{fy % 100:02d}: {margin:.1f}%", margin, cs[-1], None)
    return facts


# ---------------------------------------------------------------- more facts from XBRL (10f, N1)

def xbrl_facts(fin: dict | None, start: int, since: str | None = None) -> list[dict]:
    """Segment, capex, tax-rate and cash-conversion facts from the XBRL statements (D-103).

    Python does all arithmetic. `since` (YYYY-MM-DD) drops quarters before the research window.
    Segment results are before interest and tax (like EBIT), so they are labelled as such.
    """
    if not fin or not fin.get("quarters"):
        return []
    facts: list[dict] = []
    qs = sorted(fin["quarters"], key=lambda q: q["period_end"])
    src = lambda q: {"pdf_url": q.get("url"), "page": None, "basis": fin.get("basis"), "kind": "xbrl"}

    def add(metric: str, quarter: str, text: str, value: float | None, unit: str, q: dict) -> None:
        facts.append({"id": f"F{start + len(facts)}", "metric": metric, "quarter": quarter, "text": text,
                      "value": value, "unit": unit, "source": src(q)})

    def growth(cur: float | None, base: float | None) -> float | None:
        return round((cur - base) / base * 100, 1) if cur is not None and base and base > 0 else None

    by_end = {q["period_end"]: q for q in qs}
    seg_by_q = {q["period_end"]: {s["key"]: s for s in q.get("segments") or []} for q in qs}
    for q in qs:
        if since and q["period_end"] < since:
            continue
        ya_end = str(int(q["period_end"][:4]) - 1) + q["period_end"][4:]
        for key, sg in seg_by_q[q["period_end"]].items():
            if len(seg_by_q[q["period_end"]]) < 2:
                break
            ya = seg_by_q.get(ya_end, {}).get(key)
            g = growth(sg.get("revenue"), ya.get("revenue") if ya else None)
            add("segment_revenue", q["label"], f"Segment revenue, {sg['name']}, {q['label']}: ₹{sg['revenue']:,.0f} cr"
                + (f", {'up' if g >= 0 else 'down'} {abs(g):.1f}% YoY" if g is not None else ""), g, "% YoY", q)
            if sg.get("margin") is not None:
                prev_m = ya.get("margin") if ya else None
                add("segment_margin", q["label"], f"Segment result margin (before interest and tax, not EBITDA), {sg['name']}, "
                    f"{q['label']}: {sg['margin']:.1f}%" + (f" vs {prev_m:.1f}% a year ago" if prev_m is not None else ""),
                    sg["margin"], "%", q)
    # fiscal-year totals: segment revenue growth, effective tax rate (needs the 4 quarters of the year)
    fys: dict[str, list[dict]] = {}
    for q in qs:
        fys.setdefault(q["label"].split()[1], []).append(q)
    for fy, four in fys.items():
        if len(four) != 4 or (since and four[-1]["period_end"] < since):
            continue
        tax, pbt = [q.get("tax") for q in four], [q.get("pbt") for q in four]
        if None not in tax and None not in pbt and sum(pbt) > 0:
            add("tax_rate", fy, f"Effective tax rate {fy} (tax ÷ profit before tax, 4 quarters): {100 * sum(tax) / sum(pbt):.1f}%",
                round(100 * sum(tax) / sum(pbt), 1), "%", four[-1])
        prev = fys.get(f"FY{int(fy[2:]) - 1:02d}")
        if prev and len(prev) == 4:
            names = {k: s["name"] for k, s in seg_by_q[four[-1]["period_end"]].items()}
            for key, name in names.items():
                cur = [seg_by_q[q["period_end"]].get(key, {}).get("revenue") for q in four]
                old = [seg_by_q[q["period_end"]].get(key, {}).get("revenue") for q in prev]
                if None in cur or None in old:
                    continue
                g = growth(sum(cur), sum(old))
                add("segment_revenue_fy", fy, f"Segment revenue, {name}, {fy} (4 quarters): ₹{sum(cur):,.0f} cr"
                    + (f", {'up' if g >= 0 else 'down'} {abs(g):.1f}% YoY" if g is not None else ""), g, "% YoY", four[-1])
    # capex and cash conversion by half year; full-year capex when both halves are known
    halves = {h["label"]: h for h in fin.get("cash_flows") or []}
    for label, h in halves.items():
        q = {"url": h.get("url"), "period_end": ""}
        if h.get("capex") is not None:
            add("capex", label, f"Capex {label} (purchase of fixed assets, cash flow statement): ₹{h['capex']:,.0f} cr",
                h["capex"], "cr", q)
        if h.get("cash_conversion") is not None:
            add("cash_conversion", label, f"Cash from operations ÷ PAT, {label}: {h['cash_conversion']:.0f}%",
                h["cash_conversion"], "%", q)
        if label.startswith("H2") and f"H1 {label[3:]}" in halves and h.get("capex") is not None:
            h1 = halves[f"H1 {label[3:]}"]
            if h1.get("capex") is not None:
                add("capex", label[3:], f"Capex {label[3:]} (full year, H1 + H2): ₹{h1['capex'] + h['capex']:,.0f} cr",
                    round(h1["capex"] + h["capex"], 2), "cr", q)
    return facts


_OTHER_CHECKABLE = re.compile(r"capex|capital expenditure|tax rate|cash flow|ocf|cash conversion|segment|margin|growth|"
                              r"revenue|grow|ebitda|business", re.I)


def worth_judging(p: dict, segment_names: list[str]) -> bool:
    """A non-headline promise goes to the verdict step only if FINN may hold a figure for it."""
    text = p["statement"]
    if re.search(r"operating margin|\bEBIT\b(?!DA)|EBIT margin", text, re.I) and not re.search(r"segment|business", text, re.I):
        return False    # operating/EBIT margin is not EBITDA, and FINN does not compute company EBIT margins
    if p["metric"] in CHECKABLE:
        return True
    if re.search(r"volume|market share|export|europe|deal|closure|acquisition|payout|dividend|plant|launch|"
                 r"one-time|incremental amount|working capital|debt", text, re.I):
        return False    # FINN has no filed figure for these (or measures them differently)
    named_segment = any(n.lower().split()[0] in text.lower() for n in segment_names if n)
    return named_segment or bool(_OTHER_CHECKABLE.search(text))


# ---------------------------------------------------------------- verdicts (EN-13)

class VerdictOut(BaseModel):
    promise_id: str
    verdict: Literal["Delivered", "Partial", "Missed", "Not checkable"]
    fact_ids: list[str]
    reason: str
    target_low: float | None = None      # the promised number(s), as stated in the promise
    target_high: float | None = None
    actual_fact_id: str | None = None    # the one fact whose value is the delivered number


class VerdictsOut(BaseModel):
    verdicts: list[VerdictOut]


JUDGE_PROMPT = """You check whether a company's management delivered on its own promises.
Company: {company}. Use ONLY the facts below: they are figures from the company's results filings,
already computed by a program. Do not calculate anything yourself and use no outside knowledge.

FACTS (id: fact):
{facts}

PROMISES (id: what was promised, period, said in):
{promises}

For each promise give:
- verdict: "Delivered" (the facts show the target was met), "Partial" (direction right or close,
  target not fully met), "Missed" (clearly not met), or "Not checkable" (no fact covers it).
- Revenue, growth, margins and profit are "higher is better": landing ABOVE a target or range
  counts as Delivered (say it beat the guidance); only falling short is Partial or Missed.
- A standing range with no end date ("11-13% EBITDA margin over the medium term") is judged on the
  quarters reported since it was said: at or above the range = Delivered, just below = Partial,
  well below = Missed; say "so far" in the reason.
- A promise for a full year is judged on that year's facts if present; otherwise on the quarters of
  that year reported so far ("so far" in the reason).
- A directional promise ("margins will improve", "growth will pick up") is judged on the direction
  of the relevant facts in the quarters after it was said.
- fact_ids: the ids of the facts you relied on (at least one unless "Not checkable").
- reason: one short sentence (max 30 words) naming the figures, e.g. "Revenue grew 18% in FY26
  against 20%+ guided."
- Use only facts for quarters AFTER the call in which the promise was made.
- Segment facts: a promise about one business (e.g. "paints", "FMEG", "cables") is judged on that
  segment's facts only if the segment exists by that name; if the segment combines several businesses
  (e.g. "Paints and Adhesives") and the promise is about one of them, answer "Not checkable".
- Segment result margins are before interest and tax (like EBIT), lower than EBITDA: never judge an
  EBITDA-margin target against them ("Not checkable"), except a purely directional promise.
- Capex promises are judged on the capex facts (₹ crore; 1 billion = 100 crore).
- target_low / target_high: the promised number(s) exactly as stated (a single number: both equal;
  "20%+": low 20, high null; directional: both null). actual_fact_id: the ONE fact whose value is
  the delivered number to compare with the target (null if none fits).
Write the reason first in your head, then pick the verdict that matches it.
Return one entry per promise id.
"""


_CONTRADICTS_DELIVERED = re.compile(r"\b(missed|not (met|achieved|delivered)|fail(ed|ing)? to|fell short|below the (target|guid|range))", re.I)


def judge(ask: Ask, company: str, promises: list[dict], facts: list[dict], meta: dict) -> dict[str, dict]:
    """Strong model, one call for all of a stock's checkable promises; answers are validated."""
    if not promises:
        return {}
    fact_lines = "\n".join(f"{f['id']}: {f['text']}" for f in facts) or "(none)"
    prom_lines = "\n".join(f"{p['id']}: {p['statement']} | period: {p['period_text']} | said in the {p['made_in']} call"
                           for p in promises)
    out = ask(JUDGE_PROMPT.format(company=company, facts=fact_lines, promises=prom_lines), strong=True,
              validate=_validator(VerdictsOut), use_cache=True, meta=meta, schema=VerdictsOut)
    fact_ids = {f["id"] for f in facts}
    result: dict[str, dict] = {}
    for v in out.verdicts:
        ids = [i for i in v.fact_ids if i in fact_ids]
        verdict = v.verdict if (ids or v.verdict == "Not checkable") else "Not checkable"
        if verdict == "Delivered" and _CONTRADICTS_DELIVERED.search(v.reason):
            verdict, ids = "Not checkable", []   # verdict and reason disagree: show neither as a verdict
            v.reason = "The AI's verdict and its reason disagreed, so no verdict is shown. " + v.reason
        result[v.promise_id] = {"verdict": verdict, "fact_ids": ids if verdict != "Not checkable" else [],
                                "reason": v.reason.strip()[:240],
                                "target": {"low": v.target_low, "high": v.target_high},
                                "actual_fact_id": v.actual_fact_id if v.actual_fact_id in ids else None}
    return result


def is_guidance(p: dict) -> bool:
    """Explicit headline guidance (N7): a company-level number, or a stated figure for revenue,
    growth, margin, profit or capex (segment guidance included)."""
    if p["metric"] in CHECKABLE:
        return True
    stated = bool(_numbers(p["statement"])) or bool(re.search(r"double[- ]digit|single[- ]digit", p["statement"], re.I))
    return stated and bool(
        re.search(r"guid|revenue|growth|grow|margin|ebitda|capex|profit", p["statement"], re.I))


def guard_verdict(p: dict, facts_by_id: dict[str, dict]) -> None:
    """Python checks on an AI verdict that has a target and a delivered figure (10f).

    - An annual capex target judged on half-year capex only -> "Too early".
    - "Delivered" while the figure is outside the promise (below the low end; for capex, outside
      the range) -> no verdict shown, with the reason.
    """
    if p.get("verdict") not in ("Delivered", "Partial", "Missed"):
        return
    fact = facts_by_id.get(p.get("actual_fact_id") or "")
    tgt = p.get("target") or {}
    if not fact or fact.get("value") is None:
        return
    if fact["metric"] == "capex" and fact["quarter"].startswith("H"):
        p.update(verdict="Too early", fact_ids=[], decided_by="rules",
                 reason=f"Only half-year capex is filed so far ({fact['text']}); an annual target is judged on the full year.")
        return
    sd = say_do(p, facts_by_id)
    if not sd or p["verdict"] != "Delivered":
        return
    low, high, actual = sd["low"], sd["high"], sd["actual"]
    outside = (low is not None and actual < low) or (sd["unit"] == "cr" and high is not None and actual > high)
    if outside:
        p.update(verdict="Not checkable", fact_ids=[], decided_by="rules",
                 reason=f"The AI said Delivered, but the figure ({fact['text']}) is outside the promise, so no verdict is shown.")


def target_from_statement(statement: str) -> tuple[float | None, float | None]:
    """'11% to 13%' -> (11, 13); '20%+' / 'over 30%' -> (20, None); '22.5%' -> (22.5, 22.5); else (None, None)."""
    nums = sorted(float(n) for n in _numbers(_with_digits(statement).replace(",", "")))
    if len(nums) == 2:
        return nums[0], nums[1]
    if len(nums) == 1:
        open_top = re.search(r"\d\s*%?\s*\+|over|above|more than|at least|greater than|exceed", statement, re.I)
        return nums[0], (None if open_top else nums[0])
    return None, None


def _period_key(label: str) -> tuple[int, float]:
    """'Q2 FY27' -> (27, 2); 'H1 FY27' -> (27, 2.1); 'FY26' -> (26, 5)."""
    m = re.search(r"(Q|H)?(\d)?\s*FY(\d{2})", label or "")
    if not m:
        return (0, 0)
    fy = int(m.group(3))
    if not m.group(1):
        return (fy, 5)
    return (fy, int(m.group(2)) + (0.1 if m.group(1) == "H" else 0)) if m.group(1) == "Q" else (fy, 2.1 if m.group(2) == "1" else 4.1)


def pick_actual(p: dict, facts_by_id: dict[str, dict]) -> str | None:
    """The delivered number when the model named none: the latest cited fact in the promise's unit."""
    text = p["statement"]
    unit = "cr" if re.search(r"capex|billion|crore|₹|\bINR\b|\bRs\b", text, re.I) else \
        "% YoY" if re.search(r"grow|growth", text, re.I) else "%"
    cands = [facts_by_id[i] for i in p.get("fact_ids") or [] if i in facts_by_id
             and facts_by_id[i].get("unit") == unit and facts_by_id[i].get("value") is not None]
    return max(cands, key=lambda f: _period_key(f["quarter"]))["id"] if cands else None


def say_do(p: dict, facts_by_id: dict[str, dict]) -> dict | None:
    """Promised vs delivered numbers for the chart (N2), or None.

    The target must be numbers that appear in the promise's own words (statement or quote); the
    delivered number is a Python-made fact. Units must agree (% with %, crore with crore).
    """
    tgt, fid = p.get("target") or {}, p.get("actual_fact_id")
    low, high = tgt.get("low"), tgt.get("high")
    if low is None and high is None:                      # model gave none: read it from the promise
        low, high = target_from_statement(p["statement"])
    if fid not in facts_by_id:
        fid = pick_actual(p, facts_by_id)
    if fid not in facts_by_id or (low is None and high is None):
        return None
    words = _with_digits(p["statement"] + " " + (p.get("receipt") or {}).get("quote", ""))
    said = {float(x) for x in re.findall(r"\d+(?:\.\d+)?", words.replace(",", ""))}
    if any(v is not None and float(v) not in said and float(v) / 100 not in said and float(v) * 100 not in said
           for v in (low, high)):
        return None
    fact = facts_by_id[fid]
    if fact.get("value") is None:
        return None
    unit = fact.get("unit", "")
    if unit == "cr" and re.search(r"billion|bn", words, re.I):        # "₹12 billion" -> 1,200 crore
        low, high = (v * 100 if v is not None and v < 1000 else v for v in (low, high))
    return {"low": low, "high": high, "actual": fact["value"], "unit": unit, "fact": fact["text"]}


# ---------------------------------------------------------------- tone vs numbers (10f, N4)

class ToneOut(BaseModel):
    transcript_id: str
    score: int                 # -2 very cautious .. +2 very confident
    label: str
    quote: str
    page: int


class TonesOut(BaseModel):
    tones: list[ToneOut]


TONE_PROMPT = """You read the opening remarks of {company}'s earnings calls (management speaking).
For EACH call, rate how confident management sounds about the business outlook, from its own words:
-2 very cautious (warnings, weak demand, pressure), -1 cautious, 0 neutral or mixed, +1 confident,
+2 very confident (strong demand, upbeat outlook, raised ambitions).
Judge tone only, not the numbers. Use only the text below.
For each call return: transcript_id, score, label (2-4 words, e.g. "upbeat on demand"),
quote: ONE sentence copied exactly from that call that best shows the tone, page: its PAGE number.

{text}
"""


def opening_pages(pages: list[str], n: int = 2, window: int = 6) -> list[int]:
    """Management's opening remarks: among the first content pages, the ones where management
    speaks most ("we", "our"), not the operator's agenda or the disclaimer. In page order."""
    content = [i for i, t in enumerate(pages) if len(t.strip()) > 400][:window]
    voice = lambda i: len(re.findall(r"\b(we|our|us)\b", pages[i], re.I)) / max(len(pages[i]), 1)
    return sorted(sorted(content, key=voice, reverse=True)[:n])


def tone_vs_numbers(ask: Ask, company: str, transcripts: list[dict], fin: dict | None, meta: dict) -> list[dict]:
    """Cheap model scores each call's tone (with a verified quote); Python pairs it with growth.

    For each call: revenue growth YoY of the quarter it discussed and of the next quarter (did the
    tone hold up?). A gap is flagged when an upbeat call is followed by slower growth, or a
    cautious call by faster growth (5 points or more).
    """
    if not transcripts:
        return []
    blocks = []
    for t in transcripts:
        idx = opening_pages(t["pages"])
        blocks.append(f"##### CALL {t['id']} ({t['quarter']})\n" + pages_text(t["pages"], idx))
    out = ask(TONE_PROMPT.format(company=company, text="\n\n".join(blocks)), strong=False,
              validate=_validator(TonesOut), use_cache=True, meta=meta, schema=TonesOut)
    by_id = {t["id"]: t for t in transcripts}
    growth = {}
    if fin:
        qs = sorted(fin.get("quarters") or [], key=lambda q: q["period_end"])
        for i, q in enumerate(qs):
            growth[q["period_end"]] = (q.get("revenue_yoy"), qs[i + 1].get("revenue_yoy") if i + 1 < len(qs) else None,
                                       qs[i + 1]["label"] if i + 1 < len(qs) else None)
    rows = []
    for o in out.tones:
        t = by_id.get(o.transcript_id)
        if not t:
            continue
        page, score = verify_quote(o.quote, t["pages"], o.page)
        if page is None:
            continue
        g, g_next, next_label = growth.get(t["quarter_end"], (None, None, None))
        gap = None
        if g is not None and g_next is not None:
            if o.score >= 1 and g_next <= g - 5:
                gap = f"Upbeat call, then growth slowed to {g_next:+.1f}% in {next_label}"
            elif o.score <= -1 and g_next >= g + 5:
                gap = f"Cautious call, then growth picked up to {g_next:+.1f}% in {next_label}"
        rows.append({"transcript_id": t["id"], "quarter": t["quarter"], "quarter_end": t["quarter_end"],
                     "score": max(-2, min(2, o.score)), "label": o.label.strip()[:40],
                     "growth": g, "growth_next": g_next, "next_quarter": next_label, "gap": gap,
                     "receipt": {"quote": o.quote.strip(), "page": page, "pdf_url": t["pdf_url"], "doc": t["label"],
                                 "match": round(score, 2)}})
    return sorted(rows, key=lambda r: r["quarter_end"])


# ---------------------------------------------------------------- bull vs bear (EN-14)

class PointOut(BaseModel):
    point: str
    quote: str | None
    transcript_id: str | None
    page: int | None
    fact_ids: list[str]


class BullBearOut(BaseModel):
    bull: list[PointOut]
    bear: list[PointOut]


BULL_BEAR_PROMPT = """You are a long-term fundamental investor reviewing {company}.
Use ONLY the facts (from results filings, computed by a program) and the transcript extracts below.
No outside knowledge, no news, no opinions that the material does not support.

Give exactly 3 bull points and 3 bear points. Each:
- point: one plain sentence (max 25 words).
- quote: a VERBATIM sentence from a transcript that supports it (management or analyst), or null.
- transcript_id and page: where the quote is (null if no quote).
- fact_ids: ids of facts that support it ([] if none).
Every point needs a quote or at least one fact id. Bear points should be real risks visible in the
material (slowing growth, margin pressure, missed guidance, analyst concerns), not generic ones.

FACTS:
{facts}

TRANSCRIPT EXTRACTS:
{extracts}
"""


def bull_bear(ask: Ask, company: str, facts: list[dict], transcripts: list[dict], meta: dict) -> dict:
    """Strong model, one call. Points without a verified quote or a valid fact are dropped."""
    extracts = "\n\n".join(
        f"##### TRANSCRIPT {t['id']} ({t['quarter']} call)\n" + pages_text(t["pages"], pick_pages(t["pages"], 14000))
        for t in transcripts)
    out = ask(BULL_BEAR_PROMPT.format(company=company, facts="\n".join(f"{f['id']}: {f['text']}" for f in facts),
                                      extracts=extracts),
              strong=True, validate=_validator(BullBearOut), use_cache=True, meta=meta, schema=BullBearOut)
    fact_ids = {f["id"] for f in facts}
    by_id = {t["id"]: t for t in transcripts}
    dropped = 0

    def keep(points: list[PointOut]) -> list[dict]:
        nonlocal dropped
        kept = []
        for p in points[:3]:
            receipt = None
            t = by_id.get(p.transcript_id or "")
            if p.quote and t:
                page, score = verify_quote(p.quote, t["pages"], p.page)
                if page:
                    receipt = {"quote": p.quote.strip(), "page": page, "pdf_url": t["pdf_url"], "doc": t["label"],
                               "match": round(score, 2)}
            ids = [i for i in p.fact_ids if i in fact_ids]
            if receipt is None and not ids:
                dropped += 1
                continue
            kept.append({"point": p.point.strip(), "receipt": receipt, "fact_ids": ids})
        return kept

    return {"bull": keep(out.bull), "bear": keep(out.bear), "dropped": dropped}


# ---------------------------------------------------------------- the pipeline (EN-16)

_NUMBER_WORDS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split())}
_NUMBER_WORDS.update({"double": "2", "twice": "2", "doubling": "2", "half": "50"})


def _with_digits(text: str) -> str:
    """'two percentage points' -> '2 percentage points', so words and digits compare equal."""
    return re.sub(r"[A-Za-z]+", lambda m: _NUMBER_WORDS.get(m.group(0).lower(), m.group(0)), text or "")


def quote_states_target(statement: str, quote: str) -> bool:
    """If the promise names target numbers, at least one must be in the quote itself."""
    nums = _numbers(_with_digits(statement))
    return not nums or bool(nums & set(re.findall(r"\d+(?:\.\d+)?", _with_digits(quote))))


def _default_fin(symbol: str) -> dict | None:
    from engine import financials
    return financials.get(symbol)


def is_cover_letter(pages: list[str]) -> bool:
    """A 1-2 page letter that says the transcript is elsewhere, not the transcript itself."""
    text = " ".join(pages)
    return len(pages) <= 2 and len(text) < 2500 and bool(re.search(r"transcript", text, re.I))


def _label_doc(t: dict) -> str:
    q_end = date.fromisoformat(t["quarter_end"])
    return f"{fiscal_label(q_end)} earnings call"


def build_research(
    ticker: str,
    progress: Progress = lambda s: None,
    ask: Ask | None = None,
    finder: Callable[[str], dict] = find_documents,
    pages_loader: Callable[[str], list[str]] = docs.get_pages,
    card_getter: Callable[[dict], dict] | None = None,
    pace: Callable[[dict], None] | None = None,
    link_finder: Callable[[str], str | None] = docs.linked_pdf,
    linked_loader: Callable[[str], list[str]] = docs.get_linked_pages,
    fin_getter: Callable[[str], dict | None] | None = None,
) -> dict:
    """Run the whole research for one ticker and return the JSON the Research screen shows."""
    if ask is None:
        from engine import llm
        ask = llm.ask_json
    card_getter = card_getter or (lambda f: cards.get_card(f, require_results=False))
    pace = pace or (lambda meta: time.sleep(config.RESEARCH_PACE_S) if meta.get("cached") is False else None)
    calls: list[dict] = []
    warnings: list[str] = []

    progress("Finding transcripts and results filings on NSE")
    found = finder(ticker)
    company, symbol = found["company"], found["symbol"]
    if not found["transcripts"]:
        raise LookupError(f"NSE has no earnings-call transcripts for {symbol} in the last 18 months, "
                          "so there are no promises to check.")

    # Actual numbers: results cards (block 7 extractor; cached, so repeat runs cost nothing).
    card_list: list[dict] = []
    for n, f in enumerate(found["results"], 1):
        progress(f"Reading results filing {n} of {len(found['results'])} ({f['date'][:10]})")
        card = card_getter({**f, "ticker": symbol, "company": company})
        if card.get("status") in ("ok", "partial"):
            card_list.append(card)
            pace(card.get("ai") or {})
        elif not f.get("candidate"):
            warnings.append(f"Results filed {f['date'][:10]} could not be read: {card.get('reason')}")
    facts = card_facts(card_list)
    latest_actual = max((date.fromisoformat(c["period"]["current"]) for c in card_list), default=None)

    # Promises: one cheap call per transcript; every quote verified against the PDF text.
    transcripts: list[dict] = []
    promises: list[dict] = []
    for n, t in enumerate(found["transcripts"], 1):
        tid = f"T{n}"
        label = _label_doc(t)
        progress(f"Reading the {label} transcript")
        source_url = t["pdf_url"]
        try:
            pages = pages_loader(source_url)
            if is_cover_letter(pages):
                # The NSE filing only links to the transcript on the company's own site: follow it.
                link = link_finder(source_url)
                if link:
                    pages, source_url = linked_loader(link), link
                    label += " (company website, linked from the NSE filing)"
        except (ValueError, RuntimeError) as exc:
            warnings.append(f"{label} transcript could not be downloaded: {exc}")
            continue
        if not any(p.strip() for p in pages):
            warnings.append(f"{label} transcript is a scanned image; FINN does not read text from images.")
            continue
        transcripts.append({"id": tid, "label": label, "quarter": fiscal_label(date.fromisoformat(t["quarter_end"])),
                            "quarter_end": t["quarter_end"], "date": t["date"], "pdf_url": source_url, "pages": pages})
        meta: dict = {}
        try:
            raw = extract_promises(ask, company, t, pages, meta)
        except (ValueError, RuntimeError) as exc:
            warnings.append(f"{label}: promises could not be extracted ({str(exc)[:120]}).")
            continue
        calls.append(meta)
        pace(meta)
        for p in raw:
            page, score = verify_quote(p["quote"], pages, p.get("page"))
            if page is None:
                warnings.append(f"Dropped a promise from the {label}: its quote was not found in the transcript.")
                continue
            if not quote_states_target(p["statement"], p["quote"]):
                warnings.append(f"Dropped a promise from the {label}: the quote does not state its target "
                                f"(\"{p['statement'][:60]}\").")
                continue
            due = _parse_due(p.get("due_quarter_end"))
            promises.append({
                "id": f"P{len(promises) + 1}", "metric": p["metric"], "statement": p["statement"].strip(),
                "period_text": p["period_text"], "due": due.isoformat() if due else None,
                "due_label": fiscal_label(due) if due else None, "made_in": transcripts[-1]["quarter"],
                "made_on": t["date"][:10], "quarter_end": t["quarter_end"],
                "receipt": {"quote": p["quote"].strip(), "page": page, "pdf_url": source_url, "doc": label,
                            "match": round(score, 2)},
            })

    promises = dedupe_promises(promises)

    # Segment, capex, tax and cash facts from the XBRL statements (10f, N1). No AI.
    progress("Reading segment, capex and cash figures")
    fin = None
    try:
        fin = (fin_getter or _default_fin)(symbol)
    except Exception as exc:          # NSE down: headline facts from the cards still work
        warnings.append(f"Segment and cash-flow figures could not be read ({str(exc)[:100]}); only headline numbers were used.")
    since = min((t["quarter_end"] for t in transcripts), default=None)
    facts += xbrl_facts(fin, len(facts) + 1, since)
    segment_names = sorted({s["name"] for q in (fin or {}).get("quarters", [])[:4] for s in q.get("segments") or []})

    # Timing and checkability are decided by Python; only the rest goes to the strong model.
    progress("Checking promises against the reported numbers")
    to_judge = []
    for p in promises:
        if not worth_judging(p, segment_names):
            p.update(verdict="Not checkable", fact_ids=[], decided_by="rules",
                     reason="FINN holds no filed figure for this (e.g. volumes, market share, exports, deals, dividends).")
        elif latest_actual and date.fromisoformat(p["quarter_end"]) >= latest_actual:
            p.update(verdict="Too early", fact_ids=[], decided_by="rules",
                     reason=f"Said in the latest call; no quarter has been reported since ({fiscal_label(latest_actual)} is the latest).")
        elif p["due"] and latest_actual and date.fromisoformat(p["due"]) > latest_actual:
            p.update(verdict="Too early", fact_ids=[], decided_by="rules",
                     reason=f"Due by {p['due_label']}; latest reported quarter is {fiscal_label(latest_actual)}.")
        else:
            to_judge.append(p)
    if to_judge and facts:
        meta = {}
        try:
            verdicts = judge(ask, company, to_judge, facts, meta)
            calls.append(meta)
            pace(meta)
        except (ValueError, RuntimeError) as exc:
            verdicts = {}
            warnings.append(f"The verdict step failed ({str(exc)[:120]}); verdicts are missing.")
        for p in to_judge:
            v = verdicts.get(p["id"]) or {"verdict": "Not checkable", "fact_ids": [], "reason": "No verdict returned."}
            p.update(v, decided_by="ai")
    for p in to_judge:
        p.setdefault("verdict", "Not checkable")
        p.setdefault("fact_ids", [])
        p.setdefault("reason", "No results figures available to check against.")
        p.setdefault("decided_by", "rules")
    fact_by_id = {f["id"]: f for f in facts}
    for p in promises:
        guard_verdict(p, fact_by_id)
        p["facts"] = [fact_by_id[i] for i in p.get("fact_ids", [])]
        p["say_do"] = say_do(p, fact_by_id) if p.get("verdict") in ("Delivered", "Partial", "Missed") else None
        p["guidance"] = is_guidance(p)

    # Tone vs numbers (N4): one cheap call over every call's opening remarks.
    progress("Comparing management's tone with the numbers")
    tone: list[dict] = []
    if transcripts:
        meta = {}
        try:
            tone = tone_vs_numbers(ask, company, transcripts, fin, meta)
            calls.append(meta)
            pace(meta)
        except (ValueError, RuntimeError) as exc:
            warnings.append(f"Tone vs numbers could not be built ({str(exc)[:120]}).")

    # Bull vs bear from the two latest transcripts and the facts (D-084, decision 7B).
    progress("Weighing bull and bear points")
    bb: dict = {"bull": [], "bear": []}
    if transcripts:
        meta = {}
        try:
            bb = bull_bear(ask, company, facts, transcripts[:2], meta)
            calls.append(meta)
            if bb.get("dropped"):
                warnings.append(f"Dropped {bb['dropped']} bull/bear point(s) without a verified source.")
        except (ValueError, RuntimeError) as exc:
            warnings.append(f"Bull vs bear could not be built ({str(exc)[:120]}).")
    for side in ("bull", "bear"):
        for pt in bb.get(side, []):
            pt["facts"] = [fact_by_id[i] for i in pt.get("fact_ids", [])]

    counts = {k: sum(1 for p in promises if p["verdict"] == k)
              for k in ("Delivered", "Partial", "Missed", "Too early", "Not checkable")}
    progress("Done")
    return {
        "ticker": symbol, "company": company, "status": "ready", "engine_version": ENGINE_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "latest_quarter": fiscal_label(latest_actual) if latest_actual else None,
        "counts": counts,
        "promises": promises,
        "bull": bb.get("bull", []), "bear": bb.get("bear", []),
        "tone": tone,
        "facts": facts,
        # What NSE listed when this was built (the refresh compares against it, D-090).
        "documents_seen": {"transcripts": sorted(t["date"][:10] for t in found["transcripts"]),
                           "results": sorted(str(f.get("id")) for f in found["results"])},
        "sources": {
            "transcripts": [{k: t[k] for k in ("id", "label", "date", "pdf_url")} for t in transcripts],
            "results": [{"filing_id": c.get("filing_id"), "period": c["period"]["label"], "basis": c.get("basis"),
                         "pdf_url": c.get("pdf_url")} for c in card_list],
        },
        "warnings": warnings,
        "ai": {"calls": len(calls), "cached": sum(1 for m in calls if m.get("cached")),
               "tokens_in": sum(m.get("tokens_in") or 0 for m in calls),
               "tokens_out": sum(m.get("tokens_out") or 0 for m in calls),
               "models": sorted({m.get("model") for m in calls if m.get("model")}),
               # D-088: say so when the weaker fallback model answered instead of the strong one
               "fallback_used": any(m.get("model") == config.FALLBACK_MODEL for m in calls)},
    }


def _numbers(text: str) -> frozenset[str]:
    """The target numbers in a statement, ignoring years ('FY30', 'FY 2030', '2030')."""
    t = re.sub(r"\bFY\s*'?\d{2,4}\b|\b20\d\d\b", " ", text or "", flags=re.I)
    return frozenset(re.findall(r"\d+(?:\.\d+)?", t))


def _same_promise(a: dict, b: dict, min_ratio: float) -> bool:
    """Same target said again: same numbers and due date, or very similar wording."""
    nums_a, nums_b = _numbers(a["statement"]), _numbers(b["statement"])
    if nums_a and nums_a == nums_b and a.get("due") == b.get("due"):
        return True
    return a["metric"] == b["metric"] and difflib.SequenceMatcher(
        None, norm(a["statement"]), norm(b["statement"])).ratio() >= min_ratio


def dedupe_promises(promises: list[dict], min_ratio: float = 0.5) -> list[dict]:
    """Merge a promise restated in later calls into the first time it was made.

    The original keeps its quote; `restated_in` lists the later calls (a held target is a signal).
    """
    ordered = sorted(promises, key=lambda p: p["made_on"])
    kept: list[dict] = []
    for p in ordered:
        twin = next((k for k in kept if _same_promise(k, p, min_ratio)), None)
        if twin:
            later = twin.setdefault("restated_in", [])
            if p["made_in"] != twin["made_in"] and p["made_in"] not in later:
                later.append(p["made_in"])
        else:
            kept.append(p)
    for n, p in enumerate(kept, 1):
        p["id"] = f"P{n}"
    return kept


def _parse_due(text: str | None) -> date | None:
    """A due quarter end from the model, snapped to a real quarter end; None if vague/invalid."""
    try:
        d = date.fromisoformat((text or "").strip()[:10])
    except ValueError:
        return None
    ends = {3: 31, 6: 30, 9: 30, 12: 31}
    if d.month not in ends:
        return None
    return date(d.year, d.month, ends[d.month])
