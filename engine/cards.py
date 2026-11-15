"""Card service (API-3): find a filing's card, or build it once and keep it.

Lookup order (D-078):
1. `snapshot/cards/<filing_id>.json`: precomputed, committed, works offline and on Render.
2. `.cache/cards/<filing_id>.json`: built on this machine or server earlier (Render's disk is
   wiped on restart, so this is a convenience only).
3. Build it now: PDF -> page text -> AI copy -> Python checks. Only a card that is not a
   temporary failure (e.g. the AI was overloaded) is saved, so a retry can still succeed.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Callable

import config
from data import docs
from engine.classifier import classify
from engine.results import build_card

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def valid_id(filing_id: str) -> bool:
    """NSE filing ids are digits; anything else never reaches the file system."""
    return bool(re.fullmatch(r"\d{1,20}", filing_id or ""))


def _snapshot_path(filing_id: str) -> Path:
    return Path(config.CARDS_DIR) / f"{filing_id}.json"


def _cache_path(filing_id: str) -> Path:
    return Path(config.CACHE_DIR) / "cards" / f"{filing_id}.json"


def _read(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        card = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return card if card.get("engine_version") == config.CARD_ENGINE_VERSION else None


def stored_card(filing_id: str) -> dict | None:
    """A precomputed or cached card, or None."""
    return _read(_snapshot_path(filing_id)) or _read(_cache_path(filing_id))


def save_card(card: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(card, indent=1, ensure_ascii=False), encoding="utf-8")


def summary(card: dict) -> dict:
    """The few fields Today shows on a Results card before it is opened."""
    by = {m["key"]: m for m in card.get("metrics", []) if m.get("available")}
    top = by.get("revenue") or by.get("total_income")
    pat = by.get("pat")
    return {
        "status": card.get("status"),
        "verdict": card.get("verdict"),
        "period": (card.get("period") or {}).get("label"),
        "top": top and {"label": top["label"], "yoy_pct": top.get("yoy_pct")},
        "pat": pat and {"label": "PAT", "yoy_pct": pat.get("yoy_pct"), "yoy_note": pat.get("yoy_note")},
    }


def attach_summaries(payload: dict) -> dict:
    """Add `results` (a stored card's summary) to every Results item on Today; never builds cards."""
    for group in ("cards", "summaries", "routine"):
        for item in payload.get(group, []):
            if item.get("kind") == "results" and valid_id(str(item.get("id") or "")):
                card = stored_card(str(item["id"]))
                if card:
                    item["results"] = summary(card)
    return payload


def _lock_for(filing_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(filing_id, threading.Lock())


def get_card(
    filing: dict,
    pages_loader: Callable[[str], list[str]] = docs.get_pages,
    builder: Callable[[dict, list[str]], dict] = build_card,
) -> dict:
    """The card for a results filing; builds it on first open (one build at a time per filing)."""
    fid = str(filing.get("id") or "")
    if not valid_id(fid):
        raise ValueError("Unknown filing id.")
    if classify(filing) != "results":
        raise ValueError("Cards are only built for quarterly results filings.")
    card = stored_card(fid)
    if card:
        return card
    with _lock_for(fid):
        card = stored_card(fid)  # another request may have built it while we waited
        if card:
            return card
        try:
            pages = pages_loader(filing.get("pdf_url") or "")
        except ValueError as exc:
            return _not_saved(filing, str(exc), retryable=False)
        except RuntimeError as exc:
            return _not_saved(filing, str(exc), retryable=True)
        card = builder(filing, pages)
        if not card.get("retryable"):
            save_card(card, _cache_path(fid))
        return card


def _not_saved(filing: dict, reason: str, retryable: bool) -> dict:
    return {
        "filing_id": filing.get("id"), "ticker": filing.get("ticker"), "company": filing.get("company"),
        "filing_date": filing.get("date"), "pdf_url": filing.get("pdf_url"), "kind": "results",
        "status": "could not extract", "reason": reason, "retryable": retryable,
        "metrics": [], "checks": [], "warnings": [], "engine_version": config.CARD_ENGINE_VERSION,
    }
