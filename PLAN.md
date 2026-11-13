# FINN — end-to-end build plan

> Living document. Edit freely. Every open choice points to an entry in [DECISIONS.md](DECISIONS.md) as `D-NNN`; change the decision there, then adjust the task here.
> Last revised 2026-11-14: §0 reading guide and §2 plain-language timeline. Earlier: audit v1 ([plan_revamp_v1/audit.md](plan_revamp_v1/audit.md), decisions D-043–D-056).

## 0. How to read this file

**Two questions, two kinds of section:**
- **"What is next?"** → §2 Timeline. The order of work, day by day, across all layers. Read this first.
- **"What exactly is this task?"** → §4–§9 task tables. The full list of every task in one layer of the app, with its done/not-done box. The timeline only names task IDs; the tables hold the detail.

So the timeline is not the full pipeline: it schedules the tasks from the tables. A table like §4 "Back-end: data plumbing" is the complete to-do list for that layer, including tasks already done (BE-1 `[x]`) and optional ones (P2) the timeline may never reach.

**How the file is organised**

| Section | What it is |
|---|---|
| §1 Goal | What the reviewer must be able to do on their phone. The finish line |
| §2 Timeline | When each task happens, in plain words, with a check at the end of each block |
| §3 Architecture | Picture of the layers and how data flows between them |
| §4 Back-end data plumbing (BE) | Fetching raw data: prices, filings, PDFs, documents |
| §5 Engine / AI (EN) | The brains: classify, rank, build cards, research, call AI models |
| §6 API (API) | The connection: web endpoints the phone screen calls to get data |
| §7 Front-end (FE) | The screens on the phone. Current design: `design/DESIGN_1.md` |
| §8 Deploy and infra (OPS) | Putting it online (Render), keys, GitHub |
| §9 Quality, tests, cost (QA) | Checks that it works and what it costs |
| §10 Cut list | What to drop, in order, if behind |
| §11 Deliverables (DEL) | The email and everything attached to it |
| §12 Risks | What could go wrong and the backup plan |
| §13 Decisions index | One line per decision; full text in DECISIONS.md |

**How to read a task table (§4–§11)**

| Column | Meaning |
|---|---|
| ID | Short name used everywhere, e.g. BE-3 = back-end task 3 |
| P | Priority: P0 must have · P1 makes it good · P2 nice to have, cut first |
| Task | `[x]` done / `[ ]` not done, then what to build |
| Decisions | The `D-NNN` choices this task depends on (DECISIONS.md) |
| est | Rough hours if hand-coded; advisory only (D-057) |
| Done when | The test that proves the task is finished |

**Symbols**

| Mark | Meaning |
|---|---|
| `[...]` | Plain-English explanation of a technical term |
| `{...}` | Required or explicitly asked for by the ENAM brief / reference doc |
| `D-NNN` | Link to a decision in DECISIONS.md (open = still yours to make) |
| ~~struck~~ | Removed task; ID kept so references don't break |

Task ID prefixes: **BE** back-end data · **EN** engine / AI · **API** connection between back end and screens · **FE** front-end screens · **OPS** deploy & infra · **QA** testing · **DEL** deliverables.

---

## 1. Goal and success criteria

**One line:** {a mobile-first AI agent} that acts as {a filter, not a feed}: {Push} tells the investor what changed and why it matters; {Pull} researches any company {from primary sources only}.

The demo succeeds if a reviewer, on their phone, can:
1. Open the link and see "Today": ≤5 cards that matter, routine filings collapsed {windowed digest, default 24h, user-pickable 24h / 3d / 7d}. If 24h is empty (weekend), the app widens to the last day with filings and says so (D-046).
2. Tap a results filing → Revenue / EBITDA / PBT / PAT with QoQ and YoY {results card}. Banks get a light card (D-048).
3. Tap a management change → who the incoming person is {bio}.
4. Change an alert threshold or category toggle in Settings and see alerts change {configurable thresholds} {material announcement of a type I care about}.
5. Type a ticker we never picked → get a research view {engine works on any NSE ticker} with promise-vs-delivered {narrative vs numbers, last 4 quarters}, every claim linked to a source quote.
6. Tap "Brief me" and hear a 3-sentence summary of Today (interaction experiment, D-052).
7. Never hit a blank screen or crash {a demo that doesn't run is the worst outcome}.

Graded on {creativity, product sense, judgment, architecture}, {not completeness}. {Thin-but-working beats broad-but-broken} — P0 is re-scoped to {one or two workflows nailed}: Push (digest + alerts + results card + management card) and Pull (promise tracker with receipts, any ticker) (D-043).

---

## 2. Timeline (deadline {Sun 15 Nov 2026}, target send ≤17:30 IST, hard limit 18:00)

Work top to bottom. Finish a block's "Done when" check before starting the next block. Task IDs link to the tables in §4–§11.

| # | When | Layer | What gets built, in plain words | Tasks | Done when |
|---|---|---|---|---|---|
| 0 | Fri 13 Nov | Back end + Engine | ✔ Prices for 18 stocks, price/volume alerts, tests | BE-1, EN-1 | Done |
| 0 | Sat 14 Nov AM | Planning + Design | ✔ Plan, decisions log, front-end design v1 | FE-13 | Done |
| 1 | Sat 14 Nov AM | Setup | Put AI keys in `.env` | OPS-6 | Keys load locally |
| 2 | Sat 14 Nov AM | Back end (data) | Turn a ticker into its BSE code; fetch each stock's exchange filings; swap HAL for a small-cap | BE-2, BE-3, BE-10 | 7 days of filings print for every stock |
| 3 | Sat 14 Nov AM | Engine (brains) | Label each filing with one of 17 categories (rules, no AI); rank them High / Medium / Low; apply category toggles; build the 24h / 3d / 7d digest; unit tests for ranker and classifier | EN-2, EN-3, EN-18, EN-4 | Digest prints for all portfolio stocks |
| 4 | Sat 14 Nov PM | Connection (API) | Web endpoints so the phone can ask the server for the digest and alerts; never crash, fall back to snapshot | API-1, API-2, API-7 | Browser shows JSON from `/api/digest` |
| 5 | Sat 14 Nov PM | Front end (screens) | App shell with bottom tabs; Today screen; Settings screen; ENAM colours and fonts | FE-1, FE-2, FE-6, FE-11 | Today and Settings work on a laptop at phone width |
| 6 | Sat 14 Nov PM | Deploy | Push to private GitHub; put it on Render; open on a real phone | OPS-1, OPS-2, OPS-3 | **Deploy gate Sat 20:00**: Today opens on your phone. If missed → stop features, fix deploy, apply second-stage cuts (§10) |
| 7 | Sat 14 Nov night | Engine + Testing | Results card: read the results PDF, pull Revenue / EBITDA / PBT / PAT, compute QoQ and YoY in Python; bank-lite version; check 2 cards against real PDFs; endpoint that sends a card to the phone | BE-4, EN-5, API-3, QA-3, QA-4 | Numbers match the filings |
| 8 | Sun 15 Nov 07:00–12:00 | Back end + Engine + Front end | Promise tracker: find concall transcripts, pull management's promises, match them to actual numbers, attach quotes; Detail and Research screens; research endpoint; tests that fake AI quotes are rejected; precompute 3 research stocks | BE-5, EN-9, EN-10, EN-12, EN-13, EN-15, EN-16, API-4, QA-5, FE-3, FE-4, BE-9 | A ticker we never picked works end to end |
| 9 | Sun 15 Nov 12:00–13:00 | Engine + Testing | Management change card with bio; keep Render awake; test offline fallback, on phone, and with an unknown ticker | EN-6, OPS-4, QA-6, QA-7, QA-8 | Both pass on the phone |
| 10 | Sun 15 Nov 13:00 | Freeze | **Code freeze** [no new features, only fixes]; refresh the data snapshot and commit it | BE-7 | Final deploy tagged |
| 11 | Sun 15 Nov 13:00–16:30 | Deliverables | README, writeup, AI build-history links; make repo public | DEL-2, DEL-3, DEL-4 | Draft email ready |
| 12 | Sun 15 Nov 16:30–17:30 | Deliverables | Final checklist, wake the Render server, send the email with the deployed link | DEL-1, DEL-5 | Sent; 30 min buffer to 18:00 |

**Extras only when ahead of this timeline:** P1 tasks such as "Brief me" (FE-9) and the P1 picks in `design/DESIGN_1.md`, slotted after the block they belong to. If behind, cut in the order in §10.

**Hours check:** P0 ≈ 53h at hand-coding estimates. Claude Code writes the code, so wall-clock should be far lower — but that is an assumption. The Sat 20:00 deploy gate is the real check.

---

## 3. Architecture

```
            ┌────────────── phone browser ──────────────┐
            │ web/index.html  (Alpine.js + Tailwind)     │
            │ Today · Detail · Research · Settings       │
            │ settings in localStorage · "Brief me"      │
            └───────────────▲───────────────────────────┘
                            │ JSON over HTTPS
┌───────────────────────────┴──────────────────────────────────┐
│ api.py  (FastAPI)                                            │
│  /api/digest  /api/alerts  /api/card/{id}  /api/research/{t} │
├──────────────────────────────────────────────────────────────┤
│ engine/   alerts.py ✔  classifier.py  ranker.py  cards.py    │
│           research.py   llm.py (routing, JSON check, logs)   │
├──────────────────────────────────────────────────────────────┤
│ data/     prices.py ✔  filings.py  docs.py  symbols.py       │
├──────────────────────────────────────────────────────────────┤
│ cache.db (SQLite: AI answers + parsed docs)  snapshot/ (JSON)│
└──────────────────────────────────────────────────────────────┘
   yfinance        BSE / NSE announcements      screener.in / PDFs
   Gemini Flash (cheap, bulk)        strong model (reasoning only)
```

Principles: rules before AI · Python does arithmetic, never the model · each document processed by AI once (cache) · every network call has timeout → retry once → fallback → snapshot · results filings are the single source of quarterly numbers for both the results card and the promise tracker (D-049).

---

## 4. Back-end: data plumbing (`data/`)

{"Get them working; don't over-engineer them — this part is plumbing, not the point."}

| ID | P | Task | Decisions | est | Done when |
|---|---|---|---|---|---|
| BE-1 | P0 | [x] {EOD price & volume} via yfinance, .NS → .BO → snapshot | D-003 | done | 18/18 load |
| BE-2 | P0 | [ ] Ticker resolver: NSE symbol → BSE scrip code [BSE's numeric company ID] + company name; reject invalid tickers with a clear message | D-013 | 1 | Works for portfolio + 2 random tickers |
| BE-3 | P0 | [ ] {Corporate announcements} fetcher: per ticker, date range, returns `{date, title, category, subcategory, pdf_url}`; browser-like headers, timeout, retry, snapshot | D-012 | 2 | 7 days of filings for all portfolio stocks |
| BE-4 | P0 | [ ] Filing PDF downloader + text extractor with page numbers (pdfplumber [PDF text library]) cached by URL hash [short fingerprint of the URL] | D-021 | 1 | Text + page map for a results PDF |
| BE-5 | P0 | [ ] Fundamentals document finder: last 4 {concall transcripts} + latest {annual report} links, plus last 5 results-filing links (for EN-13 actuals) | D-020, D-049 | 2 | Links for the research set + 1 unknown ticker |
| ~~BE-6~~ | — | ~~Structured quarterly numbers source~~ — removed: actuals come from the EN-5 extractor on results filings (primary) | D-049 | 0 | — |
| BE-7 | P0 | [ ] Snapshot refresh script: one command re-freezes prices, filings, docs; **run Sun 13:00 and commit** | D-031, D-053 | 0.5 | `python refresh_snapshot.py` runs clean |
| BE-8 | P2 | [ ] Market-holiday calendar (exact last trading day) — not needed for D-046 fallback, which uses "last day with filings" | D-046 | 0.5 | Optional |
| BE-9 | P0 | [ ] Finalise research set of 3 {3–5, may be outside portfolio}: POLYCAB, PERSISTENT, ASTRAL (outside); verify ASTRAL loads; precompute all 3 after EN-16 | D-051 | 0.2 | 3 research views load instantly from cache |
| BE-10 | P0 | [ ] Replace HAL in `config.py` with a non-defence small-cap that loads in yfinance (adds {"sizes"} mix; ENAM values) | D-055 | 0.2 | 18 still load; choice logged in DECISIONS |

---

## 5. Engine / AI (`engine/`)

### 5a. Push side

| ID | P | Task | Decisions | est | Done when |
|---|---|---|---|---|---|
| EN-1 | P0 | [x] {Triggered alerts}: price ±X%, volume > N× 20-day avg | D-004, D-007 | done | 7 tests pass |
| EN-2 | P0 | [ ] Classifier, **rules only**: filing → one of {reference-doc categories} (+ `order_win`) using BSE category + keywords; unmatched → `unclassified` | D-014, D-015, D-043 | 1.5 | ≥90% of a hand-checked sample of 50 correct |
| EN-3 | P0 | [ ] Ranker: tier (High / Medium / Low) from category weights in config; boost if same stock has a price/volume alert that day | D-015, D-040 | 1 | Unit tests: tiers, boost, ties |
| EN-4 | P0 | [ ] {Windowed digest} {24h default} / 3d / 7d: top 3–5 cards + "Routine (N)"; if 24h is empty, widen to the most recent day with filings and return a `widened` flag for the banner | D-045, D-046 | 1 | Tests: counts per window; empty-24h case widens |
| EN-5 | P0 | [ ] {Results card}: Revenue, EBITDA, PBT, PAT, {QoQ, YoY}; growth % in Python. EBITDA if not printed = PBT + finance cost + D&A − other income, labelled "computed". Banks: Total income / PBT / PAT, EBITDA "n/a for banks". Extractor reused by EN-13 | D-016, D-017, D-048, D-049, D-054 | 4.5 | {Verified vs 2 actual filing PDFs} + 1 bank card |
| EN-6 | P0 | [ ] {Management change card with incoming person's background} | D-019 | 2 | 1 real example card with source link |
| EN-7 | P1 | [ ] One-line summary for Medium-tier filings (dividend amount + record date, order value, capex size) — cheap model, cached | D-015 | 1.5 | One line per Medium card |
| EN-8 | P1 | [ ] "Why it matters" line per top card (rule template first, AI only if needed) | D-011 | 1 | No generic filler text |
| EN-18 | P0 | [ ] Category toggles {"a material announcement of a type I care about"}: toggled-off category → Routine; toggled-on High category → "alert" chip; toggles passed from localStorage via API-2 | D-047 | 0.5 | Ranker tests cover on/off |
| EN-19 | P2 | [ ] Cheap-model fallback for `unclassified` filings, cached (was part of EN-2) | D-014, D-043 | 1 | Unclassified share drops on sample |

### 5b. Pull side (research)

{Primary sources only: annual reports + concall transcripts. No news, broker notes, or the model's outside knowledge.}

| ID | P | Task | Decisions | est | Done when |
|---|---|---|---|---|---|
| EN-9 | P0 | [ ] `llm.py`: one function per model tier, JSON-only output, schema validation [checking the reply has the right fields and types], one retry, log model + tokens, SQLite cache keyed by (doc hash, prompt version, model) | D-009, D-025, D-026 | 2 | Logged call, cached second call costs 0 tokens |
| EN-10 | P0 | [ ] Chunker: split transcripts / AR into page-tagged sections; pick relevant sections by keywords (guidance, outlook, margin, capex) | D-021 | 1.5 | Feeds < N tokens per call |
| EN-11 | P1 | [ ] {Business snapshot}: what it does, segments, revenue mix — from AR, with page receipts (demoted from P0) | D-023, D-043 | 1.5 | Every bullet has a quote + page |
| EN-12 | P0 | [ ] Guidance extractor (cheap model): per quarter, list {management's explicit guidance} as `{metric, target, period, quote, page}` | D-022 | 2 | 4 quarters extracted for 1 stock |
| EN-13 | P0 | [ ] {Promise tracker / narrative vs numbers}: actual numbers from EN-5 extractor on last 4–5 results filings (Python) → strong model gives Delivered / Partial / Missed + reason | D-022, D-049 | 3 | Verdicts cite both quote and number |
| EN-14 | P1 | [ ] {Bull vs bear}: 3 points each, each tied to a receipt | D-023 | 1 | No claim without a source |
| EN-15 | P0 | [ ] Grounding guard: reject any claim whose quote isn't found verbatim (fuzzy match) in the source text | D-041 | 1 | Hallucinated quote test is rejected |
| EN-16 | P0 | [ ] Any-ticker path: unknown ticker → fetch docs live → progress states → cached result; research set (BE-9) precomputed | D-024, D-051 | 1.5 | {Random NSE ticker} works end to end |
| EN-17 | P2 | [ ] Extra research views from the {menu}: financial snapshot / guidance list / cash quality | D-023 | 1–2 each | Optional |

---

## 6. API (`api.py`, FastAPI)

| ID | P | Endpoint / task | est | Done when |
|---|---|---|---|---|
| API-1 | P0 | [ ] `GET /` serves `web/index.html`; `GET /health` | 0.3 | Render health check green |
| API-2 | P0 | [ ] `GET /api/digest?window=24h&price=5&volume=2&cats=...` → cards + routine bucket + alerts + `widened` flag (thresholds and toggles come from the client's localStorage) | 1 | JSON matches the screen |
| API-3 | P0 | [ ] `GET /api/card/{filing_id}` → results / bank-lite / management / generic detail | 1 | Lazy: AI runs only on first open, then cached |
| API-4 | P0 | [ ] `GET /api/research/{ticker}` → research JSON; `status: pending/ready/error` for slow live runs | 1.5 | Polling [the page re-asks every few seconds] works |
| API-5 | P1 | [ ] `GET /api/portfolio`, `GET /api/resolve/{ticker}` (validate a ticker) | 0.5 | Bad ticker → friendly error |
| API-6 | P1 | [ ] `GET /api/costs` → token totals per model (for the README and an "about" panel) | 0.5 | Numbers match logs |
| API-7 | P0 | [ ] Error handling: every endpoint returns `{error, fallback_used}` instead of a 500 [server crash code] | 0.5 | Kill network → app still renders snapshot |

---

## 7. Front-end (`web/index.html`, mobile-first)

{"The frontend — the product, the interaction model, the design — is deliberately yours. That's where we most want to see how you think."} {Experiment with the interaction model; show a point of view.} {No AI slop: concise, dense, beautiful, interactive.}

**Current design: `design/DESIGN_1.md` (D-059). Read it before building or deciding any front-end task**; it lists the picks per screen, their tier and the build order. Visual baseline: `design/mockups_v0.html`. Idea history: `design/FRONTEND_BRAINSTORM.md`. A later design change = new `design/DESIGN_N.md` + DECISIONS.md entry + update this line.

| ID | P | Screen / task | Decisions | est | Done when |
|---|---|---|---|---|---|
| FE-1 | P0 | [ ] Shell: bottom tab bar (Today · Research · Settings), routing [switching screens without reloading], loading skeletons [grey placeholder shapes while data loads], error and empty states | D-011, D-027 | 1.5 | Usable one-handed at 375px width |
| FE-2 | P0 | [ ] **Today**: window picker (24h/3d/7d), ≤5 "what matters" cards, alert chips on cards, "Routine (N)" collapsed row, "widened" banner | D-040, D-045, D-046 | 2 | Reads in 10 seconds |
| FE-3 | P0 | [ ] **Detail**: results table (QoQ / YoY coloured), "computed" badges, bank-lite variant, link to source PDF; management card with bio | D-016, D-019, D-048 | 2 | Every number traceable |
| FE-4 | P0 | [ ] **Research**: ticker search box → scorecard: promise tracker (Delivered / Partial / Missed chips), snapshot + bull vs bear if built; **receipts included** (tap claim → bottom sheet [panel sliding up from the bottom] with quote, page, link) | D-023, D-024, D-041 | 3 | Works for an unknown ticker; 100% of claims tappable |
| ~~FE-5~~ | — | ~~Receipts~~ — merged into FE-4 | D-043 | 0 | — |
| FE-6 | P0 | [ ] **Settings**: price %, volume ×, category toggles (EN-18), portfolio list; saved in localStorage | D-029, D-047 | 1 | Change persists after reload |
| FE-7 | P1 | [ ] Visual polish on top of FE-11: spacing, type scale, dark mode | D-028, D-044 | 1 | Looks deliberate, not template |
| FE-8 | P1 | [ ] PWA [Progressive Web App: "Add to Home Screen", app icon, full-screen] manifest + icon | D-030 | 0.5 | Installs on Android/iOS |
| FE-9 | P1 | [ ] Interaction experiment: **"Brief me"** — 3-sentence summary of Today, shown and read aloud via Web Speech API [browser's built-in, free text-to-speech]; built from digest data, no extra AI call | D-011, D-052 | 1.5 | Demo-able in 15 seconds |
| FE-10 | P2 | [ ] "Seen" state: cards you've opened dim; "since you last looked" | D-046 | 1 | Stored in localStorage |
| FE-11 | P0 | [ ] ENAM theme tokens: take colours and fonts from ENAM's website into CSS variables [named colour/font settings reused everywhere]; own FINN wordmark, no ENAM logo | D-028, D-044 | 0.5 | All screens use the tokens |
| FE-12 | P1 | [ ] **On hold — review after the front-end brainstorm**: (a) the 6-screen set (Today, Results, Management change, Settings, Research, Promise tracker; one per brief item), (b) 17 categories → High / Medium / Low tiers. Decisions stand for the build; redesign only if the brainstorm shows a better structure | D-015, D-058 | 0.5 | Reviewed; kept or changed with a DECISIONS.md entry |
| FE-13 | P0 | [x] Front-end design v1 decided: recommended picks + 4 M-effort picks + push→pull link → `design/DESIGN_1.md` | D-059 | 0 | Done 2026-11-14 |

---

## 8. Deploy and infra (OPS)

| ID | P | Task | Decisions | est | Done when |
|---|---|---|---|---|---|
| OPS-1 | P0 | [ ] GitHub repo (push existing history), `.env.example` [template listing key names without values] | D-008, D-038 | 0.3 | Repo visible, no secrets in history |
| OPS-2 | P0 | [ ] Render web service: build `pip install -r requirements.txt`, start `uvicorn api:app` [uvicorn = the server program that runs FastAPI], env vars for keys, Python version pinned | D-032, D-034 | 1 | Public URL loads on phone |
| OPS-3 | P0 | [ ] Ship precomputed `cache.db` / snapshot in repo (Render free disk is wiped on every restart) | D-006, D-032 | 0.5 | Fresh deploy shows full demo instantly |
| OPS-4 | P0 | [ ] Cold-start mitigation [Render free sleeps after ~15 min idle; first visit waits ~1 min] | D-032 | 0.3 | Plan written into the email |
| OPS-5 | P2 | [ ] Nightly refresh (GitHub Actions [free scheduled jobs on GitHub] runs refresh script, commits snapshot) | D-031 | 1 | Optional |
| OPS-6 | P0 | [x] API keys: free Gemini key only (D-060) → `.env` locally; Render env var still to set at deploy; smoke test `py smoke_test_llm.py` passes (cheap via 3.5-flash-lite; strong fell back to 3.1-flash-lite under overload). `engine/llm.py` basic version (retry, fallback, token log) exists; EN-9 still owns JSON schema + SQLite cache | D-009, D-050, D-060, D-061 | 0.3 | Done 2026-11-14 |

---

## 9. Quality, tests, cost

| ID | P | Task | est | Done when |
|---|---|---|---|---|
| QA-1 | P0 | [x] Alert tests (7) | done | pass |
| QA-2 | P0 | [ ] {Unit tests} ranker + classifier + category toggles (fixtures [small saved sample inputs] of real filing titles) | 1 | pass |
| QA-3 | P0 | [ ] QoQ / YoY / EBITDA-fallback (incl. other income) maths tests, incl. negative and zero bases; bank-lite case | 0.5 | pass |
| QA-4 | P0 | [ ] {Verify ≥2 results cards against actual filing PDFs}; record in DECISIONS/README | 1 | Numbers match to the crore |
| QA-5 | P0 | [ ] LLM output validation tests (bad JSON, fake quote) with a fake model [stand-in that returns canned answers, no API cost] | 0.5 | pass |
| QA-6 | P0 | [ ] Offline test: block network → app serves snapshot | 0.3 | Works |
| QA-7 | P0 | [ ] Real-phone test (Android + iOS if possible) on deployed URL | 0.5 | No horizontal scroll, taps ≥44px |
| QA-8 | P0 | [ ] Unknown-ticker test (2 tickers never seen) | 0.5 | Works or fails gracefully |
| QA-9 | P1 | [ ] {Cost report}: tokens per model, cost per research run, cache hit rate | 0.5 | Table in README |

---

## 10. Cut list (drop from the top when behind)

1. FE-10 seen-state, EN-19 classifier AI fallback
2. OPS-5 nightly refresh, EN-17 extra research views
3. FE-8 PWA, FE-7 polish (FE-11 theme tokens stay)
4. FE-9 "Brief me" experiment
5. EN-14 bull vs bear, EN-11 business snapshot
6. EN-7 Medium-tier one-liners (show filing title + link instead)

~~3d / 7d windows~~ removed from the cut list: {"let me pick the period"} is brief-required (D-045).

**Second-stage cuts — only if the Sat 20:00 deploy gate is missed (D-043):** EN-6 management card → filing title + link only · FE-3 results table without colour/badges · QA-2 reduced to ranker only.

**Never cut:** running deploy · digest with routine collapsed + 24h/3d/7d picker · configurable alerts + category toggles · results card · promise tracker for ≥1 stock with receipts · any-ticker path · FE-11 theme tokens · README + email.

---

## 11. Deliverables ({one email to assessment@enam.com, subject "IIT Delhi – AI Engineer - 2027"})

| ID | P | Item | est | Done when |
|---|---|---|---|---|
| DEL-1 | P0 | [ ] {Working prototype usable on a phone} — deployed link | — | Opens on a phone in < 60 s, cold |
| DEL-2 | P0 | [ ] {GitHub repo} with README: what, how to run, architecture diagram, model routing, cost table, verification notes | 1.5 | A stranger can run it locally |
| DEL-3 | P0 | [ ] {AI build history}: Claude Code session exports + claude.ai chat share links | D-037 | 0.5 | Links open logged-out |
| DEL-4 | P0 | [ ] {Writeup in email body}: {what was built, key decisions and trade-offs, what was left out, next steps} — drafted from DECISIONS.md | 1 | ≤ 1 screen, links on top |
| DEL-5 | P0 | [ ] Final checklist: snapshot + cache refreshed and committed (D-053) · Render warmed up · link works logged-out · repo public / invited · no keys in repo · subject line exact | 0.3 | All ticked |

---

## 12. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| BSE / NSE / screener block scripted requests | No filings / docs | Browser headers, backup source, committed snapshot (D-012, D-020) |
| Demo opened on a weekend → 24h window empty | First screen looks broken | {24h default}, auto-widen to last filing day with banner (D-046) |
| Render cold start / wiped disk | Slow first load, lost cache | Ship cache in repo, warm-up before sending, note in email (D-032, D-053) |
| AI invents numbers or quotes | Credibility | Python maths, verbatim-quote check, receipts (EN-15) |
| Results PDF layouts vary; banks differ | Wrong numbers | Arithmetic checks, PDF verify, bank-lite card (D-016, D-048) |
| Free-tier rate limits [max requests per minute] on Gemini | Live research stalls | Cache, precompute research set, back-off + clear message |
| Python 3.14 wheels missing on Render | Deploy fails | Pin 3.12 on Render, test install early (D-034) |
| Running out of time | Broken submission | Deploy gate Sat 20:00 · second-stage cuts · code freeze Sun 13:00 · send ≤17:30 (D-043) |

---

## 13. Decisions index (details in DECISIONS.md)

| ID | Decision | State / recommendation | Needed by |
|---|---|---|---|
| D-007 | Price alert threshold | Open — ±5% default, ±3% one tap away | FE-6 |
| D-008 | Commit history | Open — real history | OPS-1 |
| D-009 | Strong model | **Decided** (D-060, D-061) — Gemini 3.5 Flash on the free tier; no Pro or Claude | OPS-6, EN-13 |
| D-011 | Interaction model | **Decided via D-052** — cards-first + "Brief me" | FE-1, FE-9 |
| D-012 | Filings source | Open — BSE primary, NSE backup | BE-3 |
| D-013 | Ticker → BSE code mapping | Open — shipped scrip list + lookup | BE-2 |
| D-014 | Classification method | **Rules only for P0 (D-043)**; AI fallback = EN-19 | EN-2 |
| D-015 | Category tiers | **Decided** — adapt: 17 categories → High / Medium / Low; review in FE-12 | EN-3 |
| D-016 | Results numbers source | Open — PDF extraction with arithmetic checks; screener option dropped (D-049) | EN-5 |
| D-017 | Consolidated vs standalone | Open — consolidated, fallback standalone, labelled | EN-5 |
| D-018 | Bank results | **Decided via D-048** — bank-lite card | EN-5 |
| D-019 | Management bio source | Open — filing's brief profile, AI-condensed | EN-6 |
| D-020 | Fundamentals source | Open — screener.in links, BSE fallback | BE-5 |
| D-021 | Document chunking | Open — page-tagged sections + keywords | EN-10 |
| D-022 | Promise-tracker method | Open — two-pass | EN-13 |
| D-023 | Research views built | Open — promise tracker P0; snapshot + bull/bear P1 (D-043) | EN-11 |
| D-024 | Any-ticker latency | Open — precompute research set, live + progress | EN-16 |
| D-025 | Cheap model | Open — Gemini Flash | EN-9 |
| D-026 | Cache key design | Open — (doc hash, prompt version, model) | EN-9 |
| D-028 | Visual identity | **Decided via D-044** — ENAM colours/fonts as tokens, own wordmark | FE-11 |
| D-030 | Push delivery | Open — in-app + PWA | FE-8 |
| D-031 | Data refresh | Open — on request with TTL + manual script | BE-7 |
| D-032 | Hosting | Open — Render free + shipped cache | OPS-2 |
| D-033 | HAL in portfolio | **Decided via D-055** — replace with non-defence small-cap | BE-10 |
| D-034 | Python version on deploy | Open — 3.12 | OPS-2 |
| D-035 | Default window | **Superseded by D-046** — 24h + auto-widen | EN-4 |
| D-037 | Build-history format | Open — export + share links | DEL-3 |
| D-038 | Repo visibility | Open — public | OPS-1 |
| D-040 | Alerts placement | Open — merged into Today cards | FE-2 |
| D-041 | Receipts standard | Open — verified quote + page + link | EN-15 |
| D-043–D-056 | Audit v1 changes | Decided 2026-11-14 | see DECISIONS.md |
| D-058 | Screen set | **Decided, on hold for review** — 6 screens, one per brief item; review in FE-12 | FE-1..6 |
| D-059 | Front-end design v1 | **Decided** — `design/DESIGN_1.md` is the current design | FE-1..13 |
| D-060 | Free-tier-only AI keys | **Decided** — one free Gemini key, no billing, no Anthropic | OPS-6 |
| D-061 | Free-tier model lineup | **Decided** — cheap 3.5-flash-lite, strong 3.5-flash, fallback 3.1-flash-lite | OPS-6, EN-9 |
