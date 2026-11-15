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
import os
import queue
import re
import threading
import time
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

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


class CardPrebuilder:
    """Builds cards for new results filings in the background (D-078).

    The feed calls `enqueue_from` after each refresh. One worker thread builds one card at a
    time and sleeps between builds, so a burst of results days never exceeds the free tier.
    Filings that already have a card are skipped (no AI call, no download). Requests never
    wait for this: a tap on a card that is still queued simply builds it on demand (the
    per-filing lock prevents a double build).
    """

    def __init__(
        self,
        build: Callable[[dict], dict] = get_card,
        pace_s: float = config.CARD_PREBUILD_PACE_S,
        max_tries: int = config.CARD_PREBUILD_MAX_TRIES,
        enabled: bool | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._build, self._pace, self._max_tries, self._sleep = build, pace_s, max_tries, sleep
        if enabled is None:
            load_dotenv(".env")  # locally the key lives in .env; on Render it is a dashboard variable
            enabled = config.CARD_PREBUILD and bool(os.environ.get("GEMINI_API_KEY"))
        self.enabled = enabled
        self._queue: queue.Queue[dict] = queue.Queue()
        self._queued: set[str] = set()
        self._tries: dict[str, int] = {}
        self._guard = threading.Lock()
        self._worker: threading.Thread | None = None
        self.built: list[str] = []          # ids built this run (for /health and tests)

    def enqueue_from(self, data) -> int:
        """Queue every results filing in the feed that has no stored card. Returns how many."""
        if not self.enabled:
            return 0
        added = 0
        for f in data.filings:
            fid = str(f.get("id") or "")
            if not valid_id(fid) or classify(f) != "results" or stored_card(fid):
                continue
            with self._guard:
                if fid in self._queued or self._tries.get(fid, 0) >= self._max_tries:
                    continue
                self._queued.add(fid)
            self._queue.put(f)
            added += 1
        if added:
            self._start()
        return added

    def _start(self) -> None:
        with self._guard:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run, daemon=True)
                self._worker.start()

    def run_pending(self) -> None:
        """Build everything queued, in this thread (the worker's loop; tests call it directly)."""
        while True:
            try:
                f = self._queue.get_nowait()
            except queue.Empty:
                return
            self._build_one(f)

    def _run(self) -> None:
        self.run_pending()

    def _build_one(self, f: dict) -> None:
        fid = str(f["id"])
        with self._guard:
            self._tries[fid] = self._tries.get(fid, 0) + 1
        try:
            card = self._build(f)
            if not card.get("retryable"):
                self.built.append(fid)
            print(f"[cards] prebuilt {f.get('ticker')} {fid}: {card.get('status')}")
        except Exception as exc:  # never let one filing stop the worker
            print(f"[cards] prebuild failed {f.get('ticker')} {fid}: {type(exc).__name__}: {exc}")
        finally:
            with self._guard:
                self._queued.discard(fid)
            self._sleep(self._pace)
