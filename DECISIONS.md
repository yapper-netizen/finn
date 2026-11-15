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

### D-067 · Web API: live cache with snapshot fallback; alerts merged into Today · 2026-11-15 · API-1, API-2, API-7 (settles D-031 for requests, D-040) · Status: decided
- Options (freshness): A live fetch + 15-min in-memory cache, parallel, snapshot fallback / B snapshot only / C live on every request
- Options (alerts): A chip on the filing card + separate "alert-only" list / B chips only / C separate Alerts tab
- Chosen: A and A (user picks).
- How it works: `engine/feed.py` loads all 18 stocks in parallel (4 workers) at server start and keeps the result in memory. After 15 minutes the stale copy is still served instantly while a background thread refreshes it (stale-while-revalidate). If the first load is not ready in 25 s or fails, the saved snapshots answer with `fallback_used: true`. `engine/today.py` builds the payload; `api.py` is thin.
- Endpoints: `GET /` (app page), `GET /health` (also says whether data is loaded), `GET /api/digest?window=24h|3d|7d&price=5&volume=2&off=cat1,cat2`, `GET /api/config` (defaults, ranges, categories, portfolio, for Settings). Thresholds and toggles ride in the URL from the phone's localStorage, so the server stores nothing per user (D-029).
- Choices made while building: toggles are sent as `off` (categories switched OFF) instead of `cats`, so new categories added later default to on for old clients; price 0.1–50 % and volume 1–20x are validated; unknown window or category gets a clear 400. Every error is JSON `{error, fallback_used}`, including unexpected ones (never a crash page).
- Alert logic: alerts come from the latest trading session in the price data and are shown whatever the filing window, labelled with `session_date`, so a Sunday visit still shows Friday's move. A stock with an alert and a filing the same day gets `moved_same_day` on that card; a stock with an alert and no filing that day goes in `alert_only` (sorted by size of move).
- Checked: live server answers in ~240 ms warm; with the network killed, `load_all` returns the same 4 cards / 1 line / 19 routine from snapshots in 0.5 s. 79 tests pass.
- Trade-off: after Render's free tier sleeps, the first visit waits for the warm-up (up to 25 s, then snapshots); the snapshot is only as fresh as the last commit (BE-7 refresh script).

### D-068 · Front end v1: shell, Today, Settings, ENAM theme · 2026-11-15 · FE-1, FE-2, FE-6, FE-11 · Status: decided
- Options (scope): A P0 screens + small P1 picks (T6, T1, T2, T4, S2, A6) / B P0 only / C everything incl. swipe triage (T3) and live preview (S1). Options (dark mode): A tokens ready, ship light only / B ship dark now.
- Chosen: A and A (user picks).
- Built (`web/index.html`, one file, Tailwind + Alpine from pinned CDN versions per D-027): tab bar (Today, Research stub, Settings); Today with 24h/3d/7d pills, every High filing as a card (D-065), "Unusual moves" cards, "Also filed" one-liners, collapsed "Routine (N)" (switched-off types marked "(off)"), widened and saved-data banners, signal strip, "That's everything that matters" end state, ENAM-voice empty state, skeletons, error state with retry; Settings with Calm/Balanced/Watchful presets, price and volume sliders, per-category switches grouped by tier, portfolio chips, reset. Everything saved in localStorage (`finn.v1`) and sent to the API as URL parameters.
- Theme (FE-11): read from enam.com on 2026-11-15: primary `#005da3`, bright `#2e7ab4`, deep `#004172`, grey `#6a6970`, border `#d2d2d2`; Helvetica body, Lato bold headings (ENAM loads HelveticaLight/LatoBold). All colours are CSS variables, so dark mode is a small later add-on. Alert red is our own (ENAM has none). Own "FINN" wordmark, no ENAM logo.
- Rule fixed while testing (D-067 refined): a stock's alert is hidden from "Unusual moves" only if it has a High/Medium filing that day; a routine filing (newspaper copy, trading window) does not explain a move. Each card now carries its same-day alert details (`alerts`).
- Bug found and fixed in testing: Alpine calls `init()` itself, so `x-init="init()"` ran it twice and the aborted first request cleared the loading state (blank screen); now one init and a request only clears state if it is still the current one.
- Checked in the browser at 375 px and 320 px: no horizontal scroll on any tab; settings persist across reload and change the result (price 3 / volume 1.5 / Management change off moved 3 cards to Routine and surfaced PIDILITIND -3.4%); error state and retry work. 81 tests pass.
- Trade-offs: Tailwind's CDN script is for prototypes (browser console warns), and the app needs the CDNs to style itself; card titles show NSE's wording (detail screens with real content come with the results card, block 7); Research is a stub until the research build.

### D-069 · Looks experiment: same wireframe, switchable skins · 2026-11-15 · FE-7, FE-2 (refines D-068) · Status: open (user choosing)
- Why: the user found v1 "too Claude-generated" but liked its concise information delivery, so the layout stays and only the visual treatment changes. Six directions were first compared side by side in `design/previews_v1.html` (A editorial, B receipt, E instrument panel, plus app-inspired C depth cards, D scorecard glyphs, F stat-on-card).
- Built (in `web/index.html`, EXPERIMENT, to be removed once one is chosen): one markup, `html[data-look]` selects the skin. Looks: classic (v1), paper (editorial: serif headlines, hairline rules, lead story), receipt (mono, stamps, ticket notches, dashed rules), panel (dot-matrix display, raised modules, LED strip), depth (layered shadows, avatars, gradient lead card), briefing (our mix: editorial type + soft depth + mono details). New elements all non-classic looks share: a big number and a gauge on "Unusual moves" cards showing how far the move went past the user's own limit (real thresholds), ticker avatars.
- Switch: the "Look" button top-right of Today, the Look section in Settings, or `?look=paper` in the URL; the choice is saved in localStorage.
- Checked at 375 px: every look renders, no horizontal scroll on Today or Settings. Next: user picks one (or a blend); then delete the others and the switcher, and apply the pick to the detail screens (FE-3) and Research (FE-4).

### D-070 · Looks round 2: six drafts after user feedback · 2026-11-15 · FE-7 (refines D-069) · Status: open (user choosing)
- Feedback on round 1: Briefing too sophisticated and its small mono type hard to read on a phone; Classic's type sizes good; Paper had no separation between cards; Receipt and Panel (dot-matrix headline) too gimmicky; Depth good but needs more separation and visual elements.
- Dropped: Paper, Receipt, Panel. Kept and doubled: Classic (c1 clean lines, c2 blue banner with tinted card headers), Depth (d1 soft depth with gradient lead card, d2 gradient header with big numeral and gradient icon tiles), Briefing (b1 readable serif headlines, b2 magazine with big serif numeral and ruled card headers).
- Rules applied to all six (checked by script at 375 px: no text under 12px, no horizontal scroll, on Today and Settings): meta text 13px, chips 12px, no mono type for details; every card has border + shadow + inner dividers (header row, footer row); a category icon tile on every card and one-liner (24 outline icons in `ICONS`, drawn by us); section labels carry a count badge and a rule; alert cards keep the big number and gauge, footer gets "Adjust limit ›" which opens Settings; company names wrap to two lines instead of truncating.
- Markup change: header + window pills + hero now sit in one `.topband` block so banner looks can wrap them; the "Look" button and `?look=` switch stay until one look is chosen (`c1 c2 d1 d2 b1 b2`).
- Next: user picks one look (or a blend); then delete the other five and the switcher and apply the pick to detail screens (FE-3) and Research (FE-4).

### D-071 · Look round 3: Depth 1 chosen, three refinements · 2026-11-15 · FE-7 (refines D-070) · Status: open (user choosing among refinements)
- Chosen so far: Depth 1 (user pick from round 2). Classic, Briefing and Depth 2 dropped (CSS removed).
- Drafts built on Depth 1 (`html[data-look]`: d1 original kept for reference, d1a, d1b, d1c):
  - 1A Polished: radial blue glow behind the page, inner highlight on cards, soft gradient icon tiles with ring, chips with ring, "Open filing" as a tinted pill button, glossy segmented time control, glowing signal dots, fading section rules, thicker gauge with a knob at the actual value, floating rounded tab bar.
  - 1B Hero card: everything in 1A plus a gradient hero card holding the big count numeral and the signal strip; the first filing card is a pale blue-bordered card instead of a second gradient block.
  - 1C Timeline: everything in 1A plus filings grouped by day under date chips, linked by a vertical rail with nodes (red nodes for filings whose stock also moved).
- Checked at 375 px for d1, d1a, d1b, d1c on Today, Settings and Research: no text under 12px, no horizontal scroll. Also fixed: chips stay on one line.
- Next: user picks one (or a blend); then delete the other drafts and the look switcher, and apply the pick to the detail screens (FE-3) and Research (FE-4).

### D-072 · Look round 4: hero card chosen; five drafts with fixed type scale · 2026-11-15 · FE-7 (refines D-071) · Status: open (user choosing)
- User feedback on round 3: the hero card (1B) is good and goes forward; text was too small next to huge numbers with empty space beside them (e.g. "close vs previous close" beside "−3.4%", gauge labels); the "Management change" chip and "Open filing" button looked generic; dates should carry an icon.
- Type scale fixed in all drafts: card title 18px, ticker 17px, company/meta/date 14px, chips 13px, stat number 38px with its 16px label wrapping beside it (ratio about 2.4), gauge labels 14px with "your limit" in bold, section labels 13px, tab labels 12.5px. Automated check: no text under 12.5px, no horizontal scroll at 375 and 360 px.
- Dates carry a calendar icon (a clock icon where the day is shown elsewhere); a "doc" icon marks the filing button; alert-card footer links to Settings ("Adjust limit").
- Drafts (all keep the 1B hero card and floating tab bar), switch with the Look button or `?look=`:
  - h0 Hero standard: 1B with the type fixes, original pill chip and button as the baseline.
  - h1 Hero + ribbon: tinted top strip with a ribbon tag flush left and the date right; "Open filing" as a dashed attachment row with a doc tile and an arrow circle.
  - h2 Hero + spine: gradient icon spine down the left edge, category as a coloured kicker, round gradient arrow button.
  - t1 Hero + timeline: rail with category-icon nodes (the icon moves out of the card, freeing width), day headers with a calendar node, left-bar label chips, folded-corner file button, time-only footer.
  - t2 Hero + timeline 2: one card per day with rows inside, a calendar node per day on the rail, kicker label row, outlined doc button.
- Markup change: card parts are a CSS grid (strip, header, rules, footer use `display: contents`) so each draft places chips, dates and the button differently; filings are grouped by day in `cardGroups`.
- Bugs fixed on the way: date text gaps, rail nodes leaking onto the alert cards, category label colliding with the ticker in T2.
- Next: user picks one; then delete the other four, the Look button and `?look=`, and apply the pick to the detail screens (FE-3) and Research (FE-4).

### D-073 · Look round 5: H1 ribbon chosen; five ways to place "Open filing" and to club same-day cards · 2026-11-15 · FE-7 (refines D-072) · Status: open (user choosing)
- User feedback on round 4: go with H1 (ribbon); the full-width "Open filing" attachment row wastes space, so partition it inside the card; also try clubbing same-day cards the way the timeline did.
- Three ways to place the action on H1 (ribbon strip, tile + ticker, title kept): A header button (compact labelled "Filing" file button with an arrow badge beside the ticker, no footer row); B split footer (a bar in two cells: how long ago it was filed | "Open filing ↗", with a divider); C tappable card (the whole card is the link, a round arrow is the cue). Picked A and B as the best two: A is the most compact and keeps a clear label; B is a true partition with useful information on the other side; C is cleanest but drops the label the user asked to rethink.
- Two timeline-feature drafts on top of A and B: D day block (A's button; one container per day, a calendar node on the rail, strips show the time only) and E day rail (B's footer; separate cards under a day header on the rail).
- New small info: "2 days ago / Yesterday / 3 hours ago" in the B footer; on alert cards the footer shows the user's rule ("Rule: ±3% a day") next to "Adjust limit". Ribbon and date/time now share one full-width strip cell, so they cannot collide.
- Checked at 375 px and 360 px for all five on Today, Settings and Research: no text under 12.5px, no horizontal scroll, no ribbon/date overlap (the time drops out of the strip below 373px in A, B, C; ribbon text is 12.5px there).
- Next: user picks the final one (or a blend); then delete the other four, the Look button and `?look=`, and apply the pick to the detail screens (FE-3) and Research (FE-4).

### D-074 · Final front-end look: hero card + ribbon cards + header button; no timeline · 2026-11-15 · FE-7, FE-2 (settles D-069..D-073) · Status: decided
- Options (last round): A header button / B split footer / C tappable card (and D day block, E day rail, which add day grouping).
- Chosen: A, header button, as a flat list. User reason: priority order is a brief deliverable, so cards must stay in ranked order; day grouping (D, E) can reorder or split the ranking (a boosted older filing jumps to the top and day headers repeat).
- Built (final): the other four drafts, the Look switcher button, `?look=`, the Settings "Look" section, day grouping (`cardGroups`) and the split-footer helpers were removed; A's styles are now the base (`html:root` selectors, same specificity as before). Spec in `design/DESIGN_2.md`.
- Checked at 375 and 360 px on Today, Settings and Research: no text under 12.5px, no horizontal scroll, no ribbon/date overlap; 81 tests pass.
- Trade-off: no day grouping, so a quiet week reads as one list; the date in each ribbon gives the time context. Light mode only.

### D-075 · Deploy: Render free, Python 3.12, uptime pinger · 2026-11-15 · OPS-2, OPS-3, OPS-4 (settles D-032, D-034) · Status: decided
- Options: hosting A Render free / B Hugging Face Spaces / C Railway or Fly (card needed); Python A 3.12 / B 3.14; cold starts A accept and warm before sending / B free uptime pinger on /health.
- Chosen (user): A, A, B.
- Prepared in the repo: `render.yaml` (web service `finn`, free plan, Singapore region, build `pip install -r requirements.txt`, start `uvicorn api:app --host 0.0.0.0 --port $PORT`, health check `/health`, `PYTHON_VERSION=3.12.8`, auto-deploy on push, no secrets); `requirements.txt` is now runtime-only and `requirements-dev.txt` adds pytest and httpx; `tests/test_deploy.py` (5 tests: blueprint complete and secret-free, snapshot folder ships for every portfolio stock, runtime requirements lean, `.env` ignored, app exposes /health) plus the offline test QA-6 (all live sources blocked: the digest still renders 4 cards from the saved snapshot, `fallback_used` true). 86 tests pass.
- Checked locally with the exact start command and `PORT`: `/health` ok, `/api/digest` 200 (4 cards, 19 routine), page 200. No Python 3.13+ features in the code.
- Not verifiable here: Python 3.12 (only 3.14 is installed locally) and a clean-venv install (Windows Application Control blocked a pandas file in a temp venv; not bypassed). Render's first build is the real test; if a library fails on 3.12, the fix is a pin in `requirements.txt` or `PYTHON_VERSION`.
- GEMINI_API_KEY is not needed on Render yet (Today runs on rules); add it as a dashboard-only env var (`sync: false`) when the research build needs it.
- Cold starts (OPS-4): free Render sleeps after ~15 minutes idle; an uptime pinger (e.g. UptimeRobot, free, every 5 minutes on `/health`) keeps it awake. First load after a restart waits up to 25 s for live data, then falls back to the snapshot (D-067). Mention both in the writeup.
- Risk still open: NSE or yfinance may block Render's IPs; the app then shows the saved copy with a banner. Check on the deployed link.
- Result (2026-11-15): live at https://finn-viku.onrender.com. Checked from here: `/health` 200 in 0.5 s, `/api/digest` on live data (fallback_used false, 0 errors, 4 cards, 19 routine), `/api/config` ok, bad window returns 400, no horizontal scroll and no text under 12.5px at 375 px. User confirmed on an iPhone: page looks right and the filing PDFs open. NSE and Yahoo were not blocked from Render's Singapore region. Uptime pinger (OPS-4): user signing up at UptimeRobot; confirm the monitor on `/health` shows Up.
- Observation: with the default thresholds (price ±5%, volume 2x) the last session (Fri 13 Nov) crosses nothing, so "Unusual moves" is empty by design; at ±3% / 1.5x it shows PIDILITIND -3.4% and IRCTC 1.6x. Default is still open under D-007.

### D-076 · Working loop saved as the standing routine · 2026-11-15 · Process · Status: decided
- Chosen (user): for every block, brief (one exhaustive, paste-able hand-off brief with ALL decisions in tables and a context pack, saved to `briefs/`) → decide → build → record → commit → report what was done and what is not verified → prompt the next brief. The options are not asked one by one in chat before the brief.
- Saved in: CLAUDE.md ("Working loop" and "Hard-won rules"), `.claude/skills/task-briefing/SKILL.md`, and the memory file `task-briefing-format`. CLAUDE.md was also brought up to date with the real stack (NSE API, free Gemini models, Render), the real folder layout and how to run things. First brief written under it: `briefs/block-07-results-card.md`.
- Session model note for the user: Opus suggested for blocks 7 and 8 (PDF extraction, arithmetic checks, promise-tracker reasoning and the grounding guard); Sonnet is enough for block 9 and the writing tasks.
- Refinement (2026-11-15, D-076): exhaustive hand-off briefs are only for changing chats; within the same chat and folder the default is a short brief (about one screen, no context pack). For a new chat the user pastes one line, not the whole answer.

### D-077 · Block 7 decisions: results card · 2026-11-15 · BE-4, EN-5, API-3, QA-3, QA-4 (settles D-016, D-017, D-007) · Status: decided
- User picks: 1A (D-016: PDF text → cheap model copies rows as JSON → Python validates), 2A (D-017: consolidated, labelled standalone fallback), 3A (cards committed under `snapshot/cards/`, local `cache.db` AI cache), 4A (bottom sheet on tapping a Results card), 5B (D-007: default price alert ±3%, volume 2×), 6A (Claude verifies, user spot-checks one), 7B (verification set IRCTC, TITAN, HDFCBANK + ASIANPAINT, LT; DIXON added).
- Built: `data/docs.py` (allowed exchange hosts only, 30 MB cap, page-text cache; fake-bold de-dupe only on affected pages, tolerance 2), `engine/results.py`, `engine/cards.py`, `GET /api/card/{id}`, Today summary line, results sheet (verdict, mini bars, QoQ/YoY, margins, "computed" EBITDA formula, page receipts, checks), `run_cards.py`.
- Safeguards: Gemini structured output (schema), temperature 0; column dates must be quarter / −3 months / −12 months; unit read by Python from the page header; every number must be printed on the cited page; full rows must be in printed column order; OCR repairs (letter O, comma/space decimal using the table's decimals); 3-decimal values rejected; cross-checks (total income, PBT vs exceptional, PAT = PBT − tax); sub-rows summed by Python (revenue, finance cost, exceptional, tax). EBITDA computed from profit BEFORE exceptional items (refines D-054).
- Result on saved filings: 18 of 20 cards, 16 tickers; DEEPAKNTR (scanned images) and MARUTI (garbled text layer) say "could not extract" with the reason. Bharti, Infosys, Vijaya fall back to standalone (consolidated page unreadable/scanned), labelled.
- QA-4 (checked against rendered page IMAGES, not the text layer): IRCTC, TITAN, ASIANPAINT, LT, DIXON and HDFCBANK: every Revenue/Total income, PBT, PAT value (3 quarters each) and the computed EBITDA match the filing to the paisa crore. Titan's failed "PAT = PBT − tax" check is a text-layer OCR error (tax printed 607, text says 601) in a row not displayed; the check correctly flags it.
- Not verified: Render build with pdfplumber; a card built live on Render (needs GEMINI_API_KEY in the Render dashboard; precomputed cards need none); user's spot-check (6A).

### D-078 · Cards for new filings: background prebuild + precompute before freeze · 2026-11-15 · EN-5, API-3, OPS-3 · Status: decided
- Chosen (user): both "A" options. (1) When a feed refresh finds a results filing with no stored card, a background worker builds it: one at a time, 10 s apart, at most 2 tries per filing per server run, off when GEMINI_API_KEY is not set. Today's verdict line then appears without a tap; cost about one cheap-model call per new results filing. A tap on a still-queued card builds it on demand (the per-filing lock prevents a double build). `/health` shows `cards_prebuild` and `cards_built`. (2) Before the code freeze: `py run_filings.py 7`, `py run_cards.py --save`, check the new cards, commit them, so everything a reviewer opens is precomputed and checked.
- Card lookup order: `snapshot/cards/` (committed) → `.cache/cards/` (built on this machine/server; Render's copy is lost on restart) → build.
- Verified 2026-11-15: live NSE refresh (25 filings in 7 days) found no new results filings, so no new cards to commit today; a test enforces that every saved results filing has a committed card. End to end: with IRCTC's card moved aside, a live feed refresh queued it and the worker rebuilt it unaided (identical verdict). 129 tests pass.
- Risk: on Render (512 MB) a very large PDF (Infosys, 25 MB, 197 pages) parsed in the background could press memory; pages are parsed one at a time and closed. Not tested on Render yet.

### D-079 · Research documents: NSE transcripts + results; follow cover-letter links · 2026-11-15 · BE-5 (settles D-020) · Status: decided
- Chosen (user): 1A, NSE corporate announcements for both concall transcripts and results filings (one call covers ~18 months; probed for POLYCAB and PERSISTENT: 5 transcripts + 5 results each). No screener.in, no annual report (business snapshot stays out, D-023).
- Rules: one transcript per quarter, tied to the latest results published before it, first one after those results (Persistent filed an investor-meet transcript before its Q1 results); 6 results filings (one extra for year-ago and FY totals); a quarter with no `results` filing may use a bare "Outcome of Board Meeting" filed within 75 days (Persistent files results that way; the statement finder decides).
- Cover letters (user pick, asked mid-build): ASTRAL's NSE "transcript" filings are 1-page letters linking to the PDF on astralltd.com. FINN now follows the PDF link written inside the NSE filing (company's own site = still primary): https only, .pdf path, host must resolve to a public address (no IP literals, private, loopback or link-local: SSRF guard), size cap, %PDF header. Receipts cite the company-site PDF and say "linked from the NSE filing".
- Gap found: Today's classifier ranks Persistent's results (titled only "Outcome of the Board Meeting") as Medium "board outcome", not High "results". Not fixed in this block.

### D-080 · Promise tracker method: two-pass, Python facts, one verdict call · 2026-11-15 · EN-12, EN-13 (settles D-022) · Status: decided
- Chosen (user): 2A. Pass 1: one AI call per transcript lists promises with verbatim quote and page. Python: actual numbers ("facts", numbered) come only from the block 7 results cards; each fact uses one card's own columns (same basis); FY totals and FY growth only when all 4 quarter cards of that year exist with the same basis. Pass 2: ONE strong-model call per stock returns Delivered / Partial / Missed / Not checkable with fact ids; Python drops unknown fact ids (no fact = "Not checkable").
- Python decides timing, not AI: due date after the latest reported quarter, or a promise from the latest call (nothing reported since) = "Too early".
- Judging rules added after reviewing real verdicts: revenue, growth, margin, profit are higher-is-better (POLYCAB was wrongly "Missed" for margins ABOVE its 11-13% range); standing ranges judged "so far"; directional guidance judged on direction; a "Delivered" whose reason says missed/below/failed is withdrawn ("verdict and reason disagreed").
- Repeats merged in Python (same target numbers and due date, or similar wording): the first statement keeps its quote; "restated in" lists later calls.

### D-081 · Promise extraction runs on the strong model (deviation from D-022's cheap model) · 2026-11-15 · EN-12 · Status: decided (by measurement)
- Measured: on the same transcripts, the cheap model's promise list changed run to run (dropped POLYCAB's margin guidance in one run, merged Persistent's "100 bps in FY26, another 100 in FY27" into one FY27 item in another), even at temperature 0 after prompt tweaks. The strong model split multi-period promises and kept them.
- So: strong model for extraction (5 calls per stock) and verdicts/bull-bear (2 calls); the cheap model still reads every results filing (the bulk of pages). `config.RESEARCH_EXTRACT_STRONG` switches it back. Per stock ≈ 7 calls, 35-45k input tokens; answers cached, so precomputed stocks and repeat runs cost nothing.

### D-082 · What counts as a checkable promise · 2026-11-15 · EN-13 (decision 3A) · Status: decided
- Chosen (user): 3A. Judged only when it is a company-level revenue, growth, EBITDA-margin or profit promise; everything else (segments, capex, exports, working capital, EBIT/operating margin, acquisitions) is listed under "Not checkable from filings" with the quote. EBIT targets are "other" because cards carry EBITDA (Persistent guides on EBIT).
- Consequence, stated on screen: companies that guide mostly by segment or far-off targets show few judged promises (POLYCAB 2 judged of 12).

### D-083 · Reading, receipts, unknown tickers · 2026-11-15 · EN-10, EN-15, EN-16, API-4 (settles D-021, D-041, D-024) · Status: decided
- 4A: keyword-picked transcript pages (guidance, outlook, margin, FYxx, ...), ≤26k characters per transcript.
- 5A: a quote is shown only if found in the transcript text: verbatim after normalising, or ≥90% fuzzy match; a fuzzy match may never change a number (every number in the quote must be on that page; a test with "35% in FY28" for "20% in FY26" caught this). The page is corrected if the model cited the wrong one. Failed quotes are dropped and counted in the notes.
- 6A: precomputed set answers at once; any other ticker runs in a background job, one at a time (free tier), and the screen polls `/api/research/{ticker}` (queued / pending with steps / ready / error). Unknown ticker → 404 with a clear message.

### D-084 · Research screen and bull vs bear · 2026-11-15 · FE-4, EN-14 (settles D-023; decisions 7B, 8A) · Status: decided
- 8A: search + 3 ready chips; hero scorecard (judged count, Delivered / Partial / Missed bar); judged promises as rows; "Too early" and "Not checkable" collapsed; tap → receipt sheet (verbatim quote in serif, transcript page link, the filing figures used with their page links, the verdict reason, and who decided it: AI or FINN's rules).
- 7B: bull vs bear behind a two-way toggle (one list at a time, so the screen stays short); 3 points each, numbered cards with a green or red edge; each point is kept only with a verified quote or a valid filing figure (one strong call per stock).
- Checked at 375×812 and 360×740: no horizontal scroll, no text under 12.5px, on the screen, both sheets and the progress list.

### D-085 · Results extractor: unit from the filing's other statements · 2026-11-15 · EN-5 (refines D-077) · Status: decided
- Persistent's statement pages carry no unit in their text layer (image or garbled "nn,Millionl"), so 3 of its 6 results filings failed. New rule: if the statement page prints no unit, accept the model's unit only when it is the ONE unit named in the headers of the same filing's other pages; the card shows a note saying so. Otherwise still "could not extract".

### D-086 · Block 8 results and the receipts rule for targets · 2026-11-15 · EN-15, QA-8 · Status: decided
- Rule added after review: if a promise names target numbers (digits or words like "two", "double"), at least one must be in the quote itself; else the promise is dropped with a note. Seen on HAVELLS: a verbatim quote "No, that remains as is..." whose target sat in the analyst's question.
- Precomputed (snapshot/research): POLYCAB 12 promises, 2 judged (both Delivered: EBITDA margin at or above the 11-13% and 12-14% guidance); PERSISTENT 11, 1 judged (Delivered: FY26 margin +100 bps); ASTRAL 13, 0 judged (its guidance is by segment and volume; transcripts fetched from the company site via the NSE filings' links).
- Unknown tickers (QA-8), live through the HTTP API and the Research screen: HAVELLS (13 promises, 1 judged Missed, ~7 AI calls, slowed by free-tier 503 retries) and NAUKRI (11 promises, 0 judgeable, ~4 min; 2 of 6 results filings unreadable, shown as notes). Both end to end, no crash.
- Limitation, stated on screen: segment-level guidance is listed but not judged (results filings do print segment tables; reading them is the main next step). Promise selection by the model still varies when its prompt changes; answers are cached, so a given prompt gives a stable result.

### D-087 · Management-change card from the filing's own annexure · 2026-11-15 · EN-6, FE-3 (settles D-019; decisions 1A-4A) · Status: decided
- 1A: the filing's SEBI annexure is the only source (no LinkedIn, no outside knowledge). The cheap model lists every change (event, person, role, previous role, date, reason, verbatim profile quote, 1-2 line bio of that quote). Python checks: the name must be printed in the filing, the date must be printed (whole words: a test caught "3 Nov" matching "13 Nov"), the role's words must be printed, the profile quote must be found (verbatim/fuzzy with exact numbers, or, for two-column annexure tables whose text interleaves, every word in order within a short span). Unverified items are dropped or blanked with a note. "Profile disclosed earlier" or "Not applicable" = no bio, said plainly.
- 2A: all management changes get a card that adapts (appointment, re-appointment, resignation, retirement, cessation, role change, auditor change). 3A: precomputed for the snapshot filings (25 cards) and prebuilt in the background for new ones (D-078); Today shows the headline ("Re-appointed: V. Srinivasa Rangan, Whole-time Director..., from 23 Nov 2026"); tap opens the same bottom sheet as Results.
- 4A: "Key role" badge by a Python rule (company-level CEO, MD, CFO, Chair, Vice-Chair, whole-time/executive director, COO; not a unit's CEO, not a VP). Ranking untouched (D-065). The badge sits on the summary line, not in the ribbon strip, which it overlapped by ~60 px at 375 px.
- Checked: 11 recent filings (ASIANPAINT, ASTRAL, DMART, HDFCBANK ×3, TITAN ×2, VIJAYA, WIPRO) build, every bio with a verified quote; layout at 375 and 360 px clean.

### D-088 · AI retries: back off on overload, skip on quota, say when the fallback answered · 2026-11-15 · EN-9, OPS (decision 6A) · Status: decided
- Seen: on Render a whole HAVELLS research run was answered by `gemini-3.1-flash-lite` (fallback), not `gemini-3.5-flash`; locally the free tier often returned 503 "high demand".
- Now: on 503 wait `LLM_BACKOFF_S` (4 s, then 12 s) and the strong model gets one extra try before falling back; on 429 (quota used up) go straight to the fallback; research JSON carries `ai.fallback_used` and the Research screen says "part of this answer came from the backup AI model" when true.
- Open: whether Render's key hits the strong model's daily limit; the user checks usage in Google AI Studio.

### D-089 · Results hidden in "Outcome of Board Meeting" filings are promoted · 2026-11-15 · EN-2, EN-5 (decision 7A) · Status: decided
- A filing classified `board_outcome` and filed within 75 days of a quarter end is opened (no AI): if the statement finder finds a results table, its results card is built and Today ranks the filing as High "results" (`kind_override`, applied before ranking; inputs not mutated). Found: PERSISTENT Q2 FY27 (15 Oct; unit million read from the filing's other statements, D-085, checked against the page image: revenue 46,639.04 / PBT 4,536.84 / PAT 3,515.14 ₹ million, all match) and TRENT. Non-PDF filings are "not results".
- Also: QA-6 offline test now covers the whole app (prices, filings, PDF downloads and AI all failing: Today, saved cards and saved research still answer). QA-8 recorded in D-086 (HAVELLS, NAUKRI).
- OPS-4: relies on the user's UptimeRobot monitor on /health (5-minute pings); stated in the writeup with the cold-start fallback.

### D-090 · Code freeze: one refresh command, research rebuilt only on new documents · 2026-11-15 · BE-7 (decisions 1A, 4A, 5A) · Status: decided
- `py refresh_snapshot.py`: live prices + 7 days of filings for all 19 stocks (merged into snapshot/), cards for saved filings that have none (results, management, board-outcome candidates, last 30 days), research for the precomputed set only if NSE lists a transcript or results filing it had not seen (`documents_seen` recorded in each research file). `--no-ai` stops after prices and filings.
- Bug found on the first run: the check compared against the documents the research USED, so an unreadable results filing (POLYCAB Q3 FY26) looked new every time and forced a rebuild. Fixed and tested.
- Freeze run (15 Nov, ~16:30 IST): no new filings since the last snapshot, so no new cards. The precomputed research had steps answered by the backup model during earlier 503 spells; those 37 cached answers were removed and the 3 stocks rebuilt, but `gemini-3.5-flash` now returns 429 "exceeded your current quota" on this key too, so the rebuilt steps came from the backup model again. Verdicts and counts are unchanged (POLYCAB 2 Delivered, PERSISTENT 1 Delivered, ASTRAL 0 judged); each file says `fallback_used: true` and the Research screen shows the note. Re-run `py run_research.py POLYCAB PERSISTENT ASTRAL --save` after the daily quota resets (after removing the backup-model research answers from cache.db) to restore strong-model answers.
- Also found: `run_research.py` crashed on import (circular import research -> cards -> mgmt -> research, hidden in tests because `cards` was imported first). Quote guard moved to `engine/quotes.py`; a new test imports every entry point in a fresh interpreter.
- D-088 diagnosis: the strong model's free daily quota is used up (429 on both the local key and, by the same symptom, Render's), not a temporary overload. Options for the user: wait for the reset, or a second free key in a new Google project for Render.
- 4A: git tag `v1.0` on the freeze commit; after it, fixes only, each re-tagged (v1.0.1 ...). 5A: snapshots keep growing (filings are small; cards point to them).

### D-091 · "Brief me": Today in three sentences, read aloud, no AI · 2026-11-15 · FE-9 (settles D-052, decision 2A) · Status: decided
- A button on Today's hero card. Python builds three sentences from the digest the screen already shows: (1) how much matters, counted by kind so the parts add up to the headline number ("5 things matter: 3 management changes, 1 results filing and 1 unusual move"); (2) the top card ("Top of the list is a key management change at HDFC Bank: V. Srinivasa Rangan re-appointed as Whole-time Director ... from 23 Nov 2026"); (3) the biggest unexplained move. Read by the browser's free speech engine (Web Speech API, Indian English voice when available), the sentence being read is highlighted, a second tap stops it, switching window or tab stops it; browsers without speech show the text with a note.
- Why no AI: instant, free, and it cannot say anything the cards do not. Tests caught two wording bugs (counts not adding up; "1 routine filings").

### D-092 · v2 revision plan adopted; research views · 2026-11-15 · Block 10b (decision 1A) · Status: decided
- Review against both brief PDFs written to `plan_revamp_v2/revision.md` (checklist, hidden cues, push/pull/interaction ideas); routing plan in `plan_revamp_v3/routing.md` (decisions deferred by the user, to be discussed later).
- Research v2 views: Business snapshot, Financial snapshot, Trajectory, Balance sheet with cash quality folded in (cash flow sits on the same filing page; the reference doc names "profit without matching cash" a red flag), deeper Narrative vs numbers, Bull vs bear kept. Guidance is not a separate view: a "Guidance only" filter inside Narrative vs numbers.

### D-093 · Numbers for the new views: XBRL first, results-filing PDFs as fallback · 2026-11-15 · Block 10b (decision 2: C then A) · Status: decided
- First probe NSE's XBRL [machine-readable filing data] for results, balance sheet, cash flow and segments; if it is reachable and complete, numbers need no AI. If not, read the same PDFs the results cards already download (half-yearly balance sheet and cash flow under SEBI LODR Reg 33, quarterly segment table, verified present in `.cache/pages`), plus 1-2 older Q4 filings for a multi-year view. No annual-report downloads unless asked.

### D-094 · "What the company does": AI-written from the documents, every sentence backed · 2026-11-15 · Block 10b (decision 3, user's variant of A) · Status: decided
- The user's call: the description is the model's own summary after reading the primary documents (transcript, results filings, AR if present), not a literal quote, with more depth (segments, customers, model of earning), inspired by the user's NUS project.
- Guard (keeps {"don't lean on the model's own outside knowledge"}): the model sees only document text; each sentence must return a supporting snippet + page that the quote guard finds in the document; a sentence without support is dropped. The receipt shows the snippet, so the sentence is a paraphrase with evidence.

### D-095 · Narrative vs numbers depth: core four + tone vs numbers · 2026-11-15 · Block 10b (decision 4B) · Status: decided
- N1 segment-level judging, N2 say-do (promised vs delivered) chart, N3 credibility meter, N7 guidance filter, plus N4 tone vs numbers (confidence of management's remarks per quarter, scored by the cheap model with a quote, against actual YoY growth).

### D-096 · Charts: hand-built SVG in the app's own visual language · 2026-11-15 · Block 10b (decision 5A) · Status: decided
- Inline SVG, no chart library. Must match the existing theme literally: ENAM tokens, the hero card's depth (layered surfaces, soft shadows, ribbon accents), same type scale; one shared chart style so every view feels part of one product.

### D-097 · Research layout: build A, then try B inside it · 2026-11-15 · Block 10b (decision 6) · Status: decided
- Build one scroll with sticky section chips first; then trial tabs (B) integrated into it, and keep what reads better on the phone.

### D-098 · Interaction: Copilot in context + Pulse first, then chat and voice · 2026-11-15 · Block 10b (decision 7: A, then B) · Status: decided
- After the research views. Significant time planned here; Copilot in context (I1) and Pulse dashboard (heatmap + event calendar) first, then fold in chat and voice (I2, I3). Details brainstormed again when the block starts.

### D-099 · Push refinements: build five, judge on screen · 2026-11-15 · Block 10b (decision 8) · Status: decided (trial)
- Build P1 since-you-last-looked, P2 why-buried, P4 live threshold preview, P6 management headline + LinkedIn search, P8 results card shows the matching promise. The user keeps or drops each after seeing it.

### D-100 · Research search: typeahead, recents, kept results · 2026-11-15 · Block 10b (decision 9A) · Status: decided
- `/api/symbols?q=` over the shipped NSE list (symbol and company name; portfolio, research set and stored research ranked first); recents in localStorage; the server lists every stored research; the browser keeps a copy of each finished result so it survives Render restarts on that phone; `run_research.py --save` still promotes one to `snapshot/`.

### D-101 · Order of work · 2026-11-15 · Block 10b (decision 10A) · Status: decided
- 10c search fixes → 10d data layer (XBRL probe, then PDFs) → 10e research views → 10f Narrative vs numbers → 10g interaction → 10h push → routing (decisions later) → tag `v1.1`.
- Built (block 10c): `data.symbols.search` ranks exact symbol > symbol prefix > name-word prefix > initials > contains, preferring portfolio, research set and stored research; `/api/symbols?q=` and `/api/research` (list); Research screen: suggestion list (keyboard arrows + Enter, a typed company name opens the top match), "Ready to open" chips (server + this phone, recently opened first), "Recent" chips for tickers not ready; finished live runs kept in localStorage (`finn.research.v1`, newest 12) and opened from the phone when the server has lost them or is unreachable ("Kept on this phone · researched …"). Checked at 375×812 and 360×740 (no horizontal scroll, badge text 12.5px). 5 new tests (183 pass).

### D-102 · Lessons carried over from the user's NUS greenwashing pipeline · 2026-11-15 · Block 10d · Status: decided
- The user's NUS project (5-stage NLP pipeline over 100+ ESG reports; relevance filter before the LLM; proxies from financial statements; structured pledge extraction) maps onto FINN v2: (1) **relevance filter before AI**: pick only the pages/passages that matter (statement pages, business-overview passages) before any model call, as page picking already does; (2) **proxies from statements, labelled**: when a figure is not printed, estimate it from lines that are (e.g. capex ≈ change in net fixed assets + depreciation when no cash flow statement is filed), shown as "proxy" with the formula, like computed EBITDA (D-054); (3) **promises = pledges**: structured extraction with a target, a metric and a deadline, then checked against numbers (already the promise tracker; deepened in 10f).
- Company description (D-094) follows the same stages: filter passages → structured extraction (what they sell, segments, customers, how they earn) → verify each sentence's support → assemble.

### D-103 · Block 10d: statements from NSE XBRL, reconciled with the printed filings · 2026-11-15 · D-093 (XBRL path taken) · Status: decided
- XBRL works for every stock tried: two NSE listings (`integrated-filing-results` from 2025, `corporates-financial-results` back to 2023) give one file per quarter and basis; the user approved downloading them (NSE archive, 30-300 KB each, ~13 per stock). Parser ignores the namespace (2020 BSE and 2026 SEBI taxonomies share tag names). No AI anywhere in this block.
- `engine/financials.py`: 13 quarters (3 years + year-ago) of revenue, computed EBITDA (D-054), PBT, PAT (owners' share when there is a minority, as cards print), margins, segment revenue/result, QoQ/YoY; half-yearly balance sheets (equity attributable to owners, debt, cash incl. bank balances and current investments, net cash, inventories, receivables, payables, fixed assets, D/E); cash flow H1 and H2 (= full year − H1): CFO, capex, FCF, cash conversion; ratios at the latest balance sheet: TTM revenue/EBITDA/PAT, ROE (average equity), ROCE (EBIT ÷ average equity + debt), working-capital days on revenue, cash cycle; banks: total income, NII, PPOP, provisions, PBT, PAT, deposits, advances, advances/deposits; capex proxy (D-102) only when no cash flow is filed; auditor's opinion line.
- Checks: PBT − tax = PAT and assets = equity + liabilities on each file; every quarter that has a PDF-verified results card is compared line by line, and the printed figure wins with a note. Found two real cases: (1) POLYCAB's tagged PAT includes the minority share (fixed by using the owners' tag; all 5 card quarters then match); (2) HDFC Bank tagged ₹837 cr of minority interest as "exceptional items", so its tagged PBT is ₹27,825 cr vs ₹28,663 cr printed: FINN shows the printed figure and says why.
- Verified against PDF pages: POLYCAB (inventory, CFO, capex, owners' equity), ASTRAL (inventory ₹1,425.6 cr, CFO ₹−68.0 cr, capex ₹318.4 cr, owners' equity ₹4,239.1 cr), HDFC Bank (deposits, advances) all match; P&L for POLYCAB, PERSISTENT, ASTRAL, HDFC Bank via the card reconciliation. PERSISTENT balance sheet not checked against a page.
- Live generalisation: IRCTC and TCS built in ~6 s each, no checks failed.
- `/api/financials/{ticker}`: precomputed from `snapshot/financials/` (POLYCAB, PERSISTENT, ASTRAL), else built on request and kept in `.cache/financials/`; NSE down → JSON 503. The PDF fallback for balance sheet/cash flow (D-093 option A) is not built: if NSE stops serving XBRL, the views say "not available" and P&L still comes from results cards. Not yet in `refresh_snapshot.py`.

### D-104 · Block 10e: research views (snapshot, trajectory, balance sheet & cash) and the company profile · 2026-11-15 · D-092, D-094, D-096, D-097 · Status: decided
- Research screen is now one scroll with a sticky chip bar (Snapshot · Trajectory · Balance sheet · Promises · Bull vs bear; scroll-spy highlights the current one). Tabs (D-097 option B) not tried yet.
- Company hero (same blue depth card as Today): 12-month revenue (banks: total income), latest quarter's growth and margin, three glass stats (ROE, ROCE, net cash; banks: ROE, loans ÷ deposits, 12-month profit).
- Snapshot: "What they do" (D-094, `engine/profile.py`: relevance filter → one cheap call → each sentence kept only if its passage is found on the transcript page and its numbers are in the passage; ~5k tokens per stock, cached; `/api/profile/{ticker}`, needs the stock's research; committed for the 3 research stocks, 0-2 sentences dropped each); six KPI tiles with sparklines, each opening a "Computed by FINN" receipt (formula, inputs, XBRL link); segment mix as 100% bars for 6 quarters with latest share and segment margin.
- Trajectory: growth-vs-margin path (one dot per quarter, revenue growth YoY across, EBITDA margin up; banks: profit margin) and quarter-by-quarter bars for revenue, EBITDA and PAT (13 quarters, YoY chip).
- Balance sheet & cash: "what it owns / who paid for it" mirror bars with one-year changes; working-capital clock (inventory + receivable days on the outer ring, payable days back on the inner ring, hand at the cash cycle, dashed hand a year ago); profit-to-cash waterfall (PAT → depreciation → working capital → operating cash → capex → free cash) with cash-conversion chips per half; checks strip (auditor opinion from the latest filing that has one, D/E, negative operating cash, low conversion, data notes). Banks: no clock or waterfall (not meaningful).
- Charts: hand-built SVG in the ENAM palette and the card depth of Today (D-096); chart text ≥13px at 360 px wide (measured). Checked at 375×812 and 360×740: no horizontal scroll, no console errors. A finished stock's financials and profile are kept on the phone with its research (D-100).

### D-105 · Block 10f: narrative vs numbers, deeper (N1-N4, N7) · 2026-11-15 · D-095 · Status: decided
- N1 more promises judged: the verdict step now also gets Python-made facts from XBRL (D-103): segment revenue and growth per quarter and fiscal year, segment result margin (labelled "before interest and tax, not EBITDA"), capex per half and full year (₹ crore), effective tax rate per fiscal year, cash conversion per half. A non-headline promise goes to the verdict step only if FINN may hold a figure for it (`worth_judging`); volumes, market share, exports, deals, dividends, working capital, and operating/EBIT-margin targets stay "Not checkable" by rule. Judge prompt: a promise about one business inside a combined segment ("Paints and Adhesives") is Not checkable; EBITDA targets are never judged against segment results; capex in crore (1 billion = 100 crore).
- Python guards on AI verdicts (`guard_verdict`): annual capex judged on half-year capex only → "Too early"; "Delivered" with the figure below the target (or capex outside the range) → no verdict shown, with the reason. Found by reviewing the first rebuild: the backup model called POLYCAB's annual capex "Delivered" from H1 spend, and judged PERSISTENT's operating-margin aim against EBITDA margin.
- Results (rebuilt): POLYCAB 3 Delivered (EBITDA-margin ranges ×2, FY26 capex ₹1,481 cr vs ₹1,200-1,600 cr) + 6 too early + 3 not checkable; PERSISTENT 2 Delivered (FY26 tax rate 22.6% vs 22.5-23.5%; cash conversion normalised); ASTRAL 1 Missed (FY26 capex ₹459 cr vs ₹300-350 cr guided), its paint/adhesive/bathware/polymer promises honestly Not checkable (no such segment in the filings).
- N2 promised vs delivered: target from the model or, if absent, parsed by Python from the promise's own words (`target_from_statement`); every target number must appear in the statement or quote; the delivered number is a Python fact (`pick_actual`: latest cited fact in the promise's unit). Dumbbell rows (band = promised, dot = delivered), one scale per row.
- N3 credibility meter: one square per promise in the hero (delivered / partial / missed / too early / not checkable).
- N4 tone vs numbers: one cheap call over each call's opening remarks (pages where management speaks most, not the operator agenda), score −2..+2 with a verified quote; Python pairs each call with that quarter's and the next quarter's revenue growth and flags "upbeat, then slowed" / "cautious, then accelerated" (≥5 points). Chart: tone line over growth bars; list with receipts.
- N7 guidance filter: "All promises / Headline guidance" (company-level metric, or a stated figure for revenue, growth, margin, profit or capex).
- Research ENGINE_VERSION 2; saved v1 results still open (without these parts). Strong-tier answers that came from the backup model are no longer cached, so a rebuild retries the strong model (the free strong quota was exhausted again today; the screen says when the backup answered; 23 cached backup answers removed).
- Bug fixed from v1.0: an unescaped apostrophe ("FINN's rules") broke the receipt note for rule-decided promises (blank note + console error).

### D-106 · Ship 10f verdicts from the backup model; push after 10g · 2026-11-15 · Block 10f follow-up (decision A) · Status: decided
- The precomputed research keeps today's verdicts and bull/bear from the backup model (`gemini-3.1-flash-lite`): they pass the Python guards (D-105) and the screen already labels them. The writeup names it as a free-tier limit. No rebuild after the quota resets unless the user asks.
- Push to `main` (Render redeploy) once block 10g is built, together with 10c-10f.

### D-107 · Block 10g decisions: Copilot, Pulse, Ask FINN, voice · 2026-11-15 · D-098 (decisions 1A, 2A, 3A, 4 all, 5A, 6A) · Status: decided
- 1A Copilot answers: Python answers number questions from the stock's figures (no AI); other questions go to the cheap model with only the best-matching transcript passages and figures; every claim must carry a verified quote or a figure id, else FINN refuses. Price targets, buy/sell and news are refused by rule.
- 2A Copilot lives in the research view and the results-card sheet, with 3 suggested questions each.
- 3A Pulse is a new tab; the app still opens on Today; Today's signal strip opens Pulse.
- 4 Pulse shows a portfolio heatmap (DB1), a 14-day event calendar from NSE's event-calendar and corporate-actions APIs (DB2, JSON, snapshot fallback), and a price-move vs volume scatter with the Settings thresholds (DB6).
- 5A Ask FINN across the portfolio: the cheap model turns the question into a structured query; Python answers from the digest, alerts and calendar. Same box as the Copilot, with a "This stock / My portfolio" switch.
- 6A Voice: mic on the Ask box (browser speech recognition, free), answer read aloud; typed fallback where unsupported.

### D-108 · Block 10g built: Copilot, Pulse, Ask FINN, voice · 2026-11-15 · D-107 · Status: decided
- Copilot (`engine/copilot.py`, `POST /api/ask` with `ticker` or `filing_id`): rules refuse advice/price targets/news; Python answers number questions from the XBRL figures (EBITDA, margins, profit, ROE/ROCE, debt and net cash, cash cycle, capex, cash flow, segments, tax rate, revenue/growth; quarter named in the question is honoured); other questions retrieve the best-matching transcript (or filing) passages by keyword overlap and ask the cheap model for ≤3 sentences with citations; quotes are verified on the page, figure ids must exist, uncited answers are not shown. If the calls do not explain something but FINN holds the figure, it says so and shows the figure. Passage ids are stripped from the text. Research view: floating "✦ Ask"; results sheet: "Ask about this filing"; 3 suggested questions each.
- Live checks: POLYCAB (EBITDA margin 14.4% by Python; FMEG commentary with 5 verified quotes p.7-8), PERSISTENT (Nagarro, p.6), ASTRAL (negative operating cash → "not explained in the calls" + the ₹−68 cr figure; "undervalued?" refused), HAVELLS outside the research set (figures built from XBRL on the fly; cables commentary p.3, p.10), IRCTC results filing (exceptional items quoted from the notes); off-topic → "Not in the documents FINN read."
- Pulse tab (`engine/pulse.py`, `data/events.py`, `GET /api/pulse`): hero (how many of 18 rose/fell, average move, best/worst, how many filed something that matters), 3×6 heatmap (colour = day's move, dot = High/Medium filing that session, tap = detail with Research/Today buttons), move-vs-volume scatter against the user's own thresholds (live with Settings), calendar: NSE confirmed events next 14 days + "Results expected" (same quarter last year moved forward a year, labelled estimate) + last 7 days. Events: NSE event-calendar + corporate-actions JSON for the 18 stocks (3 workers, ~3 s), cached 6 h in the background, `snapshot/events.json` fallback. Today's signal strip opens Pulse. Found on the first live fetch: results season had ended, so nothing was confirmed for the next 14 days; the expected-dates list keeps the calendar useful and honest.
- Ask FINN (`engine/askfinn.py`, `POST /api/ask` with `portfolio: true`): the cheap model only fills a query form (intent filings / moves / events / company / unsupported, tickers, categories, days, direction, limit); Python answers from Today's ranked filings, Pulse rows and the calendar; company questions route to that stock's Copilot; advice refused before any AI call; a rule parser fills the form if the AI fails. "✦ Ask FINN" button on Today and Pulse; "This stock / My portfolio" switch inside a stock's Ask sheet.
- Voice: mic on the Ask box (Web Speech recognition, en-IN, interim text shown, sends on stop), spoken questions get the answer read aloud (₹ → "rupees", cr → "crore"); unsupported browsers see "this browser can only type"; refused microphone permission is reported. Not verifiable in the Browser pane (microphone blocked): needs a phone check after the push.
- Tab bar now Today · Pulse · Research · Settings. Checked at 375×812 and 360×740 (no horizontal scroll, no console errors). Tests: 231 pass.

### D-109 · Block 10h built: five push refinements (P1, P2, P4, P6, P8) · 2026-11-15 · D-099 · Status: decided (trial: the user keeps or drops each after seeing it)
- P1 since you last looked: the browser stores the India-time stamp of the data it last showed (`finn.visit.v1`, saved when the page is hidden or closed; not when the saved copy was served). Next session, filings newer than that get a green "New" chip; the hero says "4 new since Thu 12 Nov" or "Nothing new since 20:35. You are caught up."; an "Only new" toggle filters the cards and one-liners. The first ever visit shows nothing. Card order stays tier-then-move-then-newest (D-065): no time dividers.
- P2 why buried: Python rules (`engine/classifier.buried_reason`, no AI) give every Routine filing one sentence (trading-window closure, ESOP allotment, newspaper copy, compliance certificate, auditor's report, store opening, call notice, investor-meeting schedule, shareholder-meeting paperwork, or "you switched this type off" with a link to Settings). The open Routine box leads with the test ("would a long-term fund manager change a view because of this? For these, no.") and counts by reason; the closed row says "tap to see why".
- P4 live threshold preview: `/api/preview` returns the last 7 sessions' day moves and volume multiples for the 18 stocks (same maths as the alerts); Settings counts them against the sliders as they move ("At ±3%, 12 day moves in the last 7 sessions (±2%: 27, ±4%: 2)", "At 2×, 9 volume spikes") and draws alerts per day. A price and a volume alert on one stock-day are two alerts, as on Today. Past days only; the box says it is not a forecast.
- P6 management card: `engine/mgmt.enrich_card` (one cheap call per card, over the filing's own profile text) adds earlier employers, years of experience and qualifications; each item is kept only if printed in the profile (duplicates like "Dabur" / "Dabur India Ltd" merged). Line: "Joins from Pfizer Limited, Hindustan Unilever Limited, Vedanta Resources Limited · 22 years' experience · Chartered Accountant"; Today's card shows it under the headline with the person's name. Exit style by rules from the wording and dates: Planned (retirement, end of tenure), Immediate (same-day effect or "with immediate effect"), Notice given (later effective date). Two rule bugs found by reading the 25 backfilled cards: "close of business hours" is ordinary scheduled wording, not "immediate", and "will complete his tenure" is planned (HDFC Bank's CEO exit). "Search LinkedIn for <name>" opens a LinkedIn people search in the user's browser (name + company from the filing); FINN fetches nothing from LinkedIn. Tenure of the outgoing person is not shown: filings do not state it, and the brief's {"where they came from"} is about the incoming person. `py run_mgmt_enrich.py` backfills saved cards (25 done; 15 have a background line).
- P8 push meets pull: `/api/card/{id}` adds `promises` to a results card (not stored on it): the promises whose evidence includes that quarter (or the fiscal year a Q4 completes), or that fell due in it, judged ones first (Missed, Partial, Delivered), up to 3, each with the promised-vs-delivered bar and a tap to its receipt; plus the next promise to be tested. A stock with no research gets "What did they promise? Research X to compare…" which opens Research. POLYCAB's Q2 FY27 card shows its two EBITDA-margin guidance promises, both Delivered (14.4% vs 11-13% and 12-14%).
- Checks: 243 tests (12 new); 375×812 and 360×740 on Today (with a previous visit), Settings, a results sheet and a management sheet: no horizontal scroll, smallest text 14px, no console errors. Live Render check of /api/pulse and /api/ask done after the 10g push.

### D-110 · Block 11: deliverables and Settings tier buttons (option A) · 2026-11-15 · Block 11 (decisions 1C, 2A, 3A; tiers option A) · Status: decided
- Settings: each filing type has a Card / Line / Routine control (High / Medium / Low), FINN's own choice marked, saved in the browser (`settings.tiers`), sent to `/api/digest?tiers=results:Medium,...` and applied in the ranker; a type the user puts in Card gets the "alert" chip; one moved to Routine is shown "(moved by you)" with the reason. "Reset filing types to FINN's defaults" clears the overrides. The old on/off switches migrate to Routine. Adding or removing portfolio stocks (option B) is left to "next steps" in the writeup (depends on NSE and yfinance being up for arbitrary stocks).
- Build history (1C): the Claude Code sessions ran locally and have no share links, so `build-history/` holds readable, scrubbed copies of the four chats (messages + one line per tool call; no raw tool output, hidden reasoning or system messages; keys, email addresses and the local path removed) and the email says so. The app's own exporter failed for the two newest sessions, so the conversion reads the session files directly.
- Writeup (3A): `WRITEUP.md`, one page of key choices with the rejected option and the reason, ready to paste as the email body. README: what it does, a diagram, five phone screenshots, who decides what, a cost table from the real answer cache (238 cheap answers 792k/135k tokens, 51 strong answers 252k/148k tokens, all free tier), run instructions, a decision map to D-IDs, a glossary.
- Repo (2A, pending the user's go-ahead for the destructive step): make it public after removing `brief/` (the ENAM brief PDFs) from git history, which needs a history rewrite and a force push.
