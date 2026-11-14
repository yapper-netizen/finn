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

### D-009 · Strong model for reasoning · 2026-11-13 · Step 1 · Status: decided (see D-060)
- Options: Claude Sonnet / Gemini Pro / Claude Opus (best reasoning, highest cost)
- Chosen: Gemini Pro on the free tier, used only for promise verdicts + bull/bear (PLAN EN-13, EN-14). Decided in D-060.
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

### D-015 · Category tiers · 2026-11-13 · Plan EN-3 · Status: decided
- Options: use the {reference-doc categories} as-is / adapt (split `order_win` out of press_release; earnings_call and investor_meetings → Low) / per-user weights in Settings
- Recommended: adapt. High: results, management_change, M&A, litigation, credit_rating, pledging. Medium: fund_raise, capex, dividend, bonus_split, insider_trading, order_win. Low (collapsed): earnings_call, investor_meetings, agm_egm, postal_ballot, press_release (non-order), unclassified. Test: "would a long-term fund manager change a hold/buy/sell view?"
- Chosen: adapt, as recommended (2026-11-14). All 17 reference-doc categories mapped; review after the front-end brainstorm (PLAN FE-12).
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

---

## Audit v1 changes (2026-11-14)

Source: [plan_revamp_v1/audit.md](plan_revamp_v1/audit.md). All recommendations approved by Ahad. Older entries are not rewritten; where a decision below settles or replaces one, it says so.

### D-043 · Re-scope P0 and re-time the plan · 2026-11-14 · Audit G1 · Status: decided
- Options: A re-scope P0 to two workflows + deploy gate / B keep scope, freeze Sun 15:00 / C precomputed research only (breaks {any NSE ticker})
- Chosen: A. EN-11 business snapshot → P1; EN-2 rules only (AI fallback → new EN-19, P2); BE-6 removed (D-049); FE-5 merged into FE-4; QA-5 trimmed. Deploy gate Sat 14 Nov 20:00; code freeze Sun 13:00; send ≤17:30. Second-stage cuts defined in PLAN §10 if the gate is missed.
- Why: the old timeline started Fri 13 Nov and those milestones were not done; P0 was ~54h at estimates. {Thin-but-working beats broad-but-broken}; {nail one or two workflows}.
- Trade-off: P0 is still ~53h at hand-coding estimates (new gap tasks added ~2.5h). Relies on Claude Code speed; the deploy gate is the real check.

### D-044 · ENAM theme is a P0 task · 2026-11-14 · Audit G2 · Status: decided
- Options: A new FE-11 P0 theme tokens, FE-7 polish stays P1 / B all of FE-7 P0 / C drop the ENAM theme
- Chosen: A. FE-11 (0.5h, never cut): ENAM website colours and fonts as CSS variables [named colour/font settings reused everywhere]; own FINN wordmark, no ENAM logo. Settles D-028.
- Why: CLAUDE.md step 5 commits to ENAM colours/fonts; PLAN had it only as cuttable FE-7. {No AI slop: beautifully presented}.
- Trade-off: dark mode and finer polish remain cuttable.

### D-045 · 3d / 7d windows cannot be cut · 2026-11-14 · Audit G3 · Status: decided
- Options: A remove from the cut list / B keep only 24h + 7d
- Chosen: A.
- Why: {"by default the last 24 hours, but let me pick the period"} is brief-required; it is only a query parameter.
- Trade-off: none.

### D-046 · Default window: 24h, auto-widen when empty · 2026-11-14 · Audit G4 · Status: decided
- Options: A {24h} default; if empty, widen to the most recent day with filings and show a banner / B "last trading session" default (D-035 recommendation) / C strict 24h
- Chosen: A. Supersedes the D-035 recommendation.
- Why: keeps the brief's {default 24h} and still avoids an empty screen on Sunday 15 Nov.
- Trade-off: the banner adds one UI state; no holiday calendar needed (BE-8 stays P2).

### D-047 · Category toggles drive alerts · 2026-11-14 · Audit G5 · Status: decided
- Options: A EN-18 engine logic (off → Routine; on + High → "alert" chip) with tests / B client-side hiding only / C drop toggles
- Chosen: A. New task EN-18 (P0, 0.5h).
- Why: brief's first alert type is {"a material announcement of a type I care about"}; PLAN had the toggle UI but nothing applied it.
- Trade-off: small extra ranker complexity.

### D-048 · Bank-lite results card · 2026-11-14 · Audit G6 · Status: decided
- Options: A Total income / PBT / PAT with QoQ + YoY, EBITDA shown "n/a for banks" / B "unsupported" label + link / C replace HDFCBANK
- Chosen: A. Settles D-018.
- Why: banks do print PBT and PAT; an empty High card on HDFCBANK's results day looks broken. ~0.5h on EN-5.
- Trade-off: no NII [net interest income] or asset-quality metrics; listed under "left out".

### D-049 · Promise-tracker actuals come from results filings · 2026-11-14 · Audit G7 · Status: decided
- Options: A reuse the EN-5 results-filing extractor on the last 4–5 results filings / B promote BE-6 (screener) to P0, labelled secondary / C XBRL parser
- Chosen: A. BE-6 removed (struck through in PLAN); BE-5 also finds results-filing links.
- Why: EN-13 (P0) depended on BE-6 (P1) — a priority contradiction; screener numbers are secondary, results filings are {primary}. One extractor serves two features.
- Trade-off: depends on EN-5 extraction quality across PDF layouts.

### D-050 · API keys task added · 2026-11-14 · Audit G8 · Status: decided
- Options: A Gemini key + Anthropic key if available, smoke test / B Gemini only (Flash cheap, Pro strong)
- Chosen: A. New task OPS-6 (P0, 0.3h). Final strong model still open in D-009.
- Why: CLAUDE.md step 1 lists keys; no PLAN task covered them.
- Trade-off: two providers to configure.

### D-051 · Research set = 3 stocks, all precomputed · 2026-11-14 · Audit G9 · Status: decided
- Options: A 3 stocks, ≥1 outside portfolio, all precomputed / B 4 (CLAUDE.md) / C 5
- Chosen: A — POLYCAB, PERSISTENT, ASTRAL (outside portfolio). DIXON dropped from the set. New task BE-9 (verify ASTRAL loads, precompute).
- Why: {3–5} minimum met; every demo stock loads instantly; {any NSE ticker} is shown by the live path, not by a bigger set.
- Trade-off: fewer showcase companies.

### D-052 · Interaction experiment: "Brief me" · 2026-11-14 · Audit G10 · Status: decided
- Options: A FE-9 → P1 with "Brief me" (3-sentence summary of Today, read aloud via Web Speech API [browser's built-in, free text-to-speech]) / B keep FE-9 at P2 / C chat as the core interface
- Chosen: A. Settles D-011 as cards-first + "Brief me".
- Why: brief: {"strongly encourage you to experiment… show a point of view"}; PLAN cut it first. Reuses digest data, no extra AI cost.
- Trade-off: ~1.5h; still cuttable (cut list item 4).

### D-053 · Snapshot refresh scheduled before submission · 2026-11-14 · Audit G11 · Status: decided
- Options: A run BE-7 at Sun 13:00 code freeze and commit, plus DEL-5 checkbox / B GitHub Action (OPS-5)
- Chosen: A.
- Why: D-006 said the snapshot must be refreshed before submission; nothing scheduled it.
- Trade-off: data is frozen as of Sun afternoon.

### D-054 · EBITDA fallback excludes other income · 2026-11-14 · Audit G12 · Status: decided
- Options: A PBT + finance cost + D&A − other income, labelled "computed" / B CLAUDE.md formula (PBT + finance cost + depreciation), labelled "incl. other income" / C show both
- Chosen: A. CLAUDE.md updated to match.
- Why: the reference doc defines EBITDA as a proxy for {core-business operating profitability}; other income [e.g. interest on treasury cash] is not core and would overstate it.
- Trade-off: companies that print EBITDA may define it differently; the printed figure is used when present.

### D-055 · Replace HAL with a non-defence small-cap · 2026-11-14 · Audit G13 · Status: decided
- Options: A replace with a non-defence small-cap / B keep HAL / C replace with a large-cap
- Chosen: A. Settles D-033. Specific stock chosen in task BE-10 (must load in yfinance); log the name here when picked.
- Why: ENAM avoids harm to living creatures (same reasoning as D-010); portfolio has no small-cap despite {"different sectors and sizes"}.
- Trade-off: lose a defence/PSU name.

### D-056 · CLAUDE.md synced with PLAN.md · 2026-11-14 · Audit G14 · Status: decided
- Options: A update CLAUDE.md (folder tree, decisions pointer, "(if time)" marks, D-046/D-048/D-051/D-054/D-055) / B record differences only in DECISIONS.md
- Chosen: A.
- Why: CLAUDE.md is loaded into every Claude session; stale content there re-creates the same contradictions.
- Trade-off: two files to keep in step; CLAUDE.md now points to DECISIONS.md instead of listing open decisions.

### D-057 · Hours estimate is advisory · 2026-11-14 · Audit follow-up · Status: decided
- Options: re-scope again to fit ~53h of P0 at estimates / treat estimates as advisory, re-scope only if a deliverable is at risk
- Chosen: advisory. No further re-scoping for the hours total. Refines D-043 (which stays as written).
- Why: user judgment; estimates are hand-coding hours and Claude Code builds faster. Avoids over-complicating the plan.
- Trade-off: schedule risk stays hidden until the Sat 14 Nov 20:00 deploy gate; §10 cuts still apply if a deliverable is at risk.

### D-058 · Screen set: 6 screens · 2026-11-14 · Plan FE-1..6, FE-12 · Status: decided, on hold for review
- Options: A 6 screens, one per brief item (Today, Results, Management change, Settings, Research, Promise tracker) / B fewer (merge detail screens into Today) / C more (one screen per research view)
- Chosen: A for the build. Review after the front-end brainstorm (FE-12); change only with a new entry.
- Why: each screen maps to one brief item ({windowed digest + alerts}, {results example}, {bio example}, {configurable thresholds}, {pull on any ticker}, {promised vs delivered worked example}); other categories live inside Today; other 7 research views skipped {thin-but-working}.
- Trade-off: push and pull don't link yet (brainstorm idea: "Research this company" button on detail screens).

### D-059 · Front-end design v1 · 2026-11-14 · Plan FE-13, all FE tasks · Status: decided
- Options: A recommended S picks only (~2.5h) / B recommended picks + the 3–4 M-effort picks that most improve quality / C all brainstorm ideas
- Chosen: B. Recommended picks (T1, T2, T4, T6, D2, D3, D4, M1, M2, R1, R4, R6, S2, A2, A6) + M picks R5 honest loading, S1 live threshold preview, D1 mini bars, T3 swipe triage + T7 "Research {company}" link. Written up in `design/DESIGN_1.md`; PLAN.md §7 routes there. Front-end design phase closed.
- Why: user judgment; M picks chosen for quality gain on brief items ({any NSE ticker}, {configurable thresholds}, {results card}, {point of view}).
- Trade-off: ≈10h extra on top of P0 FE work (advisory, D-057); build order in DESIGN_1.md puts P0 first and drops P2 then M picks if behind. 6-screen set and tiers still reviewable (FE-12).


### D-060 · Free-tier-only AI keys · 2026-11-14 · OPS-6 (settles D-009, refines D-050) · Status: decided
- Options: A Gemini Flash + Claude Sonnet (needs $5 Anthropic credits) / B Gemini Flash + Gemini Pro with prepaid billing ($5 deposit, offset by Developer Program credits) / C free tier only: Gemini Flash (cheap) + Gemini Pro free tier (strong), no billing
- Chosen: C. One free Gemini key from Google AI Studio; no Anthropic key. Model names stay in config.py, so a paid model is a one-line swap.
- Why: user judgment; the brief says {free tiers are enough} and rewards {cost efficiency}; the other options cost $5 in credits, and a spend-nothing prototype is the strongest cost story.
- Trade-off: free-tier rate limits and daily caps, and weaker verdicts than Sonnet. Mitigation: cache each AI answer in SQLite, precompute the 3 research stocks (D-051), keep a snapshot for the demo. Include this decision in the email writeup.

### D-061 · Free-tier model lineup · 2026-11-14 · OPS-6 (refines D-009, D-060) · Status: decided
- Options: A Flash for bulk + Pro for reasoning, fall back to Flash / B Flash for both / C Flash for both plus a second "verify" call
- Chosen: A in intent, adjusted to what the free key can reach. Live check on 2026-11-14: gemini-2.5-flash and gemini-2.5-pro return 404 "no longer available to new users"; no Pro model is available on this key. Working lineup in config.py: cheap = gemini-3.5-flash-lite, strong = gemini-3.5-flash (it thinks before answering), fallback = gemini-3.1-flash-lite. 3.6/3.7/3.8-flash were overloaded (503/504) during the check, so not used.
- Why: only models that answered the smoke test are safe for a demo that must run ({a demo that doesn't run is the worst outcome}); the fallback chain (retry once, then fallback) absorbs Google's overload spikes, shown live when the strong call fell back.
- Trade-off: no true "Pro" tier, so the strong model is a Flash with thinking; verdict quality to be checked on real promise-tracker data (EN-13). Model names change often: re-run `py smoke_test_llm.py` before the deploy gate. Writeup should say this honestly.
- Evidence (free key, probed 2026-11-14 with one tiny call each): OK = gemini-3.5-flash (102 output tokens, it thinks), gemini-3.5-flash-lite, gemini-3.1-flash-lite (1 output token each). 404 "no longer available to new users" = gemini-2.5-flash, gemini-2.5-pro. 503/504 overloaded = gemini-3.8-flash, 3.7-flash, 3.6-flash. Smoke test: cheap call answered by 3.5-flash-lite; strong call got 504 then 503 on 3.5-flash and was answered by the fallback 3.1-flash-lite. Re-run `py smoke_test_llm.py` to refresh this.

### D-062 · HAL replaced by Vijaya Diagnostic (VIJAYA) · 2026-11-15 · BE-10 (completes D-055) · Status: decided
- Options: VIJAYA (Vijaya Diagnostic, healthcare services) / SAFARI (Safari Industries, consumer goods) / SANSERA (Sansera Engineering, auto components)
- Chosen: VIJAYA. All three loaded in yfinance (30 daily rows each). Approx. market cap from yfinance shares x last close: VIJAYA ₹14.5k cr, SAFARI ₹6.6k cr, SANSERA ₹29.4k cr (so SANSERA is not a small-cap).
- Why: fills the healthcare-services gap (portfolio had pharma but no services), regular concalls for the promise tracker, non-defence (ENAM values). Not yet checked: that its BSE filings load (blocked, see D-063); SAFARI is the fallback pick if its filings are thin.
- Trade-off: not the smallest of the three; SAFARI is the truer small-cap by size.

### D-063 · BSE filings API blocks scripts · 2026-11-15 · BE-2, BE-3 (reopens D-012, D-013) · Status: decided via D-064
- Finding: api.bseindia.com returns 403 "Access Denied" (bot shield) to Python/PowerShell requests even with browser headers and after visiting the home page: announcements, scrip list and search endpoints all blocked. NSE's public symbol list (nsearchives.nseindia.com/content/equities/EQUITY_L.csv) downloads fine (symbol, name, ISIN).
- Not done: spoofing a browser's network fingerprint to get past the shield (bypassing bot protection; the permission check blocked it and we should not).
- Options: A NSE corporate-announcements API with a normal cookie session (D-012 option B; may also block, untested) / B build the fetcher against BSE anyway and ship a frozen snapshot of filings captured by the user from a real browser session / C demo on snapshot filings only plus a clear "live filings blocked by exchange" banner
- Chosen: —
- Why it matters: {corporate announcements} drive the whole Push side; {a demo that doesn't run is the worst outcome}, so the snapshot path must exist whichever live option works.

### D-064 · NSE announcements API is the filings source; no BSE scrip codes · 2026-11-15 · BE-2, BE-3 (settles D-012, D-013, D-063) · Status: decided
- Options: A NSE corporate-announcements API / B BSE fetcher + snapshot captured from the user's browser / C snapshot-only with a banner
- Chosen: A (user pick). Tested 2026-11-15: NSE's API answered plain requests (no cookie, no TLS tricks) for all 19 tickers plus WIPRO and MARUTI; BSE's stayed blocked. Snapshot fallback still built (D-012 intent). Ticker validation uses NSE's own EQUITY_L.csv shipped as `data/equity_list.csv` (2,635 symbols, works offline, any NSE ticker); BSE scrip codes dropped because NSE uses our symbols and ISINs.
- Result: `py run_filings.py` prints 7 days for all 19 stocks (25 filings; 6 stocks had none that week, which the empty-window banner D-046 handles). Fields: date, title, category (NSE's own label, e.g. "Change in Director(s)"), pdf_url; no sub-category, so the classifier (EN-2) refines from category + title.
- Why: {corporate announcements} drive Push, and a live source that works beats snapshot-only. NSE categories are finer than BSE's for ranking.
- Trade-off: unofficial API, can block or change (or block Render's IPs at deploy: test early at the Sat 20:00 gate); BSE-only listings are not supported; the symbol list goes stale for new listings (refresh by re-downloading the CSV).

### D-065 · Today shows every High filing; classifier and ranker choices · 2026-11-15 · EN-2, EN-3, EN-4, EN-18 · Status: decided
- Options (card count): A cap at 5 cards, rest under "More (N)" / B show every High filing, no cap / C cap at 3
- Chosen: B (user pick, overrides the 3–5 card limit in CLAUDE.md and the 3–5 wording of EN-4). Digest = `cards` (all High), `summaries` (Medium, one line), `routine` (Low, "Routine (N)"). Over 90 days the 19 stocks had ~142 High of 717 filings (about 1.6 a day), so a normal day stays short; a results-season day will not.
- Sample check (D-A): 50 varied filings from the 90-day pull, labelled by Claude from the titles alone, to be reviewed by the user (`tests/sample_labels.json`). Rules score 48/50 (96%); the 2 misses are Low-vs-Low (Infosys client-news "Updates" read as press releases) and change no ranking. Pytest enforces ≥90%.
- Classifier choices made while building (all in `engine/classifier.py`, tiers in `config.py`):
  - NSE has no "Financial Results" label; results arrive as "Outcome of Board Meeting" with "financial results" in the title, so the classifier reads title keywords for vague labels (Updates, General Updates, Press Release, Outcome ...), ~40% of filings.
  - New category `board_outcome` (Medium): a board outcome with no detail in the title (e.g. "Outcome of Board Meeting held on ...") is never hidden as Low, since it might be results.
  - Generic "Action(s) taken or orders passed" (mostly GST/tax notices, Bharti filed many) go to Routine unless the title shows NCLT/court/penalty/show-cause; otherwise High cards would flood. AI fallback EN-19 stays P2.
  - Press releases about results are Low (the results filing is the High card; avoids a duplicate).
  - "alert" chip = High category that is toggled on (D-047 literal); price/volume boost reorders within a tier and sets `moved_same_day`, it never changes the tier.
- Known gaps: unclassified is 38% of filings (mostly routine: ESOP, newspaper copies, trading windows); a stock's generic board outcome in results season stays Medium until EN-19. If the 24h window holds only routine filings (a quiet Sunday), the digest shows 0 cards and "Routine (N)" and does not widen: D-046 widens only when the window has no filings at all. Revisit if that looks empty on the phone.
- Trade-off: no card cap means a heavy day is long; the tier is the filter, so the cost is length, not noise.
- Sample review (2026-11-15): user reviewed the 50 labels in `tests/sample_labels.json` and approved them, so the 48/50 (96%) accuracy now rests on user-checked labels (D-065).

### D-066 · Repo created private, visibility to revisit before sending · 2026-11-15 · OPS-1 (settles D-038 for now) · Status: decided
- Options: public / private
- Chosen: private, `github.com/yapper-netizen/finn`, full history pushed (no secrets in history: `.env` never committed, scanned for Gemini key pattern). Decide public vs inviting assessment@enam.com before the email (Sun 15 Nov, send ≤17:30).
- Why: the repo holds ENAM's brief PDFs (`brief/`); keep them unpublished until the choice is made on purpose.
- Trade-off: reviewers cannot open a private repo until it is made public or they are invited; this must not be forgotten at send time.
