"""Run the research (promise tracker + bull vs bear) for tickers and print a summary.

Run: py run_research.py POLYCAB            (build, keep in the local cache, print)
     py run_research.py POLYCAB --save     (also write snapshot/research/POLYCAB.json, committed)
"""
import sys

from engine import research_jobs


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    save = "--save" in argv
    for ticker in [a.upper() for a in argv if not a.startswith("--")]:
        r = research_jobs.run_now(ticker, progress=lambda s: print(f"  … {s}"), save_snapshot=save)
        print(f"{r['ticker']} {r['company']}: {r['counts']}  AI calls {r['ai']['calls']} "
              f"(cached {r['ai']['cached']}), tokens {r['ai']['tokens_in']}+{r['ai']['tokens_out']}")
        for p in r["promises"]:
            print(f"  [{p['verdict']:<13}] {p['made_in']} → {p.get('due_label') or p['period_text']}: {p['statement']}")
            if p.get("reason"):
                print(f"      {p['reason']}")
        for side in ("bull", "bear"):
            for pt in r[side]:
                src = f"p{pt['receipt']['page']}" if pt.get("receipt") else ",".join(pt["fact_ids"])
                print(f"  {side.upper()}: {pt['point']} [{src}]")
        for w in r["warnings"]:
            print(f"  warn: {w}")


if __name__ == "__main__":
    main(sys.argv[1:])
