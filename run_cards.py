"""Build cards for saved filings and print a summary table.

Covers every results filing, plus management changes and "board outcome" filings that may hold
results (D-087) from the last --days (default 30).
Run: py run_cards.py            (build into the local cache, print the table)
     py run_cards.py --save     (also write snapshot/cards/<id>.json, the copies that ship)
     py run_cards.py IRCTC TCS  (only these tickers)
"""
import glob
import json
import sys
import time
from pathlib import Path

import config
from data import docs
from data.symbols import resolve
from engine import cards
from engine.classifier import classify


PACE_S = 6


def results_filings(tickers: list[str]) -> list[dict]:
    """Every results filing in snapshot/filings/, optionally only for some tickers."""
    out = []
    for path in sorted(glob.glob(f"{config.SNAPSHOT_DIR}/filings/*.json")):
        ticker = Path(path).stem
        if tickers and ticker not in tickers:
            continue
        for f in json.loads(Path(path).read_text(encoding="utf-8")):
            if classify(f) == "results":
                try:
                    name = resolve(ticker).name
                except ValueError:
                    name = ticker
                out.append({**f, "ticker": ticker, "company": name})
    return out


def card_filings(tickers: list[str], days: int = 30) -> list[dict]:
    """Results filings (all), management changes and results candidates (recent) in the snapshots."""
    from datetime import timedelta
    from data.clock import ist_now
    since = (ist_now() - timedelta(days=days)).isoformat()
    out = []
    for path in sorted(glob.glob(f"{config.SNAPSHOT_DIR}/filings/*.json")):
        ticker = Path(path).stem
        if tickers and ticker not in tickers:
            continue
        try:
            name = resolve(ticker).name
        except ValueError:
            name = ticker
        for f in json.loads(Path(path).read_text(encoding="utf-8")):
            kind = classify(f)
            recent = f["date"] >= since
            if kind == "results" or (recent and (kind == "management_change" or cards.is_results_candidate(f))):
                out.append({**f, "ticker": ticker, "company": name})
    return out


def _fmt(m: dict) -> str:
    if not m.get("available"):
        return f"{m['label']}: -"
    v = m["values"]["current"]
    q = "n/a" if m["qoq_pct"] is None else f"{m['qoq_pct']:+.1f}%"
    y = "n/a" if m["yoy_pct"] is None else f"{m['yoy_pct']:+.1f}%"
    return f"{m['label']}{'*' if m.get('computed') else ''} {v:,.0f} ({q}/{y})"


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # the Windows console cannot print some symbols
    save = "--save" in argv
    tickers = [a.upper() for a in argv if not a.startswith("--")]
    days = next((int(a.split("=")[1]) for a in argv if a.startswith("--days=")), 30)
    for f in card_filings(tickers, days):
        if save:  # rebuild: drop the stored copies (AI answers still come from cache.db, free)
            for path in (cards._snapshot_path(f["id"]), cards._cache_path(f["id"])):
                path.unlink(missing_ok=True)
        card = cards.promote_if_results(f) if cards.is_results_candidate(f) else cards.get_card(f)
        if card["status"] == "not results":
            continue
        if card.get("kind") == "management":
            if save and not card.get("retryable"):
                cards.save_card(card, cards._snapshot_path(f["id"]))
            print(f"{f['ticker']:<11} {f['id']} {card['status']:<18} management  "
                  f"{'KEY ' if card.get('key_role') else ''}{card.get('headline') or card.get('reason')}")
            if (card.get("ai") or {}).get("cached") is False:
                time.sleep(PACE_S)
            continue
        if (card.get("ai") or {}).get("cached") is False:
            time.sleep(PACE_S)  # free tier allows only a few requests a minute
        if save and not card.get("retryable"):
            cards.save_card(card, cards._snapshot_path(f["id"]))
        checks = card.get("checks", [])
        ok = sum(c["passed"] for c in checks)
        print(f"{f['ticker']:<11} {f['id']} {card['status']:<18} {card.get('basis', ''):<12} "
              f"p{card.get('pages')} checks {ok}/{len(checks)}")
        if card["metrics"]:
            print("            " + " | ".join(_fmt(m) for m in card["metrics"]))
        if card.get("reason") and card["status"] != "ok":
            print(f"            reason: {card['reason']}")
        for w in card.get("warnings", []):
            print(f"            warn: {w}")
        for c in checks:
            if not c["passed"]:
                print(f"            check failed: {c['name']} {c['detail']}")


if __name__ == "__main__":
    main(sys.argv[1:])
