"""Print the Today digest for the whole portfolio. Run: py run_digest.py [24h|3d|7d]"""
import re
import sys
import time

import config
from data.filings import fetch_filings
from data.prices import fetch_prices
from engine.alerts import check_alerts
from engine.digest import build_digest

window = sys.argv[1] if len(sys.argv) > 1 else config.DEFAULT_WINDOW
tickers = config.PORTFOLIO

filings: list[dict] = []
alerts: dict[str, list[dict]] = {}
for t in tickers:
    try:
        rows, _ = fetch_filings(t, max(config.WINDOWS_HOURS.values()) // 24)
        filings += [{**r, "ticker": t} for r in rows]
        df, _ = fetch_prices(t)
        alerts[t] = check_alerts(t, df)
    except (ValueError, RuntimeError) as e:
        print(f"{t}: skipped ({e})")
    time.sleep(0.3)


def short(title: str) -> str:
    """Drop the boilerplate 'X has informed the Exchange about' prefix."""
    return re.sub(r"^.*?(informed the Exchange|submitted to the Exchange)[^A-Za-z0-9]*(about|regarding)?\s*", "", title)[:80]


d = build_digest(filings, alerts, window)
banner = f"  (widened: no filings in {window}, showing {d['as_of']})" if d["widened"] else ""
print(f"Digest {d['window']} as of {d['generated_at']}{banner}")
print(f"{d['counts']['cards']} cards, {d['counts']['summaries']} one-liners, Routine ({d['counts']['routine']})\n")
for i in d["cards"]:
    mv = "  [moved]" if i["moved_same_day"] else ""
    print(f"CARD  {i['ticker']:<10} {i['date'][:16]}  {i['kind']:<18} {short(i['title'])}{mv}")
for i in d["summaries"]:
    print(f"line  {i['ticker']:<10} {i['date'][:16]}  {i['kind']:<18} {short(i['title'])}")
