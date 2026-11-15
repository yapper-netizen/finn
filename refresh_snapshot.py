"""Re-freeze everything the app falls back on (BE-7, D-090). Run before the code freeze, then commit.

Order: prices and filings (live, merged into snapshot/) -> cards for filings that have none
(snapshot/cards/) -> research for the precomputed set, rebuilt ONLY if its documents changed
(snapshot/research/). Prints what changed. AI answers are cached in cache.db, so a re-run is cheap.

Run: py refresh_snapshot.py            (everything)
     py refresh_snapshot.py --no-ai    (prices and filings only)
"""
import sys
import time

import config
from data import filings as filings_mod
from data import prices as prices_mod
from data.research_docs import find_documents
from engine import cards, research_jobs
from run_cards import card_filings


def refresh_market_data(tickers: list[str]) -> list[str]:
    """Live prices and 7 days of filings for every stock; returns problems (snapshot kept)."""
    problems = []
    for t in tickers:
        for label, fetch in (("prices", prices_mod.fetch_prices), ("filings", lambda x: filings_mod.fetch_filings(x, 7))):
            try:
                _, source = fetch(t)
                if source == "snapshot":
                    problems.append(f"{t} {label}: live source failed, snapshot kept")
            except (ValueError, RuntimeError) as exc:
                problems.append(f"{t} {label}: {exc}")
        time.sleep(0.4)  # be polite to the exchange
    return problems


def build_missing_cards(days: int = 30) -> list[str]:
    """Cards for saved filings that have none yet (results, management, board-outcome candidates)."""
    built = []
    for f in card_filings([], days):
        if cards._snapshot_path(f["id"]).exists():
            continue
        card = cards.promote_if_results(f) if cards.is_results_candidate(f) else cards.get_card(f)
        if card.get("status") == "not results" or card.get("retryable"):
            continue
        cards.save_card(card, cards._snapshot_path(f["id"]))
        built.append(f"{f['ticker']} {f['id']} {card.get('kind')}: {card['status']}")
        if (card.get("ai") or {}).get("cached") is False:
            time.sleep(6)  # free tier
    return built


def research_documents_changed(saved: dict | None, found: dict) -> bool:
    """True if NSE now lists a transcript or results filing that was not there when it was built."""
    if not saved:
        return True
    seen = saved.get("documents_seen")
    if seen is None:  # older file: fall back to the documents it used
        seen = {"transcripts": [t["date"][:10] for t in saved["sources"]["transcripts"]],
                "results": [str(r["filing_id"]) for r in saved["sources"]["results"]]}
    new_t = {t["date"][:10] for t in found["transcripts"]} - set(seen["transcripts"])
    new_r = {str(r["id"]) for r in found["results"] if not r.get("candidate")} - set(seen["results"])
    return bool(new_t or new_r)


def refresh_research() -> list[str]:
    """Rebuild a precomputed research stock only when its documents changed (decision 1A)."""
    out = []
    for t in config.RESEARCH_SET:
        try:
            found = find_documents(t)
        except (ValueError, RuntimeError) as exc:
            out.append(f"{t}: NSE not reachable ({exc}); saved research kept")
            continue
        if research_documents_changed(research_jobs.stored(t), found):
            r = research_jobs.run_now(t, save_snapshot=True)
            out.append(f"{t}: rebuilt ({r['counts']})")
        else:
            out.append(f"{t}: unchanged")
    return out


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    tickers = config.PORTFOLIO + config.RESEARCH_EXTRA
    print("1/3 prices and filings ...")
    for p in refresh_market_data(tickers):
        print("   ", p)
    if "--no-ai" in argv:
        return
    print("2/3 cards for new filings ...")
    for line in build_missing_cards() or ["(none new)"]:
        print("   ", line)
    print("3/3 research set ...")
    for line in refresh_research():
        print("   ", line)
    print("Done. Review `git status snapshot/`, run the tests, then commit.")


if __name__ == "__main__":
    main(sys.argv[1:])
