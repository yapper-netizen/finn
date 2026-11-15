"""Research store and background runs (API-4, EN-16, D-083).

- A precomputed result (`snapshot/research/<T>.json`, committed) or an earlier run on this server
  (`.cache/research/<T>.json`) answers at once with status "ready".
- Otherwise a run starts in a background thread and the screen polls: status "pending" with the
  steps done so far. Only one run at a time (free AI tier): a second ticker waits, "queued".
- A failed run reports status "error" with the reason; it can be retried after a short pause.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable

import config
from data.symbols import resolve
from engine import research as research_mod

_RETRY_AFTER_S = 60


def _paths(symbol: str) -> list[Path]:
    return [Path(config.RESEARCH_DIR) / f"{symbol}.json", Path(config.CACHE_DIR) / "research" / f"{symbol}.json"]


def stored(symbol: str) -> dict | None:
    """A saved research result for this symbol (precomputed first), or None."""
    for path in _paths(symbol):
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if data.get("engine_version") == research_mod.ENGINE_VERSION:
                return data
    return None


def save(result: dict, snapshot: bool = False) -> None:
    path = _paths(result["ticker"])[0 if snapshot else 1]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")


def run_now(ticker: str, progress: Callable[[str], None] = lambda s: None, save_snapshot: bool = False,
            builder: Callable[..., dict] = research_mod.build_research) -> dict:
    """Build synchronously (scripts and the background worker); keeps the result."""
    result = builder(resolve(ticker).symbol, progress=progress)
    save(result)
    if save_snapshot:
        save(result, snapshot=True)
    return result


class ResearchJobs:
    """In-memory job table; one worker thread runs one research at a time."""

    def __init__(self, builder: Callable[..., dict] = research_mod.build_research) -> None:
        self._builder = builder
        self._jobs: dict[str, dict] = {}
        self._guard = threading.Lock()
        self._one_at_a_time = threading.Lock()

    def request(self, ticker: str) -> dict:
        """Ready result, or the state of the (possibly just started) run. Raises ValueError for a bad ticker."""
        symbol = resolve(ticker).symbol
        done = stored(symbol)
        if done:
            return done
        with self._guard:
            job = self._jobs.get(symbol)
            if job and (job["status"] in ("pending", "queued") or time.monotonic() - job["at"] < _RETRY_AFTER_S):
                return self._public(symbol, job)
            job = {"status": "queued", "steps": [], "error": None, "at": time.monotonic()}
            self._jobs[symbol] = job
        threading.Thread(target=self._run, args=(symbol, job), daemon=True).start()
        return self._public(symbol, job)

    def _run(self, symbol: str, job: dict) -> None:
        with self._one_at_a_time:
            job["status"] = "pending"
            try:
                result = self._builder(symbol, progress=lambda s: job["steps"].append(s))
                save(result)
                with self._guard:
                    self._jobs.pop(symbol, None)
            except LookupError as exc:
                job.update(status="error", error=str(exc), retryable=False, at=time.monotonic())
            except Exception as exc:  # network, AI quota: say so, allow a retry later
                job.update(status="error", retryable=True, at=time.monotonic(),
                           error=f"The research run failed: {str(exc)[:200]}. Try again in a minute.")

    @staticmethod
    def _public(symbol: str, job: dict) -> dict:
        return {"ticker": symbol, "status": job["status"], "steps": list(job["steps"]), "error": job.get("error"),
                "retryable": job.get("retryable", True)}
