"""Build results cards for every saved results filing and print a summary table.

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
    for f in results_filings(tickers):
        if save:  # rebuild: drop the stored copies (AI answers still come from cache.db, free)
            for path in (cards._snapshot_path(f["id"]), cards._cache_path(f["id"])):
                path.unlink(missing_ok=True)
        card = cards.get_card(f)
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
