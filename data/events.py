"""Upcoming events for the portfolio (block 10g, Pulse DB2): board meetings and corporate actions.

Two NSE JSON APIs (no files): `event-calendar` (board meetings with their purpose, e.g. financial
results, dividend, fund raising) and `corporates-corporateActions` (ex-dates for dividends, bonus
issues, splits). Every call has a timeout and one retry; a failing stock is skipped and reported.
The last good list is frozen in `snapshot/events.json` so Pulse works if NSE blocks us.
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

import config
from data.clock import ist_now
from data.filings import _HEADERS

_session = requests.Session()


def _get(url: str, params: dict) -> Any:
    last: Exception | None = None
    for attempt in range(config.RETRIES + 1):
        try:
            r = _session.get(url, params=params, headers=_HEADERS, timeout=config.REQUEST_TIMEOUT_S)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            last = exc
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(str(last)[:120])


def _day(text: str | None) -> date | None:
    try:
        return datetime.strptime((text or "").strip(), "%d-%b-%Y").date()
    except ValueError:
        return None


def parse_board(rows: list[dict], symbol: str) -> list[dict]:
    """Board meetings -> events {ticker, date, kind, title, detail}."""
    out = []
    for r in rows if isinstance(rows, list) else []:
        d = _day(r.get("date"))
        if d:
            purpose = (r.get("purpose") or "Board meeting").strip()
            out.append({"ticker": symbol, "date": d.isoformat(), "kind": "results" if "result" in purpose.lower() else "board",
                        "title": "Results board meeting" if "result" in purpose.lower() else f"Board meeting: {purpose}",
                        "detail": " ".join((r.get("bm_desc") or "").split())[:200]})
    return out


def parse_actions(rows: list[dict], symbol: str) -> list[dict]:
    """Corporate actions -> events on their ex-date (the day the entitlement is fixed)."""
    out = []
    for r in rows if isinstance(rows, list) else []:
        d = _day(r.get("exDate")) or _day(r.get("recDate"))
        if d:
            subject = " ".join((r.get("subject") or "Corporate action").split())
            out.append({"ticker": symbol, "date": d.isoformat(), "kind": "action", "title": f"Ex-date: {subject}"[:90],
                        "detail": f"Record date {r.get('recDate') or '-'}"})
    return out


def upcoming(events: list[dict], today: date, days: int = config.EVENTS_DAYS) -> list[dict]:
    """Events from today to `days` ahead, soonest first, one per (ticker, date, title)."""
    end = today + timedelta(days=days)
    seen, out = set(), []
    for e in sorted(events, key=lambda e: (e["date"], e["ticker"])):
        key = (e["ticker"], e["date"], e["title"])
        if today.isoformat() <= e["date"] <= end.isoformat() and key not in seen:
            seen.add(key)
            out.append(e)
    return out


def recent(events: list[dict], today: date, days: int = 7) -> list[dict]:
    """Events of the last `days` days (before today), newest first."""
    start = (today - timedelta(days=days)).isoformat()
    return sorted([e for e in events if start <= e["date"] < today.isoformat()], key=lambda e: e["date"], reverse=True)


def expected_results(events: list[dict], today: date, horizon: int = 100) -> list[dict]:
    """Each stock's next results meeting, estimated from the same quarter last year (labelled).

    Only for stocks with no confirmed results meeting ahead; a pattern, not a promise.
    """
    confirmed = {e["ticker"] for e in events if e["kind"] == "results" and e["date"] >= today.isoformat()}
    out = []
    for t in sorted({e["ticker"] for e in events} - confirmed):
        past = sorted(date.fromisoformat(e["date"]) for e in events if e["ticker"] == t and e["kind"] == "results")
        cands = []
        for d in past:
            try:
                nxt = d.replace(year=d.year + 1)
            except ValueError:           # 29 Feb
                nxt = d.replace(year=d.year + 1, day=28)
            if today < nxt <= today + timedelta(days=horizon):
                cands.append((nxt, d))
        if cands:
            nxt, last_year = min(cands)
            out.append({"ticker": t, "date": nxt.isoformat(), "kind": "expected", "title": "Results expected around this date",
                        "detail": f"Estimate: last year's meeting was on {last_year.strftime('%d %b %Y')}"})
    return sorted(out, key=lambda e: e["date"])


def fetch_one(symbol: str) -> list[dict]:
    """Both NSE lists for one stock (network)."""
    board = _get(config.NSE_EVENTS_URL, {"index": "equities", "symbol": symbol})
    try:
        actions = _get(config.NSE_ACTIONS_URL, {"index": "equities", "symbol": symbol})
    except RuntimeError:
        actions = []
    return parse_board(board, symbol) + parse_actions(actions, symbol)


def fetch_all(symbols: list[str]) -> tuple[list[dict], list[str]]:
    """All events for the portfolio (few workers: the exchange is not ours); errors per stock."""
    events: list[dict] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for sym, res in zip(symbols, pool.map(_safe, symbols)):
            if isinstance(res, str):
                errors.append(f"{sym}: {res}")
            else:
                events += res
    return events, errors


def _safe(symbol: str) -> list[dict] | str:
    try:
        return fetch_one(symbol)
    except RuntimeError as exc:
        return str(exc)


def snapshot_path() -> Path:
    return Path(config.SNAPSHOT_DIR) / "events.json"


def save_snapshot(events: list[dict]) -> None:
    snapshot_path().write_text(json.dumps({"saved_at": ist_now().isoformat(timespec="seconds"), "events": events},
                                          indent=1, ensure_ascii=False), encoding="utf-8")


def load_snapshot() -> tuple[list[dict], str | None]:
    try:
        d = json.loads(snapshot_path().read_text(encoding="utf-8"))
        return d.get("events", []), d.get("saved_at")
    except (OSError, ValueError):
        return [], None


class EventsCache:
    """Snapshot at once; live list fetched in the background and kept for EVENTS_TTL_S."""

    def __init__(self, fetcher=fetch_all) -> None:
        self._fetcher = fetcher
        self._events, self._as_of = load_snapshot()
        self._live_at: float | None = None
        self._lock = threading.Lock()
        self._running = False

    def get(self, symbols: list[str]) -> dict:
        with self._lock:
            out = {"events": list(self._events), "as_of": self._as_of, "live": self._live_at is not None}
        stale = self._live_at is None or time.monotonic() - self._live_at > config.EVENTS_TTL_S
        if stale and not self._running:
            self._running = True
            threading.Thread(target=self._refresh, args=(symbols,), daemon=True).start()
        return out

    def _refresh(self, symbols: list[str]) -> None:
        try:
            events, errors = self._fetcher(symbols)
            if events and len(errors) < len(symbols) / 2:       # mostly worked: use it
                with self._lock:
                    self._events, self._as_of = events, ist_now().isoformat(timespec="seconds")
                    self._live_at = time.monotonic()
        finally:
            self._running = False
