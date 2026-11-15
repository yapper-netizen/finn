"""Push meets pull (10h, P8): which of management's promises does this results filing test?

A results card is a quarter's numbers. If FINN has researched the stock, the promise tracker
already holds what management said and what the filings showed. This picks the promises whose
evidence includes this quarter (a fact from it) or that fell due in it, so the card can say
"they promised X, delivered Y" without opening Research. Python only, no AI, no new numbers.
"""
from __future__ import annotations

from typing import Any

_JUDGED = ("Missed", "Partial", "Delivered")      # most newsworthy first
MAX_ITEMS = 3


def _fy_label(quarter_label: str) -> str | None:
    """'Q4 FY26' -> 'FY26' (the fiscal-year facts a Q4 filing completes)."""
    parts = quarter_label.split()
    return parts[1] if len(parts) == 2 and parts[0] == "Q4" else None


def relevant(promise: dict, label: str, period_end: str) -> bool:
    """Evidence from this quarter, or due in it."""
    fy = _fy_label(label)
    for f in promise.get("facts") or []:
        if f.get("quarter") == label or (fy and f.get("quarter") == fy):
            return True
    return promise.get("due") == period_end


def promises_for_card(card: dict, research: dict | None) -> dict:
    """{available, ticker, items, open_count, next_test} for a results card.

    `available` is False when FINN has no research for the stock (the sheet then offers to run it).
    """
    out: dict[str, Any] = {"available": bool(research), "ticker": card.get("ticker"), "items": [], "open_count": 0,
                           "next_test": None, "quarter": (card.get("period") or {}).get("label")}
    if not research:
        return out
    period = card.get("period") or {}
    label, end = period.get("label") or "", period.get("current") or ""
    promises = research.get("promises") or []
    hits = [p for p in promises if p.get("verdict") in _JUDGED and relevant(p, label, end)]
    hits.sort(key=lambda p: (_JUDGED.index(p["verdict"]), p.get("id", "")))
    out["items"] = hits[:MAX_ITEMS]
    out["more"] = max(0, len(hits) - MAX_ITEMS)
    waiting = sorted((p for p in promises if p.get("verdict") == "Too early" and (p.get("due") or "") > end),
                     key=lambda p: p["due"])
    out["open_count"] = sum(1 for p in promises if p.get("verdict") == "Too early")
    if waiting:
        out["next_test"] = {"statement": waiting[0]["statement"], "due_label": waiting[0].get("due_label"), "id": waiting[0].get("id")}
    return out
