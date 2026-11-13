# FINN — end-to-end build plan

> Living document. Edit freely. Every open choice points to an entry in [DECISIONS.md](DECISIONS.md) as `D-NNN`; change the decision there, then adjust the task here.
> Last revised 2026-11-14 after audit v1 ([plan_revamp_v1/audit.md](plan_revamp_v1/audit.md), decisions D-043–D-056).

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
| ~~struck~~ | Removed task; ID kept so references don't break |
| est | Rough hand-coding hours, for re-planning when behind |

Task IDs: **BE** back-end data · **EN** engine / AI · **API** web API · **FE** front-end · **OPS** deploy & infra · **QA** testing · **DEL** deliverables.

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

| When | Milestone | Exit check |
|---|---|---|
| Sat 14 Nov AM | OPS-6 keys · BE-2/3 filings · BE-10 HAL swap · EN-2 rules classifier · EN-3 + EN-18 ranker/toggles · EN-4 digest | Digest prints for all portfolio stocks |
| Sat 14 Nov PM | API-1/2/7 · FE-1/2/6/11 Today + Settings + theme tokens · OPS-1/2/3 deploy | **Deploy gate Sat 20:00**: Today opens on your phone via Render URL. If missed → stop features, fix deploy, apply second-stage cuts (§10) |
| Sat 14 Nov night | EN-5 results card (+ bank-lite) · QA-3 · QA-4 verify 2 PDFs | Numbers match filings |
| Sun 15 Nov 07:00–12:00 | EN-9/10/12/13/15/16 promise tracker · FE-3/4 Detail + Research · BE-9 precompute 3 research stocks | Unknown ticker works end to end |
| Sun 15 Nov 12:00–13:00 | EN-6 management card · QA-7/8 phone + unknown-ticker tests | |
| Sun 15 Nov 13:00 | **Code freeze** [no new features, only fixes] · BE-7 snapshot refresh, commit cache (D-053) | Final deploy tagged |
| Sun 15 Nov 13:00–16:30 | DEL-2/3/4 README, writeup, build-history links | Draft email ready |
| Sun 15 Nov 16:30–17:30 | DEL-5 checklist, warm Render, send | Sent; 30 min buffer to 18:00 |

**Hours check:** P0 ≈ 53h at hand-coding estimates. Claude Code writes the code, so wall-clock should be far lower — but that is an assumption. The Sat 20:00 deploy gate is the real check. If behind, cut in the order given in §10.

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

---

## 8. Deploy and infra (OPS)

| ID | P | Task | Decisions | est | Done when |
|---|---|---|---|---|---|
| OPS-1 | P0 | [ ] GitHub repo (push existing history), `.env.example` [template listing key names without values] | D-008, D-038 | 0.3 | Repo visible, no secrets in history |
| OPS-2 | P0 | [ ] Render web service: build `pip install -r requirements.txt`, start `uvicorn api:app` [uvicorn = the server program that runs FastAPI], env vars for keys, Python version pinned | D-032, D-034 | 1 | Public URL loads on phone |
| OPS-3 | P0 | [ ] Ship precomputed `cache.db` / snapshot in repo (Render free disk is wiped on every restart) | D-006, D-032 | 0.5 | Fresh deploy shows full demo instantly |
| OPS-4 | P0 | [ ] Cold-start mitigation [Render free sleeps after ~15 min idle; first visit waits ~1 min] | D-032 | 0.3 | Plan written into the email |
| OPS-5 | P2 | [ ] Nightly refresh (GitHub Actions [free scheduled jobs on GitHub] runs refresh script, commits snapshot) | D-031 | 1 | Optional |
| OPS-6 | P0 | [ ] API keys: Gemini key (free tier) + Anthropic key if available → `.env` locally, Render env vars; smoke test [one tiny call per model to prove the key works] | D-009, D-050 | 0.3 | Both calls return; nothing committed |

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
| Running out of time (P0 ≈ 53h at estimates) | Broken submission | Deploy gate Sat 20:00 · second-stage cuts · code freeze Sun 13:00 · send ≤17:30 (D-043) |

---

## 13. Decisions index (details in DECISIONS.md)

| ID | Decision | State / recommendation | Needed by |
|---|---|---|---|
| D-007 | Price alert threshold | Open — ±5% default, ±3% one tap away | FE-6 |
| D-008 | Commit history | Open — real history | OPS-1 |
| D-009 | Strong model | Open — whichever key you have; Claude Sonnet preferred | OPS-6, EN-13 |
| D-011 | Interaction model | **Decided via D-052** — cards-first + "Brief me" | FE-1, FE-9 |
| D-012 | Filings source | Open — BSE primary, NSE backup | BE-3 |
| D-013 | Ticker → BSE code mapping | Open — shipped scrip list + lookup | BE-2 |
| D-014 | Classification method | **Rules only for P0 (D-043)**; AI fallback = EN-19 | EN-2 |
| D-015 | Category tiers | Open — as CLAUDE.md + `order_win` | EN-3 |
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
