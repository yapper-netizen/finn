# FINN decision log

Running record of choices, newest at the bottom. Feeds the final writeup (key decisions and trade-offs).

Entry template:

```
### D-NNN · <title> · <date> · Step N · Status: decided | open
- Options: A / B / C
- Chosen: ...
- Why: ...
- Trade-off: ...
```

---

### D-001 · App stack · 2026-11-13 · Step 1 · Status: decided
- Options: FastAPI + SQLite + single HTML page / Streamlit / React + separate API
- Chosen: FastAPI [Python web-API library] + SQLite [single-file database] + one HTML page (Tailwind + Alpine.js), one deployment.
- Why: one free Render service, mobile-first control of the UI, simple for a reviewer to read.
- Trade-off: more hand-written UI than Streamlit; less polish than a React app.

### D-002 · Python environment · 2026-11-13 · Step 1 · Status: decided
- Options: system Python / `py` launcher + venv [isolated per-project package folder] / conda
- Chosen: `py -m venv .venv` with Python 3.14; plain `python` is not on PATH on this machine.
- Why: reproducible, nothing installed globally.
- Trade-off: Python 3.14 is new; some libraries may lack wheels later (Render may use a different version, so check at deploy).

### D-003 · Price data source · 2026-11-13 · Step 1 · Status: decided
- Options: yfinance only / yfinance + BSE fallback / paid API
- Chosen: yfinance NSE (.NS) -> retry once -> BSE (.BO) -> saved JSON snapshot.
- Why: free, covers any NSE ticker, and the demo survives a blocked source.
- Trade-off: EOD [end-of-day] data only, no intraday; yfinance is unofficial and can break.

### D-004 · Alert logic · 2026-11-13 · Step 1 · Status: decided
- Options: AI-judged alerts / fixed rule thresholds
- Chosen: rules. Price = close vs previous close beyond the limit; volume = latest vs mean of the prior 20 trading days (latest day excluded).
- Why: cheap, auditable, deterministic, user-configurable.
- Trade-off: no context (e.g. a split or index rebalance can trigger volume alerts).

### D-005 · Float-noise fix in price alert · 2026-11-13 · Step 1 · Status: decided
- Options: round before compare / use Decimal [exact decimal number type] / ignore
- Chosen: round the % move to 6 decimals before comparing.
- Why: a move of exactly 5% computed as 5.000000000000004 and fired falsely; a boundary test now guards it.
- Trade-off: none meaningful.

### D-006 · Commit snapshot data · 2026-11-13 · Step 1 · Status: decided
- Options: git-ignore snapshots / commit them
- Chosen: commit `snapshot/prices/*.json`.
- Why: they are the demo's fallback data if a site blocks us ("a demo that doesn't run is the worst outcome").
- Trade-off: repo carries stale-by-design data; needs a refresh before submission.

### D-007 · Price alert threshold · 2026-11-13 · Step 1 · Status: open
- Options: ±5% (current default) / ±3% / per-stock volatility-scaled
- Chosen: ±5% for now, user-configurable.
- Why: ±5% fires rarely on large caps; the history replay at ±5% gave 59 alerts across 18 stocks in the 60-day window (volume alerts included).
- Trade-off: may miss meaningful 3-5% moves. To decide: re-measure alert counts at ±3%.

### D-008 · Commit history · 2026-11-13 · Step 1 · Status: open
- Options: keep real history (recommended) / clean final copy
- Chosen: keeping real history so far.
- Why: shows the build process to reviewers.
- Trade-off: messy commits stay visible.

### D-009 · Strong model for reasoning · 2026-11-13 · Step 1 · Status: open
- Options: Claude Sonnet / Gemini Pro
- Chosen: undecided; depends on which API key is available.
- Why: cheap model (Gemini Flash) for bulk, strong model only for promised-vs-delivered verdicts and bull/bear.
- Trade-off: cost vs quality; to be logged in the README with token counts.

### D-010 · ITC excluded from portfolio · 2026-11-13 · Step 1 · Status: decided
- Options: include ITC / drop it
- Chosen: dropped.
- Why: ENAM avoids intoxication-linked businesses (tobacco).
- Trade-off: loses a large, liquid consumer name; replaced by IRCTC.
