"""'Brief me' (FE-9, D-052, D-091): Today in three spoken sentences, from the digest only.

No AI: plain templates over data the screen already shows, so it is instant, free, and cannot say
anything the cards do not. Sentence 1 = how much matters; 2 = the top item; 3 = unusual moves.
"""
from __future__ import annotations

import re

_WINDOW_WORDS = {"24h": "In the last 24 hours", "3d": "In the last 3 days", "7d": "In the last 7 days"}
_KIND_WORDS = {"results": "results filing", "management_change": "management change", "m_and_a": "deal",
               "litigation": "legal matter", "credit_rating": "credit rating", "pledging": "pledge"}


def short_name(company: str | None, ticker: str) -> str:
    """'Avenue Supermarts Limited' -> 'Avenue Supermarts'; falls back to the ticker."""
    name = re.sub(r"\s+(Limited|Ltd\.?)$", "", (company or "").strip(), flags=re.I)
    return name or ticker


def _count_kinds(cards: list[dict], moves: int = 0) -> str:
    """'3 management changes, 1 results filing and 2 unusual moves' (adds up to the headline count)."""
    counts: dict[str, int] = {}
    for c in cards:
        word = _KIND_WORDS.get(c.get("kind"), "filing")
        counts[word] = counts.get(word, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: -kv[1]) + ([("unusual move", moves)] if moves else [])
    parts = [f"{n} {w}{'' if n == 1 else 's'}" for w, n in ordered]   # filings first, moves last
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _top_item(c: dict) -> str:
    name = short_name(c.get("company"), c.get("ticker", ""))
    if c.get("results") and c["results"].get("verdict"):
        period = c["results"].get("period")
        verdict = c["results"]["verdict"].rstrip(".")
        verdict = verdict[0].lower() + verdict[1:]
        return f"Top of the list: {name}'s {period + ' ' if period else ''}results, with {verdict}."
    if c.get("mgmt") and c["mgmt"].get("headline"):
        key = "key " if c["mgmt"].get("key_role") else ""
        return f"Top of the list is a {key}management change at {name}: {_change_words(c['mgmt'])}."
    return f"Top of the list: {name}, {(c.get('title') or 'a new filing').rstrip('.')}."


_VERBS = {"appointment": "appointed as", "reappointment": "re-appointed as", "resignation": "resigning as",
          "retirement": "retiring as", "cessation": "stepping down as", "role_change": "moving to",
          "auditor_change": "named", "other": "in a change as"}


def _change_words(m: dict) -> str:
    """'V. Srinivasa Rangan re-appointed as Whole-time Director from 23 Nov 2026'."""
    f = m.get("first") or {}
    if not f.get("person"):
        return re.sub(r"\s*\(\+\d+ more\)$", "", m.get("headline") or "a change in its management")
    text = f["person"] + (f" {_VERBS.get(f.get('event'), 'as')} {f['role']}" if f.get("role") else "")
    if f.get("effective_date"):
        y, mo, d = f["effective_date"].split("-")
        months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
        text += f" from {int(d)} {months[int(mo) - 1]} {y}"
    return text


def _moves(alert_only: list[dict]) -> str:
    if not alert_only:
        return "No stock made an unusual move without a filing to explain it."
    a = alert_only[0]
    what = (f"moved {'up' if a['value'] > 0 else 'down'} {abs(a['value']):.1f} percent"
            if a["type"] == "price" else f"traded {a['value']:.1f} times its usual volume")
    more = f", and {len(alert_only) - 1} more unusual move{'s' if len(alert_only) > 2 else ''}" if len(alert_only) > 1 else ""
    return f"{short_name(a.get('company'), a['ticker'])} {what} with no filing to explain it{more}."


def brief_me(payload: dict) -> dict:
    """Three sentences for the Today payload; `text` is what the browser reads aloud."""
    cards, alert_only = payload.get("cards", []), payload.get("alert_only", [])
    when = _WINDOW_WORDS.get(payload.get("window", ""), "Recently")
    n = len(cards) + len(alert_only)
    if not cards and not alert_only:
        first = f"{when}, nothing that matters changed across your stocks."
        r = payload.get("routine_count", 0)
        second = ("There were no routine filings either." if r == 0 else
                  "There was 1 routine filing, collapsed." if r == 1 else f"There were {r} routine filings, all collapsed.")
        sentences = [first, second, _moves([])]
    else:
        first = f"{when}, {n} thing{'s' if n != 1 else ''} matter{'s' if n == 1 else ''}"
        first += f": {_count_kinds(cards, len(alert_only))}." if cards else (
            ": a price or volume move." if n == 1 else ", all of them price or volume moves.")
        second = _top_item(cards[0]) if cards else "No filing needs your attention."
        sentences = [first, second, _moves(alert_only)]
    return {"sentences": sentences, "text": " ".join(sentences)}
