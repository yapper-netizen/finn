"""Add background, qualifications and exit style to the saved management cards (10h, P6).

Reads each card's filing from the local page cache (downloads only if missing; NSE archive,
already approved), makes one cheap AI call for the incoming people, and rewrites the card.
Run: py run_mgmt_enrich.py          (snapshot/cards/ and the local cache)
Safe to re-run: AI answers are cached; cards already enriched are skipped unless --force.
"""
import glob
import json
import sys
import time
from pathlib import Path

import config
from data import docs
from engine import mgmt

PACE_S = 0.5     # AI answers are cached after the first run


def main(force: bool) -> None:
    paths = sorted(glob.glob(f"{config.CARDS_DIR}/*.json"))
    done = skipped = failed = 0
    for path in paths:
        card = json.loads(Path(path).read_text(encoding="utf-8"))
        if card.get("kind") != "management" or card.get("status") != "ok":
            continue
        if card.get("enriched") and not force:
            skipped += 1
            continue
        try:
            pages = docs.get_pages(card["pdf_url"])
        except (ValueError, RuntimeError) as exc:
            print(f"  {card['ticker']} {card['filing_id']}: pages unavailable ({exc})")
            failed += 1
            continue
        mgmt.enrich_card(card, pages)
        Path(path).write_text(json.dumps(card, indent=1, ensure_ascii=False), encoding="utf-8")
        cache = Path(config.CACHE_DIR) / "cards" / Path(path).name
        if cache.exists():
            cache.write_text(json.dumps(card, indent=1, ensure_ascii=False), encoding="utf-8")
        done += 1
        print(f"  {card['ticker']:11} {card.get('background') or '-'}")
        for ch in card["changes"]:
            if ch.get("exit_note"):
                print(f"  {'':11} {ch['person']}: {ch['exit_note']}")
        time.sleep(PACE_S)
    print(f"enriched {done}, already done {skipped}, failed {failed}")


if __name__ == "__main__":
    main("--force" in sys.argv)
