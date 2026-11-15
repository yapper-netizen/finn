"""Copilot in context (block 10g, D-107): ask about one stock or one results filing.

Answer routing, cheapest first (the brief's {smart model routing}):
1. Rules: price targets, buy/sell calls and news are refused (FINN reads filings, it does not advise).
2. Python: "what is X" number questions (revenue, margins, ROE, debt, capex, cash cycle, segments...)
   are answered from the XBRL statements (D-103) with a "computed by FINN" receipt. No AI.
3. Cheap model: everything else ("why", "what did management say"). It sees only the passages
   that best match the question (keyword retrieval over the transcripts or the filing's pages) and
   the stock's figures, and must cite them. Quotes are checked against the page (quote guard);
   figure ids must exist. An answer with no valid citation is not shown: FINN says it is not in
   the documents it read.
Answers are cached by question + context in the SQLite answer cache (llm.ask_json).
"""
from __future__ import annotations

import re
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from data import docs
from engine import llm
from engine.quotes import verify_quote

MAX_QUESTION = 300
_PASSAGE_CHARS = 700
_STOP = set("""a an the of in on for to and or is are was were be been it its this that what which who how why when
did does do has have had with by as at from about me tell show give last latest quarter year fy company management
their they them there than then so any some much many more most our we you i please""".split())

REFUSE = re.compile(r"\b(should i|buy or sell|sell call|price target|target price|share price|stock price|is it a buy|"
                    r"good buy|worth buying|valuation|undervalued|overvalued|news|rumou?r|stock tip)\b", re.I)
WHY = re.compile(r"^\s*(why|how come|explain|what (did|does) management|what is management|what are the risks?|"
                 r"what drove|what caused)|\b(said|say|guid|plan|expect|outlook|strategy|risk|concern|commentary|"
                 r"management|call|why)\b", re.I)


# ------------------------------------------------------------------ helpers

def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _STOP and len(w) > 1]


def passages(pages: list[str], size: int = _PASSAGE_CHARS) -> list[tuple[int, str]]:
    """Split pages into (page number, chunk) pieces of about `size` characters, on paragraph breaks."""
    out: list[tuple[int, str]] = []
    for i, page in enumerate(pages):
        buf = ""
        for para in re.split(r"\n\s*\n|\n(?=[A-Z][a-z]+ [A-Z][a-z]+:)", page):
            if len(buf) + len(para) > size and buf:
                out.append((i + 1, buf.strip()))
                buf = ""
            buf += para + "\n"
        if buf.strip():
            out.append((i + 1, buf.strip()))
    return out


def rank(question: str, items: list[str], k: int) -> list[int]:
    """Indexes of the k items sharing the most question words (rarer words count more)."""
    q = set(words(question))
    if not q:
        return []
    df = {w: sum(1 for t in items if w in t.lower()) for w in q}
    scored = []
    for i, t in enumerate(items):
        tl = t.lower()
        s = sum(1.0 / (1 + df[w]) * min(tl.count(w), 3) for w in q if w in tl)
        if s > 0:
            scored.append((s, i))
    return [i for _, i in sorted(scored, reverse=True)[:k]]


def refusal(text: str, suggestions: list[str] | None = None) -> dict:
    return {"answer": text, "refused": True, "answered_by": "rules", "citations": [], "suggestions": suggestions or []}


# ------------------------------------------------------------------ 2. Python answers from the figures

def _pick_quarter(question: str, quarters: list[dict]) -> dict:
    m = re.search(r"\bq([1-4])\s*'?\s*fy\s*'?(\d{2})\b", question, re.I)
    if m:
        label = f"Q{m.group(1)} FY{m.group(2)}"
        for q in quarters:
            if q["label"] == label:
                return q
    return quarters[0]


def _fig(title: str, value: str, formula: str, inputs: list[str], url: str | None, src: str) -> dict:
    return {"kind": "figure", "title": title, "value": value, "formula": formula, "inputs": inputs, "url": url, "src": src}


def _cr(v: float | None) -> str:
    return "n/a" if v is None else f"{'−' if v < 0 else ''}₹{abs(v):,.0f} cr"


def _pct(v: float | None, signed: bool = False) -> str:
    return "n/a" if v is None else (f"{v:+.1f}%" if signed else f"{v:.1f}%")


def number_answer(question: str, fin: dict | None) -> dict | None:
    """A Python answer for a plain number question, or None if the question is not one."""
    if not fin or not fin.get("quarters") or WHY.search(question):
        return None
    t = question.lower()
    q = _pick_quarter(question, fin["quarters"])
    r, bs = fin.get("ratios") or {}, (fin.get("balance_sheets") or [{}])[0]
    src = f"NSE results data (XBRL), {q['label']}, {fin.get('basis', '')}"
    url = q.get("url")
    ans: tuple[str, dict] | None = None
    if re.search(r"ebitda margin|operating margin", t) and not fin.get("bank"):
        ans = (f"EBITDA margin was {_pct(q.get('ebitda_margin'))} in {q['label']} (computed: PBT + finance costs + depreciation − other income).",
               _fig(f"EBITDA margin, {q['label']}", _pct(q.get("ebitda_margin")), "EBITDA ÷ revenue; EBITDA computed from the filed lines.",
                    [f"EBITDA {_cr(q.get('ebitda'))}", f"Revenue {_cr(q.get('revenue'))}"], url, src))
    elif re.search(r"\bebitda\b", t) and not fin.get("bank"):
        ans = (f"EBITDA was {_cr(q.get('ebitda'))} in {q['label']}, {_pct(q.get('ebitda_yoy'), True)} on a year ago (computed).",
               _fig(f"EBITDA, {q['label']}", _cr(q.get("ebitda")), "Profit before tax + finance costs + depreciation − other income.",
                    [f"PBT {_cr(q.get('pbt'))}", f"Finance costs {_cr(q.get('finance_costs'))}", f"Depreciation {_cr(q.get('dep'))}",
                     f"Other income {_cr(q.get('other_income'))}"], url, src))
    elif re.search(r"(pat|net profit|profit) margin", t):
        ans = (f"PAT margin was {_pct(q.get('pat_margin'))} in {q['label']}.",
               _fig(f"PAT margin, {q['label']}", _pct(q.get("pat_margin")), "Profit after tax ÷ revenue.",
                    [f"PAT {_cr(q.get('pat'))}", f"Revenue {_cr(q.get('revenue'))}"], url, src))
    elif re.search(r"\b(pat|net profit|profit after tax|profit|earnings)\b", t):
        ans = (f"Profit after tax was {_cr(q.get('pat'))} in {q['label']}, {_pct(q.get('pat_yoy'), True)} on a year ago "
               f"and {_pct(q.get('pat_qoq'), True)} on the previous quarter.",
               _fig(f"Profit after tax, {q['label']}", _cr(q.get("pat")), "As filed (owners' share).", [], url, src))
    elif re.search(r"\broce\b|return on capital", t) and r.get("roce") is not None:
        ans = (f"ROCE was {_pct(r.get('roce'))} for the 12 months to {r.get('label')}.",
               _fig("Return on capital employed", _pct(r.get("roce")), "12-month EBIT ÷ average (equity + debt).",
                    [f"Equity {_cr(bs.get('equity'))}", f"Debt {_cr(bs.get('debt'))}"], url, src))
    elif re.search(r"\broe\b|return on equity", t):
        ans = (f"ROE was {_pct(r.get('roe'))} for the 12 months to {r.get('label')} (on {r.get('roe_basis')}).",
               _fig("Return on equity", _pct(r.get("roe")), "12-month profit ÷ shareholders' equity.",
                    [f"12-month PAT {_cr(r.get('ttm_pat'))}", f"Equity {_cr(bs.get('equity'))}"], url, src))
    elif re.search(r"\bdebt\b|leverage|d/e|borrow|net cash", t) and not fin.get("bank"):
        nc = bs.get("net_cash")
        ans = (f"Borrowings were {_cr(bs.get('debt'))} against equity of {_cr(bs.get('equity'))} (debt ÷ equity {bs.get('de_ratio')}); "
               f"net {'cash' if (nc or 0) >= 0 else 'debt'} {_cr(abs(nc or 0))} as of {bs.get('as_of')}.",
               _fig("Debt and net cash", _cr(abs(nc or 0)), "Cash + bank balances + current investments − borrowings.",
                    [f"Cash and liquid investments {_cr(bs.get('cash'))}", f"Borrowings {_cr(bs.get('debt'))}"], bs.get("url"), src))
    elif re.search(r"working capital|cash cycle|inventory days|receivable|debtor days", t) and r.get("cash_cycle_days") is not None:
        ans = (f"Cash cycle was {r['cash_cycle_days']} days: inventory {r['inventory_days']} + customers {r['receivable_days']} − "
               f"suppliers {r['payable_days']} days of revenue (as of {r.get('as_of')}).",
               _fig("Cash cycle", f"{r['cash_cycle_days']} days", "Inventory + receivable − payable days, on 12-month revenue.",
                    [f"Inventory {_cr(bs.get('inventories'))}", f"Receivables {_cr(bs.get('receivables'))}", f"Payables {_cr(bs.get('payables'))}"], bs.get("url"), src))
    elif re.search(r"capex|capital expenditure", t) and fin.get("cash_flows"):
        lines = [f"{h['label']}: {_cr(h.get('capex'))}" for h in fin["cash_flows"][:3]]
        h = fin["cash_flows"][0]
        ans = (f"Capex was {_cr(h.get('capex'))} in {h['label']} (purchase of fixed assets, cash flow statement); earlier: "
               + "; ".join(lines[1:]) + ".", _fig("Capex", _cr(h.get("capex")), "Purchase of property, plant, equipment and intangibles.", lines, h.get("url"), src))
    elif re.search(r"cash conversion|cash flow|operating cash|free cash|\bfcf\b|\bcfo\b", t) and fin.get("cash_flows"):
        h = fin["cash_flows"][0]
        ans = (f"In {h['label']}, cash from operations was {_cr(h.get('cfo'))} against profit of {_cr(h.get('pat'))} "
               f"(conversion {_pct(h.get('cash_conversion'))}); free cash after capex {_cr(h.get('fcf'))}.",
               _fig(f"Cash flow, {h['label']}", _pct(h.get("cash_conversion")), "Cash from operations ÷ profit after tax; FCF = CFO − capex.",
                    [f"CFO {_cr(h.get('cfo'))}", f"PAT {_cr(h.get('pat'))}", f"Capex {_cr(h.get('capex'))}"], h.get("url"), src))
    elif re.search(r"segment|mix|business split|revenue split", t) and q.get("segments"):
        tot = sum(s["revenue"] or 0 for s in q["segments"]) or 1
        parts = [f"{s['name']} {100 * s['revenue'] / tot:.0f}%" + (f" (margin {s['margin']:.1f}%)" if s.get("margin") is not None else "")
                 for s in q["segments"]]
        ans = (f"In {q['label']}: " + ", ".join(parts) + ". Margins are segment results before interest and tax.",
               _fig(f"Segment mix, {q['label']}", f"{len(parts)} segments", "Segment revenue ÷ total segment revenue.", parts, url, src))
    elif re.search(r"tax rate", t):
        tax, pbt = q.get("tax"), q.get("pbt")
        rate = None if not tax or not pbt else 100 * tax / pbt
        ans = (f"Effective tax rate was {_pct(rate)} in {q['label']} (tax ÷ profit before tax).",
               _fig(f"Tax rate, {q['label']}", _pct(rate), "Tax expense ÷ profit before tax.", [f"Tax {_cr(tax)}", f"PBT {_cr(pbt)}"], url, src))
    elif re.search(r"revenue|sales|top ?line|total income|grow", t):
        name = "Total income" if fin.get("bank") else "Revenue"
        ans = (f"{name} was {_cr(q.get('revenue'))} in {q['label']}, {_pct(q.get('revenue_yoy'), True)} on a year ago and "
               f"{_pct(q.get('revenue_qoq'), True)} on the previous quarter; {_cr(r.get('ttm_revenue'))} over 12 months.",
               _fig(f"{name}, {q['label']}", _cr(q.get("revenue")), "As filed; growth computed by FINN.",
                    [f"YoY {_pct(q.get('revenue_yoy'), True)}", f"QoQ {_pct(q.get('revenue_qoq'), True)}"], url, src))
    if not ans:
        return None
    return {"answer": ans[0], "refused": False, "answered_by": "python", "citations": [ans[1]], "suggestions": []}


# ------------------------------------------------------------------ 3. grounded AI answer

class Cite(BaseModel):
    passage: str | None = None   # passage id, e.g. "P3"
    quote: str | None = None     # words copied exactly from that passage
    fact: str | None = None      # figure id, e.g. "F12"


class AnswerOut(BaseModel):
    answer: str
    found: bool
    citations: list[Cite]


PROMPT = """You answer an investor's question about {company} using ONLY the material below: passages from
{doc_desc}, and figures computed by FINN from the company's filings. No outside knowledge, no
opinions, no advice, no forecasts of your own.

QUESTION: {question}

PASSAGES (id [doc, page]: text):
{passages}

FIGURES (id: figure):
{facts}

Return:
- answer: at most 3 short sentences in plain English, every claim supported by a citation.
  Say "management says" for management's claims. If the material does not answer the question,
  set found=false and answer "Not in the documents FINN read."
- citations: for each claim, either {{"passage": "P3", "quote": "<8-40 words copied exactly from P3>"}}
  or {{"fact": "F12"}}.
"""


def ai_answer(question: str, company: str, docs_pages: list[dict], facts: list[dict], doc_desc: str,
              ask: Callable[..., Any], k: int = 6) -> dict:
    """Retrieve, ask the cheap model, verify every citation; refuse if nothing survives."""
    chunks: list[dict] = []
    for d in docs_pages:
        for page, text in passages(d["pages"]):
            chunks.append({"doc": d, "page": page, "text": text})
    top = [chunks[i] for i in rank(question, [c["text"] for c in chunks], k)]
    top_facts = [facts[i] for i in rank(question, [f["text"] for f in facts], 12)] or facts[:8]
    if not top and not top_facts:
        return refusal("Not in the documents FINN read.")
    pid = {f"P{n + 1}": c for n, c in enumerate(top)}
    fid = {f["id"]: f for f in top_facts}
    meta: dict = {}

    def check(obj: Any) -> AnswerOut:
        try:
            return AnswerOut.model_validate(obj)
        except ValidationError as exc:
            raise ValueError(f"AI answer has the wrong shape: {exc.errors()[0]['msg']}") from exc
    out = ask(PROMPT.format(company=company, doc_desc=doc_desc, question=question[:MAX_QUESTION],
                            passages="\n\n".join(f"{p} [{c['doc']['label']}, p.{c['page']}]: {c['text']}" for p, c in pid.items()) or "(none)",
                            facts="\n".join(f"{f['id']}: {f['text']}" for f in top_facts) or "(none)"),
              strong=False, validate=check, use_cache=True, meta=meta, schema=AnswerOut)
    cites: list[dict] = []
    for c in out.citations:
        if c.passage in pid and c.quote:
            chunk = pid[c.passage]
            page, score = verify_quote(c.quote, chunk["doc"]["pages"], chunk["page"])
            if page:
                cites.append({"kind": "quote", "quote": c.quote.strip(), "page": page, "pdf_url": chunk["doc"]["pdf_url"],
                              "doc": chunk["doc"]["label"], "match": round(score, 2)})
        elif c.fact in fid:
            f = fid[c.fact]
            cites.append({"kind": "fact", "text": f["text"], "pdf_url": (f.get("source") or {}).get("pdf_url"),
                          "page": (f.get("source") or {}).get("page")})
    ai_meta = {"model": meta.get("model"), "tokens_in": meta.get("tokens_in", 0), "tokens_out": meta.get("tokens_out", 0),
               "cached": meta.get("cached", False)}
    if not out.found or not cites:
        r = refusal("Not in the documents FINN read." if not out.found else
                    "FINN could not verify a source for this answer, so it is not shown.")
        r["ai"], r["answered_by"] = ai_meta, "ai"
        return r
    return {"answer": out.answer.strip(), "refused": False, "answered_by": "ai", "citations": cites, "suggestions": [], "ai": ai_meta}


# ------------------------------------------------------------------ context + entry point

def _load(url: str) -> list[str]:
    try:
        return docs.get_pages(url)
    except ValueError:
        return docs.get_linked_pages(url)


def suggestions(research: dict | None, fin: dict | None) -> list[str]:
    """Three useful questions for this stock, built from what FINN holds."""
    out: list[str] = []
    q = (fin or {}).get("quarters", [{}])[0] if fin and fin.get("quarters") else {}
    if q.get("ebitda_margin") is not None and len(fin["quarters"]) > 1:
        prev = fin["quarters"][1].get("ebitda_margin")
        if prev is not None:
            out.append(f"Why did EBITDA margin {'rise' if q['ebitda_margin'] >= prev else 'fall'} in {q['label']}?")
    segs = q.get("segments") or []
    if segs:
        top = max(segs, key=lambda s: s.get("revenue") or 0)["name"]
        out.append(f"What did management say about {top}?")
    out.append("What is the capex plan?")
    out.append("What are analysts worried about?")
    return out[:3]


def ask_stock(question: str, symbol: str, research: dict | None, fin: dict | None,
              ask: Callable[..., Any] | None = None, loader: Callable[[str], list[str]] = _load) -> dict:
    """Copilot for one stock: rules → Python figures → grounded cheap-model answer."""
    question = (question or "").strip()[:MAX_QUESTION]
    sugg = suggestions(research, fin)
    if len(words(question)) == 0:
        return refusal("Ask about this company's numbers or what its management said.", sugg)
    if REFUSE.search(question):
        return refusal("FINN answers only from the company's filings and calls. It does not give price targets, "
                       "buy or sell calls, or news.", sugg)
    num = number_answer(question, fin)
    if num:
        num["suggestions"] = sugg
        return num
    if not research:
        return refusal("Run the research for this stock first; FINN answers from the calls it has read.", sugg)
    docs_pages = []
    for t in research.get("sources", {}).get("transcripts", [])[:3]:
        try:
            docs_pages.append({"label": t["label"], "pdf_url": t["pdf_url"], "pages": loader(t["pdf_url"])})
        except (ValueError, RuntimeError):
            continue
    out = ai_answer(question, research.get("company") or symbol, docs_pages, research.get("facts", []),
                    "the company's latest earnings-call transcripts", ask or llm.ask_json)
    if out["refused"]:
        # The calls do not explain it; if FINN holds the figure, say so and show it (never guess a reason).
        plain = WHY.sub(" ", question)
        num = number_answer(plain, fin)
        if num:
            out.update(answer="Management did not explain this in the calls FINN read. What the filings show: " + num["answer"],
                       refused=False, answered_by="python", citations=num["citations"])
    out["suggestions"] = sugg
    return out


def card_facts(card: dict) -> list[dict]:
    """A results card's lines as citable figures."""
    out = []
    for m in card.get("metrics", []):
        if not m.get("available"):
            continue
        v = m.get("values") or {}
        out.append({"id": f"F{len(out) + 1}", "text": f"{m['label']} {card.get('period', {}).get('label', '')}: ₹{v.get('current'):,.2f} cr"
                    + (f", {m['yoy_pct']:+.1f}% YoY" if m.get("yoy_pct") is not None else "")
                    + (f", {m['qoq_pct']:+.1f}% QoQ" if m.get("qoq_pct") is not None else ""),
                    "source": {"pdf_url": card.get("pdf_url"), "page": (m.get("source") or {}).get("page")}})
    for g in card.get("margins") or []:
        cur = (g.get("values") or {}).get("current")
        if cur is not None:
            out.append({"id": f"F{len(out) + 1}", "text": f"{g['label']}: {cur:.1f}%", "source": {"pdf_url": card.get("pdf_url"), "page": None}})
    return out


def ask_filing(question: str, card: dict, ask: Callable[..., Any] | None = None,
               loader: Callable[[str], list[str]] = _load) -> dict:
    """Copilot on one results filing: the card's figures + the filing's own pages."""
    question = (question or "").strip()[:MAX_QUESTION]
    sugg = ["What drove the change in profit?", "Were there any exceptional items?", "What do the notes to the results say?"]
    if not words(question):
        return refusal("Ask about this results filing.", sugg)
    if REFUSE.search(question):
        return refusal("FINN answers only from the filing. It does not give price targets, buy or sell calls, or news.", sugg)
    pages = []
    try:
        pages = [{"label": f"{card.get('company', card.get('ticker'))} results filing", "pdf_url": card["pdf_url"],
                  "pages": loader(card["pdf_url"])}]
    except (ValueError, RuntimeError, KeyError):
        pass
    out = ai_answer(question, card.get("company") or card.get("ticker", ""), pages, card_facts(card),
                    "the company's results filing", ask or llm.ask_json)
    out["suggestions"] = sugg
    return out
