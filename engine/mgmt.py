"""Management-change card (EN-6, D-087): who joined or left, in what role, from when, and the
incoming person's background, all from the exchange filing itself (D-019 = A).

- The filing's SEBI annexure (reason, date, brief profile) is the only source. No LinkedIn, no
  outside knowledge.
- The cheap model copies each change into JSON; Python then checks it against the PDF text:
  the person's name must be in the filing, the profile quote must be found (same quote guard as
  research), and the effective date must be printed. Anything unverified is dropped or blanked.
- "Key role" is a Python rule on the role title (CEO, MD, CFO, Chair, whole-time director...).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable, Literal

from pydantic import BaseModel, ValidationError

import config
from engine.research import norm, verify_quote

Event = Literal["appointment", "reappointment", "resignation", "retirement", "cessation", "role_change",
                "auditor_change", "other"]


class ChangeOut(BaseModel):
    event: Event
    person: str
    role: str
    previous_role: str | None
    effective_date: str | None
    reason: str | None
    profile_quote: str | None
    bio: str | None
    page: int | None


class MgmtOut(BaseModel):
    changes: list[ChangeOut]


PROMPT = """You read a stock-exchange filing by an Indian listed company about a change in its
directors, key managerial personnel, senior management or auditors.
List every change in it. For each:
- event: appointment, reappointment, resignation, retirement, cessation, role_change (same person,
  new role), auditor_change, or other.
- person: the person's full name as printed, without Mr./Ms./Dr. (for auditors: the firm's name).
- role: the role they take up (for exits: the role they leave), as printed.
- previous_role: their earlier role if the filing says so, else null.
- effective_date: YYYY-MM-DD if the filing gives one, else null.
- reason: the stated reason in at most 15 words, else null.
- profile_quote: copy 1-3 sentences VERBATIM from the "Brief profile" section about this person
  (education, experience). null if the filing has no profile for them ("Not applicable", or it says
  the profile was disclosed earlier).
- bio: if profile_quote is given, a 1-2 sentence plain summary of THAT text only; else null.
- page: the page number where this person's details are.
Use only the filing text below. No outside knowledge.

FILING TEXT:
{text}
"""

_KEY_ROLE = re.compile(
    r"chief executive|\bceo\b|managing director|\bmd\b|chief financial|\bcfo\b|chair(man|person)?\b|"
    r"whole[- ]?time director|executive director|chief operating|\bcoo\b|vice[- ]chair", re.I)
_EVENT_LABEL = {"appointment": "Appointed", "reappointment": "Re-appointed", "resignation": "Resigned",
                "retirement": "Retiring", "cessation": "Ceases", "role_change": "New role",
                "auditor_change": "Auditor change", "other": "Change"}
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december"]


_PART_OF_BUSINESS = re.compile(
    r"\bvice president\b|\bfor\b|\bbusiness\b|\bunit\b|\bdivision\b|\bregion|\bsegment\b|\bsubsidiar", re.I)


def is_key_role(role: str | None) -> bool:
    """Company-level CEO, MD, CFO, Chair, whole-time/executive director, COO (not a unit's CEO)."""
    return bool(role and _KEY_ROLE.search(role) and not _PART_OF_BUSINESS.search(role))


def words_in_order(quote: str, page_text: str, max_spread: float = 3.0) -> bool:
    """All words of the quote appear in order on the page, within a short span.

    For two-column annexure tables, whose PDF text interleaves the two columns: the exact words
    (so the exact numbers) must be there, in order, with only the other column's words between.
    """
    q, words = norm(quote).split(), norm(page_text).split()
    if len(q) < 6:
        return False
    for start in (i for i, w in enumerate(words) if w == q[0]):
        k, i = 0, start
        while i < len(words) and k < len(q) and i - start <= max_spread * len(q):
            if words[i] == q[k]:
                k += 1
            i += 1
        if k == len(q):
            return True
    return False


def role_in_text(role: str, pages: list[str]) -> bool:
    """The role's words are printed (a role can be split across table cells)."""
    rw = [w for w in norm(role).split() if len(w) > 2]
    body = set(norm("\n".join(pages)).split())
    return bool(rw) and sum(w in body for w in rw) / len(rw) >= 0.85


def name_in_text(name: str, text: str) -> bool:
    """Every word of the name (minus titles and initials) is printed in the filing."""
    words = [w for w in norm(re.sub(r"\b(mr|ms|mrs|dr|shri|smt)\b\.?", " ", name, flags=re.I)).split() if len(w) > 1]
    body = f" {norm(text)} "
    return bool(words) and all(f" {w} " in body for w in words)


def date_in_text(d: date, text: str) -> bool:
    """The date is printed in some common form (16th November 2026, 16.11.2026, November 16, 2026)."""
    t = norm(text)
    m = _MONTHS[d.month - 1]
    forms = [f"{d.day} {m} {d.year}", f"{d.day}th {m} {d.year}", f"{d.day}st {m} {d.year}", f"{d.day}nd {m} {d.year}",
             f"{d.day}rd {m} {d.year}", f"{m} {d.day} {d.year}", f"{m} {d.day}th {d.year}",
             f"{d.day:02d} {d.month:02d} {d.year}", f"{d.day} {d.month} {d.year}", f"{d.day} {m[:3]} {d.year}",
             f"{d.day:02d} {m} {d.year}", f"{m} {d.day:02d} {d.year}", f"{d.day:02d}th {m} {d.year}"]
    padded = f" {t} "
    return any(f" {f} " in padded for f in forms)   # whole words: 3 Nov must not match 13 Nov


def _validate(obj: Any) -> MgmtOut:
    try:
        return MgmtOut.model_validate(obj)
    except ValidationError as exc:
        err = exc.errors()[0]
        raise ValueError(f"AI answer has the wrong shape at {'.'.join(map(str, err['loc']))}: {err['msg']}") from exc


def ai_extract(prompt: str, meta: dict) -> MgmtOut:
    from engine import llm
    return llm.ask_json(prompt, strong=False, validate=_validate, use_cache=True, meta=meta, schema=MgmtOut)


def check_change(c: ChangeOut, pages: list[str], warnings: list[str]) -> dict | None:
    """Python checks of one change against the filing text; None if the person is not in it."""
    text = "\n".join(pages)
    if not name_in_text(c.person, text):
        warnings.append(f"Dropped a change: the name '{c.person}' is not in the filing.")
        return None
    eff = None
    if c.effective_date:
        try:
            d = date.fromisoformat(c.effective_date[:10])
            if date_in_text(d, text):
                eff = d.isoformat()
            else:
                warnings.append(f"{c.person}: the date {d:%d %b %Y} is not printed in the filing; not shown.")
        except ValueError:
            pass
    profile = None
    if c.profile_quote:
        page, score = verify_quote(c.profile_quote, pages, c.page)
        if not page:
            page = next((i + 1 for i, t in enumerate(pages) if words_in_order(c.profile_quote, t)), None)
            score = 0.9 if page else score
        if page:
            profile = {"quote": c.profile_quote.strip(), "page": page, "match": round(score, 2),
                       "summary": (c.bio or "").strip()[:320] or None}
        else:
            warnings.append(f"{c.person}: the profile text was not found in the filing; bio not shown.")
    role_ok = bool(c.role) and role_in_text(c.role, pages)
    return {
        "event": c.event, "label": _EVENT_LABEL[c.event], "person": c.person.strip(),
        "role": c.role.strip() if role_ok else None, "role_unverified": bool(c.role) and not role_ok,
        "previous_role": (c.previous_role or "").strip() or None,
        "effective_date": eff, "reason": (c.reason or "").strip() or None,
        "profile": profile, "key_role": is_key_role(c.role) or is_key_role(c.previous_role),
        "page": c.page if c.page and 1 <= c.page <= len(pages) else None,
    }


def headline(ch: dict) -> str:
    """One line for Today: 'Retiring: Noel N. Tata, Vice-Chairman, from 12 Nov 2026'."""
    parts = [f"{ch['label']}: {ch['person']}"]
    if ch.get("role"):
        parts.append(ch["role"])
    text = ", ".join(parts)
    if ch.get("effective_date"):
        text += f", from {date.fromisoformat(ch['effective_date']):%d %b %Y}".replace(" 0", " ")
    return text


def build_mgmt_card(filing: dict, pages: list[str],
                    extractor: Callable[[str, dict], MgmtOut] = ai_extract) -> dict:
    """Management-change card for one filing whose PDF text is loaded."""
    base = {
        "filing_id": filing.get("id"), "ticker": filing.get("ticker"), "company": filing.get("company"),
        "filing_date": filing.get("date"), "pdf_url": filing.get("pdf_url"), "title": filing.get("title"),
        "kind": "management", "engine_version": config.CARD_ENGINE_VERSION,
        "extracted_at": datetime.now().isoformat(timespec="seconds"), "metrics": [], "checks": [],
    }
    text = "\n".join(f"===== PAGE {i + 1} =====\n{p}" for i, p in enumerate(pages))
    if len(text.strip()) < 200:
        return {**base, "status": "could not extract", "warnings": [], "changes": [],
                "reason": "The filing has no readable text (a scanned image); FINN does not read text from images (OCR)."}
    meta: dict = {}
    try:
        out = extractor(PROMPT.format(text=text[:20000]), meta)
    except (ValueError, RuntimeError) as exc:
        return {**base, "status": "could not extract", "retryable": True, "warnings": [], "changes": [],
                "reason": f"The AI step failed: {str(exc)[:160]}. Try again later."}
    warnings: list[str] = []
    changes = [c for c in (check_change(c, pages, warnings) for c in out.changes[:8]) if c]
    changes.sort(key=lambda c: (not c["key_role"], c["event"] not in ("appointment", "resignation", "retirement")))
    status = "ok" if changes else "could not extract"
    return {
        **base, "status": status,
        "reason": None if changes else "No change in this filing could be confirmed against its text.",
        "changes": changes, "key_role": any(c["key_role"] for c in changes),
        "headline": headline(changes[0]) + (f" (+{len(changes) - 1} more)" if len(changes) > 1 else "") if changes else None,
        "warnings": warnings,
        "ai": {k: meta.get(k) for k in ("model", "tokens_in", "tokens_out", "cached")},
    }
