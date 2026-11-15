"""Company profile: "what the company does", written by AI from the company's own words (D-094).

Stages (the NUS pipeline shape, D-102):
1. Relevance filter: from the latest earnings-call transcripts, keep only pages that describe the
   business (opening remarks, segments, products, customers, channels), up to a character budget.
2. Structured extraction (cheap model, one call): 3-5 plain sentences in the model's own words +
   one line per business segment. Each item must carry a short passage copied from the text.
3. Verify: the passage must be found on the cited page (quote guard, D-083), and every number in
   the sentence must appear in its passage. Anything unsupported is dropped and counted.
The sentence is a paraphrase; its receipt is the verified passage and page. No outside knowledge.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

import config
from data import docs
from engine import llm
from engine.quotes import norm, verify_quote

ENGINE_VERSION = 1
CHAR_BUDGET = 22000
_KEYWORDS = ("we are", "company", "segment", "business", "product", "portfolio", "customer", "channel",
             "distribut", "dealer", "market share", "manufactur", "plant", "capacity", "brand", "export",
             "revenue mix", "contribut", "vertical", "client", "service", "leader", "largest", "presence")


class Item(BaseModel):
    text: str = Field(description="One plain sentence in your own words, at most 30 words")
    quote: str = Field(description="8-40 consecutive words copied exactly from the text that support the sentence")
    page: int = Field(description="Page number of the quote, as marked in the text")


class SegmentItem(Item):
    name: str = Field(description="Segment or business line name as the company uses it")


class ProfileOut(BaseModel):
    sentences: list[Item]
    segments: list[SegmentItem] = []


PROMPT = """You are describing {company} for a long-term investor, using ONLY the earnings-call text below
(the company's own words). Do not use anything you may know about the company from elsewhere.

Write:
- "sentences": 4 to 6 short sentences, in plain English and your own words, covering in order:
  (1) what the company sells or does (always include this one); (2) who its customers are and how
  it reaches them; (3) how its business is split (segments, geographies or products) and which part
  is growing fastest, if the text says so; (4) where it is investing (capacity, products, markets);
  (5) anything management says sets it apart.
  Write "management says ..." for claims about being a leader or the best.
- "segments": one item per business segment the text describes (name + what it does), at most 5.
  Known segment names from the results filings: {segments}.
For EVERY item give "quote": 8 to 40 consecutive words copied exactly from the text that support
it, and "page": the page number shown in the [page N] marker before the quote.
Use numbers only if they appear in your quote. If the text does not say something, leave it out.

TEXT:
{text}
"""


# ------------------------------------------------------------------ stage 1: relevance filter

def page_score(text: str) -> int:
    """How much a page talks about the business itself (keyword hits, capped per keyword)."""
    t = text.lower()
    return sum(min(t.count(k), 3) for k in _KEYWORDS)


def pick_pages(pages: list[str], budget: int = CHAR_BUDGET) -> list[int]:
    """Opening remarks (first content pages) + the best-scoring pages, in page order, within budget."""
    content = [i for i, p in enumerate(pages) if len(p.strip()) > 400]
    if not content:
        return []
    chosen: list[int] = content[1:3] if len(content) > 3 else content[:2]   # skip the cover/disclaimer page
    ranked = sorted(content, key=lambda i: page_score(pages[i]), reverse=True)
    used = sum(len(pages[i]) for i in chosen)
    for i in ranked:
        if i in chosen:
            continue
        if used + len(pages[i]) > budget:
            continue
        chosen.append(i)
        used += len(pages[i])
    return sorted(chosen)


# ------------------------------------------------------------------ stage 3: verification

def numbers_supported(sentence: str, quote: str) -> bool:
    """Every number in the sentence appears in its quote (no invented figures)."""
    nums = set(re.findall(r"\d+(?:\.\d+)?", sentence.replace(",", "")))
    return nums <= set(re.findall(r"\d+(?:\.\d+)?", quote.replace(",", "")))


def verify_items(items: list[dict], pages: list[str], url: str, doc: str) -> tuple[list[dict], int]:
    """Keep items whose quote is on a page and whose numbers are in the quote; count the rest."""
    kept: list[dict] = []
    dropped = 0
    for it in items:
        text, quote = (it.get("text") or "").strip(), (it.get("quote") or "").strip()
        if not text or len(norm(quote).split()) < 6 or not numbers_supported(text, quote):
            dropped += 1
            continue
        page, score = verify_quote(quote, pages, it.get("page"))
        if page is None:
            dropped += 1
            continue
        out = {"text": text, "receipt": {"quote": quote, "page": page, "pdf_url": url, "doc": doc,
                                         "match": round(score, 2)}}
        if it.get("name"):
            out["name"] = it["name"].strip()
        kept.append(out)
    return kept, dropped


# ------------------------------------------------------------------ build

def _load_pages(url: str) -> list[str]:
    try:
        return docs.get_pages(url)
    except ValueError:              # the transcript lives on the company's own site (D-079)
        return docs.get_linked_pages(url)


def build(research: dict, segments: list[str] | None = None, ask: Callable[..., Any] | None = None,
          pages_loader: Callable[[str], list[str]] = _load_pages) -> dict:
    """Profile from the latest transcript that has text. One cheap AI call (cached by prompt)."""
    ask = ask or llm.ask_json
    company = research.get("company") or research["ticker"]
    for t in research.get("sources", {}).get("transcripts", [])[:2]:
        try:
            pages = pages_loader(t["pdf_url"])
        except (ValueError, RuntimeError):
            continue
        idx = pick_pages(pages)
        if idx:
            break
    else:
        raise LookupError(f"No readable earnings-call transcript for {company}.")
    text = "\n\n".join(f"[page {i + 1}]\n{pages[i]}" for i in idx)
    meta: dict = {}

    def check(obj: Any) -> ProfileOut:
        try:
            return ProfileOut.model_validate(obj)
        except ValidationError as exc:
            raise ValueError(f"AI answer has the wrong shape: {exc.errors()[0]['msg']}") from exc
    out = ask(PROMPT.format(company=company, segments=", ".join(segments or []) or "not given", text=text),
              strong=False, validate=check, use_cache=True, meta=meta, schema=ProfileOut)
    doc = t["label"]                     # the receipt sheet adds "transcript, page N"
    sentences, d1 = verify_items([s.model_dump() for s in out.sentences[:6]], pages, t["pdf_url"], doc)
    segs, d2 = verify_items([s.model_dump() for s in out.segments[:5]], pages, t["pdf_url"], doc)
    return {
        "ticker": research["ticker"], "company": company, "engine_version": ENGINE_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "status": "ready" if len(sentences) >= 2 else "thin",
        "sentences": sentences, "segments": segs, "dropped": d1 + d2,
        "source": {"doc": doc, "pdf_url": t["pdf_url"], "pages_read": [i + 1 for i in idx]},
        "ai": {"model": meta.get("model"), "tokens_in": meta.get("tokens_in", 0), "tokens_out": meta.get("tokens_out", 0),
               "cached": meta.get("cached", False), "calls": 0 if meta.get("cached") else 1},
    }


# ------------------------------------------------------------------ store

def _paths(symbol: str) -> list[Path]:
    return [Path(config.PROFILES_DIR) / f"{symbol}.json", Path(config.CACHE_DIR) / "profiles" / f"{symbol}.json"]


def stored(symbol: str) -> dict | None:
    for path in _paths(symbol):
        if path.exists():
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if d.get("engine_version") == ENGINE_VERSION:
                return d
    return None


def save(result: dict, snapshot: bool = False) -> None:
    path = _paths(result["ticker"])[0 if snapshot else 1]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
