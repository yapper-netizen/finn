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
- Options: Claude Sonnet / Gemini Pro / Claude Opus (best reasoning, highest cost)
- Chosen: undecided; depends on which API key is available. Recommended: Claude Sonnet, used only for promise verdicts + bull/bear (PLAN EN-13, EN-14).
- Why: cheap model (Gemini Flash) for bulk, strong model only for promised-vs-delivered verdicts and bull/bear.
- Trade-off: cost vs quality; to be logged in the README with token counts.

### D-010 · ITC excluded from portfolio · 2026-11-13 · Step 1 · Status: decided
- Options: include ITC / drop it
- Chosen: dropped.
- Why: ENAM avoids intoxication-linked businesses (tobacco).
- Trade-off: loses a large, liquid consumer name; replaced by IRCTC.

---

## Decisions added with PLAN.md (2026-11-13)

Open entries show **Recommended**; fill **Chosen** when you decide, and set Status to decided.

### D-011 · Interaction model · 2026-11-13 · Plan FE-1 · Status: open
- Options: (A) cards-first "Today" feed + Research search tab / (B) chat copilot as the main screen / (C) A + one small experiment ("Brief me" 60-second summary, swipe-to-dismiss, voice read-out) / (D) voice-first
- Recommended: C. Cards are the filter; chat as the main screen turns FINN back into a feed you must interrogate. One experiment shows the {point of view on interaction} the brief asks for.
- Chosen: —
- Trade-off: C costs ~1.5h extra; pure chat (B) looks more "AI" but answers slower and is harder to scan.

### D-012 · Corporate-filings source · 2026-11-13 · Plan BE-3 · Status: open
- Options: BSE announcements JSON endpoint (the one bseindia.com's own page calls) / NSE corporate-announcements API (needs session cookies [small tokens a site sets on first visit]) / both with fallback
- Recommended: BSE primary, NSE backup, snapshot last.
- Chosen: —
- Trade-off: both are unofficial and can block scripts; snapshot keeps the demo alive.

### D-013 · NSE symbol → BSE scrip code · 2026-11-13 · Plan BE-2 · Status: open
- Options: hardcode codes for the portfolio only / BSE's search endpoint at runtime + cache / download BSE's full scrip list [master file of all listed companies] once and ship it
- Recommended: shipped scrip list + runtime lookup fallback (needed for {any NSE ticker}).
- Chosen: —
- Trade-off: list goes stale for new listings; lookup endpoint can block.

### D-014 · Filing classification method · 2026-11-13 · Plan EN-2 · Status: open
- Options: rules only (BSE category + keyword match) / cheap model for every filing / rules first, cheap model only for leftovers, cached
- Recommended: rules first + model for leftovers ({cost efficiency}; most filings are routine and obvious).
- Chosen: —
- Trade-off: keyword rules miss odd wording; measure on a hand-labelled sample of 50.

### D-015 · Category tiers · 2026-11-13 · Plan EN-3 · Status: open
- Options: use the {reference-doc categories} as-is / adapt (split `order_win` out of press_release; earnings_call and investor_meetings → Low) / per-user weights in Settings
- Recommended: adapt. High: results, management_change, M&A, litigation, credit_rating, pledging. Medium: fund_raise, capex, dividend, bonus_split, insider_trading, order_win. Low (collapsed): earnings_call, investor_meetings, agm_egm, postal_ballot, press_release (non-order), unclassified. Test: "would a long-term fund manager change a hold/buy/sell view?"
- Chosen: —
- Trade-off: a fixed order may under-rank a large press release; user category toggles mitigate.

### D-016 · Source of results numbers · 2026-11-13 · Plan EN-5, BE-6 · Status: open
- Options: (A) PDF text + cheap model extracts numbers as JSON, validated / (B) XBRL [machine-readable tagged version of the results that exchanges also publish — exact numbers, no AI] / (C) screener.in quarterly table / (D) A with B or C as cross-check
- Recommended: D. {"Take the actual results filing"} stays the source shown to the user; structured data guards against mis-extraction.
- Chosen: —
- Trade-off: XBRL parsing may cost time; screener is secondary (allowed on the push side, but say so).

### D-017 · Consolidated vs standalone results · 2026-11-13 · Plan EN-5 · Status: open
- Options: consolidated [whole group incl. subsidiaries] / standalone [parent company only] / show both
- Recommended: consolidated, fall back to standalone with a label.
- Chosen: —
- Trade-off: some filings publish standalone first; label avoids confusion.

### D-018 · Bank results (HDFCBANK) · 2026-11-13 · Plan EN-5 · Status: open
- Options: show "bank format — not supported" / map to bank metrics (NII [net interest income], PPOP [pre-provision operating profit], PAT) / drop banks from the portfolio
- Recommended: label as unsupported + link to filing; state in writeup. Banks have no EBITDA.
- Chosen: —
- Trade-off: one portfolio stock gets a thinner card.

### D-019 · Management-change bio source · 2026-11-13 · Plan EN-6 · Status: open
- Options: "brief profile" inside the exchange filing (SEBI [market regulator] requires it for appointments) / LinkedIn ({brief says e.g. LinkedIn is fine}, but scraping breaks terms and gets blocked) / company website
- Recommended: filing profile, condensed by cheap model to 2 lines, link to source.
- Chosen: —
- Trade-off: profile quality varies; resignations carry no bio (show the outgoing role + reason instead).

### D-020 · Fundamentals documents source · 2026-11-13 · Plan BE-5 · Status: open
- Options: screener.in document links (the brief's suggestion) / company investor-relations site / BSE annual-report + filings archive
- Recommended: screener.in, BSE fallback. Both point to the company's own PDFs, so still {primary}.
- Chosen: —
- Trade-off: screener can rate-limit; cache every PDF.

### D-021 · Document chunking / retrieval · 2026-11-13 · Plan EN-10 · Status: open
- Options: send whole document to a long-context model / page-tagged sections + keyword retrieval (no extra infrastructure) / embeddings RAG [turn text into number vectors, fetch the most similar chunks]
- Recommended: page-tagged sections + keywords. Transcripts are ~20–40 pages; guidance language is predictable. {Chunking} is a named bonus instinct.
- Chosen: —
- Trade-off: keyword retrieval can miss paraphrased guidance; embeddings add setup and cost.

### D-022 · Promise-tracker method · 2026-11-13 · Plan EN-12, EN-13 · Status: open
- Options: one big prompt over 4 transcripts / two-pass: cheap model extracts promises with quotes → Python fetches actual numbers → strong model judges Delivered / Partial / Missed
- Recommended: two-pass. Cheap model for bulk, strong model only where reasoning is needed ({model routing}); numbers stay in Python.
- Chosen: —
- Trade-off: more moving parts; much cheaper and auditable.

### D-023 · Which research views to build · 2026-11-13 · Plan EN-11–EN-17 · Status: open
- Options from the {8-view menu}: business snapshot, financial snapshot, trajectory, balance sheet, cash quality, narrative vs numbers, guidance, bull vs bear
- Recommended: business snapshot + narrative vs numbers (promise tracker, the brief's {worked example, valued most}) + bull vs bear. Others stated as "left out" in the writeup.
- Chosen: —
- Trade-off: depth over breadth ({thin-but-working}).

### D-024 · Any-ticker research latency · 2026-11-13 · Plan EN-16 · Status: open
- Options: precompute everything (fails the {any NSE ticker} test) / live only (slow, rate-limit risk) / precompute demo set + live with progress steps for others
- Recommended: precompute + live with visible steps ("Finding transcripts… Reading Q2… Judging promises…").
- Chosen: —
- Trade-off: live run may take 1–2 min on free tiers.

### D-025 · Cheap / bulk model · 2026-11-13 · Plan EN-9 · Status: open
- Options: Gemini Flash (generous free tier) / Claude Haiku / open model via Groq [fast free-tier inference host]
- Recommended: Gemini Flash.
- Chosen: —
- Trade-off: free-tier rate limits; prompts must be model-agnostic so it can be swapped in config.

### D-026 · AI cache design · 2026-11-13 · Plan EN-9 · Status: open
- Options: key by document URL / key by (document hash, prompt version, model)
- Recommended: (doc hash, prompt version, model) so editing a prompt invalidates only its own entries.
- Chosen: —
- Trade-off: none significant.

### D-027 · Front-end stack · 2026-11-13 · Plan FE-1 · Status: decided
- Options: single HTML + Alpine.js + Tailwind (CDN [loaded from a public web server, no build step]) / React + Vite / HTMX
- Chosen: single HTML + Alpine + Tailwind (follows D-001).
- Why: no build step, one deployment, fast to iterate.
- Trade-off: one large file; fine at this size.

### D-028 · Visual identity · 2026-11-13 · Plan FE-7 · Status: open
- Options: ENAM-inspired palette and type / neutral "terminal" look / own brand for FINN
- Recommended: own FINN brand with an ENAM-inspired palette; don't copy ENAM's logo.
- Chosen: —
- Trade-off: time; keep to ~1.5h.

### D-029 · Settings storage · 2026-11-13 · Plan FE-6 · Status: decided
- Options: localStorage [data kept in the phone's browser] / server-side user accounts
- Chosen: localStorage, no logins.
- Why: CLAUDE.md scope; no auth needed for a prototype.
- Trade-off: settings don't sync across devices.

### D-030 · Push delivery · 2026-11-13 · Plan FE-8 · Status: open
- Options: in-app Today feed only / + PWA install (home-screen icon) / real web-push notifications / Telegram or email digest
- Recommended: in-app + PWA; real notifications listed under "next steps".
- Chosen: —
- Trade-off: "push" is simulated on open; state honestly in the writeup.

### D-031 · Data refresh strategy · 2026-11-13 · Plan BE-7, OPS-5 · Status: open
- Options: fetch on request with a TTL [time-to-live: how long cached data counts as fresh] / scheduled job (GitHub Actions nightly) / manual refresh script only
- Recommended: on request with TTL + manual refresh script; nightly job only if time remains.
- Chosen: —
- Trade-off: first request after TTL is slower.

### D-032 · Hosting · 2026-11-13 · Plan OPS-2 · Status: open
- Options: Render free (sleeps after ~15 min, disk wiped on restart) / Hugging Face Spaces / Railway / Fly.io
- Recommended: Render (per CLAUDE.md) with precomputed cache committed to the repo + warm-up before sending the email.
- Chosen: —
- Trade-off: ~1 min cold start; mention in email.

### D-033 · HAL in the portfolio · 2026-11-13 · config · Status: open
- Context: ENAM avoids businesses causing harm to living creatures. HAL makes military aircraft and helicopters (defence).
- Options: keep HAL (strategic national asset, not a weapons-only maker) / replace with a non-defence PSU or mid-cap (e.g. ULTRACEMCO, CDSL, KPITTECH)
- Recommended: replace, to stay consistent with the reason ITC was dropped (D-010).
- Chosen: —
- Trade-off: lose a defence/PSU name that adds sector variety.

### D-034 · Python version on deploy · 2026-11-13 · Plan OPS-2 · Status: open
- Options: 3.14 (matches local) / 3.12 (widest library support on Render)
- Recommended: pin 3.12 on Render; code avoids 3.13+ features.
- Chosen: —
- Trade-off: local and deploy versions differ; run tests on both if possible.

### D-035 · Default window when markets are closed · 2026-11-13 · Plan EN-4 · Status: open
- Context: submission day (15 Nov) is a Sunday; a strict 24h window may be empty when reviewers open the app.
- Options: strict last 24h / "since last trading session" default / "since you last looked" (localStorage)
- Recommended: "since last trading session" as default, 24h/3d/7d still selectable ({default 24h, but let me pick}).
- Chosen: —
- Trade-off: deviates slightly from the brief's default; explain in writeup.

### D-036 · "What matters" test · 2026-11-13 · Plan EN-3 · Status: decided
- Chosen: would a long-term fund manager change a hold/buy/sell view because of this?
- Why: ENAM is long-term, bottom-up; noise filtering is the {core problem}.

### D-037 · AI build-history format · 2026-11-13 · Plan DEL-3 · Status: open
- Options: Claude Code `/export` transcripts committed in `build-history/` / claude.ai share links / both
- Recommended: both; link them from README and email.
- Chosen: —
- Trade-off: review exports for secrets before committing.

### D-038 · Repo visibility · 2026-11-13 · Plan OPS-1 · Status: open
- Options: public / private + invite reviewers
- Recommended: public (no login needed to review).
- Chosen: —
- Trade-off: code is visible to anyone.

### D-039 · User accounts · 2026-11-13 · Status: decided
- Chosen: none.
- Why: prototype for an internal team; logins add risk to the demo.

### D-040 · Where alerts appear · 2026-11-13 · Plan FE-2 · Status: open
- Options: separate Alerts tab / merged into Today cards (chip on the stock's card, alert-only cards when no filing) / both
- Recommended: merged; a filing + unusual move on the same day is boosted to the top.
- Chosen: —
- Trade-off: Today screen carries two kinds of item; design must keep them distinct.

### D-041 · Receipts standard · 2026-11-13 · Plan EN-15, FE-5 · Status: open
- Options: link to document only / quote + page + link / quote verified verbatim against source text, else claim dropped
- Recommended: verified quote + page + link.
- Chosen: —
- Trade-off: some valid claims dropped when PDF text is messy.

### D-042 · Out of scope (state in writeup) · 2026-11-13 · Status: decided
- Chosen: no real push notifications, no intraday data, no logins, no bank-specific results card, research views beyond D-023.
- Why: {thin-but-working beats broad-but-broken}.
