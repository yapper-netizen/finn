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

ENGINE_VERSION = 1
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

def norm(text: str) -> str:
    """Lowercase, re-join words split by a line-break hyphen, keep letters and digits only."""
    t = re.sub(r"-\s*\n\s*", "", (text or "").lower())
    t = t.replace("’", "'").replace("‘", "'")
    return " ".join(re.findall(r"[a-z0-9]+", t))


def quote_score(quote: str, page_text: str) -> float:
    """How well a quote matches somewhere in a page: 1.0 = verbatim (after normalising)."""
    q, page = norm(quote), norm(page_text)
    if not q:
        return 0.0
    if q in page:
        return 1.0
    qw, pw = q.split(), page.split()
    n = len(qw)
    if n < 4 or len(pw) < n:
        return 0.0
    best = 0.0
    matcher = difflib.SequenceMatcher(autojunk=False)
    matcher.set_seq2(q)
    first = set(qw[:3])
    for start in range(0, len(pw) - n + 1):
        if pw[start] not in first and start % 3:   # cheap skip: try likely starts, plus every 3rd word
            continue
        matcher.set_seq1(" ".join(pw[start:start + n]))
        if matcher.real_quick_ratio() < best or matcher.quick_ratio() < best:
            continue
        best = max(best, matcher.ratio())
        if best >= 0.99:
            break
    return best


def verify_quote(quote: str, pages: list[str], hint_page: int | None) -> tuple[int | None, float]:
    """(1-based page where the quote is found, score); page is None if below QUOTE_MATCH_MIN.

    The model's page is tried first; if the quote is on another page, that page is cited instead.
    """
    q = norm(quote)
    for i, text in enumerate(pages):          # fast path: verbatim on some page
        if q and q in norm(text):
            return i + 1, 1.0
    q_nums = set(re.findall(r"[0-9]+", q))     # a fuzzy match may never change a number
    order = list(range(len(pages)))
    if hint_page and 1 <= hint_page <= len(pages):
        order.remove(hint_page - 1)
        order.insert(0, hint_page - 1)
    best_page, best = None, 0.0
    for i in order:
        if not q_nums <= set(re.findall(r"[0-9]+", norm(pages[i]))):
            continue
        s = quote_score(quote, pages[i])
        if s > best:
            best_page, best = i + 1, s
        if s >= 0.99:
            break
    return (best_page, best) if best >= config.QUOTE_MATCH_MIN else (None, best)


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
        facts.append({"id": f"F{len(facts) + 1}", "metric": metric, "quarter": quarter, "text": text, "value": value,
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


# ---------------------------------------------------------------- verdicts (EN-13)

class VerdictOut(BaseModel):
    promise_id: str
    verdict: Literal["Delivered", "Partial", "Missed", "Not checkable"]
    fact_ids: list[str]
    reason: str


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
                                "reason": v.reason.strip()[:240]}
    return result


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

    # Timing and checkability are decided by Python; only the rest goes to the strong model.
    progress("Checking promises against the reported numbers")
    to_judge = []
    for p in promises:
        if p["metric"] not in CHECKABLE:
            p.update(verdict="Not checkable", reason="Not a company-level number in the results filings.", fact_ids=[],
                     decided_by="rules")
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
        p["facts"] = [fact_by_id[i] for i in p.get("fact_ids", [])]

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
        "facts": facts,
        "sources": {
            "transcripts": [{k: t[k] for k in ("id", "label", "date", "pdf_url")} for t in transcripts],
            "results": [{"filing_id": c.get("filing_id"), "period": c["period"]["label"], "basis": c.get("basis"),
                         "pdf_url": c.get("pdf_url")} for c in card_list],
        },
        "warnings": warnings,
        "ai": {"calls": len(calls), "cached": sum(1 for m in calls if m.get("cached")),
               "tokens_in": sum(m.get("tokens_in") or 0 for m in calls),
               "tokens_out": sum(m.get("tokens_out") or 0 for m in calls),
               "models": sorted({m.get("model") for m in calls if m.get("model")})},
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
