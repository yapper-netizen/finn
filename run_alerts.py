"""Step 1 runner: fetch 60 days of prices for the portfolio and print alerts.

Usage:  python run_alerts.py
"""
from __future__ import annotations

import config
from data.prices import fetch_prices
from engine.alerts import check_alerts


def main() -> None:
    all_alerts: list[dict] = []
    for ticker in config.PORTFOLIO:
        try:
            df, source = fetch_prices(ticker)
        except RuntimeError as exc:
            print(f"[FAIL] {exc}")
            continue
        last = df.iloc[-1]
        found = check_alerts(ticker, df)
        all_alerts += found
        print(f"[ OK ] {ticker:<11} {len(df):>3} days via {source:<8} "
              f"last {last['Date']:%Y-%m-%d} close {last['Close']:>9.2f} "
              f"vol {int(last['Volume']):>11,}  alerts: {len(found)}")

    print(f"\n=== {len(all_alerts)} alert(s) for the latest trading day ===")
    for a in all_alerts:
        print(" *", a["message"])


if __name__ == "__main__":
    main()
