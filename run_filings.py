"""Print the last N days of filings for every stock. Run: py run_filings.py [days] [TICKER ...]"""
import sys
import time

import config
from data.filings import fetch_filings

args = sys.argv[1:]
days = int(args[0]) if args and args[0].isdigit() else config.FILINGS_DAYS
tickers = [a for a in args if not a.isdigit()] or config.PORTFOLIO + config.RESEARCH_EXTRA

total = 0
for t in tickers:
    try:
        filings, source = fetch_filings(t, days)
    except (ValueError, RuntimeError) as e:
        print(f"{t:<11} ERROR {e}")
        continue
    total += len(filings)
    print(f"{t:<11} {len(filings):>2} filings ({source})")
    for f in filings[:3]:
        print(f"    {f['date'][:16]}  [{f['category'][:28]}]  {f['title'][:70]}")
    time.sleep(0.4)  # be polite to the exchange
print(f"Total: {total} filings over {days} days")
