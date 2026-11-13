# FINN — end-to-end build plan

> Living document. Edit freely. Every open choice points to an entry in [DECISIONS.md](DECISIONS.md) as `D-NNN`; change the decision there, then adjust the task here.

## 0. How to read this file

| Mark | Meaning |
|---|---|
| `[...]` | Plain-English explanation of a technical term |
| `{...}` | Required or explicitly asked for by the ENAM brief / reference doc |
| `D-NNN` | Link to a decision in DECISIONS.md (open = still yours to make) |
| `P0` | Must have, or the demo fails / a brief requirement is missed |
| `P1` | Differentiator: what makes it good, not just working |
| `P2` | Nice to have; first to cut |
| `[x]` / `[ ]` | Done / not done |
| est | Rough hours, for re-planning when behind |

Task IDs: **BE** back-end data · **EN** engine / AI · **API** web API · **FE** front-end · **OPS** deploy & infra · **QA** testing · **DEL** deliverables.

---

## 1. Goal and success criteria

**One line:** {a mobile-first AI agent} that acts as {a filter, not a feed}: {Push} tells the investor what changed and why it matters; {Pull} researches any company {from primary sources only}.

The demo succeeds if a reviewer, on their phone, can:
1. Open the link and see "Today": ≤5 cards that matter, routine filings collapsed {windowed digest, default 24h, user-pickable}.
2. Tap a results filing → Revenue / EBITDA / PBT / PAT with QoQ and YoY {results card}.
3. Tap a management change → who the incoming person is {bio}.
4. Change an alert threshold in Settings and see alerts change {configurable thresholds}.
5. Type a ticker we never picked → get a research view {engine works on any NSE ticker} with promise-vs-delivered {narrative vs numbers, last 4 quarters}, every claim linked to a source quote.
6. Never hit a blank screen or crash {a demo that doesn't run is the worst outcome}.

Graded on {creativity, product sense, judgment, architecture}, {not completeness}. {Thin-but-working beats broad-but-broken.}

---

## 2. Timeline (deadline {Sun 15 Nov 2026}, target send 18:00 IST)

| When | Milestone | Exit check |
|---|---|---|
| Fri 13 Nov (rest of day) | Settle P0 decisions · filings + ranker · **walking skeleton** [thinnest version of the whole system that runs end to end] deployed | Today screen with real filings opens on your phone via Render URL |
| Sat 14 Nov AM | Results card (verify 2 vs PDFs) · management-change card · Settings | Cards correct against the filing |
| Sat 14 Nov PM | Research pipeline: 1 stock end to end, then the rest of the research set + an unknown ticker | Promise tracker shows receipts |
| Sun 15 Nov AM | Styling, empty/error states, phone testing, cost numbers | Checklist §11 all green |
| Sun 15 Nov 12:00 | **Code freeze** [no new features, only fixes] | Final deploy tagged |
| Sun 15 Nov 12:00–16:00 | README, writeup, build-history links | Draft email ready |
| Sun 15 Nov by 18:00 | Send email | Sent |

If behind schedule, cut in the order given in §10.

---

## 3. Architecture

```
            ┌────────────── phone browser ──────────────┐
            │ web/index.html  (Alpine.js + Tailwind)     │
            │ Today · Detail · Research · Settings       │
            │ settings in localStorage                   │
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

Principles: rules before AI · Python does arithmetic, never the model · each document processed by AI once (cache) · every network call has timeout → retry once → fallback → snapshot.

---

## 4. Back-end: data plumbing (`data/`)

{"Get them working; don't over-engineer them — this part is plumbing, not the point."}

| ID | P | Task | Decisions | est | Done when |
|---|---|---|---|---|---|
| BE-1 | P0 | [x] {EOD price & volume} via yfinance, .NS → .BO → snapshot | D-003 | done | 18/18 load |
| BE-2 | P0 | [ ] Ticker resolver: NSE symbol → BSE scrip code [BSE's numeric company ID] + company name; reject invalid tickers with a clear message | D-013 | 1 | Works for portfolio + 2 random tickers |
| BE-3 | P0 | [ ] {Corporate announcements} fetcher: per ticker, date range, returns `{date, title, category, subcategory, pdf_url}`; browser-like headers, timeout, retry, snapshot | D-012 | 2 | 7 days of filings for all 18 stocks |
| BE-4 | P0 | [ ] Filing PDF downloader + text extractor with page numbers (pdfplumber [PDF text library]) cached by URL hash [short fingerprint of the URL] | D-021 | 1 | Text + page map for a results PDF |
| BE-5 | P0 | [ ] Fundamentals document finder: last 4 {concall transcripts} + latest {annual report} links | D-020 | 2 | Links for the research set + 1 unknown ticker |
| BE-6 | P1 | [ ] Structured quarterly numbers source for results / promise tracker | D-016 | 1.5 | 5+ quarters of Rev/EBITDA/PBT/PAT for a stock |
| BE-7 | P0 | [ ] Snapshot refresh script: one command re-freezes prices, filings, docs | D-031 | 0.5 | `python refresh_snapshot.py` runs clean |
| BE-8 | P2 | [ ] Market-holiday / weekend awareness (last trading day) | D-035 | 0.5 | Sunday demo shows Friday's session |

---

## 5. Engine / AI (`engine/`)

### 5a. Push side

| ID | P | Task | Decisions | est | Done when |
|---|---|---|---|---|---|
| EN-1 | P0 | [x] {Triggered alerts}: price ±X%, volume > N× 20-day avg | D-004, D-007 | done | 7 tests pass |
| EN-2 | P0 | [ ] Classifier: filing → one of {reference-doc categories} (+ `order_win`) using BSE category + keyword rules; leftovers → cheap model, cached | D-014, D-015 | 2 | ≥90% of a hand-checked sample of 50 correct |
| EN-3 | P0 | [ ] Ranker: tier (High / Medium / Low) from category weights in config; boost if same stock has a price/volume alert that day | D-015, D-040 | 1 | Unit tests: tiers, boost, ties |
| EN-4 | P0 | [ ] {Windowed digest} 24h / 3d / 7d: top 3–5 cards + "Routine (N)" | D-035 | 1 | Correct counts per window in tests |
| EN-5 | P0 | [ ] {Results card}: Revenue, EBITDA, PBT, PAT, {QoQ, YoY}; EBITDA = PBT + finance cost + depreciation when not printed (labelled "computed"); growth % in Python | D-016, D-017, D-018 | 4 | {Verified vs 2 actual filing PDFs} |
| EN-6 | P0 | [ ] {Management change card with incoming person's background} | D-019 | 2 | 1 real example card with source link |
| EN-7 | P1 | [ ] One-line summary for Medium-tier filings (dividend amount + record date, order value, capex size) — cheap model, cached | D-015 | 1.5 | One line per Medium card |
| EN-8 | P1 | [ ] "Why it matters" line per top card (rule template first, AI only if needed) | D-011 | 1 | No generic filler text |

### 5b. Pull side (research)

{Primary sources only: annual reports + concall transcripts. No news, broker notes, or the model's outside knowledge.}

| ID | P | Task | Decisions | est | Done when |
|---|---|---|---|---|---|
| EN-9 | P0 | [ ] `llm.py`: one function per model tier, JSON-only output, schema validation [checking the reply has the right fields and types], one retry, log model + tokens, SQLite cache keyed by (doc hash, prompt version) | D-009, D-025, D-026 | 2 | Logged call, cached second call costs 0 tokens |
| EN-10 | P0 | [ ] Chunker: split transcripts / AR into page-tagged sections; pick relevant sections by keywords (guidance, outlook, margin, capex) | D-021 | 1.5 | Feeds < N tokens per call |
| EN-11 | P0 | [ ] {Business snapshot}: what it does, segments, revenue mix — from AR, with page receipts | D-023 | 1.5 | Every bullet has a quote + page |
| EN-12 | P0 | [ ] Guidance extractor (cheap model): per quarter, list {management's explicit guidance} as `{metric, target, period, quote, page}` | D-022 | 2 | 4 quarters extracted for 1 stock |
| EN-13 | P0 | [ ] {Promise tracker / narrative vs numbers}: match each promise to actual numbers (Python) → strong model gives Delivered / Partial / Missed + reason | D-022 | 3 | Verdicts cite both quote and number |
| EN-14 | P1 | [ ] {Bull vs bear}: 3 points each, each tied to a receipt | D-023 | 1 | No claim without a source |
| EN-15 | P0 | [ ] Grounding guard: reject any claim whose quote isn't found verbatim (fuzzy match) in the source text | D-041 | 1 | Hallucinated quote test is rejected |
| EN-16 | P0 | [ ] Any-ticker path: unknown ticker → fetch docs live → progress states → cached result; demo set precomputed | D-024 | 1.5 | {Random NSE ticker} works end to end |
| EN-17 | P2 | [ ] Extra research views from the {menu}: financial snapshot / guidance list / cash quality | D-023 | 1–2 each | Optional |

---

## 6. API (`api.py`, FastAPI)

| ID | P | Endpoint / task | est | Done when |
|---|---|---|---|---|
| API-1 | P0 | [ ] `GET /` serves `web/index.html`; `GET /health` | 0.3 | Render health check green |
| API-2 | P0 | [ ] `GET /api/digest?window=24h&price=5&volume=2&cats=...` → cards + routine bucket + alerts (thresholds come from the client's localStorage) | 1 | JSON matches the screen |
| API-3 | P0 | [ ] `GET /api/card/{filing_id}` → results / management / generic detail | 1 | Lazy: AI runs only on first open, then cached |
| API-4 | P0 | [ ] `GET /api/research/{ticker}` → research JSON; `status: pending/ready/error` for slow live runs | 1.5 | Polling [the page re-asks every few seconds] works |
| API-5 | P1 | [ ] `GET /api/portfolio`, `GET /api/resolve/{ticker}` (validate a ticker) | 0.5 | Bad ticker → friendly error |
| API-6 | P1 | [ ] `GET /api/costs` → token totals per model (for the README and an "about" panel) | 0.5 | Numbers match logs |
| API-7 | P0 | [ ] Error handling: every endpoint returns `{error, fallback_used}` instead of a 500 [server crash code] | 0.5 | Kill network → app still renders snapshot |

---

## 7. Front-end (`web/index.html`, mobile-first)

{"The frontend — the product, the interaction model, the design — is deliberately yours. That's where we most want to see how you think."} {Experiment with the interaction model; show a point of view.} {No AI slop: concise, dense, beautiful, interactive.}

| ID | P | Screen / task | Decisions | est | Done when |
|---|---|---|---|---|---|
| FE-1 | P0 | [ ] Shell: bottom tab bar (Today · Research · Settings), routing [switching screens without reloading], loading skeletons [grey placeholder shapes while data loads], error and empty states | D-011, D-027 | 1.5 | Usable one-handed at 375px width |
| FE-2 | P0 | [ ] **Today**: window picker (24h/3d/7d), ≤5 "what matters" cards, alert chips on cards, "Routine (N)" collapsed row | D-011, D-035, D-040 | 2 | Reads in 10 seconds |
| FE-3 | P0 | [ ] **Detail**: results table (QoQ / YoY coloured), "computed" badges, link to source PDF; management card with bio | D-016, D-019 | 2 | Every number traceable |
| FE-4 | P0 | [ ] **Research**: ticker search box → scorecard: snapshot, promise tracker (Delivered / Partial / Missed chips), bull vs bear | D-023, D-024 | 2.5 | Works for an unknown ticker |
| FE-5 | P0 | [ ] **Receipts**: tap any claim → bottom sheet [panel sliding up from the bottom] with quote, page, document link | D-041 | 1 | 100% of claims tappable |
| FE-6 | P0 | [ ] **Settings**: price %, volume ×, category toggles, portfolio list; saved in localStorage | D-029 | 1 | Change persists after reload |
| FE-7 | P1 | [ ] Visual identity: ENAM-like palette and type, dark mode | D-028 | 1.5 | Looks deliberate, not template |
| FE-8 | P1 | [ ] PWA [Progressive Web App: "Add to Home Screen", app icon, full-screen] manifest + icon | D-030 | 0.5 | Installs on Android/iOS |
| FE-9 | P2 | [ ] Interaction experiment (pick one): "Brief me" 60-second summary · swipe-to-dismiss cards · ask-box on Today · voice read-out | D-011 | 1.5 | Demo-able in 15 seconds |
| FE-10 | P2 | [ ] "Seen" state: cards you've opened dim; "since you last looked" | D-035 | 1 | Stored in localStorage |

---

## 8. Deploy and infra (OPS)

| ID | P | Task | Decisions | est | Done when |
|---|---|---|---|---|---|
| OPS-1 | P0 | [ ] GitHub repo (push existing history), `.env.example` [template listing key names without values] | D-008, D-038 | 0.3 | Repo visible, no secrets in history |
| OPS-2 | P0 | [ ] Render web service: build `pip install -r requirements.txt`, start `uvicorn api:app` [uvicorn = the server program that runs FastAPI], env vars for keys, Python version pinned | D-032, D-034 | 1 | Public URL loads on phone |
| OPS-3 | P0 | [ ] Ship precomputed `cache.db` / snapshot in repo (Render free disk is wiped on every restart) | D-006, D-032 | 0.5 | Fresh deploy shows full demo instantly |
| OPS-4 | P0 | [ ] Cold-start mitigation [Render free sleeps after ~15 min idle; first visit waits ~1 min] | D-032 | 0.3 | Plan written into the email |
| OPS-5 | P2 | [ ] Nightly refresh (GitHub Actions [free scheduled jobs on GitHub] runs refresh script, commits snapshot) | D-031 | 1 | Optional |

---

## 9. Quality, tests, cost

| ID | P | Task | est | Done when |
|---|---|---|---|---|
| QA-1 | P0 | [x] Alert tests (7) | done | pass |
| QA-2 | P0 | [ ] {Unit tests} ranker + classifier (fixtures [small saved sample inputs] of real filing titles) | 1 | pass |
| QA-3 | P0 | [ ] QoQ / YoY / EBITDA-fallback maths tests incl. negative and zero bases | 0.5 | pass |
| QA-4 | P0 | [ ] {Verify ≥2 results cards against actual filing PDFs}; record in DECISIONS/README | 1 | Numbers match to the crore |
| QA-5 | P0 | [ ] LLM output validation tests (bad JSON, missing quote, fake quote) with a fake model [stand-in that returns canned answers, no API cost] | 1 | pass |
| QA-6 | P0 | [ ] Offline test: block network → app serves snapshot | 0.3 | Works |
| QA-7 | P0 | [ ] Real-phone test (Android + iOS if possible) on deployed URL | 0.5 | No horizontal scroll, taps ≥44px |
| QA-8 | P0 | [ ] Unknown-ticker test (2 tickers never seen) | 0.5 | Works or fails gracefully |
| QA-9 | P1 | [ ] {Cost report}: tokens per model, cost per research run, cache hit rate | 0.5 | Table in README |

---

## 10. Cut list (drop from the top when behind)

1. FE-9 interaction experiment, FE-10 seen-state
2. OPS-5 nightly refresh, EN-17 extra research views
3. FE-8 PWA, FE-7 polish (keep basic clean styling)
4. EN-14 bull vs bear
5. EN-7 Medium-tier one-liners (show filing title + link instead)
6. 3d / 7d windows (keep 24h / last session)

**Never cut:** running deploy · digest with routine collapsed · configurable alerts · results card · promise tracker for ≥1 stock with receipts · any-ticker path · README + email.

---

## 11. Deliverables ({one email to assessment@enam.com, subject "IIT Delhi – AI Engineer - 2027"})

| ID | P | Item | est | Done when |
|---|---|---|---|---|
| DEL-1 | P0 | [ ] {Working prototype usable on a phone} — deployed link | — | Opens on a phone in < 60 s, cold |
| DEL-2 | P0 | [ ] {GitHub repo} with README: what, how to run, architecture diagram, model routing, cost table, verification notes | 1.5 | A stranger can run it locally |
| DEL-3 | P0 | [ ] {AI build history}: Claude Code session exports + claude.ai chat share links | D-037 | 0.5 | Links open logged-out |
| DEL-4 | P0 | [ ] {Writeup in email body}: {what was built, key decisions and trade-offs, what was left out, next steps} — drafted from DECISIONS.md | 1 | ≤ 1 screen, links on top |
| DEL-5 | P0 | [ ] Final checklist: link works logged-out, repo public / invited, no keys in repo, subject line exact | 0.3 | All ticked |

---

## 12. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| BSE / NSE / screener block scripted requests | No filings / docs | Browser headers, backup source, committed snapshot (D-012, D-020) |
| Demo opened on a weekend → 24h window empty | First screen looks broken | Default to "since last trading session" + good empty state (D-035) |
| Render cold start / wiped disk | Slow first load, lost cache | Ship cache in repo, warm-up note, health ping (D-032) |
| AI invents numbers or quotes | Credibility | Python maths, verbatim-quote check, receipts (EN-15) |
| Results PDF layouts vary; banks differ | Wrong numbers | Structured source first, PDF verify, banks marked unsupported (D-016, D-018) |
| Free-tier rate limits [max requests per minute] on Gemini | Live research stalls | Cache, precompute demo set, back-off + clear message |
| Python 3.14 wheels missing on Render | Deploy fails | Pin 3.12 on Render, test install early (D-034) |
| Running out of time | Broken submission | Walking skeleton deployed Fri; cut list §10; code freeze Sun 12:00 |

---

## 13. Open decisions index (details in DECISIONS.md)

| ID | Decision | Recommended | Needed by |
|---|---|---|---|
| D-007 | Price alert threshold | ±5% default, ±3% one tap away | FE-6 |
| D-008 | Commit history | Real history | OPS-1 |
| D-009 | Strong model | Whichever key you have; Claude Sonnet preferred for reasoning | EN-13 |
| D-011 | Interaction model | Cards-first Today + Research search; one small experiment | FE-1 |
| D-012 | Filings source | BSE primary, NSE backup | BE-3 |
| D-013 | Ticker → BSE code mapping | BSE lookup + cached map | BE-2 |
| D-014 | Classification method | Rules + cheap-model fallback | EN-2 |
| D-015 | Category tiers | As CLAUDE.md + `order_win` split from press_release | EN-3 |
| D-016 | Results numbers source | Structured (XBRL / screener) + PDF check | EN-5 |
| D-017 | Consolidated vs standalone | Consolidated, fallback standalone, labelled | EN-5 |
| D-018 | Bank results | Mark "bank format, not supported" | EN-5 |
| D-019 | Management bio source | Filing's brief profile, AI-condensed | EN-6 |
| D-020 | Fundamentals source | screener.in links, BSE fallback | BE-5 |
| D-021 | Document chunking | Page-tagged sections + keyword retrieval | EN-10 |
| D-022 | Promise-tracker method | Two-pass: extract → Python match → strong verdict | EN-13 |
| D-023 | Research views built | Business snapshot + promise tracker + bull/bear | EN-11 |
| D-024 | Any-ticker latency | Precompute demo set, live + progress for others | EN-16 |
| D-025 | Cheap model | Gemini Flash (free tier) | EN-9 |
| D-026 | Cache key design | (doc hash, prompt version, model) | EN-9 |
| D-028 | Visual identity | ENAM-inspired, own name/logo | FE-7 |
| D-030 | Push delivery | In-app + PWA; no real notifications | FE-8 |
| D-031 | Data refresh | On request with cache time limit + snapshot | BE-7 |
| D-032 | Hosting | Render free + shipped cache | OPS-2 |
| D-033 | HAL in portfolio (defence vs ENAM values) | Your call — see entry | config |
| D-034 | Python version on deploy | 3.12 | OPS-2 |
| D-035 | Default window on weekends | "Last trading session" | EN-4 |
| D-037 | Build-history format | Claude Code export + chat share links | DEL-3 |
| D-038 | Repo visibility | Public | OPS-1 |
| D-040 | Alerts placement | Merged into Today cards | FE-2 |
| D-041 | Receipts standard | Quote + page + doc link, verbatim-checked | EN-15 |
